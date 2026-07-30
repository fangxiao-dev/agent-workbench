# Orchestrated Auto-Discussion

Use this reference before invoking `scripts/discuss_orchestrator.py`.

## Critical Timeout Rule

`--timeout-s` is a per-agent, per-call timeout, not the overall orchestration timeout. When invoking the orchestrator through a tool wrapper, set the wrapper/tool timeout high enough for the whole run:

```text
agent_count * max_rounds * timeout_s + buffer
```

For the default `--agents codex,claude`, `--max-rounds 5`, and `--timeout-s 300`, use at least 3600 seconds as the outer tool timeout. If the wrapper timeout is lower, the orchestrator can still be killed even when `--timeout-s` was passed correctly.

## When To Run

If the user asks for `组织审核`, `discuss orchestrator`, `自动讨论`, "Codex 作为 orchestrator", or asks to "用 discuss 审" a target, do not perform a normal single-agent review. Run the local orchestrator unless the user explicitly asks for manual ledger editing.

Use the target project root and topic/document from the request. If both are clear, start without asking for confirmation:

```bash
python <skill>/scripts/discuss_orchestrator.py --root <target-project-root> --topic <target-doc-or-topic>
```

调用前按目标规模显式传 `--claude-effort low|medium`。大计划使用 `medium`，小计划使用 `low`；判断规则见 [router.md](router.md)。该参数只控制 Claude reasoning effort，不固定 Claude model。

When the user gives a target file path, infer the project root before running. Prefer the nearest ancestor containing `.git` as `--root`, and pass the target path relative to that root as `--topic`. This works for ordinary clones, Git worktrees, `.worktrees/<name>/...`, and other checkout layouts.

If the script is available, rely on `discuss_orchestrator.py`'s built-in root/topic resolution rather than hand-normalizing the path.

默认值为 `--agents codex,claude`、`--max-rounds 5`、`--timeout-s 300`，兼容性 fallback 为 `--claude-effort low`。一轮表示每位 participant 各发言一次；调用前按上面的 Critical Timeout Rule 为外层工具设置足够的总超时。

After the orchestrator stops, report:

- ledger path
- convergence summary
- open/deadlocked points
- whether user裁决 is needed
- **观点评估**: briefly judge the discussion quality, the findings that materially changed the outcome, weak spots in coverage/evidence, and whether continued discussion is useful or the next step should be revising the target followed by focused review.

## Claude Availability

When Claude Code / `claude -p` reports auth/login, hangs, or looks unavailable while the user says they are already logged in, read `references/claude-code-noninteractive.md` before declaring Claude unavailable.
