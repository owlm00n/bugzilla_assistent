#!/usr/bin/env python3
"""CC Parser 测试套件"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "parsers"))
from cc_parser import (
    CcProtocolParser, CcEvent, CcSession,
    parse_timestamp, parse_cc_event, detect_cc_anomalies,
    CC_STATES, CC_CURRENT, CC_ANOMALY_PATTERNS
)

DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "owlmyclaw" / "data"


def test_cc_states():
    """CC状态定义完整性"""
    assert len(CC_STATES) >= 8
    essential = ["Unattached.SNK", "Attached.SRC", "Attached.SNK"]
    for s in essential:
        assert s in CC_STATES


def test_cc_current():
    """CC电流能力定义"""
    assert "Default" in CC_CURRENT
    assert "1.5A" in CC_CURRENT
    assert "3.0A" in CC_CURRENT


def test_anomaly_patterns():
    """CC异常检测模式"""
    assert len(CC_ANOMALY_PATTERNS) >= 8


def test_parse_timestamp():
    """时间戳解析"""
    line = "[2026-05-20 10:00:00.100] [INFO] [cc_protocol] test"
    ts = parse_timestamp(line)
    assert ts is not None
    assert ts > 0


def test_parse_cc_event_state():
    """CC状态事件"""
    line = "[2026-05-20 10:00:01.000] [INFO] [cc_protocol] State: Attached.SRC"
    event = parse_cc_event(line, None)
    assert event is not None
    assert event.event_type == "STATE_CHANGE"
    assert event.details["cc_state"] == "Attached.SRC"


def test_parse_cc_event_current():
    """CC电流能力事件"""
    line = "[2026-05-20 10:00:01.600] [INFO] [cc_protocol] Current capability: 1.5A"
    event = parse_cc_event(line, None)
    assert event is not None
    assert event.event_type == "CURRENT_CHANGE"
    assert event.details["current_capability"] == "1.5A"


def test_parse_cc_event_vconn():
    """VCONN事件"""
    line = "[2026-05-20 10:00:02.600] [INFO] [cc_protocol] VCONN swap completed"
    event = parse_cc_event(line, None)
    assert event is not None
    assert event.event_type == "VCONN"


def test_parse_cc_event_error():
    """CC错误事件"""
    line = "[2026-05-20 11:00:00.500] [ERROR] [cc_protocol] CC short circuit detected"
    event = parse_cc_event(line, None)
    assert event is not None
    assert event.event_type == "ERROR"


def test_parse_cc_event_rp():
    """Rp电阻值提取"""
    line = "[2026-05-20 10:00:00.200] [INFO] [cc_protocol] CC1: Rp=56k (Default), CC2: Open"
    event = parse_cc_event(line, None)
    assert event is not None
    assert "rp_value" in event.details


def test_parse_cc_event_delay():
    """事件延迟计算"""
    line1 = "[2026-05-20 10:00:00.100] [INFO] [cc_protocol] CC initialized"
    line2 = "[2026-05-20 10:00:00.500] [INFO] [cc_protocol] State: AttachWait.SRC"
    evt1 = parse_cc_event(line1, None)
    evt2 = parse_cc_event(line2, evt1.timestamp)
    assert evt2 is not None
    assert evt2.delay_from_prev > 0


def test_parse_file_normal():
    """解析正常CC日志"""
    logfile = DATA_DIR / "sample_cc_normal.log"
    parser = CcProtocolParser()
    result = parser.parse_file(str(logfile))

    assert len(result.events) > 0
    assert result.final_state == "Attached.SRC"
    assert result.current_capability == "3.0A"
    assert result.vconn_swapped
    assert result.success


def test_parse_file_fail():
    """解析CC失败日志"""
    logfile = DATA_DIR / "sample_cc_fail.log"
    parser = CcProtocolParser()
    result = parser.parse_file(str(logfile))

    assert len(result.events) > 0
    assert len(result.anomalies) > 0
    assert not result.success


def test_parse_text():
    """解析文本输入"""
    text = """[2026-05-20 10:00:00.100] [INFO] [cc_protocol] CC initialized
[2026-05-20 10:00:00.500] [INFO] [cc_protocol] State: AttachWait.SRC
[2026-05-20 10:00:01.000] [INFO] [cc_protocol] State: Attached.SRC"""
    parser = CcProtocolParser()
    result = parser.parse_text(text, "test_cc")

    assert len(result.events) == 3
    assert result.source_id == "test_cc"


def test_get_timeline():
    """时序数据生成"""
    logfile = DATA_DIR / "sample_cc_normal.log"
    parser = CcProtocolParser()
    parser.parse_file(str(logfile))
    timeline = parser.get_timeline()

    assert len(timeline) == len(parser.events)
    for item in timeline:
        assert "order" in item
        assert "delay_ms" in item
        assert "event_type" in item


def test_to_dict():
    """序列化"""
    logfile = DATA_DIR / "sample_cc_normal.log"
    parser = CcProtocolParser()
    result = parser.parse_file(str(logfile))
    d = result.to_dict()

    assert "source_id" in d
    assert "events" in d
    assert "cc_state" in d
    assert "anomalies" in d

    json_str = json.dumps(d, ensure_ascii=False, default=str)
    parsed = json.loads(json_str)
    assert parsed["event_count"] == len(result.events)


def test_detect_anomalies_short():
    """异常检测 - CC短路"""
    events = [
        CcEvent(timestamp=1000, event_type="ERROR",
                description="CC short circuit detected",
                raw_line="[ERROR] [cc_protocol] CC short circuit detected between CC1 and CC2")
    ]
    anomalies = detect_cc_anomalies(events, [e.raw_line for e in events])
    assert len(anomalies) > 0
    assert any("短路" in a for a in anomalies)


def test_detect_anomalies_debounce():
    """异常检测 - 去抖失败"""
    events = [
        CcEvent(timestamp=1000, event_type="ERROR",
                description="debounce timeout",
                raw_line="[WARN] [cc_protocol] Debounce timeout - CC state unstable")
    ]
    anomalies = detect_cc_anomalies(events, [e.raw_line for e in events])
    assert len(anomalies) > 0


def test_file_not_found():
    """文件不存在"""
    parser = CcProtocolParser()
    try:
        parser.parse_file("/nonexistent/cc.log")
        assert False, "应该抛出异常"
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
