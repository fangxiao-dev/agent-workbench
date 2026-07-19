# Codex Harness Package Runner v0.1

`scripts/run-codex-harness-package.py` turns an approved Impl-Package snapshot into bounded parent-agent stage dispatches. It validates the source commit and current D/S/P bindings before producing any work package. It controls parent App Server sessions only; a parent may independently use native subagents and relevant Skills, but child activity is not accepted as evidence.

`scripts/prepare-codex-harness-package.py` is the fast-adaptation entry point. Given a fixed approved package snapshot, it derives a draft TOML adapter and a readiness report from its task contracts, dependencies, cohorts, ticket references and current D/S/P bindings. It works for arbitrary ticket ID formats; it is not DATEV-specific. The generated draft is deliberately non-executable until an owner provides independent verifier commands and confirms any inferred ownership boundary.

底层 Codex CLI/App Server 能力位于 `scripts/codex_harness_cli.py`，只负责 executable discovery、命令构造和 JSON-RPC stdio session；`scripts/codex_harness_controller.py` 保留 Package parent-stage 所需的 Parent Result 与外部 verdict 能力。这样只需要在多个独立 worktree 中调用 Codex 的轻量 caller 可以复用 CLI 模块，而不必加载 package adapter、policy、lease 或 ledger。

Crew 顶层 controller 已统一为 `scripts/codex_harness_orchestrator.py`；旧 parent controller 与 dispatch manifest/state 协议已删除。`scripts/codex_harness_dispatch.py` 现在只是 assignment 级 Worker/worktree adapter，没有独立 CLI 或 scheduler。Package runner 继续保持独立 parent-stage adapter，不参与 Crew assignment routing，也不写 Crew canonical state。

## Runtime policy contract

Role authority, assignment boundaries, workspace isolation, validation and cancellation policy live in `skills/codex-harness/assets/codex-harness-runtime-policy.v1.3.json`; its shape is defined by the adjacent versioned JSON Schema. The package runner loads the same canonical policy identity for its explicit stage path rather than maintaining a second legacy policy. The internal definitions of `design_baseline` and `runtime_enforced` live in the Codex Harness design asset's `术语定义` section, not in this runner document or the Schema enum.

## Manifest

Use a TOML manifest with a fixed repository, source commit, package path, attempt id, parent profile, and one `[[stage]]` per Harness stage. Each stage declares DAG dependencies, allowed mutation paths, parent role, applicable Skills, external verifier commands, sandbox mode, and whether sensitive originals may be requested on demand. Adapter preparation only accepts current Impl-Package contract 3.2 snapshots. [the pinned DATEV pre-3.2 fixture](../../examples/datev-accounting-rules.pre-3.2-upgrade-fixture.toml) exists only to prove stale packages are rejected before preparation; it is not an executable reference manifest.

`sensitive_originals = "on_demand"` does not grant blanket access. An actual execution additionally requires `--allow-sensitive-originals --sensitive-root <repository-relative-root>`; the prompt prohibits copying full source content, identifiers, or payloads into artifacts, logs, commits, or Parent Result.

## Commands

Generate a reviewable adapter draft and its readiness report. This does not start Codex, create a worktree or mutate the target repository:

```powershell
python scripts/prepare-codex-harness-package.py `
  --repository-root D:\CodeSpace\kaispan-dev `
  --source-ref <current-3.2-commit> `
  --package docs/implementations/<current-package-id> `
  --parent-profile D:\CodeSpace\agent-workbench\.codex\harness\parent.toml `
  --output D:\CodeSpace\kaispan-dev\.harness\datev.generated.toml `
  --readiness-output D:\CodeSpace\kaispan-dev\.harness\datev.readiness.json
```

Review every `TODO(owner)` verifier and every stage named in `path_ownership_review`, then copy or promote the approved values into a checked-in current manifest. A generated file is only an input to that review; the pre-3.2 fixture must never be promoted.

Validate the package snapshot and print its currently ready parent stages without creating a worktree or starting Codex:

```powershell
python scripts/run-codex-harness-package.py --manifest <reviewed-current-manifest.toml>
```

After an integration parent has accepted preceding stages and an isolated, clean worktree exists, dispatch one parent stage:

```powershell
python scripts/run-codex-harness-package.py --manifest <reviewed-current-manifest.toml> --completed T1,T2 --execute --stage T4 --worktree D:\CodeSpace\kaispan-dev\.worktrees\datev-t4
```

The runner refuses an unclean worktree, unknown/unsatisfied dependencies, source-binding drift, out-of-scope changed paths, invalid Parent Result, missing work-package hash, or an apparent success without configured independent verifier commands. A parent can still return `needs_owner`, which is preserved rather than retried as a failure.

When a later parent stage deliberately reuses a serial worktree, pass `--serial-handoff <committed-and-verified-handoff.json> --delivery-program-id <id>`. The runner then checks that the worktree is clean, the prior commit remains an ancestor of `HEAD`, and prior verification evidence is successful; this is a reuse gate, not a scheduler or promotion action.

## Current boundary

v0.1 deliberately does not create worktrees, merge parent branches, run an entire cohort automatically, write an Impl-Package gate, or perform DATEV actions. It only enforces the subset of canonical runtime policy currently evidenced by its loader/resource-ledger seam; continuation, complete failure-path enforcement and external acceptance remain under an integration parent and owner-controlled process. The runner does provide automatic draft preparation, immutable work packages, App Server parent dispatch, timeout, parent-result parsing, declared Skill context, sensitive-source consent boundary, diff allowlist, and independent verifier seam needed for the next iteration.
