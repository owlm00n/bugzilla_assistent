---
name: log-analyzer
description: 角色感知日志分析 - 基于角色画像自动筛选、异常检测、时间线重建和交互式日志查看器。关键词数据由 keyword-vault skill 提供。
version: "2.1"
tags: [log, analysis, role-profile, anomaly-detection, timeline, viewer]
---

# 角色感知日志分析

基于角色画像自动识别日志类型、筛选关键信息、检测异常模式、重建事件时间线。

> 📦 **关键词数据由 [keyword-vault](../keyword-vault/SKILL.md) skill 提供**。如需管理关键词方向，请使用 keyword-vault。

## 触发条件

- 用户上传log文件或粘贴log内容
- 用户说"分析日志"、"日志分析"、"看log"、"排查问题"
- 用户提到角色："我是PD工程师，帮我分析这个log"
- 用户提到具体故障现象："PD协商失败"、"USB枚举超时"

## 工作流程

### 流程1：自动分析

1. 用户上传log文件或粘贴log内容
2. 自动检测日志类型（PD/USB/混合/dmesg）
3. 默认使用通用分析策略
4. 输出分析摘要

### 流程2：角色感知分析

1. 用户指定角色（PD工程师/USB工程师/测试工程师）
2. 加载对应角色画像配置文件
3. 基于角色关键词和关注模块筛选日志
4. 生成角色定制化的分析报告

### 流程3：深度分析

1. 自动分析后检测异常
2. 对CRITICAL/ERROR级异常触发深度分析
3. 关联协议解析器生成可视化报告
4. 输出根因分析和建议

## 角色画像配置

角色画像文件位于 `keyword-vault` skill 的 `config/` 目录：

### PD充电工程师 (`config/pd_engineer.yaml`)
```yaml
role: pd_engineer
focus_keywords: [PD, VBUS, SRC_CAP, SNK_CAP, REQUEST, ACCEPT, PS_RDY, PDO, APDO]
concern_modules: [pd_protocol, charger_manager, vbus_control]
```
**关注**: PD协商流程、电压变化、PDO匹配、PR_SWAP/DR_SWAP

### USB驱动工程师 (`config/usb_engineer.yaml`)
```yaml
role: usb_engineer
focus_keywords: [Device Descriptor, Config Descriptor, Endpoint, Enumeration, Reset]
concern_modules: [usb_core, usb_host, usb_device, xhci]
```
**关注**: 枚举流程、描述符读取、驱动绑定、端点配置

### 测试工程师 (`config/test_engineer.yaml`)
```yaml
role: test_engineer
focus_keywords: [ERROR, WARN, FAIL, TIMEOUT, Reset, Recovery]
concern_modules: [kernel, power, usb, pd, thermal, charger]
```
**关注**: 跨模块日志关联、异常聚类、回归测试对比

## 分析能力

### 日志类型检测
基于关键词频率自动识别日志类型：
- PD协商log: PD消息类型、PDO、VBUS
- USB枚举log: Device/Config Descriptor、端点、Reset
- dmesg/kern.log: 内核消息、驱动加载
- 混合log: 多种协议消息混合

### 异常模式匹配
内置异常检测模式：
- 超时: Timeout、超时、TIMEOUT
- 重传: Retransmit、RETRY、retry
- 协议错误: REJECT、HARD_RESET、FAILED
- 电压异常: VBUS deviation、voltage mismatch
- 枚举失败: enumeration FAILED、descriptor timeout
- 系统异常: panic、oops、freeze、死机

### 时间线重建
按时间顺序重建关键事件，标注：
- 事件类型和方向（TX/RX/INFO）
- 事件间隔和累积时间
- 异常标注（⚠️ ERROR / ❌ FAIL）

### 分析摘要
生成结构化分析摘要，包含：
- 日志基本信息（类型、时长、事件数）
- 异常统计（按严重程度分类）
- 关键事件时间线
- 根因分析假设
- 针对角色的行动建议

## 输出格式

### JSON 结构化输出
```json
{
  "log_type": "pd",
  "duration_ms": 5400.0,
  "event_count": 34,
  "anomalies": [
    {"severity": "ERROR", "type": "timeout", "message": "...", "timestamp_ms": 1234}
  ],
  "timeline": [
    {"time_ms": 0, "event": "SRC_CAP received", "relevance": "high"}
  ],
  "analysis": {
    "root_cause": "...",
    "hypotheses": [...],
    "recommendations": [...]
  }
}
```

### 文本分析报告
```
## 日志摘要
- 类型: PD协商日志
- 时长: 5400ms
- 事件数: 34

## 异常发现 (4处)
### ERROR
- [10:12:03.201] Config Descriptor read timeout exceeded 500ms
- [10:12:05.200] USB enumeration FAILED at Config Descriptor

### WARNING
- [10:12:02.100] Descriptor read took 200ms (timeout=500ms)
- [10:12:03.300] Retrying GET_DESCRIPTOR (attempt 2/3)

## 根因分析
Config Descriptor读取超时导致枚举失败...

## 建议
1. 检查USB线缆连接质量
2. 增加descriptor读取超时时间
3. 检查设备固件版本
```

## 命令行用法

```bash
# 基本分析（自动检测类型）
python log_analyzer.py <logfile>

# 指定角色分析
python log_analyzer.py <logfile> --role pd_engineer

# 输出JSON
python log_analyzer.py <logfile> --json

# 深度分析模式
python log_analyzer.py <logfile> --deep

# 交互式日志查看器（基础版）
python log_viewer.py <logfile> [output_html]

# 增强版查看器（集成关键词收纳系统）
python log_viewer_v2.py <logfile> --direction protocol_timeout
python log_viewer_v2.py <logfile> --role pd_engineer

# 增强版查看器 + 预生成关键词（完全解耦，推荐）
python keyword_vault.py export -o viewer_kw.json          # 在 keyword-vault skill 中
python log_viewer_v2.py <logfile> --vault-json viewer_kw.json

# 独立关键词管理模式（无需日志文件）
python log_viewer_v2.py --standalone -o keywords.html
```

## 增强版日志查看器 (log_viewer_v2)

### 新功能
1. **左侧问题方向选择器** — 点击切换不同问题方向，自动加载对应关键词，👤 徽章标识角色来源
2. **关键词快捷复制** — 每个关键词旁有 📋 按钮，一键复制到剪贴板
3. **多格式复制** — 正则 OR / 空格 / 换行 / 通配 / grep -E 五种格式
4. **AND/OR 筛选模式** — 切换关键词匹配逻辑
5. **方向可视化 CRUD** — ➕ 新建 / ✏️ 编辑 / 🗑️ 删除问题方向
6. **关键词可视化 CRUD** — 添加 / 编辑 / 删除关键词，实时生效
7. **独立关键词管理模式** — 无日志文件时作为纯关键词管理系统使用
8. **单文件分享** — 所有数据内联在 HTML 中，一个文件即可分享

### 关键词数据加载（三级降级）

```
🥇 --vault-json viewer_kw.json    ← 预生成JSON，完全解耦（推荐）
🥈 import keyword_vault (自动发现) ← 同目录或 PYTHONPATH 可用时
🥉 subprocess 调用 export 命令     ← 跨 skill 目录自动查找
🏴‍☠️ 空数据降级                      ← 都不行也能跑（纯日志查看器）
```

### 界面布局
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

## 代码位置

- Log分析器: `owlmyclaw/skills/log-analyzer/log_analyzer.py`
- 基础查看器: `owlmyclaw/skills/log-analyzer/log_viewer.py`
- 增强查看器: `owlmyclaw/skills/log-analyzer/log_viewer_v2.py`
- 查看器模板: `owlmyclaw/skills/log-analyzer/log_viewer_v2_template.html`
- 提示词模板: `owlmyclaw/skills/log-analyzer/prompts/log_analysis.md`
- 关键词收纳: `owlmyclaw/skills/keyword-vault/` （独立 skill）
- 角色画像: `owlmyclaw/skills/keyword-vault/config/*.yaml`
