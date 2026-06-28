# HITL Pull-Forward Review

把 HITL 当成可提前消化的阻塞风险，而不是默认保留到执行期。Issue 审查时必须逐项判断：这个 HITL 是否能通过现在的 owner 决策、standing authorization packet、默认安全策略或 POC scope 降级提前解决。

## Categories

对每个 HITL / gate / external-side-effect slice，分类为：

- **Pull forward**：现在能给出清晰推荐和替代项，用户一旦批准，后续 issue 可按 `ready-for-agent` 执行，不再逐轮停等。例：destructive POC reset scope、real-write 默认不跑、read-only external smoke policy、audit sink 选择、UI 验收 oracle 来自 spec/prototype/browser evidence。
- **Convert to validation gate**：不需要人工批准，只需要 agent 提供证据。例：Gate A / Gate B / final regression、browser screenshot / viewport / console evidence、test-case registry checks。
- **Simplify overdesign**：如果当前环境是 POC / fixture / disposable data，主动建议删除 production-grade migration/audit ceremony，改为 local JSON seed、reset/apply、stub/read-only verification 或更小的 tracer-bullet。
- **Keep HITL**：只有 live owner input 不能提前决定时才保留。例：production/customer-data mutation, secret/credential not available, legal/compliance/business choice not encoded in the spec, or real external write without an approved profile / allowlist / rollback policy。

## Decision Packet

Pull-forward 决策包必须说明：

- recommendation。
- alternatives rejected。
- risk tradeoff。
- future permissions/environment values。
- what remains excluded。
- issue label/gate changes。

用户批准后，把对应 issue 从 HITL 改成 AFK / `ready-for-agent`，并在父计划记录 standing authorization scope。未批准或信息不足时，保留为 explicit remaining owner decision。
