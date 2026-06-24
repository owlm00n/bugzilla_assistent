---
name: bug-assistant
description: [已拆分] Bugzilla Bug智能助手 → bug-core / bug-logs / bug-workspace
version: "1.2"
tags: [bugzilla, deprecated, redirect]
---

# Bug智能助手（已拆分）

> **注意**: 此 Skill 已于 2026-06-05 拆分为 3 个独立 Skill。请使用新 Skill：

## 新 Skill 结构

| Skill | 功能 | 导入 |
|-------|------|------|
| **bug-core** | Bug 查询核心（REST API / 离线 / 搜索 / 解析） | `from bug_core import fetch_bug_rest, search_bugs, ...` |
| **bug-logs** | 日志目录列表 + unisoc 结构化评论解析 | `from bug_logs import list_log_directory, parse_unisoc_structured_fields, ...` |
| **bug-workspace** | 工作区创建 + rayfile 命令 + 快捷方式 | `from bug_workspace import generate_workspace, get_rayfile_command, ...` |

## MCP Server

统一 MCP Server 位于 `bug-core/mcp-server/server.py`，提供 5 个工具：
- `bug_info`, `bug_comments`, `bugs_search` → bug-core
- `bug_workspace` → bug-workspace
- `bug_logs` → bug-logs

## 拆分原因

原 `bug_assistant.py`（~984行）包含 3 个正交功能群：
- **A 群**: Bug 查询/解析/搜索（~260行）
- **B 群**: 日志目录列表 + 结构化解析（~370行）
- **C 群**: 工作区创建 + rayfile（~230行）

B 和 C 之间零函数调用，仅通过配置共享耦合。拆分为独立 Skill 提高模块化和独立部署能力。

## 迁移指南

| 旧导入 (`bug_assistant`) | 新导入 |
|--------------------------|--------|
| `from bug_assistant import fetch_bug_rest` | `from bug_core import fetch_bug_rest` |
| `from bug_assistant import search_bugs` | `from bug_core import search_bugs` |
| `from bug_assistant import format_bug_summary` | `from bug_core import format_bug_summary` |
| `from bug_assistant import list_log_directory` | `from bug_logs import list_log_directory` |
| `from bug_assistant import parse_unisoc_structured_fields` | `from bug_logs import parse_unisoc_structured_fields` |
| `from bug_assistant import fetch_bug_with_logs` | `from bug_logs import fetch_bug_with_logs` |
| `from bug_assistant import generate_workspace` | `from bug_workspace import generate_workspace` |
| `from bug_assistant import get_rayfile_command` | `from bug_workspace import get_rayfile_command` |
