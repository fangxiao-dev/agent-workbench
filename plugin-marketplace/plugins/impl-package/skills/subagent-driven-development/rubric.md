---
target: plugin-marketplace/plugins/impl-package/skills/subagent-driven-development
updated: 2026-08-12
---
## 原则

- [待验证] SDD 只拥有主 session/subagent 分层、单轴 scheduling 和共享资源顺序；Impl-Package 的实现/验证委派硬路由到 bounded dispatch。（证据: R1, R2, R5）
- [待验证] scheduling contract 使用条件化最小输出；共享资源字段只在实际存在时出现，不为所有调度建立固定七字段协议。（证据: R2）
- [待验证] 下游委派路由只在 Impl-Package router 与 SDD 保留权威定义，其他活跃入口只指向 SDD。（证据: R2）
- [待验证] 每个 bounded unit 默认使用 fresh subagent；只有同一 source unit 的不可转移连续状态或显式 standing role 才记录并复用 worker identity。（证据: R3）
- [待验证] scheduling 只有 `LOCAL | SERIAL | PARALLEL | BLOCKED`：单个委派单元为 `SERIAL`，`LOCAL` 只用于有事实理由的原子、紧耦合或不可隔离操作。（证据: R4, R5）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-08-11（调度器降载）

- 采纳将 SDD 收敛为调度合同 owner，并删除与调查和具体 worker 派发重复的决定 — 用户明确同意“降载 3 者，同时明确各自的任务，并且把配置分流到更合理的地方”。

### R2 · 2026-08-11（二次降载审计）

- 采纳把固定七字段 scheduling contract 压缩为 mode、执行形态和 route；batch/resource/cleanup 只在相关分支输出。
- 采纳让 AGENTS、dev-with-track、thread-harness 与 handoff 只指向 SDD，不再复制 Plan/Ticket/DAG 的 dispatch 条件。

### R3 · 2026-08-11（subagent 生命周期）

- 采纳 bounded unit 使用 fresh subagent 作为默认语义；`SERIAL` 与 `default-long` 只描述顺序和 mode，不隐含 worker identity 复用。
- 采纳复用必须由同一 source unit 的不可转移 live state 或下游 standing role 显式证明；context compaction 后从 canonical input 启动 fresh subagent — 用户确认：同意，GO。

### R4 · 2026-08-12（default-long 与 LOCAL 不变量）

- 采纳 `default-long ⇒ SERIAL/PARALLEL` 与 `LOCAL ⇒ ordinary + reason`，消除长任务模式与本地执行形态混用造成的执行归属歧义 — 用户批准 0.2.7 闭环修复计划。

### R5 · 2026-08-12（单轴 Scheduling）

- 采纳删除 `default-long | ordinary` mode 轴，把委派、本地、并行与阻塞压缩为唯一 scheduling 决定；保留历史记录中的旧术语，但活跃合同和调用方不再复制 mode。
