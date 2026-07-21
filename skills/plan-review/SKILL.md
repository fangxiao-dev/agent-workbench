---
name: plan-review
description: 审查 implementation plan、technical plan 或 plan package 的工程完整性、架构、代码质量、测试与性能风险，并在 owner 明确授权后安全写回。用户要求“审查计划”“工程 review”“挑战实现方案”“锁定技术计划”或对 plan 执行 apply 时使用；纯代码 diff、产品战略和视觉设计审查不要使用。
---

# Engineering Plan Review

把工程计划审查成可实施、可验证、可追责的决策集合。给 agent 足够的证据工具和判断空间，只把目标绑定、证据、owner 主权与写入安全设为硬边界。

## 核心合同

- 在 Review 阶段保持目标 plan byte-identical；不要修改 plan、spec、代码或仓库配置。
- 每轮都使用 fresh context 的 Outside Voice。先让它独立阅读目标与必要基线，不向它泄漏主审 findings。
- 根据风险决定是否启用 Section Reviewer、Answerer、Judge 或 Critic；不要为了角色齐全而创建 agent。
- 在审查开始时简短报告本轮角色、工具与测试表达形式的选择及理由；后续选择变化时只报告增量，不建立恢复协议。
- 把产品意图、外部 contract、风险偏好和不可逆选择交给 owner；不得用“recommended”代替授权。
- 只在 owner 对当前 manifest hash 明确要求 Apply 后写回；manifest、目标基线或相关证据变化时重新确认。
- 必读的 rubric、reference 或脚本缺失、路径错误或读取失败时立即返回 `BLOCKED`，报告准确路径与工具错误；禁止凭记忆替代、继续生成 findings 或执行 Apply。

## 1. 绑定目标与基线

当用户给出唯一存在的 plan 文件或 package 时直接绑定，不再提问。目标缺失、存在多个合理候选、目标不存在或请求与目标类型冲突时，只询问阻止有效审查的最小问题。

读取目标、项目指令、目标明确引用的 design/spec，以及决定当前 contract 所必需的相邻资料。不要遍历与判断无关的背景文档。

从目标仓库根目录先运行 `python <skill-dir>/scripts/review_ledger.py discover --target <path>`。没有 unfinished run 时才运行 `init`；当前会话已持有明确 ledger path 时用 `resume --ledger <ledger.json> --target <path>` 继续。发现一个或多个 unfinished run（`active` 或中断于写入的 `applying`）且当前上下文无法证明应继续哪个时，列出 run ID、状态、创建时间、baseline 是否匹配和未决集合，请 owner 明确选择 resume 或 abandon；`applying` 必须先 resume，由脚本按目标 hash 收敛为 `active`/`applied` 或要求 owner 检查。在所有同目标旧 run 被选择或审计性关闭前不要创建并行 ledger。

Owner 明确放弃旧 run 时，使用 `abandon --ledger <ledger.json> --source <abandonment.json>`；该命令只把 run 标为 abandoned、使旧授权失效并保留审计记录，不删除 temp 文件。不要恢复角色编制、问题树、消息往返或隐藏推理，只恢复 ledger 中的 baseline、formal findings、resolution、authorization 和 stale 状态。

`init` 或 `resume` 后立即向用户报告 ledger 绝对路径，而不是等到最终回复。后续 CLI 保持同一仓库工作目录，使相对 evidence paths 稳定解析；Ledger 是临时安全记录，不是项目交付物。

完成条件：目标、必要 contract baseline 和唯一 unfinished ledger 路径已经确定，所有同目标旧 run 已显式继续、完成或放弃，目标当前内容尚未变化。

## 2. 加载审查镜头、扫描材料性并报告本轮配置

先读取 [rubric.md](rubric.md) 和五个短聚焦 reference，再对 Scope、Architecture、Code Quality、Tests、Performance 做 materiality scan。每个维度最终必须记录以下一种状态：

- `reviewed`：已检查且没有 formal finding。
- `not_applicable`：不适用，并给出与本计划相关的理由。
- `finding`：存在至少一个 formal finding。

把 rubric 的横切镜头应用于每个 candidate 和 finding，而不是只做一次总评；聚焦规则只增加观察面，不替代横切规则：

- Scope 或 distribution：`references/scope-review.md`
- 架构、数据流、安全边界或 rollout：`references/architecture-review.md`
- 模块组织、错误路径或技术债：`references/code-quality-review.md`
- 行为变化、回归、failure mode 或 eval：`references/test-review.md`
- 容量、慢路径、缓存或调用放大：`references/performance-review.md`

加载全部镜头不等于机械深挖全部维度：根据实际信号决定仓库调查深度、图示、角色和输出篇幅；没有 material 风险时记录有目标依据的 `not_applicable` 或 `reviewed`。

向用户报告一行配置，例如：`本轮配置：Outside Voice=独立；Sections=主审 inline；Judge/Critic=跳过（证据无冲突且变更可逆）；Tests=coverage map。`

完成条件：五个维度都有初始材料性判断，本轮配置已对 owner 可见。

## 3. 形成候选并晋升 findings

探索时只记录 candidate 的 `claim`、初步 `evidence/reasoning` 和 `risk`。沿 `goal → contract → consumer → user/operator outcome → acceptance oracle` 检查它是否 material；不要在尚未证实时填写完整表格或制造置信度精度。

读取 `references/decision-policy.md`。只有通过 evidence gate 的 candidate 才晋升为 formal finding；正式 finding 必须包含 severity、可核验证据、具体风险、recommendation、owner gate 和同轮可比较的 confidence。Accepted finding 还必须能映射到实施动作、受影响模块、真实依赖和 verification oracle；只有真实存在依赖或 owner choice 时才添加 dependency 或 alternatives。

读取 `references/ledger-records.md`，把 formal finding、五维 materiality 状态和 Outside Voice 的 `complete/unavailable` 安全状态通过 ledger 的 `record` 命令原子写入。Candidate、角色选择、问题树、角色往返和 Critic 过程不要写成 ledger 状态机。

完成条件：每个 candidate 已被晋升、保留为观察或驳回；每个 formal finding 都通过脚本校验并绑定实际 evidence dependencies。

## 4. 获取独立视角

读取 `references/subagent-prompts.md`，始终启动 Outside Voice。第一轮只提供目标路径、审查边界和必要契约，让其独立发现遗漏、错误假设和 failure modes；完成独立输出后再与主审 findings 合并、去重或记录 tension。

在高影响自动归纳、证据冲突、不可逆性、跨边界影响或主审明显不确定时，要求 fresh reviewer 继续承担 Judge/Critic 检查。若工具允许，同一个 Outside Voice 上下文可以在独立观察完成后承担这些能力，避免额外固定编制。

若无法取得独立上下文，继续完成主审并标记 `degraded`，但禁止输出 `fully reviewed` 或 `cleared`。Owner 仍可明确授权 Apply，最终状态必须保留降级说明。

完成条件：Outside Voice 独立结果已经合并，或 `unavailable` 原因及 degraded 状态已经记录；不存在伪造的独立复核声明。

## 5. 批量收敛 owner 决策

先继续所有不依赖 owner 决定的分支。按依赖关系把剩余决定组织成少量 waves；同一 wave 只放彼此独立的选择，并允许 owner 用 `1A 2B 3A` 批量回答。

只有一个决定冻结多个 material branches、会使大量后续结论失效或涉及不可逆 contract 时才 early flush。校验漏答、冲突和因上游选择而失效的下游回答，只重问受影响项。

生成 canonical manifest，包含 run ID、基线、formal findings 的 revision/resolution、未决集合和 degraded 状态。展示简短摘要和 manifest hash；此时尚不写目标 plan。

完成条件：所有独立分支已检查；owner-required 决定已经回答或明确保持未决；展示内容与当前 manifest hash 一致。

## 6. Apply

只有用户对展示过的 manifest hash 明确要求 Apply 时，才运行 `authorize` 记录授权。该一次授权同时完成 ratification 与写入许可，不再要求重复确认。

运行 `verify`：

- 目标 baseline 变化时停止整个 Apply，重审受影响计划。
- Evidence dependency 变化时只把引用它的 findings 标为 stale，局部复核后生成新 manifest。
- 授权缺失、hash 不匹配、存在未接受的 P0、owner-required finding 未裁决或存在 stale 时停止写入。

先在 OS temp 生成完整 proposed plan，不修改目标；然后运行 `verify --apply-output <proposed-plan>`。该 guarded Apply 在 ledger 与目标锁内重新核验完整 baseline hash、当前 authorization 和 evidence freshness，先持久化可恢复的 `applying` receipt，再把原目标 inode 保留为同目录、run-bound 的 preimage backup，并以 create-if-absent 安装 proposal；因此已打开旧句柄的迟到写入仍留在报告的 backup 中，不会被静默删除。baseline 不匹配时目标零写入停止。若进程在目标写入与最终 ledger 落盘之间中断，下一次 `resume` 只按 target/backup 的 preimage/output hash 收敛状态，不猜测意图；可恢复的 preimage 会恢复为 `active`，已有 backup 不会被覆盖，重试使用新的 run-bound 后缀。写入后逐 hunk 对照授权 manifest，发现语义超出授权时不得宣称 Apply 成功，并报告 backup 供人工恢复。Backup 是持久恢复物，只有 owner 确认目标内容且无需恢复迟到写入后才清理，skill 不自动删除。多目标 package 首版不使用 guarded Apply，保持未写入并请求 owner 拆分或选择明确目标。默认不要向目标 plan 追加 ledger 路径或 review report；仅当项目模板要求、ledger 已导出到稳定位置或 owner 明确要求时写摘要。

完成条件：`verify` 通过，目标 diff 只包含当前授权 manifest 的决定，未决、stale 和 degraded 状态没有被隐藏。

## 7. 输出

读取 `references/final-report.md`。按 owner 可快速判断的顺序输出：整体 verdict、角色/工具配置、五维材料性、What already exists、NOT in scope、formal findings、测试与 failure modes、待 owner 决策、stale/degraded 状态和 Apply 授权状态。

Review 结束时给出 ledger 的绝对路径供当前用户审计，但不要把 OS-temp 路径写入持久 plan。若仍有未决、stale 或 degraded 状态，明确说明不能称为 cleared。

完成条件：只读最终回复即可判断审查是否 cleared、还缺什么、是否已授权 Apply，以及 owner 下一步需要决定什么。

## CLI 快速参考

```text
python <skill-dir>/scripts/review_ledger.py discover --target <path> [--include-closed]
python <skill-dir>/scripts/review_ledger.py init --target <path> --skill-version <version>
python <skill-dir>/scripts/review_ledger.py resume --ledger <ledger.json> --target <path>
python <skill-dir>/scripts/review_ledger.py abandon --ledger <ledger.json> --source <abandonment.json>
python <skill-dir>/scripts/review_ledger.py record --ledger <ledger.json> --input <record.json>
python <skill-dir>/scripts/review_ledger.py status --ledger <ledger.json>
python <skill-dir>/scripts/review_ledger.py authorize --ledger <ledger.json> --manifest-hash <hash> --source <authorization.json>
python <skill-dir>/scripts/review_ledger.py verify --ledger <ledger.json> [--manifest-hash <hash>] [--apply-output <proposed-plan>]
```

不要把 CLI 扩展为角色编排器。它只保护 baseline、formal finding、resolution、owner authorization、未决集合、原子写入和 stale 检测。
