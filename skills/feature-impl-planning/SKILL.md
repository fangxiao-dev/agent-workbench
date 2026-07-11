---
name: feature-impl-planning
description: >
  Impl-Package 体系的薄 plan 阶段：当用户为一个具体改动索要 implementation plan、feature plan、
  patch plan、实现计划、补丁计划或 issue 实现计划时使用；也用于其他工作流在
  tracked execution 开始前需要基于已批准 spec 创建 plan 时。不用于维护长期
  PRD、架构或 feature-design 文档，也不用于执行追踪账本。
---

# Feature Impl Planning

消费 `requirement-alignment` 已通过两道门的 `spec.md`，为一个具体实现任务创建
一份低上下文 coding agent 可以直接执行的薄 plan。Composition、状态事实源、task
到 acceptance 追踪、seam 与升级规则以
[Impl-Package Composition Contract](../../docs/skill-design/references/impl-package-composition-contract.md)
为准；本 skill 只引用，不重新定义这些语义。

## 输出模型

```text
docs/implementations/<package-id>/
  spec.md                                    # requirement-alignment 拥有的已过门合同
  plan.md                                    # 初始实现计划
  YYYYMMDD-HHMM-<patch-topic>.patch-plan.md  # 后续 patch plan
```

- `spec.md`：只读规划输入；由 `requirement-alignment` 拥有和过门。
- `plan.md`：随 `spec.md` 的 Composition 分支生成：无 tickets 时可承载可执行
  checklist；有 tickets 时只承载跨 slice 工程契约，绝不成为 ticket 或任务状态副本。
- patch plan：同一 package-id 的后续计划，链接更新后的 `spec.md`，不复制原始计划。

如果仓库已有不同的 implementation-workspace 约定，在保留这三个角色的前提下
适配该约定。

## 边界

- 不创建或重写 `design.md` / `spec.md`，也不更新长期 PRD、ARD、feature-design
  文档。合同缺失或 gate 未通过时路由回 `requirement-alignment`。
- `Composition:` 只由已过门 `spec.md` 定义。本 skill 可以发现不匹配、提出或记录
  revision 请求并路由回 `requirement-alignment`，但**不得自行改写 `Composition:`**、
  以 plan 绕过任一 gate，或把 plan 变成第二个 composition 真相源。
- 不创建或维护执行账本。`dag.md`、`tasks/Tn-progress.md`、
  `tasks/Tn-handoff.md`、`findings.md`、`gate.md` 归 `dev-with-track` 所有。
  tracked execution 开始或已激活时，交接 package-id 和当前生效的 plan 文件，由
  `dev-with-track` 依据这些规划输入自行刷新状态。

## 工作流

1. **路由请求。** 先判定需求是 new implementation，还是对已经 gate closed 的
   implementation 做 patch/follow-up。已有 package-id 只决定“复用哪个 implementation
   目录”，不自动决定 patch 生命周期：
   - implementation 尚未 gate closed（仍在需求理解、spec/plan/DAG/执行阶段）时，
     需求纠正或范围澄清路由 `requirement-alignment` 原地修订并重新通过 spec gate；
     计划修正只由本 skill 原地更新 `plan.md`；`dag.md` 修正路由 `create-task-dag`，
     tracking 修正路由 `dev-with-track`。不创建 patch plan。
   - 只有原 package 已关闭 gate，之后出现新增需求、回归修复或增量范围，才进入
     patch 模式；复用同一 package-id，并在动笔前先读 [patching.md](./patching.md)。
     不建立每 ticket patch：patch 始终属于已关闭 package 的 post-gate 生命周期。
   - 通过语义搜索 implementation 目录、plan/spec 文件名、issue ID、feature 名和
     涉及模块来定位 owning package-id。两个候选 package-id 都合理时，先问一个简短问题，
     不要另建 workspace。
   完成标准：routing、package-id 和“原地修订 vs 新 patch plan”的依据已明确。

2. **按语义发现上下文，不依赖固定目录名。** 收集：来源需求、issue、handoff
   或讨论；长期 PRD/产品文档；架构、ADR、数据契约文档；已有 feature/模块
   设计；测试与验证文档；已有 implementation workspace（含 package-id 内
   `design.md`、既往 plan、handoff）；以及用于校验或纠正文档的 focused code
   facts。目录缺失只是线索缺失，不是阻塞。完成标准：能说清功能合同和它触及
   的代码面。

3. **验证并消费 `spec.md`。** 确认 Design Gate 与 Spec Gate 都是 `PASSED`、厚
   合同八节齐全且没有 blocking owner decision。缺失或不一致时路由回
   `requirement-alignment`，本 skill 不补写合同。完成标准：已过门 spec 是 plan
   唯一功能合同输入。

4. **读取 Composition 并选择 plan 形态。** 从已过门 spec 读取且只读取唯一一行
   `Composition: tickets=<true|false>, dag=<true|false>`，检查与现有 artifact
   一致。若计划发现必须升级 composition，记录原因和受影响内容，路由
   `requirement-alignment` 修订并重新过两道门；通过后才执行本 skill 的受控 Composition 升级迁移。
   绝不在 plan 内自行决定或降级 composition。

5. **按固定顺序创建并交叉审查。** 新 implementation 的顺序恒为
   **plan → to-tickets draft → cross-check plan**：
   - 先按 Composition 写 `plan.md`。`tickets=false, dag=false` 时可写 T<n>
     executable checklist；每项必须遵循共享 contract 的 `contributes-to` / `enables`
     与 `seam: none` 规则，且不得写 seam execution owner。`tickets=false, dag=true`
     时 task decomposition 归 DAG，plan 不保留 task checklist；`tickets=false, dag=true`
     时，plan 填写 Package Engineering Contract，其中 seam contract、acceptance owner
     和 affected targets 属于 plan，execution owner 仅在 `dag.md` task 中声明。
   - `tickets=true` 时调用 `to-tickets` 的 **draft** 模式切 delivery slices，随后按
     `dag` 分支处理：
     - `tickets=true, dag=false` 时，plan 是 tickets-only 形态：不调用
       `create-task-dag`、不建立 task artifact；ticket 文件是 AC evidence 与验收状态
       的事实源，plan 不复制 ticket 正文、worker ownership、文件级步骤或实时状态；
       tickets-only 仍填写 Package Engineering Contract，记录策略、验证、rollback、
       constraints，且 seam 必须为 `none` 或 `N/A`，不声明 execution seam owner。
     - `tickets=true, dag=true` 时，plan 完全去任务化，只保留跨 slice 策略、seam
       contract、migration/rollback、verification policy 与全局约束；只有相关
       approved tickets 子集才能与本 plan 一起交给 `create-task-dag`。
   - 所有 `dag=true` 形态（only-dag 与 tickets+dag）的每条 plan seam record 都必须
     写明 **Seam ID、Contract owner、Acceptance owner、Affected targets**；execution
     owner 只在 `dag.md` task 中声明，不能回填到 plan。
   - ticket draft 返回后，交叉检查 ticket 与 plan：补足跨 slice seam、全局约束、
     migration/rollback 和 verification policy，或将 ticket 暴露的合同缺口路由回
     `requirement-alignment`。只有 `tickets=true, dag=true` 时，owner 批准的相关
     ticket 子集才可成为后续 DAG 输入。
   完成标准：plan 的形态与 spec Composition 一致，且不存在第二个可写状态源。

6. **决定允许的 plan 颗粒度并记录**在 plan 头部的 `Granularity:` 行。仅当
   `tickets=false, dag=false` 时，默认是 **repo-local executable checklist**；
   仅当改动很小且边界清晰——通常 1-2 个文件、测试明确、且完整代码片段确实能
   降低歧义——才回退到 superpowers 风格的 micro-step + 完整代码片段，并记录回退
   原因。所有其他 Composition 形态记录 `Granularity: N/A — task decomposition outside plan`，
   不以 plan 承载 executable task。

7. **读 `superpowers:writing-plans` 的 SKILL.md**（可用时），在写 plan 之前。
   只取它的质量标准：具体性、精确命令、预期结果、清除占位符。不采用它的输出
   路径（`docs/superpowers/plans/...`）和默认 micro-step 格式——颗粒度由第 4
   步决定，输出路径由本 skill 决定。

8. **写 plan**，使用
   [assets/templates/plan.md](./assets/templates/plan.md)：新实现写
   `plan.md`；patch 在 package-id 根目录新建
   `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`（绝不覆盖 `plan.md`）。按第 5 步
   形态填入 input packet、契约或 checklist、验证和回滚；不留占位符，不写
   “加个校验”这类模糊步骤。Composition 从既有形态升级时，使用模板的
   `Composition Migration` 记录 previous/new/reason/moved content/relocation
   pointer/verification，迁移旧内容至新的 canonical home 后删除旧维护入口；不
   创建每 ticket patch。

9. **成对审查。** 环境允许时用 review subagent 执行下方审查清单；否则内联
   执行，并在总结中说明用的哪种方式。应用修正，使正式文档可独立成立。

10. **返回输出契约。**

## 审查清单

- 选定 package-id 内的 `spec.md` 已由 `requirement-alignment` 通过两道门；plan 实现的
  是当前 spec 合同。
- plan 消费且不改写 spec 的唯一 Composition 行；无 tickets 与有 tickets 的形态
  满足共享 contract；`tickets=true, dag=false` 不得调用 `create-task-dag` 或建立
  task artifact，但仍填写 Package Engineering Contract 且 seam 为 `none`/`N/A`；
  `tickets=false, dag=true` 或 `tickets=true, dag=true` 必须在 plan 记录 Seam ID、
  Contract owner、Acceptance owner 与 Affected targets，execution owner 只在 DAG；
  后者才能交接相关 approved tickets 子集给 DAG。
- 新 implementation 按 **plan → to-tickets draft → cross-check plan** 执行；若不
  earn tickets，明确记录不 earn 的理由和适用的 no-ticket plan 分支。
- 无 DAG 的 checklist task 都有有效 `spec:AC-<n>` acceptance target、`seam: none`，
  且没有 seam execution owner。
- 每个 Composition 升级都有 previous/new/reason/moved content/relocation pointer/
  verification；迁移后没有双重可写事实源。
- 新实现有 `plan.md`；patch 在 package-id 根目录有新的带日期 patch plan，且复用了
  owning package-id。patch 仅能在 package gate closed 后创建，不能按 ticket 建 patch。
- 功能语义在 `spec.md` 中，而不是只藏在 plan 里。
- 颗粒度决策已记录；micro-step 风格仅用于非常小、边界清晰的任务。
- 验证命令具体、限定在本次改动范围内、写明预期结果。
- 提议的 tracking task ID 从 package-id 内已有最高 `T<number>` 继续编号。
- 长期文档只被引用，未被修改。
- 待定 owner 决策明确列出，与实现步骤分离。

## 输出契约

返回：

- 选定的 topic slug、package-id 和 routing（new implementation 或 patch/follow-up）
- 创建或修改的文件
- 消费的 Composition、plan 形态，以及是否完成 `plan → to-tickets draft → cross-check plan`
- 若有：Composition 升级迁移记录与共享 contract 验证结果
- 颗粒度决策
- 审查方式与所做修正
- 剩余 owner 决策
- plan 是否已可进入实现
