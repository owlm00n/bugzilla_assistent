#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Log智能分析器 - 角色感知日志分析
基于角色画像自动识别日志类型、筛选关键信息、检测异常模式。

用法:
    python log_analyzer.py <logfile> [--role <role_key>] [--json] [--deep]
    python log_analyzer.py sample_pd.log --role pd_engineer
"""

import json
import re
import sys
import io
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR / "config"

# ============================================================
# 异常模式库
# ============================================================

ANOMALY_PATTERNS = [
    # CRITICAL级别
    ("[Pp]anic|Kernel[ _]panic|BUG:|Call[ _]Trace|Oops|general[ _]protection",
     "CRITICAL", "系统级异常"),
    ("deadlock|死锁| Deadlock", "CRITICAL", "死锁检测"),
    ("hardware[ _]error|Hardware Error|MC Error", "CRITICAL", "硬件错误"),
    ("OOM|out[ _]of[ _]memory|Out of Memory", "CRITICAL", "内存不足"),

    # ERROR级别
    ("[Ee]rror|ERROR|error:", "ERROR", "错误"),
    ("[Ff]ailed|[Ff]ail|[Ff]AIL|FAILED", "ERROR", "操作失败"),
    ("[Tt]imeout|TIMEOUT|超时", "ERROR", "超时"),
    ("[Rr]etransmit|[Rr]etry|RETRY|retrying", "ERROR", "重传/重试"),
    ("[Mm]ax[ _](?:retransmit|retry|retries)|达到最大重试", "ERROR", "达到最大重试次数"),
    ("[Hh]ard[ _]?reset|HARD_RESET", "ERROR", "Hard Reset"),
    ("[Rr]eject|REJECT", "ERROR", "消息被拒绝"),
    ("VBUS[ _]*(anomaly|error|fault|unstable|异常|故障)", "ERROR", "VBUS异常"),
    ("[Nn]egotiation[ _]*(?:FAILED|失败|fail)", "ERROR", "协商失败"),
    ("enumeration[ _]*(?:FAILED|失败|fail)", "ERROR", "枚举失败"),
    ("descriptor[ _]*(?:read|get)[ _]*(?:timeout|fail)", "ERROR", "描述符读取失败"),

    # WARNING级别
    ("[Ww]arn|[Ww]ARNING|warn:", "WARNING", "警告"),
    ("slow|Slow|延迟|latency", "WARNING", "性能降级"),
    ("[Dd]eviation|deviation|偏差", "WARNING", "偏差检测"),
    ("[Rr]ecovery|recovery|恢复", "WARNING", "恢复操作"),
    ("[Cc]ompatibility|compatibility|兼容", "WARNING", "兼容性问题"),
    ("[Tt]hermal|thermal|Thermal|温度", "WARNING", "温度相关"),
]

# 角色关键词映射（不依赖yaml文件，内建默认配置）
DEFAULT_ROLES = {
    "pd_engineer": {
        "display_name": "PD充电工程师",
        "keywords": [
            "PD", "VBUS", "SRC_CAP", "SNK_CAP", "REQUEST", "ACCEPT",
            "PS_RDY", "PDO", "APDO", "PR_SWAP", "DR_SWAP", "FR_SWAP",
            "HARD_RESET", "WAIT", "REJECT", "NEGOTIATION", "voltage",
            "current", "power", "power_tree", "tcpm", "charger"
        ],
        "modules": ["pd_protocol", "charger_manager", "vbus_control", "tcpm"],
    },
    "usb_engineer": {
        "display_name": "USB驱动工程师",
        "keywords": [
            "USB", "Device Descriptor", "Config Descriptor", "Interface Descriptor",
            "String Descriptor", "Endpoint", "ENUM", "Enumeration", "Reset",
            "Address", "bDeviceClass", "idVendor", "idProduct", "bcdUSB",
            "Hub", "Port", "xhci", "ehci", "usb_core", "usb_host"
        ],
        "modules": ["usb_core", "usb_host", "usb_device", "hub_driver", "xhci"],
    },
    "test_engineer": {
        "display_name": "测试工程师",
        "keywords": [
            "ERROR", "WARN", "FAIL", "TIMEOUT", "Reset", "Recovery",
            "Regression", "Test", "Pass", "Power", "Thermal"
        ],
        "modules": ["kernel", "power", "usb", "pd", "thermal", "charger"],
    },
}


# ============================================================
# 角色画像加载
# ============================================================

def load_role_config(role_key: str) -> dict:
    """加载角色画像配置"""
    if role_key in DEFAULT_ROLES:
        return DEFAULT_ROLES[role_key]

    # 尝试从yaml文件加载
    config_path = CONFIG_DIR / f"{role_key}.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except ImportError:
            # Fallback: simple YAML parser for basic key-value
            return _simple_yaml_parse(config_path)
        except Exception:
            pass

    # 回退到默认
    return DEFAULT_ROLES.get("test_engineer", DEFAULT_ROLES["pd_engineer"])


def _simple_yaml_parse(path: Path) -> dict:
    """简易YAML解析（无需PyYAML依赖）"""
    result = {}
    current_list_key = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.strip().startswith("#"):
                continue
            # List item
            m = re.match(r'^\s+- "(.+)"$', line)
            if m and current_list_key:
                result[current_list_key].append(m.group(1))
                continue
            m = re.match(r'^\s+- (.+)$', line)
            if m and current_list_key:
                result[current_list_key].append(m.group(1))
                continue
            # Key-value
            m = re.match(r'^(\w+):\s+"?(.+?)"?\s*$', line)
            if m:
                current_list_key = None
                val = m.group(2)
                # Check if next lines are list items
                result[m.group(1)] = val
                continue
            m = re.match(r'^(\w+):\s*\[\s*(.+?)\s*\]$', line)
            if m:
                current_list_key = None
                items = [i.strip().strip('"').strip("'") for i in m.group(2).split(",")]
                result[m.group(1)] = items
                continue
            # Key with list on next lines
            m = re.match(r'^(\w+):\s*$', line)
            if m:
                result[m.group(1)] = []
                current_list_key = m.group(1)
                continue
    return result


# ============================================================
# 日志分析
# ============================================================

def detect_log_type(text: str) -> str:
    """检测日志类型"""
    text_lower = text.lower()

    pd_markers = ["pd_protocol", "SRC_CAP", "SNK_CAP", "VBUS", "PDO", "APDO",
                  "PR_SWAP", "PS_RDY", "REQUEST", "ACCEPT", "REJECT"]
    usb_markers = ["usb_core", "Device Descriptor", "Config Descriptor",
                   "enumeration", "Endpoint", "bcdUSB", "idVendor", "idProduct"]
    kernel_markers = ["kernel", "dmesg", "[<", "Call Trace", "Modules linked"]

    pd_count = sum(1 for m in pd_markers if m.lower() in text_lower)
    usb_count = sum(1 for m in usb_markers if m.lower() in text_lower)
    kernel_count = sum(1 for m in kernel_markers if m.lower() in text_lower)

    if pd_count >= usb_count and pd_count > 0:
        return "pd"
    elif usb_count > pd_count and usb_count > 0:
        return "usb"
    elif kernel_count > 0:
        return "kernel"
    elif pd_count > 0 or usb_count > 0:
        return "mixed"
    return "generic"


def extract_timestamp(line: str) -> Optional[float]:
    """提取时间戳(ms)"""
    m = re.search(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\]', line)
    if m:
        ts_str = m.group(1)
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        return dt.timestamp() * 1000
    return None


def analyze_log(text: str, role_key: str = None, deep: bool = False) -> dict:
    """分析日志"""
    lines = text.splitlines()

    # 检测日志类型
    log_type = detect_log_type(text)

    # 加载角色配置
    role_config = load_role_config(role_key) if role_key else DEFAULT_ROLES["test_engineer"]
    role_name = role_config.get("display_name", role_config.get("role", "通用分析"))
    focus_keywords = role_config.get("keywords", [])
    concern_modules = role_config.get("modules", [])

    # 解析事件
    events = []
    anomalies = []
    role_relevant_lines = []
    line_count = 0
    error_count = 0
    warn_count = 0

    prev_ts = None
    for line in lines:
        ts = extract_timestamp(line)
        line_count += 1

        if ts is None:
            continue

        delay = 0.0
        if prev_ts is not None:
            delay = round(ts - prev_ts, 3)
        prev_ts = ts

        # 检测异常
        for pattern, severity, desc in ANOMALY_PATTERNS:
            if re.search(pattern, line):
                events.append({
                    "time_ms": round(ts, 1),
                    "delay_ms": delay,
                    "severity": severity,
                    "type": desc,
                    "line": line.strip()[:200],
                })
                anomalies.append({
                    "severity": severity,
                    "type": desc,
                    "message": line.strip()[:150],
                    "time_ms": round(ts, 1),
                })
                if severity == "ERROR":
                    error_count += 1
                elif severity == "WARNING":
                    warn_count += 1
                break

        # 角色相关行
        if focus_keywords:
            for kw in focus_keywords:
                if kw.lower() in line.lower():
                    role_relevant_lines.append({
                        "time_ms": round(ts, 1),
                        "delay_ms": delay,
                        "line": line.strip()[:200],
                    })
                    break

    # 计算时间范围
    times = [e["time_ms"] for e in events]
    start_ts = min(times) if times else 0
    end_ts = max(times) if times else 0
    duration_ms = round(end_ts - start_ts, 1) if times else 0

    # 角色相关统计
    role_keywords_hit = {}
    for entry in role_relevant_lines:
        line = entry["line"]
        for kw in focus_keywords:
            if kw.lower() in line.lower():
                role_keywords_hit[kw] = role_keywords_hit.get(kw, 0) + 1

    # 深度分析
    analysis = {}
    if deep:
        analysis = _deep_analysis(log_type, anomalies, role_config, text)

    return {
        "log_type": log_type,
        "role": role_name,
        "role_key": role_key or "generic",
        "summary": {
            "total_lines": line_count,
            "events": len(events),
            "anomalies": len(anomalies),
            "error_count": error_count,
            "warn_count": warn_count,
            "duration_ms": duration_ms,
            "start_time_ms": start_ts,
            "end_time_ms": end_ts,
        },
        "anomalies": anomalies[:50],  # Limit output
        "timeline": events[:100],  # Limit output
        "role_relevant": {
            "keywords_hit": role_keywords_hit,
            "relevant_line_count": len(role_relevant_lines),
            "top_relevant_lines": role_relevant_lines[:20],
        },
        "analysis": analysis,
    }


def _deep_analysis(log_type: str, anomalies: list, role_config: dict, text: str) -> dict:
    """深度分析：根因假设 + 建议"""
    hypotheses = []
    recommendations = []

    anomaly_types = [a["type"] for a in anomalies]
    anomaly_severities = [a["severity"] for a in anomalies]

    if log_type == "pd":
        # PD-specific analysis
        if "协商失败" in anomaly_types or "REJECT" in "".join(a["message"] for a in anomalies):
            hypotheses.append({
                "cause": "PD协商失败 - PDO能力不匹配",
                "confidence": "high",
                "evidence": "检测到协商失败或REJECT消息",
            })
            recommendations.extend([
                "检查SRC_CAP和REQUEST的PDO匹配情况",
                "确认电压/电流请求在源端能力范围内",
                "检查PDO类型(Fixed/Variable/APDO)是否兼容",
            ])

        if "VBUS异常" in anomaly_types:
            hypotheses.append({
                "cause": "VBUS电压异常",
                "confidence": "high",
                "evidence": "检测到VBUS电压异常或偏差",
            })
            recommendations.extend([
                "检查负载调整和线路压降",
                "确认VBUS线缆质量和长度",
                "检查充电器和负载的动态响应",
            ])

        if "Hard Reset" in anomaly_types:
            hypotheses.append({
                "cause": "PD Hard Reset循环",
                "confidence": "medium",
                "evidence": "检测到Hard Reset消息",
            })
            recommendations.extend([
                "检查Hard Reset触发原因",
                "确认HARD_RESET后重新协商流程",
                "检查是否存在持续的故障条件导致反复Reset",
            ])

    elif log_type == "usb":
        # USB-specific analysis
        if "枚举失败" in anomaly_types or "描述符读取失败" in anomaly_types:
            hypotheses.append({
                "cause": "USB枚举失败 - 描述符读取异常",
                "confidence": "high" if "ERROR" in anomaly_severities else "medium",
                "evidence": "枚举或描述符读取失败",
            })
            recommendations.extend([
                "检查USB线缆连接质量和长度",
                "尝试不同USB端口(2.0/3.0)",
                "检查设备固件版本",
                "确认USB控制器驱动正常",
            ])

        if "超时" in anomaly_types:
            hypotheses.append({
                "cause": "USB通信超时",
                "confidence": "medium",
                "evidence": "检测到超时异常",
            })
            recommendations.extend([
                "增加USB事务超时时间",
                "检查USB总线负载和带宽",
                "确认USB Hub供电充足",
            ])

    # 通用建议
    if not hypotheses:
        hypotheses.append({
            "cause": "无明显根因 - 需要更多上下文",
            "confidence": "low",
            "evidence": "检测到的异常可能是副作用而非根因",
        })

    if "ERROR" in anomaly_severities and not recommendations:
        recommendations.append("检查最近的代码变更或配置更新")
        recommendations.append("对比正常工作的日志基线")

    return {
        "hypotheses": hypotheses,
        "recommendations": recommendations,
    }


def format_text_report(result: dict) -> str:
    """生成文本分析报告"""
    s = result["summary"]
    lines = []
    lines.append("=" * 60)
    lines.append(f"  日志分析报告 | 类型: {result['log_type']} | 角色: {result['role']}")
    lines.append("=" * 60)
    lines.append(f"  总行数: {s['total_lines']}")
    lines.append(f"  事件数: {s['events']}")
    lines.append(f"  异常数: {s['anomalies']} (ERROR: {s['error_count']}, WARN: {s['warn_count']})")
    lines.append(f"  时长: {s['duration_ms']:.1f}ms")
    lines.append("")

    # 异常详情
    if result["anomalies"]:
        lines.append("## 异常发现")
        severity_groups = {}
        for a in result["anomalies"]:
            severity_groups.setdefault(a["severity"], []).append(a)

        for sev in ["CRITICAL", "ERROR", "WARNING"]:
            items = severity_groups.get(sev, [])
            if not items:
                continue
            icon = {"CRITICAL": "💀", "ERROR": "❌", "WARNING": "⚠️"}.get(sev, "•")
            lines.append(f"\n### {icon} {sev} ({len(items)})")
            for a in items[:5]:
                lines.append(f"  - [{a['type']}] {a['message'][:100]}")
            if len(items) > 5:
                lines.append(f"  ... 还有 {len(items)-5} 处异常")

    # 角色相关关键词命中
    rr = result.get("role_relevant", {})
    if rr.get("keywords_hit"):
        lines.append(f"\n## 角色关键词命中 ({rr['relevant_line_count']} 行相关)")
        for kw, count in sorted(rr["keywords_hit"].items(), key=lambda x: -x[1])[:10]:
            lines.append(f"  {kw}: {count} 次")

    # 深度分析
    analysis = result.get("analysis", {})
    if analysis:
        hypotheses = analysis.get("hypotheses", [])
        if hypotheses:
            lines.append(f"\n## 根因分析")
            for h in hypotheses:
                conf_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(h["confidence"], "⚪")
                lines.append(f"  {conf_icon} [{h['confidence']}] {h['cause']}")
                lines.append(f"     证据: {h['evidence']}")

        recommendations = analysis.get("recommendations", [])
        if recommendations:
            lines.append(f"\n## 建议")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"  {i}. {rec}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Log智能分析器 - 角色感知日志分析")
    parser.add_argument("logfile", help="日志文件路径")
    parser.add_argument("--role", "-r", help="角色画像 key (pd_engineer/usb_engineer/test_engineer)")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--deep", "-d", action="store_true", help="深度分析模式")
    args = parser.parse_args()

    path = Path(args.logfile)
    if not path.exists():
        print(f"文件不存在: {args.logfile}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8", errors="replace")

    result = analyze_log(text, role_key=args.role, deep=args.deep)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(format_text_report(result))


if __name__ == "__main__":
    main()
