# Material Review Gate

shared seam（改动是否改变多个执行方共同依赖的接口、协议、模块边界或集成边界，使一方可影响另一方的行为？）、安全（改动是否改变身份、信任边界或敏感数据暴露，使未授权路径可能获得新能力？）、数据完整性（改动是否可能让已写入的数据丢失、重复、错配、越界或无法恢复到正确状态？）、并发（改动是否涉及同一份可变状态被多个执行路径同时读写的顺序？）、migration（改动是否会改变已经落地数据的 schema 或语义，而不只是新增代码路径？）、权限（改动是否改变谁可以执行某个动作、读取某类数据或触发某项外部副作用？）、不可逆外部副作用（效果是否没法靠重跑或回滚撤销，例如发信、扣费、写外部系统？）或 Plan/policy 明确要求时，当前 Topic 所属的 Ticket 需要独立 review。SDD 只判断并上报这个 requirement；review 的触发时机、topology、comparison point 和 finding closure 完全由 dev-with-track 既有的 Ticket-level 触发点与 `/impl-package:do-review` 拥有，SDD 不再自行调度或区分审查阶段。

work lane 的 `DONE` 在 required review 完成前保持 `PENDING_REVIEW`；独立 review lane PASS 后才成为 `PASSED`。

review lane 始终独立于 work lane；reviewer 的复用与退役按 SKILL.md Step 4 的 review lane lifecycle，本文件不另立条件。finding 默认回到同 Topic work lane 修复；只有 scope/ownership 实质变化、上下文不可采信或需要全新视角时更换 worker。

完成标准：material risk Topic 已标记其所属 Ticket 需要 review，`PENDING_REVIEW` 未被压成 PASS，reviewer 与 implementer 保持独立。
