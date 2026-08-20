# Codex 状态命令处境尾注

本文件记录本任务的 S1–S4 阶段证据。各阶段只在完成并落盘后进入下一阶段；上游 `e4ccede` 已提供 `selected.protocol`，本任务只接写入 CLI 的尾注触发链。

## S1 盘点（已完成，2026-08-20）

### 状态变更子命令与出口点

`impl_package_state.py` 是薄路由器，`main()` 在 `scripts/impl_package_state.py:82-88` 将命令交给 `impl_package_runtime.command_groups.main()`。实际统一 stdout/退出码出口是 `command_groups.py:15-22` 的 `_emit()`；各命令在 `_run()` (`145-163`) 映射到 engine：

| 触发范围（冻结清单） | `_run()` 映射 | engine 写入函数 | 当前统一出口 |
| --- | --- | --- | --- |
| `ticket transition`、`satisfy`、`block`、`needs-revalidation`、`pending`、`retire` | `_ticket_transition()` | `command_set_state()` | `_emit()` |
| `evidence add` | `command_evidence_add()` | `command_evidence_add()` | `_emit()` |
| `evidence invalidate` | `command_evidence_invalidate()` | `command_evidence_invalidate()` | `_emit()` |
| `recovery checkpoint` | `command_checkpoint()` | `command_checkpoint()` | `_emit()` |
| `recovery judgment` | `command_er_add()` | `command_er_add()` → `_add_judgment()` | `_emit()` |
| `gate pass`、`fail`、`defer`、`blocked` | `command_gate()` | `command_gate()` | `_emit()` |
| `trail append` | `command_trail_append()` | `command_trail_append()` | `_emit()` |
| `package validate` | `command_validate()` | `command_validate()`；异常时 `_emit()` 返回 1 | `_emit()`，成功和异常路径都需尝试尾注 |

`package init`、`package refresh-progress` 和只读别名 `package status` 不在本任务冻结的触发清单内；本实现不扩大触发范围。`package validate` 虽不是普通状态写入，因它是 session 入口且必须覆盖退出码 0/非 0，单独纳入。

写后顺序的关键事实：ticket/evidence/checkpoint/gate 的 engine 函数先写 `.impl-package/state.json`（或相关 execution 文件）再返回；`trail append` 先追加事件再返回。因此尾注必须放在 `_emit()` 已取得结果并输出 JSON 之后调用 render，凭据读取到的是新 state。

### `test_impl_package_state.py` stdout 爆炸半径清单

现有测试通过 `ImplPackageStateTests.cli()` 启动真实 subprocess；其 `result.stdout` 也被错误信息回退和 `init()` helper 消费。直接断言或解析 stdout 的用例如下（行号为盘点时基线）：

| 用例 | stdout 断言/消费 |
| --- | --- |
| `test_checkpoint_overwrites_state_and_er_accepts_judgment_only` | 两次 checkpoint 解析 JSON；judgment 断言 `recordId` |
| `test_handoff_checkpoint_rotates_only_with_flag_and_records_handoff` | ordinary/handoff 两次断言 JSON key 集合 |
| `test_cli_mutations_append_trail_rows_and_dedupe_repeated_checkpoint` | checkpoint、ticket satisfy、ticket retire 的 JSON key/idempotent 断言 |
| `test_trail_append_assigns_sequence_and_common_fields` | fact/dispatch 两次解析 JSON 并断言 `appended` |
| `test_trail_append_non_dispatch_kinds_do_not_require_situation_digest` | 三种 kind 的 stdout JSON `appended` 断言 |
| `test_trail_append_failure_returns_nonzero` | 直接捕获并断言 stdout 为空 |
| `test_retired_is_terminal_and_identical_retry_is_idempotent` | retire/retry 的 `idempotent` 断言 |
| `test_needs_revalidation_invalidates_selected_claims_only` | needs-revalidation JSON 的 `claims` 与 `invalidatedEvidence` 断言 |
| `test_blocked_retains_direct_evidence_and_does_not_enter_ready` | validate stdout JSON 的 `readyTickets` 断言 |
| `test_gate_checks_release_edges_and_clears_active_checkpoints` | gate stdout JSON 的 `verdict` 断言 |

另外，`init()` helper (`49-56`) 每个使用它的测试都会解析 `package init` stdout；`cli()` (`49-53`) 在失败回退消息中读取 stdout，`test_trail_append_failure_does_not_fail_ticket_mutation` 则直接调用 engine，不经过 CLI stdout。测试默认关闭新尾注即可保持这些 JSON 断言不变。

### 进程内 render 可行性

入口在 `scripts/impl_package_state.py` 启动时把 `scripts/` 放入 `sys.path`，随后 `command_groups` 导入 `engine`；`engine.py:23-30` 已从同目录的 `situation` 导入 `REVIEW_*` 常量。因此 `command_groups` 可以复用已加载的 `situation` 模块，调用其 `main(["render", "--package", ..., "--json"])` 并在进程内捕获 render 的 stdout/stderr，再解析 JSON。该路径不 spawn Python；render 将继续通过既有 `_run_render()` 写 `execution/<attempt>/situation-digest.json`，`selected.protocol` 来自 `Candidate.as_json()`。若调用抛出异常或返回非 0，尾注 helper 返回空值，主命令结果保持不变。

### S1 结论

证据足够进入 S2：改动集中在 `command_groups.py` 的统一出口和 `impl_package_state.py` 的 flag 路由；不触碰 `situations.yaml`、`_digest_candidate`、DSH hook 或 dispatch 缺 digest 闸门。下一阶段实现尾注、写后 render、两个关闭开关和异常隔离。

## S2 实现（已完成，2026-08-20）

### 实现内容

- `command_groups._emit()` 现在先执行状态命令，再输出原有 JSON；成功后才调用 `_situation_footer()`，所以凭据读取的是写入后的 `state.json`。
- `package validate` 同时设置成功和异常尾注路径；因此既有 validate 的 stdout/stderr 与退出码保持原语义，render 只在主命令返回后作为 best-effort 尾注尝试。
- `_situation_footer()` 进程内调用已加载的 `situation.main(["render", "--package", ..., "--json"])`，捕获 render 的 stdout/stderr，解析 `selected.protocol`、候选动作和计数后拼成紧凑尾注；没有 subprocess。
- footer helper 捕获所有普通异常、非 0 返回和 JSON 解析失败，返回空值；这不会追加任何 render 输出，也不会改变主命令已有 stdout 或退出码。
- `impl_package_state.py` 在根路由剥离 `--no-situation` 并传入 grouped CLI；`command_groups.main()` 也接受该 flag，环境变量 `IMPL_PACKAGE_NO_SITUATION=1` 与命令行 flag 任一命中都关闭尾注。

### S2 直接检查

- `python -m py_compile plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py` → exit 0。
- `git diff --check -- plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py` → 无 whitespace error（仅 Git 报告工作区换行格式提示）。

### S2 结论

实现已具备写后 render、宿主无关 stdout 载体、关闭开关和异常隔离；进入 S3 为测试默认关闭、显式打开新增行为用例，并添加 fixture 凭据 ignore 规则。

## S3 测试与卫生（已完成，2026-08-20）

### 测试与开关

- 新建 `tests/conftest.py`，pytest collection 时默认设置 `IMPL_PACKAGE_NO_SITUATION=1`，旧的 JSON stdout 断言无需改写。
- `test_situation_footer_covers_each_trigger_class` 显式打开尾注，分别覆盖 ticket、evidence、recovery、gate、trail append 和 package validate，并断言 12 位 digest 与协议行。
- `test_situation_credential_hashes_state_after_mutation` 显式打开尾注，比较凭据 `state_sha256` 与写入后的 `.impl-package/state.json` sha256。
- `test_render_failure_does_not_change_success_or_stdout` 注入 render 异常，确认主命令仍返回 0、stdout 仍是原 JSON、无尾注且无异常泄漏。
- `test_package_validate_appends_footer_on_nonzero_exit` 注入 validate 的既有 StateError，确认退出码仍为 1，同时仍尝试输出尾注。
- `test_no_situation_flag_and_environment_switch_each_disable_footer` 在环境变量置 0 时验证 CLI flag，在环境变量置 1 时验证环境开关；两者分别关闭尾注。

直接检查：

- `python -m pytest tests/test_impl_package_state.py -q -k "situation_credential or render_failure or package_validate or no_situation" -s` → `6 passed, 27 deselected`。
- `python -m pytest tests/test_impl_package_state.py -q -k situation_footer -s` → `1 passed, 32 deselected`。
- `git diff --check -- .gitignore tests/conftest.py tests/test_impl_package_state.py` → 无 whitespace error。

### fixture 卫生

`.gitignore` 新增 `/tests/fixtures/situations/**/situation-digest.json`，只覆盖 fixtures 下的情况包凭据，不覆盖真实 package 的 `execution/<attempt>/situation-digest.json`。实测：

```text
git check-ignore -v tests/fixtures/situations/p0-session-resumed/execution/fixture-attempt/situation-digest.json
→ .gitignore:35:/tests/fixtures/situations/**/situation-digest.json
git status --short tests/fixtures/situations/
→ 无输出
```

### S3 结论

新行为和卫生边界已有直接回归证据；进入 S4，必须在足够 timeout 下运行用户指定的三文件 pytest、DSH smoke、一次 fixture 手工写入并记录实际尾注全文，再做 fixture 状态复核。

## S4 验证（已完成，2026-08-20）

### 1. 指定 pytest

命令：

```text
python -m pytest tests/test_impl_package_state.py tests/test_situation_render.py tests/test_dispatch_audit.py -q
```

结果：`112 passed, 1 warning in 373.80s (0:06:13)`。唯一 warning 是当前环境无法创建 `.pytest_cache` 的权限 warning；没有测试失败。

### 2. DSH smoke

命令：

```text
node plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs
```

结果：`ALL PASS`。该 smoke 实际验证 Python render 的 `selected.protocol`，未改动 `situation-hook.mjs`。

### 3. 手工 fixture 写入与尾注原文

为避免修改仓库内受版本控制的 fixture 文件，将 `tests/fixtures/impl-package-ticket-first` 复制到被 `.test-tmp/` 忽略的临时 Git fixture package，初始化后执行：

```text
python plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py \
  --package .test-tmp/codex-ticket-footer-fixture-260820/docs/implementations/20260820-footer-fixture \
  recovery checkpoint --next "manual footer verification" --evidence evidence.md
```

命令返回 0；以下是 stdout 尾部实际原文（digest 为本次 render 写入凭据的 12 位值）：

```text
[处境] digest=e1207a59f117 · attempt.record.session-resumed · basis=prose · judgment=false
动作:
  - restore-checkpoint（默认）: /impl-package:dev-with-track restore from active checkpoint — 不读取完整历史
并列匹配: 0 | 未判定: 48 | 未匹配: 0
协议: 恢复：读 progress.md 的 current Attempt / activeCheckpoints，沿 checkpoint 的 next 动作继续；不读 state.json 全文。
```

### 4. fixture 状态复核

命令：

```text
git status --short tests/fixtures/situations/
```

结果：无输出；被 ignore 的 `situation-digest.json` 没有把 fixture 凭据暴露为工作区改动，`expected.json` 未变。

### S4 结论

本任务四项指定验证均有直接证据；尾注通过进程内调用 `situation.main(... --json)` 实现，未 spawn 新 Python 进程。进入最终 diff 审计和 main 提交。
