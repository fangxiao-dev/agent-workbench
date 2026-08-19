---
name: review-code
description: 当需要审查 pull request、固定 comparison point 的代码 diff 或相关实现变更时使用；重点检查运行行为、错误处理、安全、性能、资源、并发/原子性、测试风险与一般代码质量。
allowed-tools: Read Grep Glob
metadata:
  tags: review-code, code-review, code-quality, security, best-practices, PR-review
  platforms: Codex, Claude, ChatGPT, Gemini
---

# Review Code

## 审查意图
优先关注变更后的行为、错误处理、安全、性能、资源、并发/原子性和测试风险；结构、模块归属、抽象与一般 code-quality 仍可报告——偏重是注意力启发式，不是能力禁令。证据不足时明确范围，不猜测未提供的事实。

## Profile（判断）
选择能忠实覆盖 diff 的最小 profile：**Full behavior review**（代码或运行行为变化；除本文件外读 [Full Review Checklist](references/review-checklist.md)）；**Focused review**（仅 docs/evidence/config metadata——核对 canonical source、事实一致性、链接/路径、ownership/authorization claim、generated/source 边界与是否意外改变 executable behavior，不加载不适用的 checklist）。删除/方向纠正按剩余 authority 审查，除非可观察合同改变，不要求替代内容或扩大测试。**升级规则**：focused diff 实际改变 runtime behavior，或隐藏未解决的 contract/safety 变化 → 升级为 full。

## Review
从完整 diff 追踪运行入口、数据流、错误路径、资源生命周期与可观察结果；检查行为正确性、边界条件、失败模式、兼容性、输入/权限边界、敏感数据、依赖、并发/原子性、外部副作用、查询/缓存、cleanup、性能退化；检查测试覆盖新行为/错误/边界、可读、确定且 setup/teardown 正确，实现符合仓库惯例且无多余复杂度。每项 finding 只陈述可定位证据、影响与建议，按 Critical/Important/Nice-to-have 排序，不把偏好写成缺陷。

## 输出合同（leaf 结构化输出）
Findings 优先，给文件与紧凑行范围；无 finding 也不得只返回裸 `PASS`。始终给 Coverage：检查过的生产入口/模块、采用的审查维度、无 finding 的高风险路径、无法从 diff 或上下文验证的范围。返回 `verdict | coverage | findings` 紧凑索引，完整证据/影响/建议写入 parent 提供的报告 artifact；示例见 [审查示例](references/examples.md)。
