#!/usr/bin/env python3
"""USB Parser 测试套件"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "parsers"))
from usb_parser import (
    UsbProtocolParser, UsbEvent, UsbEnumeration,
    parse_timestamp, parse_event, parse_device_descriptor,
    extract_device_info, detect_anomalies
)

DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "owlmyclaw" / "data"


def test_parse_timestamp():
    """时间戳解析"""
    line = "[2026-05-15 14:28:01.123] [INFO] [usb_core] test"
    ts = parse_timestamp(line)
    assert ts is not None
    assert ts > 0

    assert parse_timestamp("no timestamp here") is None


def test_parse_device_descriptor():
    """设备描述符解析"""
    line = "bcdUSB: 0x0320  idVendor: 0x1234  idProduct: 0x5678  bDeviceClass: 0x00"
    info = parse_device_descriptor(line)
    assert "bcdUSB" in info
    assert "idVendor" in info
    assert "idProduct" in info


def test_parse_event_connect():
    """连接事件"""
    line = "[2026-05-15 14:28:01.100] [INFO] [usb_core] USB device detected, port 1"
    event = parse_event(line, None)
    assert event is not None
    assert event.stage == "connect"
    assert event.event_type == "INFO"


def test_parse_event_reset():
    """复位事件"""
    line = "[2026-05-15 14:28:01.200] [INFO] [usb_core] Port reset complete"
    event = parse_event(line, None)
    assert event is not None
    assert event.stage == "reset"


def test_parse_event_descriptor():
    """描述符事件"""
    line = "[2026-05-15 14:28:01.300] [TX] [usb_core] GET_DESCRIPTOR Type=DEVICE Addr=0 WLen=18"
    event = parse_event(line, None)
    assert event is not None
    assert event.stage == "descriptor"
    assert event.details["operation"] == "GET_DESCRIPTOR"
    assert event.details["desc_type"] == "DEVICE"


def test_parse_event_address():
    """地址分配事件"""
    line = "[2026-05-15 14:28:01.400] [TX] [usb_core] SET_ADDRESS Addr=5"
    event = parse_event(line, None)
    assert event is not None
    assert event.stage == "address"
    assert event.details["addr"] == 5


def test_parse_event_config():
    """配置事件"""
    line = "[2026-05-15 14:28:01.500] [INFO] [usb_core] Configuration selected: 1"
    event = parse_event(line, None)
    assert event is not None
    assert event.stage == "config"


def test_parse_event_error():
    """错误事件"""
    line = "[2026-05-15 14:28:01.600] [ERROR] [usb_core] enumeration FAILED - timeout"
    event = parse_event(line, None)
    assert event is not None
    assert event.event_type == "ERROR"


def test_parse_event_delay():
    """事件延迟计算"""
    line1 = "[2026-05-15 14:28:01.100] [INFO] [usb_core] device detected"
    line2 = "[2026-05-15 14:28:01.300] [INFO] [usb_core] reset complete"
    evt1 = parse_event(line1, None)
    evt2 = parse_event(line2, evt1.timestamp)
    assert evt2 is not None
    assert evt2.delay_from_prev > 0


def test_parse_file():
    """解析USB枚举日志"""
    logfile = DATA_DIR / "sample_usb_enum_timeout.log"
    parser = UsbProtocolParser()
    result = parser.parse_file(str(logfile))

    assert len(result.events) > 0
    assert isinstance(result.success, bool)

    # 验证事件类型
    stages = {e.stage for e in result.events}
    assert len(stages) > 0


def test_parse_text():
    """解析文本输入"""
    text = """[2026-05-15 14:28:01.100] [INFO] [usb_core] USB device detected
[2026-05-15 14:28:01.200] [INFO] [usb_core] Port reset complete
[2026-05-15 14:28:01.300] [TX] [usb_core] GET_DESCRIPTOR Type=DEVICE Addr=0
[2026-05-15 14:28:01.400] [TX] [usb_core] SET_ADDRESS Addr=5
[2026-05-15 14:28:01.500] [INFO] [usb_core] Configuration selected: 1"""
    parser = UsbProtocolParser()
    result = parser.parse_text(text, "test_usb")

    assert len(result.events) == 5
    assert result.source_id == "test_usb"


def test_extract_device_info():
    """设备信息提取"""
    events = [
        UsbEvent(timestamp=1000, stage="descriptor", event_type="INFO",
                 description="Device Descriptor", details={"operation": "READ_DEVICE_DESCRIPTOR"},
                 raw_line="bcdUSB: 0x0320  idVendor: 0x1234  idProduct: 0x5678")
    ]
    usb_ver, vid, pid, info = extract_device_info(events)
    assert usb_ver == "3.20"
    assert vid == "0x1234"
    assert pid == "0x5678"


def test_detect_anomalies_timeout():
    """异常检测 - 超时"""
    events = [
        UsbEvent(timestamp=1000, stage="descriptor", event_type="ERROR",
                 description="GET_DESCRIPTOR timeout", raw_line="[ERROR] timeout waiting for descriptor")
    ]
    anomalies = detect_anomalies(events, [e.raw_line for e in events])
    assert len(anomalies) > 0


def test_detect_anomalies_failed():
    """异常检测 - 枚举失败"""
    events = [
        UsbEvent(timestamp=1000, stage="config", event_type="ERROR",
                 description="enumeration FAILED", raw_line="[ERROR] enumeration FAILED")
    ]
    anomalies = detect_anomalies(events, [e.raw_line for e in events])
    assert len(anomalies) > 0


def test_get_timeline():
    """时序数据生成"""
    logfile = DATA_DIR / "sample_usb_enum_timeout.log"
    parser = UsbProtocolParser()
    parser.parse_file(str(logfile))
    timeline = parser.get_timeline()

    assert len(timeline) == len(parser.events)
    for item in timeline:
        assert "order" in item
        assert "delay_ms" in item
        assert "stage" in item
        assert "description" in item


def test_to_dict():
    """序列化"""
    logfile = DATA_DIR / "sample_usb_enum_timeout.log"
    parser = UsbProtocolParser()
    result = parser.parse_file(str(logfile))
    d = result.to_dict()

    assert "source_id" in d
    assert "events" in d
    assert "device" in d
    assert "anomalies" in d
    assert "success" in d

    json_str = json.dumps(d, ensure_ascii=False, default=str)
    parsed = json.loads(json_str)
    assert parsed["event_count"] == len(result.events)


def test_file_not_found():
    """文件不存在"""
    parser = UsbProtocolParser()
    try:
        parser.parse_file("/nonexistent/usb.log")
        assert False, "应该抛出异常"
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
