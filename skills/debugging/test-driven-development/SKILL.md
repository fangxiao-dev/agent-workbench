---
name: test-driven-development
description: Use after diagnosing-bugs has confirmed the root cause, minimised the reproduction, and identified a correct automated test seam for implementing the fix.
---

# Test-Driven Development

本 skill 是 `diagnosing-bugs` 的修复执行器。它不负责猜根因、选择测试层或决定产品行为；它消费已经确认的诊断结论，用 RED–GREEN–REFACTOR 把修复锁在正确 seam 上。

## 输入门

开始前必须具备：

- 已确认的 root cause 与证据；
- 最小复现及期望行为；
- 能覆盖真实 bug chain 的自动化测试 seam；
- Phase 1 原始 feedback loop 的命令或可重复步骤；
- 仓库测试政策要求的相关验证范围。

缺少 root cause 时回到 `diagnosing-bugs`。没有正确 seam 时不要制造一个过浅测试；把 testability gap 交还诊断流程记录和处理。

## RED

1. 将最小复现写成只表达目标行为的 regression test。
2. 运行测试，确认它失败而不是报错。
3. 确认失败原因正是已诊断的缺陷，而非 typo、fixture、mock 或环境问题。

测试立即通过，说明它没有捕获缺陷；先修正测试或 seam。测试因其他原因失败，先修复 harness，不能把错误的 RED 当作证据。

## GREEN

1. 实施直接修复 root cause 的最小改动。
2. 不夹带无关重构、额外功能或顺手清理。
3. 重跑 regression test，确认它通过。
4. 运行仓库政策要求的相关回归，处理本次修改造成的失败。

## REFACTOR

只有在绿色状态下才整理命名、重复或局部结构。每次 refactor 后重新运行受影响测试，不得改变已确认的行为合同。

## 交还诊断流程

把以下证据返回给 `diagnosing-bugs`：

- RED 命令、预期失败和失败原因；
- 修复摘要及其如何针对 root cause；
- GREEN 与相关回归结果；
- 未覆盖边界和残余风险。

随后由 `diagnosing-bugs` 重跑原始、未最小化的 Phase 1 feedback loop，并完成 instrumentation cleanup 与 post-mortem。TDD 的局部绿色不能单独证明原始 bug 已关闭。

## 测试边界

- 优先测试真实行为；mock 只隔离必要的慢速或外部边界。
- 添加或修改 mock、test utility 时读取 `testing-anti-patterns.md`。
- 具体采用 unit、integration、E2E 或其他层级，由仓库测试政策或 test owner 决定。
