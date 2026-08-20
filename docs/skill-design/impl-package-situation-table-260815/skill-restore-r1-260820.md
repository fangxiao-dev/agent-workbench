# SKILL Restore R1 — 2026-08-20

## `dev-with-track/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| `Restore` 中的 PowerShell 适配代码块：`package validate`、`$validationResult`、`$compactionPressure`、`$renderArgs`、`situation.py render` 的逐条命令拼接 | `plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py:39`；`plugin-marketplace/plugins/impl-package/scripts/situation.py:3265` |
| `Get-Content .\er-payload.json -Raw | python ... recovery judgment` 的具体管道命令 | `plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md:70`；`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1072` |
| `trail append` 的完整 Python/stdin 调用拼法以及由 CLI 自动补全 `v`、`seq`、`ts`、`head` 的机械说明 | `plugin-marketplace/plugins/impl-package/references/situation-inputs.md:460`；`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1143` |

### 行数

- 降载前：97
- 降载后：9
- 本次结果：36

## `subagent-driven-development/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| 无；降载前的 worker contract、mode 选择、resolver、结果 envelope、review gate、并行资源和主 session ownership 均在本次结果中压缩保留 | — |

### 行数

- 降载前：52
- 降载后：9
- 本次结果：34

## `do-review/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| `review_ledger.py create` 的完整命令行代码块（`--repo-root`、`--base`、`--head`、重复 `--source`、`--slug`、`--mode`、`--round-cap`） | `plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py:246` |
| `verify-reviewer-skills.py` 的两条完整命令行代码块（registry skills 与 custom `--skill-path` 形式） | `plugin-marketplace/plugins/impl-package/skills/do-review/scripts/verify-reviewer-skills.py:131`；`plugin-marketplace/plugins/impl-package/skills/do-review/references/reviewer-registry.json:16` |

### 行数

- 降载前：95
- 降载后：25
- 本次结果：39

## `plan-review/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| 无；降载前的 mode、输入边界、candidate Git commit 锚定、Composition 完整性、9 个审查维度、material/owner-decision 判定、decision waves、verdict、closure 边界、apply boundary 和输出合同均在本次结果中压缩保留，并移植了 `execution-boundaries` 路由及更精确 owner decision 条件 | — |

### 行数

- 降载前：61
- 降载后：13
- 本次结果：32
