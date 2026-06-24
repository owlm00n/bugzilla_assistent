import json
import shutil
import sys
import os
import requests
from bs4 import BeautifulSoup
import shutil
import win32com.client
import urllib.parse
import re
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

#打包命令 pyinstaller --onedir--windowed "D:\05_Code\python\bugzila\fetch_buginfo_by_API_UI.py"
#pyinstaller --onedir --windowed --icon="D:\05_Code\python\bugzila\favicon.ico" --add-data="D:\05_Code\python\bugzila\paths.json:." "D:\05_Code\python\bugzila\fetch_buginfo_by_API_UI.py" --noconfirm

if getattr(sys, 'frozen', False):
    # The application is running as a bundled executable
    paths_file = os.path.join(sys._MEIPASS, 'paths.json')
else:
    # The application is running in the development environment
    paths_file = "paths.json"

BASE_PATH = "下拉选择路径或输入路径(自动存储)"
paths = [
    r"E:\08_Bug",    # PATCH1
    r"E:\08_Bug\CQ",    # PATCH2
    r"E:\08_Bug\Task",   # PATCH2
    r"E:\08_Bug\Test",    # PATCH3
    r"F:\PD认证", 
    r"F:\PD认证\XIAOMI",  
    r"F:\PD认证\vivo_T612",    
    r"F:\PD认证\VIVO",    
    r"F:\PD认证\REALME",  # PATCH8   
    r"F:\PD认证\transsion",   
    r"F:\PD认证\SAGEREAL" ,# PATCH10
    r"F:\PD认证\ZTE\UMS9620S]P820F03",
    r"F:\PD认证\ZTE\UMS9620][P720F12]",# PATCH12,
    r"F:\PD认证\YINGKA",# PATCH13
    r"F:\PD认证\SPROCOMM"
]

""" [
  "E:\\08_Bug",
  "E:\\08_Bug\\CQ",
  "E:\\08_Bug\\Task",
  "F:\\PD认证",
  "F:\\PD认证\\XIAOMI",
  "F:\\PD认证\\vivo_T612",
  "F:\\PD认证\\VIVO",
  "F:\\PD认证\\REALME",
  "F:\\PD认证\\transsion",
  "F:\\PD认证\\SAGEREAL",
  "F:\\PD认证\\ZTE\\UMS9620S]P820F03",
  "F:\\PD认证\\ZTE\\UMS9620][P720F12]",
  "F:\\PD认证\\YINGKA",
  "F:\\PD认证\\SPROCOMM",
  "E:\\08_Bug\\Test",
  "F:\\PD认证\\S51CUBE"
] """

def load_paths():
    if os.path.exists(paths_file):
        with open(paths_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return paths

def save_paths(paths):
    with open(paths_file, "w", encoding="utf-8") as f:
        json.dump(paths, f, ensure_ascii=False, indent=2)

def on_path_entry(event):
    new_path = path_var.get().strip()
    if new_path and new_path!=BASE_PATH and new_path not in base_path:
        base_path.append(new_path)
        save_paths(base_path)
        path_combo['values'] = base_path

# bug info
index = 2
#BASE_PATH = paths[index-1]
BASE_BUGID = "SPCSS01592269"

bug_id = None
alias = None
summary = None

NORMALIZE_ACTION = "copy_new"  # 是否强制刷新附件目录（删除已有文件夹重新下载）
LOG_TO_PANEL = True  # True: 输出到面板和控制台，False: 只输出到控制台
REFRESH_ATTACHMENTS = False  # 是否强制刷新附件目录（删除已有文件夹重新下载）

# FOR TEST
session = requests.Session()
src_folder = r"E:\08_Bug\TEST"
dst_folder = r"E:\08_Bug\TEST\TEMP"
FTP_PATH = r"\\shnas02\CustomerData\消费电子业务管理部\huaqin_BD2\FTPDATA\2024-12\SPCSS01439883" 
BUG_PATH = r"E:\08_Bug\TEST\2854956 – (SPCSS01439883) [UMS9230E][HUAQIN_BD2][SL7509][15368][Other]【欧盟认证】【Type-C】【C3Z】TD 4.5.1 DRP Connect Sink Test测试fail" 


# url api
rest_url = "https://bugzilla.unisoc.com/bugzilla/rest"
bug_url = "https://bugzilla.unisoc.com/bugzilla/rest"+"/bug"

api_key = "GzzXtl8A0nU5M8HmTbnYYt0Yapc3skDCRfI0vmaa"
user = "Xianjun.Zeng@unisoc.com"
password = "uioqwer1234."

headers = {
    'Accept': 'application/json',  # Request JSON format
    'Content-Type': 'application/json'  # Send request as JSON
}

url_parameter = {
    'api_key': api_key,
    'include_fields': '_all'
}
 
invalid_chars = r'[<>:"/\\|?*\n\r\t]'


def normalize_downloaded_folder(attachment_folder, bug_id):
    """
    如果 attachment_folder 里只有一个子目录，并且子目录名是 bug_id 或以 SPCSS/bug_id 开头，
    提供可控开关：
      - 全局变量 NORMALIZE_ACTION 支持 'off' / 'move' / 'copy_new' 三种值
        * 'off'      : 不做任何规范化
        * 'move'     : 原来行为，移动子目录内容到顶层（会移除子目录）
        * 'copy_new' : 只复制子目录中新增的文件/子目录到顶层（不会覆盖已有），尽量删除空子目录
    若未设置 NORMALIZE_ACTION，默认使用 'copy_new'（满足“下载时 append，原来的不能移除”的需求）。
    """
    try:
        action = globals().get('NORMALIZE_ACTION', 'copy_new')
        if action == 'off':
            my_print("normalize_downloaded_folder: 已禁用（NORMALIZE_ACTION='off'），跳过规范化")
            return

        entries = [e for e in os.listdir(attachment_folder)
                   if not e.startswith('.') and os.path.isdir(os.path.join(attachment_folder, e))]
        my_print(f"normalize_downloaded_folder: scanning '{attachment_folder}', dirs found: {entries}")
        if len(entries) != 1:
            my_print(f"normalize_downloaded_folder: 跳过规范化（子目录数={len(entries)})")
            return
        child_name = entries[0]
        child_path = os.path.join(attachment_folder, child_name)
        if not os.path.isdir(child_path):
            return
        if not (child_name == str(bug_id) or child_name.upper().startswith("SPCSS") or child_name.startswith(str(bug_id))):
            my_print(f"normalize_downloaded_folder: 子目录名 '{child_name}' 不符合移动/复制条件，跳过")
            return

        def copy_missing(src, dst):
            """ 递归复制 src 到 dst，只复制目标不存在的文件/目录（不覆盖） """
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
                            except Exception as e:
                                my_print(f"复制文件失败: {s} -> {d}, 错误: {e}")
                        else:
                            my_print(f"已存在，跳过: {d}")
            else:
                # 单文件情况
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                else:
                    my_print(f"已存在，跳过: {dst}")

        if action == 'move':
            # 保留原有逻辑（移动，遇到冲突则重命名目标）
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
            my_print(f"已移动并去除多余顶层文件夹 '{child_name}'，内容已移动到: {attachment_folder}")
            return

        # 默认或 'copy_new' 模式：只复制新增的内容，不覆盖已有文件/文件夹
        for name in os.listdir(child_path):
            src = os.path.join(child_path, name)
            dst = os.path.join(attachment_folder, name)
            if os.path.isdir(src):
                if os.path.exists(dst) and os.path.isdir(dst):
                    # 合并目录：只复制缺失的部分
                    copy_missing(src, dst)
                elif not os.path.exists(dst):
                    try:
                        shutil.copytree(src, dst)
                    except Exception as e:
                        my_print(f"复制目录失败: {src} -> {dst}, 错误: {e}")
                else:
                    # 目标存在且不是目录，跳过以免覆盖
                    my_print(f"目标存在且非目录，跳过: {dst}")
            else:
                if not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception as e:
                        my_print(f"复制文件失败: {src} -> {dst}, 错误: {e}")
                else:
                    my_print(f"已存在，跳过文件: {dst}")

        # 尝试删除子目录：仅在子目录已空时删除，以免误删追加下载的历史文件
        try:
            if not any(os.scandir(child_path)):
                os.rmdir(child_path)
                my_print(f"子目录为空，已删除: {child_path}")
            else:
                my_print(f"子目录非空，保留: {child_path}")
        except Exception as e:
            my_print(f"尝试删除子目录时发生错误（可能非空或权限问题），保留子目录: {e}")

        my_print(f"规范化完成（模式={action}），子目录 '{child_name}' 内容已处理到: {attachment_folder}")

    except Exception as e:
        my_print(f"规范化下载文件夹时发生错误: {e}")

def create_request_url(url, url_parameter):
    #print(f"add url parameter: {url_parameter}")
    for index, (key, value) in enumerate(url_parameter.items()):
        if index == 0 :
            url += "?"
        else :
            url += "&"
        url = url + key + "=" + value  # 去除多余的空格

    print(f"url已创建: {url}\r\n")
    return url
    
def create_url_shortcut(url, shortcut_path):
    """创建快捷方式，如果路径太长则使用简化名称"""
    try:
        # 如果路径超过 200 字符，用简化名称
        if len(shortcut_path) > 200:
            shortcut_dir = os.path.dirname(shortcut_path)
            shortcut_name = "Bug.url"  # 简化为通用名称
            shortcut_path = os.path.join(shortcut_dir, shortcut_name)
            my_print(f"路径过长，已简化快捷方式名为: {shortcut_name}")
        
        # 确保父目录存在
        shortcut_dir = os.path.dirname(shortcut_path)
        os.makedirs(shortcut_dir, exist_ok=True)
        
        # .url 文件的内容结构
        content = f"""[InternetShortcut]
URL={url}
IconFile={url}
IconIndex=0
"""
        with open(shortcut_path, 'w', encoding='utf-8') as file:
            file.write(content)
        
        my_print(f"快捷方式已创建: {shortcut_path}")
    except Exception as e:
        my_print(f"创建快捷方式失败: {shortcut_path}, 错误: {e}")
        raise
    
def create_lnk_shortcut(target_path, shortcut_path):
    """ 创建快捷方式 """
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target_path
    shortcut.WorkingDirectory = os.path.dirname(target_path)
    shortcut.save()

def fetch_bug(bugid_url):
    request_url = create_request_url(bugid_url, url_parameter)
    response = requests.get(request_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"无法访问页面，状态码：{response.status_code}")
    data = response.json()
    return data

def fetch_summary(data):
    bugs = data.get("bugs", [])

    
    # 提取 Bug id
    if bugs and "id" in bugs[0]:
        bug_id = bugs[0]["id"]
    print("ID of the bug:", bug_id)

    # 提取 Bug 别名
    if bugs and "alias" in bugs[0]:
        alias_list = bugs[0]["alias"]
        # 取第一个元素，如果列表非空
        alias = alias_list[0] if alias_list else ""
    print("alias of the bug:", alias if alias else "No alias found")

    # 提取 Bug 标题
    if bugs and "summary" in bugs[0]:
        summary = bugs[0]["summary"]
    else:
        summary = "No summary found"
    #print("Title of the bug:", summary)

    summary = f"{bug_id}" + (f"({alias})" if alias else "") + " - " + summary

    print("Title of the bug:", summary)

    return summary

def fetch_path(bugcom_url):
    request_url = create_request_url(bugcom_url, url_parameter)
    response = requests.get(request_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"无法访问页面，状态码：{response.status_code}")

    data = response.json()

    # 获取第一个评论的 text 字段
    bugs = data.get("bugs", {})
    comments = []
    for bug in bugs.values():
        comments = bug.get("comments", [])
        break  # 只取第一个 bug

    ftp_path = ""
    path_url = ""
    if comments:
        text = comments[0].get("text", "")
        # 提取 "下载附件: ..." 后面的路径
        match = re.search(r'下载附件:\s*([^\n]+)', text)
        if match:
            ftp_path = match.group(1).strip()
            ftp_path = "/" + ftp_path
        # 提取“或使用快捷链接下载”后的URL
        url_match = re.search(r'或使用快捷链接下载.*?:\s*(https?://[^\s]+)', text)
        if url_match:
            path_url = url_match.group(1).strip()
    print(f"附件FTP路径: {ftp_path}")
    print(f"快捷下载链接: {path_url}\n")
    return ftp_path, path_url

def download_with_rayfile(attachment_folder, source_dir):
    exe_path = r"E:\08_Bug\sync-cmd-windows\rayfile-c_cmd.exe"
    args = [
        exe_path,
        "-a", "unitrans.unisoc.com",
        "-p", "2443",
        "-ssl",
        "-u", "ctd01",
        "-w", "ctd01@abAB",
        "-o", "download",
        "-d", attachment_folder,
        "-s", source_dir,
        "-space_id", "2",
        "-gr", "31240",
        "-file-update", "append",
    ]
    print("执行命令：", " ".join(args))
    subprocess.run(args, check=True)


def my_print(msg):
    print(msg)
    if LOG_TO_PANEL:
        log(msg)

def log(msg):
    log_panel.insert(tk.END, msg + "\n")
    log_panel.see(tk.END)
    root.update()

# 例如：
def main(bug_id, file_path):
    try:
        # 构造 API 地址
        bugid_url = f"https://bugzilla.unisoc.com/bugzilla/rest/bug/{bug_id}"
        bugcom_url = f"https://bugzilla.unisoc.com/bugzilla/rest/bug/{bug_id}/comment"

        # 下面的 fetch_bug、fetch_summary、fetch_path 会用到 bugid_url 和 bugcom_url
        # 可以通过全局变量或参数传递，也可以直接在 fetch_bug/fetch_path 里用
        # 推荐：将 bugid_url、bugcom_url 作为参数传递给 fetch_bug、fetch_path

        bug = fetch_bug(bugid_url)
        bug_raw_title = fetch_summary(bug)
        path, path_url = fetch_path(bugcom_url)
        # 清除路径中的非法字符
        bug_title = re.sub(invalid_chars, "_", bug_raw_title)
        my_print(f"清除非法字符后的标题: {bug_title}\n")
        # 创建文件夹路径
        bug_folder_path = os.path.join(file_path, "Bug " + bug_title)
        # 限制文件夹名长度，避免路径过长
        max_folder_name_len = 99
        my_print(f"最大文件夹名长度: {max_folder_name_len} 文件夹路径长度: {len(bug_folder_path)}")
        if len(bug_folder_path) > max_folder_name_len:
            remain_len = max_folder_name_len - len(file_path) - 5
            my_print(f"剩余长度: {remain_len}  # 5 for 'Bug '")
            if remain_len > 50:
                bug_title = bug_title[:50] + bug_title[-(remain_len-50):]
                my_print(f"文件夹名过长，已截断为: \n {bug_title}")
            else:
                bug_title = bug_title[:remain_len]
                my_print(f"文件夹名过长剩余没有50，已截断为: \n {bug_title}")

        my_print(f"title: {bug_title}, \nftp: {path}")
        # 创建文件夹路径
        bug_folder_path = os.path.join(file_path, "Bug " + bug_title)
        my_print(f"创建文件夹: {bug_folder_path}")

        bug_z = os.path.join(file_path, "Bug Z")
        # 检查目标文件夹是否存在，如果存在则拷贝
        if os.path.exists(bug_z):
            my_print(f"目标文件夹 {bug_z} 已存在")
            # 复制文件夹及其内容            
            my_print(f"正在复制 {bug_z} 到 {bug_folder_path}...")
            try:
                shutil.copytree(bug_z, bug_folder_path, dirs_exist_ok=True)
                my_print("文件夹复制完成！")
            except Exception as e:
                bug_folder_path = bug_z
                my_print(f"发生错误: {e}, 创建文件夹: {bug_folder_path}")
        else:
            os.makedirs(bug_folder_path, exist_ok=True)

        if bug_folder_path != bug_z:
            # 创建bug快捷方式
            url = f"https://bugzilla.unisoc.com/bugzilla/show_bug.cgi?id={bug_id}"
            shortcut_path = os.path.join(bug_folder_path, "Bug " + bug_title + '.url')
            my_print(f"创建url快捷方式: {shortcut_path}")
            create_url_shortcut(url, shortcut_path)

        # 创建附件文件夹：根据 REFRESH_ATTACHMENTS 决定是否先清空
        attachment_folder = os.path.join(bug_folder_path, 'Attachements')
        if REFRESH_ATTACHMENTS:
            if os.path.exists(attachment_folder):
                my_print(f"强制刷新附件目录，删除: {attachment_folder}")
                shutil.rmtree(attachment_folder)
            os.makedirs(attachment_folder, exist_ok=True)
        else:
            # 保留已有文件，允许增量下载
            os.makedirs(attachment_folder, exist_ok=True)

        my_print(f"创建（或使用）附件文件夹: {attachment_folder}")

        # 创建附件快捷方式
        shortcut_path = os.path.join(attachment_folder, str(bug_id) + '.url')
        my_print(f"创建url快捷方式: {shortcut_path}")
        create_url_shortcut(path_url, shortcut_path)
        
        # 调用 rayfile-c_cmd.exe 下载附件（-file-update append 已在 args 中）
        my_print(f"下载到附件中......: {attachment_folder}")
        download_with_rayfile(attachment_folder, path)

        # 下载后规范化（去掉多余顶层 id 目录）
        normalize_downloaded_folder(attachment_folder, bug_id)

        # 返回关键参数
        return {
            "bug_id": bug_id,
            "base_path": bug_folder_path,
            "bug_title": bug_raw_title,
            "ftp_path": path,
            "path_url": path_url
        }

    except Exception as e:
        my_print(f"发生错误: {e}")

def update_param_fields(bug_id, base_path, bug_title="", ftp_path="", path_url=""):
    bug_id_val.set(bug_id)
    base_path_val.set(base_path)  # 保留给 open_base_path 等使用

    # 同步更新 multi-line Text 显示
    try:
        base_path_text.config(state="normal")
        base_path_text.delete(1.0, tk.END)
        base_path_text.insert(tk.END, base_path)
        base_path_text.config(state="disabled")
    except Exception:
        pass

    ftp_path_val.set(ftp_path)
    path_url_val.set(path_url)
    # Bug标题多行显示
    bug_title_text.config(state="normal")
    bug_title_text.delete(1.0, tk.END)
    bug_title_text.insert(tk.END, bug_title)
    bug_title_text.config(state="disabled")

def open_path_url():
    url = path_url_val.get().strip()
    if not url:
        messagebox.showerror("错误", "快捷下载链接为空！")
        return
    try:
        os.startfile(url)
    except Exception as e:
        messagebox.showerror("错误", f"无法打开链接: {e}")

def open_base_path():
    path = base_path_val.get().strip() or path_var.get().strip()
    if not path or path == BASE_PATH:
        messagebox.showerror("错误", "路径为空或未选择有效路径！")
        return
    if not os.path.exists(path):
        messagebox.showerror("错误", f"路径不存在: {path}")
        return
    try:
        os.startfile(path)
    except Exception as e:
        messagebox.showerror("错误", f"无法打开路径: {e}")

def run_main():
    bug_id = bug_id_var.get().strip()
    base_path = path_var.get().strip()
    log_panel.delete(1.0, tk.END)
    # 判断 Bug ID 格式
    if not (bug_id.isdigit() or bug_id.startswith("SPCSS")):
        messagebox.showerror("错误", "Bug ID 必须为数字或以SPCSS开头，请重新输入！")
        bug_id_var.set("")  # 清空输入框
        bug_id_entry.focus_set()  # 输入框获得焦点
        return
    if not base_path:
        messagebox.showerror("错误", "路径不能为空！")
        return
    try:
        log(f"开始处理 Bug: {bug_id}")
        result = main(bug_id, base_path)
        update_param_fields(**result)
        log("处理完成！")
        open_base_path()
        messagebox.showinfo("完成", "处理完成！")
    except Exception as e:
        log(f"发生错误: {e}")
        messagebox.showerror("发生错误", str(e))


root = tk.Tk()
root.title("Bugzilla 工具")

# Bug ID
tk.Label(root, text="Bug ID:").grid(row=0, column=0, padx=8, pady=8, sticky="e")

# info_frame 用于在同一个 grid 单元内垂直放置「两行信息」和「输入框」
info_frame = tk.Frame(root)
info_frame.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

# 两行只读显示（剪贴板内容 + 默认 bug id）
bug_info_text = tk.Text(info_frame, height=2, width=90, wrap="word", state="disabled", bg="#f0f0f0")
bug_info_text.pack(fill="x")
bug_id_var = tk.StringVar()
# 填充显示内容（两个独立的行）
try:
    clipboard_content = root.clipboard_get().strip()
    if (clipboard_content.isdigit() or clipboard_content.startswith("SPCSS")):
        bug_id_var.set(clipboard_content)
    else:
        bug_id_var.set(BASE_BUGID)
        clipboard_content = "Invalid bug id"
except Exception:
    clipboard_content = "读取剪贴板失败"
    bug_id_var.set(BASE_BUGID)

info_lines = f"读取剪贴板: {clipboard_content}\n默认 Bug ID: {BASE_BUGID}"
bug_info_text.config(state="normal")
bug_info_text.delete(1.0, tk.END)
bug_info_text.insert(tk.END, info_lines)
bug_info_text.config(state="disabled")


bug_id_entry = tk.Entry(info_frame, textvariable=bug_id_var, width=60)
bug_id_entry.pack(fill="x", pady=(6,0))

# 路径选择
base_path = load_paths()
tk.Label(root, text="存储路径:").grid(row=1, column=0, padx=8, pady=8, sticky="e")
path_var = tk.StringVar(value=BASE_PATH)
path_combo = ttk.Combobox(root, textvariable=path_var, values=base_path, width=90)
path_combo.grid(row=1, column=1, padx=8, pady=8)
path_combo.bind("<FocusOut>", on_path_entry)

# 关键参数区
tk.Label(root, text="关键参数:").grid(row=4, column=0, padx=8, pady=(16,4), sticky="w", columnspan=2)
bug_id_val = tk.StringVar()
base_path_val = tk.StringVar()
ftp_path_val = tk.StringVar()
path_url_val = tk.StringVar()

tk.Label(root, text="Bug ID:").grid(row=5, column=0, padx=8, pady=2, sticky="e")
tk.Entry(root, textvariable=bug_id_val, width=90, state="readonly").grid(row=5, column=1, padx=8, pady=2, sticky="w")

tk.Button(root, text="存储路径", command=open_base_path).grid(row=6, column=0, padx=8, pady=2, sticky="e")
# entry = tk.Entry(root, textvariable=base_path_val, width=90, state="readonly")
# entry.grid(row=6, column=1, padx=8, pady=2, sticky="ew")
# 改为：多行只读显示（自动换行）
base_path_text = tk.Text(root, height=3, width=90, wrap="word", state="disabled", bg="#f0f0f0")
base_path_text.grid(row=6, column=1, padx=8, pady=2, sticky="ew")
tk.Label(root, text="Bug标题:").grid(row=7, column=0, padx=8, pady=2, sticky="ne")
bug_title_text = tk.Text(root, height=3, width=90, wrap="word", state="disabled", bg="#f0f0f0")
bug_title_text.grid(row=7, column=1, padx=8, pady=2, sticky="w")
tk.Label(root, text="FTP路径:").grid(row=8, column=0, padx=8, pady=2, sticky="e")
tk.Entry(root, textvariable=ftp_path_val, width=90, state="readonly").grid(row=8, column=1, padx=8, pady=2, sticky="w")
tk.Button(root, text="快捷下载链接", command=open_path_url).grid(row=9, column=0, padx=8, pady=2, sticky="e")
tk.Entry(root, textvariable=path_url_val, width=90, state="readonly").grid(row=9, column=1, padx=8, pady=2, sticky="w")

# 日志面板
tk.Label(root, text="运行日志:").grid(row=10, column=0, padx=8, pady=8, sticky="nw")
log_panel = tk.Text(root, height=12, width=90)
log_panel.grid(row=10, column=1, padx=8, pady=8, sticky="w")

# 按钮
run_btn = tk.Button(root, text="开始处理", command=run_main)
run_btn.grid(row=3, column=0, padx=8, pady=12, sticky="ew", columnspan=2)

root.mainloop()



