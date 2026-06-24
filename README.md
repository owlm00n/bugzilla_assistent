# arkclaw-skills

USB/PD 驱动开发 AI 辅助 Skill 集合

## 技能列表

| Skill | 路径 | 功能 |
|-------|------|------|
| **bug-core** | `skills/bug-core/` | Bugzilla Bug 查询核心 — REST API / 搜索 / MCP Server |
| **bug-logs** | `skills/bug-logs/` | 日志目录列表 + 附件下载（UNC/FTP 双通道） |
| **bug-workspace** | `skills/bug-workspace/` | 工作区创建 + 快捷方式 + 编排下载 |
| **log-analyzer** | `skills/log-analyzer/` | 角色感知日志分析 + 异常检测 + 交互式查看器 |
| **keyword-vault** | `skills/keyword-vault/` | 关键词收纳系统 — 方向管理 + 可视化 CRUD |
| **protocol-parser** | `skills/protocol-parser/` | PD/USB 协议解析 + 可视化时序图 |
| **code-generator** | `skills/code-generator/` | 分级调试代码生成（L1/L2/L3） |
| **feishu-integration** | `skills/feishu-integration/` | 飞书 IM Bot 集成 |
| **bug-assistant** | `skills/bug-assistant/` | 重定向 stub → bug-core/bug-logs/bug-workspace |

## 目录结构

```
arkclaw-skills/
├── skills/          # 9 个 AI Skill
├── knowledge/       # 知识库（PD/USB协议、故障案例、提示词模板）
├── data/            # 示例数据（脱敏 log 文件）
├── docs/            # 功能说明书、效果数据报告、变更日志
└── README.md
```

## 环境要求

| 条件 | 说明 |
|------|------|
| Python 3.10+ | 所有 Skill 运行环境 |
| Windows | UNC 目录列表 + log 下载功能 |
| 内网（可选） | 访问 unisoc Bugzilla + 共享目录需要办公网 |

## 快速开始

```bash
# 安装依赖
pip install httpx requests

# 测试 bug-core
cd skills/bug-core && python tests/test_core.py

# 测试 bug-logs
cd skills/bug-logs && python tests/test_logs.py

# 测试 bug-workspace
cd skills/bug-workspace && python tests/test_workspace.py
```

## 配置

编辑 `skills/bug-core/config/bugzilla_instances.json` 填入自己的 API key 和实例信息。

## 文档

- `docs/feature-manual.md` — 功能说明书
- `docs/effect-data-report.md` — 效果数据报告
- `docs/CHANGELOG.md` — 变更日志
