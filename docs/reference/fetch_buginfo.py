import shutil
import os
import requests
from bs4 import BeautifulSoup
import shutil
import win32com.client
import urllib.parse
import re


paths = [
    r"E:\08_Bug",    # PATCH1
    r"E:\08_Bug\CQ",    # PATCH2
    r"E:\08_Bug\Task",    # PATCH3
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
    r"F:\PD认证\S51CUBE",
    r"F:\PD认证\XUNRUI",
    r"F:\PD认证\SPROCOMM"
]

index = 2
BASE_PATH = paths[index-1]
BASE_BUGID = "SPCSS01504817 "

# FOR TEST
session = requests.Session()
src_folder = r"E:\08_Bug\TEST"
dst_folder = r"E:\08_Bug\TEST\TEMP"
FTP_PATH = r"\\shnas02\CustomerData\消费电子业务管理部\huaqin_BD2\FTPDATA\2024-12\SPCSS01439883" 
BUG_PATH = r"E:\08_Bug\TEST\2854956 – (SPCSS01439883) [UMS9230E][HUAQIN_BD2][SL7509][15368][Other]【欧盟认证】【Type-C】【C3Z】TD 4.5.1 DRP Connect Sink Test测试fail" 

cookie_str = "Bugzilla_login=21689; DEFAULTFORMAT=advanced; VERSION-DAPS_DEV=unspecified; Bugzilla_logincookie=OTTLYLcTK6; LASTORDER=short_desc%20DESC%2Cbug_status%2Cchangeddate%20DESC%2Cpriority%2Cbug_severity; TUI=history_query=1&people_query=1&information_query=0&custom_search_query=1&custom_search_advanced=0&expert_fields=0&attachment_text_field=0; AlteonP=AT8kQJ4XHQo7ZvllUYnICA$$"

cookies = {
    "time-summary-dates": "2022-04-01%3B2022-09-30",
    "VERSION-QogirL6_ANDROID14_MAIN": "unspecified",
    "VERSION-UMS312_ANDROID14_MAIN": "unspecified",
    "VERSION-DAPS_DEV": "unspecified",
    "DEFAULTFORMAT": "advanced",
    "VERSION-IEBU_PWS_UIS7885_Android13": "unspecified",
    "Bugzilla_login": "21689",
    "Bugzilla_logincookie": "eQITA47U2j",
    "LASTORDER": "short_desc%20DESC%2Cbug_status%2Cchangeddate%20DESC%2Cpriority%2Cbug_severity",
    "TUI": "attachment_text_field=0&search_description=1&history_query=1&people_query=1&information_query=1&custom_search_query=1&custom_search_advanced=0&expert_fields=1",
    "invalidate_session": "false",
    "j_username": "Xianjun.Zeng",
    "sess": "70CF7C4FA0050875796FC1335E2D03CF",
    "ajs_anonymous_id": "9cb56d91-70f7-45e6-817e-dc2daafd268d",
    "LtpaToken": "AAECAzY2M0M4RjBDNjYzQ0UzNkNDTj1YaWFuanVuIFplbmcvTz1TcHJlYWR0cnVtilFMxPI1In5Ak3SXpTET6NiPzlI=",
    "AlteonP": "AaBeT54XHQoZuAUnX58XMg$$"
}

reset_url = "https://bugzilla.unisoc.com/bugzilla/reset"
bug_url = "https://bugzilla.unisoc.com/bugzilla/reset"+"/bug"
bugid_url = bug_url + "/" + bug_id
login_data = {
    "username": "Xianjun.Zeng@unisoc.com",  # 填写用户名
    "password": "****."  # 填写密码
}

invalid_chars = r'[<>:"/\\|?*]'


def login_bugzila():
    print("页面需要登录")
    response = session.post(login_url, data=login_data)
    """ 抓取 Bug 页面，提取标题和附件路径 """
    if response.status_code != 200:
            raise Exception(f"无法访问页面，状态码：{response.status_code}")
    print(f"Debug: Parsed response = {response}")
    soup = BeautifulSoup(response.content, 'html.parser')
    print(f"Debug: Parsed soup = {soup}")

def handle_cooke():
    # URL 解码
    #cookie_str_decoded = urllib.parse.unquote(cookie_str)

    # 将每个 `key=value` 组合按 `;` 分割
    cookie_items = cookie_str.split(';')

    # 转化为字典

    cookies = {}
    for item in cookie_items:
        item = item.strip()  # 去除多余的空格
        if '=' in item:  # 仅处理包含 '=' 的条目
            key, value = item.split('=', 1)  # 分割 key 和 value
            cookies[key.strip()] = value.strip()  # 去掉多余的空格并存入字典

    # 输出字典
    # print(cookies)
    return cookies

    
def create_url_shortcut(url, shortcut_path):
    print(f"快捷方式创建: {shortcut_path}")
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
    
    print(f"快捷方式已创建: {shortcut_path}")
    
def create_lnk_shortcut(target_path, shortcut_path):
    """ 创建快捷方式 """
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target_path
    shortcut.WorkingDirectory = os.path.dirname(target_path)
    shortcut.save()

def fetch_bug_info(url):
    """ 抓取 Bug 页面，提取标题和附件路径 """
    cookies = handle_cooke()
    response = requests.get(url, cookies=cookies)
    if response.status_code != 200:
        raise Exception(f"无法访问页面，状态码：{response.status_code}")
    # print(f"Debug: Parsed response = {response}")
    soup = BeautifulSoup(response.content, 'html.parser')
    # print(f"Debug: Parsed soup = {soup}")

    return fetch_path_info(soup)

def fetch_path_info(soup):
    # 提取 Bug 标题
    title = soup.title.string if soup.title else "No title found"
    if title:
        print("Title of the page:", title)
    else:
        print("Failed to retrieve the webpage, status code:", response.status_code)

    # 找到所有的 <div> 标签
    divs = soup.find_all('div')
    # print(f"Debug: Parsed divs = {divs}")

    # 使用正则表达式来查找包含目标路径的文本
    target_path_pattern =  r"或使用快捷链接下载（此链接仅提供下载功能，仅供展锐员工在公司网络进行下载操作）: \s*(\\.*)\s*"

    # 遍历每一个 <div> 标签，检查其中的文本是否匹配目标路径
    for div in divs:
        # 获取 <div> 中的纯文本
        div_text = div.get_text()
        # 使用正则表达式来检查文本中是否包含目标路径
        match = re.search(target_path_pattern, div_text, re.MULTILINE)
        if match:
            # 输出提取到的路径
            print("提取的路径:", match.group(1))
            # print(div_text)
            break
    else:
        print("没有找到包含目标路径的 <div> 标签")
    

    #return title, match.group(1)
    return title

def check_path(path):
    if len(path) > 260:
        print("路径太长，请缩短路径")
    
    return re.sub(r'[\/:*?"<>|]', '_', path)

def main(bug_id, base_path):
    try:
        # 获取 bug 页面信息
        url = f"https://bugzilla.unisoc.com/bugzilla/show_bug.cgi?id={bug_id}"
        ftp_path = 0
        bug_title= fetch_bug_info(url)
        print(f"title: {bug_title}, ftp: {ftp_path}")
        # 清除路径中的非法字符
        bug_title = re.sub(invalid_chars, "_", bug_title)
        # 创建文件夹路径
        bug_folder_path = os.path.join(BASE_PATH, "Bug " + bug_title)
        print(f"创建文件夹: {bug_folder_path}\n")


        bug_z = os.path.join(BASE_PATH, "Bug Z")
        # 检查目标文件夹是否存在，如果存在则拷贝
        if os.path.exists(bug_z):
            print(f"目标文件夹 {bug_z} 已存在")
            # 复制文件夹及其内容            
            print(f"正在复制 {src_folder} 到 {bug_folder_path}...\n")
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
        shortcut_path = os.path.join(attachment_folder, str(bug_id) + '.lnk')
        print(f"创建lnk快捷方式: {shortcut_path}")
        create_lnk_shortcut(ftp_path, shortcut_path)

        # 从 FTP 路径复制文件到附件文件夹（这里仅为模拟）
        print(f"下载到附件中......: {attachment_folder}")
        shutil.copytree(ftp_path, attachment_folder, dirs_exist_ok=True)

        

    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':


    bug_id = ""
    # bug_id = input("请输入 Bug ID: ")
    bug_id = bug_id.strip() or BASE_BUGID
    # base_path = input("请输入要存储文件夹的基础路径: ")
    base_path = ""
    path = base_path.strip() or BASE_PATH
    main(bug_id, base_path)
