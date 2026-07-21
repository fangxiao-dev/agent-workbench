# 问题解析：为什么已有计划仍产生多轮返工

## 结论

这次执行时间偏长，不能简单归因于“Owner 没有手动 review 最初计划”，也不能概括成执行者一直边做边错。更准确的结论是：原计划已经覆盖了主要业务风险和验收方向，但没有把关键工程约束转化成逐项、前置、可证明的 implementation gate；实施中同时存在合同歧义、计划到代码的翻译缺口、测试设施设计过晚，以及若干纯实现错误。最终 review loop 因此承担了本应在实施前和各 seam 集成时完成的设计澄清。

Owner 手动 review 可能发现产品行为不符合预期，但不应被要求主动识别 CAS、TOCTOU、provider readback predicate、fault injection 等工程细节。防范责任主要属于工程计划审查和执行前置机制：它们应把 Owner 已批准的意图转换为可验证的状态机、写权限和失败恢复合同，并把真正需要 Owner 决策的歧义明确上抛。

## 已有计划做对了什么

P4 计划不是空泛任务列表。它已经识别并写入 Application Revision、Customer-scoped renewable lock、operation journal、Lexware-first mutation、provider readback、guarded Lark commit、partial-success recovery、archived binding、stale dialog、fault matrix、浏览器验收和 no-real-mutation 等核心风险。后续问题并不证明计划方向错误，而是说明这些正确方向大多停留在“要做什么”，没有完全达到“代码必须怎样证明自己正确”。

## 四类根因

### 1. 合同中存在真实歧义

计划要求 generic `ensureLexwareContact` 在无 persisted Contact ID 时禁止自动 create/adopt，同时又要求保留“Lieferschein 和既有 linked mirror sync”，且 S4 说明后续同步只使用已绑定 ID。实施由此把 generic bound PUT 理解为可继续执行；后续 review 又要求 generic flow 不得拥有 bound PUT，所有差异必须进入 explicit resolution。两种解释都能从计划文本找到依据，因此这不是单纯的“没有照计划做”，而是 mutation authority 没有被写成穷举矩阵。

实施前应明确如下决策面：

| Flow | GET | POST | PUT | Mutation authority |
| --- | --- | --- | --- | --- |
| Explicit create | 是 | 是 | 否 | Resolution Operation |
| Explicit overwrite | 是 | 否 | 是 | Resolution Operation |
| Generic unbound Retry | 是 | 否 | 否 | 只读 handoff |
| Generic bound sync | 是 | 否 | 必须显式决定 | 这是原计划的歧义点 |
| Reconciler | 是 | 否 | 否 | 仅补齐 journal/approval/notification evidence |
| Lieferschein bound check | 是 | 否 | 否 | 只认可 persistent binding |

如果该矩阵在实施前存在，“generic bound sync 是否可 PUT”会成为单一 Owner/architecture decision，而不会在第七轮 review 才反转实现方向。

### 2. 计划中的状态机没有变成写协议

S4 和计划列出了 `intent_recorded -> provider_call_started -> provider_succeeded -> checkpoint_pending -> approved -> notified` 等状态，并明确 ordinary retry 不得重放 provider mutation，但没有为每条 transition 指定合法前置状态、CAS 条件、冲突后的 reread/classification、禁止降级规则、latest pointer 更新语义，以及 operation body 与 latest pointer 是否原子。

这使实现可以“拥有状态枚举”却仍允许 stale writer 覆盖新状态，或由 Redis latest pointer 的读后写产生 TOCTOU 回退。需要的不是再增加一句“保证幂等”，而是一张 transition/CAS 表和硬性不变量，例如：所有 state change 必须走 `updateIfState`；普通 patch API 不得写 `state`；terminal 或更高序状态不能被旧 writer 降级；latest pointer 更新必须具备单调比较和原子提交语义。

### 3. 正确性谓词和失败边界不够可执行

计划写了 provider readback、target fingerprint 和 evidence，但没有定义“成功”的精确谓词：响应 ID 与 readback ID 是否必须相同；company/person、business email、phone、billing/shipping 是否必须逐项一致；目标值只出现在 private/extra collection 是否算成功；多余 customer-owned values 是否应使比较失败。结果是 matcher 和 readback 都可能对非精确目标产生 false positive。

同样，计划写了“通知失败不回滚审批”，但没有把通知拆成 journal prepare failure、provider factory/render failure、provider 未尝试、dispatch outcome unknown、message ID 已返回、message ID 已持久化但 final state 未更新等子状态。后续才补出的 typed provider-not-attempted classification 和 attempt timestamp，本应在计划阶段就成为失败矩阵的一部分。

### 4. 测试目标存在，但 fixture 和 fault injection 设计过晚

计划已经列出 stale、partial-success、provider-success-before-evidence crash 和浏览器验收，却没有在实施前固定每个场景的 fixture、注入点、provider call count 和 UI 持久化断言。执行中出现了三个典型信号：stale fixture 通过改变 review status 走到了 not-ready，而非真正的 revision-stale 分支；复用 local in-memory stores 污染了 partial-success 场景；warning 是否跨 route refresh 保留没有成为明确断言。它们表明测试并非单纯“最后忘记补”，而是可测架构和隔离设施没有前置设计。

## 后期 review 暴露的问题分类

| 后期 blocker | 主要性质 | Plan Eng Review 提前发现概率 | 仍需 implementation review |
| --- | --- | --- | --- |
| operation transition 非单调 CAS | 计划到写协议翻译缺口 | 高，前提是强制状态图/CAS 表 | 是 |
| Redis latest pointer TOCTOU 回退 | 并发实现细节 | 中，data-flow review 可提出原子性 gate | 是，必须看代码 |
| provider readback 未证明 exact target/ID | 正确性谓词缺失 | 高 | 是 |
| reconciliation matcher false positive | predicate/collection 语义缺失 | 高 | 是 |
| generic bound PUT authority 错位 | 真实合同歧义 | 很高 | 是 |
| notification pre-provider classification 不完整 | 失败状态模型缺失 | 高 | 是 |
| lock 内未重验 profile eligibility | 竞争窗口遗漏 | 中到高，data-flow tracing 可发现 | 是 |
| registry/archive verification parity 缺失 | 验证索引收尾缺口 | 中 | 是 |
| Browser acceptance 缺 stale/partial-success | 测试图不具体 | 很高 | 是 |
| AC-8 crash-boundary injection 缺失 | fault injection 未产品化 | 很高 | 是 |

因此，`plan-eng-review` 有望显著减少后期返工，尤其是 authority、transition、readback、notification 和 E2E fault path；但它不能替代代码审查。TOCTOU、错误 API 使用、漏掉 lock 内重验等问题，最终仍必须通过 implementation/seam review 和并发测试发现。

## 为什么看起来像“一直边做边错”

外部观感来自反馈进入得太晚：大范围实现先完成，最终 review 才一次次揭开 authority、state、readback 和 browser fixture 的深层约束。每轮修复局部 blocker 后，下一个 review 又沿新 codepath 找到另一类问题，于是表现为不断返工。这里既有正常的高风险分布式 workflow 复杂度，也有流程失配：最终 review 被当作主要设计发现机制，而不是最后一道验证机制。

更理想的节奏应是：实施前关闭 mutation/state/failure/test 四张表；每个 task 先写关键 red tests；共享 store、provider boundary、approval boundary 和 browser seam 分别 review；最终 review 只验证整合和残余漂移。这样总工作量不会消失，但错误会在成本更低的位置暴露，review 轮次和大范围返工会显著减少。

## 反事实判断

如果最初只增加一次普通人工通读，改善有限，因为原计划语言本身看起来完整。若按完整 `plan-eng-review` 做 data-flow、state-machine、failure-mode 和 test-diagram 演练，并把输出设成 implementation gate，则大概率能在编码前暴露一半以上的后期核心返工点。剩余部分仍属于实现层缺陷，需要 task/seam review、fault tests 与最终 `do-review` 捕获。
