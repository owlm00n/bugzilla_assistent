---
name: keyword-vault
description: 调试关键词收纳系统 — 按问题方向分类管理调试关键词，支持角色画像自动生成、自动学习、可视化CRUD管理
version: "1.0"
tags: [keyword, knowledge-management, role-profile, debug, vault]
---

# 关键词收纳系统 (Keyword Vault)

按问题方向分类管理调试关键词，是 OWLMYCLAW 日志分析和协议解析的知识底座。

## 触发条件

- 用户说"管理关键词"、"关键词收纳"、"添加关键词"、"新建方向"
- 用户说"从角色生成方向"、"更新关键词库"
- 用户上传角色配置文件
- 其他 skill（log-analyzer、protocol-parser）需要关键词数据时

## 核心概念

### 问题方向 (Direction)
一组相关关键词的集合，代表一类调试问题。例如：
- `protocol_timeout` — 协议超时相关的所有关键词
- `power_mismatch` — 功率/电压不匹配相关的所有关键词

### 关键词来源（双渠道）

| 来源 | 数量 | 说明 |
|------|:---:|------|
| 内置异常模式库 | 7 个 | 基于 USB/PD 驱动领域经验预置 |
| 角色画像自动生成 | 3 个 | 从 config/*.yaml 角色配置自动导入 |

## 预设问题方向

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

## 命令行用法

```bash
# 列出所有问题方向
python keyword_vault.py list

# 查看指定方向的关键词
python keyword_vault.py show protocol_timeout

# 搜索匹配的问题方向
python keyword_vault.py search "超时"

# 创建新方向
python keyword_vault.py new-direction dma_error "DMA传输异常" "DMA传输失败/数据损坏"

# 手动添加关键词
python keyword_vault.py add protocol_timeout "NEW_KW"

# 移除关键词
python keyword_vault.py remove protocol_timeout "OLD_KW"

# 从文本自动学习关键词
python keyword_vault.py learn "log内容" -d protocol_timeout

# 从角色配置文件重新生成方向（增量合并）
python keyword_vault.py generate-from-roles

# 导出为 viewer 格式
python keyword_vault.py export -o viewer_kw.json    # 保存到文件
python keyword_vault.py export --json               # 输出纯 JSON 到 stdout
```

## 自动学习

系统从用户输入的 log 内容中自动识别技术关键词：
- 全大写缩写（如 `VBUS`、`SRC_CAP`、`HARD_RESET`）
- 驼峰命名（如 `SenderResponseTimer`）
- 下划线命名（如 `pd_protocol`、`vbus_control`）
- 同一关键词出现 ≥2 次才会自动收纳

## 角色画像驱动

`generate-from-roles` 命令读取 `config/*.yaml` 中的角色画像，将每个角色的 `focus_keywords` 和 `concern_modules` 作为独立的问题方向导入关键词库。

- 增量合并：已存在的方向只追加新关键词，不覆盖
- 来源追溯：每个方向标注 `from_role` 字段，知道是从哪个角色来的

## 被其他 Skill 使用

keyword-vault 是数据提供者，被以下 skill 消费：

```
keyword-vault ──export──→ log-analyzer (log_viewer_v2.py)
keyword-vault ──export──→ protocol-parser
keyword-vault ──export──→ code-generator
```

### 集成方式（三级降级）

```bash
# 方式1: 预生成 JSON（推荐，完全解耦）
python keyword_vault.py export -o viewer_kw.json
python log_viewer_v2.py log.txt --vault-json viewer_kw.json

# 方式2: 自动发现（同目录或 PYTHONPATH）
python log_viewer_v2.py log.txt

# 方式3: 无关键词也能跑（纯日志查看器模式）
```

## 代码位置

- 关键词收纳: `owlmyclaw/skills/keyword-vault/keyword_vault.py`
- 关键词数据: `owlmyclaw/skills/keyword-vault/keyword_vault.json`
- 角色画像: `owlmyclaw/skills/keyword-vault/config/*.yaml`
