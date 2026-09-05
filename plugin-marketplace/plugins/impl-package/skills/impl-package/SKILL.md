---
name: impl-package
description: Impl-Package 体系的入口地图与路由：判断从需求对齐、计划、Ticket/DAG、执行、验证、进度监控或稳定文档回刷的哪个阶段进入；并承载交互质询（grilling）与旧 DAG 只读审计的入口判断。只导航，不代替阶段 skill 执行。
---

# Impl-Package

Impl-Package 把一次变更组织为可裁剪的链路：Decision/Spec contract ensemble → Plan → 可选 Ticket → execution state → verification → Gate → stable-doc backfill；DAG/Task 只为旧 package 的恢复与迁移保留。

## 核心原则

- 只保存会改变下一动作、阻止 false PASS 或约束危险 mutation 的状态；D/S/P 只作为可选的人类可读别名，不是新 package 的必填字段，也不绑定文件内容。
- 只有 Git commit ID 可作为版本/比较点；外部文件和 evidence 一律使用仓库相对 POSIX 路径，拒绝绝对路径和 `..`；已知 artifact 使用固定目录或显式路径，不保存扫描结果副本。
- Git 负责历史审计；现役格式不维护 contract/schema 版本、迁移账本或兼容层。正式规则见 [Composition Contract](../../references/impl-package-composition-contract.md) 与 [Current State](../../references/impl-package-current-state.md)。
- 机械操作一律走现有语义 CLI：状态、Ticket、evidence、Gate 和 trail 的写入由 `../../scripts/impl_package_state.py` 及其 runtime command groups 校验；关键 trail 字段使用具名参数和 `--help` 可见的 `choices`。状态变更后 CLI 可追加当前处境 footer，处境协议由 `../../scripts/situation.py`/宿主注入提供导航，不复制成第二套持久规则。
- Codex-only 的 state guard、session activation 与 Resume Capsule 见 [Codex Hooks](../../references/codex-hooks.md)；Hook 只提供事实和防绕过，不拥有业务状态或 Gate。

## 入口：阶段命令

路由统一使用 `/plugin:skill` 调用形式；下表同时保留宿主 native command index（`impl-*`）与跨宿主路由。宿主内部 registry/discovery 显示的无 `/` skill key 不是第二种文档写法。

| native entry | 跨宿主 route | 用途 |
| --- | --- | --- |
| `impl-req-align` | `/impl-package:req-align` | 需求/Decision/Spec 对齐 |
| `impl-grill-me-smartly` | `/impl-package:grill-me-smartly` | 高风险 Spec gate 的 ledger 审问 |
| `impl-grilling` | `/impl-package:grilling` | 对 plan、Decision 或 idea 做交互式深入质询 |
| `impl-impl-planning` | `/impl-package:impl-planning` | 创建 initial/patch plan、决定 Composition |
| `impl-plan-review` | `/impl-package:plan-review` | 审查 plan 或完整 Plan/Ticket/DAG bundle |
| `impl-to-tickets` | `/impl-package:impl-planning` 的 Ticket-split | 创建独立验收切片 |
| `impl-execution-boundaries` | `/impl-package:execution-boundaries` | 执行前授权、异步状态记账与异常对账、完成前 evidence gate |
| `impl-subagent-driven-development` | `/impl-package:subagent-driven-development` | 下游 bounded worker 的 Topic、dependency、mode、lane、lifecycle 与 review requirement |
| `impl-dev-with-track` | `/impl-package:dev-with-track` | 恢复执行、选择业务动作、消费 Dispatcher/SDD 结果、推进 Ticket 与写 Gate |
| `impl-monitor-progress` | `/impl-package:monitor-progress` | 打开实时进度页面，并可选创建只读主控监控 automation |
| `impl-do-review` | `/impl-package:do-review` | 多 reviewer 编排、fail-closed 聚合 findings 并判断收敛 |
| `impl-review-code` | `/impl-package:review-code` | 审查实现正确性与可维护性 |
| `impl-review-code-by-standards` | `/impl-package:review-code-by-standards` | 按规范、interface、depth、locality 审查 |
| `impl-review-code-by-spec` | `/impl-package:review-code-by-spec` | 按需求、Spec、Plan 审查实现忠实度 |
| `impl-safety-review` | `/impl-package:safety-review` | 审查安全、数据完整性、并发和外部副作用 |
| `impl-backfill-stable-docs` | `/impl-package:backfill-stable-docs` | 回刷稳定知识或退休 package |

仅询问体系时停在本页；用户已明确阶段和动作时直达对应 skill。执行前、异常 slow path 和 completion claim 不再分派到已合并的 standalone 名称，统一进入 `execution-boundaries`；旧 Task/DAG 也只由下面的 legacy 章节承接，不创建新的独立入口。

## 最小 package

```text
<package>/
  decision.md            # 可选；轻量 Decision 也可在 spec.md
  spec.md
  contract-design.md     # 从属 spec.md；detailed | not-required
  plan.md
  tickets/               # Ticket-only Composition earned 时
  progress.md             # active Attempt 的 machine-owned 恢复投影
  execution/
    <attempt>/
      execution-record.md
      task-handoffs/      # 仅旧 Task package 实际发生 handoff 时创建
  .impl-package/state.json
  gate.md                 # 首次 gate evaluation 时创建
```

新 package 统一使用 `tickets=true, dag=false` Ticket-only 合同；阶段 A 的 `dag=false` 是 3.4 兼容占位，不表示创建 Task/DAG；`dag=true` 只读旧 package。不要为审计完整感增加 artifact。每个新建或被修订的 Spec 都有从属 `contract-design.md`；默认 `Disposition: detailed`，精确语义已由 `spec.md` 完整承担时使用 `Disposition: not-required` 并写明理由。未触及的 legacy Spec 到下次 req-align 再补齐；该文件没有独立 alias、revision、状态、审批或生命周期。

## 交互质询（grilling）

1. **按材料成熟度定焦**：Grilling 是通过设计树 rounds 对 plan、Decision 或 idea 做深入质询；只导航与组织，不代替用户作产品决策。材料薄时广泛探索替代方向、隐藏假设、具体例子和下游后果；材料成熟后聚焦已选方向、内部一致性、未决选择和 material risk；证据暴露真实缺口或用户要求时才重开选项空间。
   - 常见误判：把成熟材料继续当成空白创意会无止境重开方向，把薄材料过早收窄又会把隐藏假设带进后续决策。

2. **建立完整 frontier**：每轮先列前置条件已 settled、当前无需猜答案的所有问题；frontier 无硬或默认大小，可读则一批提出，过大则连续分批，说明总 frontier、当前 batch 覆盖范围，并以稳定 ID 保留所有 material decision。每批回复后重新校验剩余 frontier，仍 material 的项目继续携带，新解锁分支进入后续 round。frontier 是完整性边界，不是问题配额，不得为控制长度遗漏、合并或静默延期 material 分支。
   - 常见误判：把 frontier 当问题配额会为了控制回复长度静默漏掉、合并或延期 material branch。

3. **让每个问题可被决定**：每题编号、给 recommended answer，等用户整批回复后再继续；并给足当前决策所需的 why-now、具体场景/边界/失败例、真正不同的选项、推荐及依据，以及对成本、风险、恢复、下游行为或兼容性的影响；不制造没有真实差异的选项。题面可采用：

  ```text
  ❓ Q1 - <question title>: <question body>
  ➡️ <your recommended answer>
  ```

   - 常见误判：只给选项而不给失败边界或推荐依据，用户会在没有共同语境的情况下被迫猜测 trade-off。

4. **分离事实查找与决策**：环境、文件、工具可解决的事实由 agent 自己查，可派 subagent 且不阻塞其余 frontier；决策属于用户。
   - 常见误判：把本地可查事实问回用户，或让 agent 替用户选择，会把事实缺口和产品偏好混成同一种输入。

5. **按回合收敛**：每轮末给回复合同，例如“全部采纳”“除 Q3 外全部采纳”“Q2 选 B；Q4 按推荐”“展开 Q1”；每轮回答后继续推进仍 material 的 frontier。
   - 常见误判：没有回复合同或把一次回答当成终点，用户无法稳定引用问题，后续分支也会被漏掉。

6. **处理冲突再决定是否重开**：新回答若与已确认方向冲突或暴露原则缺口，说明具体 trade-off 后让用户决定是否重开。
   - 常见误判：冲突出现时静默覆盖旧方向，或把任何小差异都当成必须重开，会同时破坏已确认选择和收敛速度。

7. **只在 frontier 清空后停止**：当 frontier 为空、所有 material branch 已访问且没有静默假设时才停止；未达共同理解前不执行设计树结论。细节与 rubric 按需读 `../grilling/rubric.md`；实际 ledger、Questioner/Answerer/Apply 生命周期由 `/impl-package:grill-me-smartly` 承接。
   - 常见误判：看到一个局部方向已收敛就执行结论，会把未访问分支变成不可见的产品承诺。

### Durable document 约束

1. **以成熟度组织 durable review**：对 PRD、plan、Decision、Spec 或 MVP slice，以文档成熟度为重心，必要时从现有证据起草最小缺失上下文并标明假设。
   - 常见误判：没有上下文就让用户从空白重写，或把假设写成已确认事实，都会遮住真正需要决定的缺口。
2. **review 中保持目标文档不变**：不编辑目标文档，先在工作记忆或用户已有 notes 记录 accepted choices、non-goals、deferrals、open items，并用稳定 ID。
   - 常见误判：中途写回会让未收敛的 working choice 看起来已经是 durable contract。
3. **收敛后按授权写回**：收敛后给 consolidated decision summary；只有调用已授权或用户明确确认才写回，并把被替代的意义分类为保留、迁移到命名承接者、被已接受决策替代或用户弃用，不能因为新文更短而静默丢掉 product commitment。
   - 常见误判：只保留新文短版本会静默丢失 product commitment，或把被迁移的意义误报为删除。
4. **写回后报告边界**：写回后简报改动文档、吸收的 decision groups、未决/延期项和有意未运行的阶段（gate、release、implementation 等）。
   - 常见误判：不报告未运行阶段，用户会把文档写回误解成 gate、实现或 release 已完成。

## Legacy（旧 Task/DAG，只读）

新 package 一律不创建 Task DAG，不调用 `create-task-dag`；仅在 owner 明确授权恢复/迁移已有 3.4 package、且 artifact 已存在时读取 `dag.md` 或 `<attempt-id>.patch-dag.md`。先读取 current plan；有 Tickets 时同时读取 `tickets/` 的直接 Markdown 子文件。

1. **先读当前 package 事实**：先读取 current plan；有 Tickets 时同时读取 `tickets/` 的直接 Markdown 子文件。
   - 常见误判：跳过 current plan 直接看旧 DAG，会把已经被新 Composition 替代的依赖当成现行要求。
2. **审计 Task 的核心关系**：只审计已有 Task 的 primary ownership、确定依赖、贡献 Ticket、已知 seam/risk 和 section-level contract references。
   - 常见误判：把 Task 数量或 handoff 数量当成完整性证明，会漏掉真正的 ownership、依赖和 seam 风险。
3. **把真实产物映射回 Ticket**：迁移时把 Task 的真实产物映射回 Ticket claim，不把 Task handoff 或 `DONE` 当 acceptance proof。
   - 常见误判：把局部 Task `DONE` 当 Ticket 已满足，会把可集成产物误报成 acceptance proof。
4. **限定 contract reference**：Contract reference 使用仓库相对路径定位到 Decision/Spec/contract-design/Plan 的具体一级或二级章节，不裸指整份文档或使用行号，只保留 Task 执行所需章节，不复制合同正文。
   - 常见误判：裸指整份合同或复制正文会让迁移后的引用失去可定位的 authority 边界。
5. **拒绝预列和新 DAG 扩张**：不预列所有文件、consumer、失败模式或 Phase/epic/子任务层；发现新 DAG 需求时回到 `impl-planning`，不在本入口创建。
   - 常见误判：为了“审计完整”预建一棵新 DAG，会把只读恢复入口变成新的任务系统。
6. **联合检查 Gate 可行性**：与 plan/Ticket 做只读联合检查：coverage、typed dependency、cycle、ownership、contribution mapping、section-level refs、evidence feasibility、integration order 和 Gate 边界。
   - 常见误判：只核单个 Task 会错过跨 Ticket 的 cycle、证据不可行或 integration order 问题。
7. **保留现行状态语义**：Task 状态只保存在 `.impl-package/state.json`；Task `DONE` 表示局部产出可集成，不表示 Ticket `SATISFIED`。P 变化时只把实际受影响 Task 设为 `NEEDS-REVALIDATION`。
   - 常见误判：另建状态轴或把所有 Task 重验，会破坏 state.json 的唯一状态 authority 和受影响范围。
8. **按旧 package 规则恢复运行时投影**：初始化后 DAG Runtime State 表由 `refresh-progress` 维护；只有 dependency 已释放的 Task 才能进入 `READY/RUNNING`，未知 dependency 和 cycle 必须在发布前阻断。旧 package 的细节按需读 `../create-task-dag/references/` 下的 `dag-and-ownership`、`worker-prompts`、`review-and-verification`、`slice-to-dag`。
   - 常见误判：在 dependency 未释放或 cycle 未阻断时发布，会让恢复后的 READY/RUNNING 状态失去可解释性。
