# Dispatcher、SDD 与 Dev With Track 联合调整提案

## 1. 结论与文档状态

建议将 Dispatcher 与 Subagent-Driven Development（SDD）合并为一个通用执行协作 Skill，保留 `$dispatcher` 名称；dev-with-track 继续拥有业务合同、Ticket readiness、证据与 Gate，同时调整其向调度层提供候选工作的方式。联合修改直接调用入口、处境提示与验证合同，避免正文已经鼓励并行，运行时注入仍要求等待。

本次优化以有效交付速度和执行可信度为目标。主控持续寻找能够推进主线的并行机会，准确限定局部阻塞的影响；worker 收到具体、可验证的委派合同。确定性落实在授权、行为要求、资源边界和证据上，执行路径由主控根据现场事实选择。

- 日期：2026-09-08。
- 状态：Proposal；Owner 已同意联合调整方向，并授权详细提案落盘。本文细化方案供后续实施使用，尚未改写 Skill、运行模型行为评测或发布安装。
- 调研基线：仓库 HEAD `cb906e681292a0d85aa38f0b2084df731b992804`；开始调研时工作区干净。另只读对照用户指定的 `impl-package/0.4.2` 安装缓存。
- 目标源文件：`skills/dispatcher/SKILL.md`、`plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md`、`plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md`。
- 当前交付：一份包含研究证据、设计理由、职责归属、约束迁移、调用链影响和验证计划的 proposal。
- 后续实施范围：Skill 内容与直接消费合同；保持现有 Ticket state schema、typed dependency 放行语义、证据与 Gate 机制。保留版本号，通过正常宿主安装流程处理后续发布。

本文是一次变更设计，沿用仓库 `docs/skill-design/` 既有位置。实际工作方法仍以现役 Skill 为准，本文不成为第二份运行规则。

## 2. 用户诉求与设计修正

### 2.1 用户直接表达的要求

1. 主控能力持续提高，Skill 应避免用过多规则限制判断能力。
2. subagent 仍会使用能力相对较弱的模型，需要具体执行边界与上下文。
3. 编写这些 Skill 的初衷是让执行更 deterministic，降低随意发挥。
4. 大任务即使有 Topic、lane、step，仍经常被 review、fix 或等待节点串行化；明明可以先调研、并行修复或继续实施，主线却停止推进。
5. 联合考虑 Dispatcher、SDD 和实际宿主流程 dev-with-track，允许删减、合并和调整。

### 2.2 本轮讨论中修正的判断

最初方案只在两个平级 Skill 之间划分职责。重新审视后发现，二者大量规则都由同一主控执行，保留两个完整入口需要不断解释交接，收益不足。

“主控已经具备依赖分析能力”也不足以支持删除主动调度规则。能够解释并行机会，不等于执行过程中会持续发现并释放机会。用户报告的局部修复循环是需要保留明确行为约束的实际问题。

放入 dev-with-track 后又发现，上游提供的候选范围、Ticket 的正式依赖和运行时处境提示都会影响并行度。因此只压缩 Dispatcher/SDD 正文无法构成完整方案。

### 2.3 什么应该确定，什么交给判断

| 层面 | 固定内容 | 留给主控的判断 |
| --- | --- | --- |
| 业务 | 批准的合同、授权、Ticket 依赖、验收与 Gate | 识别当前交付重点和可推进路径 |
| 委派 | 本次目标、行为要求、ownership、返回边界、验证证据 | 步骤内部顺序、适当粒度、是否复用 worker |
| 并行 | 资源安全、结果可归因、审查独立性 | 当前并发组合、隔离方式、修复与主线的安排 |
| 完成 | 完整证据、真实验证、权威状态 | 根据新事实选择下一项工作 |

自然语言 Skill 能降低行为波动，不能保证每次执行轨迹完全一致。“已内化能力”的判定是模型相关假设，需要行为样例验证。是否删规则还要考虑漏做代价，不能仅依据模型自评。

## 3. 调研材料与证据等级

以下引用为仓库相对位置，历史基线由第 1 节 commit 固定。源码中段落名称与函数名用于定位；后续文件迁移后，可从该 commit 恢复原文。

| 编号 | 材料 | 主要用途 |
| --- | --- | --- |
| R1 | [Dispatcher 正文](../../skills/dispatcher/SKILL.md)、[rubric](../../skills/dispatcher/rubric.md) | Topic 门槛、主动补派、review 节拍、复用和历史偏好 |
| R2 | [SDD 正文](../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md)、[rubric](../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/rubric.md) | dependency、mode、lane、lifecycle 与结果消费 |
| R3 | [Worker Briefs](../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/worker-briefs.md)、[Resource Admission](../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/parallel-work-admission.md)、[Review Gate](../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/review-gate.md) | 委派合同、实际资源和 material review 条件 |
| R4 | [Dev With Track](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md)、[Control Flow](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/control-flow.md)、[Runtime Protocol](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md)、[rubric](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/rubric.md) | 上游选择、状态单写、findings 与恢复 |
| R5 | [Composition Contract](../../plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md)、[Current State 3.5](../../plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md)、[engine.py](../../plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py) 的 `ready_tickets` / `_ticket_released` | Ticket barrier 的文档与实现 |
| R6 | [situations.yaml](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml)、[protocols.json](../../plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/protocols.json) | 实际处境候选与注入文案 |
| R7 | [situation.py](../../plugin-marketplace/plugins/impl-package/scripts/situation.py) 的 `_when_attempt_in_flight` / `_open_dispatch` 与候选排序、[dispatch_audit.py](../../plugin-marketplace/plugins/impl-package/scripts/dispatch_audit.py) 的 `_action_ids` | 在途判断、优先层投影、派发审计 |
| R8 | [Dispatcher 合同测试](../../tests/test_dispatcher_contract.py)、[SDD 合同测试](../../tests/test_subagent_driven_development_contract.py) | 对旧结构和精确措辞的保护 |
| R9 | [Dispatcher evals](../../skills/dispatcher/evals/evals.json)、[SDD evals](../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/evals/evals.json)、[dev evals](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/evals/evals.json) | 已有场景及行为验证缺口 |
| R10 | [方法优先重设计](subagent-driven-development-method-first-redesign-260825.md)、[worker briefs 调整记录](subagent-driven-development-worker-briefs-260829.md) | 既有设计动机和需要保留的执行收益 |
| R11 | [AGENTS.md](../../AGENTS.md)、[全局 rubric](../../skills/improve-skill/global-rubric.md)、[Impl Planning](../../plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md) | 宿主约束、文档偏好、整票依赖与票内接线条件 |

本文区分三类材料：用户报告是待改善的实际现象；文件和代码是已确认的规则事实；这些规则如何影响模型选择是待行为回放验证的因果假设。本轮没有读取真实业务 package 的完整执行轨迹，因此不能把以下发现宣称为所有串行现象的唯一根因。

## 4. 研究发现及其原因

### 4.1 Dispatcher 与 SDD 面向同一个实际执行者

R1 负责候选选择、资源准入、返回消费和生命周期；R2 又有“分类 dependency”“承接当前批次”“选择 lane 与 lifecycle”“消费结果并重排”。后者的 brief、worktree 选择和结果判断大部分仍由 caller/main session 完成。

二者的责任不是两个独立 agent 之间天然存在的边界，而是同一主控连续决策的不同部分。把它们保持为平级完整流程，会产生跨文件回指和重复分类。合并可以让一次委派从选取到返回在一个入口中闭环。

### 4.2 “唯一下一动作”可能过早压缩候选

R4 要求每轮说明“唯一业务下一动作”，先选择当前业务动作再交给 Dispatcher。这与同时存在的并行规则形成张力：主控可能先过滤成一个动作，再只在该动作内部寻找并行。

这是一种可解释的诱导风险，不是代码层单线程证据。设计上保留明确交付重点和一个恢复入口，同时允许当前执行集合包含多个候选。

### 4.3 处境表包含更直接的等待与单选倾向

R6 中存在以下精确规则：

| 位置 | 已确认事实 | 潜在影响 |
| --- | --- | --- |
| `attempt.readiness.multiple-ready-tickets` | `when` 包含 `attempt.in_flight: false`，`ask` 为“本轮应选择哪一个 ready Ticket” | 有在途工作时该分支不匹配；匹配后又引导单选 |
| `attempt.readiness.worker-still-running` | 默认 action 为 `wait-for-worker-result`，effect 为“等待 worker 返回，不另起动作” | 鼓励把一个在途结果当作当前行动终点 |
| 同名 protocol | “不并发派发同一 source unit；等 worker-return 后再决策” | 第一半句保护冲突，后一半句缺少不受影响工作的处理 |
| `finding.fix.reviewer-returned` 等 protocol | finding 返回后直接导向同 Topic work lane | 缺少重新比较独立修复与主线安排的空间 |

R7 的投影在 P0 命中时选择一个严格优先事项；其余情况下，将最高命中层放入 `parallel_matches`，较低层放入 `other_matches`。因此“有 parallel_matches”不等于“当前所有独立实施机会都已呈现为首选”，也不意味着这些候选已经通过资源隔离判断。

但该引擎并非机械地禁止一切并行：派发审计 `_action_ids` 会读取 `selected`、`parallel_matches`、`other_matches`、`suppressed_matches`，另有偏离理由路径。正确结论是入口存在保守等待倾向和候选呈现限制，需联合校准，不能直接宣称必须重写调度引擎。

### 4.4 有些等待来自正式 Ticket barrier

R5 的 `ready_tickets` 要求当前 Ticket 为 `PENDING`，且 implementation 入边全部释放。`_ticket_released` 接受 `SATISFIED`，以及符合现有语义的 `RETIRED` 路径；部分 early evidence 不能释放整票依赖。

因此，即使某个局部接口已经稳定，只要批准的 implementation 边仍未释放，下游 Ticket 的实施就不能由 Dispatcher 自行放行。隔离 worktree 只能解决资源冲突，不能改变业务 readiness。

R11 已要求按整票真实阻塞选择 `implementation / acceptance / release`，票内等待写成接线条件。本轮应利用这个已有设计：发现依赖过粗时交回 impl-planning 检查受影响的合同，而非新增 claim-level readiness 或第二套运行状态。

### 4.5 修复安排被 review 来源预先固定

R4 与 R3 把轻量 delta finding 固定为随下一步一起修复、不单独派 fix；formal finding 则进入 bounded fix。原意是减少微型派发，但 finding 来源不充分决定最佳执行安排。

当下一步尚未就绪、修复能独立隔离，或该 finding 阻止关键路径时，固定捆绑会增加等待。应保留 finding 的业务裁决和闭合要求，让 Dispatcher 按影响、资源和整合成本决定何时修。

### 4.6 规则膨胀的一部分已被测试固化

R8 的测试断言具体章节、四类 dependency token、`fresh worker`、连续两次 `INCOMPLETE`、固定扫描句子，以及 `由 Astra 根据任务难度决定` 等措辞。SDD 合同测试还固定 dev 的七步名称和双入口结构。

这些静态测试能发现误删与断引用，但不能证明主控真正进行了并行派发。重写时需要有意更换保护目标：结构检查负责入口与合同完整性，行为样例负责证明调度改善，不能为了让旧字符串断言通过而把被删除的规则写回来。

### 4.7 用户缓存与仓库源存在差异

用户指定的 dev 缓存版仍包含整批收齐后的全局重扫、Ticket 首次激活 preflight 和旧 slow path 路由；仓库版已明确 Dispatcher 的 return 后补派、直接结果对账与按实际资源核验。缓存版的 Runtime Protocol 又包含逐次返回补派，存在材料内部节奏表达不一致。

SDD 缓存版也比仓库版保留更多 Topic 定义、批次形成和返回调度规则。研究和未来评测必须记录实际加载版本。直接编辑安装缓存不能替代源码修复；安装同步属于后续显式执行范围。

## 5. 设计选择与替代方案

| 方案 | 成立前提 | 本轮判断 |
| --- | --- | --- |
| 保留 Dispatcher/SDD 平级，继续去重 | 两者存在足够多的独立调用场景 | 无法充分解决同一主控重复走流程，继续维护交接成本 |
| 合并二者，dev 保留业务 owner | 通用执行方法可独立于 package 验收合同 | 推荐；减少一个方法入口，保留真正独立的职责 |
| 主控 Skill 加一个真正面向 worker 的 Skill | worker 需要统一加载较长的通用执行方法 | 目前优先使用具体 brief 和既有专业方法，避免再建立一个与 brief 重复的入口 |
| 三者全部并入 dev-with-track | 所有委派都只发生于 Impl-Package | 不满足普通调查、修复等使用场景，且扩大通用委派的上下文成本 |
| 新建自动调度器、队列或 claim-level 状态 | 已有明确 runtime 能力缺口和足够收益 | 本轮证据不足；先修现有入口与消费合同 |

推荐保留 `$dispatcher` 名称和 `skills/dispatcher/` 的单一源位置。名称能表达“安排工作”的作用；通用入口不绑定 package、provider 或某个主控模型。保留它作为 standalone Skill 的现有链接方式，避免在 plugin 内复制一份正文。

## 6. 目标职责与运行关系

### 6.1 唯一归属

| 判断或事实 | 权威 owner |
| --- | --- |
| 批准行为、语义是否唯一、finding 严重性与 disposition | dev-with-track，必要时回 req-align / Owner |
| Ticket readiness、正式依赖释放、证据采信、State、Checkpoint、Gate | dev-with-track 与既有语义 CLI |
| 当前交付重点及允许调度的业务范围 | dev-with-track |
| 从该范围发现候选、比较收益、决定派发组合及具体返回边界 | Dispatcher |
| brief、worker 复用、worktree/运行资源安排、局部自证与结果归因 | Dispatcher 的委派方法 |
| delta review 派发时机与积压处理 | Dispatcher |
| formal review requirement 与业务验收点 | dev-with-track 按 Plan/policy/material risk 判断 |
| review comparison point、topology、coverage 与 finding closure | do-review |
| provider、model、原生 agent/CLI 能力 | Owner 或宿主既有设置 |

主 session 同时应用业务方法和调度方法，不增加一个主控代理。worker 只返回事实，主 session 继续单写 package 状态。一次状态记录的串行写入不会占用整个业务执行范围的 ownership。

### 6.2 交接内容

dev-with-track 提供当前目标、相关批准合同、剩余工作入口、业务依赖与授权限制、验收要求和必要的恢复事实。Dispatcher 可以据此发现新的执行候选；遇到语义或授权疑问时将局部问题交回业务判断，其他已满足条件的工作继续安排。

候选和在途安排使用当前会话及现有派发记录表达。无需新建完整候选表、打分表、队列文件或并行预算。一个 checkpoint 可以记录最先恢复的动作，并引用已有在途记录；恢复后重新判断其他工作。

### 6.3 框架内循环

```text
dev-with-track 刷新业务事实、交付重点与限制
                    ↓
Dispatcher 发现可推进工作，选择亲自执行或委派及并行组合
                    ↓
执行、自证、结果返回；主控核实并安排对应增量审查
                    ↓
dev-with-track 按需裁决业务事实、写入证据和状态
                    ↓
Dispatcher 根据更新后的事实继续补充可推进工作
                    ↓
只有业务验收条件齐备，dev-with-track 才进入相应验收/Gate
```

受新结果影响的后续动作必须先消费相关证据与必要状态更新。无关 worker 的继续执行不需要等待这条记录链。审查结论若改变共享前提，按影响范围重新判断已经在途和待派发的工作。

## 7. 合并后 Dispatcher 的主路径

主文件以以下五项行为为骨架，最终实现应保持短小。这是执行循环，不要求输出一份逐项检查表。

1. **明确交付范围。** 使用调用方提供的目标、限制和事实；普通任务可直接使用用户授权和仓库上下文。清楚本次局部结果与整体完成的区别。
2. **主动发现可推进工作。** 启动、结果返回、出现 review/fix/等待或阻塞时，检查剩余交付路径。比较提前产出的价值、依赖、资源隔离和整合成本，推进值得开展的调查、实施、修复或验证。
3. **形成具体执行合同。** 以一个可验证结果或下一个需要主控判断的边界委派；同一结果所需的调查、实现、测试、格式化、普通重跑和机械 cleanup 一起完成。亲自执行也遵守相同 ownership、自证和审查要求。
4. **核实返回并及时审查。** 确认派发成功与结果来源，消费 diff、验证、未完成项和资源残留。新增实现代码的返回在同次消费中固定增量、安排独立 delta review。纯调查或无代码重跑按其证据检查，不机械派代码审查。
5. **限定阻塞范围并继续安排。** review、fix、在途 worker 和共享资源只影响依赖其结论或争用其资源的工作。审查跟不上时收住会继续累积未审查假设的实现链；其他独立工作继续评估。没有值得当前推进的工作时等待或返回调用方，整体 closure 归业务 owner。

### 7.1 有效并行的边界

并行候选不局限于不同 Ticket 的只读准备，也包括同 Ticket 内互不依赖的工作，以及其他已获业务放行的实施和修复。Topic 整体或未来 write-set 有交叉，不自动否定当前动作并行。

资源判断覆盖实际写入、读取和验证观察。两个只读操作可以共享稳定数据；当一方会改变另一方的读取结果或验证 oracle 时，需要隔离或排序。隔离 worktree 只分开文件；DB、端口、测试数据、输出目录和外部记录分别核验，并明确整合与 cleanup owner。

前置语义变化或真实 implementation 依赖未释放时，受影响实现等待。调查和准备也必须在调用方允许范围内，保持可回收，并且不能通过把实现改名为“准备”绕过 barrier。

### 7.2 审查与有限执行容量

有空闲 reviewer 容量时及时派审。宿主槽位已满时，先冻结增量并明确待派审工作，利用下一个合适槽位补审；明确记录派审尚未成立，不把“计划审查”当作成功 receipt。

持续积压时限制会扩大审查债务的实施，不建立固定并发数字或独立持久 review 队列。正在运行的独立工作继续按其边界执行；决定新派发时还需考虑实际可用槽位及主控消费能力。

reviewer 始终独立于其所审实现；同 scope 上下文可信时可复用，每次核对新的固定输入。formal review 的特殊 reviewer 选择遵循 do-review。

## 8. 委派方法：对低阶 worker 保留具体合同

在形成 brief 时读取 `references/delegation.md`（拟迁入），包含以下必要信息，不要求固定字段数量或序列化格式：

- 单一目标、当前已知事实、需要遵循的合同章节和关键 entry point。
- 成功行为、边界状态、不变量、具体返回条件；不能只写一句功能名。
- write ownership、禁改范围、实际工作目录、前置依赖和运行资源。
- 能证明真实路径的局部验证入口及其限制；测试结果要能对应本次改动。
- 已确认 finding 的原始意见、定位和裁决，避免让 worker 重复猜测。
- 返回实际改动/结论、验证证据、未完成项、残留和 cleanup 情况。

worker 完成同一结果所需的普通恢复。边界变化、关键前提不成立或无法完成时返回事实，不自行扩大授权。具体调查、实现和修复方法可以使用已有专业 Skill，Dispatcher 不复制其专业流程。

复用取决于相关上下文仍准确、ownership 清楚、已有错误可解释。无关或不可信上下文使用 fresh worker；Topic 名称变化本身不强制清空有效上下文。一个范围完成后释放其资源与待办责任，后续复用需要重新明确授权，不形成常驻角色的隐含职责。

删除 15/30 分钟通用观察门槛。结合工具活动、进程、输出变化、任务特定超时与可观察进展判断健康；在途时间本身不是重复派发的理由。固定错误次数改为边界可信度判断：证据已表明遗漏 caller/producer 家族或 ownership 外溢时，先重新调查受影响范围，避免继续局部补丁。

通用 brief 只要求真实结果。Impl-Package 中由主 session 适配既有 `DONE | BLOCKED | INCOMPLETE`、`EVIDENCE_SUFFICIENT | EVIDENCE_GAP`、`PENDING_REVIEW | PASSED` 等真实消费者使用的值，本轮保持这些接口兼容。

## 9. Dev With Track 的联合修订

### 9.1 从单一动作改为交付重点与候选范围

将“选择唯一业务下一动作 → 形成 Topic → 交给 Dispatcher → 再执行 SDD”压成“确定业务重点、事实与限制 → 应用 Dispatcher 执行协作 → 消费结果并记录”。

业务层无需提前穷尽所有步骤。它必须让 Dispatcher 看见相关剩余范围，而非只传一个已经筛定的动作。语义尚待 Owner 决定的工作局部挂起，其他授权明确的工作继续推进。

### 9.2 findings 按影响决定安排

dev-with-track 负责确认 finding、等级、disposition、影响范围及解决期限。已确认 finding 可立即修、随相关下一步修，或隔离并行修，由 Dispatcher 判断。延后修复不能放行依赖该缺陷的实现或对应验收，也不能把 finding 从交付范围中消失。

material risk 的七类判断启发式从 SDD `review-gate.md` 归入 dev 的既有 review 规则所在位置；正式 review 的 requirement、业务边界和触发要求保持，具体 topology/coverage/closure 继续回到 do-review。通用任务按其 owning workflow 和 policy 判断正式 review。

### 9.3 处境表与注入合同同步

以下是需要跟随正文一起完成的定点修订，不是新建调度引擎：

| 当前位置 | 拟变更 |
| --- | --- |
| `multiple-ready-tickets` | 取消“无在途才考虑其他 ready 工作”的限制；从选哪一票改为依据实际依赖与资源选择当前工作组合 |
| `worker-still-running` | 默认先检查剩余工作与资源，确无可推进工作才等待；保留同一写入责任的防重复派发 |
| finding 返回分支与 protocol | 业务确认后进入当前候选安排，允许独立 fix；去除由 review 来源决定固定捆绑的规则 |
| `situations.yaml` 中 SDD 调用 | 改指 Dispatcher；mode 可保留为与既有事实消费者兼容的工作类型 |
| P0/P1 等投影消费 | 保留 P0 的真实恢复/授权约束；其它优先层用于聚焦注意力，不把局部在途事实扩展成整个 Attempt 的互斥锁 |
| 普通偏离与表外动作 | 使用现有 credential/trail/escape 合同；把常见合法并行路径纳入正常候选，避免每次并行都需要特殊说明 |

`situation.py` 的 `selected/parallel_matches/other_matches/suppressed_matches` 和 state schema 先保持不变。修改表条件后先用 fixture 验证；只有明确证明现有选择或注入代码仍阻止既定行为时，才提出局部代码修复，并补直接回归。不得以本提案为授权重写引擎或降低 P0/正式依赖要求。

## 10. 旧规则删留与唯一落点

| 原规则族 | 处理 | 原因/落点 |
| --- | --- | --- |
| 所有委派必须先建立 Topic | 弱化为连续工作可用的组织概念 | 简单任务直接表达目标、边界和返回条件 |
| Topic closure 不得被静默缩小 | 保留实质要求 | 已授权交付范围改变需重新判断；不依赖 Topic 模板 |
| 一个 baby step 到主控 return point | 保留、改为自然语言结果边界 | 防止预授权后续决策，避免微型往返 |
| 文件数、检索范围、命令数的例外说明 | 删除冗长教学 | 用可验证结果和审查承接能力判断粒度 |
| foundation 先稳定 | 保留 | 会改变下游语义的前提必须先确认 |
| 四类 dependency 必填分类 | 降为复杂情况参考 | 主路径固定授权、业务依赖与资源检查即可 |
| 当前批次收齐再决定 | 删除批次同步含义 | 返回后及时释放有收益的独立工作 |
| 必须主动寻找并行机会 | 强化并保留 | 对应用户反复观察到的局部串行问题 |
| 按整个 Topic/Ticket write-set 判断冲突 | 保留纠正后的 step 级规则 | 以实际 effect footprint 判断 |
| 共享读/观察资源影响 | 保留并澄清 | 对稳定状态的兼容读取可并行，变化中的观察需隔离 |
| worktree 等价于完整运行隔离 | 保留纠正规则 | 实际工具链、DB、端口、数据分别确认 |
| receipt 确认与迟到/重复结果归因 | 保留 | 防止重复执行和虚假在途/完成事实 |
| 每个代码增量及时独立 delta review | 保留，明确容量不足时的真实状态 | 保持审查节奏，不虚报已经派审 |
| review 积压触发全局收敛 | 改为收住受影响实现链 | 避免审查节点拖住全部工作 |
| delta finding 一律随下一步修 | 删除绝对安排 | Dispatcher 按实际收益与依赖决定 |
| work/review/test 三条 lane 必须显式建立 | 删除强制对象 | 保留实现/审查独立和有界测试活动 |
| 新 Topic 一律 fresh、关闭后一律不能复用 | 改为相关可信上下文与明确新授权 | 释放责任与进程复用分别判断 |
| reviewer 同 scope 复用 | 保留 | 独立性与上下文连续性分别保证 |
| 固定观察 15/30 分钟 | 删除 | 使用实际活跃信号与任务特定超时 |
| 连续第二次 INCOMPLETE 必须调查 | 删除数字门槛，保留失配触发 | 一次已证实的边界失配也应调查；可解释的恢复无需等次数 |
| verify 可能写 snapshot/generated file | 保留实际副作用分类 | 工作名称不能覆盖真实资源占用和授权 |
| 固定 mode 与 outcome enum | 通用正文降为辅助；package 消费层保留兼容 | 不破坏既有 parser/trail 接口 |
| 真实路径验证、局部 self-check、cleanup | 保留 | 低阶 worker 的关键执行保障 |
| material formal review requirement | 迁入 dev 的业务 review 判断 | 从通用委派中分离 Ticket 语义 |
| State/Evidence/Gate 单写与验收证据 | 保留 | 与并行实施无冲突，提供结果确定性 |
| provider/model、task-queue、宿主原生调用教程 | 继续使用既有 owner | 不新建解析、队列或模型策略层 |

上述删留是本次提案的显式语义变化。历史 rubric 中“两个平级入口”“Topic-first 全面强制”“新 Topic fresh”等已确认原则需要在正式实施时按本轮 Owner 决定修订，避免旧 rubric 重新阻止已批准的方向。当前文档写入不自动修改 rubric，也不把新的模型推断提升为全局偏好。

## 11. 文件组织、调用方与迁移范围

### 11.1 目标组织

```text
skills/dispatcher/
  SKILL.md                         通用协作主路径
  references/delegation.md          brief、执行、自证、返回、复用
  references/resource-isolation.md  复杂资源冲突时读取
  evals/evals.json                  合并后的行为样例
  rubric.md                        当前 owner 偏好

plugin-marketplace/plugins/impl-package/skills/dev-with-track/
  SKILL.md                         业务事实、候选范围、证据与 Gate
  references/control-flow.md        修订现有运行关系
  references/runtime-protocol.md    修订既有恢复与 finding 路由
  situations.yaml                  同步候选与等待语义
  evals/evals.json                  框架内场景
  rubric.md                        修订业务/执行职责偏好
```

reference 仅在分支需要时读取；不要把两份旧正文整体搬入 reference。SDD 的专业素材按第 10 节吸收，eval 按行为迁移，历史理由保留在 Git 与本提案；所有有效消费者迁移后删除独立 SDD Skill 目录。

### 11.2 已发现的直接消费面

| 消费面 | 已确认位置 | 后续动作 |
| --- | --- | --- |
| 仓库入口 | `AGENTS.md` | 将双方法路由改为 Dispatcher；保持宿主中立 |
| suite router / planning | `impl-package/SKILL.md`、`impl-planning/SKILL.md` | 更新入口及方法 owner，保留 planning 的真实依赖语义 |
| 审查 | `do-review/SKILL.md` 及 `test_three_track_contract.py` | reviewer lifecycle 改指新委派方法；审查合同保持 |
| 授权边界 | `execution-boundaries/SKILL.md`、`references/authorization-contract.md` | 资源与委派 pointer 改指 Dispatcher |
| 运行提示 | `dev-with-track/situations.yaml`、`scripts/impl_package_runtime/protocols.json` | 完成第 9.3 节的实质修订 |
| 续接 | `skills/handoff/references/task-execution.md`、`skills/handoff-to-new-session/` | 恢复业务范围与在途事实，移除旧 SDD 指引 |
| 外层任务协调 | `skills/thread-harness/references/role-a.md`、`role-b.md`、`design-notes.md` | 调整执行方法引用；区分现役规则与历史说明 |
| 显式队列调用 | `skills/task-queue/SKILL.md` | 保持独立的显式调用入口，适配 Dispatcher 的局部结果术语 |
| DSH 命令与文档 | `plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/commands.mjs`、README、baseline、status-tick 脚本 | 分类活跃调用/纯历史文字；更新实际命令和可达路径 |
| 安装与描述测试 | `tests/test_impl_package_plugin.py`、role/handoff/thread-harness 等直接测试 | 取消 SDD 必须存在的旧期望，验证新入口可达 |

此表是已经定位的迁移入口，不是承诺修改每个命中文件。实施时对 `subagent-driven-development`、`impl-subagent-driven-development`、`SDD` 和旧资源路径再做引用闭合扫描；只改当前消费合同，历史记录保留历史事实。

### 11.3 宿主与退役策略

Dispatcher 仍由现有 standalone Skill 链接机制暴露。Impl-Package 调用它前需有可解析的已安装入口；仓库相对路径不能在安装 cache 中假定成立。沿用既有宿主 Skill 解析与单 Skill 链接，不把 Dispatcher 复制进 plugin，也不从 cache 使用多级 `..` 越界猜测仓库路径。

DSH 的旧 `impl-subagent-driven-development` command 实际拼接 plugin stage 路径；删除 SDD 后不能只把 `stage` 改成 `dispatcher`，因为 suite 内没有该目录。拟将该活跃命令改为指向 standalone Dispatcher 的显式路由，复用同文件已有 `call-codex` 的自定义 `text` 模式，并验证宿主上该入口可达。同步迁移仓库内调用后删除旧命令，不建立永久兼容 wrapper。

三个现有 host manifest 均使用 `skills: ./skills/`，没有逐项枚举 SDD；不要为了删除一个自动发现的目录做无效 manifest 修改。Skill 集合变化仍需运行相应插件清单/描述合同检查。版本保持 `0.4.2`；本 proposal 不授权改版本、重装或编辑用户级缓存。

parser 和历史轨迹需要另外保护：`situation.py::_open_dispatch` 会识别既有 dispatch 事件，也有历史 `chosen` 包含 `sdd` 的判断。保留历史读取兼容，新的派发使用明确可归因事件。对 slug/action ID 先改语义和目标，能保留稳定标识就保留；不要用全仓替换破坏事件回放。

## 12. 典型开发场景推演

### 12.1 保存功能：接口已稳定，API 与页面可以独立推进

dev-with-track 确认批准合同、Ticket 依赖和当前缺口。假设页面与 API 的实施均已被正式允许，接口语义稳定，工作资源可隔离。

Dispatcher 同时安排 API 实现与页面实现；测试数据准备若能缩短后续验证且成本合理，也可提前进行。每个 worker 在各自范围完成局部验证。API 先返回后固定其增量并派 review，页面继续执行。

review 发现一个已确认的 API 局部缺陷，dev 判断它不改变接口且不会使页面实现失效。Dispatcher 可以沿原 worker 修复，同时推进页面接线；若存在当前文件冲突，安排隔离或短时排序。最终整条保存路径的证据齐备后，dev 才接受 Ticket。

### 12.2 保存功能：共享语义未稳定

若接口尚未确定，或 finding 推翻幂等/权限/数据形状，依赖这些前提的实现等待；主控先安排决定性调查。与该结论无关且已获授权的 UI 交互研究或环境准备可以继续。

调查结果更新业务事实后，Dispatcher 重新选择受影响工作。已经失效的局部结果不能被提前接受为最终证据。

### 12.3 页面实施被整票 implementation 边挡住

即使运行资源隔离，Dispatcher 仍遵守 canonical barrier。主控检查阻塞是否真实代表整票前置；若实际只需已经稳定的合同，交 impl-planning 对受影响依赖作明确修订。修订前不能使用“准备”“同 Topic”或 early evidence 偷换放行条件。

这个场景的等待可以是正确行为。评测不能把所有等待都判为失败，也不能用 worker 数量代替交付质量。

## 13. 实施顺序与验证计划

### 13.1 建议实施顺序

| 步骤 | 交付 | 该步验证 |
| --- | --- | --- |
| A 固定比较材料 | 当前三 Skill、references、处境提示与相关 eval 的基线；旧规则到新落点映射 | 逐项覆盖第 10 节，确认已有批准方向与新增设计细节 |
| B 写合并主路径与 dev 适配 | Dispatcher 正文、两个必要 reference、dev 控制循环与 findings 分工 | 静态合同、pointer、模式/输出消费者兼容检查 |
| C 联合修订处境提示和调用方 | situations/protocols、直接入口、宿主 command 路由 | 在途＋独立 ready 的 fixture，正常派发无需绕过业务约束 |
| D 迁移测试并退役 SDD | 行为 eval 归并、旧结构断言替换、有效调用清零后删除目录 | 调用闭合、历史回放兼容、目标 host 入口可达 |
| E 行为验证并修正 | 固定输入下的调度与 worker 执行证据 | 本节场景满足；再决定源码实施是否完成 |

步骤是 proposal 的实施顺序，不新增 Task/DAG 或固定 worker 派发队列。实际可以合并不需要新决策的机械部分。

### 13.2 行为验收样例

| ID | 输入情形 | 必须观察到的行为 |
| --- | --- | --- |
| V01 | worker A 在途，B 的实施前提、授权与资源已满足 | B 在 A 返回前被实际派发或执行；不能只口头建议并行 |
| V02 | A/B 在同一 Ticket，实际当前工作互不依赖 | 允许并行，不因同 Ticket 标签串行 |
| V03 | review 在途，独立主线工作已 ready | 继续主线，并保留待审结果的真实状态 |
| V04 | delta finding 可独立隔离，下一相关实现尚未 ready | 能单独安排修复，不强制捆绑到不存在的下一步 |
| V05 | finding 推翻共享接口，另有无关调查 | 停止依赖接口的实现，同时评估无关调查 |
| V06 | 两个 worktree 共用会互相影响的 DB/端口 | 隔离或排序实际冲突步骤；其他工作不被整个阻塞 |
| V07 | 新 worktree 缺本地工具链 | 核实并恢复 carrier，不虚报验证通过，不重复完整业务调查 |
| V08 | code return 的 review 持续积压 | 固定增量并收住受影响实现链；不把所有独立工作一律暂停 |
| V09 | 全部 agent 槽位已占用 | 如实保留待派审/待派发，释放容量后及时推进，避免假 receipt |
| V10 | 明确 implementation 边未释放，但有部分早期证据 | 不越过 barrier，不提前 satisfy；可报告真实依赖建模问题 |
| V11 | 仅 acceptance 边未释放，其他实施条件已满足 | 可实施，最终验收保持未完成 |
| V12 | 主控只收到一个恢复 next，但范围内还有 ready 工作 | 从权威范围恢复候选，不把 checkpoint 当作全局串行命令 |
| V13 | worker 普通工具重跑，边界仍可信；或边界一次就明确外溢 | 前者原范围恢复；后者立即调查边界，不按固定次数决定 |
| V14 | reviewer 输入更新但 scope 连续，或 reviewer 实现过待审增量 | 前者可复用并核查新版本；后者保持独立审查 |
| V15 | 低阶 worker 收到保存功能 brief | 实际实现规定的失败状态/不变量，验证走真实路径，返回可归因证据 |
| V16 | Dispatcher idle，仍有在途工作/验收缺口 | dev 保持 package 未 closed，并准确记录下一恢复事实 |

### 13.3 验证方式与完成证据

先复用现有 eval 格式和 fixture，不新建 benchmark 平台。V01/V03/V04 采用带可控返回事件的多步任务回放：先让一项工作保持在途，再提供独立工作，观察下一次实际 dispatch。V15 用授权的目标 worker profile 在可丢弃的局部代码样例中执行，检查产物与真实验证。

只读场景回答能验证理解，不能单独证明执行习惯改变。源码基线与候选版使用相同任务输入、可用工具和 model/profile；评测输入不额外提醒“请并行”。记录使用版本、事件顺序、实际派发、资源冲突、审查输入与验证结果。证据存入已有 eval 工作目录或原生运行记录，不要求业务运行增加评分日志。

合格标准：已知有收益的独立工作能在无关等待完成前推进；真实依赖仍阻断对应实施；资源、授权、审查与验收没有回归。允许不同合法调度顺序。一次表现良好的样例不能证明普遍确定性，有波动或失败时补最小重复试验并如实报告。

L0 使用改变后的 Dispatcher/dev focused tests、eval 文件结构检查与已有 Skill validator；SDD 的有价值行为迁入 Dispatcher 后验证。L1 覆盖实际改动的直接路由、review、处境提示和调用方，优先从下列现有测试中选择相关测试项：

- `tests/test_dispatcher_contract.py`、`tests/test_subagent_driven_development_contract.py`（迁移结构期望与文件归属）。
- `tests/test_dispatch_fix_contract.py`、`tests/test_situation_render.py`、`tests/test_dispatch_audit.py`、`tests/test_dev_with_track_situations_review_vocabulary.py`。
- `tests/test_execution_boundaries_contract.py`、`tests/test_impl_package_plugin.py`、`tests/test_role_skill_contract.py`。
- `tests/test_handoff_to_new_session_contract.py`、`tests/test_thread_harness_contract.py`、`tests/test_task_queue_contract.py`。
- `plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_three_track_contract.py`。

逐项选择与改动直接相关的测试，不把此清单当作每次全跑命令。保持 state/schema 代码不变时无需扩大到整个 state engine 测试集；如 fixture 暴露实际代码缺陷，则补该缺陷的定点回归。入口集合变化检查现有各 host manifest/描述合同；只有 installer/registry/manifest 真实改变时才增加对应横向 gate。L0/L1 通过后停止无差别扩测。

## 14. 风险、取舍与实施完成条件

| 风险 | 处理 |
| --- | --- |
| 删规则后主控又回到局部串行 | 把主动候选发现与限定阻塞保留在主路径，用事件回放验证 |
| 追求并发导致 speculative implementation | 遵守业务 barrier、稳定前提、授权和可回收准备边界 |
| 合并后只是形成一份更长的正文 | 按第 10 节真正删除无收益规则，reference 按读取条件设置 |
| 低阶 worker 缺乏上下文 | brief 保留具体合同、不变量、已知结论和真实验证路径 |
| 正文改善但处境提示继续发出等待命令 | 第 9.3 节与正文同批闭合，并做带注入材料的框架内评测 |
| 清理 SDD 导致插件/宿主入口失效 | 先迁移可达调用和测试，再退役；验证 standalone 依赖 |
| 全仓重命名破坏历史 trail 与 parser | 保留历史事件读取兼容，按实际消费者定点修改 |
| 缓存与源码混用污染结论 | 记录版本，分别标识研究基线、候选源码与实际安装产物 |

后续源码实施完成需同时满足：通用执行方法只有 Dispatcher 一个权威入口；dev 保有业务事实和验收职责；当前调用链不再强制 SDD 或局部等待的全局串行；旧规则均有保留/替换/删除去向；代表行为样例与直接回归通过；版本和宿主状态变更边界清楚。源码通过、宿主可用、真实业务收益应分别汇报，不能合成一个未经证据支持的“全部完成”。

本轮不需要再决定是否允许探索合并；Owner 已明确同意方向。具体条款和新增发现保留在本 proposal 中供审阅，后续实施按实际授权启动。暂不引入新的 runtime 状态或调度器。

## 15. 调研快照与本次交付核验

用户指定的安装缓存根为 `C:/Users/Xiao/.codex/plugins/cache/agent-workbench/impl-package/0.4.2/`。以下 SHA-256 对应调研时的实际文件字节，用于区分缓存和仓库源码，不作为业务 acceptance evidence。

| 文件 | SHA-256 |
| --- | --- |
| 仓库 `skills/dispatcher/SKILL.md` | `4E67B4684C7E47A5063C3DC745B0E8077FC8B1DD3887C535A9FE72F5C27E5505` |
| 仓库 dev-with-track 正文 | `903DDD43A98A06CCDC79B3328866409DF003A6CACE0BC8399E161EF6444B6CD3` |
| 缓存 dev-with-track 正文 | `1B5205525610F35DF355F8970613B4F87B3166791882027148F5DD16702C9BB1` |
| 仓库 SDD 正文 | `33DA5EBCE531C1A99A02F361B0C58A7784E60555E60975C6BA2C0A0AF0C7AF6D` |
| 缓存 SDD 正文 | `6A1A503C3FFC8595E3A9CEDC3825F627A375BAE42D169BB2BB500CAAFE14AEA2` |

本次 proposal 的核验范围是资料出处、相对链接、必需章节、内部职责与迁移逻辑，以及写入范围。第 13 节全部属于未来实施验证计划；本次未执行模型行为评测、业务测试、Skill 改写或宿主安装。

落盘核验：28 个相对文件链接均存在；15 个章节与 16 个计划验收场景编号完整；代码围栏成对；三个目标 Skill 的 SHA-256 与调研基线一致。工作区只新增本提案文件。
