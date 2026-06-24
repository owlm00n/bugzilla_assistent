# Bugzilla Assistant — Claude Code 安装文档

> 版本: v1.0 | 日期: 2026-06-24

---

## 一、安装概述

将 Bugzilla Assistant 的 7 个 AI Skill（排除飞书集成）安装到 Claude Code，覆盖 Bug 查询、日志分析、协议解析、代码生成、关键词管理的完整研发闭环。

| Skill | 版本 | 功能 |
|-------|:---:|------|
| **bug-core** | v1.0 | Bugzilla Bug 查询核心 — 多实例 REST API、智能摘要、搜索、离线模式、MCP Server |
| **bug-logs** | v2.0 | 日志目录查询 & 附件下载 — UNC+FTP 双通道、智能附件类型识别 |
| **bug-workspace** | v2.0 | Bug 工作区创建 & 编排 — 文件夹生成、Bug Z 模板、快捷方式、附件下载编排 |
| **log-analyzer** | v2.1 | 角色感知日志分析 — 3 种角色画像、异常检测、交互式日志查看器 |
| **protocol-parser** | v3.0 | PD/USB/CC 协议智能解析与可视化 — AI 驱动、HTML 报告生成 |
| **code-generator** | v1.0 | 代码辅助生成 — 三级分级（L1 快速调试 / L2 完整诊断 / L3 修复建议） |
| **keyword-vault** | v1.0 | 调试关键词收纳系统 — 10 方向 239 关键词、自动学习、可视化 CRUD |

**排除项**: `feishu-integration`（飞书集成需独立部署飞书 Bot，非 CC 本地 Skill）

---

## 二、环境要求

| 条件 | 要求 | 说明 |
|------|------|------|
| Claude Code | 最新版本 | 支持自定义 Skill 的 CC 版本 |
| Python | 3.10+ | 部分 Skill 的 Python 脚本运行环境 |
| 操作系统 | Windows 10/11 | UNC 路径访问和 bug-logs 的 FTP/UNC 双通道功能需要 |
| pip 包 | httpx, requests | REST API 查询依赖 |

## 三、安装步骤

### Step 1: 确认仓库位置

确保源代码仓库已克隆到本地：

```bash
git clone https://github.com/owlm00n/bugzilla_assistent.git D:/06_Project/arkclaw-skills
```

### Step 2: 复制 Skill 目录到 Claude Code

```bash
# 进入仓库目录
cd D:/06_Project/arkclaw-skills/skills

# 复制 7 个 Skill 到 CC 技能目录
cp -r bug-core        ~/.claude/skills/bug-core
cp -r bug-logs        ~/.claude/skills/bug-logs
cp -r bug-workspace   ~/.claude/skills/bug-workspace
cp -r log-analyzer    ~/.claude/skills/log-analyzer
cp -r protocol-parser ~/.claude/skills/protocol-parser
cp -r code-generator  ~/.claude/skills/code-generator
cp -r keyword-vault   ~/.claude/skills/keyword-vault
```

### Step 3: 安装 Python 依赖

```bash
pip install httpx requests
```

### Step 4: 配置 Bugzilla API 凭证

编辑 `~/.claude/skills/bug-core/config/bugzilla_instances.json`，填入各实例的 API Key：

```json
{
  "instances": {
    "kernel":  { "api_key": "YOUR_KERNEL_API_KEY",  ... },
    "mozilla": { "api_key": "YOUR_MOZILLA_API_KEY", ... },
    "gnome":   { "api_key": "YOUR_GNOME_API_KEY",   ... },
    "unisoc":  { "api_key": "YOUR_UNISOC_API_KEY",  ... },
    "local":   { "api_key": "", ... }
  }
}
```

> **注意**: API Key 为敏感信息，请勿提交到 Git。配置文件已默认设为空字符串，安装后需手动填写。

### Step 5: 验证安装

#### 5.1 检查目录结构

```bash
ls ~/.claude/skills/
```

预期输出:

```
blog/  bug-core/  bug-logs/  bug-workspace/  code-generator/  keyword-vault/  log-analyzer/  protocol-parser/
```

#### 5.2 验证 Python 导入

```bash
cd ~/.claude/skills
python -c "
import sys
sys.path.insert(0, 'bug-core')
from bug_core import fetch_bug_rest, format_bug_summary; print('bug-core: OK')
sys.path.insert(0, 'bug-logs')
from bug_logs import parse_unisoc_structured_fields; print('bug-logs: OK')
sys.path.insert(0, 'bug-workspace')
from bug_workspace import generate_workspace; print('bug-workspace: OK')
sys.path.insert(0, 'keyword-vault')
from keyword_vault import get_keywords; print('keyword-vault: OK')
sys.path.insert(0, 'log-analyzer')
import log_analyzer; print('log-analyzer: OK')
sys.path.insert(0, 'protocol-parser')
import smart_extractor; print('protocol-parser: OK')
print('All OK!')
"
```

预期输出: 7 行 `OK` + `All OK!`

#### 5.3 运行测试套件

```bash
cd ~/.claude/skills

# bug-core: 63 用例
cd bug-core && python tests/test_core.py && cd ..

# bug-workspace: 57 用例
cd bug-workspace && python tests/test_workspace.py && cd ..

# bug-logs: 51 用例
cd bug-logs && python tests/test_logs.py && cd ..
```

预期: 总计 **171 用例，100% 通过** (63 + 57 + 51)。

---

## 四、Skill 目录结构说明

```
~/.claude/skills/
├── bug-core/                # Bug 查询核心（其他 Skill 的依赖）
│   ├── SKILL.md             # Skill 入口 — Claude Code 读取此文件
│   ├── bug_core.py          # 核心逻辑（REST API / 离线 / 搜索 / CLI）
│   ├── config/
│   │   └── bugzilla_instances.json  # 多实例 API 配置
│   ├── data/
│   │   └── sample_bugs.json # 离线 Bug 数据
│   ├── mcp-server/
│   │   └── server.py        # MCP Server（5 个工具）
│   └── tests/
│       └── test_core.py     # 63 用例
│
├── bug-logs/                # 日志目录 & 附件下载
│   ├── SKILL.md
│   ├── bug_logs.py          # UNC+FTP 双通道、附件下载、结构化解析
│   ├── comment_0.txt        # unisoc 19 字段测试数据
│   └── tests/
│       └── test_logs.py     # 51 用例
│
├── bug-workspace/           # 工作区创建 & 编排
│   ├── SKILL.md
│   ├── bug_workspace.py     # 文件夹/快捷方式/Bug Z 模板/编排下载
│   └── tests/
│       └── test_workspace.py  # 57 用例
│
├── log-analyzer/            # 角色感知日志分析
│   ├── SKILL.md
│   ├── log_analyzer.py      # 日志分析引擎
│   ├── log_viewer.py        # 日志查看器生成（v1）
│   ├── log_viewer_v2.py     # 日志查看器生成（v2）
│   ├── log_viewer_v2_template.html  # 交互式查看器模板
│   ├── prompts/
│   │   └── log_analysis.md  # 分析提示词模板
│   └── sample_output/       # 示例输出文件
│
├── protocol-parser/         # 协议智能解析
│   ├── SKILL.md
│   ├── smart_extractor.py   # 智能协议消息提取
│   ├── protocol_combiner.py # 混合日志（PD+USB）解析
│   ├── parsers/
│   │   ├── pd_parser.py     # PD 协议解析器
│   │   ├── usb_parser.py    # USB 枚举解析器
│   │   └── cc_parser.py     # CC 协商解析器
│   ├── templates/
│   │   ├── visualization.html  # 可视化 HTML 模板
│   │   └── bit_decoder.html    # 位级解码器
│   ├── sample_output/       # 示例报告
│   └── tests/               # 测试套件
│
├── code-generator/          # 代码辅助生成
│   ├── SKILL.md
│   ├── prompts/
│   │   └── code_generation.md
│   └── templates/
│       ├── debug_level1.c   # L1: 快速调试
│       ├── debug_level2.c   # L2: 完整诊断
│       └── debug_level3.c   # L3: 修复建议
│
├── keyword-vault/           # 关键词收纳系统
│   ├── SKILL.md
│   ├── keyword_vault.py     # 关键词 CRUD + 自动学习
│   ├── keyword_vault.json   # 关键词数据（10 方向 239 关键词）
│   └── config/
│       ├── pd_engineer.yaml  # PD 工程师角色画像
│       ├── usb_engineer.yaml # USB 工程师角色画像
│       └── test_engineer.yaml # 测试工程师角色画像
│
└── blog/                    # （已有）博文写作 Skill
```

---

## 五、使用方式

Skill 通过 SKILL.md 中的 `description` 和 `tags` 字段自动匹配用户意图，无需手动调用。

### 5.1 触发方式

| Skill | 触发关键词 | 示例 |
|-------|-----------|------|
| **bug-core** | Bug ID（5 位以上数字）/ "查Bug" / 粘贴 Bug 页面 | "查 Bug 219041" |
| **bug-logs** | "列出日志目录" / "下载附件" / "日志下载" | "下载 Bug 3410487 的附件" |
| **bug-workspace** | "创建工作区" / "下载日志" / "给 Bug XXX 创建工作区" | "为 Bug 219041 创建工作区并下载附件" |
| **log-analyzer** | 上传 log 文件 / "分析日志" / "排查问题" / 角色声明 | "我是 PD 工程师，帮我分析这个 log" |
| **protocol-parser** | "解析协议" / "PD 协商" / "USB 枚举" / 上传协议日志 | "解析这个 PD 协商 log" |
| **code-generator** | "生成 debug 代码" / "写调试代码" / "生成诊断代码" | "PD 协商失败，生成 L1 调试代码" |
| **keyword-vault** | "管理关键词" / "添加关键词" / "新建方向" / "更新关键词库" | "从角色生成关键词方向" |

### 5.2 典型工作流

```
# 完整排查流程
1. "查 Bug 219041"                         → bug-core 返回摘要
2. "下载附件"                               → bug-logs 下载日志到本地
3. "分析这个 log" (上传文件)                 → log-analyzer 生成分析报告
4. "解析 PD 协商"                           → protocol-parser 生成时序图
5. "生成 L2 debug 代码"                     → code-generator 生成诊断代码
6. "打开工作区"                             → bug-workspace 打开本地文件夹
```

---

## 六、跨 Skill 依赖说明

3 个 Bug 相关 Skill 之间存在依赖关系：

```
bug-workspace ──→ bug-logs ──→ bug-core
     │               │
     └───────────────┴──→ 三级降级导入（try import → sys.path → error）
```

- **bug-core**: 零依赖，可独立使用
- **bug-logs**: 依赖 bug-core（通过 `sys.path` fallback）
- **bug-workspace**: 依赖 bug-core + bug-logs（通过 `sys.path` fallback）
- **log-analyzer / protocol-parser**: 通过 keyword-vault 获取关键词数据（三级降级加载）
- **keyword-vault / code-generator**: 零依赖

所有依赖通过 `sys.path.insert(0, "../..")` 相对路径解决，目录结构不变即可正常工作。

---

## 七、常见问题

### Q1: 提示 "No module named 'httpx'"

```bash
pip install httpx requests
```

### Q2: Bug 查询返回 401/403

API Key 未配置或已过期。编辑 `~/.claude/skills/bug-core/config/bugzilla_instances.json` 填入有效 key。

### Q3: UNC 目录列表失败

仅在 Windows 办公网环境可用。确认 `\\shnas02\TestLogs` 可访问。

### Q4: Skill 没有被触发

检查 SKILL.md frontmatter 是否存在。Claude Code 自动读取 `~/.claude/skills/*/SKILL.md`，确认文件路径正确。

### Q5: 如何卸载某个 Skill

```bash
rm -rf ~/.claude/skills/<skill-name>
```

---

## 八、与飞书 Skill 的关系

`feishu-integration` Skill 设计为在飞书开放平台 Bot 服务端运行，不属于本地 Claude Code Skill。如需飞书集成：

1. 将 `skills/feishu-integration/` 部署到有公网 IP 的服务器
2. 在飞书开放平台配置 Bot 回调地址
3. 该 Skill 通过 OpenClaw feishu 插件桥接到本地的其他 Skill

---

> 安装日期: 2026-06-24 | 共安装 7 个 Skill | 总计 171 个测试用例
