# [执行尝试名称] 实施计划

创建时间（Created）：
执行尝试 ID（Attempt ID）：<initial | YYYYMMDD-HHMM-patch-topic>
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D<n>
规格修订（Spec Revision）：S<n>
计划修订（Plan Revision）：P<n>
<!-- impl-package:projection revision-set end -->
执行组合（Composition）：tickets=<true|false>, dag=<true|false>
任务包 ID（Package ID）：
发布时绑定校验（Binding Validation at Publication）：Pending | Passed
决策：[decision.md](decision.md) | spec 中的轻量 Decision 记录
规格：[spec.md](spec.md)
门禁账本：首次 gate evaluation 由 `dev-with-track` 创建 `gate.md`；未创建表示当前 attempt 尚无 gate verdict。

> decision/spec 是当前 contract SoT。本 plan 只记录本 attempt 的执行策略、验证计划和过程证据。terminal gate verdict 后冻结。

## 摘要

## 输入与权威来源

- 需求 / patch 来源：
- 已检查的当前 module knowledge：
- 聚焦代码 / 测试事实：
- D/S gate 证据：
- 上一个 terminal gate entry（仅 patch）：
- Module Knowledge Watermark（本 attempt 打开时，decision/spec 引用的每份 module-knowledge 文件的 `git log -1` commit SHA；下次 attempt 打开时用来对账是否已被别的改动推进）：

## 执行组合决策

- 是否 earned tickets：yes | no
- Tickets 理由：
- 是否 earned DAG：yes | no
- DAG 理由：
- 执行状态来源：
- 验收状态来源：

## 执行策略

- 有序实施方式：
- 具体迁移 / 集成操作：
- Rollout / rollback 操作：
- 依赖与前置条件：
- 目标分支：
- 集成顺序：gate-before-merge | owner-approved pre-gate integration
- Gate 前集成的 owner 决策证据：<仅在 owner-approved pre-gate integration 时填写；否则 N/A>

<!-- 稳定 interface、seam contract、compatibility、global constraints 和 Acceptance Semantics 不写在这里；缺失时先修订 spec。 -->

## 计划验证

| Policy / 场景来源 | 选定检查 | 预期结果 | 证据 owner |
| --- | --- | --- | --- |

<!-- 引用权威 policy；不要复制通用 Data Safety、UI Evidence、Real Route Safety checklist。 -->

## 执行记录

<!-- 仅允许追加。旧 entry 不改；补证新增 ER-n。 -->

### ER-<n>

- 记录时间：
- Decision / Spec / Plan 修订：
- 检查或命令：
- 结果：
- 证据路径：
- 剩余风险 / 后续动作：

## 执行尝试产物交接

- 计划审查交接：仅在 earned bundle 联合校验后由 fresh `plan-review mode=bundle-admission` 填写；未执行审查时不要以 `Pending`、hash 或 receipt 伪造状态。
- 独立审查结论：
- 简短理由 / material signal：
- 下一动作：
- Ticket 集合：<paths | N/A>
- DAG：<dag.md or patch-dag path | N/A>
- 进度账本：<path | N/A until trigger>
- 执行发现：<execution-findings.md | 尚未 earned>
- 调查材料：<investigations/<topic>.md | 尚未 earned；仅按需链接>

## 计划修订历史

<!-- 当前和历史 P 内容绑定保存在内部 `.impl-package/revision-bindings.json` sidecar 中，不得要求 owner 阅读它。仍引用已被取代 P<n> 的 earned ticket/DAG 在完成对账前均为 NEEDS-REVALIDATION。 -->

| 前一修订 | 新修订 | 策略 / Composition / 验证变化 | 原因 | 产物迁移 | 日期 |
| --- | --- | --- | --- | --- | --- |

## Patch 增量

<!-- 初始 attempt 删除本节。 -->

- 上一个 terminal gate entry：
- Drift 分类：implementation-only | behavior contract | decision direction
- 复用或更新的 D/S 修订：
- 相对已验收行为的增量：
- 回归范围：
