---
name: subagent-driven-development
description: 当用户要求使用 subagent、异步或并行方式调研、实现、修复或验证，或已派发的 bounded Topic 需要指导下游 worker 时使用；以 Topic-first baby step 作为授权边界，并定义 dependency、execution lane 与 lifecycle。
---

# Subagent-Driven Development

Topic 是共享 foundation、ownership 与 closure point 的横向交付范围，用来判断当前动作边界和 worker 复用；它不是 lane、持久队列或一次派发的尺寸。本 Skill 是下游 bounded worker 的完整方法定义。它与 `$dispatcher` 平级：Dispatcher 先做 Topic-first admission 与批次调度，SDD 指导已派发 Topic 内的 dependency、mode、execution lane 与 lifecycle。

业务需求、Ticket/State/Evidence/Gate 仍由调用方及其 owning skill 决定；executor、model、provider 或 agent profile 由 Owner 选择或宿主原生能力解析。起草 `investigate`/`implement`/`fix` 的派发 prompt 时读取 [worker-briefs.md](references/worker-briefs.md)。worker 的验收目标是一个动作的答案，不是需求的 AC，也不是 Ticket 的终态；AC 与 Ticket 粒度归 impl-planning，运行状态与验收判断归 dev-with-track。同一个动作可以服务任何 Ticket，也可以不服务任何 Ticket。

每个当前 baby step 可以使用当前 worktree，也可以使用新隔离 worktree；caller 按该 step 的实际 effect footprint（实际写入集与运行资源）决定选择、创建和生命周期。资源冲突按 baby step 的实际写入集与运行资源判断，不按 Topic 或 Ticket 的整体写集判断；两个 Topic 整体有交叉不等于当前两步冲突。文件 ownership 不冲突时可以共用当前 worktree；存在交叉但能通过新隔离 worktree 分开时继续 fan out。DB、端口、测试数据和外部记录分别验证隔离，独立 worktree 只解决文件写入边界；无法隔离的共享可变资源才要求串行。

## Topic first, baby step second

caller 先形成 Topic，再沿一条 lane 授权该 Topic 当前一个 baby step，明确 ownership、write-set、禁改范围、前置依赖、成功条件和 focused verification。该授权逐 Topic 生效；同一批次可以并行释放多个不同 Topic 的已解锁 baby step。

一个 baby step 包含为同一结果服务的局部调查、RED→GREEN、实现、focused test、lint/format、普通重跑和当前动作产生的机械 cleanup；这些机械附属不单独派发。只有调查结果会改变实现方向、write-set、dependency、授权、资源 admission、是否继续当前 Topic，或立即释放另一条 Topic 时，才单独派发 `investigate`。拥有独立环境、资源、授权或 acceptance 判决的验证仍单独派发。

错误 cwd、缺少本地依赖、format 或普通测试载体故障在原边界仍可信时属于当前动作 recovery，沿同一 worker 续接，不创建新业务 step。只有边界无法完成或上述决策发生变化时才返回 `INCOMPLETE` 给主控重排。

worker 尚未返回时，普通实现至少观察 15 分钟，shared seam 调研至少观察 30 分钟；宿主可提供 PID 时结合 PID 活动判断。caller 可以询问进度或继续不依赖结果的 look-ahead，但不能仅因等待时间较长就中断、重复实现或重新派发；判断是否异常只看有没有可观察的活跃信号——运行中的进程/命令、正在产生的工具调用、有输出变化，持续没有任何这类信号时才用可用的状态查询确认并考虑 interrupt。

worker 返回后，caller 消费已有 evidence、diff 和验证结果，再决定是否沿同一 work lane 释放下一个 baby step。后续步骤不会因为属于同一 Topic 而自动获得授权。

## Step 1 · 定义 Topic

先定义 Topic 的 foundation、ownership、closure point 与生命周期，再选择当前唯一 baby step。固定该动作的 bounded outcome、write-set、禁改范围、前置证据、成功条件与答案形态；comparison point 归 review lane，由 do-review 固定。只有通过 Dispatcher 的 Topic-first 门槛后，才选择本次 worker mode 并派发。上一步轻量 delta review 的已确认 findings 随下一个 baby step 的 brief 一并下发，默认在该步一起修复。

常见误判既包括把整个 Ticket 交给一个 worker，也包括把同一 coherent outcome 的每个测试、格式化和机械修复都重新派发。前者缺少边界，后者制造调度开销；都应回到 Topic 的当前决策点。

| mode | 适用工作 | 必须保留的边界 |
| --- | --- | --- |
| `investigate` | 证据不足，需要确认 cause、boundary 与最小下一项取证 | 答案为 `EVIDENCE_SUFFICIENT` 或 `EVIDENCE_GAP`；不释放授权、acceptance 或 Gate |
| `implement` | 已有唯一业务裁决，需要产生实现或可验证产物 | 答案为 `diff`；只承担当前 Topic 的 ownership 与局部验证 |
| `fix` | finding 已确认且已边界化 | 答案为 `diff`；不重新裁决 finding、不扩大范围、不宣称 closure |
| `verify` | 执行既定、无写副作用的检查 | 答案为判定；会重写 snapshot/generated file 的动作转入 `implement` 或 `fix` |

`fix` 不阻塞后续开发，「等这个 fix 修完」不是暂停主线的理由：同 Topic 复用原 lane 与原 worktree；与当前开发不同 Topic 且写入交叉较小时，默认在隔离 worktree 并行进行，修好后合入。

完成标准：当前派发只有一个已解锁 baby step，答案形态、write-set、局部验证与前置依赖均明确；既未预先授权后续决策，也未拆出边界内的机械动作。当前派发不跨越第二个主控 return point。

## Step 2 · 分类 dependency

| dependency | 阻止的动作 | 仍可提前进行 |
| --- | --- | --- |
| foundation dependency | 会绑定未稳定语义、数据形状或材料 seam 的下游实现 | 与结果无关且资源隔离的准备 |
| acceptance dependency | 正式验收、evidence 采信和状态宣称 | 合同与实际前置已满足、资源可协调的实现或准备 |
| resource dependency | 对同一可变资源的同时执行 | 隔离 worktree 上的小 fix 或其他工作 |
| authorization dependency | 未获授权的 mutation 或外部副作用 | 只读调查和不越权准备 |

Acceptance 是结论点，不天然是 dispatch blocker。等待 worker、review、长时验证或 Gate 时，按实际前置、授权与资源复核其他动作，可继续已满足条件的独立实现。`look-ahead` 准备仍限于不绑定未稳定业务语义、结果可回收且有 cleanup owner 的工作。

完成标准：当前不可开始、只不可验收和可提前实施或准备的工作已经分开。

## Step 3 · 形成当前批次

优先稳定 foundation；消费 Dispatcher 形成的当前批次，对每个 Topic 只执行已授权的 baby step。安全的一步前瞻准备仍需独立 admission，不能借“准备”名义预派下游实现。存在多个候选、文件 ownership 交叉、共享 DB/端口/测试数据或外部记录时，完整读取 [Dependency and Resource Admission](references/parallel-work-admission.md)。

完成标准：所有已解锁的合格动作都已进入当前批次，或有明确 dependency/资源理由保持串行；任何两个并行 worker 都没有同一可变资源的 ownership，不能隔离的资源已有串行顺序和 cleanup owner。

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

主 session 核对可归因 diff、evidence、residue 和 cleanup；worker 自证（focused tests、lint、diff check）通过后，先把当前 baby step 判定为 DONE/BLOCKED/INCOMPLETE，再冻结这次 dispatch-to-return 的增量（固定 diff 或直接 commit）作为轻量 delta review 的确定输入，并同时为每个 baby step 使用 fresh reviewer 启动轻量 delta review、显式释放下一个 baby step，不等 review 返回。当前返回不会自动授权下一步；轻量 delta review 不产生 review requirement、不改 Ticket/evidence 状态、不作为主线等待条件。
独立 formal review 的判断点是 shared seam、完整 source unit 或集成边界，由主 session 判断是否已到达；只有到达该点才产生 review requirement。只归一化真正有消费者的事实：

- worker outcome：`DONE | BLOCKED | INCOMPLETE`；
- investigation：`EVIDENCE_SUFFICIENT | EVIDENCE_GAP`；
- required review（已到达 review 点）：`PENDING_REVIEW | PASSED`，具体 topology 与 finding closure 由 `/impl-package:do-review` 拥有。

主 session 将局部 `DONE`、review `PASSED` 和测试结果作为 Topic-local facts，依据 canonical evidence、Ticket acceptance 与 Gate 作业务完成判断，并始终拥有最终集成与证据采信。

worker return 使原 Topic 边界不再可信时，主 session 返回可归因的 boundary facts，由 Dispatcher 的反抖动规则决定是否先重查 foundation；SDD 不另建一套重排条件。

完成当前批次集成后重新扫描 foundation 与一步前瞻准备，再由上游 Dispatcher 决定下一轮 dispatch/idle。

完成标准：当前结果有可归因的 Topic-local 结论，业务完成判断来自 canonical facts，并已执行一次 `look-ahead`。

## 示例

同一 Topic 的 implementer 返回一个已确认 finding，且 write ownership 未变、上下文可信。
caller 将修复该 finding 定为下一个 baby step，并选择 `mode=fix`。
caller 沿同一 work lane 派发 fixer，复用现有 Topic context。
派发内容只带该 finding 及其已定边界，fixer 不重新裁决 finding。
回收 diff、evidence 和 focused verification 后，主 session 把结果作为 Topic-local fact 消费。
Topic closure 前继续逐步授权；Topic closure 后退役该 worker。
