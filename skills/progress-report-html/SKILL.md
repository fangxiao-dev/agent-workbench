---
name: progress-report-html
description: Create or incrementally update a human-readable HTML progress panel for a task package, project milestone, or set of serial/parallel work items. Use this whenever the user asks for a progress dashboard, stakeholder status view, periodic progress report, or to keep updating the same HTML over time—even when there is only one task and no thread coordination.
---

# Progress Report HTML

把工程状态转换成利益相关方可以快速理解的全局视图。这个 skill 的重点不是展示 thread、分支或命令，而是回答：范围是什么、已经完成了什么、现在卡在哪里、下一步是什么、最终目标是什么。

## 核心原则

- 先识别真实 scope，再决定面板大小。Scope 可以是一个任务包、一个任务包里的串行步骤、几条并行工作线，或者一个多 thread coordination group；不要假设一定有多个 thread，也不要写死数量。
- 如果 scope 提供 checkpoint、验收标准、里程碑、交付清单或其他可观察完成条件，可把这些条件对应的稳定工作项作为主聚合单元；工作项可以是 Ticket、task、plan step、阶段或业务纵切，不应预设唯一类型。整体估算由这些工作项聚合，不按文件数、线程数、提交数或测试总数估算。
- 主视图面向人，不面向开发工具。业务状态、结果、影响、下一步和依赖优先；内部编号、变量名、commit、branch、worktree、seam、ledger、migration number 等只放在折叠的审计区。
- 主视图默认使用简体中文和业务语言。英文只保留产品名、协议名、代码标识或确实没有自然中文替代的专有名词；首次出现时必须先给中文解释，不能把多个英文术语用斜杠或连字符堆在一句话里。
- 只在用户触发时刷新。除非用户明确要求，否则不使用定时器、后台轮询、自动 fetch、WebSocket 或远端 API。
- 如果已有 HTML，增量更新同一个文件；不要每轮创建副本。保留已有历史和可追溯信息，只追加真实变化。
- 局部阶段完成不等于整个任务完成。只有父任务的最终验收、集成、必要验证和 gate 都满足时，才显示整体 closed。
- 不能从不可访问的主会话或 thread 猜测状态。明确区分已观察、已交付、等待确认、陈旧和推断状态。
- 在 side chat 中，package ledger 只能证明登记状态，不能替代主会话的实际进展；生成报告前必须先核对主会话，或明确标记主会话实际进展不可观测。

## 触发后的工作流

### 1. 先恢复事实和范围

从当前可访问的主会话、任务包、registry、ledger、sidecar、计划和最近状态报告中恢复事实。优先级如下：

1. 用户当前提供的更新和明确决定。
2. 当前任务包的权威文档、runtime state、Ticket evidence、registry 和 ledger。
3. 当前可访问的 work item/thread 状态和已提交证据。
4. 旧聊天或旧快照只能作为背景，不能覆盖较新的权威记录。

先写出内部 scope 表，但不要把内部表原样放进主视图：

| Scope | 需要回答的问题 |
| --- | --- |
| 一个任务包 | 当前阶段、完成条件、剩余收口 |
| 串行步骤 | 上一步是否释放下一步、当前阻塞点、终点 |
| 并行工作线 | 每条线做什么、各自状态、汇合点 |
| 多 thread coordination | producer/consumer、依赖、共享验收门、总体关闭条件 |

如果当前 side chat 不能直接读取主会话或 thread，说明数据边界；只能生成明确标记为“package evidence snapshot”的报告，不能把 package-only 数据写成当前实际进展，也不能用 `0/n` 这类 ledger 数字概括实际实现程度。必要时让用户提供主会话 checkpoint。

### 1A. Side chat：主会话实际进展核对（强制）

当当前会话被标记为 `side chat` / `side conversation` / fork，或用户询问“实际进展”时，必须在生成或刷新报告前执行以下核对：

1. **定位主会话。** 优先使用当前 app/thread context 或 `owner-thread-broker` 中该 coordination group 的最新 `current_session_id`；不得使用继承历史中的旧 session ID、旧 handoff 或凭记忆猜测主会话。
2. **读取主会话最新状态。** 获取最近的主会话 checkpoint、实现/WIP 描述、已运行验证、数据库/外部系统边界、阻塞与下一动作。若平台提供 thread/app read API 或主会话 terminal，应读取其最新可访问内容。
3. **只读交叉核对本地证据。** 对照当前 worktree diff、任务包 runtime state、Execution Record、Ticket acceptance projection 和 gate 文件，区分代码实际变化、已运行证据、ledger 登记和最终 closure。
4. **分开记录四种状态：**
   - `主会话实际进展`：主会话最新明确报告的实现/WIP；
   - `可复核证据`：worktree、测试输出、报告或其他可重读证据；
   - `正式登记状态`：Ticket/runtime ledger/gate 的 machine-owned 状态；
   - `冲突或缺口`：主会话已完成但尚未 backfill，或主会话声明无法被当前证据复核。
5. **冲突时不抹平差异。** 主会话可以显示“已实现/待验收”，而 ledger 仍显示 `UNRECORDED`；报告应同时展示两者，不能将任一方静默覆盖另一方。主会话进展领先 ledger 时，写明“已在主会话完成、待 package backfill”，不得因此宣称 Ticket closed。
6. **主会话不可访问时降级。** 报告必须明确写“主会话实际进展：不可观测”，只能输出 package evidence snapshot，并将“实际实现程度”留空或标为未知；不得把 package-only 的 `0/7` 解释为“没有实现”。

### 2. 决定页面层级

根据 scope 自适应结构：

- 小范围单任务：使用一个总体状态区、一个阶段路径、一个剩余收口区；不要为了凑数加入 thread 表。
- 串行任务：用一条有方向的阶段路径，明确“下一步”和“完成后进入什么”。
- 并行工作线：用按业务能力分组的工作线列表，最后显示汇合点和共同验收门。
- 多 thread 任务：可以保留工作线数量，但不要让 thread 元数据成为主视图；将其翻译成业务能力和当前结果。

只在计数能帮助判断时显示数量。`7 threads`、`1/2`、`010/011` 这类数字如果没有业务含义，就不要放在主视图。

### 3. 设计 stakeholder 主视图

优先使用下面的结构，但可按 scope 缩小或合并：

1. **顶部总体判断**
   - 总体状态：进行中、等待决策、等待依赖、需要刷新、已关闭。
   - 当前阶段：用业务语言描述正在发生的事。
   - 一句话说明已经完成的阶段和仍未完成的阶段。
   - 若状态可计数，分开显示“实际实现/WIP”“可复核验证”“正式 Ticket 验收”和“terminal gate”；不要用一个未注明口径的 `0/7` 代表全部进展。
   - 若存在 Owner 决策，直接写清需要决定什么；没有时明确写“当前没有新的 Owner 决策”。
   - 如果能从可观察完成条件计算出估算值，可显示一个带口径说明的总体百分比；该百分比只表示实施与验收准备度，不得替代正式 acceptance 或最终 gate。

2. **全局推进路径**
   - 3–5 个阶段即可，阶段名称必须能让非开发人员理解。
   - 每个阶段包含：阶段名称、当前状态、已产生的业务结果或下一步。
   - 明确两个里程碑：`下一步` 和 `总目标`。
   - 不要用数据库迁移编号、Ticket 编号或内部阶段代号充当里程碑名称。

3. **有界工作项 / 纵切进展**
   - 当 scope 有 checkpoint、验收标准、里程碑、交付清单或其他可观察完成条件时，每个稳定工作项使用一张主卡，标题旁紧邻显示 `约 55%` 这类小型百分比徽章；工作项可由 Ticket、task、plan step、阶段或业务纵切组成，百分比必须带“约”或范围，避免伪精确。
   - 如果存在 AC，卡片只保留一行简短的 `AC 提示`，列出 2–4 个最能代表当前工作项的验收点或缺口；如果没有 AC，则使用 `完成条件提示`、`checkpoint 提示` 或 `里程碑提示`。不要在主视图展开完整清单，也不要另建独立的进度表、百分比表或线程表。
   - 每张卡至少显示：业务名称、估算百分比、当前结果、最小完成条件提示、下一步和阻塞/依赖。正式状态可在标题或状态行旁补充，例如“正式验收未登记”，但不要把它误写成“0% 实现”。
   - 如果没有可观察完成条件，改用业务能力工作线和阶段状态，不强行填百分比；多个并行子任务属于同一工作项时，合并显示其业务结果和真正的汇合条件，不把调度线程当成额外进度单位。

### 3A. 可观察完成条件的百分比估算

- 百分比的默认含义是“该工作项的实施与验收准备度”，不是正式 acceptance、发布完成度或最终 gate 状态；在页面上必须用短说明或审计区明确这一点。
- 只有在至少存在一种可观察完成条件时才估算：checkpoint、AC、里程碑、交付清单、阶段出口条件或其他能判断“已完成/未完成”的证据。没有这些条件时显示阶段状态或“暂不可估算”。
- 可以参考以下维度形成粗估：业务行为实现、直接验证证据、跨层接入/契约/目标环境验证、证据整理与收口准备。权重不是固定规则；优先遵循当前计划的完成条件，并在审计区说明采用的口径。
- 整体估算优先按最权威且可比较的完成条件数量加权，例如 `Σ(工作项估算 × AC 数) / Σ(AC 数)`；AC 不可访问或不可比较时，使用工作项等权或阶段权重，并明确标注“等权粗估”或其他替代口径。
- 只使用 5% 或 10% 粒度，或给出例如“约 50–60%”的区间；不得从改动文件数、测试条数、线程数、提交数或台账状态直接推导百分比。
- 主会话实际进展、可复核证据和正式登记有冲突时，百分比可以反映已观察的实现/WIP，但必须同时显示“正式验收未登记”或对应精确状态；`0/n` 只能表示正式登记计数，不能作为总体实现百分比。
- 主会话不可访问、完成条件不足、工作项边界不清或证据不足以支持估算时，不填百分比，显示“暂不可估算”并说明缺口。

4. **最近进展**
   - 按主题记录“发生了什么”和“对全局有什么影响”。
   - 日期只作为辅助信息，不要把日期当作主要索引。
   - 用主题名、结果和影响代替“某 commit 已变更”“某 thread 已 wake”。

5. **折叠审计区**
   - 可以放 task/thread ID、branch、worktree、commit、migration、测试命令、registry、ledger、证据路径和原始状态值。
   - 明确标记这是技术核对信息，不要让它混入 stakeholder 主视图。

### 4. 文案自检

在写完或更新 HTML 后，扫描所有用户可见文案，包括标题、徽章、状态、空状态、按钮、帮助文字、里程碑、事件和响应式布局中的文字。

主视图应避免以下形式：

- `010/011/012`、`T1/T2`、`F5/F6`、`D18` 等没有业务解释的过程编号。
- `HEAD`、`SHA`、`commit`、`branch`、`worktree`、`thread`、`seam`、`ledger`、`wiring`、`consumer`、`mutation` 等工程内部词。
- `awaiting_seam`、`waiting_on`、`IN_PROGRESS` 等变量或状态枚举。
- “完成了某脚本”“通过了某 migration”这类无法说明业务结果的句子。

把技术事实翻译成业务结果，例如：

- “Order Core delivered” → “订单核心能力已交付，可供下单、客户和库存业务接入”。
- “Catalog migration pending” → “商品与门店数据能力仍在收口，尚未进入共享测试验证”。
- “waiting on owner” → “等待最终业务规则确认，确认后进入实现”。
- “Test apply/readback passed” → “共享测试环境验证和结果核对已通过”。

主视图可以出现产品名、角色名和用户熟悉的领域词；不必为了消除所有英文而改写公认的产品名称。关键标准是读者能理解它对业务意味着什么。

### 4A. 中文可读性规则（强制）

生成或刷新报告时，先把技术事实翻译成“谁做什么、结果是什么、还缺什么”的中文句子，再决定是否保留英文原词。下面这些词在主视图中应优先使用中文：

| 原词 | 主视图推荐说法 |
| --- | --- |
| source catalog / compiler / current policy | 规则来源目录 / 规则编译器 / 当前生效规则 |
| snapshot / checkpoint | 不可变结果快照 / 可持久化检查点 |
| hash | 内容指纹 |
| runtime acceptance / Ticket closure / gate | 运行时验收 / 事项闭环 / 最终门禁 |
| WIP / readiness | 尚未收口的改动 / 可用性准备 |
| reviewed facts / fail closed | 已复核事实 / 遇到异常就停止 |
| selection intent / retain-or-refresh | 用户选择记录 / 保留仍合法选择或要求重新选择 |
| materialize / pipeline | 正式生成 / 正式处理链 |
| seam / typed contract / guard chain | 接入点 / 带类型的接口约定 / 真实权限校验链 |
| claim / DML / caller-owned transaction | 幂等占位 / 数据库业务写入 / 由调用方统一控制的事务 |

执行要求：

- 主视图标题、状态徽章、阶段说明、工作线、下一步和最近进展，除产品名/协议名/必要代码标识外，使用中文自然句；不要出现 `source catalog、compiler、current policy` 这类连续英文串。
- 英文原词只能作为中文后的短括号补充，例如“内容指纹（hash）”“运行时验收（runtime acceptance）”；同一原词在同一段不必重复。
- `API`、`UI`、`DATEV`、`PostgreSQL`、`OpenAPI` 等可保留，但必须让上下文说明它们对业务意味着什么；`WIP`、`seam`、`readiness`、`gate`、`DML` 等内部缩写或行话不得裸露在主视图。
- 折叠审计区可以保留精确英文状态、文件名和命令，但每一项必须附中文含义；审计区也不能用英文堆叠替代事实说明。
- 如果翻译后仍无法让非开发人员理解，继续改写句子，不要仅通过增加更多英文术语来“补充准确性”。

### 5. 同一个 HTML 的增量更新

如果用户指定了已有 HTML：

- 先读取并理解当前数据模型、视觉层级和审计区。
- 保持文件路径和主要结构稳定。
- 用 work item 的稳定标识合并状态，不因名称改变而重复创建工作线。
- 只有在状态、结果、下一步或依赖真实改变时，才追加最近进展事件。
- 保留历史事件，但限制数量或折叠旧记录，避免面板变成长日志。
- 对陈旧或无法核实的项目显示“需要刷新”，不要沿用旧状态伪装成当前状态。
- 更新后重新扫描全页文案；新数据也必须经过业务语言转换。

推荐的内部快照模型是可选的，不要把字段名原样展示给用户：

```js
{
  scope: {
    name: "任务或项目名称",
    overallState: "open",
    currentPhase: "当前业务阶段",
    summary: "总体判断",
    nextMilestone: "下一步",
    goal: "总目标",
    ownerDecision: null
  },
  phases: [
    { label: "业务阶段", state: "done|current|waiting|not_started", note: "业务结果" }
  ],
  workItems: [
    {
      id: "稳定的内部标识",
      name: "业务线名称",
      status: "working|waiting_decision|waiting_dependency|stale|done",
      estimatedPercent: 55,
      completionHint: "关键 AC、checkpoint 或其他完成条件，最多 2–4 个",
      progress: "已完成的业务结果",
      next: "下一步",
      blocker: "阻塞或依赖"
    }
  ],
  events: [
    { topic: "业务主题", text: "发生了什么以及影响" }
  ],
  audit: { /* technical evidence stays in the collapsed area */ }
}
```

HTML 可以提供一个手动导入快照的入口，但这个入口是辅助功能，不得替代 agent 对当前权威状态的读取和判断。若提供 `window.updateProgressSnapshot(next)`，必须做字段校验、HTML 转义和增量事件合并。

## 技术和安全约束

- 默认生成可直接打开的 standalone HTML；如果宿主明确要求 fragment，遵循宿主的 fragment 约定。
- 不使用网络请求、自动轮询、隐藏的外部写入、凭证、真实客户数据或 provider payload。
- 动态文案必须转义，避免把状态内容当 HTML 插入。
- 工作项百分比应紧邻工作项标题显示为带文字的内联徽章或短标签，并提供可读的 `aria-label`；颜色只能辅助表达，不能单独承担进度含义。AC 或完成条件提示保持紧凑，不创建独立进度表或图表。
- 维持键盘可访问的原生按钮、输入框和折叠区；保留可见 focus 状态。
- 在 320px、736px 和宽屏下避免关键文案重叠、截断和无意义的横向滚动。
- 主视图使用业务颜色和文字同时表达状态，不依赖颜色单独传达含义。
- 不要在没有证据时填写完成百分比、质量分数或风险等级；如果无法计算就使用明确的阶段状态。

## 验证清单

完成前至少进行确定性自检：

- HTML 结构和内嵌 JavaScript 语法可解析。
- 每个脚本查询的 DOM 元素都存在，主交互可以更新页面。
- 主视图不出现未经解释的 ID、commit、分支、内部枚举或过程编号。
- 不得把固定数量的 thread、task 或 work item 假设泄漏到小范围任务；页面只显示实际存在的 scope。
- overall state、next milestone、goal、work item 状态和事件之间没有相互矛盾。
- 如果 scope 有可观察完成条件，页面中的每个稳定工作项都只出现一次，并在标题旁有百分比或明确的“暂不可估算”；每张卡有 2–4 个 AC/完成条件提示；没有单独的百分比表。
- 总体百分比能够按审计区记录的工作项、完成条件和估算口径重算，且明确它不等于正式 acceptance 或最终 gate；若没有可重算依据，应改用阶段状态。
- side chat 报告已标明主会话实际进展、package evidence 与正式 ledger 的来源；主会话不可访问时没有把 package-only 快照写成实时实际状态。
- 主视图的技术英文已被翻译或首次解释；未解释的英文仅限产品名、协议名和必要代码标识。
- 若有浏览器环境，打开实际文件验证至少一个手动更新交互，并检查窄屏和宽屏；浏览器不可用时要明确报告未验证部分。

## 向用户汇报

汇报时先说功能层结论：总范围、已完成的阶段、剩余收口、整体是否 closed、需要的 Owner 决策。然后给文件路径和最小验证证据。不要把 HTML 内部数据模型、线程调度过程或工具调用顺序当成主结果。
如果 scope 有可观察完成条件，优先汇报“总体约 X%（按当前完成条件聚合）”，随后用工作项卡标题旁的百分比和简短 AC/完成条件提示解释构成；同时单独报告正式 acceptance 和 gate，不能用 `0/n` 代替总体进度。
在 side chat 中，额外说明主会话实际进展是否已读取，并分别报告“实际实现/WIP”和“正式 Ticket 验收”；若两者不同，保留差异并说明是否需要 package backfill。
报告正文优先用中文说明业务结果；如果读者仍需原始技术词，将其放入括号或折叠审计区，不把英文术语串直接当作进度结论。
