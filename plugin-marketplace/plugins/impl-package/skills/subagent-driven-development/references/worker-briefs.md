# Worker Briefs

本页只规定 `investigate`、`implement`、`fix` 三种 mode 的派发 prompt 放什么内容：不建立跨 host 抽象，不发明引用语法，不规定固定 envelope，不规定强制换人条件。mode 的答案形态见 [SKILL.md](../SKILL.md) 的 Step 1 表，换人条件见 [SKILL.md](../SKILL.md) 的 Step 4/5；executor、model、provider 的选择见仓库根 `AGENTS.md`。

## 一、统一原则

派发前，caller 必须先用一句话说清这次要什么——包括“目标就是完全不知道在哪、需要盲搜”这种情况本身也算一种明确目标，不是例外。在此基础上，caller 要把自己上下文里与这次目标**强相关、且仅强相关**的信息给 worker：不甩全部背景材料让 worker 自己筛（会让它重新做已经做完的定位/分析工作，或带着无关信息误判范围），也不能藏关键信息让 worker 从头查一遍已经查清楚的东西。

## 二、调研类（investigate）

- 一次派发只对应一个会改变 Topic 决策的子问题，不把“把整个方案/系统调研清楚”当作一个大目标。
- 多个知识来源共同回答同一个 Dispatcher-admitted Topic 决策时保持一次派发；是否拆分以 `$dispatcher` 的 Topic-first 门槛为准。
- 目标够窄时，允许给较宽的材料范围支撑这一个子目标的检索，例如把整个代码库作为搜索范围；检索范围宽不等于目标宽，不违反强相关原则。

## 三、实现类（implement / fix）

### implementer

- 给 plan 里已经裁决要做的 baby step；一次 implement dispatch 只跨越一个主控 return point；同一 implementer 可在主控消费 return 后，通过 follow-up 连续承接下一步。不把整份 plan 都丢过去，也不把每个机械步骤重新派发。
- 配上这一片段的 bounded outcome、write-set、禁改路径和验证入口。
- 这一片段对应的验收细节要逐项带上（状态、边界行为、不变量等），不能只压缩成一句 bounded outcome 摘要；被压缩掉的条款不会被 worker 或后续 review 自动找回。
- 验证入口必须走这一片段在合同里承担的真实路径（例如真实渲染树、真实上游依赖、真实交互序列），不能用绕开该路径的捷径代替——捷径证明的是别的东西，不是这一片段要保证的东西。
- focused test、lint/format、普通重跑和本动作产生的机械 cleanup 跟随实现；错误 cwd 或本地载体缺失在 scope 仍可信时沿同一 worker 恢复。
- 上一步轻量 delta review 的已确认 findings 随本次 brief 下发，在本步一起修复。

### fixer

- 把 bug 的定位、reviewer 的原始意见，以及 caller 自己对该意见的初步分析结论一起给它。
- 不能只给“有个 bug”这个现象，逼 fixer 把 reviewer 已经做完的定位工作重新做一遍。

reviewer 的 input 设计不在本页范围，见 `do-review`。
