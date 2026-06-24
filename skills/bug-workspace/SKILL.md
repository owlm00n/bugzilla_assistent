---
name: bug-workspace
description: Bug工作区创建 & 坐标 - 自动生成文件夹、.url快捷方式、Bug Z模板、路径历史、快速打开、编排附件下载
version: "2.0"
tags: [bugzilla, workspace, rayfile, download, shortcut, orchestration]
---

# Bug工作区

根据Bug信息自动创建工作区——生成文件夹、.url 快捷方式、Bug 摘要文件、Bug Z 模板复制、路径历史管理、快速打开，并通过编排调用 bug-logs 完成附件下载。复刻 original_source.py 的核心工作流。

## 触发条件

- 用户说"创建工作区"、"下载附件"、"生成下载命令"
- 用户说"给Bug XXX创建工作区"、"下载Bug XXX的日志"
- 用户查询 unisoc Bug 后需要下载日志附件
- 使用 MCP `bug_workspace` 工具

## 工作流程

1. 获取 Bug 信息（跨 Skill 调用 bug-core）
2. 根据 Bug ID + Summary 生成文件夹名: `[BugID][Summary前30字符]`
3. 在指定路径创建文件夹
4. 复制 Bug Z 模板（若存在）
5. 创建 .url 快捷方式（链接到 Bug 页面）
6. 生成 bug_summary.txt（所有 Bug 字段摘要）
7. 调用 bug-logs 下载附件（UNC 或 rayfile）

```
用户: 给 Bug 219041 创建工作区并下载附件
AI:
  1. 获取 Bug 219041 信息
  2. 生成文件夹: E:\08_Bug\[219041][USB enumeration timeout on XHCI...]
  3. 复制 Bug Z 模板
  4. 创建快捷方式: Bug_219041.url
  5. 生成摘要: bug_summary.txt
  6. 调用 bug-logs 下载附件（检测类型→下载→规范化）
  7. ✅ 工作区创建完成！
```

## 核心功能

### 文件夹命名

格式: `[BugID][Summary前30字符]`
- 自动清除非法文件名字符（`<>:"/\|?*`）
- 超长名称自动截断（保留头尾）

### rayfile 下载命令 (v2.0 已修正)

生成完整的 rayfile-c_cmd.exe 命令（匹配原工具精确参数）：
```
rayfile-c_cmd.exe -a unitrans.unisoc.com -p 2443 -ssl -u ctd01 -w <password> -o download -d "<local_dir>" -s "<ftp_path>" -space_id 2 -gr 31240 -file-update append
```

- FTP 凭证从 `config/bugzilla_instances.json` 的 unisoc 实例读取
- 返回 dict 结构：`{"command": "完整命令字符串", "args": ["参数列表"]}`
- 自动处理 UNC → FTP 路径转换

### Bug Z 模板复制 (NEW v2.0)

`copy_bug_z_template()` — 若 `{base_path}/Bug Z` 目录存在，使用 `shutil.copytree` 复制到工作区。冲突时自动合并（`dirs_exist_ok=True`）。

### 路径历史管理 (NEW v2.0)

| 函数 | 说明 |
|------|------|
| `load_workspace_paths()` | 从 `config/paths.json` 加载路径历史（15 个默认路径） |
| `save_workspace_paths(paths)` | 保存路径历史，自动去重保持顺序 |
| `open_workspace_path(path)` | `os.startfile()` 在资源管理器中打开工作区 |

### 快捷方式

创建 Windows .url 文件（`[InternetShortcut]` 格式）：
```ini
[InternetShortcut]
URL=https://bugzilla.unisoc.com/bugzilla/show_bug.cgi?id=219041
IconFile=https://bugzilla.unisoc.com/bugzilla/show_bug.cgi?id=219041
IconIndex=0
```
- 路径 >200 字符自动简化为 `Bug.url`

### 编排下载 (NEW v2.0)

`generate_workspace_with_download()` — 完整工作流编排：
1. 创建工作区文件夹
2. 复制 Bug Z 模板
3. 创建 .url 快捷方式 + bug_summary.txt
4. 调用 bug-logs `download_bug_attachments()` 下载附件
5. 返回完整结果

### Bug 摘要文件

生成 `bug_summary.txt`，包含完整的 Bug 字段信息（ID/Severity/Status/Product/Assignee/Attachment等）。

## MCP Server 工具

### bug_workspace

**基础模式（仅创建文件夹）**：
```json
{
  "tool": "bug_workspace",
  "args": {
    "bug_id": 219041,
    "bugzilla_url": "https://bugzilla.unisoc.com/bugzilla",
    "base_path": "E:\\08_Bug"
  }
}
```

**下载模式（NEW v2.0 — 创建+下载）**：
```json
{
  "tool": "bug_workspace",
  "args": {
    "bug_id": 219041,
    "bugzilla_url": "https://bugzilla.unisoc.com/bugzilla",
    "base_path": "E:\\08_Bug",
    "download": true,
    "refresh": false,
    "normalize": "copy_new",
    "copy_bug_z": true
  }
}
```

**参数说明**：
| 参数 | 类型 | 默认 | 说明 |
|------|------|:---:|------|
| `download` | bool | `false` | 是否下载附件 |
| `refresh` | bool | `false` | 是否重新下载（清空已有） |
| `normalize` | str | `"copy_new"` | 规范化模式：off / move / copy_new |
| `copy_bug_z` | bool | `true` | 是否复制 Bug Z 模板 |

返回：
```json
{
  "success": true,
  "folder": {
    "folder_name": "[219041][USB enumeration timeout on X]",
    "folder_path": "E:\\08_Bug\\[219041]...\\",
    "created": true,
    "shortcut_file": "E:\\08_Bug\\[219041]...\\Bug_219041.url",
    "summary_file": "E:\\08_Bug\\[219041]...\\bug_summary.txt"
  },
  "download": {
    "success": true,
    "attachment_type": "unc",
    "files_copied": 45
  },
  "bug_z_copied": true,
  "errors": []
}
```

## 工作区目录结构

```
E:\08_Bug\[219041] USB enumeration timeout on XHCI\
├── Bug Z/                        ← Bug Z 模板（可选）
│   ├── template.txt
│   └── SubFolder/
├── Attachements/                 ← 下载的附件
│   ├── modem_log.zip
│   └── syslog.txt
├── Bug_219041.url                ← Bugzilla 快捷方式
└── bug_summary.txt               ← Bug 摘要文件
```

## 相关 Skill

- **bug-core**: Bug 查询核心（提供 Bug 信息和 `format_bug_summary()`）
- **bug-logs**: 日志目录列表 + 附件下载（被 bug-workspace 编排调用）

## 代码位置

| 文件 | 说明 |
|------|------|
| `bug_workspace.py` | 工作区核心+编排模块（~450行） |
| `config/bugzilla_instances.json` | 实例配置（含 default_workspace/FTP凭证） |
| `config/paths.json` | 工作区路径历史（15 个默认路径） |
| `tests/test_workspace.py` | 工作区测试套件（57用例） |
