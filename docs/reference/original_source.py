# Bugzilla 工具原始源码

> 来源：Master 提供的 fetch_buginfo_by_API_UI.py
> UI截图：reference/ui_screenshot.jpg

```python
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

#打包命令 pyinstaller --onedir --windowed "D:\05_Code\python\bugzila\fetch_buginfo_by_API_UI.py"
#pyinstaller --onedir --windowed --icon="D:\05_Code\python\bugzila\favicon.ico" --add-data="D:\05_Code\python\bugzila\paths.json:." "D:\05_Code\python\bugzila\fetch_buginfo_by_API_UI.py" --noconfirm

if getattr(sys, 'frozen', False):
    paths_file = os.path.join(sys._MEIPASS, 'paths.json')
else:
    paths_file = "paths.json"

BASE_PATH = "下拉选择路径或输入路径(自动存储)"
paths = [
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
    r"F:\PD认证\SPROCOMM"
]

# ... (完整源码见 Master 原始输入，此处仅存档关键结构)

# 核心API配置
rest_url = "https://bugzilla.unisoc.com/bugzilla/rest"
bug_url = "https://bugzilla.unisoc.com/bugzilla/rest/bug"
api_key = "GzzXtl8A0nU5M8HmTbnYYt0Yapc3skDCRfI0vmaa"
user = "Xianjun.Zeng@unisoc.com"

# unitrans FTP配置
# rayfile-c_cmd.exe -a unitrans.unisoc.com -p 2443 -ssl -u ctd01 -w ctd01@abAB
```

> ⚠️ 注意：api_key 和密码已包含在原始代码中，存档时保留但需注意安全。
> 适配到Claw时应使用配置文件或环境变量管理敏感信息。
