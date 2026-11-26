# kickoff 设计阶段 Pipeline 与 impl-planning 首稿防线

日期：2026-11-26  
设计依据：结合 `2026-11-26-hr-refinement`（员工助手功能细化）从调研对齐到 Plan Review 收口的完整实战复盘，以及 Owner 对设计阶段 Pipeline 定位的确认。

## 1. 定位与职责边界

`kickoff` 是**设计阶段的纯状态/workflow 编排器**，与下游单阶段 Skill（`req-discover`、`/impl-package:req-align`、`/impl-package:impl-planning`、`/impl-package:plan-review`）互补而非替代：

| 层级 | 拥有什么 | 不拥有什么 |
| --- | --- | --- |
| **`kickoff`（Pipeline / 状态机）** | 时间轴（`init -> discover -> decision -> spec -> plan -> ready`）、输入契约、角色池登记、审阅分诊轮次、收敛熔断、阶段过门禁、各阶段 Skill 挂载提示 | 不解析下游 Markdown/JSON 文档内容，不替代 `impl-package` CLI 管理包内 Ticket/State |
| **各阶段 Skill（方法论与包内 CLI）** | 单阶段怎么把产物写好、审好，以及包内产物之间的关系与机械校验 | 不承担跨阶段时间轴推进与角色续用/收敛追踪 |

**核心价值（降载）**：以前主控需要靠背诵多份 Skill 文本来遵守跨阶段纪律；引入确定性状态机后，关键节点的输入/输出门禁由 `kickoff.py` 强制，主设计师只需沿着 Pipeline 专注写设计、做状态标记、派发各类代理取信息与审阅。本设计也是后续把 `dev-with-track` 改造为同款 pipeline-based 编排器的先行范本。

## 2. 实战复盘暴露的缺口与归位

在 `2026-11-26-hr-refinement` 全流程中，四轨并行 Plan Review（A 范围结构 / B 验证风险 / C 交付归属）+ 常驻 PE 根部裁剪效果显著，但也暴露出两类可系统化改进的缺口：

### 2.1 属于 `kickoff`（纯流程层）的 4 项改进

1. **阶段显式挂载 Skill**：现有 `PIPELINE["stages"]` 只有 `principles`，未标明每个阶段对应调用的 Skill。在声明式 `PIPELINE` 中为每个阶段补充 `skills` 列表，`advance` 与 `status` 直接输出“本阶段调用的 Skill”，真正把 `req-discover`、`req-align`、`impl-planning`、`plan-review` 串成一条链。
2. **区分设计审阅者与计划审阅者角色池**：
   - 原 `kickoff.py` 只有单个 `reviewer` 槽位且 `plan` 原则写“续用同一 reviewer”，与 `plan-review` 要求独立新审阅者 / 大包三轨并行的规则冲突。
   - 改为维护三类明确角色：
     - `pe`：单槽位常驻首席工程师（`pe=on` 时进 `decision` 前必登记；贯穿 `discover` / `decision` / `spec` / `plan` 根部裁剪；替换打 `[警告]`）。
     - `reviewer`：单槽位，负责 `decision` 与 `spec` 阶段（强制续用同一代理；替换打 `[警告]`）。
     - `plan-reviewer`：多槽位列表（支持可选 `--label`，如 `scope` / `risk` / `delivery`），用于登记 `plan-review` 的独立单审或多轨审阅者，追加不触发替换警告，且保留每轨 `agent_id` 与标签，便于后续推翻重审或局部复审时按角色精准复用。
   - 门禁同步对齐：`plan -> ready` 要求至少登记 1 名 `plan-reviewer`、`rounds>=1` 且最后一轮 `verdict=clean`；`round --stage plan` 校验 `plan-reviewer`（而非 `reviewer`）；`next_command` 在 `plan` 阶段按门禁顺序引导登记 `plan-reviewer`、记分诊轮次、复验清零与过门。
3. **Plan 阶段回改上游合同的轻量感知**：
   - 实战中 Plan Review 常会倒逼回补 `spec.md` 或 `contract-design.md`（如补齐最小视图 DTO、服务端判定字段、拆出文件步）。
   - 不把状态机复杂化成任意回环；在 `round` 命令增加可选开关 `--touched-upstream`，记录该轮回改了上游合同并打印联动提醒（重跑 `check-spec` 等确定性校验 + 确认受影响合同条款复验）。
4. **补强 `plan` 与 `ready` 阶段硬原则**：
   - `plan` 原则（纯流程级）：写前核对上游合同与代码/工具链现实（细则见 `impl-planning`）；送审前先在隔离环境跑通确定性机械校验；按 `plan-review` 派发独立 `plan-reviewer` 并保持 PE 参与根部裁剪；回改上游合同时标注 `--touched-upstream` 并联动重验；修订 material findings 后走 `focused-closure-verification` 记 `clean` 才过门。
   - `ready` 原则补充：向实施主控交接时标明干净基线分支、单票局部 vs 包级门禁边界，以及票据是否保持 `Draft` 由实施主控初始化。

### 2.2 属于 `impl-planning`（单阶段方法论）的首稿防线

将实战中“本可在 Plan 首稿一次做对”的共性教训，克制融入 `plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md` 与 `references/common-misjudgments.md`（保持版本号不变，不重复已有规则）：

1. **写前代码与工具链现实核查**：
   - 改动 Schema 非空列或约束前，先排查全部既有写入方并纳入前置票，避免首票破构建；
   - 核实项目门禁与 Harness 的真实 CLI 参数/隔离标志与套件路径解析，不凭猜测写命令或通配符套件名；
   - 改动 API/DTO 时明确 OpenAPI/客户端同步归属，并核准干净基线分支（如 `git merge-base`），不误将无关提交带入基线。
2. **结构不变式与合同闭环自检**：
   - 尾票不负责生成 `gate.md`（避免与 Final Gate 循环依赖）；长期规则分册修改归入对应业务票第 1 批，尾票只做一致性核对；
   - 新增独立权限或前端灰显/阻断逻辑时，先核对“导航 → 动作 → 零越权”闭环及服务端是否已吐出结构化判定字段，缺口先回补合同再写票。
3. **风险信号直落 Ticket AC 与送审前隔离预检**：
   - 命中 DB 约束/触发器、并发原子性、破坏性迁移/停写脚本等风险信号时，直接把真库实测、双连接并发/故障回滚、中断按幂等键续跑及双形态证据写进对应 Ticket AC；
   - 冻结送审前先在隔离临时目录/临时仓试跑 `check-spec`、`package init` 与 `package validate`（不污染工作区 `Draft` 状态），将机械错误拦在 `plan-review` 之前。

## 3. 状态文件兼容与 CLI 契约（`kickoff.py`）

- **向后兼容**：既有 `kickoff-state.json` 中 `agents` 只有 `pe` / `reviewer` 时，读取 `agents.get("plan_reviewers", [])` 自动兼容，无需迁移旧文件。
- **数据结构增量**：
  - `state["agents"]["plan_reviewers"]`：`[{"agent_id": "<id>", "label": "<optional>"}]`（按 `agent_id` 去重；重复登记同一 `agent_id` 且传入新 `label` 时更新 `label`，不报错不警告）。
  - `state["rounds"][i]["touched_upstream"]`：布尔值，仅在传入 `--touched-upstream` 时写入 `true`。
- **声明式单源**：`PIPELINE` 新增阶段 `skills` 字段与 `role:plan-reviewer` 门禁，`render_mermaid` 与 `SKILL.md` 的 Mermaid 区块通过 `diagram --sync-md` 自动保持一致。

## 4. 验证计划

1. **L0（`kickoff` 单测与静态同步）**：扩展 `skills/kickoff/tests/test_kickoff.py` 覆盖 `plan-reviewer` 多轨登记/去重/标签/门禁、`next_command` 引导、`--touched-upstream` 提醒、`skills` 输出、旧状态文件兼容与 `SKILL.md` 图块同步检查，全部通过。
2. **L1（实战包演练）**：使用 `2026-11-26-hr-refinement` 的真实路径在临时目录完整演练 `init -> confirm -> register(pe) -> bind-pkg -> advance(decision) -> register(reviewer) -> round -> advance(spec) -> round -> advance(plan) -> register(plan-reviewer x3) -> round(--touched-upstream) -> round(clean) -> advance(ready) -> status`，确认输出、门禁与降载体验符合设计。
3. **独立审阅**：派发 Sonnet (high) 独立对照本设计文档审查 `kickoff` 与 `impl-planning` 全部改动，闭环处理有效意见。
