# [执行尝试名称] 实施计划

创建时间（Created）：
Attempt ID：<initial | YYYYMMDD-HHMM-patch-topic>
Composition：tickets=true, dag=false

> 直接引用当前 decision.md / spec.md。D/S/P 为可选旧别名，不因普通编辑升级；Git commit ID 是唯一允许持久化的历史锚点。Plan 只承载主 session 的全局调度（Composition、Ticket 顺序/依赖、共享资源串行规则、全局执行边界、Final Gate 判据）；Ticket 各自的建设内容、AC 和 contract references 属于 Ticket，不在此重复。

## 摘要

## 输入

- 决策：decision.md 或 spec.md 内的轻量 Decision
- 规格：spec.md + contract-design.md disposition（未触及的 legacy Spec 可暂缺）
- 需求 / patch 来源：
- 已检查的当前代码、测试和稳定文档：
- 前置包（Predecessors）：None | <repo-relative-package-path>[, <repo-relative-package-path> ...]

前置包必须显式填写 `None` 或一个/多个已存在的仓库相对 package 目录；不要留空或省略。`package init` 会把它写入 `.impl-package/state.json`，到达路径中的 `EXISTS` 先在这些前置包的 tracked 非 Markdown 产出范围查找。

## 执行组合决策

- Tickets：yes（新 package 固定 Ticket-only）
- 理由：
- DAG：新 package 固定 no；`dag=false` 是 3.5 Composition 合同字段，旧 3.4 package 迁移前只读
- 旧 package 迁移/恢复例外：<N/A | legacy package path + owner authorization>

## 全局调度

| Ticket | 顺序 | Typed dependency | 共享资源（需串行） |
| --- | --- | --- | --- |

只登记跨 Ticket 的调度信息；单个 Ticket 的建设内容、AC 与 contract references 详见该 Ticket 文件，不在此重复。约束到 Ticket 的映射由 Ticket 自身的 Contract references 承载，本表不重复该映射；跨 Ticket 覆盖完整性由 `plan-review` 在 bundle-admission/full-review 时对照 Decision/Spec 与全部 Ticket 直接核对。

## 全局执行边界

- rollout / rollback：
- 目标分支：
- 集成顺序：gate-before-merge | owner-approved pre-gate integration
- pre-gate integration 授权：<不适用时填 N/A>

## 计划验证（跨 Ticket / 全局）

| 场景 / 约束 | 检查 | 预期结果 | 证据 owner |
| --- | --- | --- | --- |

只登记跨 Ticket 的共享验证（如集成套件、契约生成、跨系统一致性检查）；单个 Ticket 内部场景的验证写在该 Ticket 的 AC，不在此重复。

## Final Gate

- 判据：默认沿用 dev-with-track 标准（全部 Required Ticket SATISFIED + review closed + durable delta 已登记或已说明无增量）；如本 Attempt 有额外判据在此列出。
- 记录位置：`gate.md`（本节只声明判据，不复制 Gate 记录本身）。

## 交接

- Ticket 集合：<tickets/ | N/A>
- DAG：N/A（新 package）；旧 package 仅引用 existing DAG
- 下一动作：
- 剩余 owner 决策：<none | 具体事项>

## Bundle Review & Approval

- Plan freeze：<pending | frozen>
- Joint validation：<Ticket coverage / typed dependency / shared-resource validation / evidence feasibility / integration order>
- Review result：<cleared | revise | owner-decision | N/A>
- Owner approval：<same-session statement | Git commit ID | pending>
- Progress：progress.md（`init` 后生成）

## Patch 增量

<!-- initial attempt 删除本节。 -->

- 上一个 terminal gate：
- 变化分类：implementation-only | behavior-contract | decision-direction
- 复用或更新的 D/S：
- 相对已验收行为的增量：
- 回归范围：
