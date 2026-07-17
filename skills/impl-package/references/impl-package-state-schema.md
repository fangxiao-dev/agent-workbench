# Impl-Package 结构化状态契约

状态：schema gate 已通过，进入实现与验证阶段。

## 1. 边界与事实源

`.impl-package/` 只保存脚本无需理解业务即可写入和校验的 package-local 状态与指针。Acceptance Semantics、设计选择、执行策略、verdict reason、review findings、残余风险和 Durable Deltas 继续以 Markdown 为事实源，不进入 JSON。

package 目录由调用方通过 `--package <path>` 显式指定；脚本不假定 implementations root。package ID 是不可变、带日期前缀的 slug，日期格式由项目约定，不锁死为六位或八位。

结构化层由两个文件组成：

- `.impl-package/revision-bindings.json`：D/S/P current selection 与 append-only blob binding。
- `.impl-package/runtime-state.json`：package identity、task/ticket current state、append-only artifact chain、gate number allocator 与 finalized gate index。

Markdown 中由脚本维护的内容只是 JSON 的可读投影，不是第二个机器事实源。JSON 不保存 `published`、`validatedAgainstHead`、derived lifecycle、readiness 或其他可现场推导且会过期的状态。

## 2. Revision bindings schema v2

`revision-bindings.json` 使用 [`../assets/templates/revision-bindings.json`](../assets/templates/revision-bindings.json) 的 v2 形状。

- `current.design`、`current.spec` 与 `current.attempt` 选择当前 alias、artifact 和 attempt；current 可更新。
- `bindings[]` append-only。每条 binding 的 `id` 由 revision identity 与 blob OID 确定；重复登记同一 binding 是幂等 no-op。
- semantic revision 追加新 alias 的 binding；projection/editorial rebinding 追加同 alias binding，并用 `supersedes` 指向被替代 binding。历史记录不覆盖、不复用、不物理删除。
- 对同一 revision identity，未被其他记录 supersede 的 terminal binding 必须唯一；缺失或多于一个均为 validate failure。
- `evidence` 只保存 rebinding 判断或发布记录的 Markdown pointer，不复制理由正文。

`id` 的 canonical 形式为：design/spec 使用 `<revision>@<blob>`；plan 使用 `<attempt>:<revision>@<blob>`。同一输入必须得到同一 ID。

## 3. Runtime state schema v1

`runtime-state.json` 使用 [`../assets/templates/runtime-state.json`](../assets/templates/runtime-state.json) 的 v1 形状。

### 3.1 Package 与 task/ticket current state

- `packageId` 保存不可变 package identity；必须与初始化时显式给出的 ID 一致，后续命令不得改名。
- `tasks[]` 与 `tickets[]` 每个 `<attempt,id>` 只保存一个 current record：`state` 与最后一次 transition 的 `evidence` pointer。
- transition 采用 CAS-lite：调用必须提供 `--attempt` 与 `--expect <previous-state|absent>`；current attempt 或 previous state 不符时拒绝。它用于 stale-transition 防护，不承诺 multi-writer concurrency safety。
- JSON 不保存 transition log。Git 提供已提交 JSON snapshots 的 provenance；需要长期保留的执行判断与证据继续进入 ER/gate。

task record 的 canonical shape 为 `{attempt,id,state,evidence}`，四个字段均为非空 string。`state` 只能是 `PENDING | READY | RUNNING | NEEDS_SEAM | BLOCKED | FAILED | NEEDS-REVALIDATION | DONE | WAIVED | SUPERSEDED`。只有 current plan 的 `dag=true` 时才允许当前 attempt 的 task record；current attempt 的 records 与 DAG task 必须按 ID 构成 bijection，每个 earned task 恰有一个 record，初始化值从唯一 DAG task projection 机械导入（新 task 为 `PENDING`）。JSON state/evidence 是机器 SoT，DAG Runtime State 表是 marker 投影。`dag=false` 时当前 attempt 不得存在 task record，恢复仍使用 contract 已定义的 attempt/ticket progress ledger。

ticket record 的 canonical shape 同样为 `{attempt,id,state,evidence}`，四个字段均为非空 string。`state` 只能是 `UNRECORDED | IN_PROGRESS | BLOCKED | NEEDS-REVALIDATION | SATISFIED | WAIVED | SUPERSEDED`。只有 current plan 的 `tickets=true` 时才允许当前 attempt 的 ticket record；current attempt 的 records 与 earned ticket files 必须按 Ticket ID 构成 bijection，每个 earned ticket 恰有一个 record，初始化值从唯一 ticket Runtime Acceptance Status projection 机械导入（尚无判断时为 `UNRECORDED`）。JSON state/evidence 是机器 SoT，ticket Runtime Acceptance Status 与 DAG ticket table 是 marker 投影。ticket publication status 不进入 runtime JSON。

旧 attempt 的 record 可以保留但不可再由 `set-state` 修改；current attempt 已有 terminal gate 后也必须拒绝 transition。状态是否 dependency-releasing、ticket 是否真正满足 Acceptance Semantics 仍由共享 contract 和 review evidence 判断，脚本只校验 vocabulary、引用与 projection。

### 3.2 Artifact chain

`artifacts[]` append-only，并使用稳定 `id`。每条记录必须有 `recordType` discriminator，且所有未适用字段显式为 `null`，避免消费者自行猜测 shape。

- `recordType=artifact` 的 canonical shape 为 `{recordType,id,kind,path,hash,supersedes,tombstones,evidence}`：`id/kind/path/evidence` 为非空 string，`hash={algorithm,value}` 且 v1 只允许 `algorithm=sha256` 与 64 位小写十六进制 value，`supersedes` 为 artifact ID string 数组，`tombstones=null`。
- artifact identity 只由 hash 与 append-only record ID 确定；`path` 只是 provenance hint。外部交付物可使用 package/repository 之外的路径，该路径允许跨机器失效，消费者不得用 path 存在性或可解析性替代 hash identity。
- 新 artifact 可通过 `supersedes` 指向一个或多个 active artifact。
- `recordType=tombstone` 使用同一字段集合：`id/evidence` 为非空 string，`kind/path/hash=null`，`supersedes=[]`，`tombstones` 为被撤销 artifact/tombstone ID。不得删除或覆盖旧记录。
- 同一命令重复提交完全相同的 record/tombstone 是幂等 no-op；同 ID 内容不同必须失败。
- ER 只写 artifact delta 与本清单 pointer，不重复投影完整 hash 清单。

每个 `supersedes`/`tombstones` pointer 必须解析到同一文件内更早的唯一记录；不得自指、前向引用或形成环。一个 artifact 是否 active 由 append-only chain 现场推导，不另存 status。

### 3.3 Gate allocator 与 finalized index

- 下一个 G number 现场推导为该 attempt `1 + max(allocations.number)`，没有 allocation 时为 1；不另存 counter。崩溃可以留下编号空洞，G id 只要求单调、唯一，不要求连续。
- `gate.allocations[]` append-only，canonical shape 为 `{operationId,attempt,number,entryId}`；字段均为非空 string，唯 `number` 为正整数。`operationId` 由 caller 为一次逻辑分配稳定提供，在 package 内唯一；`entryId` 必须严格等于 `<attempt>-G<number>`，attempt/number/entryId 组合全局唯一。相同 operationId 重试返回原 entryId 并补建缺失 scaffold，不再次分配编号。每个 finalized entry 必须解析到唯一 matching allocation，且 id/attempt/number 完全一致。
- `gate.entries[]` 只保存 finalized entry，append-only；未完成 scaffold 不进入 entries。
- finalized entry 的 canonical shape 为 `{id,attempt,number,verdict,supersedes,entry}`。`id/attempt/verdict` 为非空 string，`number` 为正整数，`verdict` 只能是 `pass | fail | blocked | defer`，`supersedes` 为 gate entry ID 或 `null`；`entry={path,anchor,bindingMode,contentSha256}`，其中 `path=gate.md`、`anchor=id`、`bindingMode=gate-entry-v1`、contentSha256 为 64 位小写十六进制。
- `gate-entry-v1` 对从目标 `## <gate-id> · <verdict>` heading 开始、到下一个同级 `##` heading 前结束的完整 entry block 计算 SHA-256；读取时统一 CRLF/CR 为 LF、移除 UTF-8 BOM，并确保恰好一个结尾 LF。新 entry 插到文件顶部不会改变历史 entry binding。
- `finalize-gate-entry` 必须从绑定 Markdown block 反解并逐字段核对 index 的 id、attempt、number、verdict 与 supersedes；任一字段不符即 mismatch，不能直接信任 JSON verdict。verdict reason 与 Durable Deltas 只留在 Markdown。
- gate pointer 必须是规范化后仍位于显式 package root 内的 package-relative `gate.md`，并指向该 package 唯一 gate ledger；禁止 absolute path、`..` escape、symlink escape 或跨 package pointer。content hash 不能替代该 identity 检查。
- `new-gate-entry --operation-id <id>` 只分配编号并生成 scaffold；`finalize-gate-entry` 在 Markdown 判断写完后校验 block、计算 content binding 并追加 immutable index。finalize 前 Markdown 已出现 verdict 但 JSON 无对应 finalized entry 时，消费方必须报告 mismatch/manual。

## 4. 两相 revision 发布与 validate context

跨 Git、JSON 与 Markdown 不宣称事务原子性，也不新增 persisted published/unpublished 状态。

1. `register-revision` 对最终 worktree artifact 使用 Git path filters 计算 blob OID，原子替换 JSON，并立即执行 working-tree validation。
2. artifact 与 JSON 可进入同一 commit。
3. restore、ER append 与 gate evaluation 使用 committed validation，对 `HEAD:<package-relative-path>` 现场求值；是否已经对 HEAD 验证不落盘。

`validate --working-tree` 检查 JSON 与当前 worktree 内容、schema、链、投影和 plan contract；它允许 HEAD 尚未包含新 binding。`validate --committed` 除同一组检查外，还要求 current D/S/P binding 与 HEAD 内容相符。stage 调用点不得使用无上下文的模糊 validate：register/rebind/refresh 后用 working-tree，restore/ER/gate 前用 committed。

所有 JSON 写入使用同目录临时文件、flush 后 replace；重复调用必须得到相同结果。init、binding/artifact/finalize 使用确定性 identity；`set-state` 在 current state/evidence 已等于目标时先返回幂等 no-op，再检查旧 expectation；gate allocator 使用稳定 operationId。v1 执行模型是单写者，subagent 不拥有 runtime ledger；不使用 package-local lock，也不承诺 multi-writer lost-update protection。

## 5. Projection ownership 与 rebinding

机器投影必须位于成对 marker 内：

```markdown
<!-- impl-package:projection <name> begin -->
<machine-owned body>
<!-- impl-package:projection <name> end -->
```

v1 marker name 至少包括 `revision-set`、`runtime-state` 与 `gate-status`。同一 artifact 内 name 唯一；缺 marker、重复、嵌套、顺序错误或 body 无法从 JSON 重建均为 validate failure。

`refresh-projections` 只能改 marker body。自动 projection rebinding 前，脚本从 active binding baseline 与当前 artifact 中排除允许追加的 ER 区域及 marker body；marker 外仍有 diff 时必须拒绝，并返回 owning skill 做 S/P revision 或 editorial correction 判断。

只有 owning skill 已证明 `contract impact=none` 后，显式 `rebind --reason editorial --evidence <pointer> --confirm-contract-impact-none` 才能接受 marker 外 editorial diff；脚本不替代语义判断。`rebind --reason projection` 只接受 marker 内 diff，不能成为语义变化的洗白通道。

ER 的 Revision set 表示该 ER 写入时的 current D/S/P set。plan header 的 revision-set 投影表示当前 set；S/D 的机械刷新走 projection rebind，不升级 P。

## 6. Gate 消费四类结果

当 `gate.md` 存在时，消费方必须把 gate 识别为以下四类之一，并把 recognition kind、可信 `gateResolution` 与人工路由分开：

1. `indexed`：JSON finalized index 存在，目标 entry 唯一，content binding 匹配，且 index 的 id/attempt/number/verdict/supersedes 与 Markdown 反解值一致；`gateResolution=<verdict>`，无需人工路由。
2. `legacy-heading`：整个 package 没有 runtime-state JSON，旧 gate heading 可解析；`gateResolution=<verdict>` 并标 legacy，无需人工路由。
3. `mismatch`：JSON 存在但损坏、缺 entry、entry 缺失/重复、pointer 越界、content/字段 binding 不符、JSON 陈旧或无法解析；`gateResolution=null`、`needsManualGateReview=true`，不得 fallback 信任 heading。
4. `manual`：gate.md 存在、整个 package 没有 runtime-state JSON、且无合法 legacy heading；`gateResolution=null`、`needsManualGateReview=true`。

没有 `gate.md` 时 `hasGate=false`、`gateRecognition=null`、`gateResolution=null`，表示 attempt 尚无 verdict；它不是第五种 recognition result，也不默认等于人工异常。若某个消费动作本身要求 terminal gate，应由该动作正常判定未满足前提。

这四类是 compatibility result，不是新的 package lifecycle。backfill、retirement 与 verify 可以投影结果，但不得把 `mismatch` 降级成 legacy success。backfill inventory 因新增 `gateRecognition`、`gateResolution` 与 mismatch/manual 计数升到 schemaVersion 4；旧 `gateVerdictParsed` 等字段只可作为派生兼容投影，不能继续作为内部判断依据。识别可信度与 `_pending.md` 引用资格正交，referenced package 的 mismatch/manual 不得被抑制。

## 7. Schema migration

revision-bindings v1 仍可由 `validate` 以 legacy compatibility mode 只读解析：每个旧 binding 视为该 alias 的唯一 terminal binding，并继续执行原 exact-blob/plan-contract-v1 检查；结果必须报告 `migrationRequired=true`。除显式 migration 外，其他 mutating command 遇到 v1 必须拒绝。

`migrate --evidence <pointer>` 将 v1 原子转换为 v2：为现有记录生成 deterministic ID，设 `supersedes=null`，写入同一 migration evidence pointer，保持 current 与 blob 不变，然后执行 working-tree validation。相同输入与 evidence 重复运行是幂等 no-op；v1 缺字段、重复 alias/path 或 binding 本身无法验证时迁移失败且原文件保持不变。v2 不提供 downgrade。

runtime-state 不存在表示 legacy package，`init` 显式创建 v1；不得把 absence 当损坏。未知更高 schemaVersion 必须 fail closed，不得猜测字段。

## 8. v1 CLI contract

单文件、Python 标准库、显式 package path：

```text
impl_package_state.py --package <path> init --package-id <id>
impl_package_state.py --package <path> migrate --evidence <pointer>
impl_package_state.py --package <path> validate --working-tree|--committed
impl_package_state.py --package <path> register-revision <design|spec|plan> <alias> [--attempt <id>] --evidence <pointer>
impl_package_state.py --package <path> rebind <alias> --reason <projection|editorial> --evidence <pointer> [--confirm-contract-impact-none]
impl_package_state.py --package <path> refresh-projections
impl_package_state.py --package <path> set-state <task|ticket> <id> <state> --attempt <id> --expect <state|absent> --evidence <pointer>
impl_package_state.py --package <path> record-artifact <id> <path> --kind <kind> --evidence <pointer>
impl_package_state.py --package <path> supersede-artifact <old-id> <new-id> <path> --kind <kind> --evidence <pointer>
impl_package_state.py --package <path> tombstone-artifact <id> --target <artifact-id> --evidence <pointer>
impl_package_state.py --package <path> new-gate-entry --attempt <id> --operation-id <id>
impl_package_state.py --package <path> finalize-gate-entry <gate-id>
```

命令可以增加纯输出选项，但不得静默推断 package root、current attempt、previous state、editorial judgment 或 verdict reason。

CLI 的数据策略来自 skill-owned [`../assets/impl-package-state-config.json`](../assets/impl-package-state-config.json)。配置只承载 vocabulary、artifact discovery、字段及 gate heading grammar、marker 名称与 projection format；脚本自动按自身 skill 位置加载，不接受调用方任意覆盖 canonical policy。配置使用独立 `schemaVersion`，并对 placeholder、capture group 与单行 heading 范围 fail closed。完整 gate entry span、append-only、identity/content binding、active backward chain、CAS、package-local path、HEAD/worktree context 与 earned-artifact bijection 保持为代码内不可配置不变量。

## 9. Schema gate acceptance

实施脚本前必须确认：

- 没有 persisted published/validated 状态；working-tree 与 committed validate 调用点明确。
- 写入是 atomic replace、幂等、CAS-lite；single-writer 是 contract，multi-writer 不在 v1 保证内。
- projection marker/allowlist 明确，marker 外 diff 不能自动 rebind。
- gate index 绑定完整 entry，reserve/finalize 分离，mismatch 进入 manual。
- revision/artifact/gate 历史 append-only；task/ticket 只存 current + last evidence，未复制 transition ledger。
- fixtures 覆盖 legacy、schema migration、损坏/部分写入、projection drift、idempotence、stale expectation、含空格路径、CRLF/LF 和 gate 四类结果；并发写 fixture 只验证 atomic replace 不产生半截 JSON，不宣称 lost-update protection；DATEV 只用于后续副本演练。
