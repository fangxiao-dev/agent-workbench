# Codex Harness Package Runner v0.1

`scripts/run-codex-harness-package.py` turns an approved Impl-Package snapshot into bounded parent-agent stage dispatches. It validates the source commit and current D/S/P bindings before producing any work package. It controls parent App Server sessions only; a parent may independently use native subagents and relevant Skills, but child activity is not accepted as evidence.

`scripts/prepare-codex-harness-package.py` is the fast-adaptation entry point. Given a fixed approved package snapshot, it derives a draft TOML adapter and a readiness report from its task contracts, dependencies, cohorts, ticket references and current D/S/P bindings. It works for arbitrary ticket ID formats; it is not DATEV-specific. The generated draft is deliberately non-executable until an owner provides independent verifier commands and confirms any inferred ownership boundary.

## Runtime policy contract

Configurable context, delegation, task-partitioning, decision-routing, validation and lifecycle policy lives in the canonical JSON asset at `skills/codex-harness/assets/codex-harness-runtime-policy.v0.json`; its shape is defined by the adjacent JSON Schema. The internal definitions of `design_baseline` and `runtime_enforced` live in the Codex Harness design asset's `术语定义` section, not in this runner document or the Schema enum. The package runner now loads the canonical policy and records policy identity/resource-ledger evidence for its explicit stage path; continuation, failure-path and all-entry enforcement are not yet closed, so the policy remains `design_baseline`.

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

## Current boundary

v0.1 deliberately does not create worktrees, merge parent branches, run an entire cohort automatically, write an Impl-Package gate, or perform DATEV actions. It only enforces the subset of canonical runtime policy currently evidenced by its loader/resource-ledger seam; continuation, complete failure-path enforcement and external acceptance remain under an integration parent and owner-controlled process. The runner does provide automatic draft preparation, immutable work packages, App Server parent dispatch, timeout, parent-result parsing, declared Skill context, sensitive-source consent boundary, diff allowlist, and independent verifier seam needed for the next iteration.
