# Blind Opening

Use Blind Opening for independent multi-party exploration: brainstorming candidate solutions, discovering risks, or widening a design space before any participant sees another participant's opinion. Do not use it when the user specifically wants direct rebuttal or an existing ledger continuation.

## Run

```powershell
python <skill>\scripts\blind_opening.py `
  --root <target-project-root> `
  --topic <target-document-or-topic> `
  --agents codex,claude
```

Defaults are `codex,claude` and 300 seconds per participant. `--agents` also accepts `grok`. `--fake` uses deterministic participants for tests. Each participant is a new short-lived CLI process and receives only the topic, target document, Blind Opening prompt, and Blind Opening schema. Never add an existing ledger, another participant's response, or an upstream summary to its prompt.

## Result

The user-visible result is a Markdown file at `%TEMP%\discuss-ledger\blind-<slug>-<run-id>.md`. A same-directory JSON file is an internal intermediate artifact; do not present it as the deliverable unless a caller needs it programmatically.

The Markdown preserves each participant's raw `ideas` and candidate `new_points`, then lists consolidated initial points. Consolidation only deduplicates exactly equal summaries after whitespace/case normalization; it retains every source body with an agent label. Do not merge near-duplicates or conflicting recommendations automatically.

Blind Opening ends after the Markdown result unless the user selected the combined mode.
