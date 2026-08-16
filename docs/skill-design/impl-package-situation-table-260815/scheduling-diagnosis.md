# 主控调度偏差诊断与现役版本补丁清单

## 0. 范围与口径

本报告以主工作树当前内容为现役规则，以 rollout `01a00aab-2d27-7090-bb66-60263e32d75b` 为行为证据。rollout 通过 `docs/skill-design/impl-package-situation-table-260815/tools/extract_rollout.py` 的逐行解析/脱敏函数抽取；现成入口固定面向预设案例，因此用临时适配器只传入这一份 session，没有把 JSONL 整份加载进上下文。

观察快照截止到抽取序列 `seq=311`、`2026-08-16T13:52:35.150Z`。源文件当时仍在增长，所以本报告描述的是这个 ongoing session 的可复核快照，不把后续追加事件当成已知事实。

本文把一次 `multi_agent_v1__spawn_agent` 调用视为一次派发；batch 内的每个 agent 另计一个 assignment。另行区分：spawn API 的即时确认不等于 worker 的业务结果返回；后者以 `DONE/BLOCKED/INCOMPLETE` 或明确 shutdown 为准。

## 1. 实际调度序列

截至快照共有 8 次 spawn 调用：7 次成功，1 次失败；成功派发 15 个 agent assignment。

| # | 派发时间（UTC）与间隔 | 派给谁、做什么 | worker 返回/终止 | 返回后主控做了什么 |
|---|---|---|---|---|
| 1 | `13:07:50.162`；无上一次返回 | `@luna-worker` Epicurus。把整个 TAW-02 作为一个 bounded implementer：delegated authorization/provenance、文件生命周期/CAS、deterministic replay、API contract、tax-web、focused specs 和 interim manual case；`mode=implement`、review required。 | spawn 确认 `13:07:50.439`；没有正常 worker envelope。`13:08:10` 起反复 wait，直到 `13:29:22` 仍超时；中断后仍未返回，`13:30:15.388` close，`13:30:15.419` shutdown。 | 主控承认这是“过大的 Ticket 作为单一 worker 交付”，保留已有 dirty 改动，改按 ownership 拆成调研、执行和 review 切片。 |
| 2 | `13:30:52.345`；距 #1 强制 shutdown `36.9s` | 一次 `Promise.all` 的三路只读 explorer：Parfit 做 backend，Curie 做 persistence/contract，Mill 做 UI/QA。三者都只读当前 diff、合同和最小验证入口。spawn 确认 `13:30:53.365`。 | 三个都没有返回研究 envelope；多轮 group wait 超时，`13:40:51.837–.868` 关闭并收到三个 shutdown。 | 主控没有再让主 session 空等：保留未返回的 persistence 以外的独占边界，另启 #3；随后关闭这三个过宽/过慢的只读 agent，改派更窄的 #4。 |
| 3 | `13:37:04.588`；#2 尚未返回；从 #2 spawn 确认计 `6m11.2s` | `@luna-worker` Russell。只做 `packages/db` persistence：schema、migration、tenant catalog/相关 DB specs；不得改 API/UI/contracts/package state。 | `DONE` 于 `13:48:45.036`。报告 `prisma validate/generate`、DB package 298 tests、typecheck、lint/diff-check 均通过；`review_state=PENDING_REVIEW`，Ticket 未关闭。 | `13:49:07.320` 主控明确把它当 bounded slice DONE 而非 Ticket 满足，立即派 #6 做独立 AC-02 checkpoint review。 |
| 4 | `13:41:17.193`；距 #2 强制 shutdown `25.3s`，且 #3 仍运行 | 第二次两路只读 explorer：Kant 做窄 backend 文件检查，Godel 做窄 tax-web/UI 文件检查；均限定文件、只读、不生成。spawn 确认 `13:41:18.526`。 | Godel 于 `13:44:58.462` 返回 `FAST_RESEARCH_DONE`；Kant 于 `13:45:48.437` 返回 `FAST_RESEARCH_DONE`。 | #5 已在两者返回前启动；`13:45:54.753` 主控消费两项结论，确认 helper 未接入 backend、五 slot/三 slot 类型分裂、UI 仍是 current-only browse view，继续让执行切片各守自己的写集。 |
| 5 | `13:44:17.352`；#4 尚未返回；从 #4 spawn 确认计 `2m58.8s` | 一次六路 `@luna-worker` fan-out：Arendt=`domain-reducer`，Aquinas=`file-lifecycle`，Plato=`delegated-adapter`，Faraday=`service-integration`，Hypatia=`tax-web`，Leibniz=`interim-case`。主控明确列出 6 个不重叠写集，OpenAPI/generated client 与 package bookkeeping 留作后续串行传播/审阅。spawn 确认 `13:44:19.719`。 | 截止快照六个执行切片尚无可消费终态；`13:48:18.037` 主控说将“哪个切片先返回就先 review”，不等整张 TAW-02。 | 继续做独立 review 准备和 wait；没有在这些写集上并行改动。 |
| 6 | `13:49:17.244`；距 #3 正常返回 `32.2s` | Tesla，`gpt-5.6-sol`，只读审 `packages/db` 写集和 AC-02，fresh checkpoint reviewer。spawn 确认 `13:49:17.518`。 | 截止快照未返回；与 #5 的 6 个执行 agent 一起被 wait。 | 主控连续等待，未把局部 DONE 升级为 Ticket closure。 |
| 7 | `13:52:08.121`；距 interim-case 返回 `11.2s` | 试图为已返回的 Leibniz 派独立 checkpoint reviewer。 | **派发失败**：`13:52:08.164` 返回 `agent thread limit reached`；不是 worker 返回。 | 主控识别出“已完成 agent 仍占席位”，关闭已回收的 QA、persistence、Kant、Godel 四个 agent，释放席位。 |
| 8 | `13:52:28.631`；距 #7 失败尝试 `20.5s`，距 interim-case 返回 `31.7s` | Carson，fresh `gpt-5.6-sol`，只读审 interim-case 的四个 test-case/registry 文件。spawn 确认 `13:52:29.034`。 | 截止快照未返回；`13:52:35.150` 已进入 wait。 | 主控继续等待其余执行切片和 reviewer；源 session 在此仍 ongoing。 |

这里有两个容易混淆的事实：

- #1、#2 的即时 spawn 确认很快，但不能算任务返回；真正的 worker 结果分别是“无正常返回后强制关闭”和“三个无结果后关闭”。
- #7 说明宿主有后期席位回收问题，但不是首轮串行的根因。首轮之后宿主已经成功执行 3 路、2 路、6 路并行派发；因此“机制完全不支持并行”不成立。

## 2. 哪些本可以并行

### 2.1 漏掉的首轮机会：3 个 bounded units，1 次 fan-out

在 #1 的 `13:07:50`，主控已经知道 TAW-02 同时横跨数据模型、文件/CAS、API 传播和 UI；但把全部工作交给一个实现 worker。至少下面三项可以先以只读调研并行启动，后来 #2 已证明了这个拆法：

1. **backend research**：API、文件生命周期、CAS、delegated revalidation、tenant/RBAC、deterministic parser/reducer。
2. **persistence/contract research**：schema/migration、actor provenance、one-active/idempotency、OpenAPI/生成客户端传播。
3. **UI/QA research**：tax-web source rows/edit surface、API/UI mismatch、manual case/registry binding。

判定依据是具体的：三者都是只读目标，primary ownership 不重叠；共享的是同一份输入 snapshot，不是可变输出；没有 typed dependency 需要一个研究结果先释放另一个；prompt 明确禁止 DB/provider/remote/生成物，因此不争用共享验证环境。

**机会数量：3 个独立候选，组成 1 次首轮并行 fan-out。**

**可省墙钟：保守估算约 23 分钟。** 从 #1 派发到同一三路 fan-out 真正开始的 `13:07:50.162 → 13:30:52.345` 是 `23m02.183s`；其中到 Owner 明确纠偏已经浪费 `21m32.742s`。因为 Epicurus 最终没有正常返回，不能据此假装知道完整实现时长，所以只把这 23 分钟作为“研究启动提前量/可确认节省”，不虚构更大的端到端节省。

### 2.2 后续可并行机会与实际结果

这些不是再次漏掉的机会，而是纠偏后已经发生的证据：

- #3 persistence 执行与 #2 的只读调研重叠，写集隔离，安全。
- #4 的窄 backend 与 UI 调研并行。
- #5 的六个执行写集并行；主控明确把 OpenAPI/generated-client propagation 留到 API 写集稳定后串行处理，这个串行判断有共享可变资源依据。
- #6 在 persistence 返回后独立 review，不等待其他执行切片；#8 也在其他代码切片继续时审 interim case。

因此应修复的是“首次派发前没有发现候选”，不是把所有工作强行并行化。

## 3. 为什么首轮没有并行

下表的计数是**非互斥证据标签**：同一个首轮决策可以同时命中多个原因，不能把三项相加当成统计学百分比。

| 原因 | 判定与证据 | 本轮计数 |
|---|---|---:|
| **没想到** | 在 `seq=18–53` 的首次执行准备中，只有“Planning subagent-driven development / multi-agent worker dispatch”，没有候选清单、batch 判断或 `PARALLEL/SERIAL` 结论；第一次明确说“parallel”是在 Owner `seq=162` 纠偏后，主控 `seq=164` 才承认要拆分。 | 1 个首轮漏扫点 |
| **想到但放弃** | `seq=46` 的策略明确写了“串行处理共享 schema/migration/OpenAPI/generated-client/test-case 写资源”；`seq=94` 又明确说“由于 TAW-02 同时涉及数据模型、文件/CAS、API 传播和 UI，我保持其单一 bounded ownership，避免主 session 与 worker 产生写集冲突”。这是明确的冲突担忧，但把写集冲突外推成整个 Ticket 串行。 | 1 个明确放弃点 |
| **规则没提示** | 现役策略要求填 `resources`，但没有要求在派发前枚举候选；并行准入页只有在“存在并发候选”时才读取；`dev-with-track` 只要求派发时写 primary ownership/禁区/成功条件/反例/局部验证。 | 1 个结构性缺口 |
| **规则劝阻** | 没有证据表明现役规则把并行设为默认不鼓励或要求额外许可。`parallel-work-admission` 的资源条件是安全门槛，不是“默认串行”命令。 | 0 个首因 |
| **机制受限** | 首轮不是宿主不支持：后来有 3/2/6 路 `Promise.all` fan-out。只有后期 #7 出现一次 `agent thread limit reached`，原因是已完成 agent 仍占席位；这是后期 review 调度的局部机制问题，不解释首轮 23 分钟串行。 | 首因 0；后期局部 1 次 |

结论排序：直接表现是“首轮没做候选扫描”；主控随后又用“共享写资源”理由选择了单一 ownership；现役规则没有在派发点把这两个判断拉出来。不存在“并行能力不可用”的解释。

## 4. 现役规则逐条核对

以下摘录均来自主工作树当前文件；`dev-with-track` 的最后一行虽有未提交文字调整，但下列控制循环内容未依赖那一行。

### 4.1 `subagent-driven-development/SKILL.md` 策略块

原文：

```yaml
mode: investigate | implement | fix | review
worker: main-session | "$grok-worker" | "@luna-worker" | "<model>/<effort>" | "prompt:<slug>"
review: none | required
review_scope: none | checkpoint | closure
reason: <仅在 local、blocked、显式 override 或 review 判断不显然时填写>
resources: <只记录真实共享资源、顺序和 cleanup owner>
reuse: <只在同一 source unit 需要不可转移 live state 时填写>
```

紧接着的策略规则是：

> 多个 bounded unit 的派发顺序由 main session 根据依赖、ownership 和 resources 临时决定；存在并发候选时读取 [Parallel Work Admission](references/parallel-work-admission.md) 判定。

判断：这些字段提示主控记录 worker、review、资源和复用边界，但没有提示“先找出多个候选”。`resources` 还容易让主控只看到共享写资源，而看不到同一 Ticket 内的只读或不重叠写集。这里是**规则没提示**，不是规则劝阻；规则给了并行所需的判定维度，却没有触发候选发现。

### 4.2 `references/parallel-work-admission.md`

原文：

> 仅当两个以上 bounded work 候选可能并发执行时读取本页。

> 只有每个候选都具备独立目标和完成条件、没有未决前置依赖、primary ownership 不重叠且不共享可变运行资源时，才允许并行。端口、测试数据、输出目录、外部记录和其他共享资源必须先隔离；worktree 不在此隔离要求内，可由 scheduling contract 决定是否共享。

> `PARALLEL`：列出 batches、每个单元的 ownership、隔离资源和全部返回后的集成验证；
> `SERIAL`：指出要求有序执行的依赖、ownership 重叠、共享资源或未决 seam；
> `BLOCKED`：指出使串行和并行都无法安全开始的缺失决定或授权。

判断：第二段和三个结果类型本身是很好的**并行提示/安全约束**；它明确要求 ownership、typed dependency 和 mutable resource 的证据。问题在第一句：它把“发现存在候选”设成阅读本页的前置条件，却没有别的规则负责这一步。也就是本轮怀疑的**自指缺陷**：缺失的候选识别恰好导致准入页不被读取。

### 4.3 `dev-with-track/SKILL.md` 主 session 控制循环

原文：

> **Implement**：只修复已证实、当前可归责的范围；派发时给 primary ownership、禁区、成功条件、反例和局部验证。

> 步骤 1、3 的事实调查、实现、修复和验证策略由 `/impl-package:subagent-driven-development` 统一形成；本 skill 只消费其 `mode / worker / schedule / review` 与结果合同。步骤 2 和 4 由主 session 把控，package 记录通过 bookkeeper 落盘。

> 依赖是否释放由新 package 的 typed Ticket dependency 与 canonical state 判断；旧 package 才额外读取 DAG。Progress/checkpoint 不授权 dispatch，也不释放 acceptance/release dependency。

判断：这里规定了单个派发 brief 的质量，也把调度判断交给 subagent skill，但没有“派发前扫描同一 Ticket 内候选”的动作；`typed Ticket dependency` 也容易被误读成整个 Ticket 的 barrier，而不是具体 bounded unit 的 dependency。结论是**规则没提示**，不是**规则劝阻**。

## 5. 针对现役版本的最小补丁清单

这些是报告中的补丁建议，本轮不实施；不涉及 `impl_package_state.py`、新 state 字段或新的协调设施。

### P1 — 在主控派发点加入候选扫描与轻约束（约束型）

- **文件**：`plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md`，紧接 `Implement` 派发要求。
- **改成**：增加约 2–3 行：派发前按 primary ownership、typed dependency、共享可变资源列出当前 bounded-unit candidates；同一 Ticket 的独立只读/写集也算候选；候选数大于 1 时先读取 Parallel Work Admission，仍选 `SERIAL` 必须写一句具体 dependency/ownership/resource reason。
- **命中原因**：直接补上“没想到”和“规则没提示”的缺失步骤，并把 `seq=94` 那种单一 ownership 选择变成可审计的轻约束。
- **风险**：每次派发多几个 token，且可能把不成熟的拆分误报成候选；由准入页的独立目标/依赖/资源条件收口，风险可控。

### P2 — 修正并行准入页的自指入口（提示型）

- **文件**：`plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/parallel-work-admission.md` 第一行。
- **改成**：将“仅当两个以上 bounded work 候选可能并发执行时读取本页”改为“每次派发前先扫描当前 Ticket/attempt 内的 bounded work 候选（包括同一 Ticket 的不同 ownership）；扫描出两个以上就读取本页；没有候选也记录 no-candidate”。保留后面的 `PARALLEL/SERIAL/BLOCKED` 判定不变。
- **命中原因**：直接修复“候选识别缺失 → 准入页永远不读”的结构性缺口。
- **风险**：主控会更常进入准入页，增加少量启动成本；这是提示成本，不会改变安全条件。

### P3 — 把资源字段从“共享即串行”的启发式中解耦（提示型）

- **文件**：`plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md` 策略块的 `resources` 行及其相邻说明。
- **改成**：把字段说明收紧为“只记录真实共享的可变资源、隔离方式、顺序和 cleanup owner；同一 Ticket、共享只读输入或共享 worktree 不自动构成串行理由”。明确 read-only research 与不重叠写集可以进入同一 batch。
- **命中原因**：纠正主控已想到并行维度却因资源冲突过度放弃的判断；同时保留真正共享 schema/OpenAPI/generated-client 的串行约束。
- **风险**：若 ownership 识别错误，可能诱发不安全并行；后面的 admission 条件仍要求 mutable resource 隔离，P1 的具体 reason 也提供回查点。

**最先打 P1。** 它位于主 session 真正决定“派发一个还是先 fan-out”的位置，三至五行即可命中首因；P2 解决规则的结构性缺口，P3 再修正资源语义。只打 P2 而不在 dispatch loop 提醒扫描，主控仍可能根本不打开该页；只打 P3，则可能知道资源边界却仍不产生候选清单。

## 6. 与处境表的关系

结论：**会加剧串行倾向。** 另一个 worktree 的处境表设计把主控循环写成：

> 渲染处境与可选动作 → 选一个 → 执行或派发 → 记一行 → 重新渲染。

其当前 YAML/action 形状有每个处境的 `actions`，但没有表达“这些 bounded units 属于同一可并行 batch”；renderer 的 `parallel_matches` 表示同层命中的多个**处境行**，不是多个可同时派发的 action。human render 仍是“并列处境……先选一个处境，再选其动作”。因此它会把“先发现候选、再决定 batch”压扁成“从一个动作列表选一个”，特别容易重现本 rollout 的首轮行为。

处境表侧将来应补一个与 `selected/action` 并列的“可并行候选/批次”投影：至少包含每个候选的 bounded unit、primary ownership、typed dependency、共享可变资源和 fan-in 验证点；同时允许明确输出“没有并行候选”或“可并行但选择 SERIAL 的理由”。这只是对另一个 worktree 的后续建议，本轮没有修改该 worktree。
