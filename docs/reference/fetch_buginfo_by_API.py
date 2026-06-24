import json
import shutil
import os
import requests
from bs4 import BeautifulSoup
import shutil
import win32com.client
import urllib.parse
import re
import subprocess
import tkinter as tk

paths_file = "E:\\08_Bug\\paths.json"
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

def load_paths():
    if os.path.exists(paths_file):
        with open(paths_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return paths

def save_paths(paths):
    with open(paths_file, "w", encoding="utf-8") as f:
        json.dump(paths, f, ensure_ascii=False, indent=2)
# bug info
index = 2
BASE_PATH = paths[index-1]
BASE_BUGID = "SPCSS01504600"
bug_id = None
alias = None
summary = None

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
 
invalid_chars = r'[<>:"/\\|?*]'



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
    #print(f"快捷方式创建: {shortcut_path}")
    # .url 文件的内容结构
    content = f"""[InternetShortcut]
    URL={url}
    IconFile={url}
    IconIndex=0
    """
    # print(f"url已创建: {content}")
    
    # 写入内容到指定路径
    with open(shortcut_path, 'w') as file:
        file.write(content)
    
    #print(f"快捷方式已创建: {shortcut_path}")
    
def create_lnk_shortcut(target_path, shortcut_path):
    """ 创建快捷方式 """
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target_path
    shortcut.WorkingDirectory = os.path.dirname(target_path)
    shortcut.save()

def fetch_bug():
    """抓取 Bug 页面，提取标题和附件路径"""
    request_url = create_request_url(bugid_url, url_parameter)
    response = requests.get(request_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"无法访问页面，状态码：{response.status_code}")
    print(f"Debug: Parsed response code = {response}")

    data = response.json()  # 解析为 JSON
    #print(f"Debug: Parsed JSON = {data}")

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

def fetch_path():
    """从评论中提取附件下载链接和快捷链接"""
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
        "-gr", "31240"
    ]
    print("执行命令：", " ".join(args))
    subprocess.run(args, check=True)

def main(bug_id, file_path):
    try:
        bug = fetch_bug()
        bug_raw_title = fetch_summary(bug)
        path, path_url = fetch_path()
        # 清除路径中的非法字符
        bug_title = re.sub(invalid_chars, "_", bug_raw_title)
        # 创建文件夹路径
        bug_folder_path = os.path.join(file_path, "Bug " + bug_title)
        # 限制文件夹名长度，避免路径过长
        max_folder_name_len = 99
        print(f"最大文件夹名长度: {max_folder_name_len} 文件夹路径长度: {len(bug_folder_path)}  \n  ")
        if len(bug_folder_path) > max_folder_name_len:
            remain_len = max_folder_name_len - len(file_path) - 5
            print(f"剩余长度: {remain_len}  # 5 for 'Bug '")
            if remain_len > 50:
                bug_title = bug_raw_title[:50] + bug_raw_title[-(remain_len-50):]
                print(f"文件夹名过长，已截断为: \n {bug_title}")
            else:
                bug_title = bug_raw_title[:remain_len]
                print(f"文件夹名过长剩余没有50，已截断为: \n {bug_title}")

        print(f"title: {bug_title}, \nftp: {path}\n")
        # 创建文件夹路径
        bug_folder_path = os.path.join(file_path, "Bug " + bug_title)
        print(f"创建文件夹: {bug_folder_path}\n")

        bug_z = os.path.join(file_path, "Bug Z")
        # 检查目标文件夹是否存在，如果存在则拷贝
        if os.path.exists(bug_z):
            print(f"目标文件夹 {bug_z} 已存在")
            # 复制文件夹及其内容            
            print(f"正在复制 {bug_z} 到 {bug_folder_path}...\n")
            try:
                shutil.copytree(bug_z, bug_folder_path, dirs_exist_ok=True)
                print(f"文件夹复制完成！")
            except Exception as e:
                bug_folder_path = bug_z
                print(f"发生错误: {e}\n,创建文件夹: {bug_folder_path}")
        else:
            os.makedirs(bug_folder_path, exist_ok=True)

        if bug_folder_path != bug_z:
            # 创建bug快捷方式
            url = f"https://bugzilla.unisoc.com/bugzilla/show_bug.cgi?id={bug_id}"
            shortcut_path = os.path.join(bug_folder_path, "Bug " + bug_title + '.url')
            print(f"创建url快捷方式: {shortcut_path}\n")
            create_url_shortcut(url, shortcut_path)

        # 创建附件文件夹
        attachment_folder = os.path.join(bug_folder_path, 'Attachements')
        if os.path.exists(attachment_folder):
           shutil.rmtree(attachment_folder)
        os.makedirs(attachment_folder, exist_ok=True)
        # print(f"已创建附件文件夹: {attachment_folder}")

        # 创建附件快捷方式
        shortcut_path = os.path.join(attachment_folder, str(bug_id) + '.url')
        print(f"创建url快捷方式: {shortcut_path}\n")
        create_url_shortcut(path_url, shortcut_path)
        
        # 调用 rayfile-c_cmd.exe 下载附件
        print(f"下载到附件中......: {attachment_folder}")
        download_with_rayfile(attachment_folder, path)

    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':


    try:
        root = tk.Tk()
        root.withdraw()
        bug_id_clipboard = root.clipboard_get().strip()
    except Exception:
        bug_id_clipboard = ""
    # 显示剪贴板内容作为 input 的默认值，允许用户编辑
    # 剪贴板内容太长只显示前10个字符
    display_clipboard = (bug_id_clipboard[:20] + "..." if len(bug_id_clipboard) > 20 else bug_id_clipboard)
    bug_id = input(f"请输入 Bug ID (默认: {BASE_BUGID} 剪贴板: {display_clipboard}): ").strip()
    bug_id = bug_id or (bug_id_clipboard if len(bug_id_clipboard) < 20 else BASE_BUGID)

    bugid_url = bug_url + "/" + bug_id
    bugcom_url = bug_url + "/" + bug_id + "/comment"

    # base_path = input("请输入要存储文件夹的基础路径: ")
    base_path = load_paths()
    # 提供路径列表给用户选择
    print("请选择一个路径（输入序号或自行输入路径）：")
    for idx, path in enumerate(base_path, 1):
        print(f"{idx}. {path}")
    # 获取用户输入
    user_input = input("请输入路径的序号或直接输入路径：").strip()
    # 如果输入的是数字，选择对应路径
    if user_input.isdigit():
        choice = int(user_input)
        if 1 <= choice <= len(base_path):
            base_path = base_path[choice - 1]
        else:
            print("无效的选择，使用默认路径。")
            base_path = BASE_PATH
    else:
        # 如果用户输入路径，直接使用用户输入的路径
        # ...用户输入路径后...load_paths
        if user_input and user_input not in base_path:
            base_path.append(user_input)
            save_paths(base_path)
        base_path = user_input or BASE_PATH

    base_path = base_path.strip() or BASE_PATH
    # 打印最终选择的路径
    print(f"最终选择的路径是：{base_path}")
    main(bug_id, base_path)
