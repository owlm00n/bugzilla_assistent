#!/usr/bin/env python3
"""
渐进式协议日志提取器 - Progressive Protocol Log Extractor

策略: 多级提取 + 质量检查，宁可多抓不漏，AI 来过滤噪音。

Level 0: 特定格式提取（高置信度）
  ├── 展锐: sprd_tcpm_log / sprd_pd_log / sc27xx-typec-pd
  ├── 通用: [pd_protocol] / [usb_core] / [cc_protocol]
  └── 高通: pmic_pd / qcom_pd

Level 1: 协议关键词宽松匹配（中置信度）
  └── PD/CC/USB 消息类型 + 状态机关键词

Level 2: 超宽匹配（低置信度，兜底）
  └── charger/battery/VBUS/CC/Type-C/5V/9V/20V...

Level 3: 裸传（未知置信度，终极兜底）
  └── 什么都没匹配到 → 传尾部 N 行给 AI 判断

输出: JSON with confidence + extracted text
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

# ============================================================
# Level 0: 特定格式提取器
# ============================================================

SPECIFIC_FORMATS = {
    "sprd_tcpm": {
        "patterns": [r"\[sprd_tcpm_log\]", r"\[sprd_pd_log\]", r"\[sc27xx-typec-pd[^\]]*\]"],
        "label": "展锐 SC27XX TCPM/PD",
        "min_hits": 5,
    },
    "generic_pd": {
        "patterns": [r"\[pd_protocol\]", r"\[pd_controller\]", r"\[pd_phy\]"],
        "label": "通用 PD Protocol",
        "min_hits": 3,
    },
    "generic_usb": {
        "patterns": [r"\[usb_core\]", r"\[usb_host\]", r"\[dwc3\]", r"\[xhci\]"],
        "label": "通用 USB Core",
        "min_hits": 3,
    },
    "generic_cc": {
        "patterns": [r"\[cc_protocol\]", r"\[cc_logic\]", r"\[cc_state\]"],
        "label": "通用 CC Protocol",
        "min_hits": 3,
    },
    "qcom_pd": {
        "patterns": [r"\[pmic_pd\]", r"\[qcom_pd\]", r"\[qpnp_pd\]", r"\[smb.*pd\]"],
        "label": "高通 PMIC PD",
        "min_hits": 3,
    },
    "mtk_tcpc": {
        "patterns": [r"\[mtk_tcpc\]", r"\[mtk_pd\]", r"\[mt6360\]", r"\[mt6370\]"],
        "label": "MTK TCPC",
        "min_hits": 3,
    },
    "fusb": {
        "patterns": [r"\[fusb302\]", r"\[fusb\]", r"\[tcpci\]"],
        "label": "FUSB302/TCPCI",
        "min_hits": 3,
    },
}

# ============================================================
# Level 1: 协议关键词（中置信度）
# ============================================================

PROTOCOL_KEYWORDS = [
    # PD 消息类型（精确匹配，避免误匹配）
    "SRC_CAP", "SNK_CAP", "SOURCE_CAP", "SINK_CAP",
    "PS_RDY", "PR_SWAP", "DR_SWAP", "FR_SWAP", "VCONN_SWAP",
    "HARD_RESET", "SOFT_RESET",
    "GET_SOURCE_CAP", "GET_SINK_CAP",
    "VDM", "VENDOR_DEFINED", "Discover Identity",
    "BIST", "PING", "WAIT",
    "PD TX", "PD RX", "PD_MSG",
    "PDO 0:", "PDO 1:", "PDO 2:", "PDO 3:", "PDO 4:", "PDO 5:",
    "APDO", "RDO",

    # PD 状态机
    "pd_capable", "pd_connect", "pd_negotiation",
    "SNK_READY", "SNK_UNATTACHED", "SNK_ATTACHED",
    "SRC_READY", "SRC_UNATTACHED", "SRC_ATTACHED",
    "TOGGLING", "ATTACH_WAIT", "DEBOUNCED",
    "WAIT_CAPABILITIES", "NEGOTIATE_CAPABILITIES",
    "TRANSITION_SINK", "SNK_STARTUP", "SNK_DISCOVERY",

    # Type-C CC
    "CC1:", "CC2:", "CC1 =", "CC2 =",
    "Rp=", "Rd=", "VCONN",
    "polarity", "current_capability", "get_rp_limit",

    # USB 枚举
    "GET_DESCRIPTOR", "SET_ADDRESS", "SET_CONFIGURATION",
    "Device Descriptor", "Config Descriptor",
    "idVendor", "idProduct", "bcdUSB",
    "bDeviceClass", "bNumConfigurations",
    "enumeration", "enumerate",

    # PD header 十六进制（展锐格式特有）
    "header: 0x", "header = 0x", "msg header = 0x",
    "PD RX, header", "PD TX, header",
]

# ============================================================
# Level 2: 超宽匹配（低置信度，兜底）
# ============================================================

FALLBACK_KEYWORDS = [
    # 充电相关
    "charger", "charging", "charge",
    "battery", "batt", "VBUS", "vbus",
    "vbus_present", "vbus_online",
    "Setting voltage", "voltage/current limit",

    # Type-C
    "typec", "type_c", "TYPE_C", "Type-C",
    "CC", "cc_state", "cc_protocol",

    # USB
    "usb_core", "USB", "musb", "dwc3",

    # 电压值（PD 协商相关）
    "5000 mV", "9000 mV", "12000 mV", "15000 mV", "20000 mV",
    "5V", "9V", "12V", "15V", "20V",
    "3000 mA", "5000 mA",

    # 异常
    "timeout", "Timeout", "TIMEOUT",
    "retransmit", "Retransmit",
    "FAILED", "failed",
    "deadlock", "DEADLOCK",
    "hard reset loop", "Hard Reset loop",
    "debounce fail", "debounce timeout",
]


# ============================================================
# 行清洗器
# ============================================================

def clean_line(line: str, matched_format: Optional[str] = None) -> str:
    """清洗日志行，去掉内核前缀噪音，保留核心内容"""
    # 展锐 sprd_tcpm_log
    m = re.search(r'\[sprd_tcpm_log\]\s*(.+)', line)
    if m:
        return f"[TCPM] {m.group(1)}"
    # 展锐 sprd_pd_log
    m = re.search(r'\[sprd_pd_log\]\s*(.+)', line)
    if m:
        return f"[PD] {m.group(1)}"
    # 展锐 sc27xx-typec-pd
    m = re.search(r'\[sc27xx-typec-pd[^\]]*\]\s*(.+)', line)
    if m:
        return f"[SC27XX] {m.group(1)}"
    # 展锐 charger-manager
    m = re.search(r'\[charger-manager[^\]]*\]\s*(.+)', line)
    if m:
        return f"[CHG] {m.group(1)}"
    # 展锐 power_supply
    m = re.search(r'power_supply\s+\S+:\s*(.+)', line)
    if m:
        return f"[PSY] {m.group(1)}"
    # 通用格式: 去掉内核日志前缀
    # [timestamp] [LEVEL] [tag] message
    line = re.sub(r'^[0-9A-Fa-f]+\s+<\d+>\s*', '', line)
    line = re.sub(r'^\[\s*[\d.]+\s*\](?:\s*\[[\d\-:\s.]+\])?\s*T\d+@C\d+;\s*', '', line)
    line = re.sub(r'^\[\d+\s*/\s*\d+\]\s*', '', line)
    return line.strip()


def extract_timestamp(line: str) -> Optional[float]:
    """提取时间戳（秒），用于排序"""
    # 展锐格式: [   48.925429]
    m = re.search(r'\[\s*([\d.]+)\s*\]', line)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # 标准格式: [2026-05-15 14:28:01.123]
    m = re.search(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\]', line)
    if m:
        from datetime import datetime
        try:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
            return dt.timestamp()
        except ValueError:
            pass
    return None


# ============================================================
# 渐进式提取
# ============================================================

def extract(filepath: str, max_lines: int = 1000) -> dict:
    """
    渐进式提取协议相关内容。

    返回:
    {
        "confidence": "high" | "medium" | "low" | "unknown",
        "matched_format": "sprd_tcpm" | "generic_pd" | ... | None,
        "total_lines": N,
        "filtered_lines": N,
        "protocol_types": ["PD", "CC", "USB"],
        "text": "清洗后的协议文本",
        "warnings": ["如果提取结果为空或很少的警告"],
    }
    """
    path = Path(filepath)
    if not path.exists():
        return {
            "confidence": "unknown",
            "error": f"File not found: {filepath}",
            "text": "",
        }

    raw_text = path.read_text(encoding="utf-8", errors="replace")
    all_lines = raw_text.splitlines()
    total_lines = len(all_lines)

    # ---- Level 0: 特定格式提取 ----
    for fmt_name, fmt_cfg in SPECIFIC_FORMATS.items():
        matched = []
        for line in all_lines:
            if any(re.search(p, line) for p in fmt_cfg["patterns"]):
                matched.append(line)
        if len(matched) >= fmt_cfg["min_hits"]:
            cleaned = [clean_line(l, fmt_name) for l in matched]
            text = _sort_and_join(cleaned)
            return {
                "confidence": "high",
                "matched_format": fmt_name,
                "format_label": fmt_cfg["label"],
                "total_lines": total_lines,
                "filtered_lines": len(cleaned),
                "protocol_types": _detect_types(text),
                "text": text,
            }

    # ---- Level 1: 协议关键词宽松匹配 ----
    matched = []
    for line in all_lines:
        for kw in PROTOCOL_KEYWORDS:
            if kw in line:
                matched.append(line)
                break
        if len(matched) >= max_lines:
            break

    if len(matched) >= 10:
        cleaned = [clean_line(l) for l in matched]
        text = _sort_and_join(cleaned)
        return {
            "confidence": "medium",
            "matched_format": "keyword_match",
            "format_label": "关键词匹配",
            "total_lines": total_lines,
            "filtered_lines": len(cleaned),
            "protocol_types": _detect_types(text),
            "text": text,
            "warnings": ["未命中特定格式提取器，使用关键词匹配（中置信度）"],
        }

    # ---- Level 2: 超宽匹配 ----
    matched = []
    for line in all_lines:
        line_lower = line.lower()
        for kw in FALLBACK_KEYWORDS:
            if kw.lower() in line_lower:
                matched.append(line)
                break
        if len(matched) >= max_lines:
            break

    if len(matched) > 0:
        cleaned = [clean_line(l) for l in matched]
        text = _sort_and_join(cleaned)
        return {
            "confidence": "low",
            "matched_format": "fallback",
            "format_label": "超宽匹配（兜底）",
            "total_lines": total_lines,
            "filtered_lines": len(cleaned),
            "protocol_types": _detect_types(text),
            "text": text,
            "warnings": [
                "未命中特定格式和关键词提取器",
                "使用超宽匹配，可能包含大量噪音",
                "建议人工确认提取结果",
            ],
        }

    # ---- Level 3: 裸传 ----
    tail_lines = all_lines[-200:]
    text = "\n".join(tail_lines)
    return {
        "confidence": "unknown",
        "matched_format": "raw_tail",
        "format_label": "裸传（尾部200行）",
        "total_lines": total_lines,
        "filtered_lines": len(tail_lines),
        "protocol_types": [],
        "text": text,
        "warnings": [
            "⚠️ 所有提取器均未命中！",
            "已返回日志尾部 200 行原始内容",
            "请 AI 判断是否包含协议交互内容",
        ],
    }


def _sort_and_join(lines: list[str]) -> str:
    """按时间戳排序后拼接"""
    timed = []
    for line in lines:
        ts = extract_timestamp(line)
        timed.append((ts if ts is not None else 0, line))
    timed.sort(key=lambda x: x[0])
    return "\n".join(line for _, line in timed)


def _detect_types(text: str) -> list[str]:
    """检测协议类型"""
    types = []
    pd_markers = [
        "SRC_CAP", "SNK_CAP", "PS_RDY", "PR_SWAP", "PD TX", "PD RX",
        "PDO", "pd_protocol", "sprd_pd_log", "sprd_tcpm_log",
        "header: 0x", "header = 0x", "REQUEST", "ACCEPT",
    ]
    cc_markers = [
        "CC1:", "CC2:", "TOGGLING", "ATTACH_WAIT", "ATTACHED",
        "typec", "type_c", "VCONN", "Rp=", "Rd=",
        "SNK_UNATTACHED", "SNK_READY", "polarity",
    ]
    usb_markers = [
        "GET_DESCRIPTOR", "SET_ADDRESS", "Device Descriptor",
        "enumeration", "idVendor", "idProduct", "bcdUSB",
        "usb_core", "Config Descriptor",
    ]
    if any(m in text for m in pd_markers):
        types.append("PD")
    if any(m in text for m in cc_markers):
        types.append("CC")
    if any(m in text for m in usb_markers):
        types.append("USB")
    return types if types else ["UNKNOWN"]


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("渐进式协议日志提取器")
        print()
        print("用法: python smart_extractor.py <logfile> [--max N] [--text]")
        print()
        print("提取级别:")
        print("  Level 0: 特定格式 (sprd_tcpm/pd_protocol/qcom_pd...) → confidence=high")
        print("  Level 1: 协议关键词匹配 → confidence=medium")
        print("  Level 2: 超宽匹配 → confidence=low")
        print("  Level 3: 裸传尾部 → confidence=unknown")
        print()
        print("选项:")
        print("  --max N    最大提取行数 (默认 1000)")
        print("  --text     仅输出文本（默认输出 JSON）")
        sys.exit(1)

    logfile = sys.argv[1]
    max_lines = 1000
    text_only = False

    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_lines = int(sys.argv[i + 1])
        if arg == "--text":
            text_only = True

    result = extract(logfile, max_lines)

    if text_only:
        print(result.get("text", ""))
        if result.get("warnings"):
            print("\n--- 警告 ---")
            for w in result["warnings"]:
                print(f"  {w}")
    else:
        # 输出 JSON（text 字段可能很大，放最后）
        output = {k: v for k, v in result.items() if k != "text"}
        output["text_preview"] = result.get("text", "")[:500]
        output["text_length"] = len(result.get("text", ""))
        print(json.dumps(output, ensure_ascii=False, indent=2))
        print("\n--- 完整文本请用 --text 参数输出 ---")


if __name__ == "__main__":
    main()
