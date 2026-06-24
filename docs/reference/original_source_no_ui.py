# Bugzilla 工具原始源码（无UI脚本版）

> 来源：Master 提供的 fetch_buginfo_by_API_UI.py（无UI版本）
> 对比：UI版见 reference/original_source.py

```python
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

# ... (完整源码见Master原始输入)

# 核心API配置
rest_url = "https://bugzilla.unisoc.com/bugzilla/rest"
bug_url = "https://bugzilla.unisoc.com/bugzilla/rest/bug"
api_key = "GzzXtl8A0nU5M8HmTbnYYt0Yapc3skDCRfI0vmaa"
user = "Xianjun.Zeng@unisoc.com"

# unitrans FTP配置
# rayfile-c_cmd.exe -a unitrans.unisoc.com -p 2443 -ssl -u ctd01 -w ctd01@abAB
# 注意：此版本无 -file-update append 参数
```

## 与UI版的关键差异

| 差异点 | UI版 | 无UI脚本版 |
|--------|------|-----------|
| 交互方式 | Tkinter窗口 | 命令行 input() |
| Bug ID输入 | 剪贴板自动填充+手动编辑 | 剪贴板默认值+input() |
| 路径选择 | 下拉框ComboBox | 序号选择列表 |
| 附件下载模式 | append增量下载 | 每次删除重建（无append） |
| 附件目录规范化 | normalize_downloaded_folder() | 无 |
| 日志输出 | Tkinter Text面板+控制台 | 纯print |
| NORMALIZE_ACTION | copy_new/move/off | 不存在 |
| REFRESH_ATTACHMENTS | 可控开关 | 始终刷新（shutil.rmtree） |
| Bug Z模板复制 | 有 | 有（逻辑相同） |
| 快捷方式创建 | .url文件 | .url文件（逻辑相同） |

## 核心流程（与UI版一致）

1. fetch_bug() → Bugzilla REST API获取Bug信息
2. fetch_summary() → 提取id/alias/summary
3. fetch_path() → 从评论提取FTP路径+快捷链接
4. main() → 创建文件夹+Bug Z模板+快捷方式+下载附件
5. download_with_rayfile() → rayfile-c_cmd.exe下载
