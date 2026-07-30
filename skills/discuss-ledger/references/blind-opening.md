# Blind Opening

Use Blind Opening for independent multi-party exploration: brainstorming candidate solutions, discovering risks, or widening a design space before any participant sees another participant's opinion. Do not use it when the user specifically wants direct rebuttal or an existing ledger continuation.

## Run

```powershell
python <skill>\scripts\blind_opening.py `
  --root <target-project-root> `
  --topic <target-document-or-topic> `
  --agents codex,claude `
  --claude-effort <low|medium>
```

默认 participants 为 `codex,claude`，每位 participant 的超时为 300 秒，兼容性 fallback 为 `--claude-effort low`。调用 agent 按 [router.md](router.md) 判断：大计划选择 `medium`，小计划选择 `low`。`--agents` 也接受 `grok`，`--fake` 使用确定性 participant 执行测试。每位 participant 都是新的短生命周期 CLI 进程，只接收 topic、目标文档、Blind Opening prompt 和 schema；不得向 prompt 添加既有 ledger、其他 participant 的响应或上游摘要。

## Result

The user-visible result is a Markdown file at `%TEMP%\discuss-ledger\blind-<slug>-<run-id>.md`. A same-directory JSON file is an internal intermediate artifact; do not present it as the deliverable unless a caller needs it programmatically.

The Markdown preserves each participant's raw `ideas` and candidate `new_points`, then lists consolidated initial points. Consolidation only deduplicates exactly equal summaries after whitespace/case normalization; it retains every source body with an agent label. Do not merge near-duplicates or conflicting recommendations automatically.

Blind Opening ends after the Markdown result unless the user selected the combined mode.
