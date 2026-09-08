---
name: grill-me-smartly
description: >
  Review a plan with a Chinese Grill Ledger, a standing questioner subagent, and
  a local-fact answerer subagent. Use the standalone grilling skill for the
  question protocol, then record every question, answer, decision, and stop proof
  for high-risk Spec gates or auditable plan reviews.
---

# Grill Me Smartly

Questioner 按 grilling 的节奏提问，Answerer 先代 Owner 回答可查事实，两者直接对话并保存每轮记录。主控后处理记录、审定事实结论，再向 Owner 汇报与提请裁决。Ledger 保留过程证据；合法停止时生成独立中文 Grill Review，供 Owner 审阅后决定是否 apply。

## Question Protocol Dependency

开始前通过宿主 Skill 目录读取普通 Skill `/grilling`，并将其解析后的文件路径交给 Questioner。它唯一拥有设计树、frontier、分批提问、问题内容与回复合同。本 Skill 只负责角色协作、记录和 Review/Apply gate。

完整 frontier 由 Questioner 持续跟踪；每次只展开 `/grilling` 当前可读的一批，收到该批回答后再计算后续问题。未展开项以稳定 ID、前置条件和分支摘要保存在 frontier 文件中，新的回答使某项失效时记录原因。题数、批次大小和追问节奏由 `/grilling` 决定。

若 `/grilling` 不可用，使用简化降级：Questioner 每次提出下一个最高价值问题，点名分支、说明为何现在重要，并在证据充分时给推荐答案。仍执行本文角色、记录与停止规则；最终明确报告“未加载 `/grilling`，本次使用简化降级”。

## Review Then Apply

短请求（如“用 /impl-package:grill-me-smartly 审 docs/plans/x.md”）授权初始化或恢复 ledger、运行问答并交付 Review。Review 期间只写临时过程产物，保持被审 plan、spec、PRD 和源文档不变。

只有 Owner 读过 Grill Review 并明确要求 apply 后，才将已收敛决策及 Owner 批准的裁决写入目标文档。未决项继续保留；subagent 共识是候选结论，不能替代 Owner 对新产品意图、偏好或风险取舍的批准。

## Roles

- **Main session**：judge、user-intent gatekeeper。派发角色和材料，读取每批结果并通过脚本批量导入正式 ledger，审定事实结论、向 Owner 汇报与提问，最终检查 stop proof。正式 ledger 只有主控写入。
- **Questioner subagent**：拥有设计树和 frontier 文件；按 `/grilling` 向 Answerer 提问，检查回答和证据、保留异议，决定本批是否需追问。向主控返回本批审查摘要、剩余分支索引和需要裁决的事项。
- **Answerer subagent**：先代 Owner 回答本地文件、代码、git 历史、文档或工具可解决的问题，并引用证据。对于新意图或取舍，说明事实基础与缺口，标为 `needs_user`；已确认的 Owner 决策可以引用。负责保存双方每批的问答、澄清、异议和候选结论。
- **Critic subagent（可选）**：每五个已回答问题后或停止前检查遗漏分支、过早收敛、重复提问和意图越界。接受的缺口回交 Questioner 作为问题处理。

## 临时产物

文件位于 OS 临时目录 `<os-temp>/codex-grill/`，使用被审文档 basename 生成 slug；无文件锚定且没有明显 slug 时询问 Owner。

| 文件 | 写入者与用途 |
| --- | --- |
| `grill-<slug>.frontier.md` | Questioner：设计树、稳定问题 ID、依赖、剩余项、失效原因与恢复锚点 |
| `grill-<slug>.round-<batch-id>.json` | Answerer：当前批记录；`batch-id` 同时区分 grilling 的轮和轮内批次，如 `R1-B2` |
| `grill-<slug>.ledger.md` | 主控通过脚本生成：已导入问答、审定结论、待用户裁决和停止依据 |
| `grill-<slug>.review.md` | 合法 `stop` 时生成：面向 Owner 的中文独立交付物 |

frontier 和批记录是恢复依据，随产生及时保存；已导入的批记录保持不变，后续回答与裁决沿用原 ledger Q ID，澄清产生的新问题使用新批 ID 和新问题 ID 并引用原问题。发给主控的交回通知只传文件路径、当前批 ID 与简短增量摘要，主控按需读当前批。脚本兼容既有 `grill-<slug>.md` ledger；`init` 拒绝覆盖已有记录。

## Loop

1. **加载与恢复**：读取 `/grilling` 和目标材料。无 ledger 时 `init`；已有记录先 `status` 并读取摘要、frontier 与未导入批文件，识别已处理项和剩余项。
2. **启动两个角色**：使用 standing Questioner 和 Answerer，向两者提供目标材料快照、协议路径、Owner 已确认选择、当前摘要、各自写入路径及对方 agent ID。宿主支持 peer messaging 时让两者直接通信；需由主控唤醒 idle agent 时只传批 ID 和文件路径。宿主只能经主控路由消息时，转交文件引用，仍由 Answerer 保存问答。发生上下文压缩后，从这些文件和材料快照启动 fresh 角色。
3. **本批问答**：Questioner 按 `/grilling` 向 Answerer 提出当前批，Answerer 查证并按批回复。Questioner 检查证据，必要时继续澄清；Answerer 将有实质内容的往返完整保存在当前批文件，保留未解决分歧。需要 Owner 的问题及其依赖分支保持未决，独立的事实问题继续按协议推进。
4. **交回本批**：Questioner 将检查意见回发 Answerer 并更新 frontier；Answerer 将反馈写入批记录后完成保存。两者向主控报告文件路径、问题数、候选结论和待裁决项，等待本批后处理结果。此时本批每项都有事实答案或明确缺口，后续分支有可恢复的索引。
5. **主控后处理**：读取本批文件和 Questioner 检查结果，通过 `import-round` 一次导入问答；用 `--accept` 指定证据充分且不涉及新 Owner 取舍的候选结论 ID。其余记录保持已回答或待用户裁决，异议和不确定性可见。修改候选结论时使用现有 `converge`；Owner 回答经 `record-answer` 记录后再收敛。导入重试沿用原批文件和相同接纳列表。
6. **汇报与继续**：主控向 Owner 汇报审定结论、影响与剩余事项；真正需要 Owner 的选择按 `/grilling` batch 与 reply contract 提出。将审定结果、ID 映射和 Owner 回答交还 Questioner，再继续下一批。需要 Owner 的前置选择得到回答后，才展开其依赖问题。`end-turn` 用于记录完成一轮；单项收敛不表示 review 结束。
7. **检查与停止**：按需运行 Critic；停止前从 Questioner 或 Critic 获取 stop proof，核对 frontier、未导入批文件与 ledger。只有所有 material branch 已收敛、剩余项仅依赖真实 Owner，或继续提问只会重复已解决决策，才执行 `stop --proof`。未查清事实或未处理异议不满足停止条件。
8. **交付**：提供临时 Review 与 Ledger 路径，说明已问已答、已收敛和仍待 Owner 的数量。Review 独立解释选择、理由、影响、证据、待裁决项与停止依据，不混入过程流水。Owner 审阅并明确要求 apply 后才进入写回。

## Ledger Commands

准备或导入批文件前，主控和 Answerer 读取 [批记录格式](references/round-record.md)。Questioner 读取其中检查反馈的字段要求。所有命令使用 [scripts/grill_ledger.py](scripts/grill_ledger.py)；从任意目标仓库运行，默认产物仍在 OS 临时目录。参数含空格时遵守宿主 shell quoting 规则。

```text
python <skill>/scripts/grill_ledger.py init --topic <plan-or-topic> --slug <slug> --initiator <main-session-name>
python <skill>/scripts/grill_ledger.py status --slug <slug>
python <skill>/scripts/grill_ledger.py import-round --slug <slug> --file <round-json> --accept R1-Q1 R1-Q2
python <skill>/scripts/grill_ledger.py record-answer --slug <slug> --question Q1 --author Owner --answer <answer> --evidence <source> --uncertainty <uncertainty> --needs-user false
python <skill>/scripts/grill_ledger.py converge --slug <slug> --question Q1 --line <decision> --rationale <why> --impact <impact>
python <skill>/scripts/grill_ledger.py need-user --slug <slug> --question Q1 --line <question-for-owner>
python <skill>/scripts/grill_ledger.py end-turn --slug <slug>
python <skill>/scripts/grill_ledger.py stop --slug <slug> --proof <stop-proof>
```

省略 `--accept` 时仅导入问答和待用户项；接纳列表是主控的裁决，Answerer 只生成候选。旧 `add-question`、`record-answer` 命令继续支持恢复与补录；命令参数通过 `--help` 查看。
