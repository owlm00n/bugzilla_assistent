#!/usr/bin/env python3
"""
Bug Logs - 日志目录列表 & 结构化评论解析 & 附件下载模块
支持双通道：UNC (Windows) + FTP (fallback)
专门处理 unisoc Bugzilla 的 19 字段结构化 Bug 报告格式

附件下载：
  - 智能识别两种附件类型（UNC 路径 或 FTP/rayfile）
  - Type 1 (SPCSS): FTP/rayfile 下载 → subprocess rayfile-c_cmd.exe
  - Type 2 (内部测试): UNC 路径 → shutil.copy2 直接复制
"""

import json
import os
import re
import shutil
import subprocess
import sys

# 配置路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config", "bugzilla_instances.json")

# 离线模式标记
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
# 跨 Skill 导入：从 bug-core 获取 fetch_bug_rest
# ============================================================

def _import_bug_core():
    """三级降级加载 bug-core 模块"""
    try:
        from bug_core import fetch_bug_rest
        return fetch_bug_rest
    except ImportError:
        import sys as _sys
        _skills = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _core = os.path.join(_skills, "bug-core")
        if _core not in _sys.path:
            _sys.path.insert(0, _core)
        from bug_core import fetch_bug_rest as _fetch
        return _fetch


def _import_get_instance_config():
    """三级降级加载 get_instance_config"""
    try:
        from bug_core import get_instance_config as gic
        return gic
    except ImportError:
        import sys as _sys
        _skills = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _core = os.path.join(_skills, "bug-core")
        if _core not in _sys.path:
            _sys.path.insert(0, _core)
        from bug_core import get_instance_config as _gic
        return _gic


# ============================================================
# 结构化评论解析
# ============================================================

def parse_unisoc_structured_fields(text: str) -> dict:
    """解析unisoc Bugzilla结构化Bug报告格式（Comment #0的19字段模板）。

    返回dict包含:
        - header: {severity_desc, external_conditions, probability, ...}
        - fields: {N: {name, value}} 编号字段
        - log_name: str, log_path: str, log_servers: dict
        - log_type: str, occur_time: str, version_path: str
        - has_structured_format: bool
    """
    result = {
        "has_structured_format": False,
        "header": {},
        "fields": {},
        "log_name": "",
        "log_path": "",
        "log_servers": {},
        "log_type": "",
        "occur_time": "",
        "version_path": "",
    }

    # Header field patterns (Chinese labels with colons, before first [N.])
    HEADER_FIELDS = {
        "严重级别": "severity_desc",
        "外部条件": "external_conditions",
        "出现概率": "probability",
        "用户操作类型": "user_operation_type",
        "业务功能类型": "business_function_type",
        "故障影响": "fault_impact",
        "恢复性": "recoverability",
    }

    # Parse header fields
    for cn_label, key in HEADER_FIELDS.items():
        m = re.search(rf'{cn_label}[：:]\s*(.*?)(?:\n|$)', text)
        if m:
            result["header"][key] = m.group(1).strip()

    # Parse numbered fields: [N.Field Name]: value
    field_pattern = re.compile(r'\[(\d+)\.([^\]]+)\]\s*:?\s*([\s\S]*?)(?=\[\d+\.|\Z)')
    for m in field_pattern.finditer(text):
        field_num = m.group(1)
        field_name = m.group(2).strip()
        field_value = m.group(3).strip()
        result["fields"][field_num] = {"name": field_name, "value": field_value}

    if not result["fields"]:
        return result

    result["has_structured_format"] = True

    # Extract [14.Logpath] sub-fields
    logpath = result["fields"].get("14", {}).get("value", "")
    if logpath:
        # LogName (may be empty — no value after colon)
        m = re.search(r'LogName[^\S\n]*:[^\S\n]*(.*?)(?:\n|$)', logpath)
        if m and m.group(1).strip():
            result["log_name"] = m.group(1).strip()

        # LogPath (UNC path on line(s) until next section key)
        m = re.search(r'LogPath[^\S\n]*:[^\S\n]*((?:[^\n]+(?:\n(?!(?:The Path|LogName|External|Internal|UNISOC|DES|\[\d+\.))[^\n]*)*))', logpath)
        if m:
            result["log_path"] = m.group(1).strip().replace('\n', '').replace('\r', '')

        # Log Servers
        servers = {}
        ext_m = re.search(r'External[^\S\n]*:[^\S\n]*([^\n]+)', logpath)
        if ext_m:
            servers["external"] = ext_m.group(1).strip()
        int_m = re.search(r'Internal[^\S\n]*:[^\S\n]*([^\n]+)', logpath)
        if int_m:
            servers["internal"] = int_m.group(1).strip()
        ftp_m = re.search(r'(?:UNISOC\s*)?FTP[^\S\n]*:[^\S\n]*([^\n]+)', logpath)
        if ftp_m:
            servers["ftp"] = ftp_m.group(1).strip()
        des_m = re.search(r'DES[^\S\n]*:[^\S\n]*([^\n]+)', logpath)
        if des_m:
            servers["des"] = des_m.group(1).strip()
        result["log_servers"] = servers

    # Extract [15.Logtype]
    logtype_field = result["fields"].get("15", {}).get("value", "")
    if logtype_field:
        result["log_type"] = logtype_field.strip()

    # Extract [16.Occur Time]
    occur_field = result["fields"].get("16", {}).get("value", "")
    if occur_field:
        result["occur_time"] = occur_field.strip()

    # Extract [19.Version Path]
    ver_field = result["fields"].get("19", {}).get("value", "")
    if ver_field:
        result["version_path"] = ver_field.strip()

    return result


# ============================================================
# 日志目录列表 — 双通道 (UNC + FTP)
# ============================================================

def _try_unc_listdir(unc_path: str) -> dict:
    """尝试通过Windows UNC路径列出目录内容。"""
    import os as _os
    import platform as _platform

    if _platform.system() != "Windows":
        return {"accessible": False, "error": "UNC listing only supported on Windows"}

    try:
        items = []
        with _os.scandir(unc_path) as it:
            for entry in it:
                try:
                    stat = entry.stat()
                except OSError:
                    stat = None
                items.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size if stat and entry.is_file() else 0,
                    "modified": "",
                })
        return {
            "accessible": True,
            "method": "unc",
            "entries": sorted(items, key=lambda x: (x["type"], x["name"])),
        }
    except OSError as e:
        return {"accessible": False, "method": "unc", "error": str(e)}


def _try_ftp_listdir(ftp_url_or_path: str, config: dict) -> dict:
    """尝试通过FTP列出目录内容。"""
    import ftplib
    import ssl
    import os as _os

    host = config.get("ftp_host", "")
    port = int(config.get("ftp_port", 21))
    user = config.get("ftp_user", "anonymous")
    password = config.get("ftp_password", "")
    use_ssl = config.get("ftp_use_ssl", False)

    if not host:
        return {"accessible": False, "method": "ftp", "error": "No FTP host configured"}

    # Convert UNC path to FTP path
    ftp_path = ftp_url_or_path
    if ftp_path.startswith("ftp://"):
        parsed = ftp_path.replace("ftp://", "")
        if "/" in parsed:
            ftp_path = "/" + parsed.split("/", 1)[1]
        else:
            ftp_path = "/"
    elif ftp_path.startswith("\\\\"):
        parts = ftp_path.replace("\\\\", "").split("\\", 1)
        if len(parts) > 1:
            ftp_path = "/" + parts[1].replace("\\", "/")
        else:
            ftp_path = "/"

    ftp_path = ftp_path.rstrip("/")
    if not ftp_path:
        ftp_path = "/"

    try:
        if use_ssl:
            ctx = ssl.create_default_context()
            ftp = ftplib.FTP_TLS(context=ctx, timeout=15)
        else:
            ftp = ftplib.FTP(timeout=15)

        ftp.connect(host, port)
        ftp.login(user, password)
        if use_ssl:
            ftp.prot_p()

        items = []
        ftp.cwd(ftp_path)

        def _parse_line(line):
            """Parse FTP LIST line into name/type/size."""
            parts = line.split()
            if len(parts) < 4:
                return None
            perms = parts[0]
            name = parts[-1]
            if name in (".", ".."):
                return None
            is_dir = perms.startswith("d") or "<DIR>" in line
            try:
                size = int(parts[4]) if not is_dir and len(parts) > 4 and perms[0] != "d" else 0
            except (ValueError, IndexError):
                size = 0
            return {"name": name, "type": "dir" if is_dir else "file", "size": size, "modified": ""}

        for line in ftp.dir():
            parsed = _parse_line(line)
            if parsed:
                items.append(parsed)

        ftp.quit()
        return {
            "accessible": True,
            "method": "ftp",
            "entries": sorted(items, key=lambda x: (x["type"], x["name"])),
        }
    except Exception as e:
        return {"accessible": False, "method": "ftp", "error": str(e)}


def list_log_directory(path: str, config: dict = None) -> dict:
    """列出日志目录内容，依次尝试UNC和FTP方式。

    Args:
        path: UNC路径 (\\\\server\\share\\...) 或 ftp:// URL
        config: 实例配置dict（含FTP凭证），可选

    Returns:
        {
            "path": str,
            "method": "unc" | "ftp" | "none",
            "accessible": bool,
            "entries": [...],
            "files": [str, ...],
            "subdirs": [str, ...],
            "error": str or None,
        }
    """
    result = {
        "path": path,
        "method": "none",
        "accessible": False,
        "entries": [],
        "files": [],
        "subdirs": [],
        "error": None,
    }

    if not path:
        result["error"] = "No path provided"
        return result

    # Method 1: Try UNC (Windows direct access)
    if path.startswith("\\\\"):
        unc_result = _try_unc_listdir(path)
        if unc_result["accessible"]:
            result.update(unc_result)
            result["files"] = [e["name"] for e in unc_result["entries"] if e["type"] == "file"]
            result["subdirs"] = [e["name"] for e in unc_result["entries"] if e["type"] == "dir"]
            return result

    # Method 2: Try FTP
    if config and config.get("ftp_host"):
        ftp_result = _try_ftp_listdir(path, config)
        if ftp_result["accessible"]:
            result.update(ftp_result)
            result["files"] = [e["name"] for e in ftp_result["entries"] if e["type"] == "file"]
            result["subdirs"] = [e["name"] for e in ftp_result["entries"] if e["type"] == "dir"]
            return result
        # If both failed, return the errors
        if isinstance(path, str) and path.startswith("\\\\"):
            result["error"] = f"UNC: {unc_result.get('error', 'N/A')}; FTP: {ftp_result.get('error', 'N/A')}"
        else:
            result["error"] = ftp_result.get("error", "FTP listing failed")
        return result

    # No config, UNC-only path
    if path.startswith("\\\\"):
        unc_result = _try_unc_listdir(path)
        if unc_result["accessible"]:
            result.update(unc_result)
            result["files"] = [e["name"] for e in unc_result["entries"] if e["type"] == "file"]
            result["subdirs"] = [e["name"] for e in unc_result["entries"] if e["type"] == "dir"]
        else:
            result["error"] = f"UNC: {unc_result.get('error', 'N/A')}"
    else:
        result["error"] = "Unsupported path scheme (not UNC or FTP)"

    return result


# ============================================================
# 组合查询：Bug信息 + 结构化解析 + 日志目录
# ============================================================

def fetch_bug_with_logs(bug_id: str, instance: str = None) -> dict:
    """获取Bug完整信息（含结构化评论解析和日志目录列表）。

    对unisoc类型的Bug，解析Comment #0中的结构化Bug报告字段，
    列出LogPath目录下的日志文件，帮助AI根据文件名/修改时间识别相关日志。

    Returns:
        标准的fetch_bug_rest()结果，另增加:
            - "structured_fields": parse_unisoc_structured_fields()结果 或 {}
            - "log_directory": list_log_directory()结果 或 None
    """
    # 跨 Skill 导入 bug_core.fetch_bug_rest
    fetch_bug_rest = _import_bug_core()
    get_instance_config_fn = _import_get_instance_config()

    result = fetch_bug_rest(bug_id, instance=instance)

    if "error" in result:
        return result

    result["structured_fields"] = {}
    result["log_directory"] = None

    # Get instance config for FTP credentials
    try:
        inst_name, inst_config = get_instance_config_fn(instance)
    except (ValueError, KeyError):
        inst_config = {}

    # Fetch comments to find structured bug report
    import requests
    rest_url = inst_config.get("rest_url", "")
    api_key = inst_config.get("api_key", "")

    if rest_url:
        try:
            params = {"include_fields": "_all"} if not api_key else {"api_key": api_key}
            comment_resp = requests.get(
                f"{rest_url}/bug/{bug_id}/comment",
                params=params,
                headers={"Accept": "application/json"},
                timeout=15
            )
            comment_resp.raise_for_status()
            comment_data = comment_resp.json()
            comments = []
            for bc in comment_data.get("bugs", {}).values():
                comments = bc.get("comments", [])
                break
        except Exception:
            comments = []
    else:
        comments = []

    # Parse structured fields from first comment
    if comments:
        first_text = comments[0].get("text", "")
        structured = parse_unisoc_structured_fields(first_text)
        result["structured_fields"] = structured

        # If LogPath found, try to list it
        log_path = structured.get("log_path", "")
        if log_path and structured.get("has_structured_format"):
            dir_result = list_log_directory(log_path, config=inst_config)
            result["log_directory"] = dir_result

    return result


# ============================================================
# Bug 附件下载 — 智能识别两种附件类型 + 统一下载
# ============================================================

def detect_attachment_type(bug_id: str, instance: str = None) -> dict:
    """智能检测 Bug 的附件类型。

    一个 Bug 只有一种附件类型，检测逻辑（按优先级）：
    1. Type 2 (UNC): Comment #0 含 [14.Logpath] 结构化字段 + 有效 UNC 路径
    2. Type 1 (rayfile): Comment #0 含 "下载附件:" 开头的 FTP/rayfile 路径
    3. Type "none": 无法识别任何附件类型

    Returns:
        {
            "type": "unc" | "rayfile" | "none",
            "source_path": str,       # UNC 路径 或 FTP 路径
            "bug_info": dict,         # Bug 基本信息
            "instance_config": dict,  # 实例配置（含 FTP 凭证）
            "error": str or None,
        }
    """
    result = {
        "type": "none",
        "source_path": "",
        "bug_info": {},
        "instance_config": {},
        "error": None,
    }

    try:
        # 获取 Bug 完整信息（含结构化解析和评论）
        bug_data = fetch_bug_with_logs(bug_id, instance=instance)
        if "error" in bug_data:
            result["error"] = f"Failed to fetch bug: {bug_data['error']}"
            return result

        # 获取实例配置
        get_instance_config_fn = _import_get_instance_config()
        try:
            inst_name, inst_config = get_instance_config_fn(instance)
            result["instance_config"] = inst_config
        except (ValueError, KeyError):
            inst_config = {}

        # 提取 Bug 基本信息
        result["bug_info"] = {
            "bug_id": bug_data.get("bug_id", bug_id),
            "summary": bug_data.get("summary", ""),
            "status": bug_data.get("status", ""),
            "product": bug_data.get("product", ""),
            "component": bug_data.get("component", ""),
            "url": bug_data.get("url", ""),
        }

        # 检测 Type 2: UNC 路径（结构化评论 [14.Logpath]）
        structured = bug_data.get("structured_fields", {})
        if structured.get("has_structured_format"):
            log_path = structured.get("log_path", "")
            if log_path and log_path.startswith("\\\\"):
                result["type"] = "unc"
                result["source_path"] = log_path
                return result

        # 检测 Type 1: FTP/rayfile（Comment #0 中 "下载附件:" 模式）
        import requests
        rest_url = inst_config.get("rest_url", "")
        api_key = inst_config.get("api_key", "")

        if rest_url:
            try:
                params = {"include_fields": "_all"} if not api_key else {"api_key": api_key}
                comment_resp = requests.get(
                    f"{rest_url}/bug/{bug_id}/comment",
                    params=params,
                    headers={"Accept": "application/json"},
                    timeout=15
                )
                comment_resp.raise_for_status()
                comment_data = comment_resp.json()
                comments = []
                for bc in comment_data.get("bugs", {}).values():
                    comments = bc.get("comments", [])
                    break

                # 搜索 "下载附件:" 模式
                for c in comments:
                    text = c.get("text", "")
                    m = re.search(r'下载附件\s*[：:]\s*(\S+)', text)
                    if m:
                        result["type"] = "rayfile"
                        result["source_path"] = m.group(1).strip()
                        return result

                # Fallback: 搜索 ftp:// 链接
                for c in comments:
                    text = c.get("text", "")
                    m = re.search(r'(ftp://[^\s)\]]+)', text)
                    if m:
                        result["type"] = "rayfile"
                        result["source_path"] = m.group(1).strip()
                        return result

            except Exception as e:
                result["error"] = f"Failed to detect attachment type: {e}"
                return result

        result["error"] = "No attachment source found (neither UNC path nor FTP/rayfile link)"
        return result

    except Exception as e:
        result["error"] = f"Detection error: {e}"
        return result


def copy_missing(src: str, dst: str) -> None:
    """递归复制 src 到 dst，仅复制目标不存在的文件/目录（不覆盖已有）。
    移植自原 UI 工具 fetch_buginfo_by_API_UI.py line 152-174。
    """
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            s = os.path.join(src, name)
            d = os.path.join(dst, name)
            if os.path.isdir(s):
                copy_missing(s, d)
            else:
                if not os.path.exists(d):
                    try:
                        shutil.copy2(s, d)
                    except Exception:
                        pass
    else:
        # 单文件情况
        if not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass


def download_from_unc_path(unc_path: str, dest_dir: str) -> dict:
    """通过 UNC 路径直接复制日志文件到本地。

    使用 os.scandir() 遍历 UNC 路径，shutil.copy2() 复制文件保留元数据。
    等同于原工具的 [14.Logpath] 附件复制逻辑。

    Returns:
        {"success": bool, "copied": int, "skipped": int, "errors": [str, ...], "dest_dir": str}
    """
    result = {
        "success": False,
        "copied": 0,
        "skipped": 0,
        "errors": [],
        "dest_dir": dest_dir,
    }

    try:
        os.makedirs(dest_dir, exist_ok=True)

        if not os.path.exists(unc_path):
            result["errors"].append(f"UNC path not accessible: {unc_path}")
            return result

        for entry in os.scandir(unc_path):
            if entry.is_file():
                src = entry.path
                dst = os.path.join(dest_dir, entry.name)
                try:
                    if os.path.exists(dst):
                        result["skipped"] += 1
                    else:
                        shutil.copy2(src, dst)
                        result["copied"] += 1
                except Exception as e:
                    result["errors"].append(f"Failed to copy {entry.name}: {e}")

        result["success"] = len(result["errors"]) == 0 or result["copied"] > 0

    except Exception as e:
        result["errors"].append(f"UNC download error: {e}")

    return result


def download_from_rayfile(ftp_path: str, dest_dir: str, instance_config: dict = None) -> dict:
    """通过 rayfile-c_cmd.exe 从 FTP 下载附件（SPCSS 客户附件）。

    使用与原工具完全一致的命令行参数执行 rayfile 子进程。

    Returns:
        {"success": bool, "command": str, "stdout": str, "stderr": str, "error": str or None}
    """
    result = {
        "success": False,
        "command": "",
        "stdout": "",
        "stderr": "",
        "error": None,
    }

    if instance_config is None:
        instance_config = {}

    # 从实例配置读取 FTP 凭证（与原工具一致）
    host = instance_config.get("ftp_host", "unitrans.unisoc.com")
    port = str(instance_config.get("ftp_port", "2443"))
    user = instance_config.get("ftp_user", "ctd01")
    password = instance_config.get("ftp_password", "ctd01@abAB")
    # 默认 exe 路径（与原工具一致）
    exe_path = instance_config.get("rayfile_exe", r"E:\08_Bug\sync-cmd-windows\rayfile-c_cmd.exe")

    # 确保目标目录存在
    os.makedirs(dest_dir, exist_ok=True)

    # 构造 rayfile 命令（完全匹配原工具参数）
    args = [
        exe_path,
        "-a", host,
        "-p", port,
        "-ssl",
        "-u", user,
        "-w", password,
        "-o", "download",
        "-d", dest_dir,
        "-s", ftp_path,
        "-space_id", "2",
        "-gr", "31240",
        "-file-update", "append",
    ]

    result["command"] = " ".join(args)

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=600,
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["success"] = proc.returncode == 0
        if not result["success"]:
            result["error"] = f"rayfile exited with code {proc.returncode}: {proc.stderr.strip()}"
    except FileNotFoundError:
        result["error"] = f"rayfile executable not found: {exe_path}"
    except subprocess.TimeoutExpired:
        result["error"] = "rayfile download timed out (600s)"
    except Exception as e:
        result["error"] = f"rayfile execution error: {e}"

    return result


def normalize_downloaded_folder(attachment_folder: str, bug_id: str, action: str = "copy_new") -> dict:
    """规范化下载后的附件文件夹。
    移植自原 UI 工具 fetch_buginfo_by_API_UI.py line 122-235。

    如果 attachment_folder 下恰好一个有效子目录（不以 '.' 开头、
    名称等于 bug_id 或以 "SPCSS" 开头），则：
    - "off": 不做任何处理
    - "move": 移动子目录所有内容到根层级，删除子目录
    - "copy_new": 仅复制不存在的文件到根层级（不覆盖已有）

    Returns:
        {"action": str, "processed": bool, "child_name": str or None, "error": str or None}
    """
    result = {
        "action": action,
        "processed": False,
        "child_name": None,
        "error": None,
    }

    try:
        if action == "off":
            return result

        if not os.path.isdir(attachment_folder):
            result["error"] = f"Attachment folder does not exist: {attachment_folder}"
            return result

        # 查找第一个有效子目录
        entries = [e for e in os.listdir(attachment_folder)
                   if not e.startswith('.') and os.path.isdir(os.path.join(attachment_folder, e))]

        if len(entries) != 1:
            return result

        child_name = entries[0]
        child_path = os.path.join(attachment_folder, child_name)

        if not os.path.isdir(child_path):
            return result

        # 子目录名必须匹配条件
        bug_id_str = str(bug_id)
        if not (child_name == bug_id_str
                or child_name.upper().startswith("SPCSS")
                or child_name.startswith(bug_id_str)):
            return result

        result["child_name"] = child_name

        if action == "move":
            # 移动子目录所有内容到上层，冲突时重命名
            for name in os.listdir(child_path):
                src = os.path.join(child_path, name)
                dst = os.path.join(attachment_folder, name)
                if os.path.exists(dst):
                    base, ext = os.path.splitext(name)
                    i = 1
                    newname = f"{base}_{i}{ext}"
                    while os.path.exists(os.path.join(attachment_folder, newname)):
                        i += 1
                        newname = f"{base}_{i}{ext}"
                    dst = os.path.join(attachment_folder, newname)
                shutil.move(src, dst)
            try:
                os.rmdir(child_path)
            except OSError:
                shutil.rmtree(child_path, ignore_errors=True)
            result["processed"] = True

        else:
            # "copy_new" — 仅复制新增内容，不覆盖
            for name in os.listdir(child_path):
                src = os.path.join(child_path, name)
                dst = os.path.join(attachment_folder, name)
                if os.path.isdir(src):
                    if os.path.exists(dst) and os.path.isdir(dst):
                        copy_missing(src, dst)
                    elif not os.path.exists(dst):
                        try:
                            shutil.copytree(src, dst)
                        except Exception:
                            pass
                else:
                    if not os.path.exists(dst):
                        try:
                            shutil.copy2(src, dst)
                        except Exception:
                            pass

            # 如果子目录已空则删除
            try:
                if not any(os.scandir(child_path)):
                    os.rmdir(child_path)
            except Exception:
                pass
            result["processed"] = True

    except Exception as e:
        result["error"] = f"Normalize error: {e}"

    return result


def download_bug_attachments(
    bug_id: str,
    dest_dir: str,
    instance: str = None,
    refresh: bool = False,
    normalize_action: str = "copy_new",
) -> dict:
    """下载 Bug 附件的统一入口。

    智能检测附件类型（UNC 或 rayfile），自动下载到指定目录，
    下载后可选规范化文件夹结构。

    Args:
        bug_id: Bug ID
        dest_dir: 下载目标根目录（附件的实际路径为 {dest_dir}/Attachements/）
        instance: Bugzilla 实例名（可选）
        refresh: True = 清空后重新下载，False = 增量下载
        normalize_action: "off" | "move" | "copy_new"（默认 "copy_new"）

    Returns:
        {
            "success": bool,
            "bug_id": str,
            "attachment_type": "unc" | "rayfile" | "none",
            "dest_dir": str,
            "attachment_folder": str,
            "files_copied": int,
            "errors": [str, ...],
            "normalize_result": dict or None,
        }
    """
    result = {
        "success": False,
        "bug_id": str(bug_id),
        "attachment_type": "none",
        "dest_dir": dest_dir,
        "attachment_folder": os.path.join(dest_dir, "Attachements"),
        "files_copied": 0,
        "errors": [],
        "normalize_result": None,
    }

    try:
        # 1. 检测附件类型
        detection = detect_attachment_type(bug_id, instance=instance)
        result["attachment_type"] = detection["type"]

        if detection.get("error") and detection["type"] == "none":
            result["errors"].append(detection["error"])
            return result

        # 2. 创建附件目录
        attachment_folder = result["attachment_folder"]
        if refresh and os.path.exists(attachment_folder):
            shutil.rmtree(attachment_folder)
        os.makedirs(attachment_folder, exist_ok=True)

        # 3. 按类型执行下载
        source_path = detection.get("source_path", "")

        if detection["type"] == "unc":
            download_result = download_from_unc_path(source_path, attachment_folder)
            result["files_copied"] = download_result.get("copied", 0)
            result["errors"].extend(download_result.get("errors", []))
            if not download_result.get("success") and result["files_copied"] == 0:
                result["errors"].append("UNC download failed")

        elif detection["type"] == "rayfile":
            inst_config = detection.get("instance_config", {})
            download_result = download_from_rayfile(source_path, attachment_folder, inst_config)
            if not download_result.get("success"):
                result["errors"].append(
                    download_result.get("error", "rayfile download failed"))
            # rayfile 不返回确切的 copied 数，标记为 -1 表示未知
            result["files_copied"] = -1

        # 4. 规范化文件夹
        if normalize_action != "off":
            norm_result = normalize_downloaded_folder(
                attachment_folder, bug_id, action=normalize_action)
            result["normalize_result"] = norm_result

        result["success"] = len(result["errors"]) == 0

    except Exception as e:
        result["errors"].append(f"Download error: {e}")

    return result
