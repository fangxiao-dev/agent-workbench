# 2026-07-20 Prototype Blind Comparison

## 范围

对 `docs/plans/2026-03-16-task-id-workplan-layout.md` 分别运行现有 gstack `plan-eng-review` 和新的 `eng-plan-review`。两个 reviewer 使用 fresh context，互不读取对方输出；新 skill 另启 mandatory Outside Voice。目标文件全程保持只读。

## 首轮结果

旧版报告 3 个 P1、3 个 P2，覆盖计划 freshness、task ID 路径安全、遗漏 completion hooks、CLI contract、legacy migration、重复执行与状态生命周期。新版首轮报告 3 个 P1、1 个 P2，覆盖 freshness、路径安全、completion hooks 和多 active task 歧义，但漏掉 CLI contract、migration 和生命周期/覆盖语义。

这说明“新版 prompt 更短”不足以构成质量证据，首轮 candidate gate 未通过。缺口不是样本专属细节，而是适用于 CLI、schema、持久化布局和状态型计划的通用审查维度。

## 优化与重跑

使用 `write-skill-smartly` 的单一事实源和 progressive disclosure 原则，只补强四个既有 reference，不增加新角色或流程步骤：Scope 增加消费者、兼容/迁移和 freshness gate；Architecture 增加状态生命周期、重复执行和 overwrite 语义；Code Quality 增加跨计划/实现/测试的 CLI/schema contract 一致性；Tests 增加非法转换、部分写入、幂等与 legacy/canonical round-trip。

Fresh 重跑报告 3 个 P1、3 个 P2，覆盖路径安全、终态 guard、legacy migration、completion hooks、active task 解析、CLI contract，并在 test gaps 中覆盖部分写入、已有目录覆盖、幂等性和兼容迁移。相对于旧版 union，它保留全部高风险行为类别，并额外细化 active/resume 歧义与 Windows filesystem key 场景。重跑对历史计划 freshness 的显式结论不稳定，因此又把 freshness gate 固化进 Scope reference，避免依赖 reviewer 临场联想。

## Gate 判断

- Prototype safety gate：通过。Ledger 单元测试、结构验证和 Review 只读 forward-test 均通过。
- Evaluable candidate 小规模 blind comparison：通过并记录一次由失败到修订的闭环；该判断仅覆盖代表性 P1/P2 与 test-gap 样本，不等同于 default rollout。
- Default rollout：未执行完整预声明样本、容差和成本评估，因此旧 skill 尚不 deprecated，其他 gstack skills 的 release workstream 也不在本轮执行。

## 横切与聚焦能力补全后的 fresh forward test

在 parity 审查指出原 skill 的工程判断同时来自主文档横切规则和 section 聚焦规则后，补充 `rubric.md`、五个 focused references、evidence/severity 语义与 actionable finding 输出，并让一个不继承本轮讨论上下文的 agent 直接使用新 skill 重审同一计划。该 agent 自行启动 fresh Outside Voice；主审没有收到预期 finding 列表或修订目的。

Fresh run 报告 7 个 formal findings，覆盖已实施后归档的 freshness、两个遗漏 completion-hook consumers、task ID 路径 containment、既有目录/部分失败与重试语义、legacy artifact migration、CLI canonical/alias contract，以及不可执行或失焦的验收命令。相对于旧版与前次新版结果的 union，高风险类别全部召回，并把 `goal → contract → consumers → user/operator outcome → oracle`、repository fit、source of truth、error/lifecycle、test level 与 mock boundary 转化为实际证据，而不是只复述 rubric 名称。

本次 Review 前后目标 SHA-256 均为 `E382A9551A857D2491EFF6B3C872ED19A181143CA4F85922F3AB4D21FD3AD426`。Outside Voice 独立结果完成并合并；后续 Judge/Critic 因收口时限中断，但不是 mandatory Outside Voice 的替代或伪造。该 run 支持横切+聚焦能力 parity 的 candidate 判断，仍不替代 default rollout 的完整质量、成本和时延评估。
