---
name: bug-logs
description: Bug日志目录查询 & 附件下载 - unisoc结构化评论解析、UNC+FTP双通道日志目录列表、智能附件类型识别与下载
version: "2.0"
tags: [bugzilla, log-directory, structured-parsing, unc, ftp, download, rayfile]
---

# Bug日志目录查询 & 附件下载

解析 unisoc Bugzilla 结构化 Bug 报告格式（19字段模板），通过 UNC+FTP 双通道列出日志目录内容；智能识别两种附件类型（UNC 内部附件 / rayfile SPCSS 客户附件）并自动下载。

## 触发条件

- 用户说"列出日志目录"、"查看日志文件"、"Bug的log在哪"
- 用户说"下载附件"、"下载日志"、"下载Bug附件"
- 用户查询 unisoc Bug 且提到日志、附件、下载
- 用户说"查看Bug XXX的日志"

## 工作流程

### 流程1：Unisoc 日志目录查询

1. 用户输入 unisoc Bug ID
2. 调用 `fetch_bug_with_logs()` 获取 Bug 信息（跨 Skill 调用 bug-core）
3. 自动解析 Comment #0 的 19 字段结构化模板
4. 提取 LogPath 后列出日志目录内容
5. AI 根据文件名、修改时间、Bug 上下文识别相关日志

```
用户: 查 unisoc Bug 3410487
AI:
  1. 调用 fetch_bug_with_logs("3410487", "unisoc")
  2. 获取 Bug 基本信息（标题/状态/模块）
  3. 解析 Comment #0 结构化字段:
     ├ LogPath: \\shnas02\TestLogs\PSST\...
     ├ LogType: Default
     ├ OccurTime: 2026-04-15 14:30
     └ VersionPath: SPRDROID...
  4. 列出 LogPath 目录:
     ├ file: modem_log_20260415.zip (15.2 MB)
     ├ file: syslog_20260415.txt (3.1 MB)
     ├ dir:  diag_logs/
     └ dir:  crash_dumps/
  5. AI 根据 OccurTime + Bug 上下文 筛选相关日志:
     → "modem_log_20260415.zip 和 syslog_20260415.txt 日期匹配，可能是目标日志"
```

### 流程2：智能附件下载（新增 v2.0）

1. 调用 `detect_attachment_type()` 自动识别附件类型
2. 创建 `Attachements/` 目录
3. 按类型下载：
   - **Type 2 (UNC)**: 测试工程师附件，通过 `shutil.copy2` 从 UNC 路径复制
   - **Type 1 (rayfile)**: SPCSS 客户附件，通过 `rayfile-c_cmd.exe` 子进程从 FTP 下载
4. 调用 `normalize_downloaded_folder()` 规范化目录结构

```
用户: 下载 Bug 219041 的附件到 E:\08_Bug
AI:
  1. detect_attachment_type("219041", "unisoc")
     → type: "unc", source: \\shnas02\TestLogs\...
  2. 创建 E:\08_Bug\[219041]\Attachements\
  3. 从 UNC 复制 45 个文件 (320 MB)
  4. normalize: copy_new 模式
  5. ✅ 完成！文件已复制到工作区
```

## 核心功能

### 结构化评论解析

解析 unisoc Bugzilla Comment #0 的 19 字段模板格式：

```
[1.Severity]:Major
[14.Logpath]:
  LogName:
  LogPath:\\shnas02\TestLogs\PSST\...
  Log Servers:
    External:\\shnas02\TestLogs
    Internal:\\logserver\TestData
    FTP:ftp://unitrans.unisoc.com/TestLogs/...
[15.Logtype]:Default
[16.Occur Time]:2026-05-15 10:30
[19.Version Path]:SPRDROID...
```

**提取字段**:
- 7 个头部字段（严重级别、外部条件、出现概率等）
- 19 个编号字段
- LogPath/LogName/LogServers（内外部URL）
- LogType/OccurTime/VersionPath

### 日志目录列表

支持双通道列出日志目录内容：

| 通道 | 适用场景 | 技术 |
|------|---------|------|
| **UNC** | Windows 办公网，直接访问 `\\server\share` | `os.scandir()` |
| **FTP** | UNC 不可达时 fallback | `ftplib.FTP_TLS` |

返回结构：
```json
{
  "path": "\\\\shnas02\\TestLogs",
  "method": "unc",
  "accessible": true,
  "entries": [
    {"name": "log_20260515.zip", "type": "file", "size": 1234567, "modified": ""},
    {"name": "PSST", "type": "dir", "size": 0, "modified": ""}
  ],
  "files": ["log_20260515.zip"],
  "subdirs": ["PSST"],
  "error": null
}
```

### 智能附件类型检测 (NEW v2.0)

`detect_attachment_type()` 自动判断 Bug 的附件类型：

| 类型 | 来源 | 检测依据 | 下载方式 |
|:---:|------|---------|---------|
| **Type 2 (UNC)** | 测试工程师 | Comment #0 含 `[14.Logpath]` + 有效 UNC 路径 | `shutil.copy2` 直接复制 |
| **Type 1 (rayfile)** | SPCSS 客户 | Comment #0 含 "下载附件:" FTP 路径 | `rayfile-c_cmd.exe` 子进程 |
| **none** | 无附件 | 无上述格式 | 返回错误信息 |

### 附件下载 (NEW v2.0)

| 函数 | 说明 |
|------|------|
| `download_from_unc_path(unc_path, dest_dir)` | 通过 UNC 路径复制日志文件 |
| `download_from_rayfile(ftp_path, dest_dir, instance_config)` | 通过 rayfile 从 FTP 下载 SPCSS 附件 |
| `download_bug_attachments(bug_id, dest_dir, instance, refresh, normalize_action)` | **统一入口**：检测→创建目录→下载→规范化 |
| `normalize_downloaded_folder(attachment_folder, bug_id, action)` | 规范化目录结构（off/move/copy_new） |
| `copy_missing(src, dst)` | 递归复制，仅复制目标不存在的文件 |

### 组合查询 (fetch_bug_with_logs)

一次调用完成：Bug 信息获取 → 结构化解析 → 日志目录列表。返回标准 bug-core 结果 + `structured_fields` + `log_directory`。

> 此函数跨 Skill 调用 bug-core 的 `fetch_bug_rest()`，使用三级降级加载。

## MCP Server 工具

### bug_logs

获取 Bug 的日志目录列表或下载附件：

**列表模式（默认）**：
```json
{
  "tool": "bug_logs",
  "args": {
    "bug_id": 3410487,
    "bugzilla_url": "https://bugzilla.unisoc.com/bugzilla"
  }
}
```

**下载模式（NEW v2.0）**：
```json
{
  "tool": "bug_logs",
  "args": {
    "bug_id": 219041,
    "bugzilla_url": "https://bugzilla.unisoc.com/bugzilla",
    "download": true,
    "dest_dir": "E:\\08_Bug\\[219041]\\",
    "refresh": false,
    "normalize": "copy_new"
  }
}
```

## 相关 Skill

- **bug-core**: Bug 查询核心（提供 Bug 信息查询 API）
- **bug-workspace**: 工作区创建（调用 bug-logs 下载附件）

## 代码位置

| 文件 | 说明 |
|------|------|
| `bug_logs.py` | 日志+下载核心模块（~700行） |
| `config/bugzilla_instances.json` | 实例配置（含FTP凭证） |
| `comment_0.txt` | 测试用结构化评论样本 |
| `tests/test_logs.py` | 日志测试套件（51用例） |
