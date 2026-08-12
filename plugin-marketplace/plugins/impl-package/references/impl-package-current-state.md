# Impl-Package Current State 3.4

Impl-Package 只持久化会改变下一动作、阻止 false PASS 或约束危险 mutation 的状态。`formatVersion: "3.4"` 是当前文件格式标识，不建立 schema、兼容读取器或迁移账本。Git commit ID 是唯一版本锚点。

## 1. 文件与事实源

```text
<package>/
├─ progress.md
├─ execution/
│  └─ <attempt>/
│     ├─ execution-record.md
│     └─ task-handoffs/
│        └─ <task-id>-handoff.md
├─ .impl-package/state.json
└─ gate.md
```

- `.impl-package/state.json`：Task、Ticket、resume 的唯一可写 current-state 事实源。
- `execution/<attempt>/execution-record.md`：该 Attempt 无法从 state、Git 或验证产物推导的 checkpoint 与 judgment。
- Task Handoff：条件式、可更新的局部接手材料，不是状态或历史账本。
- `progress.md`、Ticket Runtime Acceptance、DAG Runtime State 都是 machine-owned projection。
- `gate.md`：当前 Gate 判决；旧判决由 Git 历史保留。

Ticket/Task 只是 Execution Record 的 subject；不创建 Ticket 专属 ER。根目录不创建 execution index，`progress.md` 的 Attempt History 提供历史导航。

## 2. Current State

```json
{
  "formatVersion": "3.4",
  "attempt": {"id": "initial", "plan": "docs/implementations/260806-topic/plan.md"},
  "tasks": {"T1": {"state": "PENDING", "evidence": null}},
  "tickets": {"TKT-01": {"state": "PENDING", "evidence": null}},
  "resume": {"blocker": null, "next": null, "evidence": null}
}
```

所有持久化路径必须是仓库相对 POSIX 路径，可带 `#anchor`；拒绝绝对路径、`..`、不存在的 evidence 和 wildcard。package 使用不可变的日期前缀目录名。D/S/P 仅在 Markdown 中作为可选别名；不因别名变化阻断当前 package，Git commit 负责历史比较。

### 状态词汇

- Task：`PENDING | READY | RUNNING | BLOCKED | FAILED | NEEDS-REVALIDATION | DONE | WAIVED | SUPERSEDED`
- Ticket：`PENDING | BLOCKED | NEEDS-REVALIDATION | SATISFIED | WAIVED | SUPERSEDED`
- 非 `PENDING` 状态必须给出直接 evidence。
- Task `DONE` 只表示局部产出可集成，不自动改变 Ticket。
- `READY/RUNNING` 的 Task 必须已释放 DAG dependency；Ticket `SATISFIED` 前必须释放 implementation/acceptance dependency。
- plan 变化只把实际受影响的记录设为 `NEEDS-REVALIDATION`。

状态变更采用 CAS-lite：调用者必须提供 `--expect`。相同目标与 evidence 的重试是幂等操作；旧状态不符时拒绝。terminal Gate 后禁止修改该 Attempt 的 state、resume 和 Execution Record。

## 3. Execution Record 与 Handoff

`execution/<attempt>/execution-record.md` 每个 Attempt 一个文件。记录 ID 为 `<attempt>-ER-001`，purpose 仅允许：

- `checkpoint`：可恢复边界，必须有 `nextAction`；同 subject 的新 checkpoint 取代旧 active checkpoint。
- `judgment`：执行期 decision、finding disposition、failure learning 或外部证据解释。

subject 为 `attempt | ticket:<id> | task:<id>`。旧记录正文保留，但不使用 seal、内容身份、receipt 或审计链。重复规范化 payload 通过字段比较识别。

Task Handoff 位于 `execution/<attempt>/task-handoffs/<task-id>-handoff.md`，仅在 BLOCKED、retry、跨 session/owner 或并行委派时创建。它可更新，terminal 后不再修改；长期判断由主 session 提炼进 Execution Record。

## 4. Progress

`progress.md` 是 current Attempt 的统一恢复入口，由 `refresh-progress` 重建，包含：

1. Attempt、可选别名、Composition、lifecycle 和 current Gate；
2. blockers 与 resume next action；
3. Ticket Acceptance 与 Task Execution 两条独立状态轴；
4. active Attempt 的 checkpoint 与 Handoff/evidence 指针；terminal Gate 后历史 checkpoint 只保留在 Execution Record，不再显示为 active；
5. 只含 Attempt、Lifecycle、Gate、Execution Record 链接的轻量历史表。

Progress 不复制历史正文、不计算百分比，也不推导或授权 readiness。

## 5. CLI

`<impl-package-plugin-root>` 是当前已加载插件的根目录，由 skill 所在路径解析；不得假设 workbench 源路径或宿主缓存路径。

```text
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> init --attempt <id> --plan <repo-relative-plan>
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> status [--commit <git-commit>]
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> validate [--commit <git-commit>]
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> refresh-progress
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> set-state <task|ticket> <id> <state> --expect <state> [--evidence <path>]
printf '<json>' | python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> er-add
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> checkpoint --next <text> [--blocker <text>] [--evidence <path>]
python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> gate <verdict> --comparison-commit <git-commit> --reason <text> [--evidence <path>] [--durable-delta <text> | --no-durable-delta-reason <text>]
```

`init` 先验证 Plan/Ticket/DAG bundle，只导入当前 Attempt 的 Ticket/Task，发布 Draft Ticket，并创建 state、Execution Record 和全部投影。`refresh-progress` 修复 Ticket/DAG/Progress 投影，不改变业务状态。

`er-add` 从 stdin 接收 `purpose`、可选 `subject`、`title`、`content`、checkpoint 的 `nextAction` 和可选 evidence。`checkpoint` 是 attempt-level 的便捷封装，并同步更新 resume。

## 6. Gate

Gate 只适用于 current Attempt：`blocked` 保持 active；`pass | fail | defer` 终结并冻结。首次写入 terminal Gate 时，comparison commit 必须等于命令执行时的 Git `HEAD`；同 verdict/commit 的幂等重试可在后续 HEAD 上修复旧的 terminal resume/投影，但不能改写判决或重新开放 Attempt。terminal Gate 清空 resume，`pass` 要求所有 earned Task/Ticket 已进入可接受终态。terminal Gate 必须记录 Durable Delta，或显式给出无 delta 原因；存在 `execution-findings.md` 时必须在 evidence 中完成分流引用。

新工作在 terminal 后创建 patch Attempt。冻结 Attempt 继续按其 Plan/Ticket/DAG bundle 自洽校验，不因后来修改的 current `decision.md`/`spec.md` aliases 失效；新 Attempt 也只把这些 aliases 作为可选展示信息。初始化新 Attempt 时，旧 Attempt 的 Execution Record 固化 lifecycle/Gate 摘要，根 `progress.md` 切换到新 Attempt并保留轻量历史链接。
