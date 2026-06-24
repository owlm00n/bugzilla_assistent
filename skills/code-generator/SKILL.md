---
name: code-generator
description: 代码辅助生成 - 基于日志分析结果自动生成debug代码片段，支持三级分级（快速调试/完整诊断/生产级修复）
version: "1.0"
tags: [code-gen, debug, template, driver, code-generation]
---

# 代码辅助生成

基于故障分析结果，一键生成分级debug代码片段。

## 触发条件

- 日志分析发现异常后，用户说"生成debug代码"、"帮我写调试代码"
- 协议解析器检测到异常后，用户说"生成追踪代码"
- 用户描述问题后，说"生成诊断代码"、"帮我添加日志"
- Bug描述包含调试需求

## 工作流程

### 流程1：基于分析结果生成

1. 用户已有日志分析报告或协议解析结果
2. 用户要求生成debug代码
3. 自动提取异常类型、涉及的模块、严重程度
4. 生成分级代码片段

### 流程2：手动描述生成

1. 用户描述问题："PD协商时VBUS电压未达到预期值"
2. 识别驱动类型（USB/PD/I2C/SPI/kernel）
3. 选择代码等级，生成对应代码

### 流程3：自定义等级生成

1. 用户指定等级："生成Level 3的修复代码"
2. 生成对应级别的代码

## 代码分级

### Level 1 - 快速调试（5分钟可用）
- 添加 `pr_debug()` / `pr_info()` / `pr_err()` 日志
- 简单的条件判断和变量打印
- 不改变程序逻辑，只增加输出
- 适用场景：快速定位问题点

### Level 2 - 完整诊断（15分钟可用）
- 条件断点 + 状态收集 + 自动上报
- 增加完整的时序追踪
- 包含关键状态机的状态打印
- 适用场景：需要系统性排查问题

### Level 3 - 修复建议（生产级）
- 补丁级代码 + 边界条件处理
- 包含回归测试建议
- 附带性能和安全影响分析
- 适用场景：问题定位后的修复代码

## 驱动类型识别

| 关键词 | 驱动类型 | 代码风格 |
|--------|---------|---------|
| pd_protocol, VBUS, PD_SRC_CAP | PD/TCPM | tcpm_state_machine, pd_src_state |
| usb_core, Enumeration, Descriptor | USB Host/Device | usb_core, usb_ep, urb |
| i2c, charger, PMIC | I2C/PMIC | i2c_transfer, regulator |
| thermal, thermal_zone | Thermal | thermal_zone, trip_point |
| kernel, dmesg, Call Trace | Kernel | printk, spin_lock, atomic |

## 输出格式

### 代码模板

```c
// Level: {level}
// 驱动类型: {driver_type}
// 问题描述: {description}

// === Level {level_num}: {level_name} ===
{code}

// === 编译/加载说明 ===
{instructions}

// === 回归测试建议 ===
{test_suggestions}
```

## 代码位置

- SKILL文件: `owlmyclaw/skills/code-generator/SKILL.md`
- 代码模板: `owlmyclaw/skills/code-generator/templates/`
- 提示词模板: `owlmyclaw/skills/code-generator/prompts/`
