---
name: subagent-driven-development
description: 当 bounded Topic 内当前一个 baby step 需要指导下游 worker 调查、实现、修复或验证时使用；以二元完成作为派发门槛，并定义 dependency、lane 与 lifecycle。
---

# Subagent-Driven Development

Topic 标识一组共享上下文的连续动作，用来判断能不能复用同一个 worker；它不是派发单元。本 Skill 是下游 bounded worker 的完整方法定义。它与 `$dispatcher` 平级：Dispatcher 与 SDD 分别直接指导上游主控调度和已派发 Topic 内的工作方法，共享 dependency、资源与生命周期原则。

业务需求、Ticket/State/Evidence/Gate 仍由调用方及其 owning skill 决定；executor、model、provider 或 agent profile 由 Owner 选择或宿主原生能力解析。worker 的验收目标是一个动作的答案，不是需求的 AC，也不是 Ticket 的终态；AC 与 Ticket 粒度归 impl-planning，运行状态与验收判断归 dev-with-track。同一个动作可以服务任何 Ticket，也可以不服务任何 Ticket。

每个 bounded Topic 可以使用当前 worktree，也可以使用新隔离 worktree；caller 根据 write ownership 与资源交叉决定选择、创建和生命周期。文件 ownership 能通过新隔离 worktree 分开时继续派发；DB、端口、测试数据和外部记录分别验证隔离，独立 worktree 只解决文件写入边界。

## Baby step first

**Topic 是上下文与 lifecycle 容器，不是派发单元。** caller 每次只派发 Topic 内当前一个 baby step；worker 返回后由 caller 消费结果，再决定是否沿同一 work lane 释放下一步。后续步骤不能因为属于同一 Topic 就被一次性预授权。

动作只有在结果可二元判定、前置依赖与 ownership 已明确且能 focused verify 时才可派发；否则继续切分，只派第一个已解锁动作。

## Step 1 · 定义 Topic

先定义 Topic 的共享上下文、ownership 与生命周期，再从中切出当前唯一 baby step。固定该动作的 bounded outcome、write-set、禁改范围、前置证据、成功条件与答案形态；comparison point 归 review lane，由 do-review 固定。只有通过上方 Baby step first 门槛后，才选择本次 worker mode 并派发。

常见误判：把一个交付切片或验收目标整包派给一个 worker，会得到没有单一答案的运行，主 session 只能等和猜；派发前未答清动作依赖，会让 worker 停下来返回，这是 worker 的正确行为，问题在派发方。

| mode | 适用工作 | 必须保留的边界 |
| --- | --- | --- |
| `investigate` | 证据不足，需要确认 cause、boundary 与最小下一项取证 | 答案为 `EVIDENCE_SUFFICIENT` 或 `EVIDENCE_GAP`；不释放授权、acceptance 或 Gate |
| `implement` | 已有唯一业务裁决，需要产生实现或可验证产物 | 答案为 `diff`；只承担当前 Topic 的 ownership 与局部验证 |
| `fix` | finding 已确认且已边界化 | 答案为 `diff`；不重新裁决 finding、不扩大范围、不宣称 closure |
| `verify` | 执行既定、无写副作用的检查 | 答案为判定；会重写 snapshot/generated file 的动作转入 `implement` 或 `fix` |

完成标准：当前派发只有一个已解锁动作，答案形态、write-set、局部验证与前置依赖均明确；未把同一 Topic 的后续动作预先塞入本次授权。

## Step 2 · 分类 dependency

| dependency | 阻止的动作 | 仍可提前进行 |
| --- | --- | --- |
| foundation dependency | 会绑定未稳定语义、数据形状或材料 seam 的下游实现 | 与结果无关且资源隔离的准备 |
| acceptance dependency | 正式验收、evidence 采信和状态宣称 | 环境、fixture、权限、身份、数据与 test carrier 准备 |
| resource dependency | 对同一可变资源的同时执行 | 可隔离副本上的工作 |
| authorization dependency | 未获授权的 mutation 或外部副作用 | 只读调查和不越权准备 |

Acceptance 是结论点，不天然是 dispatch blocker。等待 worker 或 Gate 时做一次 `look-ahead`，只提前加入不绑定未稳定业务语义、结果可回收且有 cleanup owner 的一步准备。

完成标准：当前不可开始、只不可验收和可提前准备的工作已经分开。

## Step 3 · 形成当前批次

优先稳定 foundation；当前批次只收纳分别通过 Baby step first 门槛的动作。安全的一步前瞻准备也必须是独立 baby step，不能借“准备”名义预派下游实现。存在多个候选、文件 ownership 交叉、共享 DB/端口/测试数据或外部记录时，完整读取 [Dependency and Resource Admission](references/parallel-work-admission.md)。

完成标准：任何两个并行 worker 都没有同一可变资源的 ownership；不能隔离的资源已有串行顺序和 cleanup owner。

## Step 4 · 选择 lane 与 lifecycle

| lane | lane 上依次出现的动作 | 独立性 | 退役或换 worker 的条件 |
| --- | --- | --- | --- |
| work lane | investigate → implement → fix | 拥有该 Topic 的实现上下文与 write ownership | Topic closure、scope/ownership 实质变化、上下文不可采信或持续卡住 |
| review lane | initial review → finding recheck | 始终独立于 work lane；同 Topic reviewer 可以复用 | Topic closure、review scope 实质变化或独立性失效 |
| test lane | 同一有界 test campaign 的运行、重跑与异常收集 | 不承担业务裁决或修复 | campaign 结束、环境/comparison point 变化或结果已交付 |

新 Topic 使用 fresh worker；同一 Topic/lane 连续且上下文可信时复用。

material-risk Topic（shared seam、安全、数据完整性、并发、migration、权限或不可逆外部副作用）读取 [Material Review Gate](references/review-gate.md)。

完成标准：每个 active worker 都能对应唯一 Topic/lane，且 review lane 与 work lane 保持独立。

## Step 5 · 消费结果并重排

主 session 核对可归因 diff、evidence、residue 和 cleanup；worker 自证（focused tests、lint、diff check）通过后，先把当前 baby step 判定为 DONE/BLOCKED/INCOMPLETE，再决定是否通过 follow-up 复用原 worker 执行同一 Topic 的下一个 baby step。当前返回不会自动授权下一步；review 只在到达 review 点后安排。
独立 review 的判断点是 shared seam、完整 source unit 或集成边界，由主 session 判断是否已到达；review requirement 只在到达该点后产生。只归一化真正有消费者的事实：

- worker outcome：`DONE | BLOCKED | INCOMPLETE`；
- investigation：`EVIDENCE_SUFFICIENT | EVIDENCE_GAP`；
- required review（已到达 review 点）：`PENDING_REVIEW | PASSED`，具体 topology 与 finding closure 由 `/impl-package:do-review` 拥有。

主 session 将局部 `DONE`、review `PASSED` 和测试结果作为 Topic-local facts，依据 canonical evidence、Ticket acceptance 与 Gate 作业务完成判断，并始终拥有最终集成与证据采信。

完成集成后重新扫描 foundation 与一步前瞻准备，再由上游 Dispatcher 决定下一轮 queue/dispatch/idle。

完成标准：当前结果有可归因的 Topic-local 结论，业务完成判断来自 canonical facts，并已执行一次 `look-ahead`。
