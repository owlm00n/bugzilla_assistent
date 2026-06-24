#!/usr/bin/env python3
"""
Bug Workspace - 工作区创建 & 编排模块
复刻原 UI 工具 fetch_buginfo_by_API_UI.py 的核心流程：
1. 根据Bug信息生成文件夹名
2. 创建本地文件夹 + Bug Z 模板复制
3. 调用 bug-logs 下载附件（UNC / rayfile）
4. 创建 .url 快捷方式
5. 路径历史管理 + 快速打开
"""

import json
import os
import re
import shutil
import sys

# 配置路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config", "bugzilla_instances.json")
PATHS_CONFIG = os.path.join(SCRIPT_DIR, "config", "paths.json")

# 非法文件名字符
INVALID_CHARS = r'[<>:"/\\|?*\n\r\t]'


def load_config() -> dict:
    """加载Bugzilla实例配置"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 跨 Skill 导入：从 bug-core 获取工具函数
# ============================================================

def _import_bug_core_format():
    """三级降级加载 bug-core 的 format_bug_summary"""
    try:
        from bug_core import format_bug_summary, clean_folder_name
        return format_bug_summary, clean_folder_name
    except ImportError:
        import sys as _sys
        _skills = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _core = os.path.join(_skills, "bug-core")
        if _core not in _sys.path:
            _sys.path.insert(0, _core)
        from bug_core import format_bug_summary as _fmt, clean_folder_name as _cln
        return _fmt, _cln


def _import_bug_logs_download():
    """三级降级加载 bug-logs 的下载函数"""
    try:
        from bug_logs import download_bug_attachments
        return download_bug_attachments
    except ImportError:
        import sys as _sys
        _skills = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _logs = os.path.join(_skills, "bug-logs")
        if _logs not in _sys.path:
            _sys.path.insert(0, _logs)
        from bug_logs import download_bug_attachments as _dba
        return _dba


# ============================================================
# 工作区创建 & 附件下载
# ============================================================

def generate_folder_name(bug: dict) -> str:
    """
    根据Bug信息生成文件夹名。
    格式: [BugID][Summary前30字符] (复刻原工具逻辑)
    """
    _, clean_folder_name = _import_bug_core_format()

    bug_id = str(bug.get("bug_id", "unknown"))
    summary = bug.get("summary", "")
    # 取前30字符作为摘要片段
    fragment = summary[:30].strip()
    folder_name = f"[{bug_id}][{fragment}]"
    return clean_folder_name(folder_name)


def get_default_workspace_path() -> str:
    """获取默认工作区路径（与reference中paths配置一致）"""
    config = load_config()
    unisoc_cfg = config.get("instances", {}).get("unisoc", {})
    default_path = unisoc_cfg.get("default_workspace", r"E:\08_Bug")
    return os.path.expandvars(default_path)


def get_rayfile_command(ftp_path: str, local_dir: str) -> dict:
    """
    生成 rayfile-c_cmd.exe 下载命令（匹配原工具精确参数）。

    原工具命令:
      rayfile-c_cmd.exe -a unitrans.unisoc.com -p 2443 -ssl
        -u ctd01 -w ctd01@abAB -o download
        -d {local_dir} -s {ftp_path}
        -space_id 2 -gr 31240 -file-update append

    Returns:
        {"command": str, "args": [str, ...]}
    """
    config = load_config()
    unisoc_cfg = config.get("instances", {}).get("unisoc", {})

    host = unisoc_cfg.get("ftp_host", "unitrans.unisoc.com")
    port = str(unisoc_cfg.get("ftp_port", "2443"))
    user = unisoc_cfg.get("ftp_user", "ctd01")
    password = unisoc_cfg.get("ftp_password", "ctd01@abAB")
    use_ssl = unisoc_cfg.get("ftp_use_ssl", True)
    exe_path = unisoc_cfg.get("rayfile_exe", r"E:\08_Bug\sync-cmd-windows\rayfile-c_cmd.exe")

    args = [exe_path, "-a", host, "-p", port]
    if use_ssl:
        args.append("-ssl")
    args.extend(["-u", user, "-w", password,
                 "-o", "download",
                 "-d", local_dir,
                 "-s", ftp_path,
                 "-space_id", "2",
                 "-gr", "31240",
                 "-file-update", "append"])

    return {
        "command": " ".join(args),
        "args": args,
    }


def create_bug_shortcut(bug: dict, folder_path: str) -> str:
    """创建 Bug 页面 .url 快捷方式（匹配原工具格式）。

    使用 [InternetShortcut] 格式，包含 URL/IconFile/IconIndex。
    路径 >200 字符时自动简化为 "Bug.url"。
    """
    url = bug.get("url", "")
    bug_id = str(bug.get("bug_id", "unknown"))

    if not url:
        return ""

    shortcut_name = f"Bug_{bug_id}.url"
    shortcut_path = os.path.join(folder_path, shortcut_name)

    # 路径过长时简化（原工具 >200 字符阈值）
    if len(shortcut_path) > 200:
        shortcut_path = os.path.join(folder_path, "Bug.url")

    os.makedirs(folder_path, exist_ok=True)

    content = f"""[InternetShortcut]
URL={url}
IconFile={url}
IconIndex=0
"""
    with open(shortcut_path, "w", encoding="ascii") as f:
        f.write(content)

    return shortcut_path


def create_url_shortcut(url: str, folder_path: str, name: str = None) -> str:
    """创建任意 URL 的 .url 快捷方式。

    与 create_bug_shortcut 不同，此函数允许自定义名称。
    """
    if name is None:
        name = "Shortcut.url"
    elif not name.endswith(".url"):
        name = f"{name}.url"

    shortcut_path = os.path.join(folder_path, name)

    if len(shortcut_path) > 200:
        shortcut_path = os.path.join(folder_path, "Bug.url")

    os.makedirs(folder_path, exist_ok=True)

    content = f"""[InternetShortcut]
URL={url}
IconFile={url}
IconIndex=0
"""
    with open(shortcut_path, "w", encoding="ascii") as f:
        f.write(content)

    return shortcut_path


def generate_workspace(bug: dict, base_path: str = None) -> dict:
    """
    创建工作区文件夹（不含下载）:
    1. 根据Bug信息生成文件夹名
    2. 创建本地文件夹
    3. 生成 rayfile 下载命令（dict 格式）
    4. 创建 .url 快捷方式
    5. 生成 bug_summary.txt

    返回值:
        {
            "folder_name": str,
            "folder_path": str,
            "created": bool,
            "rayfile_commands": [dict, ...],  # 每个含 command/args
            "shortcut_file": str,
            "summary_file": str,
        }
    """
    format_bug_summary, _ = _import_bug_core_format()

    if base_path is None:
        base_path = get_default_workspace_path()

    folder_name = generate_folder_name(bug)
    folder_path = os.path.join(base_path, folder_name)

    # 创建文件夹
    os.makedirs(folder_path, exist_ok=True)
    created = os.path.isdir(folder_path)

    # 生成 rayfile 下载命令（dict 格式）
    ftp_urls = bug.get("ftp_urls", [])
    rayfile_cmds = []
    for ftp_url in ftp_urls:
        cmd = get_rayfile_command(ftp_url, folder_path)
        rayfile_cmds.append(cmd)

    # 如果没有FTP URL但有UNC路径，生成替代命令
    unc_paths = bug.get("unc_paths", [])
    for unc in unc_paths:
        ftp_equiv = unc.replace("\\\\", "ftp://").replace("\\", "/")
        cmd = get_rayfile_command(ftp_equiv, folder_path)
        rayfile_cmds.append(cmd)

    # 生成 .url 快捷方式
    shortcut = create_bug_shortcut(bug, folder_path)

    # 生成 Bug 摘要文件
    summary_file = os.path.join(folder_path, "bug_summary.txt")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(format_bug_summary(bug))

    return {
        "folder_name": folder_name,
        "folder_path": folder_path,
        "created": created,
        "rayfile_commands": rayfile_cmds,
        "shortcut_file": shortcut,
        "summary_file": summary_file,
    }


# ============================================================
# Bug Z 模板 + 路径历史 + 快速打开
# ============================================================

def copy_bug_z_template(base_path: str, dest_folder: str) -> bool:
    """复制 Bug Z 模板文件夹到目标工作区。

    若 {base_path}/Bug Z 存在，使用 shutil.copytree 复制到 dest_folder，
    冲突时合并（dirs_exist_ok=True）。
    移植自原 UI 工具 line 421-432。

    Returns:
        True = 已复制, False = 模板不存在或 dest_folder 本身就是 Bug Z
    """
    bug_z = os.path.join(base_path, "Bug Z")

    if not os.path.exists(bug_z):
        return False

    # 防止自复制（目标路径就是 Bug Z 本身）
    if os.path.normpath(dest_folder) == os.path.normpath(bug_z):
        return False

    try:
        shutil.copytree(bug_z, dest_folder, dirs_exist_ok=True)
        return True
    except Exception:
        return False


def load_workspace_paths(config_dir: str = None) -> list:
    """从 config/paths.json 加载工作区路径历史。

    若文件不存在则返回预设的 14 个默认路径（移植自原工具 paths.json）。
    """
    if config_dir is None:
        config_dir = SCRIPT_DIR

    paths_file = PATHS_CONFIG if config_dir == SCRIPT_DIR else os.path.join(config_dir, "paths.json")

    if os.path.exists(paths_file):
        try:
            with open(paths_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # 默认路径（移植自原工具 paths 列表）
    return [
        r"E:\08_Bug",
        r"E:\08_Bug\CQ",
        r"E:\08_Bug\Task",
        r"E:\08_Bug\Test",
        r"F:\PD认证",
        r"F:\PD认证\XIAOMI",
        r"F:\PD认证\vivo_T612",
        r"F:\PD认证\VIVO",
        r"F:\PD认证\REALME",
        r"F:\PD认证\transsion",
        r"F:\PD认证\SAGEREAL",
        r"F:\PD认证\ZTE\UMS9620S]P820F03",
        r"F:\PD认证\ZTE\UMS9620][P720F12]",
        r"F:\PD认证\YINGKA",
        r"F:\PD认证\SPROCOMM",
    ]


def save_workspace_paths(paths: list, config_dir: str = None) -> bool:
    """保存工作区路径历史到 config/paths.json。
    去重并保持顺序。
    """
    if config_dir is None:
        config_dir = SCRIPT_DIR

    paths_file = PATHS_CONFIG if config_dir == SCRIPT_DIR else os.path.join(config_dir, "paths.json")
    os.makedirs(os.path.dirname(paths_file), exist_ok=True)

    # 去重保持顺序
    seen = set()
    unique = []
    for p in paths:
        if p and p not in seen:
            seen.add(p)
            unique.append(p)

    try:
        with open(paths_file, "w", encoding="utf-8") as f:
            json.dump(unique, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def open_workspace_path(path: str) -> bool:
    """在文件资源管理器中打开工作区路径（os.startfile）。

    移植自原 UI 工具 open_base_path() line 511-520。
    """
    if not path or not os.path.exists(path):
        return False
    try:
        os.startfile(path)
        return True
    except Exception:
        return False


# ============================================================
# 编排函数 — 完整工作区生成（含下载）
# ============================================================

def generate_workspace_with_download(
    bug: dict,
    base_path: str = None,
    download: bool = True,
    refresh: bool = False,
    normalize_action: str = "copy_new",
    copy_bug_z: bool = True,
) -> dict:
    """完整工作区生成 + 附件下载（编排函数）。

    工作流（匹配原 UI 工具流程）：
    1. 生成文件夹名 + 创建工作区目录
    2. 复制 Bug Z 模板（若存在）
    3. 调用 bug-logs 下载附件 (UNC 或 rayfile)
    4. 创建 .url 快捷方式
    5. 生成 bug_summary.txt
    6. 返回完整结果

    Args:
        bug: Bug 信息 dict（含 bug_id, summary, url, ftp_urls, unc_paths）
        base_path: 工作区根目录（默认来自配置）
        download: 是否执行下载
        refresh: 清空后重新下载
        normalize_action: "off" | "move" | "copy_new"
        copy_bug_z: 是否复制 Bug Z 模板

    Returns:
        {
            "success": bool,
            "folder": dict,       # generate_workspace 返回
            "download": dict,     # download_bug_attachments 返回
            "bug_z_copied": bool,
            "errors": [str, ...],
        }
    """
    result = {
        "success": False,
        "folder": {},
        "download": {},
        "bug_z_copied": False,
        "errors": [],
    }

    try:
        if base_path is None:
            base_path = get_default_workspace_path()

        # 1. 创建工作区文件夹
        folder_info = generate_workspace(bug, base_path)
        result["folder"] = folder_info

        if not folder_info.get("created"):
            result["errors"].append("Failed to create workspace folder")
            return result

        folder_path = folder_info["folder_path"]

        # 2. Bug Z 模板复制
        if copy_bug_z:
            result["bug_z_copied"] = copy_bug_z_template(base_path, folder_path)

        # 3. 调用 bug-logs 下载附件
        if download:
            bug_id = str(bug.get("bug_id", ""))
            if bug_id:
                download_bug_attachments_fn = _import_bug_logs_download()
                dl_result = download_bug_attachments_fn(
                    bug_id=bug_id,
                    dest_dir=folder_path,
                    instance=bug.get("instance"),
                    refresh=refresh,
                    normalize_action=normalize_action,
                )
                result["download"] = dl_result
                if not dl_result.get("success"):
                    result["errors"].extend(dl_result.get("errors", []))
            else:
                result["errors"].append("No bug_id for download")

        result["success"] = len(result["errors"]) == 0

    except Exception as e:
        result["errors"].append(f"Workspace generation error: {e}")

    return result
