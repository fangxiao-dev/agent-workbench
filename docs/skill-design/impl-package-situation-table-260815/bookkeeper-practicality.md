# Standing bookkeeper 实用性复盘

分析对象是 Codex rollout `01a00a2a-d322-75c2-98ba-060723487fd2`，分析日期为 2026-08-16。这里的 `seq` 是仓库现有 [`extract_rollout.py`](./tools/extract_rollout.py) 生成的压缩时间线序号，不是 JSONL 物理行号。

## 结论先行

这次卡住的直接原因是：主控把一批已经形成的、主要是确定性状态写入交给了多个冷启动 LLM agent；输入中的 `environment`、claim `timing` 和 evidence 路径又没有在派发前形成并验证为一份不可变 manifest。agent/CLI 随后正确地停在各个校验错误上，主控则用反复 `wait_agent` 和重新派发把这个同步点放大成了约 29 分 54 秒。

我的结论是：**降级为脚本，散文部分交回主控。** 这不是取消所有异常恢复能力，而是把正常的结构化 bookkeeping 从 standing LLM agent 的关键路径移到 `impl_package_state.py` 的幂等批量事务；Execution Record judgment、findings 分流和 Spec 修订仍由主控/owner 形成并负责语义。这个结论对本案很强，但四个正式试运行读数都没有足够回执数据，不能冒充为对所有 package 的统计结论。

## 1. 卡在哪

### 1.1 目标写入批次

seq 848 的主控已经给出了完整业务结论：TAW-01 可验收为 `SATISFIED`，需要写入 Execution Record、evidence index、Ticket 状态、两个 active checkpoint，并做 validate/refresh。也就是说，本案的难点不是再判断 TAW-01 是否通过，而是把结论落到正确的 machine-owned artifact。

按语义目标计，这批内容是：

- 1 个 Execution Record judgment；
- 7 个 AC claim + 3 个 invariant claim 的 evidence；
- 1 个 `PENDING -> SATISFIED` 状态转换；
- `ticket:TAW-01` 和 `attempt` 两个 checkpoint；
- 1 次 progress refresh，以及验证命令。

### 1.2 交互时间线

| seq | 主控与 bookkeeper 交互 | 具体表现 | 判定 |
| --- | --- | --- | --- |
| 848–850 | 主控准备派发；首次 `spawn_agent` | 主控的 JS template literal 因 prompt 中未转义的内容失败：`SyntaxError: Unexpected identifier 'ticket'`；agent 根本没有启动。 | 宿主/派发层失败 |
| 852–878 | Dalton 收到完整的大 prompt；主控连续等待 | 5 个长轮询窗口都没有最终回执；seq 862 明说“目前没有回执”，seq 867 又发收口提示。 | 宿主没有及时返回；不是无证据证明 agent 没工作 |
| 881–887 | 主控中断并关闭 Dalton | 最终状态报告说已写入 `initial-ER-003`，并确认 AC-01～03 共 9 条 evidence；Ticket 仍 `PENDING`，checkpoint、refresh 和最终验证未完成。 | 部分写入，未闭环；主控没有自己手工写 |
| 890–907、912–925 | Locke 被要求用一次 payload 补 AC-04～07、3 个 invariant、satisfy、checkpoint、validate | 又经过 5 个等待窗口没有回执。主控 seq 906–907 读到 AC-01～07 已存在，但 Ticket 仍 `PENDING`、attempt checkpoint 仍是旧值；之后发送停止信号并关闭 agent。 | 再次部分推进/无回执；不应继续以同步门等待 |
| 944–963 | Carver 从已有 ER/state 开始补 3 个 invariant | 3 条 invariant 写入成功；`ticket satisfy` 因 invariant 的 environment 与 AC acceptance pair 不一致而失败，精确结果为 `SATISFIED missing claims: ...`。 | 接口输入不一致；CLI 正确拒绝 |
| 966–974 | 主控读取既有 evidence，试图修正 pair | 发现 environment 必须逐字复用；同时看到 AC evidence 已按 claim 存在，部分 claim 有多个 artifact pointer。 | 需要 manifest，而不是继续让 agent猜 |
| 975–986 | Planck 被要求复用完整 AC environment 并直接 satisfy | 只读预检通过，但 `ticket satisfy` 仍失败：3 个 invariant record 还没有落在同一 acceptance pair；后续 5 步未执行。 | 先前记录已落盘，但 pair 没闭合；严格停止 |
| 988–1001 | Descartes 被要求追加 invariant，使用 `timing=remaining-completion` | 第 1 条 evidence 就失败：`evidence timing does not match Ticket claim ...`；合约要求 `early-falsification`，3 条都未写入。 | 接口/合同字段错误；不是 agent 不会写 |
| 1002–1025 | Mill 改用 `early-falsification` | 3 条 invariant evidence 和 `ticket satisfy` 成功；第 2 步 checkpoint 因传入 `execution/initial/execution-record.md`，而 CLI 按仓库相对路径解析，报 `checkpoint evidence does not exist`；后续 2–6 步未执行。 | 路径层级错误；CLI 的路径合同没有被主控预先消化 |
| 1027–1030 | 主控总结问题并再次派 Mencius | 主控承认之前传错了 environment、timing、路径；新 prompt 先要求 `Test-Path`，并把 checkpoint evidence 改成完整 repo-relative 路径。 | 第一次真正做了输入预检 |
| 1036–1041 | Owner 追问“记账本来就是为了异步” | 主控停止等待，把 TAW-02 交给新 session；这是对原同步握手的纠正。此时 Mencius 仍在后台。 | 证明原先的阻塞不是业务依赖，而是编排选择 |
| 1056–1058 | Mencius 最终返回 | 路径预检和 5/5 命令均 exit 0：两个 checkpoint、validate、refresh-progress、再次 validate 完成；TAW-01 `SATISFIED`，ready ticket 为 TAW-02。 | 最终成功，但成功发生在主控已经放开主线之后 |

主控没有在最后“自己动手编辑” package artifact；它是通过不断读 state、修正参数、重新启动 agent，最后由 Mencius 完成物理写入。这个事实很重要：真正的浪费不是主控写了太多，而是为了执行机械命令启动了 7 个成功 agent、经历 8 次 spawn 尝试（含 1 次宿主语法失败）、18 次 `wait_agent` 调用和 25 次等待 cell 续接。首次派发到最终成功通知约 29 分 51 秒，到 close 约 29 分 54 秒。

## 2. 为什么卡

| 可能性 | 判断 | 证据与边界 |
| --- | --- | --- |
| 接口问题 | **是，主因之一** | 高层信息足够，但没有先锁定 `claim / timing / revision / environment / artifact path` 五元组。先后出现 environment 不匹配（944–986）、timing 不匹配（988–1001）和 package-relative/repo-relative 路径错误（1002–1025）。这是“信息有，但不可直接执行”，不是缺少业务结论。 |
| 握手问题 | **是，且是放大器** | rollout 没有按现行消息格式显式写 `依赖：是/否`，所以不能计算正式 `dep=true`。但行为上主控把它当成了 `依赖：是`：seq 862 说不会启动 TAW-02，seq 901 继续等待，seq 1036 Owner 才明确要求继续 Ticket 2，seq 1041 才放开主线。这个写入不应该成为实现前沿的同步门。 |
| 能力问题 | **弱，是预检能力而非语义能力** | agent 没有正确猜出路径、timing 或 pair，但它在遇到不合法输入时停止是正确的；当输入精确且先做路径预检时，Mencius 5/5 成功。没有证据表明 bookkeeper 找不到正确 artifact 或无法理解 TAW-01；有证据表明它缺少一次性 dry-run/manifest 预检。 |
| 冷启动问题 | **是** | 每次都是 `fork_context:false` 的全新 agent，重复携带 package、state CLI、claim、revision、environment、checkpoint 和禁止项。7 个 agent 都要重新建立相同上下文，且机械写入使用了高推理配置。 |
| 宿主问题 | **是** | 首次 spawn 直接因宿主 JS 语法失败；后续 `wait_agent` 只返回 `status={}`/timeout，不能给出阶段性 receipt；停止后也没有立即得到结构化写入清单。最后一次 agent 的成功通知是后台到达的，主控没有把它作为可消费的短事务 receipt。 |

因此“真正卡在哪”的优先级是：**同步编排/冷启动 > 未预检的结构化接口 > 宿主等待机制 > agent 自身能力**。CLI 的严格检查不是根因；它把错误输入变成了可见的停止点，反而避免了把错误状态写成成功。

## 3. 三种形态在本案中的成本

下面的“往返”分两层计数：A 给出 rollout 中实际发生的 host 交互；B/C 给出完成同一逻辑批次所需的语义调用数。把多个 CLI 命令塞进一个 shell wrapper 只会减少 host wrapper 次数，不会消除内部写入动作。

| 形态 | 本案会怎样 | 往返/调用成本 | 主控方法知识装载 |
| --- | --- | --- | --- |
| **A · 现役 agent** | 实际发生 8 次 spawn 尝试、7 个 agent；先后经历无回执、部分写入、environment、timing、路径三类失败，最后才完成。主控没有获得稳定的“理解/写入/验证/阻塞”短回执，也没有可观察的 `bookkeeper-receipts.jsonl` 行。 | 实际为 18 次 `wait_agent` + 25 次等待续接，另有 3 次 send/stop；约 29 分 54 秒。理想的一次成功调用本可只是 1 次派发 + 1 次回执，但这次没有达到。 | **高且重复**。主控和每个 fresh agent 都要装载 owning artifact 路由、state/trail schema、Ticket timing 合同、evidence tuple、repo-relative 路径、checkpoint/progress/validate 规则；至少 6 类方法知识被反复搬运。 |
| **B · 脚本/批量事务** | `impl_package_state.py` 接收一个 machine receipt：10 个 claim 的 evidence manifest、transition、两个 checkpoint、refresh 要求和验证选项。脚本先全量预检，再一次性幂等落盘；错误时返回 expected-vs-actual，不产生半成品。 | **1 次批量调用 + 1 个短 receipt**，可以异步；主控不需要等待它才能派发不依赖 checkpoint 的下一张卡。若 checkpoint 是下一步的硬依赖，只等待这个本地事务 receipt，而不是 LLM agent。 | **低**：主控只保留语义结论和 manifest/Execution Record 文本；脚本封装 artifact 路由、CLI 拼接、state/trail 形状、timing/environment/path 校验和 progress refresh。 |
| **C · 主控自己写** | 主控已经拥有结论，直接调用现有 CLI 完成。不会发生 agent 冷启动或长等待，但主控必须自己处理所有精确合同。 | 以“每个逻辑目标一次命令”计：1 个 ER judgment + 10 个 evidence + 1 个 satisfy + 2 个 checkpoint + 1 个 refresh，至少 15 个写入结果；再加两次 validate，即约 17 个 CLI 结果。可以由一个 wrapper 发出，但失败恢复仍由主控承担。 | **高但只装载一次**：主控需要完整的 artifact/CLI/contract/path 知识；没有 context 外包，但也没有 7 次重复加载。 |

这里 B 的前提不是让脚本从自由散文猜出验收结论。安全的脚本输入应是“已形成的语义结论 + 结构化 machine receipt”；自然语言只用于把 supplied judgment 原样写进 Execution Record，不能用字符串解析替代 Ticket acceptance 判断。

## 4. 散文与结构化的分界

### 4.1 按语义目标计数

| 类别 | 本案内容 | 数量 |
| --- | --- | ---: |
| 结构化 | 10 个 evidence claim group（7 AC + 3 invariant）、1 个 Ticket state transition、2 个 checkpoint、1 个 progress refresh | **14** |
| 散文 | 1 个 `initial-ER-003--judgment`，包含技术结论、证据解释、已知验证缺口和环境排除 | **1** |
| 合计 | 以逻辑目标而非重试次数计 | **15** |

所以按最不夸大的逻辑口径，结构化 **93.3%**，散文 **6.7%**。本案没有 findings 分流落笔，也没有 Spec 修订。

### 4.2 按实际 evidence 行展开

实际 state 输出显示 AC-01～AC-07 采用了每个 claim 3 个 pointer 的形状（ER anchor 加 source/code/contract 证据）；3 个 invariant 先写入了短 environment 记录，后又为匹配 acceptance pair 追加了 3 条精确记录。因此把重试产生的物理行也算上，是至少 27 条 evidence 行 + 1 条 state transition + 2 条 checkpoint + 1 条 progress projection，即 **31 条结构化记录**，对 1 条 ER prose judgment；该口径下结构化约 **96.9%**。

两种口径都指向同一个判断：这不是“agent 帮主控外包了大量理解力”的批次，而是一个几乎全由固定 schema、固定 CLI 和固定路径组成的批次。当前 [`situation-inputs.md`](../../../plugin-marketplace/plugins/impl-package/references/situation-inputs.md) 已把 trail/event/fact 的闭合形状写死；文件头实际写的是 **66 个**非 `manual` `when` key，而任务描述写的是 64 个，存在 2 个 key 的文档口径差异，但不改变“结构化前提已经基本具备”的判断。它仍不能替代 ER judgment 的成文理解。

## 5. 对四个试运行读数的核对

规则见 [`trial-readout.md`](./trial-readout.md)：正式数据源是 `bookkeeper-receipts.jsonl`，回执少于 20 条时任何阈值结论都不成立。

| 读数 | 本案能否填 | 证据与结论 |
| --- | --- | --- |
| R1 定位错误率 | **不能正式填** | rollout 中没有 `bookkeeper-receipts.jsonl` 行，也没有回执 `paths` 与 correction event 的配对。environment、timing、path 的修正是主控重新派发参数，不是可计入 R1 的 correction event。 |
| R2 握手频率/阻塞时长 | **不能正式填，可作定性反馈** | 没有 `dep=true` 字段，不能算占比或逐条发起到回执的时间差。可观察到首次派发到最终成功通知约 29 分 51 秒、到 close 约 29 分 54 秒；seq 1036/1041 又明确表明主控本应继续 TAW-02。因此 R2 的问题信号很强，但不能套用“>50%”阈值。 |
| R3 越界写入次数 | **不能正式填** | 没有回执 `paths`，无法证明 0，也没有证据显示写到了 package 外。可见最终写入路径都属于 package state/progress/checkpoint/ER；这只能是观察，不是 R3 计数。 |
| R4 落盘漏记率 | **不能填** | rollout 没有目标 package 的 `git log` 与 receipts 行数交叉校验，也没有可证明的 receipts 文件样本。不能把“聊天里没有 receipt”直接当成漏记率。 |

因此本案四个读数的正式样本量都是不可用/低于 20，不能触发 R1/R2/R3/R4 的阈值结论。能填的是定性事实：正常机械写入被 LLM/宿主等待拖慢，并且记录合同本身没有在本案产生可审计回执。

## 6. 最终建议：降级为脚本，散文部分交回主控

保留“异步 sidecar”这个吞吐目标，但把正常路径改成确定性脚本：

1. 增加类似 `impl_package_state.py bookkeep/apply-receipt` 的批量入口。输入是结构化 receipt，而不是让 agent 从自然语言重新拼 CLI 参数；至少包含 package/attempt、claim/artifact/revision/environment/timing、transition、checkpoint 和是否 refresh。
2. 脚本先做全量 dry-run：验证 claim timing、同 revision/environment pair、artifact 存在性、subject scope、repo-relative 路径、当前 Ticket state 和幂等键；全部通过后再写 evidence、state transition、checkpoint、progress 和 trail。失败返回 expected-vs-actual，避免本案这种“前面已经写了，后面才发现 pair/path 错”的半事务。
3. 主控保留 semantic ownership：形成 ER judgment，决定 evidence 是否 supporting，做 findings disposition 和 Spec 修订。脚本可以把主控提供的 prose 原样落到正确 artifact，但不负责理解、改写或自行产生这些判断。
4. 默认异步。只有下一动作确实依赖 checkpoint 时，主控才等待脚本事务 receipt；`依赖：是` 不再意味着等待一个长寿命 LLM session。
5. standing agent 只保留为 slow path：证据互相矛盾、需要恢复历史、需要解释/修订散文或需要异常对账时再派。那时它的价值是理解和修复，不是逐条执行 `evidence add`/`checkpoint`。

代价是主控不能再把 Execution Record 的成文工作完全外包，脚本需要一次性实现批量事务、幂等和验证测试；但这是把约 93% 的固定形状写入从每次重复支付的上下文/等待成本中拿回来。以本案为证，继续保留现役 agent 作为默认 fast path 的收益不足以覆盖它引入的 7 次冷启动、严格参数往返和近 30 分钟关键路径阻塞。

