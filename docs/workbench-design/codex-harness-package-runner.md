# Codex Harness Package Runner v0.1

`scripts/run-codex-harness-package.py` turns an approved Impl-Package snapshot into bounded parent-agent stage dispatches. It validates the source commit and current D/S/P bindings before producing any work package. It controls parent App Server sessions only; a parent may independently use native subagents and relevant Skills, but child activity is not accepted as evidence.

`scripts/prepare-codex-harness-package.py` is the fast-adaptation entry point. Given a fixed approved package snapshot, it derives a draft TOML adapter and a readiness report from its task contracts, dependencies, cohorts, ticket references and current D/S/P bindings. It works for arbitrary ticket ID formats; it is not DATEV-specific. The generated draft is deliberately non-executable until an owner provides independent verifier commands and confirms any inferred ownership boundary.

## Manifest

Use a TOML manifest with a fixed repository, source commit, package path, attempt id, parent profile, and one `[[stage]]` per Harness stage. Each stage declares DAG dependencies, allowed mutation paths, parent role, applicable Skills, external verifier commands, sandbox mode, and whether sensitive originals may be requested on demand. [examples/datev-accounting-rules.harness.toml](../../examples/datev-accounting-rules.harness.toml) is the DATEV reference manifest.

`sensitive_originals = "on_demand"` does not grant blanket access. An actual execution additionally requires `--allow-sensitive-originals --sensitive-root <repository-relative-root>`; the prompt prohibits copying full source content, identifiers, or payloads into artifacts, logs, commits, or Parent Result.

## Commands

Generate a reviewable adapter draft and its readiness report. This does not start Codex, create a worktree or mutate the target repository:

```powershell
python scripts/prepare-codex-harness-package.py `
  --repository-root D:\CodeSpace\kaispan-dev `
  --source-ref 3cc2a9350d5820c236a352b7e1a756f13a837e27 `
  --package docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules `
  --parent-profile D:\CodeSpace\agent-workbench\.codex\harness\parent.toml `
  --output D:\CodeSpace\kaispan-dev\.harness\datev.generated.toml `
  --readiness-output D:\CodeSpace\kaispan-dev\.harness\datev.readiness.json
```

Review every `TODO(owner)` verifier and every stage named in `path_ownership_review`, then copy or promote the approved values into a checked-in manifest. The checked-in [examples/datev-accounting-rules.harness.toml](../../examples/datev-accounting-rules.harness.toml) remains the reviewed reference; a generated file is only an input to that review.

Validate the package snapshot and print its currently ready parent stages without creating a worktree or starting Codex:

```powershell
python scripts/run-codex-harness-package.py --manifest examples/datev-accounting-rules.harness.toml
```

After an integration parent has accepted preceding stages and an isolated, clean worktree exists, dispatch one parent stage:

```powershell
python scripts/run-codex-harness-package.py --manifest examples/datev-accounting-rules.harness.toml --completed T1,T2 --execute --stage T4 --worktree D:\CodeSpace\kaispan-dev\.worktrees\datev-t4
```

The runner refuses an unclean worktree, unknown/unsatisfied dependencies, source-binding drift, out-of-scope changed paths, invalid Parent Result, missing work-package hash, or an apparent success without configured independent verifier commands. A parent can still return `needs_owner`, which is preserved rather than retried as a failure.

## Current boundary

v0.1 deliberately does not create worktrees, merge parent branches, run an entire cohort automatically, write an Impl-Package gate, or perform DATEV actions. This keeps git integration and external acceptance under an integration parent and owner-controlled process. The runner does provide automatic draft preparation, immutable work packages, App Server parent dispatch, timeout, parent-result parsing, declared Skill context, sensitive-source consent boundary, diff allowlist, and independent verifier seam needed for the next iteration.
