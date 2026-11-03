---
name: call-oracle
description: 用 Oracle 的 GPT-5.6 Pro 浏览器链路对代码、Skill、设计或文档做一次独立复核。
disable-model-invocation: true
---

# call-oracle

把 Oracle 当作独立顾问：提交最小充分上下文，取得建议，再由当前 Agent 对照本地事实判断。此入口不安装、升级或维修 Oracle，也不代替本地验证。

## 调用

1. 明确复核问题、只读边界、目标平台和期望输出；Oracle 不继承当前会话上下文。
2. 选择能回答问题的最小充分文件集。排除 `.env`、密钥、令牌、浏览器资料及无关大目录；只有经用户授权且已脱敏时才附带敏感材料。
3. 用 `oracle status --hours 24` 检查近期任务；同一问题已有运行中或可恢复 session 时续接，不创建重复任务。
4. 默认执行 GPT-5.6 Sol 的 Pro 浏览器链路：

```powershell
oracle --engine browser --browser-transport cdp `
  --model gpt-5-pro --browser-thinking-time pro `
  --prompt "<6-30 句、可独立理解的复核任务>" `
  --file "<path-or-glob>" --slug "<3-5-words>" --wait --no-notify
```

`gpt-5-pro` 是 Oracle 在浏览器模式下选择 GPT-5.6 Sol / Pro 的稳定别名。只有用户明确要求基础 Sol 时才改用 `gpt-5.6-sol`；不要把 API 的 `--reasoning-effort high` 混入浏览器 Pro 链路，也不要静默更换模型、档位、引擎、传输或账号。

普通复核直接调用；仅当文件范围可能过大或不确定时，先用 `oracle --dry-run summary --files-report` 检查 bundle。

## 恢复与边界

- 超时、detached 或输出中断时，从 CLI 返回的 slug/ID 执行 `oracle session <id> --render`；先恢复，后判断，避免重发。
- receipt/commit/prompt identity 不确定时，把结果标为不确定并停止。仅在 Oracle 明确报告已保留且允许 harvest 时使用相应恢复命令。
- Pro 不可确认、额度受限或浏览器链路失败时原样报告；由用户决定是否改变档位或通道。
- Batch、API 计费调用、安装升级、浏览器 heal/reconcile 等高级操作超出此薄入口；先查看 `oracle --help --verbose` 和 Oracle 包内的权威 `skills/oracle/SKILL.md`。

## 返回

简要给出 Oracle 的结论与 findings、当前 Agent 的本地核验判断、session slug/会话证据，以及尚未确认的风险。Oracle 意见是审阅输入，不是完成或正确性的证明。
