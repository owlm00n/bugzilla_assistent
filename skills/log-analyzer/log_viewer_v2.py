#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版交互式日志查看器 v2 - 集成关键词收纳系统
================================================
功能:
  1. AND/OR 筛选模式切换
  2. 多格式复制（正则OR/空格/换行/通配/grep）
  3. 独立模式：无log也能浏览/编辑/复制关键词库
  4. 关键词编辑/删除

关键词数据加载（三级降级）:
  1. --vault-json <file>      预生成JSON，完全解耦
  2. import keyword_vault      自动发现同目录或 PYTHONPATH
  3. subprocess 调用 export    跨 skill 目录自动查找
  4. 空数据降级                纯日志查看器模式

用法:
    python log_viewer_v2.py <logfile> --direction protocol_timeout
    python log_viewer_v2.py <logfile> --vault-json viewer_kw.json
    python log_viewer_v2.py --standalone -o vault.html
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def _load_vault_data(vault_json: str = None) -> dict:
    """加载关键词库数据，三级降级策略。

    Args:
        vault_json: 预生成的 JSON 文件路径（优先级最高）

    Returns:
        {"directions": {...}, "all_keywords": [...]}
    """
    # 🥇 策略1: 预生成 JSON 文件（完全解耦）
    if vault_json:
        try:
            with open(vault_json, encoding="utf-8") as f:
                data = json.load(f)
            if "directions" in data:
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️  无法读取 vault JSON: {e}", file=sys.stderr)

    # 🥈 策略2: import keyword_vault 模块（自动发现）
    # 先尝试从兄弟 skill 目录加载
    try:
        import importlib.util
        vault_skill_dir = SCRIPT_DIR.parent / "keyword-vault"
        vault_py = vault_skill_dir / "keyword_vault.py"
        if vault_py.exists():
            spec = importlib.util.spec_from_file_location("keyword_vault", str(vault_py))
            kv = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(kv)
            return kv.export_for_viewer()
    except Exception:
        pass

    # 再尝试直接 import（同目录或 PYTHONPATH）
    try:
        from keyword_vault import export_for_viewer
        return export_for_viewer()
    except ImportError:
        pass

    # 🥉 策略3: subprocess 调用 export 命令
    try:
        import subprocess
        vault_script = SCRIPT_DIR.parent / "keyword-vault" / "keyword_vault.py"
        if not vault_script.exists():
            vault_script = SCRIPT_DIR / "keyword_vault.py"
        if vault_script.exists():
            result = subprocess.run(
                [sys.executable, str(vault_script), "export", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
    except Exception:
        pass

    # 🏴‍☠️ 策略4: 空数据降级
    print("ℹ️  关键词库未加载，使用纯日志查看器模式", file=sys.stderr)
    print("   💡 运行 keyword_vault.py export -o viewer_kw.json 预生成关键词数据", file=sys.stderr)
    return {"directions": {}, "all_keywords": []}


def parse_log_file(filepath: str) -> list:
    lines = []
    text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        level = ""
        if "ERROR" in line:
            level = "ERROR"
        elif "WARN" in line or "WARNING" in line:
            level = "WARN"
        elif "[TX]" in line:
            level = "TX"
        elif "[RX]" in line:
            level = "RX"
        elif "INFO" in line:
            level = "INFO"
        lines.append({"num": i, "text": line, "level": level})
    return lines


def generate_viewer(logfile: str = None, output_html: str = "keyword_vault_viewer.html",
                    direction: str = "", role: str = "", standalone: bool = False,
                    vault_json: str = None) -> str:
    if standalone:
        log_lines = []
        title = "关键词管理系统"
    else:
        log_lines = parse_log_file(logfile)
        title = Path(logfile).name

    # Load keyword vault (decoupled)
    vault_data = _load_vault_data(vault_json)

    # Build direction items HTML
    direction_items = ""
    for key, info in vault_data.get("directions", {}).items():
        direction_items += f'''
            <div class="direction-item" data-direction="{key}" onclick="selectDirection('{key}')">
                <span style="font-size:0.85rem;">{_get_icon(key)}</span>
                <span class="dir-name">{info["name"]}</span>
                <span class="dir-count">{len(info["keywords"])}</span>
            </div>'''

    # Read HTML template
    template_path = SCRIPT_DIR / "log_viewer_v2_template.html"
    if template_path.exists():
        html = template_path.read_text(encoding="utf-8")
    else:
        print("ERROR: template not found", file=sys.stderr)
        sys.exit(1)

    html = html.replace("{title}", title)
    html = html.replace("{log_lines_json}", json.dumps(log_lines, ensure_ascii=False))
    html = html.replace("{keyword_vault_json}", json.dumps(vault_data, ensure_ascii=False))
    html = html.replace("{direction_items}", direction_items)
    html = html.replace("{initial_direction}", direction)
    html = html.replace("{initial_role}", role)
    html = html.replace("{is_standalone}", "true" if standalone else "false")

    Path(output_html).write_text(html, encoding="utf-8")
    return output_html


def _get_icon(key: str) -> str:
    icons = {
        "protocol_timeout": "⏱️",
        "power_mismatch": "⚡",
        "enum_failure": "🔌",
        "connection_stability": "🔗",
        "role_swap": "🔄",
        "thermal_throttle": "🌡️",
        "firmware_boot": "🐛",
    }
    return icons.get(key, "📌")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="增强版日志查看器 - 集成关键词收纳系统")
    parser.add_argument("logfile", nargs="?", help="日志文件路径（独立模式不需要）")
    parser.add_argument("--output", "-o", help="输出HTML文件路径")
    parser.add_argument("--role", "-r", help="角色 (pd_engineer/usb_engineer/test_engineer)")
    parser.add_argument("--direction", "-d", help="初始问题方向")
    parser.add_argument("--standalone", "-s", action="store_true", help="独立关键词管理模式（无需log文件）")
    parser.add_argument("--vault-json", help="预生成的关键词库 JSON 文件（完全解耦模式）")
    args = parser.parse_args()

    if args.standalone:
        output = args.output or "keyword_vault_viewer.html"
        path = generate_viewer(standalone=True, output_html=output,
                               direction=args.direction or "", role=args.role or "",
                               vault_json=args.vault_json)
        print(f"✅ 关键词管理系统已生成!")
        print(f"  输出: {path}")
        print(f"")
        print(f"  📚 功能:")
        print(f"     - 浏览/编辑/删除关键词")
        print(f"     - 多格式复制（正则OR/空格/换行/通配/grep）")
        print(f"     - 添加新关键词到指定方向")
    elif args.logfile:
        output = args.output or f"{Path(args.logfile).stem}_viewer_v2.html"
        path = generate_viewer(args.logfile, output, direction=args.direction or "",
                               role=args.role or "", vault_json=args.vault_json)
        print(f"✅ 日志查看器 v2 已生成!")
        print(f"  输入: {args.logfile} ({len(parse_log_file(args.logfile))} 行)")
        print(f"  输出: {path}")
        print(f"")
        print(f"  🎯 新功能:")
        print(f"     - AND/OR 筛选模式切换")
        print(f"     - 多格式复制（正则OR/空格/换行/通配/grep）")
        print(f"     - 关键词编辑/删除")
        print(f"     - 独立模式: --standalone")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
