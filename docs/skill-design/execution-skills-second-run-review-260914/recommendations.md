# 第二次实战复盘的推荐优化范围

日期：2026-09-14
状态：推荐清单，待 Owner 挑选。证据来自 [report.md](report.md)，本文只写「改哪里、改成什么、怎么验收、不改什么」。未修改任何 Skill、runtime 或 rubric。

## 0. 取舍原则

- 只改引导，不加门槛：不新增 hook、阈值、清单或 gate。
- 验收挂在已有检查上：Skill validator、`tests/test_dispatcher_contract.py`、`tests/test_impl_package_state.py`、do-review 三轨合同、stage evals。
- 不重提上轮已否决项：15/30 分钟门槛、候选清单、bookkeeper、自动换 session、Loop 十轮上限、通用 `PreToolUse` 校验 hook、全 lane 同 HEAD 门槛、E4、backfill 全局不阻塞条款。
- OF-01..04 只补复发证据，不做干预实验。
- call-grok 是临时替换，不进 Skill。
- 版本仍 `0.4.2`，改 runtime 不自动 bump。

## 1. 核心项：让四条执行原则 stand out

### 1.1 四条原则与它们现在的位置

Owner 每个 session 开工前贴的「调度行为补充」，去掉 grok 那行后是四条：

| # | 原则（Owner 措辞） | 现在写在哪 | 写法 |
| --- | --- | --- | --- |
| P1 | impl（两个 role）、fix 都是角色不是载体，可按需并行创建多个 | [`dispatcher/SKILL.md:26`](../../../skills/dispatcher/SKILL.md)「同一 profile 可并行派发多次」；`:30` 对 investigate/fix/verify 只说「沿用现有判断」 | 只覆盖 frontend/backend profile；通用角色没写 |
| P2 | 载体可以有自己的 worktree；业务可分割但物理文件不可分割时开多个 wt，fix 同理 | [`resource-isolation.md:18`](../../../skills/dispatcher/references/resource-isolation.md)「独立 worktree 只隔离文件」 | 在 reference 里，且该页只在「存在多个候选、共享可变资源、隔离 worktree 时」才读——想到 worktree 才会去读讲 worktree 的页 |
| P3 | 先分析前置 foundation/seam，再 fan-out，避免补丁和返工 | [`impl-planning/SKILL.md:23-24`](../../../plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md)「先核实真实 caller、复用入口、依赖产物…只提前开展能独立实施并验证的工作」；[`resource-isolation.md:9`](../../../skills/dispatcher/references/resource-isolation.md) `foundation` 行 | 在设计阶段 skill 和一张表里；执行阶段的 dispatcher 正文没有这句 |
| P4 | Ticket ready 只是 ticket 粒度的依赖，不是执行层面的 dependency；可以提前调研甚至开始无依赖的 lane | [`dev-with-track/SKILL.md:13`](../../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md)「`implementation` edge 阻止绑定未稳定语义的实现」（语义是对的）；[`dispatcher/SKILL.md:13`](../../../skills/dispatcher/SKILL.md)「局部 barrier 只扣住受影响候选」、`:42`「dependency 词汇…逐候选限制动作，不构成全局暂停」 | 用的是 `effect footprint`、`dependency 词汇`、`局部 barrier` 这类抽象词，没有一句说「ready 不是执行 dependency」 |

结论：四条都有承载，但分散在 3 个 skill + 2 个 reference 里，用的是抽象词，没有一处是 Owner 贴的那种「四行、具体、能直接照做」的形态。

### 1.2 为什么被淹没：启动时读了什么

执行 session 开工时主控一次性读的材料（report §6、各 worker 第 6 节）：

| 切片 | 一次读入 | 体量 |
| --- | --- | --- |
| W4 L46 + L53 | dev-with-track、dispatcher、call-grok、execution-boundaries、ponytail 5 个 SKILL + composition-contract、current-state、progressive-system-evidence、delegation、resource-isolation、caller-contract、runtime-protocol 7 个 reference | ≈ 60 KB |
| W2 L137 | dev-with-track、execution-boundaries、dispatcher、ponytail | 22 KB（单次输出） |
| W7 L55 | execution-boundaries、dev-with-track、dispatcher、ponytail | ≈ 25 KB |
| W6 | 只读了 delegation.md、resource-isolation.md；dispatcher 本体没读 | — |

dispatcher 本体 6.7 KB，在这一堆里占 10–15%，四条原则又分散在其中的三处，其余是 receipt、trail 字段、handoff 路径这类协议细节。`[$dispatcher](path)` 引用在本批多数 session 里**不注入正文**（W5、W6、W7 零 `<skill>` 命中），所以「用户引用了」不等于「主控读了」。

Owner 贴的四行为什么有效：短、具体、用业务词、**紧挨着第一次派发之前**到达（W2 L145 → 首次 spawn L310；W3 L312 在三个只读调研之后、第一次 implement 之前；W7 L246 在准备派 backend/frontend 之前）。这四个性质就是改法。

### 1.3 改什么

**R1a · dispatcher 开头加「执行原则」块。** 在 `dispatcher/SKILL.md` 的 `## 执行循环` 之前加一节 `## 执行原则`，4 行，用 Owner 的措辞，每行括号指向展开段落：

- 角色 ≠ 载体：`investigate | implement | fix | verify | review` 和 `frontend-worker | backend-worker | luna-worker` 都可以同时有多个实例；实例数跟随可独立验收的候选与 write ownership，不跟随角色种类（→ Implementer executor、并行与复用）
- 载体可以有自己的 worktree：业务可分割而物理文件不可分割时，先分 worktree 再集成；impl 与 fix 同理（→ Resource Isolation）
- 先 foundation/seam 再 fan-out：共享契约、数据形状、共同前置先固定并 checkpoint，之后业务 lane 并行；不为并行而并行（→ 执行循环第 2 步）
- Ticket ready 是 Ticket 粒度的验收依赖，不是执行 dependency：`implementation` 边只挡「绑定未稳定语义的实现」，只读调研、child-local 测试、无依赖 lane 随时可以开始（→ 并行与复用、dev-with-track 第 2 步）

正文其余段落不复述这四句，只被指向。`:42` 的「dependency 词汇…逐候选限制动作」保留，但在它后面补一句具体的：「`implementation` 边只挡绑定未稳定语义的实现」，与 dev-with-track `:13` 用同一句话。

**R1b · 入口指向原则块，而不是整份 skill。** 三个入口：
- `dev-with-track/SKILL.md:14`「应用 `$dispatcher`」改成「形成第一份 brief 前先读 `$dispatcher` 执行原则（4 行），形成 brief 时再读 Delegation」。W6 就是从这一步直接跳到 references、跳过了本体。
- `handoff-to-new-session` 的 continuation card（[`SKILL.md:35`](../../../skills/handoff-to-new-session/SKILL.md)「它指向 owning skills，不展开其执行方法」）加：指向 `$dispatcher` 执行原则锚点。交接是本批 4 个执行 session 的起点，也是 Owner 贴四行的时刻。
- `impl-package/SKILL.md` 路由到执行阶段的那一行同样指向原则块。

**R1c · 启动读取减量。** `dev-with-track/SKILL.md:8`「先读 composition-contract 和 current-state；涉及 material seam 时再读 progressive-system-evidence」——改成按需：composition-contract 在写 evidence/claim 时读，current-state 在恢复或核对 state 时读；开工必读只剩 execution-boundaries 的授权边界段 + dispatcher 执行原则。这一项是让原则块有机会被看到的前提，不是新规则。

**R1d · 抽象词换具体词。** `dispatcher/SKILL.md:44`「并行按当前动作的实际 effect footprint 判断」后补「写集不重叠、验证 oracle 互不改变的 lane 可以同时跑」；`:13`「局部 barrier 只扣住受影响候选」后补「有 worker 在途不是等待理由」。不改语义，只加一句能照做的话。

**验收**：`tests/test_dispatcher_contract.py` 加「执行原则节存在、四条各有指向」断言；`tests/test_handoff_to_new_session_contract.py` 加 continuation card 含原则锚点；dev-with-track validator。行为验证只能等下一批 rollout：Owner 不贴四行的 session 里，第一次派发前有没有读原则块、profile 与并行度是否正确。

**可选（待 Owner 决定）：处境注入。** `situation.py render` 是主控读得最勤的东西（W1a 15 次、W2 21 次、W6 34 次），比任何 skill 正文都靠近决策点。可以在两个处境下各加一行提示：`in_flight` 非空且 `runnable` 非空时「在途 worker 不阻塞独立候选」；PENDING Ticket 的 `implementation` 边未释放时「只读调研 / child-local 可先做」。这是上轮诊断里说的「额外投影注入」，纪律是**不做效果声明**——可以加，但不能说它解决了 OF-01，效果要等下一批看。

### 1.4 不改什么

- 不把四行写进 checkpoint / continuation 文本本身（那是每次交接手打一遍，本批 W4 L38 已经证明这种做法会漏）。
- 不加派发前的机械校验。
- 不为 grok 写任何绑定。

## 2. 其余推荐项

### R2 · terminal-final 的启动时机与 fix 后的路由

**证据**：report §1 第三行、§4.1。W1b terminal 3 轮（用户 L15553「本次 terminal 后再有问题 closure 就够了」）；W4 TKT-02 4 轮；W7 TKT-02 4 轮 + TKT-03 2 轮，L4166→L6471 约 1.5 小时 27 次派发只为关一个 ticket。

**现状**：规则在 do-review——[`SKILL.md:34`](../../../plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md)「`terminal-final` 在已知仍会改变实现或合同的事项闭合后启动」、`:49`「`finding-closure` 只用一个 independent reviewer」、[`review-topology.md:34`](../../../plugin-marketplace/plugins/impl-package/skills/do-review/references/review-topology.md) B/C/Safety 按 admission 复用旧 PASS。缺的是 dev-with-track 侧：[`SKILL.md:62`](../../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md) 只写「启动条件与结果复用遵循 do-review」，没说 terminal FAIL 之后下一步是什么。

**改什么**：`dev-with-track/SKILL.md` terminal 段与 `situations.yaml` 对应 situation：terminal FAIL/INCOMPLETE 后走 fix + `finding-closure`（一名 reviewer 核对点名 findings）；accepted findings 全部闭合、没有在途 fix、HEAD 不再变化时才再起一次 terminal-final。do-review §5 报告露出「本轮哪些 track 复用了哪个 PASS HEAD」。

**验收**：do-review 三轨合同 + `tests/test_dev_with_track_situations_review_vocabulary.py` 不变；dev-with-track stage eval 加一个场景：terminal FAIL + accepted finding 未闭合 → 期望 `dispatch-fix` → `finding-closure`，不是 `terminal-final`。

**待 Owner 决定**：各轨默认档位。W3 要「全部 luna/max」，W4 要「A 用 sol/medium 其余 luna/max」，都是现场指定，W4 因此作废重跑 82.5 agent-分钟。固定到 `reviewer-registry.json` 或 `agents/review-track-*.toml`，固定成哪套，由 Owner 定。

### R3 · evidence 登记：可抄的批量模板

**证据**：report §1 第一行、§4.2。真正批量 3 次，逐条约 150 次；W7 两次批量尝试失败（L6979/L6985）后退回逐条。

**现状**：唯一范例 [`situations.yaml:223`](../../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml) 用 `printf`，8 个 rollout 没有一次读到；runtime 已支持数组（`engine.py:1195-1229`）。

**改什么**：`situations.yaml:223` 的 `do` 给两种可直接抄的形态——bash `printf ... |`；PowerShell 先 `Set-Content` 临时 `evidence.json` 再 `Get-Content -Raw evidence.json | python ... evidence add`。加一句「多条一律数组，一次登记一个 revision」。同一段放进 [`runtime-protocol.md`](../../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md) 的 evidence 部分。

**验收**：`tests/test_impl_package_state.py` 现有单条/批量对照不变；situations validator。

**待 Owner 决定**：terminal 每次 HEAD 前移的全量重登记（W6 5 轮 × 28 claim）是 runtime 强制的——`_evidence_coverage_for` 要求每条 claim 在同一 revision + environment 下有 supporting 记录。要省就得让 runtime 把未受影响 claim 的记录搬到新 revision，这是验收语义变化，上轮明确不动；本轮只列为决定点。

### R4 · Ticket 依赖粒度：默认 acceptance，主控可自行降级

**证据**：report §3.2 第 1 条。JP-308、#309、#304 三个包都写 `implementation:`；#309 主控 L2010 看出粒度过严，等到用户 L2016 才改；#304、JP-308 都要用户问「ticket 02 能不能先做」。

**现状**：[`impl-planning/SKILL.md:24`](../../../plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md)「按整票真实阻塞选择 `implementation / acceptance / release`」没有默认值和判据；[`dispatcher/SKILL.md:42`](../../../skills/dispatcher/SKILL.md)「真实 implementation dependency 与授权仍由业务 owner 决定」——这句让主控看出问题也不敢改。

**改什么**：
- `impl-planning/SKILL.md:24` 与 [Ticket 模板 `:46-48`](../../../plugin-marketplace/plugins/impl-package/skills/to-tickets/assets/templates/ticket.md)：默认 `acceptance`；只有下游没有上游产物就无法实现或无法做 child-local 验证时才写 `implementation`，依赖行后一句话写出该产物。
- `dispatcher/SKILL.md:42`：package 自己写的 `implementation` 边，主控按上述判据核实后可降为 `acceptance` 并记一条 judgment Execution Record；升级和 Owner 明示的边归 Owner。

**验收**：`tests/test_impl_package_state.py` 加「编辑 Ticket 依赖后 readyTickets 变化」；impl-planning stage eval 加「上游只挡验收」场景期望 `acceptance`。

**待 Owner 决定**：主控能否自行降级。W4 L2016 原话是「应自动调整为…」，本文按此推荐；若要保留人工确认，只做 impl-planning 侧默认值。

### R5 · 收尾汇报的硬字段与小请求的轻路径

**证据**：report §4.7。W6 L7000 缺 worktree/branch/HEAD → L7011；L7034「业务比较点」→ L7041；W1b 一份说明文档 12.7 分钟 → L16538。

**改什么**：`talk-to-boss/SKILL.md` 完成条件加：涉及仓库状态的汇报首段带 worktree、分支、HEAD；内部词同句写它与当前 HEAD 的关系。[`handoff-to-new-session/SKILL.md`](../../../skills/handoff-to-new-session/SKILL.md) 开头加边界：用户要的是给人看的说明文档而不是 session 交接时，不走 anchor/continuation，用已有事实一次成文。

**验收**：`tests/test_handoff_to_new_session_contract.py` + talk-to-boss validator。

### R6 · 清掉旧 profile 文件

**证据**：W2 POLR-02 fan-out 用了旧名 `backend` / `frontend`（L3170/L3182），一次因缺 `task_name` 失败。`~/.codex/agents/` 里 `backend.toml` / `frontend.toml` 与 managed 的 `*-worker.toml` 并存。

**改什么**：[`install_codex_agents.py:206-227`](../../../plugin-marketplace/plugins/impl-package/scripts/install_codex_agents.py) 已能识别 legacy 渲染，加上：内容等于 legacy 渲染的旧文件直接删除，不等的仍报 conflict。

**验收**：`tests/test_impl_package_agents.py` 加删除用例。

### R7 · 主控 context 卫生扩到轮询与收尾

**证据**：report §2 第 11 行。W7 主控自己 53 次 `write_stdin` 轮询 + 24 次 pytest；W1b L15838 稳定文档回刷用户要求交给 worker。

**改什么**：`dispatcher/SKILL.md:14` 第 3 步加：预期输出长或需多次轮询才收敛的动作（长测试、长驻进程轮询、稳定文档回刷、批量登记核对）默认包给 worker，主控只消费摘要。

**验收**：`tests/test_dispatcher_contract.py` 句子存在断言。

## 3. 先查再定

| 事项 | 证据 | 要查什么 |
| --- | --- | --- |
| 跨 session 汇报在承诺停止后仍发生 | W2 L1450/L1602 紧跟 `trail append` 0.02–0.14 秒，rollout 里只有 `function_call_output` 没有 `function_call` | 是主控又调了，还是宿主把 worker-return 自动中继给 source thread；后者仓库改不了 |
| `[$skill]` 引用何时注入正文 | W4 `learn-lessons`、W5 `handoff-to-new-session` 被注入；同为仓库路径的 `dispatcher` 在 W6/W7 没注入 | 是否只在 IDE 选择器路径触发；结论影响 R1b 要不要更强的入口 |
| 长寿命 subagent 与质量 | W7 `tkt01_backend/frontend` 各 2 轮后四轨 4/4 FAIL（L1063）；W4 `grok_monitor` 17 次 followup 无退化 | 一例时间相关，不构成规律；不加复用轮次上限，下一批继续看 |

## 4. 本轮不做

- 缩短 `wait_agent` 超时、「N 次超时后必须核查」——固定门槛的变体；W1b L8946「存活确认仍中断」作为 OF-03 复发证据保留。
- exec JS 包装 / apply_patch 转义 / followup_task 参数的通用校验——上轮否决通用校验 hook。
- evidence 覆盖语义（同 revision 全 claim）——R3 决定点，不推荐。
- 验收 claim 数量上限——plan-review 和 Owner 收缩已经在起作用。
- call-grok 的任何改动——临时替换。

## 5. 实施分组

| 组 | 项 | 性质 | 验收 |
| --- | --- | --- | --- |
| A（文案，可并行） | R1a–R1d、R2 路由句、R3 模板、R4 判据与默认值、R5、R7 | SKILL.md / situations.yaml / 模板 / reference | validator + 现有合同测试 + 新增 stage eval 场景 |
| B（脚本） | R6 | `install_codex_agents.py` | pytest |
| C（待决定） | R1 处境注入、R2 档位、R3 重登记、R4 主控降级权 | Owner 拍板后进 A 或 runtime | — |

R1 是本轮主项，A 组其余各项互不依赖，可与 R1 同时开工。

## 6. Owner 决定（2026-09-14）

1. R1 处境注入：**做**，与 handoff-to-new-session 的原则锚点一起联动改。
2. R2 review 各轨默认档位：**暂不动**。
3. R3 terminal 重登记 runtime 语义：**不动**，只做批量模板。
4. R4 主控自行降级 `implementation` 边：**两侧都改**（impl-planning 默认 `acceptance` + dispatcher 允许主控核实后降级并记 judgment）。
5. Codex 独立审核：**先不派**。

实施范围 = A 组全部 + B 组 + 处境注入。
