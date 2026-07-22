---
name: receiving-code-review
description: Deprecated compatibility archive. Do not invoke for new reviews; use `do-review`, whose parent verification and classification already cover review-feedback validation.
deprecated: true
disable-model-invocation: true
---

# Receiving Code Review (Deprecated)

This skill was retired because its useful behavior is already owned by the canonical `do-review` convergence layer. It is retained only as a historical compatibility record and must not be exposed through the active skill catalog.

退役前的核心行为是把 reviewer 输出视为待核查输入，而不是权威结论：

1. 完整阅读反馈并识别条目依赖。
2. 用当前需求、代码、测试和仓库约束核查每一项。
3. 区分真实缺陷、证据缺口、可选改进和不适用意见。
4. 对正确意见给出动作，对不正确或证据不足的意见保留明确 disposition。

这些职责现在由 `do-review` Step 4 统一承担：leaf result 只是 candidate；主 session 负责证据核验、去重，并分类为 accepted、disputed、downgraded、out of scope，以及 blocker、follow-up、backlog 或 no issue。

退役 skill 不再提供活动 workflow，也不把“用户只要求评估时不能实施”迁移为 `do-review` 的新约束。
