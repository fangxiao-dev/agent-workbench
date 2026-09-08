---
name: grill-me-smartly
description: >
  Review a plan with a Chinese Grill Ledger, a standing questioner subagent, and
  a local-fact answerer subagent. Use the standalone grilling skill for the
  question protocol, then record every question, answer, decision, and stop proof
  for high-risk Spec gates or auditable plan reviews.
---

# Grill Me Smartly

Questioner 按 grilling 的节奏提问，Answerer 先代 Owner 回答可查事实，两者直接对话并保存每轮记录。主控审定事实结论，跨轮整合为连贯设计，再向 Owner 汇报与提请裁决。`grill-<slug>.ledger.json` 是唯一权威状态，批原件保留完整问答，`.ledger.md` 只提供短状态、计数和分页索引；合法停止后由主控编写独立中文 Grill Review，供 Owner 审阅后决定是否 apply。

## Question Protocol Dependency

开始前通过宿主 Skill 目录读取普通 Skill `/grilling`，并将其解析后的文件路径交给 Questioner。它唯一拥有设计树、frontier、分批提问、问题内容与回复合同。本 Skill 只负责角色协作、记录和 Review/Apply gate。

完整 frontier 由 Questioner 持续跟踪；每次只展开 `/grilling` 当前可读的一批，收到该批回答后再计算后续问题。未展开项以稳定 ID、前置条件和分支摘要保存在 frontier 文件中，新的回答使某项失效时记录原因。题数、批次大小和追问节奏由 `/grilling` 决定。

若 `/grilling` 不可用，使用简化降级：Questioner 每次提出下一个最高价值问题，点名分支、说明为何现在重要，并在证据充分时给推荐答案。仍执行本文角色、记录与停止规则；最终明确报告“未加载 `/grilling`，本次使用简化降级”。

## Review Then Apply

短请求（如“用 /impl-package:grill-me-smartly 审 docs/plans/x.md”）授权初始化或恢复 ledger、运行问答并交付 Review。Review 期间只写临时过程产物，保持被审 plan、spec、PRD 和源文档不变。

只有 Owner 读过 Grill Review 并明确要求 apply 后，才将已收敛决策及 Owner 批准的裁决写入目标文档。未决项继续保留；subagent 共识是候选结论，不能替代 Owner 对新产品意图、偏好或风险取舍的批准。

Apply 时按目标文档已有的概念与章节吸收设计：更新对应规则，合并重复表述，将已被批准的新结论替代的旧表述同步清理；边界、状态转换、失败恢复与例外归入各自规则。验收以最终文档内部一致、每项有效承诺均有归属为准，问答顺序和 Q 数量不决定正文结构。

## Roles

- **Main session**：judge、设计整合者、user-intent gatekeeper。派发角色和材料，通过脚本批量导入正式 ledger 并审定事实结论，跨轮合并规则、处理冲突、向 Owner 汇报与提问；检查 stop proof 后亲自编写 Review。正式 ledger 只有主控通过脚本写入，Review 由主控组织内容。
- **Questioner subagent**：拥有设计树和 frontier 文件；按 `/grilling` 向 Answerer 提问，检查回答和证据、保留异议，决定本批是否需追问。向主控返回本批审查摘要、剩余分支索引和需要裁决的事项。
- **Answerer subagent**：先代 Owner 回答本地文件、代码、git 历史、文档或工具可解决的问题，并引用证据。对于新意图或取舍，说明事实基础与缺口，标为 `needs_user`；已确认的 Owner 决策可以引用。负责保存双方每批的问答、澄清、异议和候选结论。
- **Critic subagent（可选）**：每五个已回答问题后或停止前检查遗漏分支、过早收敛、重复提问和意图越界。接受的缺口回交 Questioner 作为问题处理。

## 临时产物

文件位于 OS 临时目录 `<os-temp>/codex-grill/`，使用被审文档 basename 生成 slug；无文件锚定且没有明显 slug 时询问 Owner。

| 文件 | 写入者与用途 |
| --- | --- |
| `grill-<slug>.frontier.md` | Questioner：设计树、稳定问题 ID、依赖、剩余项、失效原因与恢复锚点 |
| `grill-<slug>.round-<batch-id>.json` | Answerer：不可变的批原件；`batch-id` 同时区分 grilling 的轮和轮内批次，如 `R1-B2` |
| `grill-<slug>.ledger.json` | 主控通过脚本维护的唯一权威状态：来源路径/哈希/引用、问题映射、控制器裁决和必要的变更历史 |
| `grill-<slug>.ledger.md` | 从 JSON 派生的短状态、计数、前 20 条待处理索引和命令；不嵌入完整 JSON 或问答 |
| `grill-<slug>.review.md` | 合法 `stop` 后由主控编写：整合后的整体方案、规则、例外、影响与待裁决项 |

frontier 和批原件是恢复依据，随产生及时保存；已导入批文件保持原路径和原字节不变，JSON ledger 只保存其路径、哈希、引用、问题映射和主控裁决。`get-question` 取详情时解析并校验原件；原件缺失或哈希变化只对该详情返回明确错误，不能阻塞 `status` 或索引。旧的嵌入 JSON ledger 可只读查询；首次 mutation 先以 `grill-<slug>.legacy.md` 备份原字节，再原子提交新 JSON，随后生成派生索引，不做批量迁移。发给主控的交回通知只传文件路径、当前批 ID 与简短增量摘要，主控按需读当前批。

## Loop

1. **加载与恢复**：读取 `/grilling` 和目标材料。无 ledger 时 `init`；已有记录先运行 `status` 取得紧凑状态、计数和文件路径，再用 `list-questions` 分页读取索引（默认首 20 条），只对选中的 Q 使用 `get-question` 读取详情，必要时显式加 `--history`。随后读取摘要、frontier 与未导入批文件，识别已处理项和剩余项；不要用 `Get-Content` 或等价方式展开整个 JSON/Markdown 状态。
2. **启动两个角色**：使用 standing Questioner 和 Answerer，向两者提供目标材料快照、协议路径、Owner 已确认选择、当前摘要、各自写入路径及对方 agent ID。宿主支持 peer messaging 时让两者直接通信；需由主控唤醒 idle agent 时只传批 ID 和文件路径。宿主只能经主控路由消息时，转交文件引用，仍由 Answerer 保存问答。发生上下文压缩后，从这些文件和材料快照启动 fresh 角色。
3. **本批问答**：Questioner 按 `/grilling` 向 Answerer 提出当前批，Answerer 查证并按批回复。Questioner 检查证据，必要时继续澄清；Answerer 将有实质内容的往返完整保存在原路径的批文件中，后续导入不得改写原件。需要 Owner 的问题及其依赖分支保持未决，独立的事实问题继续按协议推进。
4. **交回本批**：Questioner 将检查意见回发 Answerer 并更新 frontier；Answerer 将反馈写入批记录后完成保存。两者向主控报告原件路径、问题数、候选结论和待裁决项，等待本批后处理结果。此时本批每项都有事实答案或明确缺口，后续分支有可恢复的索引。
5. **主控后处理**：读取本批文件和 Questioner 检查结果，通过 `import-round` 一次导入来源引用；用 `--accept` 指定证据充分且不涉及新 Owner 取舍的候选结论 ID。JSON 只保存来源路径、哈希、映射和控制器裁决，不复制完整问答；其余记录保持已回答或待用户裁决，异议和不确定性仍从原件解析。修改候选结论时使用现有 `converge`；Owner 回答经 `record-answer` 记录后再收敛。导入重试沿用原批文件和相同接纳列表。
6. **整合与继续**：主控将本批结论与前轮设计按主题合并，识别共同规则、适用边界、例外和冲突。已确认的替代关系保留依据；尚未裁决的冲突回到相关问题处理，不凭轮次新旧决定取舍。向 Owner 汇报整合后的设计变化、影响与剩余事项；真正需要 Owner 的选择按 `/grilling` batch 与 reply contract 提出。将审定结果、ID 映射和 Owner 回答交还 Questioner，再继续下一批。需要 Owner 的前置选择得到回答后，才展开其依赖问题。`end-turn` 用于记录完成一轮；单项收敛不表示 review 结束。
7. **检查与停止**：按需运行 Critic；停止前从 Questioner 或 Critic 获取 stop proof，核对 frontier、未导入批文件与 ledger。只有所有 material branch 已收敛、剩余项仅依赖真实 Owner，或继续提问只会重复已解决决策，才执行 `stop --proof`。未查清事实或未处理异议不满足停止条件。
8. **编写与交付 Review**：`stop` 只校验并记录停止状态，成功不代表 Review 已完成。主控按下述整合标准编写或更新既有临时 Review 路径，逐项核对有效结论的归属后再交付 Review 与 Ledger。说明已问已答、已收敛和仍待 Owner 的数量。恢复已有 Review 时也对照当前 ledger 重新核对内容；Owner 审阅并明确要求 apply 后才进入写回。

## Review 整合标准

先解释整体方案和关键机制，再按设计主题组织规则；同一规则可吸收多轮多个 Q 的结论。每条规则说明适用条件、理由、影响及必要证据，将边界和例外挂在对应规则下。同一规则只有一个完整展开的位置，其他主题引用该规则；Apply 也为它选择一个规范章节。章节按概念关系组织，篇幅与规则数由设计本身决定。

规则附来源 Q ID；交付前逐项对照 ledger，确保每项有效结论都进入某条规则或明确的待裁决项。已被替代的结论在来源说明中指明替代依据，不与现行规则并列生效。跨轮冲突必须显式解决或列为待裁决，重要失败语义不能在概括时丢失。保留 ledger 作为完整过程记录，Review 展示整合结果、影响、待裁决项和停止依据。

例如，多轮删除问题可能共同支撑“先持久化意图再执行删除”“成功后清理元数据”“失败沿原 operation 恢复”等规则；部分成功、对象缺失与引用阻断归入相关规则的边界和例外。“67 问归纳为 6 条”只说明可跨问题整合，不是交付配额，也不是本 Skill 对业务方案的预设。

## Ledger Commands

准备或导入批文件前，主控和 Answerer 读取 [批记录格式](references/round-record.md)。Questioner 读取其中检查反馈的字段要求。所有命令使用 [scripts/grill_ledger.py](scripts/grill_ledger.py)；从任意目标仓库运行，默认产物仍在 OS 临时目录。JSON 是权威状态，Markdown 是派生索引；参数含空格时遵守宿主 shell quoting 规则。

```text
python <skill>/scripts/grill_ledger.py init --topic <plan-or-topic> --slug <slug> --initiator <main-session-name>
python <skill>/scripts/grill_ledger.py status --slug <slug> [--proof]
python <skill>/scripts/grill_ledger.py list-questions --slug <slug> --offset 0 --limit 20
python <skill>/scripts/grill_ledger.py get-question --slug <slug> --question Q1 Q2
python <skill>/scripts/grill_ledger.py import-round --slug <slug> --file <round-json> --accept R1-Q1 R1-Q2
python <skill>/scripts/grill_ledger.py record-answer --slug <slug> --question Q1 --author Owner --answer <answer> --evidence <source> --uncertainty <uncertainty> --needs-user false
python <skill>/scripts/grill_ledger.py converge --slug <slug> --question Q1 --line <decision> --rationale <why> --impact <impact>
python <skill>/scripts/grill_ledger.py need-user --slug <slug> --question Q1 --line <question-for-owner>
python <skill>/scripts/grill_ledger.py end-turn --slug <slug>
python <skill>/scripts/grill_ledger.py stop --slug <slug> --proof <stop-proof>
python <skill>/scripts/grill_ledger.py rebuild-index --slug <slug>
```

`status` 默认只输出紧凑状态、各状态计数和 JSON/Markdown/Review 等文件路径，不输出完整状态；按需加 `--proof` 才附上 `stop_proof`。`list-questions` 支持 `--offset`、`--limit`、中文 `--status` 和 `--branch` 子串过滤，返回 `id`、`branch`、`preview`、`status` 与 `next_offset`；`get-question` 只返回所选问题的有效详情，`--history` 才展开必要的历史版本。原件缺失或哈希变化时，详情命令返回明确错误，但 `status` 和索引仍可用；legacy 详情通过 `legacy_archive` 指向只读原记录。`rebuild-index` 从 JSON 重建 `.ledger.md`；索引生成失败只告警，已保存的 JSON 不回滚。

省略 `--accept` 时仅导入问答和待用户项；接纳列表是主控的裁决，Answerer 只生成候选。旧 `add-question`、`record-answer` 命令继续支持恢复与补录；直接答案或决策发生实质改变时保留必要的前一版本，不能用无语义的通用事件日志代替；命令参数通过 `--help` 查看。
