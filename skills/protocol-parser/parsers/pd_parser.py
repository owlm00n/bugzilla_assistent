#!/usr/bin/env python3
"""
PD协议解析器 - Protocol Parser for USB-PD
解析PD协商日志，提取消息交互、检测异常、生成结构化数据。

支持的PD消息类型:
  SRC_CAP / SNK_CAP / REQUEST / ACCEPT / REJECT / PR_SWAP / CU_SWAP / DR_SWAP
  WAIT / SOFT_RESET / HARD_RESET / GET_SOURCE_CAP / GET_SINK_CAP
  PS_RDY / BIST / SOURCE_CAP_EXTENDED / GET_SOURCE_CAP

输出:
  - 结构化JSON: 时间戳、TX/RX方向、消息类型、参数、时序关系
  - 异常检测: 超时、重传、电压异常、状态机死锁
  - 时序图数据: 用于可视化渲染
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
class PdMessage:
    """单条PD消息"""
    timestamp: float          # 毫秒级时间戳
    direction: str            # TX / RX
    message_type: str         # SRC_CAP, REQUEST, ACCEPT, etc.
    raw_line: str             # 原始日志行
    params: dict = field(default_factory=dict)   # 解析出的参数
    delay_from_prev: float = 0.0  # 距离上一条消息的延迟(ms)

    def to_dict(self):
        d = asdict(self)
        return d


@dataclass
class PdNegotiation:
    """PD协商会话"""
    source_id: str
    log_file: str
    start_time: float
    end_time: float
    messages: list = field(default_factory=list)  # list[PdMessage]
    capabilities: list = field(default_factory=list)
    negotiated_voltage: float = 0.0  # mV
    negotiated_current: float = 0.0  # mA
    anomalies: list = field(default_factory=list)  # list[str]
    success: bool = False
    state_machine_status: str = "UNKNOWN"

    def to_dict(self):
        return {
            "source_id": self.source_id,
            "log_file": self.log_file,
            "start_time_ms": self.start_time,
            "end_time_ms": self.end_time,
            "duration_ms": self.end_time - self.start_time,
            "messages": [m.to_dict() for m in self.messages],
            "capabilities": self.capabilities,
            "negotiated": {
                "voltage_mv": self.negotiated_voltage,
                "current_ma": self.negotiated_current,
                "power_mv_a": self.negotiated_voltage * self.negotiated_current,
                "success": self.success,
            },
            "anomalies": self.anomalies,
            "state_machine_status": self.state_machine_status,
            "message_count": len(self.messages),
        }


# ============================================================
# PD消息类型定义
# ============================================================

PD_COMMANDS = {
    "01": "SIGNAL_RESET",
    "02": "WAIT",
    "03": "SOFT_RESET",
    "04": "GET_SOURCE_CAP",
    "05": "SOURCE_CAP",       # SRC_CAP alias
    "06": "REQUEST",
    "07": "ACCEPT",
    "08": "REJECT",
    "09": "PING",
    "0A": "PS_RDY",
    "0B": "GET_SOURCE_CAP_EXTENDED",
    "0C": "DR_SWAP",
    "0D": "PR_SWAP",
    "0E": "FR_SWAP",
    "0F": "GET_SINK_CAP",
    "10": "DOCUMENT_SINK_CAP",
    "11": "BIST",
    "12": "SINK_CAP",         # SNK_CAP alias
    "13": "BATTERY_STATUS",
    "14": "ENTRY_FM",
    "15": "ATTENTION",
    "16": "GET_SOURCE_EXTENDED_PARAMS",
    "17": "VSW_SOURCE_EXTENDED_PARAMS",
    "18": "VSW_SINK_EXTENDED_PARAMS",
    "19": "VSW_INTERRUPT",
    "1A": "VSW_STATUS",
    "1B": "GET_POWER_STATUS",
    "1C": "GET_BATT_CAP_STATUS",
    "1D": "BATT_CHARGED",
    "1E": "BATT_DISCHARGING",
    "1F": "VDM",
    "FF": "HARD_RESET",
}

# 需要特殊解析的字段
COMPLEX_MESSAGE_TYPES = {"SOURCE_CAP", "SINK_CAP", "REQUEST"}


# ============================================================
# PDO解析
# ============================================================

def parse_pdo(raw: str) -> dict:
    """解析Fixed/Variable/APDO"""
    result = {}

    # Fixed PDO: "Fixed PDO - 9V/2A (18000mW)"
    m = re.search(r'Fixed\s+PDO\s*-\s*(\d+(?:\.\d+)?)V/(\d+(?:\.\d+)?)A\s*\((\d+)mW\)', raw)
    if m:
        result = {
            "type": "Fixed PDO",
            "voltage_v": float(m.group(1)),
            "current_a": float(m.group(2)),
            "power_mw": int(m.group(3)),
        }
        return result

    # Variable PDO: "Variable PDO - 12-20V/3A (36000mW)"
    m = re.search(r'Variable\s+PDO\s*-\s*(\d+)-(\d+)V/(\d+(?:\.\d+)?)A\s*\((\d+)mW\)', raw)
    if m:
        result = {
            "type": "Variable PDO",
            "min_voltage_v": int(m.group(1)),
            "max_voltage_v": int(m.group(2)),
            "current_a": float(m.group(3)),
            "power_mw": int(m.group(4)),
        }
        return result

    # Variable Operated: "Variable Operated - 9-12V/2.5A (25000mW)"
    m = re.search(r'Variable\s+Operated\s*-\s*(\d+)-(\d+)V/(\d+(?:\.\d+)?)A\s*\((\d+)mW\)', raw)
    if m:
        result = {
            "type": "Variable Operated PDO",
            "min_voltage_v": int(m.group(1)),
            "max_voltage_v": int(m.group(2)),
            "current_a": float(m.group(3)),
            "power_mw": int(m.group(4)),
        }
        return result

    # Simple format: "Capability 2: Fixed PDO - 5V/3A (15000mW)"
    m = re.search(r'(Capability\s+\d+):\s*(.+)', raw)
    if m:
        label = m.group(1).strip()
        content = m.group(2).strip()
        result["label"] = label
        result["content"] = content
        # Try to extract voltage/current
        vm = re.search(r'(\d+(?:\.\d+)?)V', content)
        cm = re.search(r'/(\d+(?:\.\d+)?)A', content)
        pm = re.search(r'(\d+)mW', content)
        if vm:
            result["voltage_v"] = float(vm.group(1))
        if cm:
            result["current_a"] = float(cm.group(1))
        if pm:
            result["power_mw"] = int(pm.group(1))
        return result

    result["raw"] = raw.strip()
    return result


# ============================================================
# 请求解析
# ============================================================

def parse_request(raw: str) -> dict:
    """解析REQUEST消息"""
    result = {"type": "REQUEST"}
    m = re.search(r'REQUEST\s*\[Cap=(\d+)\]', raw)
    if m:
        result["cap_index"] = int(m.group(1))
    vm = re.search(r'(\d+(?:\.\d+)?)V', raw)
    cm = re.search(r'(\d+(?:\.\d+)?)A', raw)
    if vm:
        result["voltage_v"] = float(vm.group(1))
    if cm:
        result["current_a"] = float(cm.group(1))
    return result


# ============================================================
# 日志行解析
# ============================================================

def parse_timestamp(line: str) -> Optional[float]:
    """提取毫秒级时间戳"""
    m = re.search(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\]', line)
    if m:
        ts_str = m.group(1)
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        return dt.timestamp() * 1000  # return as ms
    return None


def parse_message(line: str, prev_ts: Optional[float]) -> Optional[PdMessage]:
    """从单行日志解析PD消息"""
    line = line.strip()
    if not line:
        return None

    ts = parse_timestamp(line)
    if ts is None:
        return None

    # 提取方向
    direction = "OTHER"
    if "[TX]" in line:
        direction = "TX"
    elif "[RX]" in line:
        direction = "RX"

    # 提取消息类型 - 支持别名
    msg_type = None
    # Aliases: common abbreviations used in real logs
    ALIASES = {
        "SRC_CAP": "SOURCE_CAP", "SNK_CAP": "SINK_CAP",
        "HARD_RESET": "HARD_RESET", "Hard Reset": "HARD_RESET",
        "SOFT_RESET": "SOFT_RESET", "Soft Reset": "SOFT_RESET",
        "PR_SWAP": "PR_SWAP", "DR_SWAP": "DR_SWAP", "FR_SWAP": "FR_SWAP",
        "GET_SOURCE_CAP": "GET_SOURCE_CAP", "GET_SINK_CAP": "GET_SINK_CAP",
        "PS_RDY": "PS_RDY", "WAIT": "WAIT", "WAIT_PWR_OK": "WAIT",
        "ACCEPT": "ACCEPT", "REJECT": "REJECT", "REQUEST": "REQUEST",
        "BIST": "BIST", "PING": "PING", "VDM": "VDM",
        "GET_SOURCE_CAP_EXTENDED": "GET_SOURCE_CAP_EXTENDED",
        "BATTERY_STATUS": "BATTERY_STATUS", "ATTENTION": "ATTENTION",
    }
    for alias, canonical in ALIASES.items():
        if f"[pd_protocol] {alias}" in line:
            msg_type = canonical
            break
    # Fallback: try PD_COMMANDS values
    if msg_type is None:
        for cmd_code, cmd_name in PD_COMMANDS.items():
            if f"[pd_protocol] {cmd_name}" in line:
                msg_type = cmd_name
                break

    # Special: "Capability X:" lines are part of SRC_CAP/SNK_CAP
    if msg_type is None and "Capability" in line and ("PDO" in line or "Operated" in line):
        # This is a capability listing, associate with the nearest CAP message
        msg_type = "CAPABILITY_ENTRY"

    if msg_type is None:
        return None

    # 解析参数
    params = {}
    if msg_type in ("SOURCE_CAP", "SINK_CAP"):
        # Parse capability block
        cap_m = re.search(r'\[Caps=(\d+)\]', line)
        if cap_m:
            params["num_caps"] = int(cap_m.group(1))
        # Try to find voltage info for top-level line
        vm = re.search(r'vbus=(\d+)mV', line)
        if vm:
            params["vbus_mv"] = int(vm.group(1))
        cm = re.search(r'current=(\d+)mA', line)
        if cm:
            params["current_ma"] = int(cm.group(1))

    elif msg_type == "REQUEST":
        params = parse_request(line)

    elif msg_type == "HARD_RESET":
        if "transmitted" in line:
            params["role"] = "transmitter"
        elif "received" in line:
            params["role"] = "receiver"

    elif msg_type == "PR_SWAP":
        type_m = re.search(r'Type=(\w+)', line)
        if type_m:
            params["swap_type"] = type_m.group(1)

    elif msg_type == "GET_DESCRIPTOR":
        type_m = re.search(r'Type=(\w+)', line)
        addr_m = re.search(r'Addr=(\d+)', line)
        len_m = re.search(r'WLen=(\w+)', line)
        if type_m:
            params["desc_type"] = type_m.group(1)
        if addr_m:
            params["addr"] = int(addr_m.group(1))
        if len_m:
            params["w_len"] = type_m.group(1)

    # 计算延迟
    delay = 0.0
    if prev_ts is not None and ts is not None:
        delay = round(ts - prev_ts, 3)

    return PdMessage(
        timestamp=ts,
        direction=direction,
        message_type=msg_type,
        raw_line=line,
        params=params,
        delay_from_prev=delay,
    )


# ============================================================
# 异常检测
# ============================================================

ANOMALY_PATTERNS = [
    (r'[Tt]imeout|TIMEOUT', "消息超时未响应"),
    (r'[Rr]etransmit|RETRANSMIT', "消息重传"),
    (r'[Mm]ax\s+(?:retransmit|retry)', "达到最大重传/重试次数"),
    (r'VBUS\s+anomaly|VBUS.*异常|VBUS.*unstable|VBUS.*anomaly', "VBUS电压异常"),
    (r'[Dd]eadlock|DEADLOCK|死锁|卡死', "状态机死锁"),
    (r'[Nn]egotiation\s*(?:FAILED|失败)', "PD协商失败"),
    (r'[Hh]ard\s+Reset\s+loop|Hard Reset循环|HARD_RESET.*loop', "Hard Reset循环"),
    (r'[Ff]allback|FALLBACK', "降级回退"),
    (r'expected\s+\d+\s*,\s*actual\s+\d+', "预期值与实际值不符"),
    (r'Unknown\s+REQUEST|unexpected|Unexpected|UNEXPECTED', "非预期消息"),
]


def detect_anomalies(messages: list[PdMessage], raw_lines: list[str]) -> list[str]:
    """检测PD协商异常"""
    anomalies = []

    # 从消息级别检测
    for msg in messages:
        if msg.message_type in ("CAPABILITY_ENTRY",):
            continue
        for pattern, desc in ANOMALY_PATTERNS:
            if re.search(pattern, msg.raw_line):
                anomalies.append(f"[{msg.direction}] {desc} @ {msg.delay_from_prev:.1f}ms: {msg.raw_line.strip()}")
                break

    # 从原始日志行检测（覆盖消息解析遗漏的情况）
    for line in raw_lines:
        line = line.strip()
        if not line or "[ERROR]" not in line and "[WARN]" not in line:
            continue
        for pattern, desc in ANOMALY_PATTERNS:
            if re.search(pattern, line):
                # 避免重复
                if desc not in anomalies:
                    anomalies.append(f"{desc}: {line.strip()}")
                break

    return anomalies


# ============================================================
# 协商参数提取
# ============================================================

def extract_capabilities(messages: list[PdMessage]) -> list[dict]:
    """从消息序列中提取能力列表"""
    caps = []
    current_cap_list = []
    cap_source = "UNKNOWN"

    for msg in messages:
        if msg.message_type in ("SOURCE_CAP", "SINK_CAP"):
            if current_cap_list:
                caps.append({"source": cap_source, "items": current_cap_list.copy()})
            current_cap_list = []
            cap_source = f"{msg.direction} {msg.message_type}"
        elif msg.message_type == "CAPABILITY_ENTRY":
            if msg.params:
                current_cap_list.append(msg.params)
        elif msg.message_type == "REQUEST":
            if current_cap_list:
                caps.append({"source": cap_source, "items": current_cap_list.copy()})
                current_cap_list = []

    # 保留最后一个
    if current_cap_list:
        caps.append({"source": cap_source, "items": current_cap_list.copy()})

    return caps


def extract_negotiation_result(messages: list[PdMessage]) -> tuple[float, float, bool]:
    """提取协商结果: (voltage_mv, current_ma, success)"""
    voltage_mv = 0
    current_ma = 0
    success = False

    # 查找 PS_RDY 后面的 VBUS 稳定信息
    for i, msg in enumerate(messages):
        if msg.message_type == "PS_RDY":
            # 检查后面的日志行看VBUS状态
            raw = msg.raw_line
            vm = re.search(r'(?:VBUS|vbus).*?(\d+)mV', raw)
            if vm:
                voltage_mv = int(vm.group(1))
            # 检查是否标注成功
            if "stable" in raw.lower() or "ok" in raw.lower() or "NEGOTIATION OK" in raw.upper():
                success = True
                # 从能力或请求中推断电流
                for prev_msg in reversed(messages[:i]):
                    if prev_msg.message_type == "REQUEST" and "current_ma" in prev_msg.params:
                        current_ma = prev_msg.params["current_ma"]
                        break
            break

    # 检查失败的标志
    for msg in messages:
        if "FAILED" in msg.raw_line.upper() or "negotiation failed" in msg.raw_line.lower():
            success = False

    return voltage_mv, current_ma, success


# ============================================================
# 主解析器
# ============================================================

class PdProtocolParser:
    """PD协议日志解析器"""

    def __init__(self, source_id: str = "pd_session"):
        self.source_id = source_id
        self.messages: list[PdMessage] = []
        self.raw_lines: list[str] = []

    def parse_file(self, filepath: str) -> PdNegotiation:
        """解析PD协议日志文件"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {filepath}")

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return self.parse_lines(lines, str(path.name))

    def parse_text(self, text: str, source_id: str = None) -> PdNegotiation:
        """解析PD协议日志文本"""
        if source_id:
            self.source_id = source_id
        lines = text.splitlines()
        return self.parse_lines(lines, "inline_text")

    def parse_lines(self, lines: list[str], log_file: str) -> PdNegotiation:
        """解析日志行列表"""
        self.raw_lines = lines
        self.messages = []

        prev_ts: Optional[float] = None
        for line in lines:
            msg = parse_message(line, prev_ts)
            if msg:
                self.messages.append(msg)
                prev_ts = msg.timestamp

        # 构建协商结果
        start_ts = self.messages[0].timestamp if self.messages else 0
        end_ts = self.messages[-1].timestamp if self.messages else 0

        capabilities = extract_capabilities(self.messages)
        voltage, current, success = extract_negotiation_result(self.messages)
        anomalies = detect_anomalies(self.messages, lines)

        # 判断状态机状态
        state = self._determine_state_machine_status()

        return PdNegotiation(
            source_id=self.source_id,
            log_file=log_file,
            start_time=start_ts,
            end_time=end_ts,
            messages=self.messages,
            capabilities=capabilities,
            negotiated_voltage=voltage,
            negotiated_current=current,
            anomalies=anomalies,
            success=success,
            state_machine_status=state,
        )

    def _determine_state_machine_status(self) -> str:
        """判断状态机最终状态"""
        last_msg = self.messages[-1] if self.messages else None
        if not last_msg:
            return "EMPTY"

        raw_upper = last_msg.raw_line.upper()
        if "FAILED" in raw_upper:
            return "FAILED"
        if "HARD RESET" in raw_upper and ("LOOP" in raw_upper or "循环" in raw_upper):
            return "HARD_RESET_LOOP"
        if "STUCK" in raw_upper:
            return "STUCK"
        if "STABLE" in raw_upper or "OK" in raw_upper or "PS_RDY" in last_msg.message_type:
            return "COMPLETED"
        if "DISCONNECTED" in raw_upper:
            return "DISCONNECTED"
        return "UNKNOWN"

    def get_timeline(self) -> list[dict]:
        """获取消息时序数据（用于可视化）"""
        timeline = []
        for i, msg in enumerate(self.messages):
            timeline.append({
                "order": i + 1,
                "timestamp_ms": round(msg.delay_from_prev, 3),
                "cumulative_ms": round(sum(m.delay_from_prev for m in self.messages[:i+1]), 3),
                "direction": msg.direction,
                "message": msg.message_type,
                "params": msg.params,
                "is_anomaly": any(p in msg.raw_line for p in ["ERROR", "WARN", "Timeout", "Retransmit"]),
            })
        return timeline


# ============================================================
# CLI入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("PD协议解析器 - 解析PD协商日志")
        print("用法: python pd_parser.py <logfile> [output_json]")
        print("示例: python pd_parser.py sample_pd.log output.json")
        sys.exit(1)

    logfile = sys.argv[1]
    parser = PdProtocolParser()

    try:
        negotiation = parser.parse_file(logfile)
        result = negotiation.to_dict()

        if len(sys.argv) >= 3:
            output_path = sys.argv[2]
            Path(output_path).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            print(f"✅ 解析完成，结果已保存到: {output_path}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

        # 打印摘要
        print(f"\n📊 解析摘要:")
        print(f"  消息数: {result['message_count']}")
        print(f"  成功率: {'✅ 是' if result['negotiated']['success'] else '❌ 否'}")
        if result['negotiated']['voltage_mv']:
            print(f"  协商电压: {result['negotiated']['voltage_mv']}mV")
        if result['negotiated']['current_ma']:
            print(f"  协商电流: {result['negotiated']['current_ma']}mA")
        if result['anomalies']:
            print(f"  ⚠️  异常数: {len(result['anomalies'])}")
            for a in result['anomalies'][:3]:
                print(f"    - {a[:100]}")

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
