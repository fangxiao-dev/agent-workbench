# SKILL 降载减法审计（r2）

工作底稿统一取 `4e53faa^`；先移植当前 HEAD 的压缩表达、leaf 结构化输出和宿主无关的语义 CLI/处境注入指针，再只删除有明确承接者的内容。未列入台账的内容均保留或仅做压缩。

## 1. `review-code/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| （无；审查意图、适用范围、profile 选择/升级、五步审查、Coverage 和 leaf 输出合同均保留，仅压缩表达并补入语义 CLI/处境注入指针） | — |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`4e53faa^`） | 40 |
| 降载后（当前 HEAD） | 22 |
| 本次结果 | 28 |

本次自查：降载前每个段落均可在结果文件中定位；没有仅因行数删除判断内容。

## 2. `review-code-by-standards/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| （无；输入锚定、仓库规范优先、12 个 Fowler smell 及其判断、codebase-design 基线、深度触发、证据指引、400 words/覆盖范围和 Standards 边界均保留，仅压缩并补入语义 CLI/处境注入指针） | — |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`4e53faa^`） | 67 |
| 降载后（当前 HEAD） | 22 |
| 本次结果 | 33 |

本次自查：降载前的输入合同、每个 Fowler smell 的识别与建议、深度选择/触发条件、证据要求、Coverage record 和非本轴边界均可在结果文件中定位；没有把高频 Standards 判断下沉到 strict-maintainability reference。

## 3. `review-code-by-spec/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| （无；比较点与合同 evidence 输入边界、缺失/scope creep/错误行为/interface/seam/module/兼容/状态机判断、双证据要求、Coverage 和“不得以非合同依据替代”的边界均保留，仅压缩并补入语义 CLI/处境注入指针） | — |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`4e53faa^`） | 35 |
| 降载后（当前 HEAD） | 17 |
| 本次结果 | 17 |

本次自查：降载前输入合同的不可变 SHA/完整 diff/commit 列表、六项 Spec 维度、合同与 diff 双证据、400 words/Coverage 以及非合同证据排除边界均可在结果文件中定位。

## 4. `safety-review/SKILL.md`

### 删除台账

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| `Data integrity` 专项：检查数据写入、schema/data migration、事务边界、校验、重试与 rollback；报告重复写、部分写、丢失、损坏或无法恢复路径及失败恢复证据覆盖 | `plugin-marketplace/plugins/impl-package/skills/safety-review/references/five-categories.md:7` |
| `Security boundary` 专项：检查认证、authorization/permission、tenant/数据隔离、secret、输入信任边界和 webhook 签名验证，重点检查绕过 auth/permission | `plugin-marketplace/plugins/impl-package/skills/safety-review/references/five-categories.md:11` |
| `Concurrency` 专项：检查竞态、重复投递、at-least-once handler、锁/版本控制、幂等键和重试交互，不因当前串行而忽略外部回调/队列/用户并发 | `plugin-marketplace/plugins/impl-package/skills/safety-review/references/five-categories.md:15` |
| `External side effects` 专项：检查 payment、webhook、邮件、供应商 API、数据库外写入和其他 external mutation；核实 idempotency、去重或 compensation/rollback 及失败/重试路径 | `plugin-marketplace/plugins/impl-package/skills/safety-review/references/five-categories.md:19` |
| `Change map` 专项：列出受影响入口、写入点、数据存储、外部 adapter、异步消费者、迁移及验证证据，并标出未审计/无法确认路径 | `plugin-marketplace/plugins/impl-package/skills/safety-review/references/five-categories.md:23` |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`4e53faa^`） | 76 |
| 降载后（当前 HEAD） | 25 |
| 本次结果 | 35 |

本次自查：触发信号、focused path 三点与其“不建新 artifact”边界、SHA 锚定命令、P0/P1/P2 fail-closed、五类总表、change map、工作流和 canonical evidence 均保留；仅删除五类专项的展开说明，并由专项 reference 承接。
