---
target: plugin-marketplace/plugins/impl-package/skills/subagent-driven-development
updated: 2026-08-11
---
## 原则

- [待验证] SDD 只拥有主 session/subagent 分层、mode、batch 和共享资源顺序；Impl-Package 的实现/验证委派硬路由到 bounded dispatch。（证据: R1, R2）
- [待验证] scheduling contract 使用条件化最小输出；共享资源字段只在实际存在时出现，不为所有调度建立固定七字段协议。（证据: R2）
- [待验证] 下游委派路由只在 Impl-Package router 与 SDD 保留权威定义，其他活跃入口只指向 SDD。（证据: R2）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-08-11（调度器降载）

- 采纳将 SDD 收敛为调度合同 owner，并删除与调查和具体 worker 派发重复的决定 — 用户明确同意“降载 3 者，同时明确各自的任务，并且把配置分流到更合理的地方”。

### R2 · 2026-08-11（二次降载审计）

- 采纳把固定七字段 scheduling contract 压缩为 mode、执行形态和 route；batch/resource/cleanup 只在相关分支输出。
- 采纳让 AGENTS、dev-with-track、thread-harness 与 handoff 只指向 SDD，不再复制 Plan/Ticket/DAG 的 dispatch 条件。
