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

优先关注变更后的行为、错误处理、安全、性能、资源、并发/原子性和测试风险。结构、模块归属、抽象与一般 code-quality 现象仍可发现和报告；偏重是注意力启发式，不是能力禁令。

适用于 pull request、固定 comparison point 的实现 diff、代码质量反馈、潜在 bug、安全或性能审查。调用者应提供目标、完整 diff、comparison point、相关合同与仓库上下文；证据不足时明确范围，不猜测未提供的事实。

## Profile

选择能忠实覆盖 diff 的最小 profile：

- **Full behavior review**：代码或运行行为变化。除本文件外，读取 [Full Review Checklist](references/review-checklist.md)。
- **Focused review**：仅 docs、evidence、config metadata。核对 canonical source、事实一致性、链接/路径、ownership、authorization claim、generated/source 边界，以及是否意外改变 executable behavior；不加载不适用的函数、性能或测试 checklist。
- 删除或方向纠正按剩余 authority 审查；除非可观察合同改变，不要求替代内容或扩大测试。

若 focused diff 实际改变 runtime behavior，或隐藏未解决的 contract/safety 变化，升级为 full behavior review。

## Review

1. 理解目标、issue、变更类型、文件范围、已有测试和特殊约束。
2. 从完整 diff 追踪运行入口、数据流、错误路径、资源生命周期与可观察结果；检查行为正确性、边界条件、失败模式和兼容性。
3. 检查输入与权限边界、敏感数据、依赖、并发/原子性、外部副作用、查询与缓存、cleanup 及性能退化。
4. 检查测试是否覆盖新行为、错误与边界，是否可读、确定且正确 setup/teardown；检查实现是否符合仓库惯例且没有不必要复杂度。
5. 每项 finding 只陈述可定位证据、影响与建议；按 Critical、Important、Nice-to-have 排序，不把偏好写成缺陷。

## 输出合同

- Findings 优先，给出文件和紧凑行范围；没有 finding 时也不得只返回裸 `PASS`。
- 始终提供 Coverage：检查过的生产入口/模块、采用的审查维度、无 finding 的高风险路径，以及无法从 diff 或上下文验证的范围。
- 建议应具体、建设性并解释原因；示例格式见 [审查示例](references/examples.md)。
