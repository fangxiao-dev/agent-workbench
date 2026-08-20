# 处境协议迁回 Python 侧

本文件记录本次迁移的分阶段证据。阶段状态分别表示盘点、迁移、DSH 改造、验证和提交，不把上游阶段误记为整个任务完成。

## S1 盘点（已完成，2026-08-20）

### 协议表和 API 引用

当前 DSH 源表是 `plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/protocols.json`，实测包含 62 个键：`_comment`、`default` 和 60 个 slug 条目。Python 目标文件 `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/protocols.json` 在盘点时尚不存在。

按 `protocols.json`、`resolveProtocol`、`loadProtocols`、`protocolsFile` 做固定字符串审计，相关引用如下：

| 位置 | 当前职责 | 后续处理 |
| --- | --- | --- |
| `plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/protocols.json` | DSH 本地协议表 | S2 原样迁移（两条 review 片段改为占位符），S3 删除 |
| `plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/situation-hook.mjs:40-64,255-256,287` | 配置 `protocolsFile`，加载并按 slug 解析协议 | S3 删除本地加载/解析，改读 `render.selected.protocol` |
| `plugin-marketplace/plugins/dsh-impl-package/test/coverage-check.mjs:6-9` | 直接读取 DSH 表检查 slug 覆盖 | S3 改读 Python 侧表 |
| `plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs:10,86-100` | 导入加载/解析 API，检查加载、fallback、覆盖和消息拼接 | S3 删除 API 测试，改验证 render 输出中的 protocol 与消息注入 |
| `plugin-marketplace/plugins/dsh-impl-package/README.md:15,36,103` | 描述 DSH preset 内协议表 | S3 同步为 Python 侧唯一表及 render 输出 |
| `plugin-marketplace/plugins/dsh-impl-package/baseline-skill-sizes.md:89,91,93,97,153` | 记录协议承接位置 | S3 同步协议表归属 |
| `plugin-marketplace/plugins/dsh-impl-package/review-checklist.md:41` | 检查处境指针与协议 slug 一致 | S3 改为 Python 侧协议表 |

`agent.cordis.yml` 中没有 `protocolsFile` 或协议表加载配置注释；因此 S3 不会凭空添加改动，只保留现有通用 hook 配置注释。

仓库中其他命中 `protocols` 的内容是通用英文词或无关数据（例如 typography 数据），不是本协议表/API 引用，未纳入迁移范围。

盘点还确认 `situations.yaml` 有 59 个 slug，而协议表有 60 个显式 slug；额外的 `ticket.readiness.evidence-lane-preflight` 属于源表内容，按本任务“原样搬运”要求保留，不能因 coverage 目前只检查缺失而删掉。

### `as_json()` 输出影响面和 digest 边界

`plugin-marketplace/plugins/impl-package/scripts/situation.py:306` 的 `Candidate.as_json()` 被 `_derive()` 用于 `selected`、`parallel_matches`、`other_matches`、`suppressed_matches` 和 `matches`。本次只新增候选级 `protocol` 字段；`situations.yaml` 的推导、候选排序和分组不变。

`_digest_candidate()`（同文件约 2965 行）是白名单投影，只读取 `slug`、`subject`、`layer`、`action_ids`。因此 `protocol` 不参与 digest；必须以 fixture render 实测守住这一点，不能为 digest 变化修改期望。

受影响或用于回归的测试边界：

- `tests/test_situation_render.py` 的 52 个 `tests/fixtures/situations/*/expected.json` 参数化用例：逐个复核 primary/layer/secondary/suppressed/undetermined，期望文件全部不变。
- 同文件的 `test_rotated_trail_uses_current_file_only`、`test_cli_written_trail_rows_are_renderable`、`test_escape_event_and_legacy_escape_decision_are_read`、`test_human_render_collapses_undetermined_and_supports_since`、`test_render_writes_situation_digest_credential`、`test_render_since_writes_situation_digest_credential`、`test_render_succeeds_when_situation_digest_credential_cannot_be_written`、`test_compaction_pressure_is_high_low_or_unknown_without_fact_channel`、`test_json_render_exposes_digest_and_short_circuits_since`：验证 render 结构/副作用/digest，protocol 增加不应改变既有断言。
- `tests/test_dispatch_audit.py` 的 `test_normal_digest_is_checked_against_replayed_action`、`test_action_outside_replayed_situation_is_deviation`、`test_replay_calls_situation_at_json`：间接消费 render 的 digest/action 白名单；应保持通过。
- `tests/test_impl_package_state.py` 的 situation-digest 凭据与 `trail append` 闸门用例不读取候选 JSON，但属于本次指定的直接回归集；尤其不能因缺 digest 自动补 render。
- DSH 的 `smoke-test.mjs` 和 `coverage-check.mjs` 会从旧表/API 断言切换到 Python render 输出，是 S3 的契约测试边界。

### S1 结论

证据足够进入 S2。保留的硬边界是：只新增 `protocol` 输出；不改任何 `situations.yaml` 推导逻辑、`_digest_candidate` 白名单、`impl_package_state.py` stdout 或 `trail append` 缺少 `situation_digest` 时的闸门；render 协议表加载失败必须降级为空 default 且不阻断渲染。

## S2 迁移（已完成，2026-08-20）

### 实现

- 新增 `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/protocols.json`，按 DSH 源表逐键迁移，保留 `_comment`、`default` 和额外的 `ticket.readiness.evidence-lane-preflight`。
- 在 `situation.py` 增加模块级协议加载：文件缺失、读取/JSON 失败、JSON 根值或任意值类型不符合要求、review 占位符缺失时统一返回 `{"default": ""}`；模块导入时只加载一次，candidate 不逐个读盘。
- `Candidate.as_json()` 新增 `protocol`，已知 slug 取表值，未知 slug 使用 default；该字段随 `selected` 等候选 JSON 一起进入 render。
- 两条 review 协议片段使用 `{review_phase_values}` / `{review_track_values}` 占位符。展开值来自 `situation.py` 已有的 `REVIEW_PHASE_VALUES` / `REVIEW_TRACK_VALUES`；`engine.py` 已直接从该模块导入同一组常量，因此没有第二份合法值字面量。加载时断言两条协议都携带两个占位符，展开后断言不残留占位符；断言失败同样降级 default。

### S2 方案选择

选择“静态 JSON 占位符 + `situation.py` 一次替换”，没有把合法值复制进 JSON。原因是 JSON 不能引用 Python 常量，而现有 `engine.py` 的常量实际由 `situation.py` 提供；沿用该依赖方向既保持 engine 与 render 一份真相，又避免循环导入。

### 证据

- Python 语法检查通过。
- 新旧协议表逐键 parity 检查通过：除两条按设计增加占位符的 review 片段外，所有键和值原样一致；源表键数为 62（60 个 slug 加 `_comment`/`default`）。
- 协议 smoke 显示两条片段已展开为 `initial | finding-closure | terminal-final` 与 `Track A | Track B | Track C | Track D`，无未消费占位符。
- 临时文件测试覆盖非法 JSON、`default` 非字符串和数组根值，均返回 `{"default": ""}`。
- 独立 checkpoint reviewer：`PASS`；P0/P1 findings `none`；residual gaps `none`。
- `_digest_candidate` 未修改，下一阶段仍需用实际 render 验证 digest 不变。

## S3 DSH 改造（已完成，2026-08-20）

### 实现

- `plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/situation-hook.mjs` 删除 `protocolsFile` 默认配置、`loadProtocols`、`resolveProtocol` 及本地文件读取；`agent/pre-step` 现在直接把 `fresh.render?.selected?.protocol` 传给 `composeSituationMessage`。
- 删除 DSH preset 的 `presets/impl-package/protocols.json`，规则只保留在 Python 侧；`agent.cordis.yml` 原本没有 `protocolsFile` 注释或覆盖项，无需制造空改动。
- `coverage-check.mjs` 和 `smoke-test.mjs` 的协议表路径改为 `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/protocols.json`；smoke 还验证实际 render 的 `selected.protocol` 和消息组装的协议行。
- DSH README、baseline 和 review checklist 的旧 DSH 本地表描述同步改为 Python 侧唯一表/`render.selected.protocol`；未触碰 `situations.yaml`。

### S3 证据

- `node plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs`：`ALL PASS`；实际注入消息含 `协议: 恢复：读 progress.md ...`。
- `node plugin-marketplace/plugins/dsh-impl-package/test/coverage-check.mjs`：`59` 个 situations slug、`59` 个显式覆盖、`0` 个 uncovered。
- 作用域固定字符串审计：无残留 `resolveProtocol`、`loadProtocols`、`protocolsFile` 或旧 DSH 本地协议表路径引用。

## S4 验证（已完成，2026-08-20，由主 session 补收）

Codex 作业在 S4 撞满 1800s 超时，S1–S3 已落盘，代码改动全部留在工作区且未提交。以下读数由主 session 独立实测，不采信作业自述。

### 1. digest 不变（本次改动的前提）

```
python .../situation.py render --package tests/fixtures/situations/p0-session-resumed \
  --validation-result '{"projection_drift":false,"source":"x"}' --json
→ digest = a1c00c2605f7   （改动前同值）
→ selected.protocol = "恢复：读 progress.md 的 current Attempt / activeCheckpoints，沿 checkpoint 的 next 动作继续；不读 state.json 全文。"
```

`_digest_candidate()` 的白名单投影假设成立：新增 `protocol` 字段不进 digest。

### 2. expected.json 逐个复核

`git status --short tests/fixtures/situations/` 除一个未跟踪的 `situation-digest.json`（render 副作用凭据，本就存在且按设计保持未跟踪）外无任何输出。**52 个 expected.json 全部未变**，无需逐条解释。

### 3. 词表一份真相

`REVIEW_PHASE_VALUES` / `REVIEW_TRACK_VALUES` 定义在 `situation.py:42-43`；`engine.py:26-28` 从该模块 import。`protocols.json` 中两条 review 片段使用 `{review_phase_values}` / `{review_track_values}` 占位符，无第二份字面量。依赖方向 situation.py → engine.py，无循环导入。

### 4. DSH 契约测试

- `node .../test/smoke-test.mjs` → `ALL PASS`
- `node .../test/coverage-check.mjs` → slugs 59 / covered 59 / uncovered 0

### 5. 全量 pytest

`python -m pytest tests/ -q` → **7 failed, 363 passed in 475.11s**。

这 7 个失败**与本次改动无关，是既有红**。验证方法：把本次全部改动 stash 后在干净 HEAD 上重跑同样四个测试文件，得到**完全相同的 7 个失败**：

```
tests/test_backfill_stable_docs_router.py::test_paths_and_versions_use_the_lightweight_contract
tests/test_req_align_contract.py::test_req_align_is_public_router_with_internal_decision_and_spec_subskills
tests/test_req_align_contract.py::test_spec_gate_and_planning_backstop_enforce_contract_completion
tests/test_req_align_contract.py::test_touched_spec_requires_contract_design_but_untouched_legacy_is_not_migrated
tests/test_standing_bookkeeper_contract.py::test_standing_bookkeeper_entry_and_role_are_complete
tests/test_standing_bookkeeper_contract.py::test_package_writers_delegate_physical_mutation_without_moving_semantic_ownership
tests/test_ticket_first_contract.py::TicketFirstContractTests::test_stage_a_docs_mark_legacy_task_and_checkpoint_boundaries
```

直接原因是 SKILL 合并后被删除的文件仍被契约测试引用，例如
`FileNotFoundError: plugin-marketplace/plugins/impl-package/skills/create-task-dag/SKILL.md`。
来源是 `4e53faa`（19 SKILL → 14），该 commit message 自述“契约测试更新匹配新结构……全绿”，与全量实测不符。**这是一笔独立的既有欠账，不在本次范围内修。**

### S4 结论

本次改动的验收标准全部达成：digest 不变、expected.json 零改动、词表一份真相、DSH 契约测试绿。全量套件的 7 个红是 `4e53faa` 遗留，需另开一次清理。
