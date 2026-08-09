# Test Review

## 识别现状

先识别仓库已有测试框架、测试层级、fixtures、mock 边界、CI 入口和相邻回归测试。不要为计划虚构与项目不兼容的测试栈。

## 发现 Material Behaviors

对每个 material entry point 做有界追踪：`input/setup → validation → transform/branch → state or side effect → user/operator 可观察结果`。追踪真实 contract 和高风险分支，不要求逐行枚举或机械达到 100%；每个纳入 coverage map 的行为都要有可观察 oracle，不能只写“增加测试”。

用户交互相关计划按实际风险检查重复提交、中途离开、陈旧会话、慢响应、并发操作、空/边界状态和失败后能否恢复。后台或运维流程用 operator signal、持久状态和重试/恢复结果替代 UI 假设。

## Coverage Judgment

行为变更必须形成可核验的 coverage judgment。单路径或少量场景直接用短段或列表表达；当多个行为、风险与测试层级的对应关系用 prose 容易混淆时，再使用紧凑 coverage map：

```text
behavior | risk | test level | oracle | failure mode
```

无论使用哪种表达形式，都按风险选择正常流、负向流、边界、并发、超时、重试、重复执行、非法状态转换、已有目标覆盖、部分写入、陈旧数据、权限、兼容迁移和回滚场景。对 schema 或持久化格式变化检查 legacy/canonical round-trip 与非目标内容保留。只有多路径、跨组件或短表无法清楚表达对应关系时才升级为 test diagram。

每项关键测试说明 setup/input、执行边界、oracle 和预期 failure。纯逻辑与局部边界优先 unit；mock 会遮蔽真实失败的集成点、跨组件主路径以及 auth、支付、数据破坏等高风险流程使用 integration/E2E；Prompt、LLM 或其他非确定行为使用 eval 与 baseline。不要仅凭组件数量决定测试层级。

检查已有测试是在断言行为与外部结果，还是只有 existence、snapshot-noise 或“不抛异常”的 smoke assertion。计划依赖 mock 时，确认 mock 没有跳过 serialization、权限、事务、队列、协议版本或真实失败边界。

## 高风险验证就绪

当计划涉及分页/cursor、并发/锁、权限范围、持久化或外部 mutation、single-use/replay/recovery 等 material 高风险边界时，确认执行者能从 spec/AC 行为边界直接定位到本次选定的正常流和关键负向/竞态场景、测试层级或入口、可观察 oracle 与后续 ER evidence owner。测试必须能区分正确实现与常见错误实现；只写“补测试”、只覆盖绿色路径或把关键 case 留给执行阶段设计，都不满足 implementation-ready。

只判断语义链路是否稳定可定位，不要求统一 case/invariant ID、固定矩阵或每条 edge 单独建档；已有 AC anchor、场景名、测试名或清晰引用足以消除歧义时直接复用。缺少行为边界或 Acceptance Semantics 时路由 `/impl-package:req-align`，缺少验证选择、入口、oracle 或 evidence owner 时路由 `/impl-package:impl-planning`；reviewer 不替 owning skill 补写第二套合同。

## Failure Modes

对每个 material 行为或集成分别检查：是否有测试、是否有错误处理、失败是否对用户或 operator 可见。三者都缺失时形成 critical test requirement。

已确认 regression 如果没有防止复发的测试，必须进入 critical requirement；不要把它降为普通 owner 偏好。触及已知 regression、revert 或 incident 区域时按需读取相邻历史和既有回归测试，不做无关的全仓 retrospective。Prompt、LLM 或 agent 行为变化需要对应 eval cases、baseline 和判定 oracle。

输出与风险相称的 coverage judgment、关键 failure gaps 和必要测试要求。表达形式可以不同，但不得省略测试分析或关键语义链路。
