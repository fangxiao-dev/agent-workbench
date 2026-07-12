---
name: receiving-code-review
description: Use when code review feedback must be evaluated, clarified, prioritized, or applied to the current codebase.
---

# Receiving Code Review

Review feedback 是待核查的技术输入。目标是理解问题并改善代码，而不是机械同意或机械反驳。

## 处理流程

1. 完整阅读全部反馈，识别条目之间的依赖。
2. 用当前需求、代码、测试和仓库约束核查每一项。
3. 对含义、范围或期望结果不明确的条目先澄清；不要用猜测补全 reviewer 意图。
4. 判断反馈属于真实缺陷、证据缺口、可选改进，还是不适用于当前代码库。
5. 按阻断风险、简单修正、复杂变更的顺序处理，并逐项验证。

## 回应原则

- 正确反馈：说明实际问题和已采取或建议采取的动作。
- 不正确或不适用：用代码、测试或既有决策解释原因。
- 与 owner 决策冲突：暂停该条，交由 owner 裁决。
- 无法验证：明确缺少什么证据，不把不确定性包装成结论。

如果用户只要求评估 review，不要自行实施修改。实施完成后，重新检查相关反馈是否真正关闭，并确认没有引入回归。
