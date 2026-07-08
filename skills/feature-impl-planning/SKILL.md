---
name: feature-impl-planning
description: >
  当用户为一个具体改动索要 implementation plan、feature plan、Func Design、
  patch plan、实现计划、补丁计划或 issue 实现计划时使用；也用于其他工作流在
  tracked execution 开始前需要 task-local spec/plan 规划输入时。不用于维护长期
  PRD、架构或 feature-design 文档，也不用于执行追踪账本。
---

# Feature Impl Planning

为一个具体实现任务创建 task-local 规划文档：ad-hoc 功能合同（`spec.md`）和一份
低上下文 coding agent 可以直接执行的实现计划。

## 输出模型

```text
docs/implementations/<slug>/
  spec.md                                    # task-local ad-hoc Func Design
  plan.md                                    # 初始实现计划
  YYYYMMDD-HHMM-<patch-topic>.patch-plan.md  # 后续 patch plan
```

- `spec.md`：临时功能合同——范围、行为、数据语义、模块边界、验收语义、待定
  owner 决策。
- `plan.md`：执行机制——精确文件、任务、命令、预期结果、验证。
- patch plan：同一 slug 的后续计划，链接更新后的 `spec.md`，不复制原始计划。

如果仓库已有不同的 implementation-workspace 约定，在保留这三个角色的前提下
适配该约定。

## 边界

- 不更新长期 PRD、ARD、feature-design 文档。只引用它们，并把回写候选记入
  `spec.md` 的 Backfill Candidates。
- 不创建或维护执行账本。`dag.md`、`tasks/Tn-progress.md`、
  `tasks/Tn-handoff.md`、`findings.md`、`gate.md` 归 `dev-with-track` 所有。
  tracked execution 开始或已激活时，交接 slug 和当前生效的 plan 文件，由
  `dev-with-track` 依据这些规划输入自行刷新状态。

## 工作流

1. **路由请求。** 判定是 new implementation 还是 patch/follow-up。只要已有
   slug 明确拥有该 feature、issue 或模块改动就复用它；通过语义搜索
   implementation 目录、plan/spec 文件名、issue ID、feature 名和涉及模块来
   找到它。两个候选 slug 都合理时，先问一个简短问题，不要另建 workspace。
   patch/follow-up 路由在动笔前先读 [patching.md](./patching.md)。
   完成标准：routing 和 slug 已确定。

2. **按语义发现上下文，不依赖固定目录名。** 收集：来源需求、issue、handoff
   或讨论；长期 PRD/产品文档；架构、ADR、数据契约文档；已有 feature/模块
   设计；测试与验证文档；已有 implementation workspace（含 slug 内
   `design.md`、既往 plan、handoff）；以及用于校验或纠正文档的 focused code
   facts。目录缺失只是线索缺失，不是阻塞。完成标准：能说清功能合同和它触及
   的代码面。

3. **写或更新 `spec.md`**，使用
   [assets/templates/spec.md](./assets/templates/spec.md)（slug 已有兼容
   spec 时沿用原结构）。功能语义放进 `spec.md`；实现步骤不进 spec。
   完成标准：实现者不读 plan 也能复述要构建什么。

4. **决定 plan 颗粒度并记录**在 plan 头部的 `Granularity:` 行。默认：
   **repo-local executable checklist**。仅当改动很小且边界清晰——通常 1-2 个
   文件、测试明确、且完整代码片段确实能降低歧义——才回退到 superpowers 风格
   的 micro-step + 完整代码片段，并记录回退原因。

5. **读 `superpowers:writing-plans` 的 SKILL.md**（可用时），在写 plan 之前。
   只取它的质量标准：具体性、精确命令、预期结果、清除占位符。不采用它的输出
   路径（`docs/superpowers/plans/...`）和默认 micro-step 格式——颗粒度由第 4
   步决定，输出路径由本 skill 决定。

6. **写 plan**，使用
   [assets/templates/plan.md](./assets/templates/plan.md)：新实现写
   `plan.md`；patch 在 slug 根目录新建
   `YYYYMMDD-HHMM-<patch-topic>.patch-plan.md`（绝不覆盖 `plan.md`）。填入
   input packet（当前 spec、稳定文档、既有实现上下文、code facts、验证文档）、
   精确文件清单、带命令和预期结果的 checklist 任务、验收 gate、回滚说明。
   不留占位符，不写"加个校验"这类模糊步骤。

7. **成对审查。** 环境允许时用 review subagent 执行下方审查清单；否则内联
   执行，并在总结中说明用的哪种方式。应用修正，使正式文档可独立成立。

8. **返回输出契约。**

## 审查清单

- 选定 slug 内的 `spec.md` 已创建或更新；plan 实现的是当前 spec 合同。
- 新实现有 `plan.md`；patch 在 slug 根目录有新的带日期 patch plan，且复用了
  owning slug。
- 功能语义在 `spec.md` 中，而不是只藏在 plan 里。
- 颗粒度决策已记录；micro-step 风格仅用于非常小、边界清晰的任务。
- 验证命令具体、限定在本次改动范围内、写明预期结果。
- 提议的 tracking task ID 从 slug 内已有最高 `T<number>` 继续编号。
- 长期文档只被引用，未被修改。
- 待定 owner 决策明确列出，与实现步骤分离。

## 输出契约

返回：

- 选定的 slug 和 routing（new implementation 或 patch/follow-up）
- 创建或修改的文件
- 颗粒度决策
- 审查方式与所做修正
- 剩余 owner 决策
- plan 是否已可进入实现
