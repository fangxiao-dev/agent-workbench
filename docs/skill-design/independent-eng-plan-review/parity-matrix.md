# Eng Plan Review 语义保真矩阵

状态：设计决策已对齐，实施期与分阶段 eval 期间继续补齐。

用途：证明现有 gstack `plan-eng-review` 的高价值审查语义在新 `eng-plan-review` 中被 preserve、adapt 或明确 drop，并为保留项绑定 eval。正式 skill 不读取本文件。

| ID | 现有语义 | 分类 | 新位置 | 处理 | Eval |
| --- | --- | --- | --- | --- | --- |
| PAR-001 | 用户已给唯一 plan 时仍先询问审查目标 | 交互机制 | `SKILL.md` 目标绑定 | adapt：唯一目标直接绑定，只有歧义时询问 | E-TARGET-01 |
| PAR-002 | Scope Challenge：复用、最小完整变更、复杂度、TODO、distribution、完整度 | 审查内核 | `scope-review.md` | preserve；删除固定文件数硬停止 | E-SCOPE-01 至 E-SCOPE-04 |
| PAR-003 | DRY、explicit over clever、right-sized diff、engineered enough、repository fit、single source of truth 与 change sequencing | 工程判断 | `rubric.md`、`code-quality-review.md` | preserve：按组织惯例、contract/source of truth、错误/状态边界、abstraction/迁移维护四个薄镜头发现风险 | E-CODE-01、E-CODE-02 |
| PAR-004 | Blast radius、boring technology、reversibility、failure ownership、DX、ownership/handoff、failure learning 与 reliability trade-off | 工程判断 | `rubric.md`、`architecture-review.md` | preserve：作为贯穿每个 candidate/finding 的横切镜头，按 material signal 选择，不作为评分表 | E-ARCH-01、E-CROSS-01 |
| PAR-005 | 架构边界、依赖图、数据流、瓶颈、SPOF、安全边界 | 审查内核 | `architecture-review.md` | preserve | E-ARCH-02 |
| PAR-006 | 新 artifact 的 build、publish、update 和 target platforms | 审查内核 | `scope-review.md`、`architecture-review.md` | preserve | E-DIST-01 |
| PAR-007 | Confidence Calibration、severity 语义与 pre-emit evidence gate | 质量门 | `decision-policy.md` | adapt：candidate 只记录 claim、初步 evidence/reasoning 和 risk；formal finding 才要求可核验证据、稳定 P0–P3 语义与同轮可比较的 confidence；支持 evidence ladder、generated/framework source 核验、direct evidence 和有界 absence proof | E-EVID-01 至 E-EVID-05 |
| PAR-008 | 每个 finding 单独 AskUserQuestion 并立即 STOP | 交互机制 | `decision-policy.md` | replace：薄 Batch Decision Protocol、依赖波次和 early flush | E-INT-01 至 E-INT-04 |
| PAR-009 | Test Framework Detection 与 material behavior trace | 审查内核 | `test-review.md` | adapt：从 entry/input 经 validation、transform/branch、state/side effect 追踪到 user/operator outcome；不恢复逐行或机械 100% | E-TEST-01、E-TEST-06 |
| PAR-010 | 覆盖 code paths、user flows、error states、test quality 与 E2E/EVAL 选择 | 质量门 | `test-review.md` | adapt：行为变更默认 coverage map，按真实边界风险选择 unit/integration/E2E/eval；只有短表难表达关系时升级 test diagram | E-TEST-02 至 E-TEST-07 |
| PAR-011 | Regression 缺测必须进入 critical test requirement | 质量硬门 | `test-review.md`、`decision-policy.md` | preserve；不作为 owner 可省略的普通偏好 | E-REG-01 |
| PAR-012 | Failure modes：test、error handling、user-visible outcome 三联检查 | 质量门 | `test-review.md`、`final-report.md` | preserve | E-FAIL-01 |
| PAR-013 | Performance：N+1、内存、缓存、慢路径和复杂度 | 审查内核 | `performance-review.md` | preserve | E-PERF-01 |
| PAR-014 | Independent Outside Voice 与 cross-model tension | 独立复核 | `subagent-prompts.md`、`decision-policy.md` | adapt：每轮 mandatory fresh context，并在 decision waves 前汇总；不可用时 degraded，禁止 fully reviewed/cleared verdict | E-VOICE-01 至 E-VOICE-04 |
| PAR-015 | NOT in scope、What already exists、diagrams、actionable Implementation Tasks | 审查输出 | section references、`final-report.md` | preserve：accepted finding 映射到实施动作、受影响模块、真实依赖与 observable verification oracle；不猜 effort 或不存在路径 | E-OUT-01、E-OUT-03 |
| PAR-016 | Worktree parallelization strategy | 下游执行建议 | `final-report.md` | adapt：仅存在两个以上独立 workstreams 时输出 | E-OUT-02 |
| PAR-017 | `GSTACK REVIEW REPORT` 与 unresolved sentinel | 收尾安全门 | `final-report.md` | adapt：unresolved/degraded 状态保留在 ledger 与聊天；默认不写目标 plan report，仅项目模板、稳定导出或 owner 明确要求时写摘要 | E-REPORT-01 至 E-REPORT-02 |
| PAR-018 | Review 与目标 plan 同步修改 | 写入行为 | Review/Apply contract | replace：review byte-identical，owner 对 manifest hash 的一次明确 apply 同时构成 ratification 与写入授权 | E-APPLY-01 至 E-APPLY-04 |
| PAR-019 | Tasks JSONL、dashboard、review chaining、ship readiness | gstack 生态 | 无 | drop；不影响单次 finding 质量 | — |
| PAR-020 | Telemetry、artifact sync、checkpoint、first-run、question tuning | gstack runtime | 无 | drop | — |
| PAR-021 | 固定五阶段全量审查与统一停止证明 | 覆盖机制 | `SKILL.md`、section references | adapt：每轮先加载横切 rubric 与五个短聚焦镜头，再做 materiality scan；每维记录已审查、不适用及理由或存在 finding，仓库调查深度、依赖图和停止证明按风险与复杂度生成 | E-MAT-01 至 E-MAT-03 |
| PAR-022 | 固定 Judge/Critic/Section Reviewer 编制 | 角色机制 | `decision-policy.md`、`subagent-prompts.md` | adapt：高影响自动归纳、证据冲突、不可逆性、跨边界影响或 reviewer 不确定时启用；同一 fresh reviewer 可合并 Judge 与 Critic | E-ROLE-01 至 E-ROLE-03 |
| PAR-023 | 审查角色和工具选择隐式存在 | 运行可见性 | `SKILL.md` | add：每轮在聊天中报告启用或跳过的角色与工具及理由，不持久化为恢复协议 | E-ROLE-04 |
| PAR-024 | Review ledger、目标 stale 与 Apply gate | 安全状态 | `review_ledger.py`、`decision-policy.md` | adapt：脚本仅 init/record/authorize/verify/status；绑定结构化 owner Apply source 与 exact manifest hash，校验 materiality/finding 一致性并拒绝未接受的 P0，恢复 stale locks；每个 formal finding 记录 evidence dependency identity/hash，变化只触发关联 finding 局部复核；单目标 plan 使用 guarded Apply | E-LEDGER-01 至 E-LEDGER-09 |
| PAR-025 | 单次大门式对照验收 | Eval 治理 | 设计期 eval 资料 | replace：prototype、evaluable candidate、default rollout 分阶段 gate；完整质量成本比较使用预声明样本、容差和风险权重 | E-EVAL-01 至 E-EVAL-03 |
| PAR-026 | 技术决策回到真实目标、acceptance 与用户/operator 结果 | 横切完整性 | `rubric.md`、`SKILL.md`、`final-report.md` | preserve：每个 material candidate 追踪 goal→contract→consumer→observable outcome→oracle | E-CROSS-01 |
| PAR-027 | 完整方案覆盖 success、error、recovery、migration、distribution 与 verification | 横切完整性 | `rubric.md` 与五个聚焦 reference | adapt：只覆盖与目标相关的 material slice，不恢复 Boil-the-Ocean score、固定阈值或全路径强制图 | E-CROSS-02 |

## 使用规则

- 实现每个 reference 时，补齐对应行的精确检查项和输出合同。
- 建立分阶段 eval corpus 时，每个 `preserve` 或 `adapt` 行至少绑定一个与其准入阶段相符的可运行 eval；`drop` 行必须保留删除理由。
- 对照结果以人工裁决的 golden/union findings 为 oracle，不能把旧 skill 输出直接当作正确答案。
- 如果实现决定改变本矩阵中的处理方式，先更新 proposal 的设计决策，再更新本矩阵；不要只修改正式 skill。
