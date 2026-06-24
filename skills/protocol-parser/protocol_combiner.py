#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议解析组合器 - Protocol Parser Combiner
自动检测日志类型(PD协商/USB枚举/混合)，组合解析并生成可视化HTML报告。

用法:
    python protocol_combiner.py <logfile> [output_html]
    python protocol_combiner.py sample_pd.log report.html
"""

import json
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add parsers directory to path
SCRIPT_DIR = Path(__file__).parent
PARSERS_DIR = SCRIPT_DIR / "parsers"
TEMPLATES_DIR = SCRIPT_DIR / "templates"

import sys
sys.path.insert(0, str(PARSERS_DIR))

from pd_parser import PdProtocolParser
from usb_parser import UsbProtocolParser
from cc_parser import CcProtocolParser


def detect_log_type(filepath: str) -> str:
    """检测日志类型"""
    text = Path(filepath).read_text(encoding="utf-8", errors="replace")

    pd_markers = ["pd_protocol", "PD", "PD Charger", "VBUS", "SRC_CAP", "SNK_CAP", "PR_SWAP"]
    usb_markers = ["usb_core", "USB", "USB Host", "Device Descriptor", "Config Descriptor", "enumeration"]
    cc_markers = ["cc_protocol", "cc_state", "CC", "Type-C", "TYPE_C", "VCONN", "Rp=", "Rd="]

    pd_count = sum(1 for m in pd_markers if m.lower() in text.lower())
    usb_count = sum(1 for m in usb_markers if m.lower() in text.lower())
    cc_count = sum(1 for m in cc_markers if m.lower() in text.lower())

    if pd_count > usb_count and pd_count > cc_count:
        return "pd"
    elif usb_count > pd_count and usb_count > cc_count:
        return "usb"
    elif cc_count > pd_count and cc_count > usb_count:
        return "cc"
    elif pd_count > 0 and usb_count > 0:
        return "mixed"
    elif pd_count > 0 and cc_count > 0:
        return "mixed"
    elif usb_count > 0 and cc_count > 0:
        return "mixed"
    else:
        return "unknown"


def parse_all(filepath: str) -> dict:
    """解析所有类型的日志"""
    log_type = detect_log_type(filepath)
    result = {
        "log_type": log_type,
        "log_file": filepath,
    }

    if log_type in ("pd", "mixed"):
        try:
            pd_parser = PdProtocolParser()
            pd_result = pd_parser.parse_file(filepath)
            result["pd"] = pd_result.to_dict()
        except Exception as e:
            result["pd_error"] = str(e)

    if log_type in ("usb", "mixed"):
        try:
            usb_parser = UsbProtocolParser()
            usb_result = usb_parser.parse_file(filepath)
            result["usb"] = usb_result.to_dict()
        except Exception as e:
            result["usb_error"] = str(e)

    if log_type in ("cc", "mixed"):
        try:
            cc_parser = CcProtocolParser()
            cc_result = cc_parser.parse_file(filepath)
            result["cc"] = cc_result.to_dict()
        except Exception as e:
            result["cc_error"] = str(e)

    return result


def generate_report(data: dict, output_html: str, template_path: str = None) -> str:
    """生成HTML可视化报告"""
    if template_path is None:
        template_path = str(TEMPLATES_DIR / "visualization.html")

    html_template = Path(template_path).read_text(encoding="utf-8")

    # For now, inject data as JSON into the template
    # The Jinja2-like template needs simple substitution
    # Since we may not have Jinja2, use manual replacement
    data_json = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    html = html_template.replace("{% raw %}", "").replace("{% endraw %}", "")
    html = html.replace("{{ data_json | tojson }}", data_json)

    # Title based on log type
    type_label = {"pd": "PD协议解析", "usb": "USB枚举解析", "cc": "Type-C CC协议解析", "mixed": "混合协议解析"}.get(data.get("log_type", ""), "协议解析")
    html = html.replace("⚡ PD协议解析可视化", f"⚡ {type_label}可视化", 1)

    Path(output_html).write_text(html, encoding="utf-8")
    return output_html


def main():
    if len(sys.argv) < 2:
        print("协议解析组合器 - 自动检测日志类型并生成可视化报告")
        print("用法: python protocol_combiner.py <logfile> [output_html]")
        sys.exit(1)

    logfile = sys.argv[1]

    # Parse
    data = parse_all(logfile)

    # Output JSON
    json_output = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    if len(sys.argv) >= 3:
        # Also generate HTML report
        output_html = sys.argv[2]
        html_path = generate_report(data, output_html)
        print(f"✅ 解析完成!")
        print(f"  日志类型: {data['log_type']}")
        print(f"  JSON结果已输出到控制台")
        print(f"  HTML报告: {html_path}")
    else:
        print(json_output)

    # Print summary
    print(f"\n📊 解析摘要:")
    if "pd" in data:
        n = data["pd"]
        print(f"\n  PD协议:")
        print(f"    消息数: {n['message_count']}")
        print(f"    成功率: {'✅' if n['negotiated']['success'] else '❌'}")
        if n['negotiated']['voltage_mv']:
            print(f"    电压: {n['negotiated']['voltage_mv']/1000:.1f}V")
        if n['anomalies']:
            print(f"    异常: {len(n['anomalies'])} 处")
    if "usb" in data:
        n = data["usb"]
        print(f"\n  USB枚举:")
        print(f"    事件数: {n['event_count']}")
        print(f"    USB版本: {n['device']['usb_version']}")
        print(f"    VID/PID: {n['device']['vendor_id']}/{n['device']['product_id']}")
        print(f"    成功率: {'✅' if n['success'] else '❌'}")
    if "cc" in data:
        n = data["cc"]
        print(f"\n  Type-C CC:")
        print(f"    事件数: {n['event_count']}")
        print(f"    初始状态: {n['cc_state']['initial']}")
        print(f"    最终状态: {n['cc_state']['final']}")
        print(f"    电流能力: {n['cc_state']['current_capability']}")
        print(f"    角色: {n['cc_state']['role']}")
        print(f"    连接成功: {'✅' if n['success'] else '❌'}")
        if n['anomalies']:
            print(f"    异常: {len(n['anomalies'])} 处")


if __name__ == "__main__":
    main()
