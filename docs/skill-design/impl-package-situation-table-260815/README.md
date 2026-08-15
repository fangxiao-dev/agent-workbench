# Impl-Package 处境表设计

## 1. 文档状态

- 日期：2026-08-15。
- 状态：方向讨论完成；命名空间固定为 `<对象>.<环节>.<状况>`，正式机读来源固定为 `skills/dev-with-track/situations.yaml`；字段与优先级仍以试运行读数为准。
- 目标：把 Orchestrator 现在靠记忆承担的流程规则移出主 thread，使它只承担判断。
- 设计对象：`dev-with-track` 的处境表、处境推导器与决策轨迹。
- 本文不授权实施。

## 2. 问题

两个现象：

1. **流程被跳过**，而且在 context 压缩之前就会发生。规则仍在 context 里，但没有被用上。
2. **记账与派活串行**。worker 返回后必须先落账才能派下一张卡，单次不长，累计很长。

第一条的成因不是模型不遵守，是四个结构性事实：

- **在场不等于被注意。** SKILL.md 在入口加载一次，之后被数十轮工具输出压住，早期指令的有效权重持续下降。
- **位置每轮靠重推导。** 系统里没有任何地方记录"当前在哪一步"，agent 每轮从聊天记录重新推断。
- **规则是前置批量加载，不是按步投递。** 规则的送达时间和使用时间差了整个流程。
- **不留载体的步骤没有缺席信号。**

第四条是根因，可以写成判据：

> 一个步骤如果不产生产物、不产生一次调用、不产生一次 fresh 派发，它就没有缺席信号；没有缺席信号的步骤，长跑中必然被跳过。

用现有历史验证：Ticket 有文件与 state 作载体，活了下来；Task/DAG 载体过重，退成只读兼容；evidence 有 `evidence add` 调用，稳定；`investigate` 与 `subagent-driven-development` 的 `mode` 策略块没有任何载体，前者经常被跳过，后者输出到聊天即蒸发。被跳过的恰好是唯二没有载体的两项。

## 3. 为什么不做工作流引擎

旧 DAG 失败有两层原因。第一层是它绑在 Task 上，Task 定义有问题时图随之失效。第二层更根本：**图必须预先完备**。画图时就要穷举全部边，而实际流程的边是运行时才长出来的——例如"上一个 Ticket 已 SATISFIED，下一个 Ticket 的实现证伪了它的某条 AC，是否重开"，这条边在计划阶段不存在。补边意味着改图，改图意味着图与现实持续漂移。

因此这一层不画图。流程里没有"路径"这个概念，只有"此刻我能做什么"。正确的形态是一张**处境到动作的查表**：

- 没有路径，所以环不成立。重开只是某个处境下的一个可选动作，不是"回到上一个节点"。
- 每一行独立，不完备是优雅降级的。表里没有的处境交给判断并记一行理由；图缺边是故障，表缺行只是没帮上忙。
- 每轮只需要当前一行，投递成本与流程长度无关。

## 4. 四个构件

| 构件 | 形态 | 作用 |
| --- | --- | --- |
| 处境表 | 声明式数据 | 此处境有哪些合法动作、各自的前置、载体、机械后果与默认执行者 |
| 处境推导器 | 只读脚本 | 从产物与轨迹推导当前命中哪一行 |
| 决策轨迹 | append-only JSONL | 记录每次实际选择，供恢复、缺席检测与事后分析 |
| 投递点 | CLI 返回值 | 让上述内容在动作发生的那一刻在场 |

主控的循环收敛为：渲染处境与可选动作 → 选一个 → 执行或派发 → 记一行 → 重新渲染。每一圈都重新投递，不依赖任何东西被记住。

### 4.1 什么进表，什么留给主控

判据：

> 这条规则的答案依不依赖本次的具体事实？不依赖的进表，依赖的留给主控。

| 进处境表 | 留给主控 |
| --- | --- |
| 此处境有哪几个动作可选 | 选哪一个 |
| 每个动作的前置、要留什么载体 | 前置是否真的成立 |
| 动作的机械后果（释放或不释放依赖、失效范围） | 这条证据到底证伪了什么 |
| 每个动作默认由谁执行 | 这次要不要偏离默认 |

最后一行的副作用是：`subagent-driven-development` 的 `mode / worker / review` 策略块从"每次现写"变成"预填加偏离时说明"，既变便宜又终于有了载体，而主控写下的字正好是最有价值的那部分。

### 4.2 只引导，不阻断

处境表只叙述，不拦截。跳过某一步依然合法——有时确实应当跳过。区别只是跳过会被当场点名，而不是拖到 Gate 才发现。取向与 `thread-harness` 的 `dispatches_since_progress` 一致：只测量，不阻断，把静默失效变成可见信号。

`stall-check` 的 `CHECK_HEARTBEAT` 做法同样可以照搬：不在第一次偏离就报警，先给一轮确认机会，说得出具体理由就放行。

### 4.3 表会说谎

漏列一个合法动作，主控就可能想不到它。这是本方案唯一的真风险，而且比图漏边更隐蔽——图会报错，表只是沉默。

缓解：每一行都留逃逸出口（以上都不适用时按判断行动，记一行理由），并且**逃逸记录就是表的待补清单**。同一处境反复被逃逸说明缺一行；per-package 的裁剪攒多了说明默认谱该升级。表因此是自己长出来的，不需要一次设计完备。

## 5. per-package 可调

reference 提供默认谱，package 只写差异，不写副本：

```text
step-spec: 继承 default
  跳过: investigate（理由：本 package 全部工作源自已定位的 review finding）
  新增: locale-verify（载体：browser 截图证据，位于 ticket 验收之前）
```

三个效果：默认谱升级时 package 自动跟随；差异本身是一个载体，把"故意跳过"和"忘了"分开，渲染器不再点名已裁剪的步；这些差异攒起来是下一版默认谱的输入。

要防的是它变成泄压阀——长跑后期压力大时改谱而不是做步骤。不禁止，只让它可见：差异落在 package 内、走 git、渲染器带一句"本 package 已裁剪 N 步"。

## 6. dev-with-track 枚举结论

完整枚举见 [situation-table-dev-with-track.md](situation-table-dev-with-track.md)。

共 **55 行**，其中：

| 类型 | 行数 | 特征 |
| --- | --- | --- |
| 记忆行 | 44 | 只有一个合法动作，或后果完全机械，没有可选余地 |
| 判断行 | 11 | 有两个以上合法动作，选哪个取决于本次具体事实 |

三个从枚举掉出来的发现：

**表比它替换的散文短。** 55 行约 2k token，覆盖的规则现在分散在 `dev-with-track/SKILL.md`、`references/runtime-protocol.md`、`subagent-driven-development/references/review-gate.md`、`references/mode-contracts.md`、Composition Contract 第 6 节与 Current State 的 Ticket/evidence 段，合计约 4 至 6k token。表每轮只投递一行，散文是入口全量加载，两头都省。

**有 6 行的分辨率取决于轨迹字段。** C1、C6、C10、C11、C12、E3 无法从产物推导，只有记了轨迹才能分辨。轨迹不是附赠的分析功能，它是这几行成立的前提；其中 C1 既是最痛的一行，也是最依赖轨迹的一行。

**有 2 行永远推不出来。** C3（是否存在多个合理业务结果）与 C5（来源是否含糊或冲突）是纯语义判断，没有机械来源。这两行只能由主控主动进入或走逃逸出口；表能做的只是在相邻处境挂一句提醒。

**42 / 55 是赌的。** 按 [9.6 的 basis](#96-basis) 标注一遍后，只有 13 行有 CLI 强制。分布高度不均：

```text
investigate  route  implement  fix  review       18 行，强制 0 条
accept  gate  rework                             13 行，强制 8 条
```

**关于"怎么工作"的五个环节没有一条规则有强制，关于"记账是否正确"的三个环节强制占了大半。** 这解释了第 2 节的现象——流程被跳过不是因为规则缺失，而是全部强制预算都花在了记账正确性上，工作方法那一侧一条也没有。处境表是第一个触及工作方法那一侧的机制；它不增加强制，但让这 18 行第一次有了读数。

## 7. 决策轨迹

字段集与写入分工见 [trail-schema.md](trail-schema.md)。要点：

- 落在 `execution/<attempt>/trail.jsonl`，随 attempt 分段，terminal gate 冻结，Git 保存历史。
- 一次决策一行，字段固定，机读优先；自由文本只有 `reason` 一项且只在偏离默认时出现。
- 凡以 CLI mutation 收尾的动作由 CLI 自己追加轨迹行，主控无额外成本，且这些行天然是地面真相。
- 只有没有其它载体的动作需要显式写行：派发的发起与返回、逃逸、Ticket 选择、finding 定级与分流、来源路由判断。

### 7.1 增长问题

轨迹增长在磁盘上，不在 context 里。运行中的三种读者需求都是有界的：

| 读者 | 需要什么 | 读多少 |
| --- | --- | --- |
| 正在跑的主控 | 当前处境加那一行动作 | 零历史，处境从产物与轨迹尾部推导 |
| 恢复中的新 session | active checkpoint 加当前 state | 常数，`activeCheckpoints` 是覆盖写 |
| 事后分析 | 整份轨迹 | 全量，但这是另一个进程，不占执行时 context |

按一次决策一行、约 40 token 计，四小时任务约 100 至 300 个决策点，合计约 12k token 在磁盘、0 在 context。它变大只有一种情况：每轮追加一段自然语言叙述。因此要约束的是记录格式，不是保留策略。

纪律只有一条：**没有任何运行中的 agent 会整份读它。**

## 8. 与现有体系的关系

- `impl_package_state.py` 继续拥有 runtime state 的机械写入与校验；处境表不复制状态语义，也不新增状态字段。
- 各 stage skill 继续拥有各自的语义与完成条件；本方案只改变规则的投递方式，不改变 owner。
- `subagent-driven-development` 继续编排 investigate/implement/fix/review；处境表为其策略块提供默认值，不接管 worker 解析。
- `do-review` 继续拥有 review topology 与 coverage；处境表只指出何时应当进入它。
- `progress.md` 仍不作为推导输入。它是 projection，作为输入会绕成环，与 `runtime-protocol.md` 中"Progress 不授权 readiness"同一条理由；projection drift 改由 `package validate` 基于 authoritative state/contract 生成的诊断提供判据。

## 9. 命名空间

slug 有两个身份同时成立：它是处境表一行的主键，表是活的；它又是每条轨迹行里写死的值，轨迹是不可变的。全部约束都来自这个双重身份——改一个名字，成本不落在表上，落在已经写下的历史行上，查询从此需要同义词表，而那正是本体系明确拒绝维护的兼容层。

### 9.1 结构

```text
<对象>.<环节>.<状况>
```

固定三段，不允许两段或四段。

- **段 1 对象，封闭**：`package` | `attempt` | `ticket` | `finding`，与轨迹的 `subject` 类型对齐。
- **段 2 环节，封闭**：见 9.2。
- **段 3 状况，开放**：在同一环节内把本处境与其它处境区分开的那个状况，允许自由新增。**只有这一段开放**，新处境不断出现但只在一个位置生长。

段 3 不叫"缺口"，因为有相当一部分行并非缺口（`satisfiable`、`sources-uniquely-decide`、`all-tickets-terminal`）。也不能叫"下一步"——判断行没有唯一的下一步，而 slug 必须是主键。

字符集：全小写，段内用 `-`，段间用 `.`。

### 9.2 段 2 取值域

```text
record  readiness  investigate  route  implement  fix
verify  review  accept  rework  disposition  gate
```

段 2 由表在编写时**静态指定**，不在运行时推导，因此不会漂移；同一行永远产生同一个 slug。

取值不以"现有文档里有这个词"为依据——那些文档正是被升级的对象，拿它们背书是循环论证。取值只经四条检验：

| 检验 | 问什么 |
| --- | --- |
| 可判定性 | 给一个新处境，两个人独立分类会不会分到同一个值 |
| 分布 | 每个值几行。极度倾斜说明出现了 catch-all，单行说明切得太细 |
| 换执行者不变 | 值会不会随"谁来做"而变 |
| 生成力 | 能不能问出"这个环节还有哪些处境没列"，并真的想得出来 |

这四条抓到过的问题：`decide` 曾装下 9 行异质内容（可判定性）、`bookkeeping` 曾只剩 1 行（分布）、`evaluate` 与 `review` 曾用执行者论证拆分（换执行者不变）。

### 9.3 对象与环节的组合

段 1 与段 2 不自由组合，允许矩阵由**对象有没有这种活动**决定：

| 对象 | 允许的环节 |
| --- | --- |
| `package` | `record` |
| `attempt` | `record` `readiness` `verify` `review` `accept` `rework` `disposition` `gate` |
| `ticket` | `record` `readiness` `investigate` `route` `implement` `verify` `review` `accept` `rework` `disposition` |
| `finding` | `record` `fix` `review` `disposition` |

23 个允许组合。`package` 是容器，本身不承担工作；`gate` 只在 attempt 级；`fix` 的对象是 finding。未列出的组合由校验拒绝，提示"要用先显式修改矩阵"。

### 9.4 三条使用规则

1. **段 2 命名的是活动，不是执行者。** 任何值都不暗示由谁执行；执行者只写在动作行上。
2. **循环之外的行统一用 `record`。** 段 2 主体是控制循环的环节；不属于循环、只关于记录层的行（state 损坏、投影漂移、checkpoint 未写、结论未入账、落账积压、跨 session 接手）一律用 `record`。它不叫 `bookkeeping`，因为落账只占其中一半，另一半是记录层完好性与从记录恢复；而且 `bookkeeping` 会被读成执行者，违反第 1 条。
3. **不改名。** 措辞变了就是新 slug；旧 slug 在表中标 `retired-by: <新 slug>` 供查阅，但不动任何历史行。段 1、段 2 新增取值或修改允许矩阵都属于重大变更，需要单独决定。

### 9.5 六条判定线

相邻值最容易混，边界显式写下：

| 相邻值 | 判定线 |
| --- | --- |
| `verify` / `record` | 证据**不存在**是 `verify`；证据或结论**存在但未入账**是 `record` |
| `investigate` / `verify` | `investigate` 建立事实、原因与边界，同一次调查的发起与返回都算它（含返回 `EVIDENCE_GAP`）；`verify` 检验某个具体主张是否成立并留下证据 |
| `readiness` / `route` / `disposition` | 对象不同：能不能开始 / 走哪条技术路线 / 已知项的归宿 |
| `readiness` / `accept` | `readiness` 管能不能**开始**（implementation 边）；`accept` 管能不能**收**（acceptance 与 release 边） |
| `route` / `rework` | 对象是否已进终态。首次裁决走哪条路是 `route`；已达成的验收结论被推翻后的处置是 `rework` |
| `fix` / `implement` | `fix` 只消费已确认且已边界化的 finding，必须 fresh invocation |

### 9.6 basis

每行标注这条规则靠什么成立：

| 取值 | 含义 |
| --- | --- |
| `cli` | CLI 本来就会拒绝违反者，表只是提前说一声 |
| `prose` | 只有散文这么说，没有任何强制——**表在赌它是对的** |
| `observed` | `prose` 行被真实读数支持后升上来 |

它的作用是**让逃逸计数变得可行动**。同一行被逃逸 8/10 次，`cli` 意味着 agent 在试图绕过 CLI 反正会拒的东西（该改 agent 或改措辞），`prose` 意味着这条规则在真实工作里八成不成立（该改规则）。没有这个字段，同样的数字给不出方向。

派生用处：渲染措辞的强度（`cli` 可以说"必须"，`prose` 只能说"默认"）、首版验证范围（只需验 `prose` 行）、以及规则被检验过这件事从印象变成状态。

边界条件：它的价值全部在下游。**不读逃逸读数的话，这个字段是死重量。**

### 9.7 `when` 比较表达式

`when` 是 mapping 时，每个 key 都必须能在渲染器的解析器注册表中找到；解析结果为 `unknown` 时不得静默当作 `false`。比较规则如下：

- YAML 布尔值 `true` / `false` 只做严格布尔比较；未带比较操作符的字符串、数字和状态枚举做精确相等比较。
- 带引号的 `>N`、`>=N`、`<N`、`<=N`、`==N`、`!=N` 是数值比较，`N` 必须是数值；例如 `attempt.ready_ticket_count: ">1"` 与 `evidence.count: ">0"`。
- `manual` 是显式不可推导 sentinel，不是一个可比较的值。
- 缺少事实、输入文件不可读或解析器无法确定值时，结果为 `unknown`，渲染器保留该未决行并报告原因。

渲染器和表校验器对未注册的 key 直接报错；新增 `when` key 必须同时提供命名解析函数，不能通过放宽校验来吞掉缺口。

### 9.8 未命中怎么记

- 命中了处境但选了逃逸：`situation` 照记命中值，`chosen: escape`。
- 一行都没命中：`situation` 记 `<对象>.<环节>.unmatched`。

第二条使"表没覆盖到"本身成为可查询、可统计的事实。逃逸记录即表的待补清单，靠的就是它——否则未覆盖的处境在轨迹里是一片空白，而那正是最需要看见的部分。

## 10. 落地形式

### 10.1 处境表存放在拥有它的 skill 目录

```text
skills/dev-with-track/situations.yaml     # 正式来源，机读
scripts/situation.py                      # 渲染器，按 skills/<stage>/situations.yaml 约定查找
```

不放 plugin 根的 `references/`：那里躺的是跨 skill 共享的合同，而处境表是单个 stage 的资产。将来若铺开到其它 stage，每个 stage 各自一份住在自己目录下，不会长成一个装所有 stage 的大文件。

**只存机读格式。** 人读全表跑渲染器打印；同一张表不留第二份人读副本，否则必然漂移。[situation-table-dev-with-track.md](situation-table-dev-with-track.md) 在 YAML 落地时降级为设计草稿，只保留枚举过程与讨论记录。

单行的字段形态：

```yaml
- slug: ticket.investigate.no-carrier
  basis: prose                   # cli | prose | observed
  when:                          # 推导判据，机读
    ticket.state: PENDING
    trail.has_investigate: false
    evidence.count: 0
  judgment: true
  ask: 违约边界是否已经确认
  actions:
    - id: dispatch-investigate
      default: true
      by: dispatch               # 执行者
      do: "sdd mode=investigate"
      effect: "返回 EVIDENCE_SUFFICIENT 或 EVIDENCE_GAP"
    - id: implement-direct
      by: dispatch
      do: "sdd mode=implement"
      requires_reason: true
  escape: true
```

这一份同时是四样东西的唯一来源：表本身、渲染器的输入、轨迹 `chosen` / `alt` 的取值域、以及轨迹的校验依据——写了该 slug 下不存在的 action id 可以当场发现。

### 10.2 首版不改动 `impl_package_state.py`

全部轨迹行显式写入，不在语义命令里追加自动写行。

**风险不对称**：表错了只是提示不准，state 引擎错了是数据损坏。自动写行要在每个语义命令里插入追加逻辑，那些命令跑在 CAS 路径上；为一个尚未验证的表去动它，赔率不对。

**并且首版需要这个读数**：显式写行的漏记率本身就是决定"要不要自动化、先自动化哪几条"的数据。首版就自动化 15 条，等于放弃这个读数。

代价是纪律面大（15 至 20 处显式写行），首版接受。

### 10.3 per-package 差异存放在 package 根下

```text
<package>/situations.yaml        # 与 plan.md、tickets/ 同级
```

**不放 `.impl-package/`**：该目录是 machine-owned，`state.json` 由 CLI 写；而裁剪差异是人写、要 review、进 git 的东西。混进 machine-owned 目录会让"谁能改这个文件"变得含糊。

**不塞进 Plan 正文**：一是渲染器要解析 Markdown 内嵌代码块，脆；二是 Plan 冻结后差异仍可能需要调整，改 Plan 的语义成本高得多。

裁剪流程仍是一个决策，不应悄悄发生。折中：文件独立存放，但**首次创建或修改时按 Plan 变更同等对待**——记一行轨迹，且渲染器持续显示"本 package 已裁剪 N 步"。可见性保住，又不绑上 Plan 的冻结语义。

仓库特定的能力（例如预置的环境启动 skill）应当在 per-package 覆盖层具体点名；默认表只写通用指引。

### 10.4 下游影响

`<package>/situations.yaml` 成立后，Composition Contract 第 3 节的固定位置清单需要增加一行。那是现役合同文档，落地时再改。

### 10.5 轨迹 `alt` 只记 id

不逐个记录排除原因；`reason` 维持现状（只在偏离默认或判断行时填），另加可选的 `near_miss` 记下差点被选中的那个 action id。理由见 [trail-schema.md](trail-schema.md#alt-只记-id不记排除原因)。

## 11. 明确不做

- 不建工作流引擎，不建流程图，不引入路径或节点概念。
- 不新增状态字段表示"当前阶段"；处境一律推导，推不出来的不进表。
- 不用处境表阻断动作；它只叙述并留痕。
- 不在首版覆盖 `req-align`、`impl-planning`、`backfill-stable-docs`；这些阶段本身线性，收益远小于 `dev-with-track`。
- 不因本方案改变任何 stage 的语义 owner 或验收判据。

## 12. 与 standing bookkeeper 设计的关系

[impl-package-standing-bookkeeper-skill-design-260814.md](../impl-package-standing-bookkeeper-skill-design-260814.md) 保持现状进入第一轮试运行，不因本方案提前重写。2026-08-15 讨论结论：

- **保留**：§2 的裁决者与执行者分离、§6 ownership 表、§12 身份边界、role.md 的禁止越界。这些与处境表正交。
- **将被吸收**：§19.4 要求主 thread 填写 `artifact / section / operation`。定位是路由问题而非记账问题，处境表定型后由表与渲染器给出目标，主 thread 只需给 fact kind 与 subject，`NEEDS_SPLIT` 随之基本消失。
- **将被替换**：§10 与 §19.5 的 `依赖：是` 阻塞回执，改为前沿写入与追溯写入的划分。前沿写入（释放依赖的 `ticket satisfy`、交接前 checkpoint）由主 thread 直接执行，追溯写入异步完成，积压由 `package.record.intake-backlog` 处境暴露。
- **需要裁决**：§6 的"主 thread 对 package artifact 保持只读"覆盖 runtime state，与 `impl-package-current-state.md` 及 Composition Contract 的 single-writer 规定冲突。建议重述为"文档的唯一 writer"。

改动依据必须来自试运行实测，不来自推演；观察项已记入该文档第 15 节。
