# CLI-written trail

状态：阶段 1、阶段 2 已落盘并实测成立；阶段 3 的显式 `recovery checkpoint --handoff`
入口已落盘，最终回归见 `escape-shape-and-rotation-hook.md`。

## 阶段 1：CLI 追加轨迹行

实际 mutation 位于 `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py`；顶层 `impl_package_state.py` 只负责路由，未改变其参数解析、stdout JSON 或退出码。

### 设计结论

1. **kind**

   - `recovery checkpoint` 使用既有历史 `kind=checkpoint`，并带 `checkpoint=true`、`subject`、checkpoint 的 `next/blocker/evidence`。
   - `ticket satisfy` / `ticket retire` 使用既有规范 `kind=result`，并带 `transition=ticket-state`、`from`、`to`、`outcome`。`result` 是现有 schema 中唯一能表达 subject + outcome 的既有事件形状；不新增 mutation kind，也不把 Ticket state 冒充成 fact key。

2. **写失败**

   state JSON 写入并刷新 projection 成功后才尝试追加 trail。追加捕获普通异常，只向 stderr 输出 warning；不回滚 state，不改变命令成功返回的 JSON 或退出码。state 是权威，trail 是观察记录。

3. **幂等**

   `satisfy/retire` 的 `--expect` 保护和已有终态重试逻辑保持不变；没有新的 state transition 就不追加。checkpoint 继续保持原有 stdout `idempotent=false` 语义，但活动 trail 内对相同 `subject/kind/事件字段/head` 做语义去重；同样的 checkpoint 重复调用不会制造重复边界行。不同 next、不同 head 或中间已有其它事件时仍可形成新的边界行。

4. **轮换位置（历史阶段 1 结论）**

   阶段 1 不在普通 `recovery checkpoint` 中轮换。checkpoint 也用于 BLOCKED、retry 和普通恢复记录，不等于 handoff；每次普通 checkpoint 都轮换会过于频繁，并反复要求重新声明仍成立的 fact。轮换由显式 `recovery checkpoint --handoff` / 边界调用承担；pressure-driven `attempt.record.handoff-due` 仍独立存在。

### fixture 实测

构造 ticket-first fixture，依次运行 `recovery checkpoint` 与 `ticket satisfy` 后，`execution/initial/trail.jsonl` 实际新增行如下（原文）：

```jsonl
{"blocker":null,"checkpoint":true,"evidence":["evidence.md"],"head":"1125dd70849bfd504dcfafb6fe1215d741bb2847","kind":"checkpoint","next":"run source test","seq":1,"subject":"attempt","ts":"2026-08-17T15:55:45.202310Z","v":1}
{"from":"PENDING","head":"1125dd70849bfd504dcfafb6fe1215d741bb2847","kind":"result","outcome":"SATISFIED","seq":2,"subject":"ticket:TKT-01","to":"SATISFIED","transition":"ticket-state","ts":"2026-08-17T15:56:31.941425Z","v":1}
```

阶段 1 focused 验证：

- `test_cli_mutations_append_trail_rows_and_dedupe_repeated_checkpoint`：通过。
- `test_trail_append_failure_does_not_fail_ticket_mutation`：通过。
- 两个测试均同时覆盖 CLI 真实 subprocess 初始化/状态 mutation；失败注入覆盖 state 已提交但 trail append 抛错的路径。

## 阶段 2：Ticket 边界交接与轮换触发

阶段 1 的结论成立后，加入一个 derived when-key（不是 fact key）：
`trail.last_ticket_terminal_transition`。它只读取当前活动 `trail.jsonl`，在 attempt scope
扫描 Ticket subject 的 `kind=result`、`transition=ticket-state` 状态转换，取最后一条并判断
`to/outcome` 是否为 `SATISFIED` 或 `RETIRED`。缺失/空 trail 和没有转换都是已知 false，坏 trail
仍是 unknown；这样既不会对历史无轨迹 package 凭空建议交接，也不改变既有 fixture 的
undetermined 期望值。没有新增 fact key、gate 或常驻进程。

P1 新增两条相互独立的处境行：

- `attempt.record.ticket-boundary-handoff`：终态转换后仍有 `PENDING` Ticket，表达“此处适合在下一个 Ticket 前交接”。
- `attempt.record.trail-rotation-due`：同一机械窗口，表达“该交接必须执行活动 trail 轮换”。

两行均不读取 `attempt.compaction_pressure_high`，所以与既有 pressure-driven
`attempt.record.handoff-due` 是机会与需求的两条独立输入，不互相 AND。轮换仍是 handoff
动作的显式步骤：按 trail schema 原样归档当前 `trail.jsonl` 并新建活动文件；普通
`recovery checkpoint` 不轮换。

阶段 2 验证：

- `python plugin-marketplace/plugins/impl-package/scripts/situation.py check`：PASS，59 situations / 68 implemented when keys / 6 priority groups。
- 临时 fixture 的 `kind=result + transition=ticket-state + pending Ticket` render 命中两条新 P1 行。
- `python -m pytest tests/test_situation_render.py -q`：57 passed，未修改任何既有 fixture 的 expected.json。

最终指定回归仍需在阶段 2 closure 运行；整个任务在此之前不宣称 closed。

## 阶段 3：显式交接 checkpoint 入口

`recovery checkpoint --handoff` 是普通 checkpoint 的显式交接变体。state 写入和已有
checkpoint trail 记录完成后，CLI 将活动 `trail.jsonl` 原样归档为下一个 `trail.NNN.jsonl`，
创建新的活动文件，并写一条 `kind=handoff`、`subject`、`checkpoint:true` 和当前 checkpoint
payload 的记录。普通 checkpoint 不轮换。轮换或 handoff 记录失败只写 warning；state 不回滚，
命令 stdout JSON、退出码和既有 `--expect` 语义不变。
