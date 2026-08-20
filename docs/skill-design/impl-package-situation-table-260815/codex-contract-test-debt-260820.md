# 4e53faa 遗留契约测试红处理记录

## S1 分类

基线命令：

```text
python -m pytest tests/test_backfill_stable_docs_router.py tests/test_req_align_contract.py tests/test_standing_bookkeeper_contract.py tests/test_ticket_first_contract.py -q
```

实测结果：`7 failed, 9 passed`。失败逐项分类如下；分类针对断言所验证的契约，不只针对 traceback 中出现的文件名。

| 失败测试 | 断言内容与直接原因 | 分类 | 判定依据与处置 |
| --- | --- | --- | --- |
| `test_backfill_stable_docs_router.py::test_paths_and_versions_use_the_lightweight_contract` | 入口 `backfill-stable-docs/SKILL.md` 不再含 `仓库相对路径`、`target Git commit`；前者由当前 config schema 的 path 约束承接，后者在 `references/verify-runbook.md`，测试仍只读入口。 | A | 路径/版本契约仍成立，且没有被取消；只是机械约束下沉到当前轻量载体。把测试引用指向 schema 与 verify runbook，并继续保留 `package-retirement` 禁止断言，不削弱契约。 |
| `test_req_align_contract.py::test_req_align_is_public_router_with_internal_decision_and_spec_subskills` | `req-align/SKILL.md` 仍列 `full`、`decision-only`、`spec-only`，但降载时删除了两个内部 `SUB-SKILL` 的显式路径与公共入口的语义 owner 说明；对应子技能文件仍存在。 | C | 公共 router 仍需要告诉跨宿主调用者如何到达内部 Decision/Spec，并明确主 thread 保留 contract/Gate/采信权；这些判断没有在新 router 或宿主无关引用中得到等价承接。按 parent 原文补回压缩后的链接与 owner 边界，测试继续保持原断言。 |
| `test_req_align_contract.py::test_spec_gate_and_planning_backstop_enforce_contract_completion` | `impl-planning/SKILL.md` 把原来的 `不得创建或更新 Plan/state`、`不得在 Plan 中补第二套 DTO/schema` 压成 `不创建/更新...`、`不在...`，虽然有暗示但丢失了 parent 的 fail-closed canonical wording。 | C | 这是 planning 的判断边界，不能只靠更短的否定缩写承接；按 parent 原文恢复为一条压缩但明确的 `不得...` 启发式，测试继续检查全部行为维度、Spec Gate 迁移依据和两条 backstop 规则。 |
| `test_req_align_contract.py::test_touched_spec_requires_contract_design_but_untouched_legacy_is_not_migrated` | `req-align/SKILL.md` 不再重复 `未触及的 legacy Spec` 与 `每个新建或被修订的 Spec`；同一契约仍在 `references/package-lifecycle.md` 与 Spec sub-skill，但公共 router 本身没有保留该入口判断。 | C | lifecycle/sub-skill 的存在不能替代公共入口对“新建/修订才补、未触及 legacy 不迁移”的路由判断；按 parent 原文补回一条压缩规则，保留测试原断言。 |
| `test_standing_bookkeeper_contract.py::test_standing_bookkeeper_entry_and_role_are_complete` | `skills/standing-bookkeeper/SKILL.md` 与其 `references/role.md` 被删除，导致入口/角色文件断言直接 `is_file()` 失败；异常 slow path 已合并到 `skills/execution-boundaries/`。 | B | 独立 standing-bookkeeper 入口是有意撤销的，职责形态改为 execution-boundaries 的异常边界。测试改查合并后的 entry/role，保留 slow-path、唯一 state writer、回执和 focused validation 等语义断言；独立 skill name 的 eval 断言不再适用并删除。 |
| `test_standing_bookkeeper_contract.py::test_package_writers_delegate_physical_mutation_without_moving_semantic_ownership` | `to-tickets/SKILL.md` 已因与 `impl-planning` 合并而不存在；同一测试后续还要求 callers 明确写出 package writer 的物理写入与主 thread 语义 ownership。 | B（直接路径）+ C（语义缺口） | 独立 `to-tickets` 载体的消失属于有意合并，测试改查 `impl-planning` 的 Ticket-split 部分；但合并后的 planning SKILL 没有保留 parent 中明确的“不直接编辑 Plan/state”和“Ticket 文件/运行时 state 由 writer 执行”判断，需按原文压缩回补。所有 callers 的 bound route 同步指向 execution-boundaries，不能靠放宽断言掩盖旧路径。 |
| `test_ticket_first_contract.py::TicketFirstContractTests::test_stage_a_docs_mark_legacy_task_and_checkpoint_boundaries` | 测试读取被合并删除的 `skills/create-task-dag/SKILL.md`；当前 `skills/impl-package/SKILL.md` 已承接 legacy Task/DAG 只读、迁移和 `DONE` 不等于 acceptance，但 `impl-planning/SKILL.md` 的“新 package 不调用 create-task-dag”子断言也曾被删掉。 | A（路径）+ C（planning 子断言） | legacy Task/DAG 契约的主载体迁到 impl-package router，测试改读新 carrier并保持更强边界断言；planning 仍是实际计划入口，故按 parent 原文补回其禁止调用与只读迁移判断。 |

### S1 处置边界

- 只修改本表涉及的 contract tests、`impl-package` 下直接承接契约的 SKILL 文本，以及本记录；不修改 `situations.yaml`、runtime/state 实现、DSH preset、`call-grok` 相关改动。
- C 类优先以 `git show 4e53faa^:<原路径>` 对照恢复，再压成当前一条一行的判断启发式；不把 DSH preset 当作跨宿主承接。

## S2 处置

已按 S1 分类实施：

- A：`test_backfill_stable_docs_router.py` 改为读取当前 repository-config schema 的 path deny rule 与 `references/verify-runbook.md` 的 target Git commit 检查；Stage A 测试改读合并后的 `skills/impl-package/SKILL.md`，并继续检查 legacy Task/DAG 的只读与 acceptance 边界。
- B：standing bookkeeper 入口/角色测试改读 `skills/execution-boundaries/` 的合并 entry/role；移除仅针对已撤销 standalone `skill_name` 的 eval 断言。`to-tickets` caller 改由合并后的 `impl-planning` Ticket-split 语义承接。
- C：从 `4e53faa^` 对照压缩回补 req-align 的 Decision/Spec sub-skill 路由、contract/Gate/最终采信权、Spec/legacy 补齐规则；回补 impl-planning 的 fail-closed `不得...` backstop、Plan/state 与 Ticket writer ownership，以及 legacy `create-task-dag` 禁用边界；回补 plan-review 的 bound writer 物理应用语义。
- 合并后的 package writers 与 dev-with-track caller 已从 standalone `standing-bookkeeper` 路由更新为 `/impl-package:execution-boundaries`；未修改 `situations.yaml`、runtime/state、DSH preset 和 `call-grok` 相关文件。

定向验收（S2 后）：`16 passed, 1 warning`；warning 为 pytest 无法写入受权限限制的 `.pytest_cache`，不是测试失败。

## S3 验证

定向测试已通过；全量 `python -m pytest tests/ -q` 待运行并记录。
