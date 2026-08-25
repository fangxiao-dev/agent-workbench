# Material Review Gate

shared seam、安全、数据完整性、并发、migration、权限、不可逆外部副作用或 Plan/policy 明确要求时，当前 Topic 所属的 Ticket 需要独立 review。SDD 只判断并上报这个 requirement；review 的触发时机、topology、comparison point 和 finding closure 完全由 dev-with-track 既有的 Ticket-level 触发点与 `/impl-package:do-review` 拥有，SDD 不再自行调度或区分审查阶段。若一个 Topic 大到必须在完成前中途止损，回到 Step 1 收窄 Topic 边界，不要另开一次审查。

work lane 的 `DONE` 在 required review 完成前保持 `PENDING_REVIEW`；独立 review lane PASS 后才成为 `PASSED`。

review lane 始终独立于 work lane。同一 Topic 的 reviewer 可以承担 finding recheck；review scope 实质变化、独立性失效或 Topic 已闭合时退役并重新选择 reviewer。finding 默认回到同 Topic work lane 修复；只有 scope/ownership 实质变化、上下文不可采信或需要全新视角时更换 worker。

完成标准：material risk Topic 已标记其所属 Ticket 需要 review，`PENDING_REVIEW` 未被压成 PASS，reviewer 与 implementer 保持独立。
