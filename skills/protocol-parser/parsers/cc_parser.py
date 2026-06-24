#!/usr/bin/env python3
"""
Type-C CC协议解析器 - USB Type-C Configuration Channel Parser
解析CC线状态日志，提取连接状态、角色协商、电流能力、VCONN交换等信息。

支持的CC状态:
  - CC连接检测: Rp/Rd/Ra识别
  - 电流能力: Default(500mA)/1.5A/3.0A
  - 角色: SRC/SNK/DRP
  - VCONN交换
  - CC方向检测
  - 连接状态变化: Attached/Detached/Debounce
"""

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
# 数据模型
# ============================================================

@dataclass
class CcEvent:
    """CC线事件"""
    timestamp: float
    event_type: str          # STATE_CHANGE / ROLE_CHANGE / CURRENT_CHANGE / VCONN / ERROR
    description: str
    details: dict = field(default_factory=dict)
    delay_from_prev: float = 0.0
    raw_line: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class CcSession:
    """CC协议会话"""
    source_id: str
    log_file: str
    start_time: float
    end_time: float
    events: list = field(default_factory=list)  # list[CcEvent]
    initial_state: str = "UNKNOWN"
    final_state: str = "UNKNOWN"
    current_capability: str = "UNKNOWN"  # Default/1.5A/3.0A
    role: str = "UNKNOWN"               # SRC/SNK/DRP
    vconn_swapped: bool = False
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
            "cc_state": {
                "initial": self.initial_state,
                "final": self.final_state,
                "current_capability": self.current_capability,
                "role": self.role,
                "vconn_swapped": self.vconn_swapped,
            },
            "anomalies": self.anomalies,
            "success": self.success,
            "event_count": len(self.events),
        }


# ============================================================
# CC状态定义
# ============================================================

CC_STATES = {
    "Unattached.SNK": "未连接(SNK)",
    "Unattached.SRC": "未连接(SRC)",
    "AttachWait.SNK": "等待连接(SNK)",
    "AttachWait.SRC": "等待连接(SRC)",
    "Attached.SNK": "已连接(SNK)",
    "Attached.SRC": "已连接(SRC)",
    "Try.SNK": "尝试SNK",
    "Try.SRC": "尝试SRC",
    "TryWait.SNK": "等待尝试(SNK)",
    "PoweredAccessory": "供电配件",
    "AudioAccessory": "音频配件",
    "DebugAccessory": "调试配件",
}

CC_CURRENT = {
    "Default": "500mA (USB Default)",
    "1.5A": "1.5A",
    "3.0A": "3.0A",
}

CC_ROLES = ["SRC", "SNK", "DRP"]

CC_ANOMALY_PATTERNS = [
    (r'CC.*short|CC.*short circuit|CC短路', "CC线短路"),
    (r'CC\s+open\s+circuit|CC开路', "CC线开路"),
    (r'CC.*debounce.*fail|debounce.*timeout', "CC去抖失败"),
    (r'Rp.*mismatch|Rp.*异常|Rp.*wrong', "Rp电阻值异常"),
    (r'Rd.*mismatch|Rd.*异常|Rd.*wrong', "Rd电阻值异常"),
    (r'VCONN.*fail|VCONN.*异常|VCONN.*short', "VCONN异常"),
    (r'role.*conflict|角色冲突|DRP.*conflict', "角色冲突"),
    (r'current.*mismatch|电流能力不匹配', "电流能力不匹配"),
    (r'CC.*toggle.*fail|CC切换失败', "CC切换失败"),
    (r'orientation.*fail|方向检测失败', "方向检测失败"),
]


# ============================================================
# 日志解析
# ============================================================

def parse_timestamp(line: str) -> Optional[float]:
    """提取毫秒级时间戳"""
    m = re.search(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\]', line)
    if m:
        dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
        return dt.timestamp() * 1000
    return None


def parse_cc_event(line: str, prev_ts: Optional[float]) -> Optional[CcEvent]:
    """从单行日志解析CC事件"""
    line = line.strip()
    if not line:
        return None

    ts = parse_timestamp(line)
    if ts is None:
        return None

    # 检测CC相关日志
    cc_markers = ["CC", "cc_state", "cc_protocol", "Type-C", "TYPE_C", "VCONN", "Rp", "Rd"]
    if not any(m in line for m in cc_markers):
        return None

    # 确定事件类型
    event_type = "STATE_CHANGE"
    if "VCONN" in line:
        event_type = "VCONN"
    elif "role" in line.lower() and ("SRC" in line or "SNK" in line or "DRP" in line):
        event_type = "ROLE_CHANGE"
    elif any(w in line for w in ["1.5A", "3.0A", "Default", "current", "Current"]):
        event_type = "CURRENT_CHANGE"
    elif "ERROR" in line or "WARN" in line or "fail" in line.lower():
        event_type = "ERROR"

    # 构建描述
    desc = re.sub(r'^\[[\d\-:\s.]+\]\s*\[\w+\]\s*\[.*?\]\s*', '', line).strip()

    # 提取细节
    details = {}
    # 提取CC状态
    for state, label in CC_STATES.items():
        if state in line:
            details["cc_state"] = state
            details["cc_state_label"] = label
            break

    # 提取电流能力
    for cap, label in CC_CURRENT.items():
        if cap in line:
            details["current_capability"] = cap
            details["current_label"] = label
            break

    # 提取角色
    for role in CC_ROLES:
        if f"role={role}" in line or f"Role={role}" in line or f"role: {role}" in line:
            details["role"] = role
            break

    # 提取Rp/Rd值
    rp_m = re.search(r'Rp[=:\s]*(\d+\.?\d*)k?', line)
    if rp_m:
        details["rp_value"] = f"{rp_m.group(1)}kΩ"
    rd_m = re.search(r'Rd[=:\s]*(\d+\.?\d*)k?', line)
    if rd_m:
        details["rd_value"] = f"{rd_m.group(1)}kΩ"

    # 提取方向
    if "orientation" in line.lower():
        ori_m = re.search(r'orientation[=:\s]*(\w+)', line, re.IGNORECASE)
        if ori_m:
            details["orientation"] = ori_m.group(1)

    # 计算延迟
    delay = 0.0
    if prev_ts is not None and ts is not None:
        delay = round(ts - prev_ts, 3)

    return CcEvent(
        timestamp=ts,
        event_type=event_type,
        description=desc,
        details=details,
        delay_from_prev=delay,
        raw_line=line,
    )


# ============================================================
# 异常检测
# ============================================================

def detect_cc_anomalies(events: list[CcEvent], raw_lines: list[str]) -> list[str]:
    """检测CC协议异常"""
    anomalies = []

    for event in events:
        raw = event.raw_line
        for pattern, desc in CC_ANOMALY_PATTERNS:
            if re.search(pattern, raw, re.IGNORECASE):
                anomalies.append(f"[{event.event_type}] {desc}: {event.description[:120]}")
                break

    # 从原始行检测
    for line in raw_lines:
        if "[ERROR]" not in line and "[WARN]" not in line:
            continue
        for pattern, desc in CC_ANOMALY_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                anomaly_text = f"[WARN] {desc}: {line.strip()[:120]}"
                if anomaly_text not in anomalies:
                    anomalies.append(anomaly_text)
                break

    return anomalies


# ============================================================
# 主解析器
# ============================================================

class CcProtocolParser:
    """Type-C CC协议解析器"""

    def __init__(self, source_id: str = "cc_session"):
        self.source_id = source_id
        self.events: list[CcEvent] = []
        self.raw_lines: list[str] = []

    def parse_file(self, filepath: str) -> CcSession:
        """解析CC协议日志文件"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {filepath}")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return self.parse_lines(lines, str(path.name))

    def parse_text(self, text: str, source_id: str = None) -> CcSession:
        """解析CC协议日志文本"""
        if source_id:
            self.source_id = source_id
        lines = text.splitlines()
        return self.parse_lines(lines, "inline_text")

    def parse_lines(self, lines: list[str], log_file: str) -> CcSession:
        """解析日志行列表"""
        self.raw_lines = lines
        self.events = []

        prev_ts: Optional[float] = None
        for line in lines:
            event = parse_cc_event(line, prev_ts)
            if event:
                self.events.append(event)
                prev_ts = event.timestamp

        # 构建会话结果
        start_ts = self.events[0].timestamp if self.events else 0
        end_ts = self.events[-1].timestamp if self.events else 0

        # 提取状态
        initial_state = "UNKNOWN"
        final_state = "UNKNOWN"
        current_capability = "UNKNOWN"
        role = "UNKNOWN"
        vconn_swapped = False

        for event in self.events:
            if "cc_state" in event.details:
                if initial_state == "UNKNOWN":
                    initial_state = event.details["cc_state"]
                final_state = event.details["cc_state"]
            if "current_capability" in event.details:
                current_capability = event.details["current_capability"]
            if "role" in event.details:
                role = event.details["role"]
            if event.event_type == "VCONN" and "swap" in event.description.lower():
                vconn_swapped = True

        anomalies = detect_cc_anomalies(self.events, lines)
        success = final_state.startswith("Attached") and len(anomalies) == 0

        return CcSession(
            source_id=self.source_id,
            log_file=log_file,
            start_time=start_ts,
            end_time=end_ts,
            events=self.events,
            initial_state=initial_state,
            final_state=final_state,
            current_capability=current_capability,
            role=role,
            vconn_swapped=vconn_swapped,
            anomalies=anomalies,
            success=success,
        )

    def get_timeline(self) -> list[dict]:
        """获取CC事件时序数据"""
        timeline = []
        for i, event in enumerate(self.events):
            timeline.append({
                "order": i + 1,
                "delay_ms": round(event.delay_from_prev, 3),
                "cumulative_ms": round(sum(e.delay_from_prev for e in self.events[:i+1]), 3),
                "event_type": event.event_type,
                "description": event.description[:80],
                "details": event.details,
                "is_anomaly": event.event_type == "ERROR",
            })
        return timeline


# ============================================================
# CLI入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Type-C CC协议解析器 - 解析CC线状态日志")
        print("用法: python cc_parser.py <logfile> [output_json]")
        sys.exit(1)

    logfile = sys.argv[1]
    parser = CcProtocolParser()

    try:
        session = parser.parse_file(logfile)
        result = session.to_dict()

        if len(sys.argv) >= 3:
            output_path = sys.argv[2]
            Path(output_path).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            print(f"✅ 解析完成，结果已保存到: {output_path}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        print(f"\n📊 CC协议解析摘要:")
        print(f"  事件数: {result['event_count']}")
        print(f"  初始状态: {result['cc_state']['initial']}")
        print(f"  最终状态: {result['cc_state']['final']}")
        print(f"  电流能力: {result['cc_state']['current_capability']}")
        print(f"  角色: {result['cc_state']['role']}")
        print(f"  VCONN交换: {'✅ 是' if result['cc_state']['vconn_swapped'] else '❌ 否'}")
        print(f"  连接成功: {'✅ 是' if result['success'] else '❌ 否'}")
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
