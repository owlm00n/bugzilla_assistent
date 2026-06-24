# 📝 变更日志

## [2026-06-05]

### bug-logs & bug-workspace 下载功能重构 (v2.0)
- feat(bug-logs): 新增 `detect_attachment_type()` — 智能识别 UNC 内部附件 vs rayfile SPCSS 客户附件 [Claude Code]
- feat(bug-logs): 新增 `download_from_unc_path()` — Windows `shutil.copy2` 从 UNC 路径直接复制日志 [Claude Code]
- feat(bug-logs): 新增 `download_from_rayfile()` — `rayfile-c_cmd.exe` 子进程从 FTP 下载 SPCSS 附件 [Claude Code]
- feat(bug-logs): 新增 `normalize_downloaded_folder()` — 3 种目录规范化模式（off/move/copy_new）[Claude Code]
- feat(bug-logs): 新增 `copy_missing()` — 递归复制辅助函数，仅复制目标不存在的文件 [Claude Code]
- feat(bug-logs): 新增 `download_bug_attachments()` — 统一附件下载入口（检测→下载→规范化）[Claude Code]
- feat(bug-workspace): 新增 `copy_bug_z_template()` — 自动复制 Bug Z 模板到工作区 [Claude Code]
- feat(bug-workspace): 新增 `create_url_shortcut()` — `[InternetShortcut]` 格式 .url 文件，>200 字符自动简化 [Claude Code]
- feat(bug-workspace): 新增 `load/save_workspace_paths()` — 15 个默认工作区路径，支持增删去重 [Claude Code]
- feat(bug-workspace): 新增 `open_workspace_path()` — `os.startfile()` 一键打开工作区 [Claude Code]
- feat(bug-workspace): 新增 `generate_workspace_with_download()` — 创建+模板+快捷方式+下载一站式编排 [Claude Code]
- fix(bug-workspace): 修正 `get_rayfile_command()` 参数 — `-remote`/`-local` → `-o download -d` `-s` [Claude Code]
- feat(bug-workspace): 新增 `config/paths.json` — 15 个默认工作区路径 [Claude Code]
- feat(mcp-server): `bug_workspace` 工具新增 download/refresh/normalize/copy_bug_z 参数 [Claude Code]
- feat(mcp-server): `bug_logs` 工具新增 download/dest_dir/refresh/normalize 参数 [Claude Code]
- fix(mcp-server): 修复 `bug_workspace` 中 `instance_name` 未定义 bug [Claude Code]
- test(bug-logs): 新增 GROUP 9 — 19 用例（detect_attachment_type / download_from_unc / normalize / download_bug_attachments）[Claude Code]
- test(bug-workspace): 新增 GROUP 9 — 27 用例（copy_bug_z_template / url_shortcut / paths / orchestration）[Claude Code]
- test: 总计 136 用例 / 10 组 / 100% 通过（51+57+63=171 文件行）[Claude Code]
- docs(bug-logs): SKILL.md v2.0 — 新增下载能力、附件类型检测、MCP 下载参数 [Claude Code]
- docs(bug-workspace): SKILL.md v2.0 — 新增编排功能、Bug Z 模板、路径历史 [Claude Code]
- docs: feature-manual.md v1.5 — 模块2/3 更新下载与编排能力、测试覆盖更新 [Claude Code]
- docs: effect-data-report.md v1.4 — 数据更新（下载通道→实际下载、MCP工具能力、136用例）[Claude Code]

### bug-assistant 拆分为 3 个独立 Skill
- refactor: bug-assistant (~984行) 拆分为 bug-core / bug-logs / bug-workspace 三个独立 Skill [Claude Code]
- feat(bug-core): Bug 查询核心 — REST API / 离线 / 搜索 / 解析 / CLI / MCP Server (~320行) [Claude Code]
- feat(bug-logs): 日志目录列表 + unisoc 结构化评论解析 + fetch_bug_with_logs (~370行) [Claude Code]
- feat(bug-workspace): 工作区创建 + rayfile 命令 + 快捷方式 + 跨 Skill 导入 (~230行) [Claude Code]
- feat(mcp-server): 统一 MCP Server 从 3 个模块导入，5 个工具（bug_info / bug_comments / bugs_search / bug_workspace / bug_logs）[Claude Code]
- feat: 三级降级导入模式（try import → sys.path fallback → error），支持独立部署和联合使用 [Claude Code]
- test: 3 个独立测试套件（test_core.py 63 用例 / test_workspace.py 23 用例 / test_logs.py 32 用例），总计 118/118 通过 [Claude Code]
- docs: bug-assistant/SKILL.md 更新为 v1.2 重定向 stub，指向 3 个新 Skill [Claude Code]
- docs: bug-core/bug-logs/bug-workspace 各新增 SKILL.md [Claude Code]
- docs: 新增 skills/bug-logs/comment_0.txt — unisoc 19 字段结构化测试参考数据 [Claude Code]

### bug-assistant 新增日志目录功能
- feat(bug-assistant): 新增 `parse_unisoc_structured_fields()` — 解析 unisoc 19 字段结构化评论格式 [Claude Code]
- feat(bug-assistant): 新增 `list_log_directory()` — UNC+FTP 双通道目录列表 [Claude Code]
- feat(bug-assistant): 新增 `_try_unc_listdir()` — Windows os.scandir() UNC 目录访问 [Claude Code]
- feat(bug-assistant): 新增 `_try_ftp_listdir()` — ftplib.FTP_TLS FTP 目录 fallback [Claude Code]
- feat(bug-assistant): 新增 `fetch_bug_with_logs()` — Bug 信息+结构化解析+日志目录组合查询 [Claude Code]
- feat(mcp-server): 新增 `bug_logs` MCP 工具 — AI 可调用日志目录查询 [Claude Code]
- test: 新增 GROUP 8 测试组 — 22 个测试用例全部通过，总 118/118 [Claude Code]
- docs: 新增 tests/TEST_GUIDE.md — 测试工程师详细指南 [Claude Code]
- docs: 更新 SKILL.md v1.1 — 补充日志目录/结构化解析/新增 MCP 工具 [Claude Code]
- docs: 更新 feature-manual.md v1.3 — 模块1扩充日志目录功能 [Claude Code]
- docs: 更新 effect-data-report.md v1.2 — 新增日志目录定位效率数据 [Claude Code]

## [2026-06-02]

### 协作策略
- docs: COLLABORATION v4 — 开发平等 + 部署仅限核心平台 [OpenClaw]
- docs: COLLABORATION v3 — 所有 Agent 平等协作，去掉角色区分 [OpenClaw]
- docs: COLLABORATION v2 — 新增冲突管理、崩溃恢复、策略更新协议 [OpenClaw]
- docs: 新增 ONBOARD.md — 新 Agent 快速上手指南 [OpenClaw]
- docs: 新增 SESSION_STATE.md — 会话状态追踪 [OpenClaw]
- docs: 新增 HANDOVER.md — 项目交接文档 [OpenClaw]
- docs: 新增 memory-export.md — 记忆导出 [OpenClaw]
- docs: 更新 README.md — 完整目录结构 + 当前进度 [OpenClaw]

### 部署
- chore(deploy): 5 个自定义技能部署到 runtime [OpenClaw]
  - bug-assistant, code-generator, feishu-integration, log-analyzer, protocol-parser
- chore(deploy): 同步 runtime-backup/ [OpenClaw]

### 项目结构
- chore: 目录结构整理 v2 — workspace 非仓库，项目独立仓库 [OpenClaw]
- chore: 新增 runtime-backup/ — 运行时文件备份 [OpenClaw]
- chore: 清理仓库中的 OpenClaw 运行时文件 [OpenClaw]
- chore: 修复配置文件 symlink [OpenClaw]

### 记忆管理
- cleanup: 删除 v1 目录结构约定（已过时）[OpenClaw]
- store: 多 Agent 协作策略 v1 [OpenClaw]
- store: 目录结构约定 v2 [OpenClaw]
