# 约束提取与分流

## 两问 litmus

对每条原子陈述依次问：

1. 完全替换实现但用户价值不变时，它是否仍必须成立？是则是 intent 候选。
2. 它能否由测试、接口、状态查询或故障演练直接验证？是则是 behavior contract
   候选。

双是时，第二问优先：把可验证承诺归 module spec。外部系统速率义务既保护
价值又可观测，属于典型双是合同。若一句话同时解释 why 和规定 how，拆成两个
delta；不要在 PRD 与 spec 原样复制。

第二问不是“任何可测试实现都进 spec”。还要问：替换 adapter、锁实现、缓存或
队列后，外部可观察承诺是否仍需成立？若不需要，保留测试/代码 authority，不
提升 token、helper、具体锁顺序等机制。

## 约束型合同清单

每轮逐模块显式搜索以下类别。描述型 happy path 不能代替这些负向边界。

| 类别 | 泛化示例 | 优先线索源 |
| --- | --- | --- |
| 禁止事项 | 已确认记录不得被 replay 重复变更 | `rejects`、`never`、`does not` 测试名；guard；fail-closed branch |
| 信任边界 | mutation 不接受 browser 提交的 authoritative rows | Server Action/handler DTO；hidden input；server reload；authorization guard |
| 数值精度与归一化 | 输入 money 用 cents，比率 evidence 用固定小数精度 | rounding helper；decimal constant；serialization；mismatch test |
| 外部 provider 义务 | 主动遵守当前 provider 限速；retry 不能替代 pacing | client 调用面；env/config 常量；429 测试；官方 contract；共享 request gate |
| 负依赖 / hard cut | 新流程不得重新读写 legacy audit store | deleted adapter；readiness/schema check；“no longer requires” test；migration decision |

线索只负责发现候选，不自动证明 durability。每条候选都要找到 current authority
和对未来替换实现仍有意义的 observable statement。

## Source 顺序

按以下顺序交叉验证，不把单一来源当完整真相：

1. 当前常青 PRD/spec、项目语言与 architecture 边界；
2. confirmed gate、批准 design 和 owner 决策；
3. 当前接口、状态模型、guard、tests 与 verification；
4. watermark 后 commits 与无法归属的 diff；
5. 外部 provider 合同时，使用当前官方来源确认 versioned 数值。

代码能证明 current behavior，不能单独证明 product intent。旧设计能发现遗漏，
不能在没有 current evidence 时自动复活。发生冲突时报告 owner decision，不猜。

## 分流

| 输入 | 目的地 |
| --- | --- |
| 可验证的当前模块行为、禁止项、边界、失败与恢复 | `module-spec` 或子域合同 |
| 模块为何存在、拥有的价值切片 | `module-prd` |
| journey/product 级 intent | `top-level-prd` |
| canonical actor、对象或术语 | `context-language` |
| 本次变更的方案与取舍 | implementation-local design |
| 可复用 trap、诊断或恢复捷径 | hands-on knowledge |
| 没有 durable delta | `none` + 原因 |

## Module PRD 惰性创建门

缺失的 `prd.md` 只有同时满足以下条件才可在 apply 首建：

- Purpose；
- 用户或 journey；
- Outcomes；
- Scope/Non-goals；
- top-level PRD 上链；
- module spec 下链；
- intent authority 来自 top-level PRD、批准 design、owner 决策或 confirmed gate。

材料不足时保留 pending。不得用代码行为扩写缺失的 intent，也不得创建只有标题
和一句 slogan 的文件。

## 人工 fixtures

| 输入 | 预期结果 |
| --- | --- |
| “过期 snapshot 必须被拒绝并返回可重试冲突。” | `module-spec` |
| “该模块让用户跨会话恢复未完成 journey。” | 已有 PRD 则更新；缺失且内容门不足则 pending |
| “多个模块共同支撑从配置到首次成功结果的 journey。” | `top-level-prd` |
| “Account 是全项目 canonical actor 名称。” | `context-language` |
| “本次迁移先加 adapter 再切换 persisted schema。” | implementation-local design |
| “只重命名 local helper，外部行为与意图未变。” | `none` |
| “必须主动遵守 provider 当前速率限制；使用共享 pacing。” | observable 义务进 `module-spec`；可替换机制仅作 evidence/实现建议 |

Fixture 通过标准不是关键词命中，而是 statement 被拆到正确层、没有重复或把
implementation mechanism 误当常青承诺。
