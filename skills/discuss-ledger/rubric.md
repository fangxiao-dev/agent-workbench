---
target: skills/discuss-ledger
updated: 2026-11-03
---
## 原则

- [待验证] Ledger 只服务多方、多轮或明确讨论；普通单轮 review 和 subagent findings handoff 直接交付，不创建讨论 artifact。（证据: R1）
- [待验证] Claude 用默认最新 `sonnet`/`high`，Codex 用其默认 `sol`/`high`，不写具体模型版本号，也不按规模分级，也不提供 effort 开关。（证据: R3，取代 R2）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-15

- 采纳「单轮不建 ledger」— 用户明确要求 review 去重，单轮 review/subagent handoff 不得为了记录而升级为讨论流程。

### R2 · 2026-07-30

- 采纳「Claude effort 按计划规模分级」— 用户原话：改成 low/medium agent 自己选择，大计划用 medium，小计划 low。

### R3 · 2026-11-03

- 采纳「模型固定为默认最新 sonnet/high 与 sol/high，不指定版本号」— 用户原话：模型就提示用默认最新的 sonnet/high 以及 sol/high，但是不指定具体模型版本号。取代 R2 的 low/medium 分级。
