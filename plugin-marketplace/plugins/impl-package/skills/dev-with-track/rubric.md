# Dev With Track Rubric

## Confirmed preferences

- `state.json` 是 current state 的唯一来源；Progress 与 runtime tables 是投影。
- 旧 Task completion 不等于 Ticket acceptance；新 package 不创建 Task 状态。
- Evidence 使用存在的仓库相对路径；Gate 保存 current verdict，Git 保存历史。
- 只 revalidate 被实际 contract/plan 变化影响的子集。
- terminal Gate 冻结执行时 Git HEAD 并清空 active checkpoint；历史 judgment 留在 frozen Execution Record。
- do-review 拥有 formal review topology、coverage 和 finding closure；dev-with-track 判断业务 requirement 并消费报告。
- `$dispatcher` 是唯一通用执行协作入口；本 Skill 提供业务重点、相关剩余工作范围、typed dependency、授权与 acceptance，并消费其局部结果。
- Dispatcher idle、worker `DONE` 与 review `PASSED` 是局部事实；本 Skill依据 canonical Ticket/State/Evidence/Gate 判断 closure。
- 业务控制循环先恢复 canonical facts 和候选范围，再调用 Dispatcher，随后消费结果并写 package 权威状态。
- finding 的等级、disposition、影响范围和期限归本 Skill；修复安排由 Dispatcher 按影响与资源选择。
- shared seam、安全、数据完整性、并发、migration、权限、不可逆外部副作用七类 material risk 产生 formal review requirement。
- 每个代码 return 的 delta review 节拍归 Dispatcher；本 Skill只消费结果，不克隆派审规则。
- 候选清单只辅助恢复与审计；missing/stale 不阻塞按当前业务事实重算出的合法工作，旧显式 blocker 保留到最新清单更新。

## 2026-09-08 consolidation

- Owner 批准把 Dispatcher 与 SDD 合并为单一 model-invoked 入口。
- 业务循环从“唯一下一动作”改为“交付重点 + 相关剩余工作范围”，避免局部等待缩窄整个 Attempt；持久候选清单仅作辅助。
- finding 可立即修、随相关工作修或隔离并行修；review 来源不再固定安排。
- SDD material review gate 的七类启发式迁入本 Skill，formal topology 与 closure 继续归 do-review。
