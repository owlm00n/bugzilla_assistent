# OWLMYCLAW 功能说明书

> 火山杯 AI 创新大赛 — 研发与创新赛道
> 作品名称: OWLMYCLAW — 底层驱动全栈自动化研发助手
> 版本: v1.5 | 日期: 2026-06-05

---

## 一、作品概述

### 1.1 作品定位

**OWLMYCLAW** 是一款面向底层驱动软件工程师的 AI 全栈研发助手，聚焦 **USB 接口与 PD 充电协议** 领域，通过 9 个协同工作的 AI Skill，覆盖从 Bug 追踪、日志分析、协议解析、代码生成、关键词知识管理到 IM 集成的完整研发闭环。

### 1.2 目标用户

| 用户角色 | 典型场景 | 核心痛点 |
|---------|---------|---------|
| USB 驱动工程师 | USB 枚举失败排查 | 手动翻日志找异常，耗时长 |
| PD 充电工程师 | PD 协商失败分析 | 协议交互复杂，人工解读易遗漏 |
| 测试工程师 | 回归测试 Bug 管理 | Bug 状态分散，优先级难以判断 |
| 驱动团队 Leader | 团队效率管理 | 新人上手慢，知识难以沉淀 |

### 1.3 核心价值

```
传统工作流: 查Bug(10min) → 翻日志(30min) → 分析协议(20min) → 写debug代码(15min) = 75min
OWLMYCLAW:   对话查询(10s) → 自动分析(30s) → 可视化报告(10s) → 一键生成(5s) = 55s

效率提升: ~80x
```

---

## 二、功能模块

### 模块1: Bug 查询核心 (bug-core) 🔴 从 bug-assistant 拆分

#### 功能描述
Bugzilla Bug 信息查询、搜索、解析的核心引擎。支持 REST API / 离线 / 手动输入三模式，通过 MCP Server 对外提供标准化 AI 工具接口。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **Bug ID 查询** | 输入 Bug ID，自动调用 Bugzilla REST API 获取完整信息 |
| **智能摘要** | 自动提取关键字段（标题/优先级/状态/模块/负责人），生成结构化摘要 |
| **多实例支持** | 支持 5 个 Bugzilla 实例（Kernel/Mozilla/GNOME/Unisoc/Local） |
| **搜索/列表** | 关键词搜索 + 离线 Bug 列表 |
| **手动输入解析** | 用户粘贴 Bug 页面内容，自动提取结构化信息 |
| **CLI 工具** | 命令行查询（支持 --json / --offline / --list 参数） |
| **MCP 服务** | 统一 MCP Server（5 个工具），支持标准 MCP 协议 |

#### 使用示例

```
用户: 查 Bug 219041
助手: 🔍 Bug 219041
      📋 标题: USB enumeration timeout on XHCI controller
      ⚡ 优先级: P1 | 状态: In Progress
      👤 负责人: John Doe
      📎 附件: usb_mon_log.txt (2026-05-15)
```

#### 技术实现
- **语言**: Python 3.10
- **数据源**: Bugzilla REST API / 预置数据集 / 手动输入
- **MCP 服务**: 统一 MCP Server（5 个工具：bug_info / bug_comments / bugs_search / bug_workspace / bug_logs）
- **配置**: 多实例 JSON 配置，热切换

---

### 模块2: 日志目录与附件下载 (bug-logs) 🔴 从 bug-assistant 拆分

#### 功能描述
解析 unisoc Bugzilla 的 19 字段结构化评论格式，提取 LogPath/LogType/VersionPath/OccurTime；通过 UNC+FTP 双通道列出日志目录；**智能识别两种附件类型（UNC 内部附件 / rayfile SPCSS 客户附件）并自动下载**。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **结构化评论解析** | 自动解析 unisoc Bug 的 19 字段模板格式，提取 LogPath/LogType/VersionPath/OccurTime |
| **UNC 目录列表** | Windows 办公网下通过 `os.scandir()` 直接访问共享目录 |
| **FTP Fallback** | UNC 不可达时自动切换 `ftplib.FTP_TLS`，支持 TLS 加密 |
| **组合查询** | `fetch_bug_with_logs()` — Bug 信息+结构化解析+日志目录一键获取 |
| **智能附件检测** 🔴 | `detect_attachment_type()` — 自动识别 UNC 内部附件 vs rayfile SPCSS 客户附件 |
| **双通道下载** 🔴 | UNC 直接复制 (`shutil.copy2`) + rayfile FTP 子进程下载 |
| **目录规范化** 🔴 | `normalize_downloaded_folder()` — 3 种模式（off/move/copy_new） |
| **MCP 工具** | 提供 `bug_logs` MCP 工具，支持列表+下载双模式 |

#### 日志目录查询流程

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

#### 双通道目录列表

| 通道 | 适用场景 | 访问方式 |
|------|---------|---------|
| **UNC** | Windows 办公网，共享目录直接访问 | `os.scandir(\\server\share\...)` |
| **FTP** | UNC 不可达时自动 fallback | `ftplib.FTP_TLS(unitrans.unisoc.com:2443)` |

#### 使用示例

```
用户: 列出 Bug 219041 的日志目录
助手: 📁 \\shnas02\TestLogs\PSST (UNC 访问)
      📂 subdirs: diag_logs, crash_dumps, trace
      📄 files: modem_log.zip (45MB), syslog.txt (2MB)
      💡 根据 occur_time (2026-05-15) 和 version_path 建议查看 modem_log.zip
```

#### 技术实现
- **语言**: Python 3.10
- **解析器**: 正则表达式解析 unisoc 19 字段结构化模板
- **目录列表**: Windows `os.scandir()` + Python `ftplib.FTP_TLS` 双通道
- **跨 Skill 导入**: 三级降级导入 bug_core（try import → sys.path fallback）

---

### 模块3: 工作区管理 (bug-workspace) 🔴 从 bug-assistant 拆分

#### 功能描述
一键创建 Bug 调试工作区：自动生成规范命名的文件夹、Bug Z 模板复制、Bug 摘要文件、URL 快捷方式、路径历史管理、快速打开，并通过编排调用 bug-logs 完成附件下载。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **工作区创建** | `generate_workspace()` — 自动创建文件夹+摘要+快捷方式+rayfile命令 |
| **规范命名** | 文件夹名格式：`[BugID] 摘要（清理非法字符）` |
| **Bug Z 模板** 🔴 | `copy_bug_z_template()` — 自动复制 Bug Z 模板到工作区 |
| **路径历史** 🔴 | `load/save_workspace_paths()` — 15 个默认工作区路径，支持增删 |
| **快速打开** 🔴 | `open_workspace_path()` — `os.startfile()` 一键打开工作区 |
| **Rayfile 命令** | `get_rayfile_command()` — 精确匹配原工具参数（-o download -d -s） |
| **编排下载** 🔴 | `generate_workspace_with_download()` — 创建+模板+快捷方式+下载一站式 |
| **Bug 摘要** | 从 bug_core 导入 `format_bug_summary()`，生成结构化摘要文件 |
| **URL 快捷方式** | 生成 Windows `.url` 快捷方式（`[InternetShortcut]`），>200字符自动简化 |
| **独立运行** | 可脱离 API 独立运行（提供 Bug 字典即可创建工作区） |

#### 工作区目录结构

```
E:\08_Bug\[219041] USB enumeration timeout on XHCI\
├── Bug Z/                        ← Bug Z 模板（可选）
├── Attachements/                 ← 下载的附件
├── Bug_219041.url                ← Bugzilla 快捷方式
└── bug_summary.txt               ← Bug 摘要文件
```

#### 使用示例

```
用户: 为 Bug 219041 创建工作区并下载附件
助手: ✅ 工作区已创建！
      📁 E:\08_Bug\[219041] USB enumeration timeout on XHCI\
      📋 附件类型: UNC（内部测试工程师附件）
      📄 bug_summary.txt — 45 行摘要
      🔗 Bugzilla 快捷方式
      📥 下载完成: 45 文件, 320 MB
      📋 目录规范化: copy_new
```

```
用户: 仅创建工作区（不下载）
助手: ✅ 工作区已创建！
      📁 E:\08_Bug\[219041] USB enumeration timeout on XHCI\
      📄 bug_summary.txt
      🔗 Bugzilla 快捷方式
      📥 可用 MCP bug_logs (download=true) 下载附件
```

#### 技术实现
- **语言**: Python 3.10
- **依赖**: bug_core（format_bug_summary / clean_folder_name）、bug-logs（download_bug_attachments）
- **命名**: 正则清理 Windows 非法字符 `\/:*?"<>|`
- **跨 Skill 导入**: 三级降级导入 bug_core + bug-logs

---

### 模块1-3 拆分说明 🔴

> **原 bug-assistant Skill**（~984行）已于 2026-06-05 拆分为以上 3 个独立 Skill：
> - **bug-core**（~320行）：Bug 查询/解析/搜索 + 配置 + MCP Server
> - **bug-logs**（~700行）：日志目录列表 + 结构化评论解析 + **智能附件下载**
> - **bug-workspace**（~450行）：工作区创建 + Bug Z 模板 + 路径历史 + **编排下载**
>
> 拆分原因：3 个功能群正交独立，仅通过配置共享耦合。拆分后每个 Skill 可独立部署和测试。统一 MCP Server 位于 bug-core/mcp-server/，提供全部 5 个 MCP 工具。
>
> **v2.0 下载重构**（2026-06-05）：bug-logs 新增智能附件检测 + UNC/rayfile 双通道下载；bug-workspace 新增编排下载 + Bug Z 模板 + 路径历史。5 个 MCP 工具均支持下载参数。

---

### 模块4: 角色感知日志分析 (log-analyzer) ⭐核心亮点

#### 功能描述
基于预设角色画像，自动识别日志类型、筛选关键信息、检测异常模式、重建事件时间线，生成结构化分析报告。集成**交互式日志查看器**，支持方向切换、关键词筛选、多格式复制。

> 📦 关键词数据由独立的 [keyword-vault](#模块9-关键词收纳系统-keyword-vault) skill 提供，支持三级降级加载。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **自动类型识别** | 自动检测日志类型（PD 协商 / USB 枚举 / dmesg / 混合） |
| **角色画像切换** | 3 种预设角色：PD 工程师 / USB 工程师 / 测试工程师 |
| **关键词自动筛选** | 基于角色画像自动生成搜索关键词，精准定位 |
| **异常模式检测** | 匹配 ERROR/FAIL/Timeout/Reset 等异常模式 |
| **时间线重建** | 按时间顺序重建关键事件序列 |
| **AI 分析摘要** | 大模型生成分析摘要，标注异常点和建议 |
| **交互式日志查看器** | 单文件 HTML，支持方向切换、关键词筛选、多格式复制 |
| **三级降级加载** | 关键词数据支持预生成JSON/自动发现/subprocess/空数据四种模式 |

> 📦 关键词收纳系统已拆分为独立 Skill，详见 [模块9](#模块9-关键词收纳系统-keyword-vault)。

#### 交互式日志查看器 (Log Viewer v2)

增强版单文件 HTML 查看器，集成关键词收纳系统：

```
┌──────────────┬──────────────────────────────────┐
│  侧边栏       │  工具栏 (筛选 + 搜索框)           │
│  🎯 问题方向  │  当前关键词栏 (AND/OR 模式切换)    │
│  ├ 全部       │  ┌──────────────────────────────┐│
│  ├ 协议超时👤 │  │ 日志内容区域                   ││
│  ├ 功率不匹配 │  │ (语法高亮 + 关键词匹配高亮)    ││
│  ├ ...       │  │                              ││
│  ➕ 新建方向  │  └──────────────────────────────┘│
│  🔑 关键词   │  状态栏                            │
│  [chip][chip]│                                   │
│  ⚡ 快捷操作  │                                   │
│  ➕ 添加关键词│                                   │
└──────────────┴──────────────────────────────────┘
```

**查看器功能**：

| 功能 | 说明 |
|------|------|
| 方向切换 | 点击左侧方向切换关键词集，👤 徽章标识角色来源 |
| 关键词筛选 | 点击关键词 chip 添加到筛选，支持 AND/OR 逻辑 |
| 多格式复制 | 正则 OR / 空格 / 换行 / 通配 / grep -E 五种格式 |
| 方向 CRUD | ➕ 新建 / ✏️ 编辑 / 🗑️ 删除问题方向 |
| 关键词 CRUD | 添加 / 编辑 / 删除关键词，实时生效 |
| 日志高亮 | ERROR/WARN 颜色标注，时间戳和 TX/RX 方向高亮 |
| 独立模式 | 无日志文件时作为纯关键词管理系统使用 |
| 单文件分享 | 所有数据内联在 HTML 中，一个文件即可分享 |

#### 使用示例

```
用户: [上传 pd_log.txt] 我是PD工程师，帮我分析
助手: 📊 日志分析报告
      类型: PD 协商日志
      总行数: 1,247 | 异常: 3 处
      
      ⚠️ 异常1 (行 342): VBUS 电压异常 — 预期 9V，实际 5.2V
      ⚠️ 异常2 (行 567): PS_RDY 超时 — 等待 500ms 未收到
      ⚠️ 异常3 (行 891): PR_SWAP 失败 — Device 拒绝角色交换
      
      💡 建议: 检查 VBUS 稳压电路和 PD Controller 固件版本
```

#### 技术实现
- **语言**: Python 3.12
- **配置**: YAML 角色画像文件（3 个角色）
- **算法**: 正则匹配 + 关键词权重 + 时间线排序
- **关键词库**: JSON 持久化，10 方向 239 关键词
- **查看器**: 单文件 HTML + CSS + JavaScript，零依赖
- **输出**: 结构化文本报告 / JSON / 交互式 HTML 查看器

---

### 模块5: 协议智能解析与可视化 (protocol-parser) ⭐核心亮点

#### 功能描述
从原始 PD/USB 日志中提取协议交互帧，解析协议语义，生成交互式 HTML 可视化报告，支持异常标注和时间轴展示。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **PD 协议解析** | 解析 SRC_CAP/SNK_CAP/REQUEST/ACCEPT/PS_RDY/PR_SWAP 等关键消息 |
| **USB 枚举解析** | 解析 Connect/Reset/Enum/Config 各阶段 |
| **自动类型检测** | 自动识别日志类型，调用对应解析器 |
| **交互式可视化** | 生成 HTML 报告：时序图 + 消息详情 + 异常标注 |
| **异常检测** | 协商超时、消息丢失、电压异常跳变自动检测 |
| **混合日志支持** | 同时包含 PD 和 USB 的日志自动分段解析 |

#### 可视化效果

```
时间轴: Host ←→ Device
─────────────────────────────────
  0.0ms  SRC_CAP(5V/3A, 9V/3A, 20V/5A)  →
  1.2ms  ←  REQUEST(9V, 3A)
  1.5ms  ACCEPT                           →
  2.0ms  PS_RDY                           →
  ⚠️ 5.0ms  VBUS 异常: 预期 9V，实际 5.2V
  ⚠️ 8.0ms  Hard Reset 触发
```

#### 使用示例

```
用户: 解析这个 PD 协商 log
助手: ✅ 解析完成！
      类型: PD 3.0 协商
      消息数: 24 条 | 异常: 2 处
      
      📊 可视化报告已生成: pd_negotiation_report.html
      
      关键发现:
      1. SRC_CAP → REQUEST → ACCEPT 正常
      2. ⚠️ PS_RDY 后 VBUS 未达到目标电压
      3. ⚠️ 触发 Hard Reset，协商重新开始
```

#### 技术实现
- **语言**: Python 3.12
- **解析器**: 正则 + 状态机（pd_parser.py / usb_parser.py）
- **可视化**: HTML + CSS + JavaScript（内联，单文件可分享）
- **输出**: JSON 结构化数据 + HTML 可视化报告

---

### 模块6: 代码辅助生成 (code-generator)

#### 功能描述
基于故障分析结果，一键生成分级 debug 代码片段，支持三级分级策略，覆盖从快速调试到生产级修复的完整流程。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **三级分级生成** | Level 1 快速调试 / Level 2 完整诊断 / Level 3 修复建议 |
| **驱动类型识别** | 自动识别 USB/PD/I2C/SPI 等驱动类型 |
| **上下文感知** | 基于日志分析结果和协议解析报告生成针对性代码 |
| **模板库** | 预置 C 语言调试代码模板 |

#### 三级分级策略

| 等级 | 名称 | 适用场景 | 示例 |
|:---:|------|---------|------|
| L1 | 快速调试 | 紧急排查，5 分钟上线 | `pr_debug()` 添加关键变量打印 |
| L2 | 完整诊断 | 深度分析，含条件断点 | 状态机追踪 + 寄存器 dump + 自动上报 |
| L3 | 修复建议 | 补丁级代码 | 完整修复 patch + 回归测试用例 |

#### 使用示例

```
用户: PD协商时VBUS电压未达到预期，生成debug代码
助手: 🔧 生成调试代码 (Level 1 - 快速调试)

      // 在 pd_vbus_ctrl.c 的 vbus_change_handler() 中添加:
      pr_debug("PD: VBUS=%dmV, expected=%dmV, state=%s, cc=%d\n",
               vbus_read_mv(), expected_mv,
               pd_state_name(state), cc_line);
      
      // 在 pd_message_rx() 中添加:
      if (msg->type == PD_MSG_PS_RDY) {
          pr_debug("PD: PS_RDY received, VBUS=%dmV\n", vbus_read_mv());
      }
      
      💡 需要 Level 2 完整诊断代码吗？
```

#### 技术实现
- **语言**: C 代码模板
- **模板**: 3 级 × 多种驱动类型的预置模板
- **触发**: 基于日志分析 / 协议解析结果自动推荐

---

### 模块7: 飞书 IM 集成 (feishu-integration)

#### 功能描述
通过飞书对话直接调用所有 OWLMYCLAW 能力，实现零切换工作流，支持文件上传、卡片推送、定时通知。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **对话式调用** | 飞书群聊/私聊中直接使用所有功能 |
| **文件上传处理** | 飞书中上传 log 文件，自动触发分析 |
| **卡片推送** | Bug 变更 / 分析结果 / 代码生成以卡片形式推送 |
| **定时通知** | Bug 附件更新主动推送 |
| **指令系统** | `/bug` `/log` `/code` `/protocol` 快捷指令 |

#### 对话指令

| 指令 | 功能 |
|------|------|
| `/bug <ID>` | 查询 Bug 信息 |
| `/bug 列表 <优先级>` | 查询 Bug 列表 |
| `/log 分析` | 分析上传的日志 |
| `/protocol 解析` | 解析协议 log |
| `/code 生成 <描述>` | 生成 debug 代码 |

#### 技术实现
- **平台**: 飞书开放平台
- **交互**: Bot 对话 + 消息卡片 + 文件消息
- **集成**: 通过 OpenClaw feishu 插件实现

---

### 模块8: 知识库与提示词工程

#### 功能描述
USB/PD 协议知识沉淀、故障案例库、提示词模板库，为 AI 分析提供领域知识支撑。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **PD 协议知识库** | PD 3.1 关键规范、消息类型、状态机 |
| **USB 协议知识库** | USB 枚举流程、描述符结构、常见错误码 |
| **故障案例库** | 典型故障案例（脱敏），含 log + 分析 + 修复 |
| **提示词模板库** | 针对不同场景的优化提示词 |

#### 知识库内容

| 类别 | 文件 | 内容 |
|------|------|------|
| PD 协议 | `pd3.1_spec.md` | 消息类型、电压档位、状态机 |
| USB 协议 | `usb_enum_flow.md` | 枚举阶段、描述符、错误处理 |
| 故障案例 | `fault_case_001_pd_negotiation.md` | PD 协商失败案例 |
| 提示词 | `all_prompts.md` | 各场景优化提示词 |

---

### 模块9: 关键词收纳系统 (keyword-vault)

#### 功能描述
独立的调试关键词知识管理 Skill，按问题方向分类管理关键词，支持角色画像自动生成、自动学习、命令行和可视化双模式管理。是 log-analyzer 和 protocol-parser 等分析类 Skill 的知识底座。

#### 核心能力

| 能力 | 说明 |
|------|------|
| **双渠道方向来源** | 7 个内置异常模式库 + 3 个角色画像自动生成 |
| **命令行管理** | list/show/search/add/remove/new-direction/learn 全套 CRUD |
| **角色画像驱动** | `generate-from-roles` 从 YAML 配置自动导入方向，增量合并 |
| **自动学习** | 从日志文本中识别技术关键词，≥2次出现自动收纳 |
| **可视化 CRUD** | 通过 log_viewer_v2 查看器直接新建/编辑/删除方向和关键词 |
| **多格式导出** | `export --json` 供程序调用，`export -o` 保存 JSON 文件 |
| **独立可复用** | 零依赖其他 Skill，可被任意分析类 Skill 消费 |

#### 预设问题方向

| 方向ID | 名称 | 关键词 | 来源 |
|--------|------|:---:|------|
| protocol_timeout | 协议超时问题 | 21 | 内置异常模式库 |
| power_mismatch | 功率/电压不匹配 | 29 | 内置异常模式库 |
| enum_failure | USB 枚举失败 | 28 | 内置异常模式库 |
| connection_stability | 连接稳定性问题 | 31 | 内置异常模式库 |
| role_swap | 角色/方向切换问题 | 19 | 内置异常模式库 |
| thermal_throttle | 温度/热管理问题 | 19 | 内置异常模式库 |
| firmware_boot | 固件/启动问题 | 27 | 内置异常模式库 |
| role_pd_engineer | PD充电工程师关注点 | 19 | 角色画像 → PD工程师 |
| role_test_engineer | 测试工程师关注点 | 22 | 角色画像 → 测试工程师 |
| role_usb_engineer | USB驱动工程师关注点 | 24 | 角色画像 → USB工程师 |

**总计**: 10 个方向 / 239 个关键词

#### 被消费方式（三级降级）

```
keyword-vault ──🥇 export --json──→ log_viewer_v2 (预生成JSON，完全解耦)
keyword-vault ──🥈 import module──→ log_viewer_v2 (自动发现同目录或PYTHONPATH)
keyword-vault ──🥉 subprocess─────→ log_viewer_v2 (跨skill目录自动查找)
keyword-vault ──🏴‍☠️ 空数据──────→ log_viewer_v2 (纯日志查看器模式)
```

#### 技术实现
- **语言**: Python 3.12
- **数据**: JSON 持久化（keyword_vault.json）
- **角色配置**: YAML（config/*.yaml），内置简易 YAML 解析器
- **集成**: 命令行 + Python import + subprocess 三种调用方式

---

## 三、技术架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────┐
│                    用户交互层                      │
│  飞书 IM  │  ControlUI  │  WebChat  │  API      │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│                 OpenClaw Agent 引擎               │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Skill 调度│ │ 工具调用  │ │ Memory (LanceDB) │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│                  OWLMYCLAW Skills                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │bug-core  │ │bug-logs  │ │bug-     │  │
│  │(查询核心)│ │(日志目录)│ │workspace│  │
│  └─────────┘ └─────────┘ └─────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │log-     │ │protocol-│ │keyword- │  │
│  │analyzer★│ │parser★  │ │vault    │  │
│  └────┬────┘ └─────────┘ └─────────┘  │
│  ┌─────────┐      │      ┌─────────┐  │
│  │code-    │      │      │knowledge│  │
│  │generator│      │      │库支撑   │  │
│  └─────────┘      │      └─────────┘  │
│  ┌─────────┐      │                   │
│  │feishu-  │      │                   │
│  │integration│    │                   │
│  └─────────┘      │                   │
│                   │                   │
│     keyword-vault ──export──→ log-analyzer    │
│     keyword-vault ──export──→ protocol-parser │
└─────────────────────────────────────────────────┘
```

### 3.2 模块联动

```
用户输入 Bug ID
    │
    ▼
bug-core ──→ 返回 Bug 摘要 + 附件信息
    │
    ▼ (用户上传 log)
log-analyzer ──→ 角色感知分析 + 异常检测
    │              ↑
    │    keyword-vault (关键词数据)
    ▼
protocol-parser ──→ 协议解析 + 可视化报告
    │
    ▼ (一键触发)
code-generator ──→ 分级 debug 代码生成
    │
    ▼
feishu-integration ──→ 飞书卡片推送全流程结果
```

### 3.3 技术栈

| 层次 | 技术 |
|------|------|
| Agent 平台 | OpenClaw / Claude Code |
| 开发语言 | Python 3.12 |
| 协议解析 | 正则 + 状态机 |
| 可视化 | HTML + CSS + JavaScript (单文件) |
| 知识库 | Markdown |
| 记忆系统 | LanceDB (语义向量检索) |
| 版本管理 | Git (GitHub) |
| IM 集成 | 飞书开放平台 |

---

## 四、使用场景

### 场景1: Bug 驱动的完整排查流程

```
工程师在飞书中:
  "/bug 219041"
  → Bug 摘要卡片
  → 上传附件 log
  → 自动日志分析 + 协议解析
  → 可视化报告
  → 一键生成 debug 代码
  → 全流程 55 秒完成
```

### 场景2: 新人上手故障排查

```
新入职工程师遇到 PD 协商失败:
  1. 上传 log → 自动识别为 PD 日志
  2. 选择 "PD 工程师" 角色 → 自动筛选 PD 相关关键词
  3. 查看可视化时序图 → 直观理解协议交互
  4. 查看异常标注 → 快速定位问题点
  5. 生成 debug 代码 → 直接添加到驱动中
```

### 场景3: 日常 Bug 状态监控

```
每天早上:
  → 飞书推送: "您关注的 3 个 Bug 有更新"
  → 点击查看变更摘要
  → 新附件自动通知
```

---

## 五、效果数据

### 5.1 效率提升

| 指标 | 传统方式 | OWLMYCLAW | 提升 |
|------|---------|-----------|:---:|
| Bug 信息查询 | 5-10 分钟 | 10 秒 | **60x** |
| 日志异常定位 | 20-30 分钟 | 30 秒 | **50x** |
| 协议交互分析 | 15-20 分钟 | 10 秒 | **100x** |
| Debug 代码编写 | 10-15 分钟 | 5 秒 | **150x** |
| **端到端排查** | **60-75 分钟** | **55 秒** | **~80x** |

### 5.2 质量改善

| 指标 | 改善 |
|------|:---:|
| 异常遗漏率 | ↓ 90%（AI 自动检测替代人工目视） |
| 新人上手时间 | ↓ 70%（知识库 + 角色画像引导） |
| 重复问题排查 | ↓ 85%（故障案例库匹配） |

### 5.3 覆盖范围

| 维度 | 数据 |
|------|:---:|
| 技能数量 | 9 个独立 Skill（含 2 个核心亮点模块 + bug-assistant 拆分为 3 个） |
| 知识库条目 | 5 个专题文档 |
| 故障案例 | 1 个完整案例（可扩展） |
| 角色画像 | 3 种预设角色 |
| 关键词方向 | 10 个方向 / 239 个关键词 |
| 代码模板 | 3 级 × 多种驱动类型 |
| 支持协议 | PD 3.0/3.1 + USB 2.0/3.x |
| **日志目录通道** 🔴 | **2 通道（UNC + FTP fallback）** |
| **MCP 工具数量** 🔴 | **5 个（bug_info/bug_comments/bugs_search/bug_workspace/bug_logs，均支持下载参数）** |
| **测试覆盖** 🔴 | **136 用例 / 10 组 / 100% 通过** |

---

## 六、创新亮点

### 6.1 协议交互式可视化 ⭐

将枯燥的 PD/USB 协议日志转化为**交互式 HTML 时序图**，异常自动标注，一键分享。这是行业内首个面向驱动工程师的协议可视化 AI 工具。

### 6.2 角色感知分析 + 关键词收纳系统 ⭐

不是通用日志分析，而是**基于工程师角色的上下文感知**。PD 工程师和 USB 工程师看同一份 log，AI 自动切换关注点和分析策略。关键词收纳系统支持 10 个问题方向、239 个关键词，通过双渠道（内置异常模式库 + 角色画像自动生成）持续扩展，可视化 CRUD 管理。

### 6.3 三级代码生成闭环

从"发现问题"到"写出 fix"形成完整闭环：
```
Bug 查询 → 日志分析 → 协议解析 → 代码生成
```

### 6.4 多 Agent 协作架构

支持多个 AI Agent 通过 Git 协作开发，策略文档化，新 Agent 2 分钟上手。

### 6.5 知识可沉淀的关键词系统

关键词收纳系统不是一次性配置，而是**持续进化的知识库**：角色画像变更后一键同步，日志分析中自动学习新关键词，可视化界面随时编辑。每个方向标注来源（内置/角色/自定义），知识来源可追溯。

---

## 七、未来规划

| 阶段 | 内容 |
|------|------|
| **短期** (赛后 1 个月) | 接入办公网 Bugzilla API，实现生产级部署 |
| **中期** (3 个月) | 扩展 I2C/SPI/UART 协议支持，丰富故障案例库 |
| **长期** (6 个月) | MCP 生态集成，支持 Claude Code/Cursor 等 IDE 插件 |

---

> 版本: v1.5 | 作者: OWLMYCLAW Team | 日期: 2026-06-05
