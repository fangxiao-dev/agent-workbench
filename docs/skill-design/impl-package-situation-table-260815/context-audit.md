# Impl-Package 全链路 context 审计：降载与 agent 化的同一张表

审计快照：2026-08-16，工作目录为当前 linked worktree。本文只做测量与方案，不改变任何 Skill、脚本、表或 fixture。

## 结论先行

按题目列出的主链（`impl-package → req-align → impl-planning → to-tickets → dev-with-track → subagent-driven-development → do-review → verification-before-completion → backfill-stable-docs`），并把 `impl-planning` 明确调用的 `plan-review`、`execution-preflight` 计入，一次正常的 initial/full、Ticket-only、非 legacy、无额外 Focused PRD/contract surface、一次普通 worker review 的主控上下文约为 **34,200 token**。把这条路径上的条件 reference、模板、reviewer 内部文档和 backfill 分支全部保守读入，主控可达材料约 **100,300 token**，差约 **66,100 token**；如果连四个 reviewer track 的内部文档也误装入主控，再加约 **11,500 token**。

`situation-inputs.md` 当前为 **1,056 行 / 98,891 UTF-8 字节 / 约 28,300 token**。它**不是无条件 runtime load**：当前 `dev-with-track/SKILL.md:69` 明确写着它和 `trail-schema.md`“运行时不需要打开，仅在维护处境表或写 per-package 覆盖时查阅”。运行时由 `scripts/situation.py` 读取的是 `skills/dev-with-track/situations.yaml`，不是这份 Markdown 合同。因此它是“误读会造成高危”的大文档，而不是当前主控开局的无条件高危项。

整条可达材料中，按章节把“主控必须知道的调用/验收合同”与“执行者才需要的查法、写法、模板、检查清单”拆开，方法知识约 **85,100 / 111,700 = 76%**（按语义分段估算，合理区间约 72%–79%）。所以真正的收益点不是继续把 127 条规则搬进表，而是把大量方法知识留在 worker/工具侧，把主控只保留接口和验收边界。

第一顺序建议是 **先把 do-review 的四个 leaf track 作为不透明 worker 执行**：三条默认 track 可从主控上下文卸下约 **9,900 token**，连条件 Safety track 约 **11,500 token**；输入/输出边界较窄、主控不依赖内部检查方法、结果已有结构化 ledger/report 合同。`req-align` 的 Decision 与 Spec 可以合成一个 worker，但它们是主控要审批的产物，接口更宽，建议第二顺序做“worker 起草 + 主控审批”，不要先把 D/S gate 外包。

## 0. 口径、范围和估算方法

### 0.1 口径

- “无条件”指在选定的典型路径中，Skill 明确要求先读、必须执行的阶段或该阶段明确要求的 reference；不是说用户只加载入口 Skill 就会自动加载全部后续阶段。
- “条件”指只有特定 route、风险、mode、review phase、artifact 写入或 backfill 动作才读取。
- “按需”指维护表、排障、legacy 迁移、apply/verify/retirement 等不属于普通 dev 主循环的读取。
- 没有明确 `read` 边、只有文件存在或模板可用的材料，标为“条件/未能确认”；不把它擅自算成无条件。
- 选定的是一次正常 Ticket-only initial/full 执行路径。入口表中 `grill-me-smartly`、`grilling`、`create-task-dag` 等可选 sibling 不属于同一次典型 dev 执行，另在末尾说明；否则“典型一次执行”没有单一总量。

### 0.2 token 估算

使用当前 working tree 文件的 UTF-8 字节数除以 3.5，四舍五入到整数；行数按换行计数。这个比例是混合中文、英文、Markdown、YAML/JSON 的保守工程估算，不是模型 tokenizer 的精确计数，单文件误差可能约 ±15%–25%。文中所有 `~` 数字都遵循同一口径，适合比较相对收益，不应当作模型账单。

### 0.3 当前快照边界

审计过程中最终采样到的 worktree 已有用户侧变更：

- `plugin-marketplace/plugins/impl-package/scripts/situation.py`
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/control-flow.md`
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md`
- `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/review-gate.md`
- `tests/test_situation_render.py`
- `docs/skill-design/impl-package-situation-table-260815/rule-coverage-map.md`

这些不是本审计创建或修改的内容。当前脚本 diff 已增加 renderer digest/`--since` 短路接口；这进一步支持“主控消费结构化 renderer 结果，不读 1,056 行输入合同”的结论，但本文不评价该实现是否正确。

## 1. 强制加载集合和文档可达图

### 1.1 典型主控链上的阶段文档

下面的“典型路径 load”是在一次 initial/full 执行真的走到该阶段时的性质。`无条件（阶段内）`不是全局启动保证；它表示一旦进入该阶段，文档是该阶段的固定主控材料。

| 文档 | 行数 | 估算 token | 加载性质 | 触发位置 | 知识属性 |
| --- | ---: | ---: | --- | --- | --- |
| `plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md` | 69 | ~1,250 | 无条件（入口） | 入口本身；路由表 `:27-44` | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md` | 51 | ~1,340 | 无条件（initial/full route） | 入口 `:27`；本页 `:30-36` | 接口为主，混合 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md` | 53 | ~1,390 | 无条件（D/S PASSED 后） | 入口 `:30`；req-align `:34` | 接口为主，混合 |
| `plugin-marketplace/plugins/impl-package/skills/to-tickets/SKILL.md` | 22 | ~720 | 无条件（`tickets=true`） | impl-planning `:28`；入口 `:32` | 接口为主，混合 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md` | 92 | ~2,850 | 无条件（进入执行） | impl-planning `:39`；入口 `:37` | 接口/方法混合 |
| `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md` | 54 | ~1,350 | 条件（需 dispatch/local scheduling） | dev `:9, :45`；入口 `:36` | 接口为主，混合 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md` | 84 | ~2,880 | 条件（review phase） | dev `:75`；入口 `:38` | 接口为主，混合 |
| `plugin-marketplace/plugins/impl-package/skills/verification-before-completion/SKILL.md` | 79 | ~2,000 | 条件（completion claim） | 本页 `:18`；入口 `:43` | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/SKILL.md` | 43 | ~1,000 | 条件（terminal 后 backfill） | 入口 `:44`；本页 Audit/Apply/Verify/Retirement | 接口为主，混合 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/SKILL.md` | 62 | ~1,210 | 无条件（planning 的 bundle admission） | impl-planning `:29` | 接口为主，混合 |
| `plugin-marketplace/plugins/impl-package/skills/execution-preflight/SKILL.md` | 48 | ~750 | 无条件（进入 dev 前） | impl-planning `:39` | 接口为主，混合 |

### 1.2 跨 skill 共享合同和典型路径固定读取

| 文档 | 行数 | 估算 token | 加载性质 | 触发位置 | 知识属性 |
| --- | ---: | ---: | --- | --- | --- |
| `plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md` | 85 | ~1,890 | 无条件（planning/dev） | impl-planning `:8`；dev `:8`；入口 `:19`给出链接 | 接口 |
| `plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md` | 78 | ~1,680 | 无条件（dev；planning 也依赖） | dev `:8`；入口 `:19`给出链接 | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/references/package-lifecycle.md` | 28 | ~640 | 无条件（需要 D/S 的 route） | req-align `:30` | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/sub-skills/decision/SUB-SKILL.md` | 36 | ~1,000 | 无条件（full/decision-only） | req-align `:32`；本页 `:18` | 方法为主，含返回接口 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/references/requirement-inputs.md` | 46 | ~1,140 | 无条件（Decision 阶段） | Decision SUB-SKILL `:18` | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/references/decision-gate.md` | 34 | ~940 | 无条件（Decision Gate） | Decision SUB-SKILL `:18` | 接口/方法混合 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/sub-skills/spec/SUB-SKILL.md` | 52 | ~1,550 | 无条件（initial/full 在 Decision PASSED 后） | req-align `:33`；本页 `:22` | 方法为主，含返回接口 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/references/spec-gate.md` | 43 | ~1,330 | 无条件（initial Spec Gate） | Spec SUB-SKILL `:22` | 接口/方法混合 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/references/handoff.md` | 15 | ~580 | 无条件（汇报 Gate 结果） | req-align `:36` | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/worker-resolver.md` | 50 | ~880 | 无条件（每次 worker 启动前） | subagent `:41` | 接口为主，含解析方法 |
| `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/mode-contracts.md` | 31 | ~500 | 条件（按选定 mode） | subagent `:37` | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/references/reviewer-registry.json` | 31 | ~200 | 无条件（do-review 建立 ReviewRun） | do-review `:17, :23`“Load the registry” | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/references/review-topology.md` | 47 | ~1,360 | 无条件（每个 review phase） | do-review `:43` | 接口/方法混合 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/references/subagent-briefs.md` | 118 | ~1,870 | 无条件（派发 leaf 前） | do-review `:39, :58` | 方法为主，含 leaf 接口 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/references/output-templates.md` | 156 | ~1,860 | 无条件（leaf 返回后/报告时） | do-review `:66, :74` | 接口/方法混合 |

这 26 份材料合计约 **34,200 token**（其中 `mode-contracts.md` 是每次实际选择 mode 时的固定接口材料）。这里没有计入 Focused PRD、contract surface、处境输入合同、reviewer track 内部 checklist 等条件材料。

### 1.3 条件、按需和“有文件但没有明确主控 read 边”的材料

| 文档 | 行数 | 估算 token | 加载性质 | 触发位置/证据 | 知识属性 |
| --- | ---: | ---: | --- | --- | --- |
| `plugin-marketplace/plugins/impl-package/references/progressive-system-evidence.md` | 101 | ~2,920 | 条件 | impl-planning `:8`、dev `:8`、verification `:10`；仅 material seam/昂贵验证等信号 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/references/focused-prd.md` | 71 | ~1,990 | 条件 | Decision SUB-SKILL `:18` 的“earned Focused PRD” | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/references/contract-surface-design.md` | 70 | ~1,430 | 条件 | Spec SUB-SKILL `:35`；存在 API/persistence/seam/read model 时 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/alignment-proposal.md` | 52 | ~390 | 条件/未能确认主控是否直读 | Decision SUB-SKILL `:22` 使用 working output | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/decision.md` | 91 | ~1,150 | 条件/未能确认主控是否直读 | Decision SUB-SKILL `:23` earned Decision | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/spec.md` | 102 | ~1,260 | 条件/未能确认主控是否直读 | Spec SUB-SKILL `:34` | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/contract-design.md` | 42 | ~410 | 条件/未能确认主控是否直读 | Spec SUB-SKILL `:36` | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/patching.md` | 32 | ~610 | 条件/按需 | patch attempt；当前 `impl-planning/SKILL.md`没有明确 read 句 | 方法/接口混合 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/assets/templates/plan.md` | 71 | ~670 | 条件/未能确认主控是否直读 | plan artifact 生成；SKILL 规定字段但未显式链接该模板 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/references/scope-review.md` | 22 | ~660 | 条件 | plan-review `:42`，full-review 使用 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/references/architecture-review.md` | 14 | ~480 | 条件 | plan-review `:42`，full-review 使用 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/references/test-review.md` | 40 | ~1,140 | 条件 | plan-review `:42`，full-review 使用 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/references/performance-review.md` | 10 | ~250 | 条件 | plan-review `:42`，按风险使用 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/references/code-quality-review.md` | 28 | ~660 | 条件 | plan-review `:42`，full-review 使用 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/execution-preflight/references/authorization-contract.md` | 12 | ~280 | 条件/未能确认主控是否直读 | preflight 的授权判断；SKILL 未显式链接 | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/to-tickets/assets/templates/ticket.md` | 42 | ~500 | 条件/未能确认主控是否直读 | `tickets=true` 写 Ticket；SKILL 未显式链接 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/control-flow.md` | 18 | ~340 | 条件/未能确认 | 执行控制/排障参考；当前 SKILL 只保留相关语义，不显式 read | 接口/方法混合 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md` | 36 | ~810 | 条件/未能确认 | runtime/evidence/findings 排障参考；当前 SKILL 未显式 read | 方法为主，含接口 |
| `plugin-marketplace/plugins/impl-package/references/situation-inputs.md` | 1,056 | ~28,300 | 按需；运行时明确不打开 | `dev-with-track/SKILL.md:69` 明确“运行时不需要打开”，只在维护表或 per-package override 查阅 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml` | 927 | ~9,890 | 条件（工具运行时读取） | `dev-with-track/SKILL.md:13-25` 调用 `situation.py render`; `situation.py:30`固定 `TABLE_PATH` | 方法/机读合同 |
| `docs/skill-design/impl-package-situation-table-260815/trail-schema.md` | 186 | ~3,270 | 按需；运行时明确不打开 | `dev-with-track/SKILL.md:69` 同上；维护轨迹格式/per-package override 时查阅 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/dag.md` | 28 | ~270 | 按需（legacy） | 旧 3.4/Task package；新 package 不创建 DAG | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/execution-findings.md` | 34 | ~570 | 条件（需要创建/分流 findings） | dev `:77`及 Gate 前 findings triage；writer 侧使用 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/gate.md` | 21 | ~220 | 条件（写 Gate） | dev Verify/Gate 段；writer 侧使用 | 方法/接口混合 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/handoff.md` | 14 | ~190 | 按需（legacy） | 仅旧 Task Handoff；Ticket-only 使用 checkpoint | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/manual-acceptance-readiness.md` | 13 | ~170 | 条件（manual owner） | dev `:77`明确使用 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/progress.md` | 26 | ~200 | 条件（projection 生成/恢复） | current-state/standing-bookkeeper 生成；不是主控权威输入 | 方法/接口混合 |
| `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/parallel-work-admission.md` | 14 | ~300 | 条件（两个以上 bounded unit） | subagent `:26` | 接口/方法混合 |
| `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/review-gate.md` | 23 | ~460 | 条件（`review=required`） | subagent `:51`；track reviewer 需要时 | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/audit-runbook.md` | 11 | ~230 | 条件（backfill audit） | backfill SKILL `:19-27` Audit | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/audit-json-contract.md` | 30 | ~300 | 条件（输出 audit JSON） | backfill SKILL `:19-27`要求 audit JSON | 接口 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/source-selection-and-pending-consumption.md` | 24 | ~510 | 条件（source/pending/done inventory） | backfill SKILL `:12, :20-24`；SKILL 未显式写“read” | 接口/方法混合 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/constraint-extraction-and-routing.md` | 71 | ~1,700 | 条件（durable statement 分类） | backfill SKILL `:23-27`；SKILL 未显式写“read” | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/apply-runbook.md` | 25 | ~660 | 按需（owner approved apply） | backfill SKILL `:30-34` Apply | 方法/安全接口 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/verify-runbook.md` | 4 | ~80 | 按需（apply 后 verify） | backfill SKILL `:36-38` Verify | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/package-retirement-runbook.md` | 12 | ~190 | 按需（retirement） | backfill SKILL `:40-42` Retirement | 方法/安全接口 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/assets/apply-template.md` | 40 | ~410 | 按需/未能确认 | apply artifact；SKILL 未显式链接 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/assets/pr-summary-template.md` | 35 | ~470 | 按需/未能确认 | apply/PR summary；SKILL 未显式链接 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/assets/report-template.md` | 80 | ~860 | 条件/未能确认 | report output；SKILL `:23-27`只说明输出 | 方法/接口 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/assets/verify-template.md` | 41 | ~340 | 按需/未能确认 | verify output；SKILL 未显式链接 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/config/repository-config.example.json` | 21 | ~140 | 条件（配置缺省/示例） | backfill SKILL `:12`配置说明 | 方法/接口 |
| `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/config/repository-config.schema.json` | 54 | ~500 | 条件（配置校验） | backfill SKILL `:12`配置说明；脚本校验时读取 | 方法/接口 |

把上述条件材料全部算上（但不把 leaf reviewer 内部文档算作主控材料），主控上限约 **100,300 token**；相对典型固定路径的 **34,200 token**，差约 **66,100 token**。其中处境三件套（`situation-inputs.md`、`situations.yaml`、`trail-schema.md`）合计约 **41,400 token**，但正常 dev 主控只应得到 renderer 的结构化结果。

### 1.4 worker-only 文档和 sidecar

这些文档是可达图的一部分，但不应装入主控；它们由 leaf reviewer、standing bookkeeper 或 `$grok-worker` 自己读取。

| 文档 | 行数 | 估算 token | 加载性质 | 触发位置 | 知识属性 |
| --- | ---: | ---: | --- | --- | --- |
| `plugin-marketplace/plugins/impl-package/skills/review-code/SKILL.md` | 41 | ~830 | 条件（Track A） | `do-review/references/reviewer-registry.json`；leaf 按 assigned path 读取 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/review-code/references/review-checklist.md` | 219 | ~1,590 | 条件（Track A full behavior） | `review-code/SKILL.md` Profile 段 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/review-code/references/examples.md` | 147 | ~750 | 条件（Track A 输出示例） | `review-code/SKILL.md`输出合同链接 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/review-code-by-standards/SKILL.md` | 68 | ~1,800 | 条件（Track B） | reviewer registry；leaf assigned path | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/review-code-by-standards/references/strict-maintainability.md` | 222 | ~4,260 | 按需（Track B 深挖） | standards SKILL 的结构风险/严格审查条件 | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/review-code-by-spec/SKILL.md` | 36 | ~690 | 条件（Track C） | reviewer registry；leaf assigned path | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/safety-review/SKILL.md` | 77 | ~1,540 | 条件（Safety track） | `review-topology.md` Safety admission | 方法 |
| `plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/SKILL.md` | 47 | ~1,010 | 条件（绑定 writer） | 入口 `:35`；各 owning stage 的物理写入声明 | 方法/接口混合 |
| `plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/references/role.md` | 60 | ~1,170 | 条件（writer 启动/恢复） | standing-bookkeeper `:42`；role `:8` | 方法 |
| `skills/call-grok/SKILL.md` | 63 | ~950 | 条件（选择 `$grok-worker`） | `worker-resolver.md`解析表 | 方法/接口混合 |
| `skills/call-grok/references/caller-contract.md` | 123 | ~1,600 | 条件（$grok-worker invocation） | `call-grok/SKILL.md:62` | 方法 |

四个 review track 的 leaf 内部材料合计约 **11,500 token**。如果把它们也错误地当作主控 read，保守总量从 100,300 上升到约 **111,700 token**。standing bookkeeper 和 call-grok 是另一侧的冷启动，不是主控 savings 的直接对象。

### 1.5 legacy/route 边界

`impl-package/references/impl-package-current-state.md:3`链接的 `plugin-marketplace/plugins/impl-package/references/ticket-first-migration-runbook.md` 为 **23 行 / ~1,030 token**，只在 3.4/Task package 迁移时条件加载；普通 3.5 Ticket-only dev 不计入上面的典型总量。

入口路由表还可到达 `grill-me-smartly`（~2,990 token）、`grilling`（~1,720 token）和 `create-task-dag`（~520 token）等独立动作。它们不是一次正常 dev attempt 的必经节点；若 owner 要审计“入口菜单的所有 sibling 的静态传递闭包”，应另开一个 route-wide audit，不能把这些可选动作混进本次典型执行读数。

## 2. 接口知识与方法知识

### 2.1 判定规则

- **接口知识**：主控必须知道才能正确调用和验收，例如触发时机、输入、返回 envelope、Gate/approval 边界、结果如何分流。
- **方法知识**：实际执行者才需要，例如如何解析 66 个 `when` key、如何构造 trail、如何写 Ticket/Plan、review checklist、backfill routing 和 retry/fallback 细节。
- 混合文档按 heading/段落拆分，不按文件名粗暴归类。比如 `do-review/SKILL.md` 的 trigger/mode/ownership 是接口，ledger canonicalization 是方法；`current-state.md` 的 state schema/CLI 既是主控调用接口又是状态合同，保留在主控。

### 2.2 非重叠分组估算

为避免重复计数，下表把 75 份主链/条件/worker 文档分成互不重叠的组。总量是 **111,732 token**，其中包含四个 reviewer track 的内部文档；不包含 eval/rubric/脚本源码。

| 分组 | 总 token | 接口估算 | 方法估算 | 方法占比 | 典型内容 |
| --- | ---: | ---: | ---: | ---: | --- |
| 主控阶段 Skill（9 个主链 + plan-review + preflight） | ~16,734 | ~10,040 | ~6,694 | 40% | route、approval、execution、claim、Gate 的主流程和 caller glue |
| 共享合同（Composition、Current State、Progressive Evidence） | ~6,488 | ~3,796 | ~2,692 | 41% | artifact/state/证据边界；progressive 中的判断方法 |
| req-align 内容（不重复计 router） | ~13,820 | ~4,146 | ~9,674 | 70% | requirement capture、PRD、contract surface、Decision/Spec Gate、模板 |
| situation runtime/trajectory 三件套 | ~41,420 | ~2,071 | ~39,349 | 95% | `situation-inputs.md`、YAML 56 rows、trail schema |
| subagent scheduling references | ~2,139 | ~1,176 | ~963 | 45% | mode、parallel admission、review gate、worker resolver |
| do-review parent references（不重复计 parent Skill/leaf） | ~5,286 | ~2,114 | ~3,172 | 60% | registry、topology、brief、output/ledger contract |
| 四个 reviewer leaf track 内部材料 | ~11,457 | ~573 | ~10,884 | 95% | behavior/standards/spec/safety checklist 与方法 |
| planning/Ticket 条件材料 | ~5,239 | ~786 | ~4,453 | 85% | patching、plan review checklists、templates、authorization |
| dev ancillary materials（不重复计 situation 三件套） | ~2,766 | ~691 | ~2,075 | 75% | runtime/control-flow、Gate/ER/progress/manual templates |
| backfill ancillary materials（不重复计 backfill Skill） | ~6,383 | ~1,277 | ~5,106 | 80% | audit/apply/verify/retirement runbook、配置、报告模板 |
| **合计** | **~111,732** | **~26,670** | **~85,062** | **76.1%** | — |

### 2.3 主控应保留什么

常驻主控的不是整份方法文档，而是下面的薄接口：

- route/阶段 ownership：何时进入 req-align、planning、execution、review、claim audit、backfill；
- Composition/Current State 的 authoritative source、Ticket dependency、revision/environment、Gate 和 approval 边界；
- worker scheduling envelope：`mode / worker / schedule / review`，以及 `DONE/BLOCKED/INCOMPLETE`、`review_state` 如何影响主控判断；
- do-review 的触发、phase、track 选择、scope、immutable ReviewRun 和 fail-closed report 字段；
- Decision/Spec 的角色差异、Gate 结果、owner approval 和“不能把 worker PASSED 当 owner approval”；
- verification 的 claim-to-evidence contract；
- Situation renderer 的结构化返回（`selected`、`parallel_matches`、`undetermined`、`unmatched`、digest），而不是 66 个 key 的构造方法。

## 3. 跨 skill 重复

### 3.1 当前版本的语义重复清单

下表是按“规则语义”而不是逐字字符串做的人工去重。估算列只统计可以删掉的重复副本，不删 canonical owner，也不删一行必要的 caller/interface 提醒。

| 重复规则 | 当前重复位置 | canonical owner 建议 | 原始重复副本估算 | 安全可省估算 |
| --- | --- | --- | ---: | ---: |
| 新 package 固定 `tickets=true, dag=false`、不制造 Task/DAG | `impl-package/SKILL.md:49-69`；Composition Contract §2；`impl-planning/SKILL.md:12-17,26`；`to-tickets/SKILL.md:17`；Plan/Ticket/Progress templates | Composition Contract §2；下游只留一行接口提醒 | ~350 tok | ~180 tok |
| artifact/state 的物理写入由 standing bookkeeper，语义 owner 仍在主 thread/owning skill | `req-align/SKILL.md:22,35`；`impl-planning/SKILL.md:19,30-41`；`to-tickets/SKILL.md:10`；`dev-with-track/SKILL.md:8,56`；Decision/Spec subskills；standing-bookkeeper | standing-bookkeeper boundary + 各 skill 一句 routing hook | ~550 tok | ~250 tok |
| initial bundle approval 在同一 package/session/update 中沿用；新 package 才重新 approval | Composition Contract §4；`req-align/SKILL.md:24,32,43`；`impl-planning/SKILL.md:23,41`；`patching.md:1-4,31`；plan-review；preflight/auth | Composition Contract 生命周期；下游只指出受影响范围 | ~600 tok | ~300 tok |
| readiness 由 Ticket typed dependency/state，旧 package 才读 Task/DAG；Progress/checkpoint 不授权 readiness | Composition Contract §5-6；Current State §State/Ticket；`dev-with-track/SKILL.md:32,42`；runtime-protocol `:8-9,23`；control-flow | Current State + Composition；runtime 只留 renderer/caller 适配 | ~350 tok | ~180 tok |
| 路径必须 repo-relative、contract reference 指向一级/二级章节而非整份文档/行号 | Composition Contract `:16,48`；`impl-planning/SKILL.md:15`；`to-tickets/SKILL.md:14`；backfill SKILL `:12`；review briefs | Composition Contract；各阶段保留违反时的本地 consequence | ~250 tok | ~120 tok |
| review 触发条件、fresh reviewer/fixer、checkpoint/closure 和 `PENDING_REVIEW` fail-closed | subagent SKILL `:25,51`；`references/review-gate.md:5-23`；mode-contracts `:30`；do-review briefs；YAML review rows | `review-gate.md` + mode/output envelope；dev 只消费 report | ~550 tok | ~280 tok |
| evidence 必须带直接 artifact、claim、revision、environment；普通 PASS 不能升级成 package completion | Current State `:55`；runtime-protocol `:15`；mode-contracts；verification SKILL `:35-62`；trail/situation contract | Current State/verification；worker/renderer 只返回 tuple | ~400 tok | ~200 tok |
| terminal Gate 后 Attempt 冻结；新工作走 patch；completion claim/Stage 7/Gate 必须按顺序收口 | Composition Contract §4；dev SKILL Verify/Gate；control-flow `:10-18`；runtime `:35`；verification `:20-29`；patching | Composition/verification；dev 留一行 Gate handoff | ~350 tok | ~180 tok |
| do-review 默认 Track A/B/C，Safety 条件追加；closure 不等 terminal-final | do-review SKILL `:17,43,70`；reviewer-registry；review-topology | registry/topology machine/source，SKILL 只说何时消费 | ~200 tok | ~100 tok |
| **跨 skill 语义重复小计** | 9 个簇；按同一 mixed-byte/token 口径 | — | **约 3,550–3,900 tok** | **约 1,700–2,000 tok** |

`review-gate` 是否在 `dev-with-track` 中被完整重述：**当前不是**。working tree 的 `dev-with-track/SKILL.md` 已把 source recheck、P1/P2 closure 和 findings 四路分流的长段删掉，只保留 `:75-77` 的 review/report 消费边界；`review-gate.md` 当前也把主 session finding 的 fresh fixer 交给处境表。这是正确方向，剩下的是必要接口提醒，不应再删除到主控无法判断 `PENDING_REVIEW`/closure 的程度。

### 3.2 处境表本轮重复的独立读数

当前未跟踪的 `docs/skill-design/impl-package-situation-table-260815/rule-coverage-map.md` 已给出上一轮对照口径：共 **127 条规则**，其中 **25 完全承载、72 部分承载、30 未承载**；建议卸掉的纯重复为 **9 条**（D55、D57、D58、D60、R06、R15、C04、C07、G09）。该对照的实际结论是净减约 **2 行**，说明“把相同句子移入处境表”不是主要降载杠杆；本节的跨 skill 去重也应优先删方法副本，而不是继续复制更多表行。

## 4. agent 化候选评估

### 4.1 do-review 的四个 track

#### 结论

这是四项判据中最强的候选。推荐把 Track A/B/C/Safety 的内部检查作为 leaf worker；主控只给 ReviewRun、phase、scope、选中的 track 和政策，主控保留 topology 选择与总体 verdict。四个 leaf 的内部文档约 **11,457 token**：A 约 3,165、B 约 6,060、C 约 693、Safety 约 1,539。正常默认三 track 省约 **9,900 token**，适用 Safety 时省约 **11,500 token**。

| 判据 | 实证判断 |
| --- | --- |
| 接口窄 | **强**。每个 leaf 只需一个固定 ReviewRun + assigned track/path；返回 track verdict、coverage、candidate findings。共同 context 虽然字段多，但不需要把内部 checklist 传给主控。 |
| 主控判断不依赖内部方法 | **强**。主控判断“何时 review、选哪些 track、scope/phase、findings 如何归类和是否收敛”；不需要知道 A 如何追行为、B 如何找 smell、C 如何对 Spec、Safety 如何走五类审查。 |
| 内部知识量大 | **强**。四个 track 内部材料 11.5k token，且 B 的 strict maintainability 一份就约 4.3k；这些知识主要在 leaf 内部复用。 |
| 结果可验收 | **强，但必须结构化**。`output-templates.md` 已要求 per-track verdict、coverage、evidence、finding classification、dedup/convergence。leaf 不得返回裸 `PASS`，也不得自己决定 overall verdict。 |

#### 建议接口

输入：

```text
ReviewRun = {
  base_sha, head_sha, diff_range, included_commits,
  phase: initial | finding-closure | terminal-final,
  mode, round, round_cap, scope,
  immutable_contract_sources: [{path, git_object_id, sha256}],
  standards/spec-discovery/safety evidence,
  selected_track: review-code | review-code-by-standards |
                   review-code-by-spec | safety-review,
  prior_canonical_ledger_readonly
}
```

返回：

```text
TrackResult = {
  track, phase, base_sha, head_sha,
  verdict: PASS | FAIL | UNCERTAIN,
  coverage: [...],
  findings: [{id, status=candidate, severity, invariant, evidence, impact, handoff}],
  evidence_gaps: [...], cleanup/residue, next_action
}
```

leaf 不返回 topology、capacity、cross-track classification 或 overall verdict；父级 `do-review` 负责合并到唯一 canonical ledger。主控验收最低要求是：SHA/范围与 ReviewRun 一致、每个 selected track 都有结果、每个 finding 有 target-revision evidence、coverage 不为空、`UNCERTAIN`/incomplete 不被当作 PASS。

### 4.2 req-align 的 Decision + Spec

#### 结论

可以合成一个 **D/S alignment worker**，但不能把它当成 do-review 那种透明度很高的内部方法 agent。Decision 和 Spec 是主控要拍板的产物：Decision 决定为什么做、Core/Capability、方向和 owner decision；Spec 冻结可观察行为、authority、state、permission、recovery、API/data/seam 及 Acceptance Semantics。主控不能把 `PASSED` 标签直接当审批。

两者合成一个 worker **在 initial/full 时更划算**：共享同一 requirement context、repository facts 和当前 package；Spec 必须在 Decision PASSED 后顺序执行，拆成两个 worker 会重复传递需求和当前 artifact。合成不适用于 `decision-only`、`spec-only` 或 follow-up 只改一个 artifact 的 route。

| 判据 | 实证判断 |
| --- | --- |
| 接口窄 | **弱/中**。输入包含 requirement delta、当前 D/S、repository authority/code/tests、route、package 和 owner decisions；输出同时含两个 artifact 的内容/路径、两个 Gate、contract-design disposition、evidence 和 blocker，宽于 review leaf。 |
| 主控判断不依赖内部方法 | **弱**。主控可以把“如何收集输入、如何写 PRD/template、如何做 surface coherence check”交给 worker，但必须自己判断 selected direction、Core/Capability、是否 contract-ready、是否接受 owner decision 和是否批准进入 planning。 |
| 内部知识量大 | **强**。完整 D/S 子图约 15,200 token；required initial/full 部分约 8,500，Focused PRD、contract surface 和模板再增加约 6,600。 |
| 结果可验收 | **中/强**。只要返回 promise→home map、Decision/Spec status、Gate evidence、所有 blocker/owner decision、Spec surface/authority/producer map 和 artifact diff，主控可验收；不能只返回“Decision PASSED / Spec PASSED”。 |

#### 建议接口与收益

输入：

```text
AlignmentInput = {
  route: full | decision-only | spec-only | follow-up,
  package_id, current_head,
  requirement_and_delta,
  current_decision/spec/contract_design paths and contents or fixed refs,
  repository instructions, authority sources, relevant code/tests,
  already-confirmed owner decisions and explicit constraints
}
```

返回：

```text
AlignmentResult = {
  decision: {status, selected_direction, core_capability_boundary,
             promise_home_map, blockers, owner_decisions, evidence},
  spec: {status, behavior/state/permission/recovery/acceptance summary,
         surface_map, authority_producer_map, contract_design_disposition,
         blockers, evidence},
  route_next, canonical_paths, comparison_head,
  needs_main_approval: true
}
```

主控 context 可省下的是方法部分，不是完整 15.2k：简单 initial/full 约 **4–6k**，带 Focused PRD 和多个 contract surface 约 **7–10k**。把 D/S 合成一个 worker 相对两个独立 worker 另可少传一份共享 requirement/current-artifact context；实际 prompt 大小当前未记录，保守估计 **1–3k token/initial bundle**，应在试运行中测量，不能当成已证实数字。

不适合外包的部分：最终 product direction、Core/Capability 边界、owner decision、Decision/Spec Gate 的采信、contract ambiguity 是否阻断 planning，以及是否批准 bundle。worker 可以起草和给 evidence，不能以定位失败为由要求主控补交 artifact/section/operation 清单；物理写入仍由 bound bookkeeper 做。

### 4.3 其它候选

| 候选 | 四项判据 | 主控可省 token | 输入/返回 | 结论与不可外包部分 |
| --- | --- | ---: | --- | --- |
| `backfill-stable-docs` 的只读 audit | 接口中等偏窄；判断可分离；方法材料约 4–7k；item report 易验收 | ~2–4k | 输入 package/config/source HEAD；返回 item ID、origin、source/destination、statement、evidence、disposition、blocker | 适合第三顺序。主控必须批准精确 item ID；Apply、删除、retirement 不外包审批。 |
| `plan-review` full-review | 接口中等；内部 checklist 约 3.2k；结果有 verdict/findings | ~2–3k | 输入固定 plan/Ticket/D/S/HEAD；返回 material findings、coverage、verdict、owner decisions | 可作为 reviewer worker，但 owner approval、bundle readiness 和是否接受 `admitted` 留在主控。 |
| situation renderer | 接口极窄、内部知识约 41.4k、结果可机械验收，但已有 deterministic `situation.py` | **当前实际 0**；Markdown 本来不应装入主控 | 输入 package + validation result + optional digest；返回 selected/parallel/undetermined/unmatched/digest | 不应再做 LLM agent；继续用 CLI/tool。把 41.4k 方法材料变成 agent 会增加冷启动和漂移，不能胜过现有 parser。 |
| `standing-bookkeeper` | 已经是 sidecar；自然语言事实→receipt 接口尚可，内部约 2.2k | 主控已避免加载其 role | 输入事实/结论、依赖性；返回理解/写入/验证/阻塞 receipt | 不再扩大接口。尤其不要把定位知识推回主控；§19 的教训正是接口会因 `artifact/section/operation` 变宽。主控只验收 receipt。 |
| `verification-before-completion`/Gate | 接口看似简单，但 claim scope、evidence freshness、owner acceptance 是主控判断 | ~0–2k | 输入 claim + evidence + revision/environment；返回 gap/claim status | 可委派证据收集，不外包最终 completion claim、Gate verdict、Stage 7 和 freeze。 |
| 整个 `dev-with-track` 控制循环 | 内部知识大，但接口宽、每轮主控要做 Investigate/Decide/Evaluate | 不宜估 | package state/progress/renderer/worker results→state/Gate | 不建议整体外包；主控必须保留 authority、scope、acceptance、Gate 和 escape 判断。 |

## 5. 三条风险的实证

### 5.1 冷启动成本

| 候选 | 调用频率/冷启动 | 是否可能不划算 | 护栏 |
| --- | --- | --- | --- |
| do-review leaf | initial 和 terminal-final 各一次；finding-closure 可能每个 finding batch 一次；Loop 每轮对 active track fresh start。四 track 一轮约 11.5k 内部读入 | **小 diff、重复 closure、Loop** 时可能不划算；省的是主控 context，不是全系统 token | 尽量把同一批 findings 合并为一次 closure；只在 owner 选择的 track/phase 派发；不要把 Loop 的 fresh 规则改成隐式复用。 |
| D/S combined worker | initial 少量调用，follow-up/behavior change 会重复；单次内 D→S 顺序 | 低频，通常值得；若每次只改一条 Spec，调用 full D/S worker 反而浪费 | route-aware：decision-only/spec-only/follow-up 不强行合并；一次 worker 内复用同一输入。 |
| backfill audit | terminal 后通常一次，可能因 durable delta 多次审计 | 冷启动通常可接受；不应为了每个候选 item 单独起 worker | 一个 package 一次 item-level report，主控批量验收。 |
| situation parser | dev 每轮都可能调用，但 CLI 是低成本确定性工具 | LLM agent 会比当前工具更贵，不应 agent 化 | 只传 JSON/digest；不要传 `situation-inputs.md`。 |

### 5.2 接口漂移

`docs/skill-design/impl-package-standing-bookkeeper-skill-design-260814.md` §19 是现成教训：一旦 worker 的定位能力不足，把 `artifact / section / operation` 退回主控，接口就从“事实/结论”变成“事实 + 物理定位 + 写入操作”，上下文和耦合同时增加。

- do-review 的防漂移边界是 immutable ReviewRun：主控传 resolved SHA、contract source record、scope 和 assigned track；leaf 不自己找相似 Skill、不决定 topology、不把跨 track 分类推回主控。
- req-align 的防漂移边界是传当前 requirement/authority 和 package identity，但让 worker 按现行 owning-stage 规则产出 promise/home/surface map；不能要求主控预先列出每个 Decision/Spec 章节，也不能让 worker 发明第二套 contract。
- backfill 的防漂移边界是 item ID + source/destination/evidence；不能让 worker 返回“请主控自行判断这条长期知识属于哪里”的开放式定位结果。
- situation 的防漂移边界是直接调用现有 parser；不要把 66 个 key 的解释搬成自然语言 agent prompt。

### 5.3 验收退化

| 候选 | 主控必须收到的结构化字段 | 不能接受的返回 |
| --- | --- | --- |
| do-review leaf | `track`、phase、base/head SHA、verdict、coverage、每条 finding 的 invariant/evidence/impact/status、evidence gap、cleanup/residue | 裸 `PASS`、无 coverage、把 candidate 当 accepted、没有 target-revision evidence |
| D/S combined | Decision/Spec 各自 status、promise→home、selected direction、surface/authority/producer、contract-design disposition、Gate evidence、exact blocker/owner decision、`needs_main_approval=true` | 只有两个 artifact 路径或“Gate passed”；漏掉 owner decision/contract ambiguity |
| backfill audit | `<package>::<delta-id>`、origin、source/destination、statement、comparison commit、evidence、candidate/already-covered/conflict/no-delta | “建议回刷若干文档”、无 item ID 或无 done/gap-catching 证据 |
| situation renderer | `selected`、`parallel_matches`、`undetermined`、`unmatched`、priority/layer、digest；保留 unknown，不把 U 当 false | 只返回一个推荐 action，隐藏并列/unknown，或让 agent 重算表语义 |

## 6. 方案与顺序

### 6.1 常驻主控

保留在入口和主控上下文：

1. `impl-package` route、Composition Contract、Current State 的 authoritative boundary；
2. req-align 的 Decision/Spec 角色、Gate、owner approval 和返回 handoff（方法 reference 按需读）；
3. impl-planning 的 admission backstop、Composition/coverage/approval；
4. dev-with-track 的 Investigate/Decide/Implement/Evaluate ownership、renderer caller glue、Ticket acceptance、Gate/freeze；
5. subagent 的 mode/worker/review/schedule envelope 和 `DONE/BLOCKED/INCOMPLETE` 结果边界；
6. do-review 的何时触发、track 选择、scope、phase、immutable ReviewRun、fail-closed aggregation；leaf 内部 checklist 下沉；
7. verification 的 claim-to-evidence contract；backfill 的 audit/apply/retirement 阶段边界和 exact item approval。

### 6.2 按需读取

- `progressive-system-evidence.md`：只在 material seam、跨模块、昂贵 browser/provider/native-tool 或系统性 failure 时读；
- `focused-prd.md`、`contract-surface-design.md`：只在对应 Decision/Spec signal 出现时读；
- plan-review 的五份 checklist：只在 full-review 或信号触发时读；
- `parallel-work-admission.md`：只有两个以上 bounded unit；`review-gate.md`：只有 review required；strict maintainability：只有结构风险；
- `situation-inputs.md`、`trail-schema.md`：维持当前 `dev-with-track/SKILL.md:69` 的 no-runtime-open 约束，只在表维护、per-package override 或 trail schema 维护时读；
- backfill audit/apply/verify/retirement runbook：只按当前阶段读；apply/retirement 额外要求 exact owner authorization；
- legacy migration/runbook/template：只在 3.4 package 恢复/迁移。

### 6.3 外包

1. **第一步：do-review 四个 leaf track。** 固定 ReviewRun + selected track 输入；结构化 TrackResult 返回；主控继续拥有总体判断。
2. **第二步：req-align D/S combined worker。** 只做 draft/evidence，内部顺序 Decision→Spec；主控审批；decision-only/spec-only/follow-up 保持 route-aware。
3. **第三步：backfill audit worker。** 一次产出 item-level inventory；主控批准 exact IDs；Apply/retirement 不自动化 owner decision。
4. **可选第四步：plan-review worker。** 先只 externalize checklist execution，保留 bundle admission/approval 在主控。

### 6.4 为什么第一步是 do-review

它同时满足“节省大、接口窄、主控不需内部方法、结果有现成验收合同”四项；而且当前 `do-review` 已有 immutable ReviewRun、registry、brief、output template 和 parent/leaf ownership，新增 agent 边界是在收紧现有边界，不需要重新发明 D/S contract。req-align 的绝对方法量也大，但 approval interface 宽，第一步外包容易把“worker 产出”误当“owner 拍板”。

## 7. 审计状态

本报告已完成本轮的测量、加载分类、接口/方法分层、重复清单、agent 候选和排序方案；**任务在“只读审计/报告”阶段 closed**。Skill/脚本/表/fixture 的 apply、worker 化实现和验证尚未做，也不属于本轮授权。下一项需要 owner 决定的是：是否按 6.3 批准先做 do-review leaf agent 边界试点；在此决定前不应修改任何实现文件。
