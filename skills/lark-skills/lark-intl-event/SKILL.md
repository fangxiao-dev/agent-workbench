---
name: lark-intl-event
version: 1.0.0
description: "Lark International 事件订阅：使用 Webhook 模式接收 Lark 事件（消息、通讯录变更、日历变更等）。当用户需要配置 Lark International 事件订阅或构建事件驱动管道时使用。"
metadata:
  requires:
    bins: ["lark-cli"]
  cliHelp: "lark-cli event --help"
---

# event (v1)

> **前置条件：** 先阅读 [`../lark-intl-shared/SKILL.md`](../lark-intl-shared/SKILL.md) 了解认证、权限处理和安全规则。

## Event Subscription

**Note:** WebSocket long-connection mode (`+subscribe`) is NOT available on Lark International. Configure event subscription using **Webhook mode** instead:

1. In your app settings at `open.larksuite.com/app`, go to **Event Subscriptions**.
2. Set **Request URL** to your webhook endpoint.
3. Subscribe to specific events.
4. Lark will POST events to your endpoint as JSON.

