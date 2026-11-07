# [实施名称] 规格

状态（Status）：Draft | Spec Gate Passed | Spec Gate Blocked
创建时间（Created）：
需求来源（Requirement source）：
主题 slug（Topic slug）：
任务包 ID（Package ID）：
规范任务包路径（Canonical package）：`docs/implementations/<package-id>/`
决策（Decision）：[decision.md](decision.md) | 无独立 decision 文件

## Decision 门记录（Decision Gate Record）

<!-- 仅在 Decision PASSED 后填写。没有 decision.md 时，本节是必经 lightweight Decision 步骤的规范最小证据。Decision BLOCKED 路径使用 decision.md，不生成本 spec。因此，已存在 spec 中的 Decision Gate Result 只能是 PASSED。`Status: Spec Gate Passed` 要求 Spec Gate Result 为 PASSED；`Status: Spec Gate Blocked` 要求 Spec Gate Result 为 BLOCKED。若引用 investigations/<topic>.md，本 spec 仍必须自足表达当前行为合同。 -->

- 结果（Result）：PASSED
- 目标落点与预期结果：
- 权威来源 / 当前状态证据：
- 选定方向与理由：
- Blocking-uncertainty triage / 开放问题处理结果：
- Owner 决策（已解决 / 未解决）：
- 证据位置：decision.md | 本记录
- 评估人 / 日期：

## Spec 设计范围

<!-- 每次创建或更新本 Spec 时首先整体重建本节。这里只保存当前完整合同对象与唯一承载位置，不记录本轮 delta 或历史判断。对象必须写具体名称，不能只写 api=true / persistence=true。没有某类 surface 时写“无”。只冻结会改变可观察行为或正确性的维度，不为不适用项补空合同。 -->

- API operations：
- Persistence models：
- Cross-module seams：
- Public read models：
- 详细合同承载：[contract-design.md](contract-design.md)（Disposition: detailed | not-required；not-required 时写明本文件如何完整承担精确语义）

## Spec 门记录（Spec Gate Record）

- 结果（Result）：PASSED | BLOCKED
- 当前设计范围已完整兑现：
- 详细合同 authority 无重复或冲突：
- 八个行为合同章节完整：
- Journey、必验变体与必需套件已批准、行为合同的每条承诺有可观察证据：
- 阻塞决策 / 歧义：
- 批准人 / 日期：

## 1. 范围 / 权威来源 / 非目标

- 范围：
- 权威来源与优先级：
- 非目标：
- 需要确认的假设：

## 2. 术语 / 数据合同

- 领域术语：
- 输入、输出、身份与不变量：
- 数据结构、归一化、精度与 ownership 语义：
- 精确合同引用：本节 | [contract-design.md](contract-design.md) 的稳定章节 | 不适用
- 条件化 evidence-integrity 合同（仅当验收结论依赖权威证据、发布/消费状态、兼容投影、外部副作用或随状态变化的公共输出时填写）：主要断言与比较单元；来源权威与私有字段排除；实际范围与声明范围；完整 frozen-format admission；发布不完整后 reader 可相信的权威状态；预期 operational failure 表面与稳定公共 shape。

## 3. 行为 / 状态机 / 工作流

| Actor / 系统 | 条件 / 状态 | 动作 / 事件 | 结果 / 下一状态 |
| --- | --- | --- | --- |

## 4. 模块边界 / 依赖

- Owning 模块及其职责：
- Core 不变量与 Capability 暴露边界：
- 接口与 seam：
- 上游 / 下游依赖：
- 兼容或迁移窗口：

## 5. 错误边界 / 失败恢复

| 失败模式 | 可观察影响 | 隔离方式 | 重试 / 补偿 / 恢复 | Owner |
| --- | --- | --- | --- | --- |

## 6. 约束合同

- 禁止行为：
- Trust 与 permission 边界：
- 精度 / 归一化义务：
- 外部 provider 义务：
- 负向依赖（不得依赖）：

## 7. 验收语义 / 验证证据

<!-- 验收合同是下面三张固定表（Journeys、Rule Matrix、Required Suites），表头与标题原样保留，由 runtime 解析；`### Journey 变体` 是补充信息小节，runtime 不解析。Spec 不写 Ticket ID（Ticket 的 Coverage 认领 step 与套件）。-->

### Journeys

<!-- 每条 Journey 用 Owner 语言写一次完整业务旅程，2–5 条是经验值。每步是某个角色亲手做或亲自收到的事：角色列写执行者（如 企业端用户 / 税务师 / 平台管理员），页面步用该角色自己的账号做。入口类型 `页面`（在界面上操作，控件列写页面上可见的控件名或稳定标识，如 `完成`）、`文件`（收到的真实文件，控件列写 `—`）或 `记录`（核对页面无法呈现的运行记录，如“AI 确实调用了平台工具”，控件列写 `—`）；`记录` 步补证、不替代页面/文件步，也不能做第 1 步。用户看不到的行为（并发、幂等、回滚、租户隔离等）写进 Rule Matrix 与套件，不进 Journey。账号、权限、种子账套等前置条件写在标题下的 `准备：` 行，由 harness 预置，不是步骤；每条 Journey 只能有一行 `准备：`；必须发生在步骤之间的脚手架（回放邮件、刷新前造数据）写在该步操作入口前的说明里，不另起 `准备：`。承接列写上一步交给本步的业务对象（如 `账单 ID`），无则 `—`；第 1 步恒为 `—`。step id 为 J<n>-S<m>。
取证行（紧随 `准备：`，每条 Journey 一行，建 Journey 时定，之后不因失败改）：默认写 `取证：浏览器走查`，页面步由执行 agent 用内置浏览器逐步操作并截图。只有浏览器走查给不了的精确测量（响应时间/延迟阈值如 ≤300ms、动画时长）才写 `取证：Playwright（理由：<点名 step 与要测量的量>）`；未点名的步仍走查。理由写不出测量量，就改回浏览器走查。 -->

#### J1 <终态>

准备：<账号、权限、种子数据；无则 none>
取证：浏览器走查 | Playwright（理由：<J1-S? 的响应 ≤300ms 等测量量>）

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J1-S1 | | 页面 | | | | | — |

### Journey 变体

<!-- 本小节必须是与 `### Journeys` 同级的 `###` 小节，不能放进 Journeys 内（runtime 会把其中的标题和表格当作 Journey 解析并报错）；runtime 不解析本小节。只对涉及权限或数据范围的步骤补充，按 step id 关联，不改上面的 Journey 表头与步骤；细则见 req-align 的 references/acceptance-contract.md。每个涉及权限或数据范围的步骤都要出现（变体或步骤级不适用）。每个关联步骤一个 `#### J<n>-S<m>` 小标题：先写“要读的数据”（含历史、跨门店、参考数据），再用表列变体执行者；变体所需账号、授权状态与前置动作写在“前置”列，不写进 `准备：`。下面的 `J1-S?` 等占位必须换成真实 step id 或删除：runtime 不解析本小节，占位不会报错。预期取 完成 / 部分 / 拒绝；必验取 是 / 否，必验变体是验收合同的一部分。无适用变体的步骤写 `- J<n>-S<m>：不适用（理由：…）`，整条 Journey 不适用可写 `- J<n>：不适用（理由：…）`，理由点名各步角色与数据范围，不虚构变体。触发词（委派、临时、只读、历史、跨门店、跨月）只是示例，不机械触发。必验变体的走查核对属于验收 Gate（见 acceptance-contract.md），不是 Spec Gate 条件。 -->

#### J1-S? <步骤简述>

- 要读的数据：

| 变体执行者 | 前置 | 预期 | 可观察表现 | 必验 |
| --- | --- | --- | --- | --- |
| | | 完成 \| 部分 \| 拒绝 | | 是 \| 否 |

- J?-S?：不适用（理由：）

### Rule Matrix

| Rule | Source | Suite | Oracle |
| --- | --- | --- | --- |

- 无需验收的章节：

<!-- Source 写本 Spec 内的章节引用（`§N`、`§N.M` 或标题原文，逗号分隔），引用父章节即覆盖其子章节。除 §7 外，每个二、三级标题都要被某条规则的 Source 引用，或列在“无需验收的章节”行（无则写 none）；`package check-spec` 列出遗漏。每条规则有可观察 oracle 并指向一个必需套件；展示、编辑或拒绝结果可以不产生新记录，发生权威状态转换时明确记录、producer 和下游消费。 -->

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |

<!-- Kind：rule | safety；Scope：ticket | package。触及 tenant、RBAC/privacy、幂等或数据完整性时声明包级 safety 套件，未触及时在此写明理由。Environment 写明确字符串，记录按字符串精确匹配。 -->
<!-- 当条件化 evidence-integrity 合同适用时，只加入相关的 false-PASS 反例，例如：归一化掩盖比较 drift、副作用后失败、rollback/invalidation 失败、不兼容投影输入或状态 shape 漂移。这些只是示例，不是必选场景。 -->

## 8. 合同一致性

- 跨章节一致性：
- 接口 / seam ownership：
- 验收覆盖：
- 剩余非阻塞假设：

## 变更说明

<!-- 当前文档只保留事实源；历史由 Git 保存。只有影响 Gate 或下游范围的变化才在正文中说明。 -->
