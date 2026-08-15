# Impl-Package 处境表改动：大局观

## 整体判断

本轮盘点的范围是审计报告中的 248 个产出、六份 replay、现役 Impl-Package 和并行中的 standing bookkeeper 设计。机械审计、replay 合并和当前 fixture/check 读数已经产出；但新件尚未接入 runtime，9 条文档口径尚未修、9 个候选项尚未处置，独立性更强的 fixture 复验也未完成，所以整个改动不能称为 closed。建议 Owner 把“先证明当前模型，再接入 `dev-with-track`，最后降载散文规则”作为主线；兼容物退休暂不与接线混做。

下文引用的机械事实以 [stocktake-audit.md](stocktake-audit.md) 为准；它的结论是证据索引，不是本文件要重复的清单。

## 1. 现在这套体系长什么样

```text
Impl-Package
├─ 语义层：各 owning stage 持有“这件事是什么意思、何时算完成”
│  ├─ req-align → Decision / Spec / contract
│  ├─ impl-planning / plan-review → Plan、Composition、批准与可执行性
│  ├─ to-tickets → Ticket 的纵向验收切片与 typed dependency
│  ├─ dev-with-track → investigate、route、implement、fix、verify、finding、Gate
│  ├─ subagent-driven-development / do-review / verification / safety-review
│  │  分别持有 worker 调度、review topology、完成声明审计和实现安全审查
│  └─ standing-bookkeeper / backfill-stable-docs → 物理记账边界与长期知识回刷
├─ 契约层：Composition Contract、Current State、progressive evidence 等
│  规定 artifact 位置、Ticket-only 组合、证据与恢复边界；不替 stage 做语义裁决
├─ 状态层：.impl-package/state.json + impl_package_state.py
│  state.json 是 current state 的权威；CLI 拥有状态转换、CAS、证据、checkpoint、Gate
│  的机械写入/校验。bookkeeper 负责按 owning stage 执行物理写入，但不拥有这些语义。
└─ 今天新增的规则投递层（现在仍是旁路原型）
   ├─ skills/dev-with-track/situations.yaml：55 行处境→动作规则、默认执行者与机械后果
   ├─ scripts/situation.py：只读地从 state、Ticket、evidence、Gate、finding、Git、trail
   │  推导 selected / parallel / secondary / unknown；只提供 render、print-table、check
   ├─ trail-schema.md：计划中的 execution/<attempt>/trail.jsonl，记录选择、返回、escape、
   │  unmatched 与恢复线索；它是草案，当前没有现役 writer
   └─ 目标循环：render → 主控选择 → 执行/派发 → append trail → 再 render
      审计已确认这条循环目前没有 caller，因此“规则投递”还没有发生在真实执行链里。
```

边界可以压成三句话：stage skill 拥有语义，state CLI 拥有状态，处境表/推导器/轨迹只负责把静态规则按当前事实送到主控面前并留下选择证据。`do-review` 仍拥有 review topology，`subagent-driven-development` 仍拥有 worker strategy；处境表只能给默认动作，不能接管它们。

“现役 12 个 skill”是审计为主流程采用的 12 个分组，不是插件 manifest 的权威目录数；仓库实际有 19 个 skill 目录，另含 legacy、router、辅助和 reviewer leaf。这个差异不能被当成新体系已经有 12 个统一入口的证据。`thread-harness` 是相邻的成熟协调体系：它用 registry/ledger、H1、stall-check 做“测量并暴露停滞，不替 Owner 阻断”的协调层；处境表借用了这个取向，但处理的是 package 内每轮动作，不是跨 thread 的 session 路由。

## 2. 今天到底改变了什么

以前的流程规则主要住在 `SKILL.md`、各 reference 和共享契约里：入口一次性加载，之后被工具输出淹没；当前位于哪一步没有 durable carrier，每轮靠聊天重推导；规则是前置批量送达，不是在动作发生时重新投递。Ticket、state、`evidence add` 有载体，所以较稳定；`investigate` 和 `subagent-driven-development` 的 mode 策略没有载体，正是容易蒸发的部分。问题不是“模型不遵守”，而是规则没有缺席信号。

今天新增的机制把这环节拆开了：表把与具体事实无关的合法动作、前置、载体、默认执行者和机械后果声明出来；推导器每轮只读当前事实，给出当前行和不确定原因；轨迹把实际选择、返回、逃逸和未命中变成可查询历史。它因此把主控的工作从“记住整套流程”改成“读当前处境并作判断”，同时保留只引导、不阻断的姿态。55 行中 44 行是机械/记忆行、11 行需要判断；当前正式表只有 13 行有 CLI 强制，42 行仍是 `prose` 赌注（见 `README.md` §6、§9.6）。

这次真正触及的是规则的注意力、当前位置推导和缺席可见性，也暴露了 61 条多重命中和 39 批 evidence timing 不可观测的问题。完全没有触及的包括：

- runtime caller、action dispatch 和 trail writer 尚不存在；所以行为没有改变，`check: PASS` 不是 runtime 接入。
- 不改变 stage 语义、Ticket acceptance、state schema、Gate 判据，也没有把 `impl_package_state.py` 变成自动记账器。
- 不解决表漏列合法动作的根风险；表会沉默，逃逸/unknown 只是缓解，不是完备性证明。
- 不提供 3.5 真实 package 的经验覆盖，不替 Owner 做多个业务结果、来源冲突或证据是否足以支持 claim 的语义判断。
- 不完成 standing bookkeeper §19；现役 receipt 仍是 `done|blocked`，`NEEDS_SPLIT` 等仍是 proposed contract。
- 不把 req-align/impl-planning 的 planning lifecycle 纳入 `dev-with-track`；replay 的 M01 仍应表外处理。

审计列出的 9 条文档不一致，本质上是“旧 42 行数字/历史 replay 标签”“consolidated 的未 apply 状态、路径和 grammar 陈旧”“YAML 已部分吸收但 trail schema 未对账”“bookkeeper proposed receipt 被写成现行”“README 对人读枚举的权威性含混”五类口径问题；没有一条说明 runtime 已经接通。

## 3. 关键读数与可信度

| 读数 | 能证明什么 | 可信度与偏差 |
| --- | --- | --- |
| 六份 replay：240 个决策点，167 个主命中，命中率 69.6%，61 条多重命中 | 当前表对旧真实时间线的映射质量，以及 priority 重叠是主要风险（61/240=25.4%） | 作为六份 overlay mapping 的机械汇总可信；作为当前 3.5 runtime 行为的预测只有中低可信。全部输入来自 3.2/3.4 时代 package，两个业务仓库里零个 3.5 package；再叠加分片、旧工具版本和截断，不能把 69.6% 当成现行命中率或执行违规率。 |
| evidence 未入账 39 批 | 5 批严格确认“return 后先推进、之后才入账”，另 34 批只能判 evidence-limited | 这是“可观测性/记账成本有问题”的强信号，不是 39 次永久漏记。权限边界、nested tool-call 和输出截断都可能遮住 `evidence add`；因此不能据此直接把 prose 行升为 observed。 |
| fixture 测试 50/50 通过；覆盖 55 行中的 51 个可见命中，另验证 1 个 suppressed 行，即 52/55 | 当前 parser/render、priority suppression 和 fixture 期望在这批场景上自洽 | 对实现回归是中等可信，对规则正确性和生产泛化是低可信：造 fixture 的作业能读取处境表和推导器，50/50 全绿缺乏独立性保证；fixture 主要由两个 legacy 源仓库的 3.2/3.4 package 翻译而来，且测试消费者仍未纳入 tracked suite。 |
| `python ... situation.py check`：PASS，55 situations、64 implemented when keys、6 priority groups | YAML 结构、slug/priority/when parser 的静态一致性 | 对“脚本能读这张表”高可信；对“表的判断正确、运行时会调用它”不提供证据，因为校验与实现来自同一 CLI，且审计已找到零个 skill/runtime caller。 |

所以最不可信的单个“好消息”是 50/50 fixture 全绿：它最接近端到端，却缺少独立 oracle；69.6% replay 至少还有明确的旧版本偏差和 evidence 边界声明。

## 4. 从躺着的数据到真正在跑，缺哪几根线

| 缺口 | 接上后会改变什么 | 主要风险与护栏 |
| --- | --- | --- |
| `dev-with-track` 主循环的 caller：restore 后、每次动作后调用 `situation.py render --json`，传入 package/attempt/subject，并消费 `selected`/`parallel_matches`/`unknown` | 当前一轮的合法动作会在动作发生前重新出现；跳步、unmatched 和 unknown 当场可见 | 误把 renderer 变成阻断器、重复派发或把低层 secondary 当 primary。首版只做提示；保留结构化 JSON，human 输出把“无法判定 82 行”折成计数，细节留 JSON，控制在 150 token 目标内。 |
| action adapter：把表内 action id 映射到既有 `sdd`、`do-review`、state CLI、bookkeeper 或主控判断 | 默认动作不再只是名单，而能进入现有 stage 流程 | 产生第二个 workflow engine 或越权替代语义 owner。adapter 只做薄映射；规则仍由 owning skill 执行，业务判断仍回主控，表不能直接写 state。 |
| trail lifecycle/writer：初始化 `execution/<attempt>/trail.jsonl`，追加 decision/result，维护 `seq`、`head`、`of`、subject，识别悬空派发、escape 和 unmatched | “派了没回来”“选了什么”“跳过什么”成为 durable signal，跨 session 可恢复、事后可统计 | 多 writer、重复 seq、半行和 terminal 后继续写会污染历史。首版按草案显式写行，做原子 append/格式校验和 terminal freeze；不要先把写行偷偷塞进 CAS 状态命令。 |
| fact/contract adapter：给 `when` 提供稳定的 package validate、worker mode/envelope、evidence return→intake→index 和 Git comparison head 事实 | renderer 能区分“证据不存在”和“证据存在但未入账”，priority 才有可靠输入 | 缺事实被静默当 false 会制造假安全；未知必须保留为 unknown。`trail-schema.md` 中 42/55 统计、worker/evidence timing 字段和 consolidated 提案必须先对账。 |
| per-package override 与恢复边界的正式入口 | package 可记录有意裁剪，而不是把跳过伪装成忘记；恢复时从 state/checkpoint/trail 尾部重建 | override 变成后期泄压阀，或 progress projection 绕成推导输入。沿用现有 CLI 已支持的 `package/situations.yaml` 合并规则，要求 git 可审查，`progress.md` 仍不作 authoritative input。 |

这几根线接通前，新增件只是独立设计源和只读 CLI 原型。接线的第一版不应改 state engine；若为了“自动记轨迹”先动 `impl_package_state.py` 的 CAS 路径，应停下来重新评估风险和读数价值。

## 5. 路线与依赖顺序

建议的依赖图是：

```text
冻结当前 55 行基线
├─ 独立性更强的 fixture 复验 ─┐
├─ 渲染噪音 + 9 条文档口径修复 ├─→ priority / intake / schema 决策闸门
└─ standing bookkeeper 回执试运行 ┘              │
                                               ↓
                                  dev-with-track runtime 接线
                                               ↓
                                  SKILL.md 降载与回归验收
                                               ↓
                                  其它 stage 铺开（远期）
```

因此必须串行的是“基线复验 → 契约闸门 → runtime 接线 → SKILL 降载”；可以并行的是基线捕获后的 renderer 修复、文档口径修复和 bookkeeper 试运行。其它 stage 铺开与兼容物退休都不能插入 runtime 接线之前。

1. **先冻结基线并做独立 fixture 复验（必须串行在表改动之前）。**
   前置是暂不改 55 行、priority 和 renderer 判定；产出应由不读取 YAML/推导器实现的独立 oracle 生成期望，至少复跑现有 50 个并补齐 3 个未覆盖行/边界。风险是复验会推翻当前表；如果 mismatch 集中在 priority、3.2→3.5 翻译或同一类 `when`，先改模型，不得升 basis、接 runtime。

2. **基线捕获后，三条低耦合线可以并行。**
   - 修 renderer human output：`无法判定 82 行` 只保留计数，JSON 保留完整名单和原因。
   - 修 9 条文档口径：先改 42→55 的历史标注、consolidated 的时间边界/路径/已吸收状态，再对账 trail schema、bookkeeper receipt 与 README 权威性。它们是文档一致性 apply，不是 runtime apply。
   - 继续 standing bookkeeper 试运行，按 `trial-readout.md` 取 R1–R4。少于 20 条只能定性；R1 在 10%–20% 不下结论，R1>20% 或 R4>30% 都应阻止过早固化 §19/自动记账。
   如果这组三条线发现“正式来源”无法唯一确定、renderer JSON 合同被破坏，或 receipt 语义仍只能靠猜，就停在文档/试运行阶段，不进入契约闸门。

3. **在第 1 步通过、且第 2 步的 receipt/文档边界可解释后，串行做规则契约闸门。**
   产出是：唯一 priority P0–P5、是否吸收 replay 的高频候选行、return→intake→index 的 evidence intake 契约、trail 字段和 150-token 渲染约束。建议先处理 N21 comparison head、N05 handoff、N20 integration carrier、N18 reviewer unavailable、N15 envelope、N13 closure review、N09–N12 record 行；M01 `ticket.plan.lifecycle-boundary` 留在 `dev-with-track` 表外。若仍没有任何 3.5 真实 package，或 61 类多重命中在新 priority 下仍不能稳定选出 primary，就停在 advisory mode，不接行为。

4. **再在 Owner 指定 worktree 接入 runtime（必须串行）。**
   前置是契约闸门、独立 fixture 结果和 hook/action/trail 接口已写清。产出是 restore/loop caller、薄 action adapter、显式 trail writer、focused fixture/replay smoke，以及 package override 的审计路径。风险是重复派发、subject 错配、stale fact 或把表偷偷变成 state machine；任一动作无法从“render→选择→执行→trail”重放，都应停止并退回接口设计。

5. **runtime 接线验证通过后才做 SKILL.md 降载（必须串行）。**
   只从散文中卸掉已由表和 renderer 稳定承载的机械规则，保留语义 owner、判断边界、escape、unknown 和 fallback 指针。若先卸载，表一旦漏判就没有可用 fallback；即使 Git 上可恢复，也不应把它当成安全的可逆试验。降载后需重新跑 L0/L1 focused checks，并用一次真实/仿真的 compaction 恢复确认规则仍会被投递。

6. **退休与其它 stage 铺开是后置工作。** 前置是第 5 步已经有 runtime 回归证据，且每个兼容物的依赖都有清点；产出是历史材料的归档决定、3.4 兼容链的独立 deprecation 计划，以及其它 stage 是否复用同一合同的决定。风险是把“新 package 不调用”误读成“旧 package 不需要”；如果发现仍有活动 3.4 package、外部消费者或 stage 间的 trail 语义不一致，就停下来重新划边界。缓存清理和历史文档归档可在依赖满足后分别处理；3.4 compatibility 必须成组、最后处理。其它 stage 只有在 `dev-with-track` 的通用 trail/renderer/unknown/override 合同跑稳后才值得铺开；否则是在复制未接通的原型。

不可逆点要单独看：代码和文档修改可由 Git 回退，但第一次写入 live `trail.jsonl` 不是普通试验——slug、action id、subject 和 seq 会成为 append-only 历史，改名会制造兼容层，而设计明确拒绝同义词表。因此必须在第 4 步之前冻结 namespace、priority、action id 和 terminal freeze 规则。候选文件的删除是破坏性操作，也必须 Owner 明确批准，但若已保留 Git/归档证据，属于可恢复的文件层动作。

## 6. 退休清单与顺序

这里的“退休”是处置建议，不代表本轮已删除。顺序按“先无语义价值、再历史材料、最后兼容链”排列。

1. **#9 两个 Python 缓存：现在可退休，确认没有生成进程后清理。** 没有代码、测试或合同依赖，损失只是本地加速；不应把它们和源文件一起提交。
2. **#4 `.test-tmp/replay-timelines/`：独立复验和 replay 结论归档后再删。** 当前 map/replay 的可复核输入依赖原始 JSONL 与抽取脚本；删早了会损失重建时间线的 provenance。它是 ignored 中间物，不是第二 runtime，但目前还不能说无价值。
3. **#1 早期 `replay/case-3.md`：改标“旧版/不纳入 consolidated”，之后再归档或退休。** 当前主动依赖只有早期 provenance；`consolidated.md` 明确忽略它，较新的 `map-case3.md` 承担完整映射。退休会失去早期超时/中断时间线，须等新映射和独立复验不再需要重现它。
4. **#2 `situation-table-dev-with-track.md`：不删除，先降级为设计史。** README §6、Owner review、回放解释仍依赖其枚举、basis 和分组统计；YAML 是事实源但不能替代推导过程。等 `print-table` 输出、README 权威性和独立 oracle 都稳定后，才可归档。
5. **#5 `replay/consolidated.md`：先修陈旧声明，再决定归档。** 六份 map 的去重、23 条候选、61 条多重命中和 39 批 evidence 结论都依赖它；退休前必须把“当时未 apply”改成时间边界，并把已吸收/未吸收/只改 YAML 未改 schema 分开，否则会丢失 Owner 决策 provenance。
6. **#3 standing bookkeeper 设计 §19：保留到试运行裁决之后。** 现役 SKILL/role、`trial-readout.md` 和后续 eval 方向都需要它解释 bounded write unit、`NEEDS_SPLIT`、`unexpected paths`；但它现在仍是 proposed，不可当现役 contract。只有 receipt 数据达到可判定样本并已把结论 apply/明确否决后才可归档。
7. **#6 `create-task-dag/` 与 #8 `validate_ticket_first_migration.py`：在同一条 3.4 deprecation 线上最后处理。** 前者仍被 legacy router、旧包恢复和测试读取；后者仍被 migration runbook、admission 测试和 subprocess 断言调用。当前没有活动 3.4 package 的证据，不等于依赖已经消失；退休前要有 3.4 inventory、迁移窗口结束和测试/路由替代物。
8. **#7 Composition Contract 中 `dag=false` 兼容占位：最后退休，且不是本轮。** 它仍被 3.5 Ticket-only runtime、composition 校验、plan 模板和 migration 边界共同依赖；删除会把“Ticket-only”误读成“无合同”。只有 runtime phase B 明确移除兼容字段、validator/tests/docs 同步完成后，才可作为一个独立重大变更处理。

最终取舍是：#9 是唯一可以低风险即时清理的项；#1/#2/#5/#3 主要是“修口径后归档”，不是简单删除；#6/#7/#8 是现役兼容链，不因“新流程不用”就退休。这样既消除陈旧信息，又不把历史证据和 3.4 恢复能力误删。
