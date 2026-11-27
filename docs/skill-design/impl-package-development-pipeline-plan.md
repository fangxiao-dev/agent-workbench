# 实施包开发 Pipeline：二八原则实施计划

- **目标仓库 / Worktree**：`D:/CodeSpace/agent-workbench/.worktrees/development-pipeline`
- **需求基线**：`docs/skill-design/impl-package-development-pipeline-261126.md`
- **风格标杆**：`skills/kickoff/`（纯流程编排、外置 `pipeline.json` + 职责清晰的纯 Python stdlib 模块拆分、薄每包状态、零侵入下游内容）

---

## 1. 核心原则与红线

1. **二八原则**：覆盖原设计中 80% 让主控掌控大型实施包全流程的核心能力（统一视图、自动刷新、多票并行、跨 Ticket 多返回组合审阅、审阅轮次/收敛诚实提示、每包模型路由与 agent 池续用、宽松补录与恢复），坚决砍掉 20% 导致复杂度爆炸的对抗式机器证明与历史回溯引擎。
2. **非必要不动下游**：既有 `impl-package` 运行时、trail、do-review、audit 均已稳定运转。只在极少数必须接缝的入口文档/插件清单做局部改动（总计 <30 行），严禁整体重构或向底层引擎灌入新状态机。
3. **只管流程，不管内容**：Pipeline 负责状态聚合、流程提醒、缺失标注和下一步命令指引；业务裁决、分诊取舍、隔离快照等价判断、是否换人仍归主控，工具不做“防作弊”强拦截。
4. **合并概念与模块化拆分（参考 `skills/kickoff/`）**：
   - 不另建 `development-pipeline` 新 Skill，直接将 `dev-loop` 与实施包开发 Pipeline 合并为统一的 `skills/dev-loop/`（与 `skills/kickoff/` 同级对称：包外普通任务走轻量 5 步闭环，实施包模式走 `dev_loop.py` 编排 CLI）。
   - **不设行数硬指标**，以职责清晰、可读可维护为准，仿照 `skills/kickoff/` 将流程定义、存储、只读事实聚合、推导引擎、视图渲染与薄 CLI 入口拆分到独立模块（全部纯 Python stdlib）：
     - `skills/dev-loop/pipeline.json`：外置声明式包级主线定义与默认元数据；
     - `skills/dev-loop/scripts/store.py`：每包轻量状态（`.impl-package/development-pipeline.json`）的原子读写、symlink 校验与损坏降级；
     - `skills/dev-loop/scripts/facts.py`：只读事实聚合（相对路径定位 `situation.py` + 降级读 `state.json`，读取 `.rounds.json` 摘要与收敛推导）；
     - `skills/dev-loop/scripts/engine.py`：加载 `pipeline.json`，推导包级主线与统一状态快照，以及 `config`/`agent`/`batch` 领域操作；
     - `skills/dev-loop/scripts/render.py`：人类可读紧凑视图格式化（与 JSON 输出解耦）；
     - `skills/dev-loop/scripts/dev_loop.py`：薄 CLI 入口（argparse、子命令分发、输出与退出码）。
   - `skills/dev-loop/SKILL.md`：合并包外轻量循环 + 包内 Pipeline 入口。
   - 聚焦测试 `skills/dev-loop/tests/test_dev_loop.py`：覆盖核心场景与边界，保持精炼可读。

---

## 2. 明确的范围边界

### 2.1 必须实现（Core 80%）

1. **声明式包级主线（共享流程定义）**
   - 表达统一主线：`intake`（接入/恢复）→ `tickets`（Ticket 并行推进）→ `final-review`（包级终审）→ `final-verify`（最终验证）→ `gate`（Gate）→ `closeout`（收尾）。
   - 多 Ticket 与多审阅批次并行运行，不强制全局串行锁死；自动根据当前权威事实推导每个主线节点的状态（`done` / `active` / `pending` / `blocked` / `attention`）。

2. **只读聚合现有权威事实（自动刷新，无手动 `advance`）**
   - **Package / Situation 事实**：复用现有 `situation.py`（直接 import 其只读入口，或读取 `state.json` + 既有输出）取得 Attempt、Ticket 状态（`PENDING`/`BLOCKED`/`NEEDS-REVALIDATION`/`SATISFIED`/`RETIRED`）、依赖关系、`blocking`/`runnable`/`withheld`/`in_flight`/`manual`/`undetermined`、待派审的 `worker-return` 与 Gate 缺口。
   - **审阅轮次事实**：读取批次关联（或包内可发现）的 `do-review` `.rounds.json`，提取当前 `group`、当前 `round`、`phase`、各已登记轨道 `verdict`、open findings 数量与清单、`nextAction`。
   - **诚实的收敛与分诊提示**：
     - 本轮尚有未返回轨道 → 提示“等待审阅轨收齐”（不提前分诊）。
     - 轨道收齐并关轮，仍有 open findings 或未标分诊完成 → 提示“待主控统一分诊 / 安排修复”。
     - 任一轨道为 `UNCERTAIN` / `INCOMPLETE` / `FAIL` 或缺少有效 verdict → **明确标示未收敛/待核实**，绝不以“无 finding”冒充 PASS。

3. **每包轻量状态持久化（`.impl-package/development-pipeline.json`）**
   - 按包独立保存，**不复制** Ticket、Evidence、Gate、Rounds 的权威状态，只存既有工具缺失的 3 块运行属性：
     1. **`routing`（模型路由建议）**：按职责（如 `implementer`、`reviewer`、`fixer` 等）记录 `{ "model": "...", "effort": "..." }`。派发前在视图中提示；修改 `routing` 只影响后续推荐，**不改写**已有 `agents` 中的历史自填配置。
     2. **`agents`（Agent 池）**：记录 `id`、`role`、`scope`（关联 Ticket / batch）、`host`、`agent_id`（宿主返回的可恢复 ID，缺则显示 `unconfirmed`）、自填 `model` / `effort`（入口不可指定时允许留空/如实填写，不作派发后强制核验）、`review_group`（可选）、`status`（`active` / `replaced` / `retired`）、`replaced_by`、`handoff_note`、`note`。支持随时宽松补录。
     3. **`batches`（跨 Ticket / 多返回组合审阅批次）**：记录 `batch_id`、`tickets`（数组）、`returns`（数组）、`reviewed_head`、`snapshot_kind`（`integrated` / `isolated`）、`review_run_id`、`rounds_file`、`status`（`open` / `triaged` / `closed` / `superseded`）、`ticket_notes`（按票记录主控核对/采信备注）、`note`。
   - **视图消解与提醒**：
     - 已被有效 `batch`（`open`/`triaged`/`closed`）覆盖的 `returns`，在 `pipeline status` 中归入对应审阅批次展示，不再重复提示为“未派审”；未覆盖的 return 保留欠审提示。
     - 若 `reviewed_head` 与当前仓库 `HEAD`（可获取时）不一致，或 `snapshot_kind == "isolated"`，视图清晰提醒主控核对影响范围、确认等价并按票执行 `evidence add`。
     - 组织新审阅组时，视图列出 `agents` 中已知的前驱审阅者，提醒主控保持审阅独立性（提示而非强制拦截）。

4. **宽松恢复与局部降级**
   - 进行中的包没有 `.impl-package/development-pipeline.json` 时，直接按只读视图正常接入。
   - `.rounds.json` 缺失、JSON 损坏或 `situation` 某项不可推导时，仅将对应对象标为 `unconfirmed` / `undetermined` 并说明来源，不崩溃、不阻断其他无关 Ticket 推进。
   - 写入 `.impl-package/development-pipeline.json` 使用原子写（临时文件 + `os.replace`），拒绝 symlink 路径。

5. **极简 CLI 接口（均支持 `--json`，写入成功后自动输出刷新后的紧凑状态或 JSON）**
   - `status --package <dir> [--json]`：统一主控视图（包级主线 + Ticket 概览 + 活跃审阅批次与轮次/verdict + 未覆审 return + 续用 agent 与模型路由提示 + 下一步推荐操作及原 CLI 命令指引）。
   - `config show|set-route --package <dir> ...`：查看 / 设置本包模型路由建议。
   - `agent register|update|replace|list --package <dir> ...`：登记、补录、替代 agent 与自填模型/强度。
   - `batch register|update|close|list --package <dir> ...`：登记 / 更新 / 关闭跨 Ticket 多返回组合审阅批次及逐票备注。

### 2.2 允许改动的下游接缝（严格限制）

| 文件 | 允许的最小改动 |
|---|---|
| `plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md` | 阶段导航表增加 1 行指向 `dev-loop` |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md` | 开头/职责边界增加 1–2 行说明流程状态与推进视图由 `dev-loop` 统一提供，本 Skill 保留业务裁决与契约 |

### 2.3 严禁改动 / 明确不做（Non-Goals）

- **严禁改动**：`cmd_trail.py`、`attempt_store.py`、`engine.py`、`acceptance.py`、`cmd_evidence.py`、`command_groups.py`、`review_rounds.py`、`do-review/*`、`dispatch_audit.py`、`review_track_stats.py`、`situation.py`（若确需极小只读辅助，先停下说明）。
- **明确不做**：
  - 不写 `review_batch.py`（报告 7 行头解析、`scopeEvidence` 行格式校验、triage 全等核对）。
  - 不写 `review_equivalence.py`（哈希附件、`ticket-assessments/`、git ancestor 强制证明、替代证据恢复链）。
  - 不写 `recover-dispatch` 历史回溯引擎、`dispatch.recovery_pending`、`recovery_provenance`。
  - 不做迟到身份补录导致历史审阅批次自动失效的状态机。
  - 不在 `development_pipeline.py` 里重包一层底层写命令代理（`evidence add`、`gate`、`do-review`、trail 仍由主控调用原 CLI）。

---

## 3. 交付与验证要求

1. **新增文件**：
   - `skills/dev-loop/pipeline.json`
   - `skills/dev-loop/scripts/store.py`
   - `skills/dev-loop/scripts/facts.py`
   - `skills/dev-loop/scripts/engine.py`
   - `skills/dev-loop/scripts/render.py`
   - `skills/dev-loop/scripts/dev_loop.py`
   - `skills/dev-loop/SKILL.md`
   - `skills/dev-loop/tests/test_dev_loop.py`
2. **聚焦测试必须覆盖**：
   - 单 Ticket 小包与进行中旧包（无 profile）的只读接入与主线状态推导；
   - 双 Ticket 并行 + 跨 Ticket 多返回 `batch register` 在 `status` 中消解对应 pending returns，未纳入的 return 仍提示欠审；
   - 读取 `.rounds.json`：轨道未收齐提示等待、收齐关轮提示分诊、存在 `UNCERTAIN` 或 `INCOMPLETE` 且无 finding 时明确标示**未收敛**；
   - `isolated` 快照或 `reviewed_head` 与当前 HEAD 不一致时给出核对与 `evidence add` 提示；
   - 每包 `routing` 隔离（更新 `routing` 不改写已有 `agents` 记录）、`agent` 宽松补录（缺 ID 标 `unconfirmed`）、原实现者续用推荐、替代交接与前驱审阅者换人提醒；
   - 损坏/缺失 `.rounds.json` 局部降级不阻断其他 Ticket；
   - 运行既有 `impl-package` 相关测试，确认零回归。
3. **验证命令**：在 worktree 根目录运行 `python -m unittest` 覆盖 `skills/dev-loop/tests/test_dev_loop.py` 以及 `tests/test_impl_package_plugin.py`、`tests/test_situation_render.py`、`tests/test_impl_package_state.py`。
