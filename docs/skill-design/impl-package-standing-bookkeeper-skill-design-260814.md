# Impl-Package Standing Bookkeeper Skill 设计

## 1. 文档状态

- 日期：2026-08-14。
- 状态：顶层方向与简化边界已由 Owner 确认；Blind Opening 和 Owner review 已完成，具体写入内容、依赖判定和消息格式留待试运行收敛。
- 目标：把 Implementation Package 的文档与运行状态写入移出主 thread 的开发关键路径。
- 设计对象：新的 package-bound standing bookkeeper 能力；本文不授权实施。

## 2. 已确认结论

当前工作模型固定为：

```text
1 package = 1 主 thread = 1 standing bookkeeper
```

1. 主 thread 负责业务与工程判断、实现工作、结果采信和最终复核。
2. standing bookkeeper 是该 package 文档与状态的唯一 writer。
3. 主 thread 通过轻量自然语言事件报告已经发生的事实、已经作出的结论或需要执行的更新，不亲自修改 package artifact。
4. bookkeeper 负责定位 owning artifact、加载适用规则、执行写入、运行验证并返回短回执。
5. 控制流只区分“下一动作依赖本次更新”和“不依赖本次更新”。具体分类规则通过试运行决定，不在首版设计中提前穷举。

主 thread 复核 bookkeeper 的结果不构成第二写者。发现错误时，主 thread 发送 correction event，仍由 bookkeeper 修改。

## 3. 问题

Impl-Package 已经用脚本承担 state、projection 和部分 validation，但主 thread 仍需：

- 在开发过程中切换到文档与状态维护；
- 重新加载 owning stage 的规则并判断写入位置；
- 组织 Markdown judgment、checkpoint、Gate 或 contract delta；
- 执行写入、检查投影和确认状态没有漂移；
- 再返回实现上下文继续工作。

这些动作中既有机械写入，也有对已作出结论的结构化表达。它们与实现工作串行发生，会占用主 thread 的上下文和关键路径时间。现有 bounded worker 能返回代码或证据，但默认不能直接维护 package state，因此无法消除这段簿记成本。

## 4. 目标与非目标

### 4.1 目标

- 主 thread 可以在不亲自编辑 package artifact 的情况下推进实现。
- 同一 package 始终只有一个 writer，避免双写和 lost update。
- bookkeeper 能从 package canonical state 和当前 Impl-Package 规则恢复，不依赖聊天记忆成为事实源。
- 依赖更新在成功写入并验证后才释放主 thread；非依赖更新可以后台完成。
- 主 thread 只消费压缩回执和必要 diff，不重新执行完整簿记流程。

### 4.2 非目标

- 不把 requirement、architecture、acceptance、finding disposition 或 Gate verdict 的裁决权交给 bookkeeper。
- 不让 bookkeeper 修改业务实现代码。
- 不建立跨 package 的全局 writer、共享 standing agent 或协调 ledger。
- 不新增独立的协调基础设施或通用 workflow engine。
- 首版不接管 Git commit、merge、push、release 或其他外部 mutation。
- 不把 stable-doc backfill 混入 package 日常簿记；它继续由现有 owning workflow 处理。

## 5. 目标拓扑

```text
Owner
  │
  ▼
主 thread（判断、实现、复核）
  │  update event
  ▼
standing bookkeeper（唯一 package writer）
  ├─ 解析目标与 owning stage
  ├─ 读取 canonical package state
  ├─ 调用确定性 state CLI / 编辑 owning artifact
  ├─ 运行 focused validation
  └─ 返回 receipt
  │
  ▼
主 thread（采信、继续或发送 correction event）
```

standing bookkeeper 是 LLM actor；现有或后续的确定性 CLI 是它的 mutation kernel。两者不是替代关系：bookkeeper 解释轻量意图，CLI 保证机械状态转换和投影一致性。

## 6. Ownership

| Surface | Writer / Decision owner |
| --- | --- |
| 业务与工程判断 | 主 thread |
| implementation code | 主 thread 或其 bounded workers |
| package Decision/Spec/contract-design/Plan/Ticket 文档的物理写入 | standing bookkeeper，按 owning stage 规则执行 |
| package state、evidence index、active checkpoint、Progress、Execution Record、Gate 的物理写入 | standing bookkeeper，优先通过 state CLI 执行 |
| Ticket acceptance、Gate verdict、contract delta 的语义结论 | 主 thread；bookkeeper 只消费明确结论 |
| bookkeeper 写入结果的最终采信 | 主 thread |

主 thread 对 package artifact 保持只读。该限制只覆盖当前 package 的文档和状态表面，不阻止主 thread 或其他 worker 修改授权范围内的实现代码。

## 7. Skill 形态

候选 Skill 名为 `/impl-package:standing-bookkeeper`，位于 Impl-Package plugin 内。它不是 `subagent-driven-development` 的 bounded worker mode：

- bounded worker 默认 fresh invocation，交付一个有限 source unit 后结束；
- standing bookkeeper 与 package thread 一一绑定，在 package thread 生命周期内持续接收更新；
- bounded worker 返回实现或证据，standing bookkeeper 持有 package write ownership；
- standing bookkeeper 不参与 implementer、fixer 或 reviewer 的选择与验收。

Skill 建议分成两个上下文表面：

1. 主入口：供主 thread 初始化或恢复 bookkeeper、发送 update event、处理 receipt。
2. role reference：只在 standing subagent 中加载，定义 package writer 的解析、写入、验证和回报流程。

这种拆分使主 thread 只承担薄调用合同，完整写入方法留在 bookkeeper 的独立上下文中。

## 8. 生命周期

1. 每个 package thread 创建并绑定一个 standing bookkeeper subagent。
2. bookkeeper 初始化时读取 Impl-Package 入口、状态规则、相关 owning stage Skill、canonical package root 和当前 package state。
3. bookkeeper 在该 package thread 生命周期内持续接收更新，不服务其他 package。
4. bookkeeper session 结束时，主 thread 启动新的 bookkeeper；新 bookkeeper 重新读取规则和 package state 后继续工作。

首版是在 package thread 开始时创建，还是第一次需要写 package 时创建，由试运行决定。

## 9. 自然语言更新

主 thread 与 bookkeeper 使用普通对话，不引入新的消息协议。起始模板可以是：

```text
更新：
结论/事实：<要记录什么>
依据：<必要时提供>
依赖：是 | 否
```

package、Attempt、目标文件、模板和命令由已经绑定该 package 的 bookkeeper 自行定位。具体哪些信息经常需要写入模板，通过实际使用逐步补充，不在设计阶段预设完整字段。

## 10. 依赖模型

控制流只区分两种情况：

- **依赖=是**：主 thread 的下一动作需要本次更新结果，因此等待 bookkeeper 写完并回复。
- **依赖=否**：下一动作不需要本次更新结果，因此主 thread 可以继续，稍后查看 bookkeeper 回复。

具体怎样判断依赖，只能根据试运行中的真实更新形成经验规则。设计阶段不建立固定判定表。

## 11. 简单工作流

1. 主 thread 作出判断或确认事实。
2. 主 thread 用自然语言告诉 bookkeeper 要记录什么，以及当前是否依赖这次更新。
3. bookkeeper 读取适用规则和当前 package 状态，定位正确 artifact。
4. bookkeeper 使用现有 CLI、模板或 Markdown 编辑完成写入，并运行对应验证。
5. bookkeeper 简短回复自己的理解、实际修改和验证结果。
6. 主 thread 查看结果；正确则继续，需要修正则继续通过对话告诉 bookkeeper。

主 thread 不为修正结果而亲自编辑 package artifact，bookkeeper 也不替主 thread 作出新的语义判断。

## 12. 身份边界

### 主 thread：裁决者

- 决定 requirement、architecture、implementation direction、acceptance、finding disposition 和 Gate verdict。
- 完成或调度实现工作。
- 复核 bookkeeper 的写入结果。

### standing bookkeeper：执行者

- 理解主 thread 已经给出的结论或事实。
- 决定应写到哪个 owning artifact，并按对应 Skill 规则执行。
- 运行写入后的 focused validation。
- 报告结果；信息不足时直接询问主 thread。

这组身份边界是首版的完整控制合同，不再为自然对话增加消息系统或并发控制抽象。

## 13. 普通异常处理

- bookkeeper 没听明白：直接问主 thread。
- 写入或验证失败：说明失败位置，等待主 thread 决定下一步。
- 主 thread 发现内容不对：通过对话要求 bookkeeper 修正。
- bookkeeper session 不可用：启动新的 bookkeeper，从当前 package 文档和状态恢复。

首版不为这些情况建立独立状态机。只有实际试运行反复出现无法靠自然对话解决的问题，才考虑增加机械支持。

## 14. 与现有 Impl-Package 的关系

- `req-align`、`impl-planning`、`to-tickets`、`dev-with-track` 和 `backfill-stable-docs` 继续拥有各自语义与完成条件。
- standing bookkeeper 只转移物理写入和 focused validation，不重新定义 owning stage。
- `subagent-driven-development` 继续编排 investigate/implement/fix/review bounded work，不管理 standing bookkeeper。
- D-1 broker 继续管理跨 thread coordination；standing bookkeeper 只服务自己的 package thread。
- `impl_package_state.py` 继续承担 runtime state 的机械写入和验证。

实施时需要把 stage skill 中要求主 thread 直接写 package artifact 的位置，改为由主 thread 通知 bookkeeper 执行。

## 15. 试运行

首轮选择一个非关键 active package，按上述简单工作流实际使用。观察：

- 主 thread 是否减少文档切换和规则重读；
- 哪些更新只需一句话，哪些需要补充依据；
- “依赖/不依赖”在真实工作中怎样判断；
- bookkeeper 是否能稳定找到正确 artifact 和写入方式；
- bookkeeper 的回复是否足够让主 thread 快速复核；
- 自然对话中的澄清和修正是否足以处理日常偏差。

试运行结束后，再根据实际事件整理轻量模板和依赖判断经验。没有发生的问题不进入 Skill 合同。

## 16. Acceptance Criteria

Skill 只有在试运行满足以下条件后，才适合进入默认工作流：

1. 一个 package thread 只使用自己的 standing bookkeeper 写 package artifact。
2. 主 thread 能用轻量自然语言表达常见更新，不需要自己重读完整写入规则。
3. bookkeeper 能正确定位 owning artifact，完成写入并运行 focused validation。
4. 依赖更新会等待 bookkeeper 回复，非依赖更新允许主 thread 继续推进。
5. bookkeeper 不自行创造 requirement、acceptance、finding disposition 或 Gate verdict。
6. 主 thread 能快速复核并通过自然对话要求修正。
7. 实际使用中，主 thread 的文档上下文占用和工作中断明显下降。

## 17. 试运行后再定

- update event 最终需要哪些常用信息；
- “依赖/不依赖”的经验判定；
- bookkeeper 回复应保留多少内容；
- bookkeeper 的最佳初始化时机；
- 是否存在值得脚本化的重复机械动作。

这些问题都由真实使用决定，不预先设计复杂基础设施。

## 18. Blind Opening 与 Owner 处置

本轮按 `discuss-ledger` Blind Opening 模式运行，参与者为 Codex 与 Claude，Claude effort 为 `medium`。原始结果：

`C:\Users\Xiao\AppData\Local\Temp\discuss-ledger\blind-impl-package-standing-bookkeeper-skill-design-260814-653757aa.md`

Blind Opening 认可语义裁决与物理写入分离，也提出了更复杂的异常与协调机制。Owner review 后作出以下处置：

1. 保留“主 thread 是裁决者、standing bookkeeper 是执行者”的简单工作流。
2. 保留自然语言交流，不增加独立消息协议。
3. 不引入额外的消息或并发协调基础设施。
4. 不预设固定依赖判定表，待实际试运行后总结。
5. 日常异常先通过自然对话、现有 package state 和现有 CLI 处理；只有真实反复出现的失败才进入后续设计。

Blind Opening 到此结束；Owner 处置优先于 reviewer 提出的候选机制，本文没有开始 implementation。
