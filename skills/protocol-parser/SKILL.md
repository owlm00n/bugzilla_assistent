---
name: protocol-parser
description: PD/USB/CC协议智能解析与可视化 - AI驱动，兼容任意日志格式
version: "3.0"
tags: [pd, usb, type-c, cc, protocol, visualization, ai-parser]
---

# 协议智能解析与可视化

## 核心理念

**不依赖固定正则，AI + 知识库驱动解析。**

- 日志格式千变万化（展锐/高通/MTK/通用...），正则无法穷举
- AI 理解日志语义 + 知识库提供协议规范 → 正确解析任意格式
- 简单提取器只负责"缩小范围"，AI 负责"理解内容"

## 架构

```
用户上传 log / 其他 skill 提供 log
         │
         ▼
┌─────────────────────────────────┐
│  Layer 1: 渐进式提取器           │
│  smart_extractor.py             │
│                                 │
│  Level 0: 特定格式 → high       │
│  Level 1: 关键词匹配 → medium   │
│  Level 2: 超宽匹配 → low        │
│  Level 3: 裸传尾部 → unknown    │
│                                 │
│  输出: JSON {confidence, text}  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Layer 2: AI 语义理解            │
│  (当前 Agent 直接执行)           │
│                                 │
│  输入: 提取文本 + 知识库         │
│  ├── pd_protocol/pd3.1_spec.md  │
│  └── usb_protocol/usb_enum_flow │
│                                 │
│  能力:                          │
│  ├── 解码 header hex → 消息类型 │
│  ├── 解析 PDO 结构              │
│  ├── 识别状态机流转             │
│  ├── 检测异常/超时/死锁         │
│  └── 提取协商参数               │
│                                 │
│  输出: 结构化 JSON              │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Layer 3: 可视化渲染            │
│  templates/visualization.html   │
│                                 │
│  力科协议分析仪风格:             │
│  ├── 仪表盘 (V/A/W)            │
│  ├── 状态机流转图               │
│  ├── 报文时序表格               │
│  ├── PDO 能力表                 │
│  ├── SVG 时序图                 │
│  └── 异常标注                   │
└─────────────────────────────────┘
```

## 触发条件

- 用户上传 log 文件（任意格式）
- 用户说"解析协议"、"PD分析"、"USB枚举"、"CC状态"
- 其他 skill（如 bug-assistant）提供 log 文本
- 用户粘贴 log 内容

## 工作流程

### 标准流程

1. **接收输入**: 用户提供 log 文件路径或文本内容
2. **渐进式提取**: 运行 `smart_extractor.py <logfile>` 获取 JSON
3. **AI 分析**: Agent 阅读提取文本 + 知识库，生成结构化数据
4. **渲染报告**: 将数据注入可视化模板，生成 HTML

### 提取器用法

```bash
# JSON 输出（含置信度）
python smart_extractor.py <logfile>

# 纯文本输出
python smart_extractor.py <logfile> --text

# 限制行数
python smart_extractor.py <logfile> --max 500
```

### AI 分析指南

Agent 收到提取文本后，按以下步骤分析：

1. **判断内容**: 先确认文本中是否包含 PD/CC/USB 协议交互
2. **加载知识库**: 读取 `knowledge/pd_protocol/pd3.1_spec.md` 和 `knowledge/usb_protocol/usb_enum_flow.md`
3. **解析协议**:
   - PD: 解码 header hex → 消息类型、解析 PDO 结构、追踪状态机
   - CC: 提取 CC 状态变化、Rp/Rd、电流能力、VCONN
   - USB: 追踪枚举阶段、提取描述符信息
4. **检测异常**: 超时、重传、死锁、VBUS 异常、协商失败
5. **生成 JSON**: 结构化输出，包含 messages/timeline/capabilities/anomalies

## 知识库

| 文件 | 内容 |
|------|------|
| `knowledge/pd_protocol/pd3.1_spec.md` | PD 3.1 消息类型、PDO 结构、状态机、时序要求、故障模式 |
| `knowledge/usb_protocol/usb_enum_flow.md` | USB 枚举流程、描述符结构、传输类型、速率、故障模式 |

## 代码位置

| 文件 | 用途 |
|------|------|
| `smart_extractor.py` | 渐进式日志提取器（Layer 1） |
| `parsers/pd_parser.py` | PD 解析器（传统正则，兼容旧格式） |
| `parsers/usb_parser.py` | USB 解析器（传统正则，兼容旧格式） |
| `parsers/cc_parser.py` | CC 解析器（传统正则，兼容旧格式） |
| `protocol_combiner.py` | 组合器（自动检测 + 生成报告） |
| `templates/visualization.html` | 可视化模板 |
| `templates/lecroy_style_report.html` | 力科风格报告模板 |
| `tests/` | 测试套件（60 tests） |

## 支持的日志格式

### Level 0: 特定格式（高置信度）
- 展锐 SC27XX TCPM/PD (`sprd_tcpm_log` / `sprd_pd_log`)
- 通用 PD Protocol (`[pd_protocol]`)
- 通用 USB Core (`[usb_core]`)
- 通用 CC Protocol (`[cc_protocol]`)
- 高通 PMIC PD (`[pmic_pd]` / `[qcom_pd]`)
- MTK TCPC (`[mtk_tcpc]`)
- FUSB302/TCPCI (`[fusb302]` / `[tcpci]`)

### Level 1-3: 兜底
- 包含 PD/CC/USB 关键词的任意文本
- 包含充电/VBUS/Type-C 关键词的任意文本
- 完全未知格式 → 裸传给 AI 判断
