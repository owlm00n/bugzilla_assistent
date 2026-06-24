#!/usr/bin/env python3
"""
USB协议解析器 - USB Enumeration Log Parser
解析USB枚举日志，提取连接、重置、设备描述符读取、配置描述符读取等关键步骤。

支持的USB枚举阶段:
  Connect -> Reset -> Address Assignment -> Descriptor Read -> Configuration
  - Device Descriptor (bDescriptorType=0x01)
  - Config Descriptor (bDescriptorType=0x02)
  - Interface Descriptor (bDescriptorType=0x04)
  - String Descriptor (bDescriptorType=0x03)

支持USB 2.0 (HS/FS/LS) 和 USB 3.0+ (SS) 协议。
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Any


# ============================================================
# 数据模型
# ============================================================

@dataclass
class UsbEvent:
    """USB枚举事件"""
    timestamp: float          # 毫秒级时间戳
    stage: str               # connect / reset / descriptor / address / config
    event_type: str          # TX / RX / INFO / WARN / ERROR
    description: str         # 人类可读描述
    details: dict = field(default_factory=dict)   # 结构化参数
    delay_from_prev: float = 0.0
    raw_line: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class UsbEnumeration:
    """USB枚举会话"""
    source_id: str
    log_file: str
    start_time: float
    end_time: float
    events: list = field(default_factory=list)  # list[UsbEvent]
    device_info: dict = field(default_factory=dict)
    usb_version: str = ""
    vendor_id: str = ""
    product_id: str = ""
    configuration: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)
    success: bool = False

    def to_dict(self):
        return {
            "source_id": self.source_id,
            "log_file": self.log_file,
            "start_time_ms": self.start_time,
            "end_time_ms": self.end_time,
            "duration_ms": self.end_time - self.start_time,
            "events": [e.to_dict() for e in self.events],
            "device": {
                "usb_version": self.usb_version,
                "vendor_id": self.vendor_id,
                "product_id": self.product_id,
                "full_info": self.device_info,
            },
            "configurations": self.configuration,
            "anomalies": self.anomalies,
            "success": self.success,
            "event_count": len(self.events),
        }


# ============================================================
# 日志解析
# ============================================================

def parse_timestamp(line: str) -> Optional[float]:
    """提取毫秒级时间戳"""
    m = re.search(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\]', line)
    if m:
        from datetime import datetime
        ts_str = m.group(1)
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        return dt.timestamp() * 1000
    return None


def parse_device_descriptor(line: str) -> dict:
    """解析Device Descriptor信息"""
    info = {}
    patterns = {
        "bcdUSB": r'bcdUSB:\s*0x([0-9A-Fa-f]+)',
        "bDeviceClass": r'bDeviceClass:\s*0x([0-9A-Fa-f]+)',
        "bDeviceSubClass": r'bDeviceSubClass:\s*0x([0-9A-Fa-f]+)',
        "bDeviceProtocol": r'bDeviceProtocol:\s*0x([0-9A-Fa-f]+)',
        "bMaxPacketSize0": r'bMaxPacketSize0:\s*0x([0-9A-Fa-f]+)',
        "idVendor": r'idVendor:\s*0x([0-9A-Fa-f]+)',
        "idProduct": r'idProduct:\s*0x([0-9A-Fa-f]+)',
        "bcdDevice": r'bcdDevice:\s*0x([0-9A-Fa-f]+)',
        "iManufacturer": r'iManufacturer:\s*0x([0-9A-Fa-f]+)',
        "iProduct": r'iProduct:\s*0x([0-9A-Fa-f]+)',
        "bNumConfigurations": r'bNumConfigurations:\s*0x([0-9A-Fa-f]+)',
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, line)
        if m:
            val = m.group(1)
            # Convert hex strings like "0x0310" to human readable
            if key == "bcdUSB":
                bcd = int(val, 16)
                major = (bcd >> 8) & 0xFF
                # Lower byte is BCD encoded (e.g. 0x20 = 20, not 32)
                minor_byte = bcd & 0xFF
                minor = ((minor_byte >> 4) & 0xF) * 10 + (minor_byte & 0xF)
                info[key] = f"USB {major}.{minor}"
            elif key in ("idVendor", "idProduct", "bcdDevice"):
                info[key] = f"0x{val.upper()}"
            else:
                info[key] = f"0x{val.upper()}"
    return info


def parse_event(line: str, prev_ts: Optional[float]) -> Optional[UsbEvent]:
    """从单行日志解析USB事件"""
    line = line.strip()
    if not line:
        return None

    ts = parse_timestamp(line)
    if ts is None:
        return None

    # 确定事件级别
    level = "INFO"
    if "[ERROR]" in line:
        level = "ERROR"
    elif "[WARN]" in line:
        level = "WARN"
    elif "[TX]" in line:
        level = "TX"
    elif "[RX]" in line:
        level = "RX"

    # 确定阶段
    stage = "other"
    if "connect" in line.lower() or "detected" in line.lower():
        stage = "connect"
    elif "reset" in line.lower():
        stage = "reset"
    elif "descriptor" in line.lower() or "DESCR" in line.upper():
        stage = "descriptor"
    elif "address" in line.lower():
        stage = "address"
    elif "config" in line.lower():
        stage = "config"
    elif "enumeration" in line.lower():
        stage = "config"
    elif "endpoint" in line.lower():
        stage = "config"

    # 构建描述
    # Remove timestamp and log level prefix for description
    desc = re.sub(r'^\[[\d\-:\s.]+\]\s*\[\w+\]\s*\[.*?\]\s*', '', line)
    desc = desc.strip()

    # 提取细节
    details = {}

    # USB枚举阶段详情
    if "GET_DESCRIPTOR" in line:
        dm = re.search(r'Type=(\w+)', line)
        if dm:
            details["desc_type"] = dm.group(1)
        am = re.search(r'Addr=(\d+)', line)
        if am:
            details["addr"] = int(am.group(1))
        lm = re.search(r'WLen=(\w+)', line)
        if lm:
            details["w_len"] = lm.group(1)
        details["operation"] = "GET_DESCRIPTOR"

    elif "SET_ADDRESS" in line:
        am = re.search(r'Addr=(\d+)', line)
        if am:
            details["addr"] = int(am.group(1))
        details["operation"] = "SET_ADDRESS"

    elif "Device Descriptor" in line:
        details["operation"] = "READ_DEVICE_DESCRIPTOR"
        # Parse individual fields from following lines (will be merged later)

    elif "Port status" in line:
        details["operation"] = "PORT_STATUS"
        sm = re.search(r'signaling=(\w+)', line)
        if sm:
            details["signaling_speed"] = sm.group(1)

    elif "enumeration FAILED" in line:
        details["operation"] = "ENUM_FAILED"
        stage = "config"  # failure happens at some stage

    # 计算延迟
    delay = 0.0
    if prev_ts is not None and ts is not None:
        delay = round(ts - prev_ts, 3)

    return UsbEvent(
        timestamp=ts,
        stage=stage,
        event_type=level,
        description=desc,
        details=details,
        delay_from_prev=delay,
        raw_line=line,
    )


# ============================================================
# 信息聚合
# ============================================================

def extract_device_info(events: list[UsbEvent]) -> tuple[str, str, str, dict]:
    """从事件序列中提取USB设备信息"""
    usb_version = ""
    vendor_id = ""
    product_id = ""
    full_info = {}

    # First pass: scan raw lines directly for vendor/product/version info
    for event in events:
        raw = event.raw_line
        if not usb_version:
            vm = re.search(r'USB\s*(\d+\.\d+)', raw)
            if vm:
                usb_version = vm.group(1)
        if not vendor_id:
            vm = re.search(r'idVendor:\s*0x([0-9A-Fa-f]+)', raw)
            if vm:
                vendor_id = f"0x{vm.group(1).upper()}"
        if not product_id:
            pm = re.search(r'idProduct:\s*0x([0-9A-Fa-f]+)', raw)
            if pm:
                product_id = f"0x{pm.group(1).upper()}"
        # Parse bcdUSB hex (BCD encoded)
        bm = re.search(r'bcdUSB:\s*0x([0-9A-Fa-f]+)', raw)
        if bm:
            bcd = int(bm.group(1), 16)
            major = (bcd >> 8) & 0xFF
            minor_byte = bcd & 0xFF
            minor = ((minor_byte >> 4) & 0xF) * 10 + (minor_byte & 0xF)
            if not usb_version:
                usb_version = f"{major}.{minor}"

    # Also check details dict
    for event in events:
        if event.details.get("operation") == "READ_DEVICE_DESCRIPTOR":
            full_info.update(event.details)

    return usb_version, vendor_id, product_id, full_info


def detect_anomalies(events: list[UsbEvent], raw_lines: list[str]) -> list[str]:
    """检测USB枚举异常"""
    anomalies = []
    anomaly_keywords = [
        (r'超时|timeout|TIMEOUT', "描述符读取超时"),
        (r'重传|Retransmit|RETRY|retry', "请求重传"),
        (r'Max retransmit|最大重试', "达到最大重试次数"),
        (r'FAILED|失败', "枚举失败"),
        (r'死机|freeze|stuck|卡死', "控制器异常"),
        (r'disconnect|断开|disconnected', "意外断开"),
        (r'compatibility|兼容', "兼容性问题"),
    ]

    checked = set()
    for event in events:
        raw = event.raw_line
        level = event.event_type
        if level not in ("WARN", "ERROR"):
            continue
        for pattern, desc in anomaly_keywords:
            if re.search(pattern, raw, re.IGNORECASE) and desc not in checked:
                anomalies.append(f"[{level}] {desc}: {event.description[:120]}")
                checked.add(desc)

    # Also scan raw lines for anything missed
    for line in raw_lines:
        if "[ERROR]" in line or "[WARN]" in line:
            for pattern, desc in anomaly_keywords:
                if re.search(pattern, line, re.IGNORECASE) and desc not in checked:
                    anomalies.append(f"[WARN] {desc}: {line.strip()[:120]}")
                    checked.add(desc)
                    break

    return anomalies


# ============================================================
# 主解析器
# ============================================================

class UsbProtocolParser:
    """USB协议枚举日志解析器"""

    def __init__(self, source_id: str = "usb_session"):
        self.source_id = source_id
        self.events: list[UsbEvent] = []
        self.raw_lines: list[str] = []

    def parse_file(self, filepath: str) -> UsbEnumeration:
        """解析USB枚举日志文件"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {filepath}")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return self.parse_lines(lines, str(path.name))

    def parse_text(self, text: str, source_id: str = None) -> UsbEnumeration:
        """解析USB枚举日志文本"""
        if source_id:
            self.source_id = source_id
        lines = text.splitlines()
        return self.parse_lines(lines, "inline_text")

    def parse_lines(self, lines: list[str], log_file: str) -> UsbEnumeration:
        """解析日志行列表"""
        self.raw_lines = lines
        self.events = []

        prev_ts: Optional[float] = None
        descriptor_details: dict = {}

        for line in lines:
            event = parse_event(line, prev_ts)
            if event is None:
                # Maybe it's a descriptor field line (e.g. "  bcdUSB: 0x0310")
                if descriptor_details and line.strip() and not line.strip()[0].isdigit():
                    # Try to parse as descriptor field
                    for field_name in ("bcdUSB", "bDeviceClass", "bDeviceSubClass",
                                       "bDeviceProtocol", "bMaxPacketSize0",
                                       "idVendor", "idProduct", "bcdDevice",
                                       "iManufacturer", "iProduct", "bNumConfigurations"):
                        if field_name in line:
                            # Extract value
                            vm = re.search(rf'{field_name}:\s*(.+)', line)
                            if vm:
                                descriptor_details[field_name] = vm.group(1).strip()
                continue

            prev_ts = event.timestamp
            self.events.append(event)

            # Collect descriptor info
            if event.details.get("operation") == "READ_DEVICE_DESCRIPTOR":
                event.details.update(descriptor_details)
                # Also extract info directly
                for key in ("bcdUSB", "idVendor", "idProduct"):
                    if key in descriptor_details and key not in event.details:
                        event.details[key] = descriptor_details[key]
                descriptor_details = {}

        # Build result
        start_ts = self.events[0].timestamp if self.events else 0
        end_ts = self.events[-1].timestamp if self.events else 0

        usb_version, vendor_id, product_id, device_info = extract_device_info(self.events)
        anomalies = detect_anomalies(self.events, lines)

        # Determine success
        success = False
        for event in reversed(self.events):
            if "FAILED" in event.raw_line.upper() or "失败" in event.raw_line:
                break
            if "Configuration" in event.raw_line or "Configuration selected" in event.raw_line:
                success = True
                break
            if event.stage == "other" and event.event_type == "INFO":
                success = True  # Events progressing normally

        # Check if last events are failures
        last_few = self.events[-3:] if len(self.events) >= 3 else self.events
        for event in last_few:
            if "FAILED" in event.raw_line.upper() or "disable" in event.raw_line.lower():
                success = False

        return UsbEnumeration(
            source_id=self.source_id,
            log_file=log_file,
            start_time=start_ts,
            end_time=end_ts,
            events=self.events,
            device_info=device_info,
            usb_version=usb_version,
            vendor_id=vendor_id,
            product_id=product_id,
            anomalies=anomalies,
            success=success,
        )

    def get_timeline(self) -> list[dict]:
        """获取枚举时序数据"""
        timeline = []
        for i, event in enumerate(self.events):
            timeline.append({
                "order": i + 1,
                "delay_ms": round(event.delay_from_prev, 3),
                "cumulative_ms": round(sum(e.delay_from_prev for e in self.events[:i+1]), 3),
                "event_type": event.event_type,
                "stage": event.stage,
                "description": event.description[:80],
                "is_anomaly": event.event_type in ("WARN", "ERROR"),
                "details": event.details,
            })
        return timeline


# ============================================================
# CLI入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("USB协议解析器 - 解析USB枚举日志")
        print("用法: python usb_parser.py <logfile> [output_json]")
        print("示例: python usb_parser.py sample_usb.log output.json")
        sys.exit(1)

    logfile = sys.argv[1]
    parser = UsbProtocolParser()

    try:
        enumeration = parser.parse_file(logfile)
        result = enumeration.to_dict()

        if len(sys.argv) >= 3:
            output_path = sys.argv[2]
            Path(output_path).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            print(f"✅ 解析完成，结果已保存到: {output_path}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        print(f"\n📊 解析摘要:")
        print(f"  事件数: {result['event_count']}")
        print(f"  USB版本: {result['device']['usb_version'] or 'N/A'}")
        print(f"  VID: {result['device']['vendor_id'] or 'N/A'}")
        print(f"  PID: {result['device']['product_id'] or 'N/A'}")
        print(f"  成功率: {'✅ 是' if result['success'] else '❌ 否'}")
        if result['anomalies']:
            print(f"  ⚠️  异常数: {len(result['anomalies'])}")

    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
