# Router Contract

`discuss_router.py` 只选择 workflow、participants，并转发调用 agent 已选定的 Claude effort；它不定义模型 identity、participant role、prompt、permission 或业务流程语义。

| Setting | Default | Accepted values | Effect |
| --- | --- | --- | --- |
| `--mode` | `ledger` | `ledger`, `blind`, `combined` | Select normal discussion, independent discovery, or Blind Opening followed by normal Ledger. |
| `--agents` | `codex,claude` | `full`, or exactly two distinct names from `codex`, `claude`, `grok` | Select participants independently of the workflow. `full` expands to `codex,claude,grok`. |
| `--claude-effort` | `low` | `low`, `medium` | 将调用 agent 按规模选择的 Claude effort 转发到所有阶段；participants 不含 Claude 时忽略。 |

The Router dispatches without changing the selected workflow's semantics:

- `ledger` → `discuss_orchestrator.py`; `--max-rounds` defaults to five full participant cycles.
- `blind` → `blind_opening.py`; it writes only the independent-opening artifacts.
- `combined` → `blind_opening_then_ledger.py`; it runs Blind Opening, then hands its consolidated points to the unchanged Ledger workflow.

调用 agent 先判断规模：跨模块/系统、迁移或 cutover、权限/数据正确性/recovery、多阶段交付属于大计划，选择 `medium`；单模块、聚焦修订、短文档或窄决策属于小计划，选择 `low`。默认 `low` 只用于兼容未升级的直接脚本调用，不替代 agent 的显式判断。

Use the lower-level scripts only when a caller deliberately needs their implementation-level flexibility. The public Router rejects one-participant and literal three-participant lists so its externally visible choices remain “default pair”, “an explicit pair”, or `full`.
