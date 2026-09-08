# 三个核心执行 Skill 的第一性原则审查

对 [dispatcher-dev-with-track-sdd-consolidation-proposal-260908.md](dispatcher-dev-with-track-sdd-consolidation-proposal-260908.md) 的审查与重设计。日期 2026-09-08，基线 HEAD `cb906e6`。

## 1. 结论

提案的方向成立（合并 Dispatcher 与 SDD、dev-with-track 保留业务合同），但它把用户报告的串行化当成**正文问题**来治，因而修不好。串行化的机械来源在运行时投影契约里，而提案第 9.3 节明确冻结了 `situation.py` 的投影结构。结果是提案自己的验收项 V01/V03/V12 在其自身实施范围内无法通过。

三条修正：

1. **先改投影契约，再改正文。** 投影从"当前唯一处境"改成"全局闸门 `blocking` + 候选集 `runnable` + 缺席原因 `withheld` + 在途标注 `in_flight`"。`blocking[]` 只收全局 fail-closed，局部 barrier 一律进 `withheld[]`，否则串行化会在新契约里原样复发。这一步不动任何 Skill 正文，但要先固定输入合同。
2. **outcome 类 fact 从 Ticket / attempt 聚合改成按 dispatch 归属。** 聚合粒度高于工作粒度时兄弟 dispatch 必然互相污染，这不是调参问题；代价是求值接口要动，不能声称零改动。
3. **正文负责触发，runtime 负责核验。** receipt 成立、含代码 return 是否及时派了 delta review，`dispatch_audit.py` 读 trail 能核验，但它是只读事后报告、触发不了任何动作，所以正文各留一句触发、不再讲解。

按此重排后，提案 V01–V16 中有 9 项从"模型行为评测"降级成普通 pytest fixture 断言。

## 2. 提案中已经成立、本文不再重复论证的部分

- Dispatcher 与 SDD 合并、保留 `$dispatcher` 名称、退役 SDD 目录。
- dev-with-track 保留 Ticket readiness、语义裁决、State/Evidence/Gate 单写。
- 第 10 节的删留清单大部分方向正确（删固定 15/30 分钟门槛、删"delta finding 一律随下一步修"、删"批次收齐再决定"）。
- 第 11.3 节对安装缓存与 trail parser 历史兼容的识别是对的（但同节的 DSH 判断有事实错误，见 §6.1）。

## 3. 根因：串行化写在投影契约里，不在正文里

三处代码事实叠加，构成一台确定性的串行机器：

**(a) 投影只输出最高命中层。** [situation.py:2983-3008](../../plugin-marketplace/plugins/impl-package/scripts/situation.py) —— 无 P0 命中时，只有 `highest_layer` 的候选进入 `parallel_matches`，所有更低层候选降为 `other_matches`，渲染成一行 `secondary（较低层）N 个：...`。真正的实施工作全部住在 P2–P4。

**(b) 渲染句直接下达单选命令。** [situation.py:3119-3126](../../plugin-marketplace/plugins/impl-package/scripts/situation.py) 输出 `判断点: 先选一个处境，再选其动作`。

**(c) in-flight 是 attempt 级布尔。** [situations.yaml:722](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml) 的 `attempt.readiness.worker-still-running` 命中条件是 `trail.decision_without_result`，而 [situation.py:1665](../../plugin-marketplace/plugins/impl-package/scripts/situation.py) 的 `_decision_without_result` 用 `all_attempt_rows=True` 在整个 attempt 范围内求值。

合起来：**attempt 里任何一处有未回收的 dispatch，P1 就命中，于是 P2–P4 的全部实施候选被降为一行 secondary，注入文案是"等 worker-return 后再决策"，可选动作只有 `wait` 和 `interrupt`。**

更尖锐的一点：正确的并行指引其实已经写好了，但被挂在了永远够不着的位置。对比两条 `protocols.json` 注入文案：

| slug | 注入文案 | 何时可达 |
| --- | --- | --- |
| `multiple-ready-tickets` | 「按实际 dependency 和资源隔离决定并行；消费 return 后检查受影响候选补派」 | 仅当 `attempt.in_flight: false`，即**没有任何 worker 在跑**时 |
| `worker-still-running` | 「不并发派发同一 source unit；等 worker-return 后再决策」 | 只要有 worker 在跑 |

需要并行指引的时刻恰好是它被关掉的时刻。这两条的可达条件是反的。

因此提案第 9.3 节"改两行 `when`、保持 `situation.py` 不变"不足以成立：即使删掉 `multiple-ready-tickets` 的 `in_flight: false` 守卫，两条 P1 同时命中，渲染仍然是"并列命中，先选一个处境"，而 `worker-still-running` 的默认动作仍在里面。任何写在 Dispatcher 正文里的"主动发现并行机会"都排在 dispatch 时注入的 P1 默认动作后面。

## 4. 第一性原则：按失败模式决定该不该写规则

系统里存在三类权威，它们的失败方式不同，所以"写死规则"的收益完全不同。这是判断某条规则该留、该删、还是该搬进代码的分类依据。

| 权威类型 | 失败模式 | 失败是否可被模型自查 | 结论 |
| --- | --- | --- | --- |
| **事实**：Ticket 状态、evidence、gate | 虚假完成宣称 | 否，且静默 | 值得写死。单写、CLI、fail-closed。**现状正确，不动。** |
| **合法性**：现在允许跑什么 | 越过 barrier 的投机实现、越权 mutation、资源破坏 | 否，且静默 | 值得写死，但必须由 runtime 从事实**算**出来，不能靠正文复述 |
| **选择**：在合法项里跑哪些、什么组合 | 慢、串行 | 是，主控当场能看见 | **写规则的边际收益为负**。每条规则删掉一个选项，且不可能在所有现场都对 |

**当前设计的错误是把第二类和第三类交给了同一个机制**，而这个机制的输出契约是单游标。单游标只能用"你现在的处境是等待"来表达"你不许并发写同一个 source unit"——合法性约束因此必然溢出成选择约束。这就是串行化的机械来源。

由此得到一条可以贯穿三个 Skill 的设计不变式：

> **运行时只回答"什么被禁止、为什么"；不在多个合法项之间挑选。**
> **正文只回答"在合法项里怎么挑、怎么委派、怎么收"；不复述运行时能算出来的东西。**

提案第 2.3 节的表在精神上说了同一件事，但落地时把它当成了正文分工，没有落到投影契约上。

## 5. 目标形态

### 5.1 投影契约：一个游标 → 一个全局闸门 + 一组候选 + 两组标注

```text
blocking[]    只放全局 fail-closed：命中即整个 Attempt 暂停
              （terminal-frozen、state-missing、projection-drift、anchor-mismatch）
runnable[]    当前全部合法候选，不按层压制、全量渲染
              每项带业务 subject、声明的 resource key、以及"为什么合法"
withheld[]    某个候选为什么不在 runnable 里：带 dependency 类型 token
              （foundation / acceptance / resource / authorization）与作用范围
in_flight[]   标注，不是处境：哪些 dispatch 在跑，各占用什么 subject / resource key
```

**局部 barrier 不进 `blocking[]`。** 这是本节相对初稿的修正：初稿把"未释放的 implementation edge、缺 authorization、不可隔离的共享资源"和 terminal-frozen 一起列为"必须先清"。但 T1 的 implementation edge 未释放只挡 T1，把它放进有序的"必须先清"列表，等于在新契约里重造 §3 刚诊断掉的串行化，只是换了一层。局部 barrier 的正确位置是 `withheld[]`——它不是待办，而是某候选缺席的原因。这样"为什么不能跑"和"现在能跑什么"是同一次投影的两面。

关键的本体论修正：**在跑的 worker 不是一个"处境"（一个要求你采取动作的状态），而是一个"事实"（一个收缩候选集合的约束）**。`worker-still-running` 应当从 `situations` 移出，成为 `in_flight[]` 标注。它现在占着一个 P1 处境位，这就是它能吞掉整层投影的原因。

单游标语义只保留在 `blocking[]` 内——那是确定性真正值钱、且确实该停下整个 Attempt 的地方。

### 5.2 in-flight 粒度

把 `_decision_without_result` 的 attempt 级聚合改成按 dispatch 归属，`worker-still-running` 的"不并发派发同一 source unit"这条**真实**约束才第一次被准确表达——它本来就只想锁住同一个 source unit，是聚合粒度把它放大成了 attempt 锁。

但这不是零改动。`FactContext` 按 (kind, subject) 构造、`_subject_rows` 按 `row.get("subject")` 过滤、`when` 整体挂在这条轴上，所以 `of` / `dispatch_id` 只能关联事件，**不足以让求值器区分同票的 A 与 B**；要么加一条 dispatch 轴的 context，要么让 fact 返回按 dispatch 分组的值并改 `when` 的匹配方式，二选一都要动求值接口。而且 `resource_key` 在当前 runtime 里根本不存在（`scripts/` 与 `references/` 全仓无命中），所以"每项带 resource key"目前没有数据源。

因此投影改造要先定输入合同：dispatch 行带 `dispatch_id`、业务 `subject` 和**由派发方声明的** `resource_keys`，result 行带 `of`，字段缺失走已有的 `unknown` 路径而不是静默聚合。resource key 只接受声明、系统不推断——这同时划定了改造上界：投影负责把已声明的事实完整准确地呈现出来，资源与授权的实际判断仍归主控。

### 5.3 正文 / reference 的切分依据：加载点，不是执行者

提案用"同一个主控执行"论证合并。这不是正确的判据——正确的判据是**文本在什么时刻被读**，因为 SKILL.md 的成本按轮次付、reference 的成本按条件付。

- SKILL.md = 每轮都要读的循环（发现候选 → 组合 → 委派 → 核实返回 → 限定阻塞范围）。必须短。
- `references/delegation.md` = 组 brief 时读。
- `references/resource-isolation.md` = 出现资源交叉时读。

按这个判据复核提案第 7/8 节：五步循环留在正文是对的；delegation 进 reference 是对的。但第 10 节把 **dependency 四分类**（foundation / acceptance / resource / authorization）整个删掉是过头了——它不是流程枷锁，是让"blocked"这个词有确定含义的词汇表，删掉之后 `withheld[]` 的每一项就没有类型可标了。正确处理是**降级进 reference 并让投影复用同一套 token**（`withheld[]` 逐项标类型时就用它），而不是删除。

同理，`investigate | implement | fix | verify` 四个 mode 应当整体保留：它有真实消费者（[situation.py](../../plugin-marketplace/plugins/impl-package/scripts/situation.py) 的 `_last_worker_mode`、trail、audit），一共四个词，而且是给弱模型 worker 的答案形态锚点。提案的"通用正文降为辅助、package 消费层保留兼容"会造出同一概念的两个等级——正是这次合并想消灭的克隆形态。

### 5.4 正文负责触发，runtime 负责核验

用户的四条诉求里有两条是关于**可靠性**的（执行更 deterministic、worker 是弱模型）。以下两条现在以正文形式散在三个 Skill 里，正文物理上无法保证它们成立，但 trail 能核验：

| 规则 | 现状 | 改为 |
| --- | --- | --- |
| 单个派发只在宿主 receipt 明确成功后成立 | Dispatcher 正文第 3 条 | 正文留一句触发；`dispatch_audit.py` 断言：每条**实际 dispatch 行**有匹配 receipt 或消歧记录（非派发的业务 decision 不在断言范围） |
| 含新增实现代码的 return 及时派独立 delta review | 三个 Skill 各写一遍 | 正文只在 Dispatcher 留一句触发；`dispatch_audit.py` 断言**时序**：同一 subject 上 review dispatch 早于下一次 implementation dispatch，或有显式 escape |

更准确的说法不是"搬进 runtime"，而是**正文负责触发、runtime 负责核验**：`dispatch_audit.py` 是只读事后报告（`main` 只做 `print(_format_report(...))`），既不能触发派审也不阻断状态推进，所以触发必须留在 Dispatcher 正文——但只留一句，不再讲解。两条核验也要写准：receipt 的断言对象限于实际 dispatch 行（`_dispatch_is_running` 已能区分），不能要求所有业务 decision 都有宿主 receipt；delta review 的可测条件是**时序**——同一 subject 上 review dispatch 必须早于下一次 implementation dispatch，只断言"result 之后存在 review dispatch"会被期末集中补审蒙混过关。这样三份正文里的重复段落仍然删得掉，同时保住原规则真正想要的行为。

## 5.5 同一个根因的第三、第四个症状

§3 的 in-flight 是"阻塞侧"的粒度错配。同一个错配在"读取侧"同样成立，而且在允许同 Ticket 并行之后才变得危险：

- [situation.py:1515](../../plugin-marketplace/plugins/impl-package/scripts/situation.py) 的 `last_outcome()` 在 Ticket 范围内倒序取**最后一条** result 的 outcome，不区分它属于哪次 dispatch。
- [situation.py:1727](../../plugin-marketplace/plugins/impl-package/scripts/situation.py) 的 `_incomplete_count()` 只数尾部连续的 `INCOMPLETE`，遇到任何非 INCOMPLETE 结果就 `break`。

于是同一 Ticket 上 A 返回 `INCOMPLETE`、B 随后返回 `DONE`，投影得到 `last_outcome=DONE`、`incomplete_count=0`——A 的未完成事实从投影里消失了。A 的轨迹还在 trail 里，但没有任何处境会因此命中。

第四个症状在这两个 fact 的消费端：

| slug | when | judgment | 默认动作 |
| --- | --- | --- | --- |
| `ticket.implement.worker-incomplete-first` | `incomplete_count: 1` | `false` | `by: dispatch` 直接换 fresh worker，effect 写"视为上下文污染/持续卡住" |
| `ticket.implement.worker-incomplete-second` | `incomplete_count: 2` | `false` | `by: main-session` 直接 `ticket block` |

这两行（[situations.yaml:242-268](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml)）与**同一个 Skill 今天就在发布的** `runtime-protocol.md`「不套固定 fallback 次数；上下文可信则同 lane 继续」直接冲突，也与 SDD「边界仍可信时沿同一 worker 续接」冲突。两条都是 `judgment: false`，即机械命中、默认动作直接执行。提案 §8/§10 说了要删次数门槛，但 §9.3 的迁移表没有覆盖这两个分支。

**四个症状是同一个根因**：trail 投影按 Ticket / attempt 聚合，而工作按 dispatch 发生。聚合粒度高于工作粒度时，兄弟 dispatch 会互相污染——阻塞侧表现为一个 worker 锁住整个 attempt，读取侧表现为一个 DONE 抹掉兄弟的 INCOMPLETE。

因此 §5.2 的修法要扩大一档：不只是 `_decision_without_result` 改 subject 级，而是**所有从 trail 派生的 outcome 类 fact 都按 dispatch 归属**（`of` / `dispatch_id` 关联机制 `_open_dispatch` 已经在用，不需要新状态系统）。`last_outcome` / `incomplete_count` 保留为导航摘要即可，但**不能再作为 `when` 条件驱动换人或 `ticket block`**——这是代码层修正，不是在正文里加一句"别只信 last_outcome"的告诫。

## 6. 对提案的逐条修正

### 6.1 §11.3 的 DSH 判断是事实错误

提案说"删除 SDD 后不能只把 `stage` 改成 `dispatcher`，因为 suite 内没有该目录"，据此建议改用自定义 `text` 路由。源码不支持这个理由：

- [commands.mjs:68](../../plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/commands.mjs) 生成的是 steering 文本 `以 ${def.stage} 阶段处理当前 Impl-Package 任务。`，没有拼接任何 plugin 内 Skill 路径。
- [agent.cordis.yml:151-153](../../plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/agent.cordis.yml) 的 `customSkillDirs` 同时包含 plugin skills 目录和 standalone `skills/` 目录。

所以直接把 `stage` 改成 `dispatcher` 就能解析。自定义 `text` 路由仍可选（能带更明确的意图），但不应以"路径不存在"为理由。

### 6.2 新增的兼容性缺口：旧 Dispatcher + 新 plugin

§11.3 只要求"有可解析的已安装入口"。缺口在于**旧 Dispatcher 同样可解析，但它正文里有三处 `/impl-package:subagent-driven-development` 引用**（[SKILL.md:8/30/40](../../skills/dispatcher/SKILL.md)）。宿主装了新 plugin（SDD 已删）却加载旧 Dispatcher 时，执行方法指向不存在的入口，而且不报错——主控会回到旧流程。

宿主验收要从"能找到 `$dispatcher`"提升为"实际加载的 Dispatcher 与 plugin 内容兼容"：至少覆盖新组合成功、错配可被识别。用已有的 commit / 内容指纹即可，不需要改版本号。

### 6.3 逐条修正表

| 提案位置 | 问题 | 修正 |
| --- | --- | --- |
| §9.3「`situation.py` 先保持不变」 | 与 §13.2 的 V01/V03/V12 直接冲突；冻结的正是根因所在 | 投影契约改造前置为第一步 |
| §9.3 `worker-still-running` 改默认动作 | 它不该是处境 | 移出 `situations`，改为 `in_flight[]` 标注 |
| §9.3 `multiple-ready-tickets` 删 `in_flight` 守卫 | 只删守卫仍受最高层压制 +「先选一个处境」 | 随投影契约一起处理；该行的注入文案本身是对的，保留 |
| §10 删除 dependency 四分类 | 删掉了 `blocking[]` 的类型词汇 | 降级进 reference，与投影 token 统一 |
| §10 mode enum 分两级 | 造出同一概念的两个等级 | 四个 mode 整体保留 |
| §10 receipt / delta review「保留」 | 正文保证不了 | 搬进 `dispatch_audit.py` |
| §13.2 V01–V16 全部按模型行为评测 | §13.3 自己承认现有 eval 是只读问答，测不了执行习惯 | 见 §8 分层 |
| §13.1 顺序 A→B→C→D→E | 正文（B）在注入（C）还在反着说的时候无法验证 | 见 §7 重排 |
| §9.3 迁移表未覆盖 `worker-incomplete-first/second` | 与同 Skill 的 `runtime-protocol.md` 当前就冲突 | 随投影按 dispatch 归属一起改；次数只作观察事实，不驱动换人或 `BLOCKED` |
| §11.3 DSH `stage` 判断 | 事实错误，见 §6.1 | 直接改 `stage`；`text` 路由是可选项不是必需项 |
| §11.3 宿主验收「入口可达」 | 旧 Dispatcher 可达但内容错配，见 §6.2 | 验收改为「加载到的 Dispatcher 与 plugin 内容兼容」 |
| 全文 | 未提渲染句「先选一个处境，再选其动作」 | 它是显式单选命令，必须一并改 |

## 7. 重排实施顺序

每一步独立可发布、独立可验证，这是当前 A→E 顺序不具备的性质。

| 步 | 交付 | 验证 |
| --- | --- | --- |
| 1 | 输入合同 + 投影契约：`blocking` / `runnable` / `withheld` / `in_flight` 四段输出；trail outcome 类 fact 按 dispatch 归属（含 `_decision_without_result` / `last_outcome` / `_incomplete_count`）；渲染句改为「以下均可推进」 | fixture pytest，不动任何 Skill 正文 |
| 2 | `situations.yaml` 按新契约重标：`worker-still-running` 转标注、`multiple-ready-tickets` 去守卫、`worker-incomplete-first/second` 去次数门槛、finding 行去掉固定捆绑 | 复用 `tests/test_situation_render.py` fixture |
| 3 | Dispatcher 合并正文 + 两个 reference；删掉第 1/2 步之后 runtime 已经拥有的段落 | 结构合同测试 |
| 4 | 退役 SDD 目录 + 迁移 §11.2 的消费面 | 引用闭合扫描、宿主入口可达 |
| 5 | receipt / delta-review pacing 迁入 `dispatch_audit.py` | 该脚本自身的回归 |

第 1、2 步是一个**交付单元、两个开发步骤**：第 1 步单独落地时新键已存在，但旧表的 `in_flight` 守卫和 wait 默认动作还在过滤候选，所以不能声称已修掉机械串行；发布边界画在两步集成验证之后。第 1 步排最前是因为它不依赖任何 Skill 内容决定。第 3 步必须在第 2 步之后：正文一旦先落，第 2 步可能推翻它的措辞。

## 8. 验收分层

按"能不能由脚本判定"重新切分提案的 V 表——这是把 16 项模型行为评测降成 9 项确定性测试的地方：

**投影 fixture 测试（普通 pytest，无模型）**：V02、V03、V10、V11、V12、V13，以及 V05/V06 的合法性部分。给定 `state.json` + trail fixture，断言 `runnable[]` 含 X、缺席项在 `withheld[]` 里带正确的 dependency 类型 token、`blocking[]` 只在全局 fail-closed 时非空。V13 必须**带真实处境注入**验证，否则只证明了模型读懂新正文，没证明注入不再反着说。

补两个 fixture（提案与本文初稿都缺）：

- **同票乱序返回**：同 Ticket 的 A、B 分别派发，A 返回 `INCOMPLETE`、B 返回 `DONE`，断言 A 的未完成事实仍出现在投影里、B 不被重复派发、局部失败不扩大成整票 `BLOCKED`。这一条直接证伪或证实 §5.5。
- **代码已返回但审查未派成 + handoff**：断言恢复后能找回被冻结的增量、待派审如实保留、且不虚构成功 receipt。这是 V09 与恢复场景的组合。

**trail 事后审计（`dispatch_audit`）**：V01、V09。V01 是可计算的——「存在两条时间上重叠、subject 不相交的 open dispatch，且当时 runnable 中有 ≥2 个独立 subject」。V09 是「无 receipt 的 dispatch 不得被当作已派发」。

**真·模型行为评测（承认是采样）**：V04、V08、V14、V15、V16。这几项确实取决于主控当场的取舍，保留 eval 形式，接受它证明不了普遍性。

**关于"有效交付速度"**：直接比较基线版与候选版达到同一验收条件的耗时或轮次，方向对但不该进完成条件——单次运行的方差远大于这次改动的效应量，"少量重复"分不出信号，而做到能分出信号的重复次数不值这个成本。改用两个稳定的确定性代理：`dispatch_audit` 数「存在独立 runnable 工作时是否出现了并发 dispatch」，以及返工次数（同一 subject 的重复 fix 轮）。真实交付速度作为实跑观察记录，不作为放行门槛。

## 9. 兼容性约束（提案未写）

用户的实际运行时从安装缓存 `impl-package/0.4.2` 加载。投影输出结构变化会同时影响 `protocols.json` 注入与 Resume Capsule；缓存与源码半迁移状态下，一个进行中的 attempt 会拿到两套契约。

因此第 1 步的投影改造必须**向后兼容输出**：保留 `selected` / `parallel_matches` / `other_matches` / `suppressed_matches` 四个键继续按旧语义填充，新增 `blocking` / `runnable` / `withheld` / `in_flight`。旧渲染器读旧键仍可工作，新渲染器读新键。等宿主装到新版本后再考虑退役旧键。

## 10. 未做的事

本文只审查提案并给出目标形态，没有改写任何 Skill、没有改 `situation.py`、没有跑行为评测、没有动安装缓存。第 3 节的代码事实来自基线 HEAD `cb906e6` 的仓库源码，不是安装缓存。
