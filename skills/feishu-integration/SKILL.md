---
name: feishu-integration
description: 飞书IM集成 - 通过飞书对话调用所有OWLMYCLAW能力，零切换工作流
version: "1.0"
tags: [feishu, im, bot, card, notification, integration]
---

# 飞书IM集成

通过飞书对话直接调用所有OWLMYCLAW能力，实现零切换工作流。

## 触发条件

- 用户在飞书群聊或私信中与OWLMYCLAW Bot对话
- 用户上传文件或log到飞书聊天窗口
- 定时触发Bug状态变更通知
- 分析结果/代码生成结果推送

## 对话指令

### 基本指令

| 指令 | 功能 | 示例 |
|------|------|------|
| `/bug 查询` | 查询Bug信息 | `/bug 219041` |
| `/log 分析` | 分析日志 | `/log 上传pd_log.txt` |
| `/code 生成` | 生成debug代码 | `/code 生成VBUS调试代码` |
| `/protocol 解析` | 解析协议log | `/protocol 解析usb_enum.log` |
| `/bug 列表` | 查询Bug列表 | `/bug 列表 P1` |
| `/bug 订阅` | 订阅Bug变更 | `/bug 订阅 BUG-20261` |
| `/status` | 检查OWLMYCLAW状态 | `/status` |

### 组合指令

| 指令 | 功能 |
|------|------|
| `/bug 分析 BUG-20261` | 查询Bug + 自动分析附件log |
| `/log 诊断 log.txt` | 日志分析 + 生成debug代码 |
| `/protocol 分析 log.txt` | 协议解析 + 可视化 + 异常检测 |

## 飞书卡片消息

### Bug变更通知卡片

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {"tag": "plain_text", "content": "🔔 Bug变更通知"},
      "template": "warning"
    },
    "elements": [
      {
        "tag": "div",
        "fields": [
          {"is_short": true, "text": {"tag": "lark_md", "content": "**Bug ID:**\nBUG-20261"}},
          {"is_short": true, "text": {"tag": "lark_md", "content": "**状态:**\nIn Progress"}},
          {"is_short": true, "text": {"tag": "lark_md", "content": "**优先级:**\nP1"}},
          {"is_short": true, "text": {"tag": "lark_md", "content": "**负责人:**\n张三"}}
        ]
      },
      {"tag": "hr"},
      {
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**变更内容:**\n状态从 Open → In Progress\n\n**备注:**\n正在分析PD协商log，定位VBUS问题"}
      },
      {"tag": "action",
        "actions": [
          {"tag": "button", "text": {"tag": "plain_text", "content": "查看详情"}, "url": "https://bugzilla.unisoc.com/show_bug.cgi?id=219041", "type": "primary"},
          {"tag": "button", "text": {"tag": "plain_text", "content": "分析附件log"}, "type": "warning"}
        ]
      }
    ]
  }
}
```

### 日志分析结果卡片

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {"tag": "plain_text", "content": "📊 日志分析结果"},
      "template": "blue"
    },
    "elements": [
      {
        "tag": "div",
        "fields": [
          {"is_short": true, "text": {"tag": "lark_md", "content": "**日志类型:**\nPD协商"}},
          {"is_short": true, "text": {"tag": "lark_md", "content": "**时长:**\n5400ms"}},
          {"is_short": true, "text": {"tag": "lark_md", "content": "**异常数:**\n4"}},
          {"is_short": true, "text": {"tag": "lark_md", "content": "**严重程度:**\nERROR"}}
        ]
      },
      {"tag": "hr"},
      {"tag": "div", "text": {"tag": "lark_md", "content": "**发现异常:**\n- [ERROR] 枚举失败 - Config Descriptor读取超时\n- [ERROR] 达到最大重试次数\n- [WARN] 描述符读取超时\n- [WARN] 请求重传"}
      },
      {"tag": "action",
        "actions": [
          {"tag": "button", "text": {"tag": "plain_text", "content": "查看详情"}, "type": "primary"},
          {"tag": "button", "text": {"tag": "plain_text", "content": "生成debug代码"}, "type": "warning"}
        ]
      }
    ]
  }
}
```

## 文件处理

### 支持的文件类型

- `.txt` - 日志文件
- `.log` - 日志文件
- `.json` - Bug数据/配置文件
- `.html` - 可视化报告
- `.c` / `.h` - 代码文件

### 文件处理流程

1. 用户发送文件到飞书聊天
2. Bot识别文件类型并自动分类
3. 日志文件 → 触发模块2(日志分析) + 模块3(协议解析)
4. Bug数据文件 → 触发模块1(Bug助手)
5. 代码文件 → 触发模块4(代码生成)或分析

## 定时任务

### 配置示例

```yaml
schedule:
  - name: "Bug变更巡检"
    cron: "0 */4 * * *"  # 每4小时
    action: "check_bug_changes"
    targets: ["BUG-20261", "BUG-20262"]
    channel: "#bug-alerts"

  - name: "每日Bug报告"
    cron: "0 9 * * 1-5"  # 工作日早上9点
    action: "daily_bug_report"
    channel: "#dev-team"
```

## 部署说明

### 开发环境

1. 创建飞书应用，获取 App ID 和 App Secret
2. 配置事件订阅 URL: `https://your-domain.com/feishu/webhook`
3. 添加机器人能力
4. 配置所需权限:
   - `im:message` - 发送消息
   - `im:chat` - 群聊管理
   - `contact:user:readonly` - 用户信息读取

### 生产环境

1. 部署飞书Bot服务 (Node.js/Python)
2. 配置API网关处理消息路由
3. 集成各模块Skill作为后端服务
4. 配置消息队列处理异步任务

## 代码位置

- SKILL文件: `owlmyclaw/skills/feishu-integration/SKILL.md`
- 提示词模板: `owlmyclaw/skills/feishu-integration/prompts/`
