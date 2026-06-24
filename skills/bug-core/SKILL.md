---
name: bug-core
description: Bugzilla Bug查询核心 - 多实例Bug信息查询、智能摘要、搜索、离线模式
version: "1.0"
tags: [bugzilla, bug, query, summary, search]
---

# Bug查询核心

查询Bugzilla Bug信息，生成智能摘要，支持多实例和多模式查询。

## 触发条件

- 用户输入 Bug ID（纯数字5位以上 或 SPCSS开头）
- 用户说"查Bug"、"Bug助手"、"Bug查询"、"查一下Bug"
- 用户粘贴Bug页面内容
- 用户上传文件并提及Bug相关关键词

## 工作流程

### 流程1：Bug ID查询（默认）

1. 用户输入Bug ID
2. 调用 REST API 获取Bug信息
3. 如果REST API失败，尝试 web_fetch 获取HTML页面
4. 生成智能摘要展示给用户
5. 提示用户上传附件或联动分析

### 流程2：手动输入解析

1. 用户粘贴Bug页面内容
2. 调用 parse_bug_from_text() 自动解析提取
3. 展示解析结果，确认后继续

### 流程3：web_fetch降级

当REST API不可用时：
1. 使用web_fetch获取Bug页面HTML
2. LLM从HTML中提取关键信息
3. 或使用 ?ctype=xml 获取结构化XML

## 实例切换

| 关键词 | Bugzilla实例 | URL |
|--------|------------|-----|
| kernel / 默认 | Linux Kernel | bugzilla.kernel.org |
| mozilla | Mozilla | bugzilla.mozilla.org |
| gnome | GNOME | bugzilla.gnome.org |
| unisoc | Unisoc内网 | bugzilla.unisoc.com（办公网） |
| local | 本地模拟数据 | sample_bugs.json |

## 离线模式

通过 `--offline` 参数或 `instance=local` 启用离线模式，无需网络连接即可查询模拟Bug数据。

```bash
# 列出所有本地Bug
python bug_core.py --list

# 查询指定Bug（离线模式）
python bug_core.py BUG-20261 local

# 全局启用离线
python bug_core.py BUG-20262 --offline
```

环境变量 `OFFLINE_MODE=1` 全局生效。

## 搜索功能

```python
from bug_core import search_bugs

# 按关键词搜索
results = search_bugs("pd")  # 搜索含"pd"的Bug

# 按严重度筛选
results = search_bugs(severity="critical")

# 同时使用
results = search_bugs("pd", severity="critical")
```

## MCP Server 工具

统一的 MCP Server 提供 5 个工具（位于 mcp-server/server.py）：

| 工具 | 功能 | 依赖模块 |
|------|------|---------|
| `bug_info` | 获取Bug详细信息 | bug-core |
| `bug_comments` | 获取Bug评论列表 | bug-core |
| `bugs_search` | 搜索Bug（quicksearch） | bug-core |
| `bug_workspace` | 创建工作区 | bug-workspace |
| `bug_logs` | 日志目录列表 | bug-logs |

## 相关 Skill

- **bug-logs**: 日志目录列表 + unisoc 结构化评论解析
- **bug-workspace**: 工作区创建 + rayfile 下载命令 + 快捷方式

## 代码位置

| 文件 | 说明 |
|------|------|
| `bug_core.py` | 核心模块（~320行） |
| `mcp-server/server.py` | 统一 MCP Server |
| `config/bugzilla_instances.json` | 实例配置 |
| `data/sample_bugs.json` | 离线模拟数据 |
| `tests/test_core.py` | 核心测试套件 |
