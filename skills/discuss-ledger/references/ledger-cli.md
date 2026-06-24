# Ledger CLI Reference

Run ledger commands from the repo root:

```bash
python <skill>/scripts/discuss_ledger.py <subcommand> ...
```

`--root` defaults to the current working directory, so you only need to pass `--root <repo-root>` when you are not already at the repo root. All subcommands except `init` take `--slug`. Mutating commands that take `--author` automatically add that author to `participants` if missing.

## Initialize

If a ledger does not exist, create it:

```bash
python <skill>/scripts/discuss_ledger.py init --topic docs/plans/2026-06-18-foo.md --initiator <you>
```

`--topic` may be a doc path (recorded as the review target) or free text. `--initiator` is whoever speaks round 1 (usually you). `--participants CC,Codex` is optional; if omitted, the initiator starts the list and later `--author` / `set-next --next` calls add participants as they appear.

## Status

If a ledger exists, read ground truth with `status` before doing anything:

```bash
python <skill>/scripts/discuss_ledger.py status --slug 2026-06-18-foo
```

## Converge

Promote settled points before writing new opinions:

```bash
python <skill>/scripts/discuss_ledger.py converge --slug S --point D1 --marker "一致" --line "保留兼容入口,重指新 dashboard"
```

Marker is `一致` (both agree) or `用户裁决` (user ruled; write `用户裁决·覆盖CC` if it overrides a party).

## Add A Point

Register a materially new disagreement:

```bash
python <skill>/scripts/discuss_ledger.py add-point --slug S --author <them> --summary "..." --body "their argument"
```

First map free-form notes to existing points. Use `contest` for a response to an existing point, `converge` for a settled point, and `add-point` only for a materially new disagreement.

`add-point` auto-allocates the next `Dn`, adds a table row, and writes the argument under the current round.

## Contest

Counter an existing point in the current round:

```bash
python <skill>/scripts/discuss_ledger.py contest --slug S --point D2 --author <you> --body - --movement true
```

Set `--movement false` when you are restating with no new ground. Set `--movement true` only for new evidence, corrected facts, a narrowed scope, an explicit concession, or a concrete compromise.

## End Turn

Close your turn:

```bash
python <skill>/scripts/discuss_ledger.py end-turn --slug S
```

Do not run `end-turn` until every existing point has one of: converged, contested with evidence, marked no-movement, or intentionally left open for the next party.

If the debate remains open, `end-turn` sets `next: 待指定`. The previous speaker must not choose the next speaker. The actual caller, user, or orchestrator assigns the next turn explicitly:

```bash
python <skill>/scripts/discuss_ledger.py set-next --slug S --next Codex
```

Use `--dry-run` on any mutating command to preview the resulting file without writing.
