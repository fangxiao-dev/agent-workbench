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

Ledger 是过程 source of truth，记录问题、回答、已收敛决策、待用户裁决与停止证明。所有 ledger 读写一律经 `scripts/grill_ledger.py`（init/status/add-question/record-answer/converge/need-user/end-turn/stop）；脚本拥有 ledger 结构与中文摘要区块（已收敛决策摘要/待用户裁决/问题与回答总览/停止证明），并只在合法 stop 时生成独立中文 Grill Review——它是面向人的交付物与 approval surface，不混入过程日志。Ledger 默认在 OS 临时目录，不建仓库内 ledger；`init` 拒绝覆盖，已有则 `status` 继续；slug 用被审文档 basename，无锚定时问用户。简短请求（如"审 docs/plans/x.md"）即视为授权运行全流程，无需重述内部角色与 ledger 机制。

## Review Then Apply

Review 阶段在 ledger 维护完整过程，不修改被审阅文档；只有用户读过 Grill Review 并明确要求 apply 后，才进入 Apply 阶段，且只应用已收敛决策与用户批准的裁决，未决项保留在 ledger。

## Roles

- **Main session**：scribe/judge/user-intent gatekeeper，唯一 ledger 写入者（经脚本），并负责问真实用户。
- **Questioner subagent**：拥有决策树，一次只提一个最高价值问题并说明为何现在重要，不自答。
- **Answerer subagent**：只答本地文件/代码/git 历史/工具可解决的事实问题；不答产品意图、偏好或风险容忍度。
- **Critic subagent**（可选）：每五个已回答问题后或停止前检查缺失分支、过早收敛、重复提问、用户意图被误当本地事实；接受的批评点以新问题记入 ledger。

Subagents 不直接写 ledger，返回结构化文本由 main session 记录。

## Loop

1. 确认目标并读够理解设计树；review 期间不编辑目标文档。
2. init/status 加载 ledger。
3. Questioner 提问 → `add-question`（不合并无关问题）；本地可答则交 Answerer → `record-answer`，依赖产品意图/偏好/风险/外部事实则 `need-user` 问真实用户一个问题。
4. 本地证据可解决则 `converge`（中文收敛行：选择、理由、影响）；每轮 `end-turn`；状态为进行中则继续——单个问题解决不代表审阅结束。
5. 需要时 critic pass；仅当所有 material branch 已收敛、剩余问题需真实用户、或后续问题会重复已解决决策时，才 `stop --proof`（proof 由 Questioner/critic 提供）。
6. 最终回复给出两个临时文件路径并总结：已做决策、已问已回答、仍待用户；不修改被审阅文档，请用户检查后明确要求 apply。

## Question Quality Bar

好问题：force one exact decision、点名受影响分支、说明为何现在重要、证据充分时给 recommended default、避免问本地可查事实（除非让 Answerer 验证）。坏问题：捆绑无关决策、问 ledger 已记录信息、让 Answerer 推断用户偏好、无 stop proof 停止。

## Common Mistakes

- main session 重掌决策树（树归 Questioner）；subagent 直接写 Markdown（脚本拥有结构）；首个回答当整个审阅（须等 stop proof）；只记最终决策（问题与回答保留在 ledger，停止时发布 Grill Review）；Review 阶段修改被审阅文档。
