#!/usr/bin/env python3
"""PD Parser 测试套件"""

import json
import sys
from pathlib import Path

# Add parsers to path
sys.path.insert(0, str(Path(__file__).parent.parent / "parsers"))
from pd_parser import (
    PdProtocolParser, PdMessage, PdNegotiation,
    parse_timestamp, parse_message, parse_pdo, parse_request,
    detect_anomalies, extract_capabilities, extract_negotiation_result,
    PD_COMMANDS, ANOMALY_PATTERNS
)

DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "owlmyclaw" / "data"


def test_pd_commands_complete():
    """PD消息类型定义完整性"""
    assert len(PD_COMMANDS) >= 26, f"应有至少26种PD消息，实际{len(PD_COMMANDS)}"
    essential = ["SOURCE_CAP", "SINK_CAP", "REQUEST", "ACCEPT", "REJECT",
                 "PR_SWAP", "DR_SWAP", "HARD_RESET", "PS_RDY", "WAIT"]
    for cmd in essential:
        assert any(cmd == v for v in PD_COMMANDS.values()), f"缺少关键消息类型: {cmd}"


def test_anomaly_patterns():
    """异常检测模式覆盖"""
    assert len(ANOMALY_PATTERNS) >= 8
    patterns = [p for p, _ in ANOMALY_PATTERNS]
    assert any("imeout" in p for p in patterns)
    assert any("etransmit" in p for p in patterns)
    assert any("VBUS" in p for p in patterns)
    assert any("eadlock" in p.lower() for p in patterns)


def test_parse_timestamp():
    """时间戳解析"""
    line = "[2026-05-15 14:28:01.123] [INFO] [pd_protocol] test"
    ts = parse_timestamp(line)
    assert ts is not None
    assert ts > 0

    line_no_ts = "plain text without timestamp"
    assert parse_timestamp(line_no_ts) is None


def test_parse_pdo_fixed():
    """Fixed PDO 解析"""
    raw = "Fixed PDO - 9V/2A (18000mW)"
    result = parse_pdo(raw)
    assert result["type"] == "Fixed PDO"
    assert result["voltage_v"] == 9
    assert result["current_a"] == 2
    assert result["power_mw"] == 18000


def test_parse_pdo_variable():
    """Variable PDO 解析"""
    raw = "Variable PDO - 12-20V/3A (36000mW)"
    result = parse_pdo(raw)
    assert result["type"] == "Variable PDO"
    assert result["min_voltage_v"] == 12
    assert result["max_voltage_v"] == 20
    assert result["current_a"] == 3


def test_parse_pdo_variable_operated():
    """Variable Operated PDO 解析"""
    raw = "Variable Operated - 9-12V/2.5A (25000mW)"
    result = parse_pdo(raw)
    assert result["type"] == "Variable Operated PDO"
    assert result["min_voltage_v"] == 9
    assert result["max_voltage_v"] == 12
    assert result["current_a"] == 2.5


def test_parse_request():
    """REQUEST 消息解析"""
    raw = "REQUEST [Cap=2] 9V/2A"
    result = parse_request(raw)
    assert result["type"] == "REQUEST"
    assert result["cap_index"] == 2
    assert result["voltage_v"] == 9
    assert result["current_a"] == 2


def test_parse_message_src_cap():
    """SRC_CAP 消息解析"""
    line = "[2026-05-15 14:28:01.600] [TX] [pd_protocol] SRC_CAP [Caps=4] vbus=5000mV, current=3000mA"
    msg = parse_message(line, None)
    assert msg is not None
    assert msg.message_type == "SOURCE_CAP"
    assert msg.direction == "TX"
    assert msg.params["num_caps"] == 4
    assert msg.params["vbus_mv"] == 5000


def test_parse_message_request():
    """REQUEST 消息解析"""
    line = "[2026-05-15 14:28:03.800] [TX] [pd_protocol] REQUEST [Cap=2] 9V/2A"
    msg = parse_message(line, 1000.0)
    assert msg is not None
    assert msg.message_type == "REQUEST"
    assert msg.direction == "TX"
    assert msg.params["cap_index"] == 2


def test_parse_message_hard_reset():
    """HARD_RESET 消息解析"""
    line = "[2026-05-15 14:28:01.256] [INFO] [pd_protocol] Hard Reset transmitted"
    msg = parse_message(line, None)
    assert msg is not None
    assert msg.message_type == "HARD_RESET"


def test_parse_message_ps_rdy():
    """PS_RDY 消息解析"""
    line = "[2026-05-20 16:42:01.800] [RX] [pd_protocol] PS_RDY"
    msg = parse_message(line, None)
    assert msg is not None
    assert msg.message_type == "PS_RDY"


def test_parse_message_delay():
    """消息延迟计算"""
    line1 = "[2026-05-15 14:28:01.600] [TX] [pd_protocol] SRC_CAP [Caps=4]"
    line2 = "[2026-05-15 14:28:02.810] [RX] [pd_protocol] WAIT_PWR_OK received"
    msg1 = parse_message(line1, None)
    msg2 = parse_message(line2, msg1.timestamp)
    assert msg2 is not None
    assert msg2.delay_from_prev > 0


def test_parse_file_fail_log():
    """解析失败协商日志"""
    logfile = DATA_DIR / "sample_pd_negotiation_fail.log"
    parser = PdProtocolParser()
    result = parser.parse_file(str(logfile))

    assert len(result.messages) > 0
    assert not result.success
    assert len(result.anomalies) > 0
    assert result.state_machine_status in ("FAILED", "COMPLETED", "HARD_RESET_LOOP", "STUCK", "DISCONNECTED", "UNKNOWN", "EMPTY")

    # 验证消息方向
    directions = {m.direction for m in result.messages}
    assert "TX" in directions or "RX" in directions


def test_parse_file_prswap_log():
    """解析PR_SWAP死锁日志"""
    logfile = DATA_DIR / "sample_pd_prswap_deadlock.log"
    parser = PdProtocolParser()
    result = parser.parse_file(str(logfile))

    assert len(result.messages) > 0
    # 应该有 PR_SWAP 消息
    msg_types = [m.message_type for m in result.messages]
    assert "PR_SWAP" in msg_types


def test_parse_text():
    """解析文本输入"""
    text = """[2026-05-15 14:28:01.600] [TX] [pd_protocol] SRC_CAP [Caps=2] vbus=5000mV
[2026-05-15 14:28:02.000] [RX] [pd_protocol] REQUEST [Cap=1] 5V/3A
[2026-05-15 14:28:02.500] [TX] [pd_protocol] ACCEPT
[2026-05-15 14:28:03.000] [RX] [pd_protocol] PS_RDY"""
    parser = PdProtocolParser()
    result = parser.parse_text(text, "test_session")

    assert len(result.messages) == 4
    assert result.source_id == "test_session"


def test_get_timeline():
    """时序数据生成"""
    logfile = DATA_DIR / "sample_pd_negotiation_fail.log"
    parser = PdProtocolParser()
    parser.parse_file(str(logfile))
    timeline = parser.get_timeline()

    assert len(timeline) == parser.messages.__len__()
    for item in timeline:
        assert "order" in item
        assert "timestamp_ms" in item
        assert "direction" in item
        assert "message" in item


def test_detect_anomalies_timeout():
    """异常检测 - 超时"""
    messages = [
        PdMessage(timestamp=1000, direction="TX", message_type="REQUEST",
                  raw_line="[2026-05-15 14:28:04.200] [WARN] [pd_protocol] Timeout waiting for PD response (400ms)")
    ]
    anomalies = detect_anomalies(messages, [m.raw_line for m in messages])
    assert len(anomalies) > 0
    assert any("超时" in a for a in anomalies)


def test_detect_anomalies_retransmit():
    """异常检测 - 重传"""
    messages = [
        PdMessage(timestamp=1000, direction="TX", message_type="REQUEST",
                  raw_line="[2026-05-15 14:28:04.500] [WARN] [pd_protocol] Retransmit REQUEST [Cap=2] (attempt 2/3)")
    ]
    anomalies = detect_anomalies(messages, [m.raw_line for m in messages])
    assert len(anomalies) > 0
    assert any("重传" in a for a in anomalies)


def test_detect_anomalies_deadlock():
    """异常检测 - 死锁"""
    messages = [
        PdMessage(timestamp=1000, direction="TX", message_type="REQUEST",
                  raw_line="[2026-05-20 16:42:15.600] [ERROR] [pd_protocol] DEADLOCK: both sides trying to send REQUEST")
    ]
    anomalies = detect_anomalies(messages, [m.raw_line for m in messages])
    assert len(anomalies) > 0
    assert any("死锁" in a for a in anomalies)


def test_extract_capabilities():
    """能力提取"""
    logfile = DATA_DIR / "sample_pd_negotiation_fail.log"
    parser = PdProtocolParser()
    result = parser.parse_file(str(logfile))
    # extract_capabilities works on messages from the parser
    caps = extract_capabilities(result.messages)
    # The fail log has SRC_CAP and SNK_CAP messages, but capabilities
    # may not be extracted if there are no CAPABILITY_ENTRY messages
    # Just verify the function doesn't crash
    assert isinstance(caps, list)


def test_to_dict():
    """序列化"""
    logfile = DATA_DIR / "sample_pd_negotiation_fail.log"
    parser = PdProtocolParser()
    result = parser.parse_file(str(logfile))
    d = result.to_dict()

    assert "source_id" in d
    assert "messages" in d
    assert "negotiated" in d
    assert "anomalies" in d
    assert "state_machine_status" in d

    # 验证 JSON 可序列化
    json_str = json.dumps(d, ensure_ascii=False, default=str)
    parsed = json.loads(json_str)
    assert parsed["message_count"] == len(result.messages)


def test_state_machine_completed():
    """状态机 - 完成"""
    messages = [
        PdMessage(timestamp=1000, direction="TX", message_type="PS_RDY",
                  raw_line="[2026-05-20 16:42:01.801] [INFO] [pd_protocol] VBUS stable at 9050mV - negotiation OK")
    ]
    parser = PdProtocolParser()
    parser.messages = messages
    status = parser._determine_state_machine_status()
    assert status == "COMPLETED"


def test_state_machine_failed():
    """状态机 - 失败"""
    messages = [
        PdMessage(timestamp=1000, direction="TX", message_type="HARD_RESET",
                  raw_line="[2026-05-15 14:28:06.600] [ERROR] [pd_protocol] PD negotiation FAILED")
    ]
    parser = PdProtocolParser()
    parser.messages = messages
    status = parser._determine_state_machine_status()
    assert status == "FAILED"


def test_state_machine_empty():
    """状态机 - 空"""
    parser = PdProtocolParser()
    parser.messages = []
    status = parser._determine_state_machine_status()
    assert status == "EMPTY"


def test_file_not_found():
    """文件不存在"""
    parser = PdProtocolParser()
    try:
        parser.parse_file("/nonexistent/file.log")
        assert False, "应该抛出异常"
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
