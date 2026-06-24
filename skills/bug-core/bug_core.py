#!/usr/bin/env python3
"""
Bug Core - Bugzilla Bug查询核心模块
支持多模式：web_fetch / REST API / 手动输入
支持多实例：kernel / mozilla / unisoc 等

部署流程：
1. pip install requests beautifulsoup4 lxml
2. 配置 config/bugzilla_instances.json
3. 通过 Claw Skill 或独立运行
"""

import json
import os
import re
import sys
from typing import Optional

# 配置路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config", "bugzilla_instances.json")
SAMPLE_BUGS_PATH = os.path.join(SCRIPT_DIR, "data", "sample_bugs.json")

# 非法文件名字符
INVALID_CHARS = r'[<>:"/\\|?*\n\r\t]'

# 离线模式标记：通过环境变量 OFFLINE_MODE=1 或 --offline 参数启用
OFFLINE_MODE = os.environ.get("OFFLINE_MODE", "0") == "1"


def load_config() -> dict:
    """加载Bugzilla实例配置"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_instance_config(instance_name: str = None) -> dict:
    """获取指定实例配置"""
    config = load_config()
    if instance_name is None:
        instance_name = config.get("default_instance", "kernel")
    instances = config.get("instances", {})
    if instance_name not in instances:
        raise ValueError(f"未知实例: {instance_name}, 可用: {list(instances.keys())}")
    return instance_name, instances[instance_name]


# ============================================================
# 模式D：离线模拟数据查询（无需联网）
# ============================================================

def _load_sample_bugs() -> list:
    """加载离线模拟Bug数据"""
    try:
        with open(SAMPLE_BUGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def fetch_bug_offline(bug_id: str) -> dict:
    """通过离线模拟数据查询Bug（无需网络）"""
    bugs = _load_sample_bugs()
    match = None
    for b in bugs:
        if b.get("bug_id", "").upper() == bug_id.upper():
            match = b
            break
    if not match:
        return {"error": f"离线模式下未找到 Bug {bug_id}"}

    return {
        "source": "offline:sample",
        "bug_id": match["bug_id"],
        "summary": match.get("title", ""),
        "status": match.get("status", ""),
        "resolution": "",
        "priority": match.get("priority", ""),
        "severity": match.get("severity", ""),
        "product": match.get("product", ""),
        "component": match.get("component", ""),
        "assignee": match.get("assignee", ""),
        "reporter": match.get("reporter", ""),
        "module": match.get("module", ""),
        "description": match.get("description", ""),
        "attachment_hint": match.get("attachment_hint", ""),
        "tags": match.get("tags", []),
        "update_time": match.get("update_time", ""),
        "url": f"# (离线模式)",
    }


# ============================================================
# 模式A：REST API 查询（直接HTTP请求）
# ============================================================

def fetch_bug_rest(bug_id: str, instance: str = None) -> dict:
    """通过REST API获取Bug信息"""
    if OFFLINE_MODE:
        return fetch_bug_offline(bug_id)

    # Handle "local" instance (alias for offline)
    if instance == "local":
        return fetch_bug_offline(bug_id)

    import requests

    inst_name, inst_config = get_instance_config(instance)
    rest_url = inst_config["rest_url"]
    api_key = inst_config.get("api_key", "")

    params = {"include_fields": "_all"}
    if api_key:
        params["api_key"] = api_key

    # 获取Bug信息
    bug_resp = requests.get(
        f"{rest_url}/bug/{bug_id}",
        params=params,
        headers={"Accept": "application/json"},
        timeout=15
    )
    bug_resp.raise_for_status()
    bug_data = bug_resp.json()

    bugs = bug_data.get("bugs", [])
    if not bugs:
        return {"error": f"Bug {bug_id} 不存在或无权限访问"}

    bug = bugs[0]

    # 获取评论
    try:
        comment_resp = requests.get(
            f"{rest_url}/bug/{bug_id}/comment",
            params=params,
            headers={"Accept": "application/json"},
            timeout=15
        )
        comment_resp.raise_for_status()
        comment_data = comment_resp.json()
        comments = []
        for bug_comments in comment_data.get("bugs", {}).values():
            comments = bug_comments.get("comments", [])
            break
    except Exception:
        comments = []

    # 提取附件路径（unisoc Bugzilla特有）
    ftp_paths = []
    ftp_urls = []
    unc_paths = []
    if comments:
        # 扫描所有评论（通常第一条评论包含FTP/UNC路径）
        all_text = " ".join(c.get("text", "") for c in comments)
        # 提取 ftp:// URL
        ftp_urls = list(set(re.findall(r'ftp://[^\s)\]]+', all_text)))
        # 提取 UNC 路径 (\\server\share\...)
        unc_paths = list(set(re.findall(r'\\\\[a-zA-Z0-9_.-]+\\(?:[^\s)\]]+\\)*[^\s)\]]+', all_text)))
        # 提取 下载附件 路径
        attachment_match = re.search(r'下载附件:\s*([^\n]+)', all_text)
        if attachment_match:
            ftp_paths.append(attachment_match.group(1).strip())
        # 合并所有FTP路径
        ftp_path = ftp_urls[0] if ftp_urls else (unc_paths[0] if unc_paths else "")

    path_url = ""
    if comments:
        all_text = " ".join(c.get("text", "") for c in comments)
        url_match = re.search(r'或使用快捷链接下载.*?:\s*(https?://[^\s]+)', all_text)
        if url_match:
            path_url = url_match.group(1).strip()

    # 构建结果
    result = {
        "source": f"rest_api:{inst_name}",
        "bug_id": str(bug.get("id", bug_id)),
        "alias": bug.get("alias", []),
        "summary": bug.get("summary", ""),
        "status": bug.get("status", ""),
        "resolution": bug.get("resolution", ""),
        "priority": bug.get("priority", ""),
        "severity": bug.get("severity", ""),
        "product": bug.get("product", ""),
        "component": bug.get("component", ""),
        "assignee": "",
        "reporter": "",
        "creation_time": bug.get("creation_time", ""),
        "last_change_time": bug.get("last_change_time", ""),
        "url": f"{inst_config['base_url']}/show_bug.cgi?id={bug_id}",
        "comments_count": len(comments),
        "first_comment": comments[0].get("text", "")[:500] if comments else "",
        "ftp_path": ftp_path,
        "ftp_urls": ftp_urls,
        "unc_paths": unc_paths,
        "path_url": path_url,
    }

    # 提取 assignee / reporter
    assigned = bug.get("assigned_to", "")
    if isinstance(assigned, dict):
        assigned = assigned.get("name", str(assigned))
    result["assignee"] = str(assigned)

    reported = bug.get("reporter", "")
    if isinstance(reported, dict):
        reported = reported.get("name", str(reported))
    result["reporter"] = str(reported)

    return result


# ============================================================
# 模式B：web_fetch 查询（通过Claw内置web_fetch工具）
# ============================================================

def fetch_bug_webfetch(bug_id: str, instance: str = None) -> dict:
    """
    生成web_fetch URL，供Claw agent调用web_fetch工具获取页面内容
    返回URL字典，agent按顺序调用
    """
    if OFFLINE_MODE:
        return fetch_bug_offline(bug_id)
    if instance == "local":
        return fetch_bug_offline(bug_id)

    inst_name, inst_config = get_instance_config(instance)
    base_url = inst_config["base_url"]

    urls = {
        "bug_page": f"{base_url}/show_bug.cgi?id={bug_id}",
        "bug_xml": f"{base_url}/show_bug.cgi?id={bug_id}&ctype=xml",
        "bug_rest": f"{inst_config['rest_url']}/bug/{bug_id}",
        "comment_rest": f"{inst_config['rest_url']}/bug/{bug_id}/comment",
    }
    return urls


# ============================================================
# 模式C：手动输入解析（用户粘贴内容）
# ============================================================

def parse_bug_from_text(text: str) -> dict:
    """从用户粘贴的Bug页面内容中提取结构化信息"""
    result = {
        "source": "manual_input",
        "bug_id": None,
        "summary": "",
        "status": "",
        "priority": "",
        "severity": "",
        "product": "",
        "component": "",
        "ftp_path": "",
        "path_url": "",
    }

    # 提取Bug ID（SPCSS开头或纯数字或 BUG-xxxx）
    m = re.search(r'(SPCSS\d+)', text)
    if m:
        result["bug_id"] = m.group(1)
    else:
        m = re.search(r'(BUG-\d+)', text)
        if m:
            result["bug_id"] = m.group(1)
        else:
            m = re.search(r'[Bb]ug[\s#:]+(\d{4,})', text)
            if m:
                result["bug_id"] = m.group(1)

    # 提取标题
    m = re.search(r'[Ss]ummary[\s:]+(.+?)(?:\n|$)', text)
    if m:
        result["summary"] = m.group(1).strip()

    # 提取状态
    m = re.search(r'[Ss]tatus[\s:]+(\w+)', text)
    if m:
        result["status"] = m.group(1)

    # 提取优先级
    m = re.search(r'[Pp]riority[\s:]+(\S+)', text)
    if m:
        result["priority"] = m.group(1)

    # 提取FTP路径（unisoc特有格式）
    m = re.search(r'下载附件:\s*([^\n]+)', text)
    if m:
        result["ftp_path"] = "/" + m.group(1).strip()

    # 提取快捷下载链接
    m = re.search(r'或使用快捷链接下载.*?:\s*(https?://[^\s]+)', text)
    if m:
        result["path_url"] = m.group(1).strip()

    # 提取Product/Component
    m = re.search(r'[Pp]roduct[\s:]+(.+?)(?:\n|$)', text)
    if m:
        result["product"] = m.group(1).strip()
    m = re.search(r'[Cc]omponent[\s:]+(.+?)(?:\n|$)', text)
    if m:
        result["component"] = m.group(1).strip()

    return result


def search_bugs(keyword: str = "", severity: str = "", limit: int = 20) -> list:
    """离线搜索Bug（支持关键词和严重度过滤）"""
    bugs = _load_sample_bugs()
    results = []
    for b in bugs:
        if severity and b.get("severity", "").upper() != severity.upper():
            continue
        if keyword:
            search_text = f"{b.get('title', '')} {b.get('description', '')} {b.get('tags', [])} {b.get('bug_id', '')}"
            if keyword.lower() not in search_text.lower():
                continue
        results.append(b)
    return results[:limit]


# ============================================================
# 工具函数
# ============================================================

def clean_folder_name(name: str, max_len: int = 99) -> str:
    """清除文件夹名中的非法字符，复刻原工具逻辑"""
    cleaned = re.sub(INVALID_CHARS, "_", name)
    if len(cleaned) > max_len:
        if max_len > 50:
            cleaned = cleaned[:50] + cleaned[-(max_len - 50):]
        else:
            cleaned = cleaned[:max_len]
    return cleaned


def format_bug_summary(bug: dict) -> str:
    """格式化Bug摘要输出"""
    lines = []
    lines.append(f"[Bug Summary]")
    lines.append("=" * 40)
    lines.append(f"ID: {bug.get('bug_id', 'N/A')}")

    alias = bug.get("alias", [])
    if isinstance(alias, list) and alias:
        lines.append(f"Alias: {alias[0]}")
    elif alias:
        lines.append(f"Alias: {alias}")

    lines.append(f"Title: {bug.get('summary', 'N/A')}")
    lines.append(f"Status: {bug.get('status', 'N/A')}")
    if bug.get("resolution"):
        lines.append(f"  Resolution: {bug['resolution']}")

    priority = bug.get("priority", "")
    severity = bug.get("severity", "")
    if priority or severity:
        lines.append(f"Priority: {priority} | Severity: {severity}")

    lines.append(f"Product: {bug.get('product', 'N/A')} / {bug.get('component', 'N/A')}")

    assignee = bug.get("assignee", "")
    if assignee:
        lines.append(f"Assignee: {assignee}")

    reporter = bug.get("reporter", "")
    if reporter:
        lines.append(f"Reporter: {reporter}")

    lines.append(f"URL: {bug.get('url', 'N/A')}")
    lines.append(f"Source: {bug.get('source', 'N/A')}")

    # FTP/附件路径 (unisoc特有)
    if bug.get("ftp_path"):
        lines.append(f"\n[FTP Path]: {bug['ftp_path']}")
    ftp_urls = bug.get("ftp_urls", [])
    if ftp_urls:
        lines.append("[FTP URLs]:")
        for u in ftp_urls:
            lines.append(f"  {u}")
    unc_paths = bug.get("unc_paths", [])
    if unc_paths:
        lines.append("[UNC Paths]:")
        for u in unc_paths:
            lines.append(f"  {u}")
    if bug.get("path_url"):
        lines.append(f"[Quick Link]: {bug['path_url']}")

    # 离线模式附加信息
    module = bug.get("module", "")
    if module:
        lines.append(f"[Module]: {module}")
    desc = bug.get("description", "")
    if desc:
        lines.append(f"[Description]: {desc}")
    tags = bug.get("tags", [])
    if tags:
        lines.append(f"[Tags]: {', '.join(tags)}")
    hint = bug.get("attachment_hint", "")
    if hint:
        lines.append(f"[Attachment Hint]: {hint}")
    update = bug.get("update_time", "")
    if update:
        lines.append(f"[Update Time]: {update}")

    creation = bug.get("creation_time", "")
    if creation:
        lines.append(f"[Created]: {creation}")
    last_change = bug.get("last_change_time", "")
    if last_change:
        lines.append(f"[Last Changed]: {last_change}")

    comments_count = bug.get("comments_count", 0)
    if comments_count:
        lines.append(f"\n[Comments]: {comments_count}")
        first = bug.get("first_comment", "")
        if first:
            preview = first[:200] + "..." if len(first) > 200 else first
            lines.append(f"  First: {preview}")

    return "\n".join(lines)


# ============================================================
# 主入口（独立脚本运行）
# ============================================================

if __name__ == "__main__":
    import argparse
    import io

    # Fix Windows console UTF-8 output
    if sys.stdout.encoding is None or "936" in sys.stdout.encoding or "ascii" in sys.stdout.encoding.lower():
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    parser = argparse.ArgumentParser(description="Bug Core - Bug查询工具")
    parser.add_argument("bug_id", nargs="?", help="Bug ID (数字或 BUG-xxxx)")
    parser.add_argument("instance", nargs="?", default="kernel",
                        help="Bugzilla实例: kernel(默认) / mozilla / unisoc / local")
    parser.add_argument("--offline", action="store_true", help="离线模式（使用模拟数据）")
    parser.add_argument("--list", action="store_true", help="列出所有本地模拟Bug")
    parser.add_argument("--webfetch", action="store_true", help="仅输出web_fetch URL（JSON格式）")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出Bug信息")
    args = parser.parse_args()

    if args.list:
        bugs = _load_sample_bugs()
        print(f"[Local Bug List] ({len(bugs)} entries):")
        print("=" * 50)
        for b in bugs:
            print(f"  {b['bug_id']}  [{b['severity']}] {b['title']}")
            print(f"    Assignee: {b['assignee']} | Status: {b['status']} | Update: {b['update_time']}")
        sys.exit(0)

    if args.offline:
        os.environ["OFFLINE_MODE"] = "1"

    if not args.bug_id:
        parser.print_help()
        sys.exit(1)

    bug_id = args.bug_id

    if args.webfetch:
        urls = fetch_bug_webfetch(bug_id, args.instance)
        print(json.dumps(urls, indent=2))
        sys.exit(0)

    print(f"[Query] Bug {bug_id} (instance: {args.instance or 'default'})...\n")

    try:
        result = fetch_bug_rest(bug_id, args.instance)
        if "error" in result:
            print(f"[ERROR] {result['error']}")
        else:
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(format_bug_summary(result))
    except Exception as e:
        msg = str(e)
        if "401" in msg:
            print(f"[ERROR] API Key required for instance ({args.instance})")
            print(f"   Configure api_key in config/bugzilla_instances.json")
        elif "403" in msg:
            print(f"[ERROR] Access denied to instance ({args.instance})")
        else:
            print(f"[ERROR] Query failed: {e}")
