---
name: grill-me-smartly
description: >
  Review a plan with a Chinese Grill Ledger, a standing questioner subagent, and
  a local-fact answerer subagent. Use this when the user wants a relentless
  grill-me style review but also wants the agent to research local facts, record
  every question and answer, and summarize the choices already made on their
  behalf.
---

# Grill Me Smartly

Use this skill to stress-test a plan through a ledger-driven review loop. Ledger 是过程 source of truth，记录问题、回答、已收敛决策、待用户裁决与停止证明；只有合法停止时才生成独立中文 Grill Review，它是面向人的交付物和 approval surface，不混入过程日志。

## User Invocation

用户只需短请求，例如：

```text
用 /impl-package:grill-me-smartly 审 docs/plans/user-auth-migration.md。
```

短请求（如“审 docs/plans/x.md”）即视为授权运行全流程：初始化或加载 Grill Ledger，按需使用 Questioner/Answerer，记录中文摘要并只在有 stop proof 时停止；无需用户重述内部角色、ledger 机制或 subagent 编排。

## Review Then Apply

1. **Review phase**：在 ledger 维护完整过程并生成 Grill Review，不修改被审阅的 plan、spec、PRD 或源文档。Grill Review 必须让用户无需阅读过程 ledger 就能理解最终选择、证据、影响、待裁决项和停止依据；ledger 作为 audit trail 保留。
   - 常见误判：不先隔离 review，临时判断会被误写进目标文档，未决项也会看起来像已批准。

2. **Apply phase**：只有在用户读过 Grill Review 并明确要求 apply 后才开始，只应用已收敛决策与用户批准的裁决，未决项保留在 ledger 或先向用户询问。
   - 常见误判：不经过这道门，模型会把自己的收敛误当成用户对 durable 文档的批准。

## Roles

- **Main session**：scribe、judge、user-intent gatekeeper，唯一 ledger 写入者，所有写入经 `scripts/grill_ledger.py`，并负责问真实用户。
- **Questioner subagent**：拥有设计树，只提出下一个最高价值问题并说明为何现在重要；一次只提一个，不自答。
- **Answerer subagent**：只回答本地文件、代码、git 历史、文档或工具可解决的事实问题；不回答产品意图、偏好或风险容忍度。
- **Critic subagent（可选）**：每五个已回答问题后或停止前检查缺失分支、过早收敛、重复提问和把用户意图误当本地事实的问题；接受的批评点以新问题写入 ledger。

Subagents 不直接写 ledger 或目标文档，返回结构化文本由 main session 记录和判断。

## Ledger Location

Ledger 位于用户 OS 临时目录，不进入当前 workspace：

```text
<os-temp>/codex-grill/grill-<slug>.ledger.md
<os-temp>/codex-grill/grill-<slug>.review.md
```

脚本默认使用该临时位置；不要创建 repo-local `docs/exchange/grill/` ledger，也不要为此修改 `.gitignore`。优先用被审文档 basename 生成 slug；无文件锚定且没有明显 slug 时询问用户。`init` 拒绝覆盖已有 ledger，已有记录用 `status` 继续；为兼容既有记录仍可读取旧的 `grill-<slug>.md`，只有合法 `stop` 才创建或刷新 review 文件。

## Ledger Commands

命令可从目标仓库根执行，但 ledger 仍写入 OS 临时目录；参数含空格时遵守宿主 shell 的 quoting 规则：

```text
python <skill>/scripts/grill_ledger.py init --topic <plan-or-topic> --slug <slug> --initiator <main-session-name>
python <skill>/scripts/grill_ledger.py status --slug <slug>
python <skill>/scripts/grill_ledger.py add-question --slug <slug> --author Questioner --branch <branch> --question <question> --why-now <reason> --recommended-default <default>
python <skill>/scripts/grill_ledger.py record-answer --slug <slug> --question Q1 --author Answerer --answer <answer> --evidence <evidence> --uncertainty <uncertainty> --needs-user true|false
python <skill>/scripts/grill_ledger.py converge --slug <slug> --question Q1 --line <decision> --rationale <why> --impact <impact>
python <skill>/scripts/grill_ledger.py need-user --slug <slug> --question Q1 --line <question-for-user>
python <skill>/scripts/grill_ledger.py end-turn --slug <slug>
python <skill>/scripts/grill_ledger.py stop --slug <slug> --proof <stop-proof>
```

## Loop

1. **确认目标**：识别正在审阅的 plan、spec、PRD 或当前对话，读到足以理解设计树；review 期间不编辑目标文档。
   - 常见误判：没读够设计树就开始提问，后面的 frontier 会建立在错误前提上。
2. **初始化/恢复 ledger**：无记录运行 `init`，有记录先 `status` 并读 Markdown；顶部中文摘要是实时过程摘要，更新仍必须经脚本完成，不是最终交付物。
   - 常见误判：跳过恢复会丢掉已问问题和停止依据，重复提问会被误当成新发现。
3. **启动 Questioner**：上下文未压缩时可复用 standing Questioner；发生 compaction 后用 plan snapshot 和 current ledger summary 启动 fresh Questioner。给它材料快照与摘要，要求一次只提一个问题、不自答，并返回 branch name、exact question、why-now、证据足够时的 recommended default、是否 locally answerable。
   - 常见误判：压缩后复用旧上下文会让已失效的分支重新成为前提。
4. **记录问题**：用 `add-question`，不把无关问题合并到一个 Q item。
   - 常见误判：合并后无法知道哪一个决定已回答，frontier 也会错误收敛。
5. **本地回答**：问题可由本地事实解决时交 Answerer，并用 `record-answer` 记录简洁答案、文件/命令证据、不确定性和是否需要用户意图；否则由 main session 用 `need-user` 问真实用户一个具体问题。
   - 常见误判：把可查事实交给用户，会把事实缺口伪装成偏好决策；把偏好交给 Answerer，则会替用户做决定。
6. **收敛**：本地证据足以决定时用 `converge`，中文收敛行写明选择、理由和影响；每个问题解决不等于整个 review 结束。
   - 常见误判：一个问题的 converge 只释放后续分支，不能证明整棵树已经走完。
7. **继续回合**：每轮完成后 `end-turn`；状态仍为进行中就把更新后的 ledger 摘要交给 Questioner，重新计算 frontier。不要因为一个问题已回答就停止。
   - 常见误判：在首个回答后停止会把尚未展开的 material branch 静默丢掉。
8. **Critic pass**：每五个回答、停止前或 review 显得过窄时运行 critic；把接受的缺口作为新问题记录，不把批评直接写成结论。
   - 常见误判：只让原 Questioner 自检，容易把过早收敛误认为完整性。
9. **停止证明**：只有所有 material branch 已收敛、剩余问题明确需要真实用户，或继续提问会重复已解决决策时，才用 `stop --proof`。proof 必须来自 Questioner 或 critic；单个 converge 不足以停止。`stop` 生成包含最终决策、理由、影响、证据、待用户裁决和停止依据的 `grill-<slug>.review.md`，不包含问题流水和机器状态。
   - 常见误判：没有外部 stop proof 就停止，最终 Review 只是一份自信摘要，不是可审计的收口依据。
10. **最终交付**：给出两个临时文件路径，并总结已做决策、已问已答和仍待用户；review 阶段不更新目标文档，要求用户检查后明确批准 apply。
   - 常见误判：把过程 ledger 当最终交付，用户就无法只看 Review 判断选择、证据和待裁决项。

## Chinese Summary Requirements

Ledger 顶部摘要由脚本维护，至少让不读完整日志的读者看懂：`已收敛决策摘要`（每个选择的理由、影响、证据）、`待用户裁决`、`问题与回答总览`、`停止证明`。只有合法停止时才发布独立 Grill Review；它是用户 approval surface，不取代过程 ledger。

## Question Quality Bar

好问题必须 force one exact decision、点名受影响分支、说明为何现在重要、证据充分时给 recommended default，并避免询问本地可查事实（除非让 Answerer 验证）。坏问题是捆绑无关决策、重复询问 ledger 已记录信息、让 Answerer 推断用户偏好，或没有 stop proof 就停止。

## Common Mistakes

不要让 main session 重新掌管决策树（树归 Questioner）；不要让 subagent 直接写 Markdown（脚本拥有 ledger 结构）；不要把首个回答当成整个 review；不要只记录最终决策而丢掉问题/回答流水；不要在 review phase 修改目标文档。先生成 Grill Review，再等待用户明确批准 apply。
