# SKILL 步骤与 why 回补（s2）

工作底稿统一取 `4e53faa^`；本轮只恢复有顺序内容的结构和原文已有/可直接对应的事故型 why，不恢复宿主专属 worker 或已撤销入口，不改组外文件。

## 1. `grill-me-smartly/SKILL.md`

- 编号步骤：`Review Then Apply` 原为两个顺序阶段但现文未编号，本次恢复为 2 步；`Loop` 保留原有 10 步，并为每步补充 why 子项，逻辑检查点为 10 → 12。
- why：Review phase 对应“临时判断误写目标文档、未决项看似批准”；Apply phase 对应“把模型收敛误当用户批准”；Loop 1–10 分别对应错误前提、丢失 ledger 状态、compaction 后复用失效分支、Q item 合并导致错误收敛、事实/偏好错路由、单题 converge 冒充整棵树完成、首答后漏掉 material branch、Questioner 过早收敛、无 stop proof 停止、把过程 ledger 当最终交付。
- 行数：89 → 101。

## 2. `execution-boundaries/SKILL.md`

- 编号步骤：preflight 的渐进读取 3 步与 Ticket 首次激活 4 步明确标为步骤 1–3、4–7，顺序保持为 anchor → control map → active unit → target → port → library separation → cleanup；standing bookkeeper 的主 thread 流程保留 6 步，合计 13 步未改序。
- why：preflight 1–3 对应 authority 漂移、越过 write-set/漏 blocker、全量读取造成恢复假象；首次激活 4–7 对应错误 target、端口争用、应用库/integration 库串线、残留资源无人清理；bookkeeper 1–6 对应日常路径被慢路径接管、缺上下文导致猜测、辅助角色越权、依赖语义误用、跳过 correction event、日常 trail 与异常回执混淆。
- 行数：122 → 135。

## 3. `impl-package/SKILL.md`

- 编号步骤：交互质询从 4 个压平 bullet 恢复为 7 步；Durable document 约束从复合段落恢复为 4 步；Legacy Task/DAG 从 4 个复合 bullet 恢复为 8 步，保留只读恢复边界。
- why：交互质询补回材料成熟度误判、frontier 漏项、问题缺少失败边界、事实/决策错路由、回合未推进、冲突静默覆盖和局部收敛冒充完成；durable 文档补回假设伪装事实、中途写回、短文静默丢 promise、未运行阶段被误报；legacy 入口补回跳过 current plan、把 Task 数量/`DONE` 当验收、引用越界、扩张新 DAG、漏跨 Ticket 检查、另建状态轴和未释放 dependency 发布等事故。
- 行数：88 → 119。

## 4. `impl-planning/SKILL.md`

- 编号步骤：主流程原有 9 步保留为 9 步，每步补事故型 why；合并的 Ticket-split 原为 7 个复合 bullet/段落，本次恢复为 9 步：切分、登记、到达路径、UI 形状、合同引用、evidence/coverage、Composition 发布、acceptance 不变量、发布后投影。
- why：主流程分别对应使用未批准合同、把 Plan 当第二套 Spec、patch 范围漂移、误建 DAG、AC/evidence 不可归属、旧入口偷换 Composition、跳过 bundle review、state 未 validate、绕过 execution boundary；Ticket-split 对应横向半路径、字段/owner 缺失、`EXISTS`/`NEW` 混淆、UI 形状被笼统通过、authority 引用过宽、测试声明无入口/owner、双状态 authority、`DONE` 冒充 acceptance、Ticket 混入 progress projection。
- 行数：54 → 73（保留处理前已存在的到达路径与 UI Ticket 改动）。

## 5. `req-align/SKILL.md`

- 编号步骤：主路径保持 7 → 7 步；本次为 no-contract fast path 和每个主路径步骤补充 why 子项，未改变 `full`、`decision-only`、`spec-only` 取值或路由顺序。
- why：对应把真实 contract impact 当 fast path、delta 当 replacement、未过 Decision 就进入 Spec、单 Gate 就进入 planning、提前创建 runtime state，以及只汇报 Gate 结果而不给可恢复入口等误判。
- 行数：48 → 56。

## 6. `req-align/sub-skills/decision/SUB-SKILL.md`

- 编号步骤：Decision 流程保持 7 → 7 步；每步补 why 子项，没有改变 Decision Gate 的先后关系或 `Decision BLOCKED` 入口。
- why：对应输入不足、另造长期 authority、follow-up 丢 carry forward、授权调查错判、proposal 过早 durable 化、BLOCKED 仍建 Spec/绕过 bound writer、以及把 initial Gate 重新发明或在 uncertainty 未闭合时 PASSED。
- 行数：34 → 41。

## 7. `req-align/sub-skills/spec/SUB-SKILL.md`

- 编号步骤：Spec Design Preflight 保持 5 → 5 步；设计与写入保持 6 → 6 步；Spec Gate 从一行 6 个有前置关系的检查拆为 6 步，另保留留白导致 `BLOCKED` 的边界。
- why：Preflight 对应只读 delta、漏 surface、规则没有 identity/retry/recovery、blocker 落点错误和 `not-required` 过度使用；设计写入对应范围未先冻结、surface 下限分散、双 artifact authority、延迟分类、只改 disposition、风险信号被固定流程/完全跳过；Gate 对应漏 object、coherence 假通过、authority 冲突、章节互相矛盾、没有 observable evidence、owner decision 留给 Plan，以及两个实施者可产生不同实现。
- 行数：51 → 78。

## 8. `backfill-stable-docs/SKILL.md`

- 编号步骤：新增阶段顺序 5 步；Audit 保持 5 → 5 步；Apply 从 1 个复合段落恢复为 4 步；Verify 明确为 1 步，Retirement 保持条件闸门。
- why：阶段顺序对应基准未固定、候选被当批准、apply 范围扩大、verify 变成自动修复、过早删除；Audit 对应脚本越权、pending 屏蔽/去重误用、代码冒充 intent、临时 ID、audit 副作用和重复 version authority；Apply 对应宽泛批准、顺手改候选、破坏性授权越界和失败不可归因；Verify 对应失败绕过授权，Retirement 对应 Gate/合入不足以证明 durable meaning 已安全退休。
- 行数：40 → 69。
