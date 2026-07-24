---
name: plan-review
description: Explicitly invoked engineering plan review. 仅当用户明确点名 `$plan-review` / `plan-review`，或上游编排合同按确切名称或路径显式选择本 skill 时使用；不得因为请求包含“审查计划”“implementation-ready”、复杂工程风险或类似语义而由模型主动推断调用。负责审查 implementation plan、technical plan 或 plan package，并在 owner 明确授权后安全写回。
user-invocable: true
---

# Engineering Plan Review

> **Invocation gate：**本 skill 是 opt-in 能力。只有用户明确调用 `$plan-review` / `plan-review`，或已激活的上游编排 workflow 以确切 skill 名称或路径选择它时才继续读取 references、创建/恢复 ledger 或开展审查。仅仅因为任务看起来需要工程计划审查、计划复杂、存在风险或使用了“review/implementation-ready”等词，不构成调用授权；此时停止使用本 skill，并把控制权交还调用方。

把工程计划审查成可实施、可验证、可追责的决策集合。给 agent 足够的证据工具和判断空间，只把目标绑定、证据、owner 主权与写入安全设为硬边界。

## 核心合同

- 在 Review 阶段保持目标 plan byte-identical；不要修改 plan、spec、代码或仓库配置。
- **审查对象是同一 revision 的 candidate bundle。**它由 candidate plan、该 candidate 已 earned 的 Ticket/DAG、candidate projection、必要的 D/S contract 与联合校验证据组成。registry 的 current projection 只说明已登记历史；不得用它判定未登记 candidate 的 drift、设计缺陷或风险。candidate projection 缺失时只报告 `review input incomplete`，先补齐输入，不晋升为产品、架构或 P0/P1 finding。
- 每轮都使用 fresh context 的 Outside Voice。正常 full review 让它独立发现遗漏；`focused-closure-verification` 则给它规范化 closure brief，只独立验证已冻结的收口项，不把 fresh context 误用为重新开放的问题搜索。
- Outside Voice 默认采用 5 分钟的等待。不要因第一个短轮询超时就将其标为 unavailable；在此窗口内保持目标只读。窗口届满仍无结果则主动 message 要求先返回已有的结论，确认仍在工作就继续等待直到完成。
- 正常 full review 固定启用本 skill 定义的 B/C 维度 reviewer；根据风险决定是否额外启用 Answerer、Judge 或 Critic，避免无理由扩编。
- 在审查开始时简短报告本轮角色、工具与测试表达形式的选择及理由；后续选择变化时只报告增量，不建立恢复协议。
- 把产品意图、外部 contract、风险偏好和不可逆选择交给 owner；不得用“recommended”代替授权。
- owner 对已展示且唯一的候选回复 `apply` 即构成语义授权；脚本在锁内把该消息引用绑定到当前 manifest hash。hash 只作机器审计，候选、目标基线或相关证据变化时旧授权失效。
- `cleared` 只可由 `finalize-clearance` 写入临时 ledger；调用方在 owner approval、publish 或 plan registration 前必须用同一绝对路径运行 `verify-clearance`，裸文本 verdict 无效。
- 调用上下文决定停点：`impl-planning` 只在 review 收敛后交回一次完整 bundle approval；已 GO 的 `dev-with-track` 通过 `do-review` 自动闭环 findings、验证与 gate；用户直接调用 `$do-review` 时只得到 review checkpoint，由用户或上层决定是否修订/继续。ledger 不改变这些 owner-facing 语义。
- 必读的 reference 或脚本缺失、路径错误或读取失败时立即返回 `BLOCKED`，报告准确路径与工具错误；禁止凭记忆替代、继续生成 findings 或执行 Apply。

## Bundle-admission mode（仅由明确编排选择）

当活跃的 `impl-planning` 编排以确切 skill 名称选择 `plan-review`，并明确标注 `mode=bundle-admission` 时，本 skill 执行一次轻量、只读的 admission review。调用方先扫描下方 escalation signals；命中任一项时直接启动完整 workflow，不先运行 admission。该调用必须运行在相对产出 bundle 的主 session 而言 fresh 的 subagent context；这个 admission reviewer 本身就是独立视角，不再为轻量路径额外启动 Outside Voice 或创建 ledger。用户直接调用 `$plan-review` 时一律走下方既有完整 workflow，不能因为计划看起来简单而自行选择 admission mode。

admission 输入只包含同一 candidate bundle 的 plan、Composition earned 的 Ticket/DAG（若存在）、candidate projection、必要的 Decision/Spec contract、联合校验结论和审查目标；不得附带 registry current projection、主 session findings、materiality 结论或期望 verdict。沿本 skill 的工程判断基线快速检查 Scope、Architecture、Code Quality、Tests、Performance 中实际相关的维度。

每次 admission 在开始和返回 verdict 时都用一行向 owner 报告本轮配置：`Mode=bundle-admission`、独立 reviewer 是否 fresh、额外 Outside Voice/ledger 明确不启用、发现的 full-review escalation signals 及路由结果。该报告是非阻塞的人类可读说明，不创建新 artifact、receipt 或 schema；即使没有 signal 也要明确写 `none`，不能让 owner 从“独立审查”反推实际配置。

以下是 full-review escalation signals。它们描述计划所处理问题的固有风险性质，不是“当前文本仍有缺口”的同义词；即使 plan 已写出 recovery、测试和 acceptance oracle，只要命中任一项仍进入完整 review：

- 跨模块、跨服务、跨系统或外部 contract 变化。
- 权限、身份、租户/数据范围、资金或会计正确性、外部或持久化 mutation、通知、不可逆或 single-use 动作。
- 并发、锁、CAS/claim、重复执行、replay、partial success、unknown outcome、crash recovery、迁移或 rollback。
- 错误路径、operator signal、mutation authority、恢复责任或 acceptance oracle 存在多个合理解释。
- mock、stub 或静态 fixture 可能遮蔽真实协议、provider、序列化、权限、事务或版本边界。

按以下优先级返回唯一 verdict 及简短、可核验证据：

- `unavailable`：没有 fresh context、输入不可读取或无法形成独立判断；给出具体原因。调用方只能重试、暂停或取消 approval，不能把它改写成 `ready`。
- `revise`：计划、contract、acceptance oracle、联合校验或 owner decision 不足，导致当前无法有效进入完整审查；指出 owning skill 和最小修订动作。修订后必须重新扫描固有 escalation signals，不能因缺口已修复而默认转成 `ready`。
- `full review`：存在任一 escalation signal；指出触发信号，停止 admission，由调用方按确切 `plan-review` skill 路径启动正常 workflow，取得已 `verify-clearance` 的 ledger 绝对路径后再判断 owner approval。
- `ready`：材料足以判断、没有待修订缺口且 escalation signal 为 `none`；说明已检查的风险、为何其余维度不适用，以及计划可以进入 owner approval。

admission mode 不创建 ledger、manifest、receipt 或跨 session state，也不执行 Apply。admission reviewer 如发现调用方遗漏的 signal，主 session 必须把 `ready` 升级为 `full review`，不得降级该结果。主 session 不能把 `full review`、`revise` 或 `unavailable` 降级为 `ready`；owner 也不能以 waiver 伪造独立通过。

## Focused-closure-verification mode（仅由明确编排选择）

当一个正常 full review 已完成材料性 discovery、owner decision wave 与完整 impact sweep，`impl-planning` 可以为其后只实现该批已知决议的同一 candidate bundle 明确选择 `mode=focused-closure-verification`。它不是低风险 admission，也不是重新做一轮开放式审查：调用方必须提供一个有限的 closure brief，逐项列出原 formal finding、已接受的 resolution/owner decision、需要重验的 `input → state/storage → consumer → audit/privacy → failure recovery → verification evidence` 链路，以及候选未扩大 D/S/P、authority 或 public contract 边界的声明。缺少任一项即返回 `blocked`，不得猜测或把它补成 closure。

该模式仍以 fresh Outside Voice 保持独立性，并照常绑定同一 candidate bundle、建立当前 ledger、检查 bundle snapshot 和运行 `verify-clearance`；不同之处只是审查范围。主审和 Outside Voice 仅验证 closure brief 所列项是否在完整链路上自洽、证据是否支持、以及候选是否确实没有越出声明的边界。不要追加“顺手发现”的 formal finding、建议或 D/S/P 修订；fresh 指独立的验证者，而非无限扩张的审查范围。

按以下优先级返回唯一 mode verdict，并附逐项证据与下一动作：

- `blocked`：closure brief、candidate bundle、所需基线或独立上下文不完整；修复输入后重验，不能 clearance。
- `reopen-full-review`：发现已知收口项的直接矛盾、声明链路中的材料性遗漏，或新证据证明目标、D/S/P、authority/public contract 边界已经改变。只报告这一升级理由；不要在聚焦模式中继续拆分连续补丁。调用方必须将该理由连同现有收口项合成新的 closure batch，再走正常 full review。
- `closure-verified`：每项均已验证，未出现上述升级信号，且当前 ledger 也满足 `finalize-clearance` 与 `verify-clearance`。此时对调用方的可用凭据仍是 verified ledger 的 `cleared`，不是聊天中的 mode verdict。

用户直接调用 `$plan-review` 默认走正常 full review；不能因为存在旧 findings 自行选择本模式。`impl-planning` 也只能在明确的 closure brief 和上述前提成立时选择它。该模式不新增公共 schema、长期 registry 或额外 owner approval；它复用正常 full review 的 ledger 安全边界。

## 工程判断基线

Material 指会影响行为、contract、数据、安全、运营、发布或显著工程成本的事项；不得用文件数、类数量、角色数量、阶段数量或 completeness score 代替材料性判断。每个 candidate 和 finding 都沿 `goal → contract → consumer → user/operator outcome → acceptance oracle` 追踪；最小完整变更按实际风险覆盖 success、error、recovery、migration、distribution 和 verification，不适用路径可以说明理由后跳过。

流程顺序是推荐路径，不是额外权限门。纯格式、ID 重命名、machine-owned projection、状态 seed 或经同一候选校验器证明的 mechanical binding 修正不自动触发 full review。AGENT 在拥有等价或更强证据时可以跳过重复 admission/review，并在 handoff 或 Execution Record 说明：跳过了什么、为什么仍安全、使用的证据、残余风险。这个 judgment escape hatch 不能跳过明确 owner 授权、候选/输出漂移检查、完整 baseline/manifest/receipt 证据、未决或 stale/degraded 暴露，也不能把 semantic 或安全边界变化降级为 mechanical change。

以下原则横切 Scope、Architecture、Code Quality、Tests 和 Performance：

- 优先局部、边界清楚、可回退的改动；扩大 blast radius 必须有真实需求依据。
- 优先复用成熟、简单、仓库已有的方案；不得以“简单”为由遗漏完整 contract、失败处理或分发链路。
- 让验证、ownership 和故障恢复依赖可重复机制与证据，不依赖个人记忆、隐式调用顺序或手工救火。
- 把构建、测试、调试、发布和长期维护成本纳入材料性判断。

五个专项 reference 只扩展观察面，不替代这些横切原则。它们是帮助 agent 形成判断的启发式工具，不是逐项评分表；根据实际信号选择能改变 scope、architecture、test、rollout、finding 或 owner decision 的镜头，不在结论中机械复述原则名。

## Full-review subagent 分工与收发协议

正常 full review 固定采用三路 fresh subagent，以减少主 session 对五个维度的重复深读；若编排器可选择模型，三路均使用 `gpt-5.6-sol`、`reasoning_effort=medium`。A 是 mandatory fresh Outside Voice，保持完整、独立的开放式审查；B 只审 Scope + Architecture，重点检查 authority、tenant、transaction、lineage、custody；C 只审 Code Quality + Tests + Performance，重点检查实现边界、failure/recovery、验证充分性与调用放大。`bundle-admission` 与 `focused-closure-verification` 保持各自已定义的角色约束，不适用本固定分工。

主 session 在派发前建立一次精简、同 revision 的 candidate bundle：candidate plan、earned Ticket/DAG、candidate projection、必要 D/S contract、联合校验证据、审查边界与只读约束。三路获得同一 bundle，且不接收主审 findings、预期 verdict、materiality 结论或 owner 偏好；A 仍按 Outside Voice prompt 保持独立发现。不要为每个维度重新拼装或扩展上下文。

每路返回统一的结构化结论：`assigned_dimensions`、每个维度的 `reviewed/not_applicable/finding` 状态及理由、candidates（claim、evidence pointer、reasoning、risk）、检查过但未成 finding 的关键边界、tensions/未知项，以及最值得挑战的一个假设。evidence pointer 必须能由主 session 在同一 bundle 或仓库中复核；subagent 不写 ledger、不晋升 formal finding、不向 owner 提问或修改文件。

主 session 不重复深读各维度；它只复核被引用的证据和冲突点，去重合并 candidates，按 evidence gate 晋升 formal findings，处理 tension，并组织真正需要 owner 决定的 decision waves。主 session 仍负责 ledger 原子写入、manifest、clearance 与最终报告。subagent 无结果或 evidence 无法复核时，不得把对应维度记为 `reviewed` 或 `not_applicable`；先标记 `review input incomplete` 并重试或补齐输入，不能 clearance。只有 A（Outside Voice）不可用会触发既有 degraded 限制，B/C 的不足同样不得伪装成主审已完成审查。

## 1. 绑定目标与基线

当用户给出唯一存在的 plan 文件或 package 时直接绑定，不再提问。目标缺失、存在多个合理候选、目标不存在或请求与目标类型冲突时，只询问阻止有效审查的最小问题。

读取目标、项目指令、目标明确引用的 design/spec，以及决定当前 contract 所必需的相邻资料。不要遍历与判断无关的背景文档。

从目标仓库根目录绑定 candidate plan；完整 package review 把同一 candidate 的全部 earned Ticket 路径（集合可传目录）、DAG、candidate projection、联合校验证据和必要 Decision/Spec contract 作为重复 `--baseline` 传入，使它们可被 review 与 applied-evidence 复验、却不成为 Apply 写入对象。按 [`references/ledger-cli.md`](references/ledger-cli.md) 建立或恢复内部 ledger：`init` 自动 supersede 候选/基线已变化的旧 run，`resume` 遇到漂移也自动终结为 `superseded`。不向 owner 询问路径、恢复、归档、清理或旧 run 的选择；`abandon` 只用于 owner 明确取消整个 stage。

后续 CLI 保持同一仓库工作目录，使相对 evidence paths 稳定解析；ledger 绝对路径只进入内部 runtime handoff 或审计记录，不是默认 owner-facing deliverable。

完成条件：目标、必要 contract baseline 和唯一可恢复 ledger 已由 CLI 自动确定；同目标旧 run 已自动复用、supersede 或保留为关闭审计历史，目标当前内容尚未变化。

## 2. 应用工程判断基线、加载审查镜头并报告本轮配置

使用本文件的工程判断基线并读取五个短聚焦 reference，再按“Full-review subagent 分工与收发协议”并行派发 Scope、Architecture、Code Quality、Tests、Performance 的 materiality scan。每个维度最终必须记录以下一种状态：

- `reviewed`：已检查且没有 formal finding。
- `not_applicable`：不适用，并给出与本计划相关的理由。
- `finding`：存在至少一个 formal finding。

把上述横切原则应用于每个 candidate 和 finding，而不是只做一次总评；聚焦规则只增加观察面，不替代横切规则：

- Scope 或 distribution：`references/scope-review.md`
- 架构、数据流、安全边界或 rollout：`references/architecture-review.md`
- 模块组织、错误路径或技术债：`references/code-quality-review.md`
- 行为变化、回归、failure mode 或 eval：`references/test-review.md`
- 容量、慢路径、缓存或调用放大：`references/performance-review.md`

加载全部镜头不等于机械深挖全部维度：根据实际信号决定仓库调查深度、图示、角色和输出篇幅；没有 material 风险时记录有目标依据的 `not_applicable` 或 `reviewed`。

向用户报告一行配置，例如：`本轮配置：Outside Voice=A 独立；Scope+Architecture=B；Code Quality+Tests+Performance=C；Judge/Critic=跳过（证据无冲突且变更可逆）；Tests=coverage map。`

完成条件：五个维度都有初始材料性判断，本轮配置已对 owner 可见。

## 3. 形成候选并晋升 findings

正常 full review 探索时只记录 candidate 的 `claim`、初步 `evidence/reasoning` 和 `risk`。沿 `goal → contract → consumer → user/operator outcome → acceptance oracle` 检查它是否 material；不要在尚未证实时填写完整表格或制造置信度精度。对已证实的 material candidate，在展示候选前做与风险相称的有界 closure sweep：检查可能受影响的相邻合同、实施边界和验证证据，并把同一闭环的 findings 合并；这不是新阶段或新产物，只避免把一个问题拆成连续补丁。`focused-closure-verification` 跳过此开放式探索，只验证其 closure brief；发现直接矛盾或材料性边界漂移时返回 `reopen-full-review`，不在该模式继续产生新 finding。

读取 `references/decision-policy.md`。只有通过 evidence gate 的 candidate 才晋升为 formal finding；正式 finding 必须包含 severity、可核验证据、具体风险、recommendation、owner gate 和同轮可比较的 confidence。Accepted finding 还必须能映射到实施动作、受影响模块、真实依赖和 verification oracle；只有真实存在依赖或 owner choice 时才添加 dependency 或 alternatives。

读取 `references/ledger-records.md`，把 formal finding、五维 materiality 状态和 Outside Voice 的 `complete/unavailable` 安全状态通过 ledger 的 `record` 命令原子写入。Candidate、角色选择、问题树、角色往返和 Critic 过程不要写成 ledger 状态机。

完成条件：每个 candidate 已被晋升、保留为观察或驳回；每个 formal finding 都通过脚本校验并绑定实际 evidence dependencies。

## 4. 获取独立视角

读取 `references/subagent-prompts.md`，始终启动 Outside Voice。正常 full review 按“Full-review subagent 分工与收发协议”同时启动 A、B、C；A 的第一轮只基于同一精简 candidate bundle 独立发现遗漏、错误假设和 failure modes，完成后主 session 才合并三路结果、去重或记录 tension。`focused-closure-verification` 使用其中的 bounded closure prompt：提供 closure brief 与必要基线，要求逐项独立证伪或确认，不要求也不允许开放式找新问题。

在高影响自动归纳、证据冲突、不可逆性、跨边界影响或主审明显不确定时，要求 fresh reviewer 继续承担 Judge/Critic 检查。若工具允许，同一个 Outside Voice 上下文可以在独立观察完成后承担这些能力，避免额外固定编制。

若无法取得独立上下文，继续完成主审并标记 `degraded`，但禁止输出 `fully reviewed` 或 `cleared`。Owner 仍可明确授权 Apply，最终状态必须保留降级说明。

完成条件：Outside Voice 独立结果已经合并，或 `unavailable` 原因及 degraded 状态已经记录；不存在伪造的独立复核声明。

## 5. 批量收敛 owner 决策

先完成上一节的 closure sweep，并继续所有不依赖 owner 决定的分支。按依赖关系把剩余决定组织成少量 waves；同一 wave 只放彼此独立的真实产品意图、外部合同、风险偏好或不可逆选择，并允许 owner 用 `1A 2B 3A` 批量回答。ledger、manifest、reviewer 调度、旧 run、机械 projection 与验证命令不得进入 wave。

只有一个决定冻结多个 material branches、会使大量后续结论失效或涉及不可逆 contract 时才 early flush。校验漏答、冲突和因上游选择而失效的下游回答，只重问受影响项。

生成 canonical manifest，包含 run ID、基线、formal findings 的 revision/resolution、未决集合和 degraded 状态。展示简短语义摘要；脚本可同时运行 `present-candidate --ledger <ledger.json>`，内部记录展示时的 manifest hash，但不要要求 owner 阅读、复制或确认该 hash。若本轮需要向 `impl-planning` 交接通过结果，运行 `finalize-clearance --ledger <ledger.json>`；它只在五维完整、Outside Voice=complete、非 degraded、无 pending/deferred/stale finding 且所有 bundle snapshot 未变化时写入 clearance。随后运行 `verify-clearance --ledger <ledger.json>`，把成功的 ledger 绝对路径作为 runtime handoff；任何失败都只能报告 `not cleared`，不能用聊天文本替代。

完成条件：所有独立分支已检查；owner-required 决定已经回答或明确保持未决；展示内容与当前 manifest hash 一致。

## 6. Apply

展示唯一候选后，owner 回复 `apply` 即表示授权；宿主把这条已解析为 `action=apply` 的消息交给 `authorize-contextual`，脚本在锁内绑定其引用与当前 manifest hash。该一次授权同时完成 ratification 与写入许可，不再要求 owner 复制或确认 hash。`authorize --manifest-hash` 仅保留给旧自动化兼容调用。

运行 `verify`：

- 目标 baseline 变化时停止整个 Apply，重审受影响计划。
- Evidence dependency 变化时只把引用它的 findings 标为 stale，局部复核后生成新 manifest。
- 授权缺失、hash 不匹配、存在未接受的 P0、owner-required finding 未裁决或存在 stale 时停止写入。

先在 OS temp 生成完整 proposed plan，不修改目标；然后运行 `verify --apply-output <proposed-plan>`。guarded Apply 必须在 baseline、授权或证据漂移时零写入停止，并保留可恢复 preimage。按 [`references/guarded-apply.md`](references/guarded-apply.md) 执行恢复、backup 与多目标限制；不要把临时 ledger 路径写入持久 plan。

完成条件：`verify` 通过，目标 diff 只包含当前授权 manifest 的决定，未决、stale 和 degraded 状态没有被隐藏。

## 7. 输出

读取 `references/final-report.md`，按其中结构输出 owner 可快速判断的结论。

由 `impl-planning` 调用时，正常 full review 只交回经 `verify-clearance` 验证的内部 runtime handoff；随后由 `impl-planning` 展示同一完整 bundle 并请求唯一 approval。plan-review 不单独制造第二次 owner approval。直接 `$plan-review` 则停在 review checkpoint，只有用户随后明确要求 Apply 才执行 `present-candidate`、`authorize-contextual` 和 guarded Apply；带 hash 的 `authorize` 仅为旧自动化兼容。若仍有未决、stale 或 degraded 状态，明确说明 `not cleared`。

完成条件：只读最终回复即可判断审查是否 cleared、还缺什么、是否已授权 Apply，以及 owner 下一步需要决定什么。

需要执行 CLI 时读取 [`references/ledger-cli.md`](references/ledger-cli.md)。不要把 CLI 扩展为角色编排器；它只保护 baseline、formal finding、resolution、owner authorization、未决集合、原子写入和 stale 检测。
