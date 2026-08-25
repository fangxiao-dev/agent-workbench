# Material Review Gate

shared seam、安全、数据完整性、并发、migration、权限、不可逆外部副作用或 Plan/policy 明确要求时，当前 Topic 需要独立 review。SDD 只确定 requirement 与局部边界：中间 material seam 使用 `checkpoint`，Topic 收口使用 `closure`；review topology、comparison point、finding closure 和 terminal review 由 `/impl-package:do-review` 拥有。

work lane 的 `DONE` 在 required review 完成前保持 `PENDING_REVIEW`；独立 review lane PASS 后才成为 `PASSED`。checkpoint PASS 只释放当前 Topic 的下一步，不支持 Ticket/package 完成声明。

review lane 始终独立于 work lane。同一 Topic 的 reviewer 可以承担 finding recheck；review scope 实质变化、独立性失效或 Topic 已闭合时退役并重新选择 reviewer。finding 默认回到同 Topic work lane 修复；只有 scope/ownership 实质变化、上下文不可采信或需要全新视角时更换 worker。

完成标准：material risk 有明确 `checkpoint|closure` 边界，`PENDING_REVIEW` 未被压成 PASS，reviewer 与 implementer 保持独立。
