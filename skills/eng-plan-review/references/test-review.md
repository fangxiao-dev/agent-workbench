# Test Review

## 识别现状

先识别仓库已有测试框架、测试层级、fixtures、mock 边界、CI 入口和相邻回归测试。不要为计划虚构与项目不兼容的测试栈。

## 发现 Material Behaviors

对每个 material entry point 做有界追踪：`input/setup → validation → transform/branch → state or side effect → user/operator 可观察结果`。追踪真实 contract 和高风险分支，不要求逐行枚举或机械达到 100%；每个纳入 coverage map 的行为都要有可观察 oracle，不能只写“增加测试”。

用户交互相关计划按实际风险检查重复提交、中途离开、陈旧会话、慢响应、并发操作、空/边界状态和失败后能否恢复。后台或运维流程用 operator signal、持久状态和重试/恢复结果替代 UI 假设。

## Coverage Map

行为变更默认生成紧凑 coverage map：

```text
behavior | risk | test level | oracle | failure mode
```

按风险选择正常流、负向流、边界、并发、超时、重试、重复执行、非法状态转换、已有目标覆盖、部分写入、陈旧数据、权限、兼容迁移和回滚场景。对 schema 或持久化格式变化检查 legacy/canonical round-trip 与非目标内容保留。只有多路径、跨组件或短表无法清楚表达对应关系时才升级为 test diagram。

每项关键测试说明 setup/input、执行边界、oracle 和预期 failure。纯逻辑与局部边界优先 unit；mock 会遮蔽真实失败的集成点、跨组件主路径以及 auth、支付、数据破坏等高风险流程使用 integration/E2E；Prompt、LLM 或其他非确定行为使用 eval 与 baseline。不要仅凭组件数量决定测试层级。

检查已有测试是在断言行为与外部结果，还是只有 existence、snapshot-noise 或“不抛异常”的 smoke assertion。计划依赖 mock 时，确认 mock 没有跳过 serialization、权限、事务、队列、协议版本或真实失败边界。

## Failure Modes

对每个 material 行为或集成分别检查：是否有测试、是否有错误处理、失败是否对用户或 operator 可见。三者都缺失时形成 critical test requirement。

已确认 regression 如果没有防止复发的测试，必须进入 critical requirement；不要把它降为普通 owner 偏好。触及已知 regression、revert 或 incident 区域时按需读取相邻历史和既有回归测试，不做无关的全仓 retrospective。Prompt、LLM 或 agent 行为变化需要对应 eval cases、baseline 和判定 oracle。

输出 coverage map、关键 failure gaps 和必要测试要求。不要因为计划不需要图示而省略测试分析。
