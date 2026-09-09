---
name: dispatcher
description: 当任务需要 subagent、异步或并行调研/实现/修复/验证，或需要消费 worker 返回并继续安排工作时使用；统一定义执行范围、候选选择、委派合同、资源隔离、receipt、独立审查与 idle。
---

# Dispatcher

Dispatcher 是通用执行协作入口。调用方提供交付目标、授权、业务依赖与验收事实；Dispatcher 负责从可推进工作到 worker 返回的执行闭环。Topic 只是连续工作可用的组织概念，不是每次派发的前置模板、持久队列或业务状态。

## 执行循环

1. **明确交付范围。** 使用调用方给出的目标、限制、授权和事实；普通任务直接使用用户授权与仓库上下文。区分当前局部结果和整体完成，保留仍在授权范围内的剩余工作。
2. **主动发现可推进工作。** 启动、worker 返回、出现 review/fix/等待或阻塞时扫描剩余路径。比较提前产出的价值、dependency、资源隔离和整合成本，推进值得开展的调查、实施、修复或验证；局部 barrier 只扣住受影响候选。
3. **形成具体执行合同。** 以一个可验证结果或下一个需要主控判断的边界委派；同一结果所需的调查、实现、focused test、lint/format、普通重跑和机械 cleanup 一起完成。亲自执行也明确 write ownership、成功条件、自证和独立审查要求。形成 brief 时读取 [Delegation](references/delegation.md)；存在多个候选、共享资源或隔离 worktree 时读取 [Resource Isolation](references/resource-isolation.md)。
4. **核实返回并及时审查。** 宿主 receipt 明确成功后派发才成立；消费时核对来源、实际 diff、验证、未完成项、residue 和 cleanup。新增实现代码的 return 在同次消费中固定 `code_delta={base,head}`，并沿独立 review lane 派 delta review；无法立即派审时记录与该 return 关联的待派审欠项，后续扫描继续处理。纯调查或无代码重跑按证据检查。
5. **限定阻塞范围并继续安排。** review、fix、在途 worker 和共享资源只影响依赖其结论或争用其资源的工作。审查跟不上时收住会继续累积未审查假设的实现链；其他独立工作继续评估。没有值得当前推进的工作时等待或返回调用方；idle 只表示当前无合格且值得派发的动作，整体 closure 归业务 owner。

完成标准：所有成功派发都有真实 receipt；所有返回都已按来源消费；代码增量已有独立 review receipt 或明确待派审事实；最后一次扫描没有被局部 barrier 错误压住的高价值候选。

## 候选、归因与返回

`investigate | implement | fix | verify` 固定 worker 的答案形态。worker 返回 `DONE | BLOCKED | INCOMPLETE`；调查返回 `EVIDENCE_SUFFICIENT | EVIDENCE_GAP`；已产生的 required review 使用 `PENDING_REVIEW | PASSED`。这些都是局部事实，不代替 Ticket、acceptance 或 Gate。

investigate/review 结果需要交给另一个 worker 或后续 implement/fix 消费时，由主控在用户 temp 目录提供一份临时 handoff 路径。investigator/reviewer 写入结论后，主控读取、按需原地修订并验收，再把同一路径作为下游 brief 的只读输入；消费完成后由主控清理。该 handoff 不进入仓库、Git revision、业务状态或 durable docs；没有下游消费时继续直接返回，避免无用文件。

使用 Impl-Package trail 时，工作无需预登记；`candidate_id` 是实际派发工作及其可信续接的身份。dispatch 记录 `dispatch_id/candidate_id/subject/mode/chosen/resource_keys/receipt`；worker return 用 `of` 指回 dispatch，并带唯一 `return_id`。含代码增量时，return 与 review 使用同一个 `code_delta` 和 `consumption_id`。旧轨迹只读兼容；字段缺失不得静默归到同 Ticket 的其他 dispatch。

## 并行、复用与恢复

- `foundation`、`acceptance`、`resource`、`authorization` 是 dependency 词汇；它们逐候选限制动作，不构成全局暂停。真实 implementation dependency 与授权仍由业务 owner 决定。
- 主控根据当前授权和资源事实选择工作；需要恢复的判断沿用现有 Execution Record、checkpoint、handoff 与 trail，不新建独立 blocker fact。
- 并行按当前动作的实际 effect footprint 判断；未来可能交叉的 Topic/Ticket 不提前串行当前独立工作。可兼容的稳定读取可以共享；会改变他人读取结果或验证 oracle 的资源需要隔离或排序。
- worker 复用取决于相关上下文仍准确、ownership 清楚且已有错误可解释。边界、failure model 或 write-set 已失真时先调查受影响范围，再使用 fresh worker；不按 Topic 名称、固定等待时间或 `INCOMPLETE` 次数机械换人。
- worker 处于 `running` 时继续等待；需要收敛时向原 worker 发消息，让其停止扩展并总结已有结果。等待超时或在途时长只调整轮询，不触发中断、换人或重复派发；只有用户取消、确认越权或危险 mutation、不可恢复资源冲突、carrier/tool 明确失败时才中断。原边界仍可信的 carrier/tooling recovery 由同一 worker 完成。
- reviewer 始终独立于所审实现；同 scope 上下文可信时可以复用，每次核对新的固定输入。formal review 的 topology、coverage 和 closure 由 owning review workflow 决定。
