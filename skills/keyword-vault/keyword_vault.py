#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键词收纳系统 (Keyword Vault)
==============================
按问题方向分类管理调试关键词，支持：
1. 按方向分类存储关键词（协议超时、功率不匹配、枚举失败等）
2. 自动学习：从用户交互中识别新关键词并收纳
3. 方向标记：用户可主动标记问题方向，调用对应关键词集
4. 导出为 log_viewer 可用的搜索建议

数据结构:
    vault.json
    {
      "directions": {
        "protocol_timeout": {
          "name": "协议超时问题",
          "keywords": ["timeout", "TIMEOUT", "超时", ...],
          "auto_learned": ["..."],
          "usage_count": 5
        },
        ...
      },
      "global_ignore": ["debug", "trace", ...]
    }
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

SCRIPT_DIR = Path(__file__).parent
VAULT_FILE = SCRIPT_DIR / "keyword_vault.json"
CONFIG_DIR = SCRIPT_DIR / "config"

# ============================================================
# 简易 YAML 解析（无需 PyYAML 依赖）
# ============================================================

def _simple_yaml_parse(path: Path) -> dict:
    """简易YAML解析，用于读取角色配置文件"""
    result = {}
    current_list_key = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.strip().startswith("#"):
                continue
            m = re.match(r'^\s+- "(.+)"$', line)
            if m and current_list_key:
                result[current_list_key].append(m.group(1))
                continue
            m = re.match(r'^\s+- (.+)$', line)
            if m and current_list_key:
                result[current_list_key].append(m.group(1))
                continue
            m = re.match(r'^(\w+):\s+"?(.+?)"?\s*$', line)
            if m:
                current_list_key = None
                result[m.group(1)] = m.group(2)
                continue
            m = re.match(r'^(\w+):\s*\[\s*(.+?)\s*\]$', line)
            if m:
                current_list_key = None
                items = [i.strip().strip('"').strip("'") for i in m.group(2).split(",")]
                result[m.group(1)] = items
                continue
            m = re.match(r'^(\w+):\s*$', line)
            if m:
                result[m.group(1)] = []
                current_list_key = m.group(1)
                continue
    return result


def load_role_config(role_key: str) -> dict:
    """加载角色配置文件（独立实现，避免循环导入）"""
    config_file = CONFIG_DIR / f"{role_key}.yaml"
    if not config_file.exists():
        return {}
    return _simple_yaml_parse(config_file)

# ============================================================
# 预设问题方向
# ============================================================

DEFAULT_VAULT = {
    "directions": {
        "protocol_timeout": {
            "name": "协议超时问题",
            "description": "PD/USB 协议协商超时、消息响应超时",
            "from_role": "通用（基于异常模式库自动生成）",
            "keywords": [
                "timeout", "TIMEOUT", "超时", "Timeout",
                "no response", "No Response", "无响应",
                "retry", "Retry", "RETRY", "重试",
                "max retries", "达到最大重试",
                "wait timeout", "WAIT_TIMEOUT",
                "sender_response_timer", "SenderResponseTimer",
                "hard reset", "HARD_RESET",
                "message timeout", "MessageTimeout",
            ],
            "auto_learned": [],
            "usage_count": 0,
        },
        "power_mismatch": {
            "name": "功率/电压不匹配",
            "description": "PDO 能力不匹配、VBUS 电压异常、充电功率异常",
            "from_role": "通用（基于异常模式库自动生成）",
            "keywords": [
                "VBUS", "vbus", "voltage", "Voltage",
                "PDO", "pdo", "APDO", "apdo",
                "SRC_CAP", "SNK_CAP", "REQUEST", "ACCEPT",
                "PS_RDY", "REJECT",
                "mismatch", "不匹配", "偏差", "deviation",
                "over voltage", "under voltage",
                "OVP", "UVP", "OCP",
                "power", "Power", "current", "Current",
                "charger", "Charger",
            ],
            "auto_learned": [],
            "usage_count": 0,
        },
        "enum_failure": {
            "name": "USB 枚举失败",
            "description": "设备枚举失败、描述符读取异常、驱动绑定失败",
            "from_role": "通用（基于异常模式库自动生成）",
            "keywords": [
                "enumeration", "Enumeration", "ENUM",
                "Device Descriptor", "Config Descriptor",
                "Interface Descriptor", "String Descriptor",
                "Endpoint", "endpoint",
                "descriptor", "Descriptor",
                "idVendor", "idProduct", "bcdUSB",
                "bDeviceClass", "bConfigurationValue",
                "Reset", "reset", "Port Reset",
                "Address", "Set Address",
                "xhci", "ehci", "usb_core", "usb_host",
                "bind", "unbind", "probe",
            ],
            "auto_learned": [],
            "usage_count": 0,
        },
        "connection_stability": {
            "name": "连接稳定性问题",
            "description": "USB 连接断开/重连、CC 线状态异常、物理层问题",
            "from_role": "通用（基于异常模式库自动生成）",
            "keywords": [
                "disconnect", "Disconnect", "断开",
                "reconnect", "Reconnect", "重连",
                "CC", "cc", "CC1", "CC2",
                "attach", "detach", "Attach", "Detach",
                "debounce", "Debounce",
                "cable", "Cable", "线缆",
                "hub", "Hub", "Port",
                "suspend", "resume", "Suspend", "Resume",
                "remote wakeup", "Remote Wakeup",
                "link", "Link", "LTSSM",
            ],
            "auto_learned": [],
            "usage_count": 0,
        },
        "role_swap": {
            "name": "角色/方向切换问题",
            "description": "PR_SWAP/DR_SWAP/FR_SWAP 切换异常",
            "from_role": "通用（基于异常模式库自动生成）",
            "keywords": [
                "PR_SWAP", "DR_SWAP", "FR_SWAP",
                "swap", "Swap", "SWAP",
                "role", "Role",
                "source", "sink", "Source", "Sink",
                "DFP", "UFP", "DRP",
                "data role", "power role",
                "VCONN", "vconn",
            ],
            "auto_learned": [],
            "usage_count": 0,
        },
        "thermal_throttle": {
            "name": "温度/热管理问题",
            "description": "过热保护、温度降功率、thermal throttling",
            "from_role": "通用（基于异常模式库自动生成）",
            "keywords": [
                "thermal", "Thermal", "温度",
                "temperature", "Temperature",
                "throttle", "Throttle", "降频",
                "overheat", "Overheat", "过热",
                "cooling", "Cooling",
                "OTP", "otp",
                "TSD", "tsd",
                "fan", "Fan",
            ],
            "auto_learned": [],
            "usage_count": 0,
        },
        "firmware_boot": {
            "name": "固件/启动问题",
            "description": "固件崩溃、启动失败、看门狗复位",
            "from_role": "通用（基于异常模式库自动生成）",
            "keywords": [
                "panic", "Panic", "Kernel panic",
                "oops", "Oops", "BUG:",
                "Call Trace", "call trace",
                "watchdog", "Watchdog", "看门狗",
                "boot", "Boot", "启动",
                "crash", "Crash", "崩溃",
                "freeze", "Freeze", "死机",
                "hang", "Hang",
                "init", "Init",
                "firmware", "Firmware", "固件",
            ],
            "auto_learned": [],
            "usage_count": 0,
        },
    },
    "global_ignore": [
        "debug", "trace", "verbose",
        "printk", "pr_debug", "dev_dbg",
    ],
    "auto_learn_settings": {
        "enabled": True,
        "min_occurrences": 2,
        "max_auto_keywords_per_direction": 20,
    },
    "meta": {
        "version": "1.0",
        "created": "2026-06-03",
        "updated": "2026-06-03",
    },
}


# ============================================================
# Vault 管理
# ============================================================

def load_vault() -> dict:
    """加载关键词库"""
    if VAULT_FILE.exists():
        try:
            with open(VAULT_FILE, encoding="utf-8") as f:
                vault = json.load(f)
            # 合并默认方向（确保新方向被加入）
            for key, val in DEFAULT_VAULT["directions"].items():
                if key not in vault.get("directions", {}):
                    vault.setdefault("directions", {})[key] = val
            vault.setdefault("global_ignore", DEFAULT_VAULT["global_ignore"])
            vault.setdefault("auto_learn_settings", DEFAULT_VAULT["auto_learn_settings"])
            return vault
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_VAULT


def save_vault(vault: dict):
    """保存关键词库"""
    vault["meta"]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(VAULT_FILE, "w", encoding="utf-8") as f:
        json.dump(vault, f, ensure_ascii=False, indent=2)


def list_directions(vault: dict = None) -> list:
    """列出所有问题方向"""
    if vault is None:
        vault = load_vault()
    result = []
    for key, info in vault["directions"].items():
        result.append({
            "id": key,
            "name": info["name"],
            "description": info.get("description", ""),
            "keyword_count": len(info["keywords"]) + len(info.get("auto_learned", [])),
            "usage_count": info.get("usage_count", 0),
        })
    return result


def get_keywords(direction_id: str, vault: dict = None) -> dict:
    """获取指定方向的关键词"""
    if vault is None:
        vault = load_vault()

    direction = vault["directions"].get(direction_id)
    if not direction:
        return {"error": f"方向 '{direction_id}' 不存在", "available": list_directions(vault)}

    all_keywords = list(direction["keywords"]) + list(direction.get("auto_learned", []))
    return {
        "id": direction_id,
        "name": direction["name"],
        "description": direction.get("description", ""),
        "keywords": all_keywords,
        "preset_count": len(direction["keywords"]),
        "auto_learned_count": len(direction.get("auto_learned", [])),
        "usage_count": direction.get("usage_count", 0),
    }


def search_direction(query: str, vault: dict = None) -> list:
    """根据描述搜索匹配的问题方向"""
    if vault is None:
        vault = load_vault()

    results = []
    query_lower = query.lower()
    for key, info in vault["directions"].items():
        score = 0
        name_lower = info["name"].lower()
        desc_lower = info.get("description", "").lower()

        # 名称匹配
        if query_lower in name_lower:
            score += 10
        # 描述匹配
        if query_lower in desc_lower:
            score += 5
        # 关键词匹配
        for kw in info["keywords"]:
            if query_lower in kw.lower():
                score += 3
                break

        if score > 0:
            results.append({
                "id": key,
                "name": info["name"],
                "score": score,
            })

    results.sort(key=lambda x: -x["score"])
    return results


def auto_learn(text: str, direction_id: str = None, vault: dict = None) -> dict:
    """从文本中自动学习新关键词"""
    if vault is None:
        vault = load_vault()

    if not vault["auto_learn_settings"]["enabled"]:
        return {"learned": [], "message": "自动学习已禁用"}

    learned = []
    settings = vault["auto_learn_settings"]
    global_ignore = set(k.lower() for k in vault["global_ignore"])

    # 提取潜在关键词（大写单词、技术术语）
    patterns = [
        r'\b([A-Z_]{3,})\b',                          # 全大写缩写
        r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b',         # 驼峰命名
        r'\b([a-z]+_[a-z_]+)\b',                       # 下划线命名
        r'\b(0x[0-9A-Fa-f]{2,})\b',                   # 十六进制
    ]

    candidates = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            m_lower = m.lower()
            if m_lower not in global_ignore and len(m) >= 3:
                candidates.add(m)

    # 统计出现次数
    text_lower = text.lower()
    word_counts = {}
    for c in candidates:
        count = text_lower.count(c.lower())
        if count >= settings["min_occurrences"]:
            word_counts[c] = count

    # 如果指定了方向，添加到该方向
    if direction_id and direction_id in vault["directions"]:
        direction = vault["directions"][direction_id]
        existing = set(k.lower() for k in direction["keywords"])
        existing.update(k.lower() for k in direction.get("auto_learned", []))

        for word, count in sorted(word_counts.items(), key=lambda x: -x[1]):
            if word.lower() not in existing:
                if len(direction.get("auto_learned", [])) < settings["max_auto_keywords_per_direction"]:
                    direction.setdefault("auto_learned", []).append(word)
                    learned.append({"word": word, "count": count, "direction": direction_id})

        if learned:
            save_vault(vault)

    return {
        "learned": learned,
        "candidates": list(word_counts.keys()),
        "direction": direction_id,
    }


def add_keyword(direction_id: str, keyword: str, vault: dict = None) -> dict:
    """手动添加关键词到指定方向"""
    if vault is None:
        vault = load_vault()

    if direction_id not in vault["directions"]:
        return {"error": f"方向 '{direction_id}' 不存在"}

    direction = vault["directions"][direction_id]
    existing = set(k.lower() for k in direction["keywords"])
    existing.update(k.lower() for k in direction.get("auto_learned", []))

    if keyword.lower() in existing:
        return {"status": "exists", "keyword": keyword, "direction": direction_id}

    direction.setdefault("auto_learned", []).append(keyword)
    save_vault(vault)
    return {"status": "added", "keyword": keyword, "direction": direction_id}


def remove_keyword(direction_id: str, keyword: str, vault: dict = None) -> dict:
    """移除关键词"""
    if vault is None:
        vault = load_vault()

    if direction_id not in vault["directions"]:
        return {"error": f"方向 '{direction_id}' 不存在"}

    direction = vault["directions"][direction_id]
    for lst in [direction["keywords"], direction.get("auto_learned", [])]:
        if keyword in lst:
            lst.remove(keyword)
            save_vault(vault)
            return {"status": "removed", "keyword": keyword, "direction": direction_id}

    return {"status": "not_found", "keyword": keyword, "direction": direction_id}


def add_direction(direction_id: str, name: str, description: str = "",
                  keywords: list = None, vault: dict = None) -> dict:
    """创建新的问题方向"""
    if vault is None:
        vault = load_vault()

    if direction_id in vault["directions"]:
        return {"error": f"方向 '{direction_id}' 已存在"}

    vault["directions"][direction_id] = {
        "name": name,
        "description": description,
        "keywords": keywords or [],
        "auto_learned": [],
        "usage_count": 0,
        "from_role": "自定义",
    }
    save_vault(vault)
    return {"status": "created", "direction_id": direction_id, "name": name}


def record_usage(direction_id: str, vault: dict = None):
    """记录方向使用次数"""
    if vault is None:
        vault = load_vault()

    if direction_id in vault["directions"]:
        vault["directions"][direction_id]["usage_count"] = \
            vault["directions"][direction_id].get("usage_count", 0) + 1
        save_vault(vault)


def generate_directions_from_roles(vault: dict = None) -> dict:
    """从角色配置文件生成问题方向
    
    读取 config/*.yaml 中的角色画像，将每个角色的 focus_keywords 
    和 concern_modules 作为独立的问题方向导入关键词库。
    
    返回: {"imported": [...], "skipped": [...]}
    """
    if vault is None:
        vault = load_vault()

    config_dir = SCRIPT_DIR / "config"
    if not config_dir.exists():
        return {"error": "config 目录不存在", "imported": [], "skipped": []}

    imported = []
    skipped = []

    for yaml_file in sorted(config_dir.glob("*.yaml")):
        role_config = load_role_config(yaml_file.stem)
        role_name = role_config.get("display_name", yaml_file.stem)
        role_desc = role_config.get("description", "")
        keywords = role_config.get("focus_keywords", [])
        modules = role_config.get("concern_modules", [])

        if not keywords and not modules:
            continue

        # 方向ID: role_<role_key>
        direction_id = f"role_{yaml_file.stem}"

        if direction_id in vault["directions"]:
            # 已存在，合并关键词
            existing_kw = set(k.lower() for k in vault["directions"][direction_id]["keywords"])
            new_kw = [k for k in keywords if k.lower() not in existing_kw]
            new_mod = [m for m in modules if m.lower() not in existing_kw]
            if new_kw or new_mod:
                vault["directions"][direction_id]["keywords"].extend(new_kw + new_mod)
                vault["directions"][direction_id]["from_role"] = role_name
                imported.append({"direction": direction_id, "name": role_name, "new_keywords": len(new_kw) + len(new_mod)})
            else:
                skipped.append({"direction": direction_id, "name": role_name, "reason": "关键词已全部存在"})
        else:
            # 新建方向
            vault["directions"][direction_id] = {
                "name": f"{role_name}关注点",
                "description": f"来自角色画像「{role_name}」: {role_desc}",
                "keywords": keywords + modules,
                "auto_learned": [],
                "usage_count": 0,
                "from_role": role_name,
            }
            imported.append({"direction": direction_id, "name": role_name, "new_keywords": len(keywords) + len(modules)})

    if imported:
        save_vault(vault)

    return {"imported": imported, "skipped": skipped}


def export_for_viewer(vault: dict = None) -> dict:
    """导出为 log_viewer 可用的格式"""
    if vault is None:
        vault = load_vault()

    result = {
        "directions": {},
        "all_keywords": [],
    }

    for key, info in vault["directions"].items():
        all_kw = list(info["keywords"]) + list(info.get("auto_learned", []))
        result["directions"][key] = {
            "name": info["name"],
            "description": info.get("description", ""),
            "keywords": all_kw,
            "from_role": info.get("from_role", ""),
        }
        result["all_keywords"].extend(all_kw)

    # 去重
    result["all_keywords"] = list(set(result["all_keywords"]))
    result["all_keywords"].sort()

    return result


# ============================================================
# CLI
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="关键词收纳系统 (Keyword Vault)")
    sub = parser.add_subparsers(dest="command", help="命令")

    # list
    sub.add_parser("list", help="列出所有问题方向")

    # show
    show_p = sub.add_parser("show", help="显示指定方向的关键词")
    show_p.add_argument("direction", help="方向ID")

    # search
    search_p = sub.add_parser("search", help="搜索匹配的问题方向")
    search_p.add_argument("query", help="搜索关键词")

    # learn
    learn_p = sub.add_parser("learn", help="从文本自动学习关键词")
    learn_p.add_argument("text", help="文本内容（或文件路径，用 file: 前缀）")
    learn_p.add_argument("--direction", "-d", help="目标方向ID")

    # add
    add_p = sub.add_parser("add", help="手动添加关键词")
    add_p.add_argument("direction", help="方向ID")
    add_p.add_argument("keyword", help="关键词")

    # remove
    rm_p = sub.add_parser("remove", help="移除关键词")
    rm_p.add_argument("direction", help="方向ID")
    rm_p.add_argument("keyword", help="关键词")

    # new-direction
    new_p = sub.add_parser("new-direction", help="创建新方向")
    new_p.add_argument("id", help="方向ID")
    new_p.add_argument("name", help="方向名称")
    new_p.add_argument("--description", "-d", default="", help="描述")
    new_p.add_argument("--keywords", "-k", nargs="*", default=[], help="初始关键词")

    # export
    export_p = sub.add_parser("export", help="导出为 viewer 格式")
    export_p.add_argument("--output", "-o", help="输出文件路径")
    export_p.add_argument("--json", action="store_true", help="输出纯 JSON 到 stdout（供程序调用）")

    # init
    sub.add_parser("init", help="初始化关键词库")

    # generate-from-roles
    sub.add_parser("generate-from-roles", help="从角色配置文件生成问题方向")

    args = parser.parse_args()

    if args.command == "list":
        directions = list_directions()
        print(f"\n📋 问题方向 ({len(directions)} 个):\n")
        for d in directions:
            print(f"  [{d['id']}] {d['name']}")
            print(f"       描述: {d['description']}")
            print(f"       关键词: {d['keyword_count']} 个 | 使用: {d['usage_count']} 次")
            print()

    elif args.command == "show":
        result = get_keywords(args.direction)
        if "error" in result:
            print(f"❌ {result['error']}")
            print("\n可用方向:")
            for d in result["available"]:
                print(f"  [{d['id']}] {d['name']}")
            sys.exit(1)

        print(f"\n📌 [{result['id']}] {result['name']}")
        print(f"   描述: {result['description']}")
        print(f"   关键词: {result['preset_count']} 预设 + {result['auto_learned_count']} 自动学习")
        print(f"   使用次数: {result['usage_count']}")
        print(f"\n   关键词列表:")
        for kw in result["keywords"]:
            print(f"     • {kw}")

    elif args.command == "search":
        results = search_direction(args.query)
        if results:
            print(f"\n🔍 搜索 '{args.query}' 匹配 {len(results)} 个方向:\n")
            for r in results:
                print(f"  [{r['id']}] {r['name']} (匹配度: {r['score']})")
        else:
            print(f"❌ 未找到匹配 '{args.query}' 的方向")

    elif args.command == "learn":
        text = args.text
        if text.startswith("file:"):
            filepath = text[5:]
            text = Path(filepath).read_text(encoding="utf-8", errors="replace")

        result = auto_learn(text, direction_id=args.direction)
        if result["learned"]:
            print(f"\n✅ 自动学习了 {len(result['learned'])} 个关键词:")
            for item in result["learned"]:
                print(f"  • {item['word']} (出现 {item['count']} 次) → [{item['direction']}]")
        else:
            print(f"📭 未发现新关键词 (候选: {len(result['candidates'])} 个)")

    elif args.command == "add":
        result = add_keyword(args.direction, args.keyword)
        if "error" in result:
            print(f"❌ {result['error']}")
        elif result["status"] == "exists":
            print(f"⚠️ 关键词 '{args.keyword}' 已存在于 [{args.direction}]")
        else:
            print(f"✅ 已添加 '{args.keyword}' → [{args.direction}]")

    elif args.command == "remove":
        result = remove_keyword(args.direction, args.keyword)
        if "error" in result:
            print(f"❌ {result['error']}")
        elif result["status"] == "removed":
            print(f"✅ 已移除 '{args.keyword}' 从 [{args.direction}]")
        else:
            print(f"⚠️ 未找到 '{args.keyword}' 在 [{args.direction}]")

    elif args.command == "new-direction":
        result = add_direction(args.id, args.name, args.description, args.keywords)
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            print(f"✅ 已创建方向 [{args.id}] {args.name}")

    elif args.command == "export":
        result = export_for_viewer()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✅ 已导出到 {args.output}")
        elif getattr(args, 'json', False):
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "init":
        save_vault(DEFAULT_VAULT)
        print(f"✅ 关键词库已初始化: {VAULT_FILE}")
        print(f"   💡 运行 'generate-from-roles' 从角色配置导入方向")

    elif args.command == "generate-from-roles":
        result = generate_directions_from_roles()
        if "error" in result:
            print(f"❌ {result['error']}")
        else:
            print(f"✅ 从角色配置生成了 {len(result['imported'])} 个方向:")
            for item in result["imported"]:
                print(f"  [{item['direction']}] {item['name']} (+{item['new_keywords']} 关键词)")
            if result["skipped"]:
                print(f"\n⏭️ 跳过 {len(result['skipped'])} 个（已存在）:")
                for item in result["skipped"]:
                    print(f"  [{item['direction']}] {item['name']}: {item['reason']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
