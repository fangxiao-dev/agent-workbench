# Impl-Package SKILL 全量降载说明

> 状态：**2026-08 完成**。19 个 SKILL 主文件（~860 行）压缩为 **14 个判断启发式文件（231 行，-73%）**；references（~1,840 行）从"默认读"改"按需读"。跨宿主（Codex/Claude/Grok/DSH）通用，机制指针保持宿主无关。
> 行数口径：`Measure-Object -Line` 实测 md 主文件；evals/scripts/assets/tests 不计。

---

## 1. 背景与目标

Impl-Package 是一套跨宿主的开发工作流插件（Ticket 状态机、处境路由、review 编排、Gate）。它的问题：**SKILL 主文件同时承载流程、协议与判断**——主 session 每次进入阶段都要把整套方法论读进上下文，token 消耗大（此前审计：dev-with-track 族 + subagent 族 + 插件级 references 合计 ~34k token 常驻）。

降载目标：
- 主文件 ~860 → ~230 行（实际 231，-73%）；
- references 默认不再读，只按需读；
- 判断启发式留在 SKILL，机械/流程/协议下沉到机制；
- 不新增方法论（只删机械、压缩判断）；跨宿主行为不变坏。

## 2. 降载判据：M/J/O 三分法

每个 SKILL 的内容按三类归类，**只有 J 留在压缩后的主文件**：

| 类 | 含义 | 去向 |
| --- | --- | --- |
| **M 机械/协议** | 顺序、CLI 拼装、文件位置、schema、路由、轨迹格式 | 删 → 机制承接（typed 工具 / 原生命令 / 处境注入 / CLI 校验 / orchestrator / 脚本） |
| **J 判断启发式** | 怎么判断质量、边界、可信度、是否偏离、如何定级 | 保留并压缩成短句（1 行/条） |
| **O 编排** | subagent 角色分工、调度、收敛状态机 | 删 → preset / orchestrator / provider |

**判断/流程分界示例**（逐文件按此归类）：Safety admission、finding 接受/分类、Loop clean 判定、Gate 三态、fast path、P0/P1/P2 定级、READY/BLOCKED、claim-evidence 契约、停止证明是**判断**；registry 读取、phase→topology 映射、brief 组装、并行派发、fail-closed 聚合、报告模板、trail schema 是**机械**。

**指针宿主无关原则**：压缩稿里指向机制的句子不写 DSH 专属词（"pre-step hook"/"typed tools"），写"处境注入"/"语义 CLI"等通用表述；跨宿主路由保留 `/impl-package:xxx` 形式。DSH 下这些指针由具体机制兑现，其他宿主按需读 references。

## 3. 全量扫描基线（改造前）

### 3.1 主文件与目录体量

| SKILL | 主文件（前） | 目录 md 合计（前） | 类型 |
| --- | --- | --- | --- |
| grill-me-smartly | 170 | 170 | 编排（ledger+双 subagent） |
| do-review | 70 | 323 | 编排（review orchestrator） |
| dev-with-track | 67 | 118 | 执行控制（每轮） |
| impl-package 入口 | 55 | 75 | 路由 |
| verification-before-completion | 51 | 51 | 判断（claim-evidence） |
| safety-review | 47 | 58 | 审查（leaf） |
| execution-preflight | 43 | 55 | 检查（wave 读取） |
| review-code-by-standards | 43 | 225 | 审查（leaf） |
| standing-bookkeeper | 41 | 79 | 异常 slow path |
| plan-review | 40 | 136 | 审查 |
| impl-planning | 39 | 69 | 内容创建 |
| subagent-driven-development | 37 | 153 | 编排（worker） |
| grilling | 37 | 52 | 交互质询 |
| req-align (+2 sub-skills 59) | 34 | 320 | 内容创建 |
| review-code | 28 | 327 | 审查（leaf） |
| backfill-stable-docs | 25 | 160 | 流程（audit/apply/verify/retire） |
| review-code-by-spec | 23 | 36 | 审查（leaf） |
| to-tickets | 15 | 15 | 内容创建（切片） |
| create-task-dag | 14 | 121 | legacy 只读 |
| **合计** | **~860** | **~2,700** | |

### 3.2 插件级 references（不进主 session 默认读）

| 文件 | 行数 | 处置 |
| --- | --- | --- |
| situation-inputs.md | 864 | renderer 实现字典，**主 session 永不读**（删掉 SKILL 里的读取指示） |
| current-state.md | 61 | CLI/state 手册 → typed 工具 schema + 协议片段按需替代 |
| composition-contract.md | 60 | artifact 合同 → 工具/模板按需 |
| progressive-system-evidence.md | 58 | 保留**按需**（仅 material seam/昂贵 E2E/failure learning 时读） |
| 其余（system-design/runbook 等） | ~50 | 保留按需 |

## 4. 分组方案（19+2 → 14 文件，8 组）

| 组 | 成员 | 合并/独立 | 目标行数 |
| --- | --- | --- | --- |
| A 执行轴 | dev-with-track、subagent-driven-development | 各自独立 | ~12 / ~10 |
| B review 轴 | do-review | 独立 | ~18 |
| C 需求→计划 | req-align、impl-planning+to-tickets、plan-review | planning 合并 to-tickets | ~18 / ~20 / ~12 |
| D 边界与收口 | execution-preflight + standing-bookkeeper + verification-before-completion | **三合一** `execution-boundaries` | ~35 |
| E reviewer leaf | review-code / by-standards / by-spec / safety-review | 各自独立（preset 绑定，不合并） | ~15 / ~15 / ~12 / ~15 |
| F 内容/流程 | backfill-stable-docs、grill-me-smartly | 独立 | ~12 / ~35 |
| G 入口与轻量 | impl-package 入口 + grilling + create-task-dag | **三合一** | ~25 |

合并理由：D 组三者都是"边界判定"（执行前/异常/收口），合并不稀释语义且省一次默认读取；G 组三者是路由/轻量/legacy；to-tickets 的切片判断与 impl-planning 同属 planning 语义。

## 5. 逐文件降载明细

### 5.1 A 组：执行轴（每轮消耗，收益最大）

**dev-with-track**（67 → 9 行）
- 删除 → 承接：
  - §Restore 手动 validate→render→digest 循环 → **处境注入**（每步自动；Python 侧协议表随 render 输出）
  - CLI 命令/ER payload 拼装 → typed 工具 + `impl_package_state.py` 校验（SATISFIED 需 revision/environment、escape 三字段、轨迹只追加由 CLI 强制）
  - trail/handoff/checkpoint 协议细节 → Python 侧协议表（`attempt.record.handoff-*`、`attempt.record.checkpoint-*`、`attempt.record.trail-rotation-due` 等）
  - manual acceptance 模板 → assets 按需；talk-to-boss → 删
  - references/control-flow.md、runtime-protocol.md → 内容已由处境表 + Python 侧协议表逐处境承接（文件保留按需）
- 保留（判断）：Investigate/Decide/Implement/Evaluate 四步；checkpoint 时机（BLOCKED/retry/跨 session/交接）；escape 规则（偏离即写 kind=escape）；Gate 三态 + Stage 7；恢复指针（读 progress.md 不读 state.json 全文）；preflight 指针（四项 lane 首次激活一次）

**subagent-driven-development**（37 → 9 行）
- 删除 → 承接：worker resolver 解析表（`$grok-worker`/`@luna-worker` → 逻辑角色 → provider 映射）、envelope 字段清单（→ 结构化输出/工具描述）、fallback 细节（→ 一句话规则 + Python 侧协议表 `ticket.implement.worker-*` slug）、策略 YAML 格式（→ preset/orchestrator）
- 保留（判断）：mode 选择（investigate 禁 READY|BLOCKED/固定 6 行、fix 不重新裁决/fresh、review 只读无副作用）；review_scope（checkpoint|closure）；并行与失败（共享资源隔离、BLOCKED 不猜近似、一次 fallback、主 session 最终集成权）

### 5.2 B 组：review 编排轴

**do-review**（70 → 24 行）
- 删除 → 承接：
  - leaf 映射表 → **4 个只读 reviewer presets**（DSH 侧；跨宿主仍用 agents/review-track-*.md）
  - registry 默认 tracks / phase→topology 确定性路由 → **do-review-orchestrator** `resolveTopology`（读 reviewer-registry.json；closure 单选；显式名单 exact-in-order）
  - brief 组装 / anti-duplicate 模板 → orchestrator `buildBrief`（模板从 subagent-briefs.md 提取为常量）
  - ReviewRun 创建 → `review_ledger.py`（指针保留）
  - 并行派发与等待 → 原生 subagent（fresh 独立会话 + 结构化输出）
  - fail-closed 聚合 / 报告模板 → orchestrator `aggregateVerdicts` / `renderReport` + `impl_review_aggregate` 工具
- 保留（判断）：Gate 0（HEAD 固定、dirty 阻塞、leaf 必须、不可用停止询问）；Safety admission（六类边界，关键字是线索不是证据）；finding 接受/去重（按 broken invariant）/分类（blocker/follow-up/backlog）；Track C source recheck 结论（唯一裁决/req-align/owner）；Loop clean 与收敛；closure ≠ terminal；带到达路径的 claim 证据检查

### 5.3 E 组：reviewer leaf 家族（各自压缩；leaf 只进子代理上下文，主 session 无感）

| 文件 | 前→后 | 保留判断 | 删除→承接 |
| --- | --- | --- | --- |
| review-code | 28→17 | 审查意图优先序（behavior/error/security/…）；full/focused profile 选择与升级规则 | 输出合同 → leaf 结构化输出（verdict/coverage/findings）；checklist → references 按需 |
| review-code-by-standards | 43→17 | 仓库规范优先；Fowler baseline（judgement call）；codebase-design vocabulary；深度选择 | strict-maintainability.md 按需；输出 → 结构化 |
| review-code-by-spec | 23→13 | spec 忠实度；章节级合同引用；不以规范/smell 替代合同 | 输出 → 结构化 |
| safety-review | 47→18 | 触发信号；收缩型 focused path 三点核对；P0/P1/P2 fail-closed | 五类清单 → `references/five-categories.md`（新文件，从原文提取）；SHA 固定 → 机制 |

### 5.4 C 组：需求→计划轴

**req-align**（34 → 13 行）：保留路由判定（full/decision-only/spec-only）、contract impact 分类、no-contract fast path 判定；删除主路径步骤（→ SUB-SKILL 按需 + bookkeeper 承接）、Package ID/影响路由细节（→ package-lifecycle.md 按需）。sub-skills（decision 25/spec 34）保留按需。

**impl-planning + to-tickets**（39+15 → 16 行）：保留 admission backstop 判定（缺合同即停→req-align）、纵向切片/seam 冻结判断、验证分级与 evidence owner、Ticket AC 可观察性；删除必填字段/Composition 写法/文件位置（→ composition contract + 模板）、bookkeeper 命令（→ CLI）。

**plan-review**（40 → 13 行）：保留 material finding 判定、verdict 判定（cleared/revise/owner-decision/blocked）、bundle-admission 判定、decision waves 收敛；checklists → references 按需；输出 → final-report.md 模板。

### 5.5 D 组：边界与收口（三合一）

**execution-boundaries**（43+41+51 → 19 行，三节独立）：
- 执行前（preflight）：READY/BLOCKED 判定、四项 lane 核查、授权 write-set 边界；Wave 读取顺序删（恢复/处境注入承接）
- 异常（bookkeeper）：slow path 触发判定、主 thread 唯一写入权边界；receipts 细节删
- 收口（verification）：claim-evidence 五条契约、复用与独立验证判断、真实状态报告（implemented, not verified / Integrated, gate open）

### 5.6 F 组：内容/流程型

**backfill-stable-docs**（25 → 10 行）：保留 audit/apply/verify/retire 授权判定（owner 精确批准、destructive-apply 授权）；配置校验/inventory/Gate 识别/item ID → 6 个脚本 + config schema 强制。

**grill-me-smartly**（170 → 30 行）：保留 Review/Apply 两阶段边界、四角色分工（Questioner 决策树/Answerer 本地事实/Critic 收敛）、问题质量判断、停止证明判定、收敛判断；ledger 命令清单/中文摘要区块/10 步 workflow → `grill_ledger.py` 脚本 + 循环骨架。

### 5.7 G 组：入口与轻量（三合一）

**impl-package 入口**（55+37+14 → 23 行）：
- 入口：18 原生命令索引表 + 最小 package 结构（人类参考）；核心原则压缩为 3 条 + references 指针
- 交互质询（grilling）：frontier 穷尽/分批不遗漏、事实自查、收敛后写回边界（细节 → ../grilling/rubric.md 按需）
- Legacy（create-task-dag）：只读标注 + 迁移指针（细节 → ../create-task-dag/references/ 按需）

## 6. 机制承接总览

| 机械负担（原来在 SKILL 里） | 承接机制 | 状态 |
| --- | --- | --- |
| 每轮 validate → render → digest | pre-step 处境注入 + Python render 的 protocol 字段 | ✅ |
| CLI 命令 / JSON payload 拼装 | 9 个 typed 工具（impl_package_validate / impl_situation_render / impl_ticket_transition / impl_evidence_add / impl_evidence_invalidate / impl_recovery_checkpoint / impl_recovery_judgment / impl_gate_commit / impl_trail_append） | ✅ |
| 阶段路由表 | 18 个原生命令（impl-req-align … impl-backfill-stable-docs，0 token） | ✅ |
| worker 派发 / 宿主名 | 原生 subagent（subagent_codex / subagent_grok） | ✅ |
| review topology / brief / 聚合 / 报告 | do-review-orchestrator.mjs（resolveTopology / buildBrief / aggregateVerdicts / renderReport）+ `impl_review_aggregate` 工具 | ✅ 纯函数完成；并行派发接线待续 |
| reviewer 只读边界 | 4 个只读 reviewer presets（read/git_show/glob/grep，无写/派发） | ✅ |
| 审查清单（safety 五类等） | references 按需读（five-categories.md 等） | ✅ |
| skill on-demand 加载 | skill catalog 注册（customSkillDirs → plugin skills） | ✅ |

## 7. 判断启发式保留清单（审校核对，21 项）

逐文件压缩后，以下判断语义必须保留（已由主控按 `review-checklist.md` 逐项核对）：

Gate 三态与 Stage 7 · SATISFIED 前提（revision/environment/claims 覆盖）· RETIRED 语义 · escape 写法规格 · trail 只追加 · checkpoint 不授权派发 · P0/P1/P2 fail-closed · fast path 条件 · Safety admission 六类边界 · finding 去重（broken invariant）/分类 · Loop 收敛（两轮 clean + 全 dormant）· closure ≠ terminal · Track C recheck 结论三选一 · claim-evidence 五条 · 真实状态报告 · READY/BLOCKED 边界 · bookkeeper 唯一写入权 · admission backstop · worker mode 语义（investigate 禁 READY、fix 不重裁决）· grill 停止证明 · Review/Apply 两阶段。

## 8. 验证结果

| 套件 | 结果 |
| --- | --- |
| 仓库级契约测试（test_impl_package_plugin.py + test_subagent_driven_development_contract.py） | 14 passed（断言更新为新结构） |
| 插件 evals（description_trigger / review_contract / 契约） | 22 passed |
| do-review 内部契约（test_three_track_contract.py 等） | 12 passed（断言更新为压缩稿语义） |
| grill src（grill_ledger_core） | passed |
| DSH smoke（resolution/protocols/commands/orchestrator/reviewer presets/readLines） | ALL PASS |
| 行数 | 231 行（-73%） |

被合并的旧 SKILL.md 已删除（to-tickets / execution-preflight / standing-bookkeeper / verification-before-completion / grilling / create-task-dag）；references/rubric/evals 保留按需，无残留引用。

## 9. 遗留与后续

- **orchestrator 派发接线**：纯函数核心（topology/brief/聚合/报告）完整；`dispatchLeaf`/`createReviewRun` 的并行派发与 ledger 接线待接入（主 session 驱动或 `impl-do-review` 命令触发）。
- **grill ledger 目录名**：脚本默认路径含 `codex-grill`（宿主专属），压缩稿已用"OS 临时目录"规避；脚本层改名待办。
- **跨宿主**：压缩版 SKILL 机械细节从"默认读"变"按需读"；Codex/Claude 的执行效率依赖各自 adapter 成熟度，如遇回归可单文件 git revert（每文件独立 commit）。
- **evals 宿主名断言**：subagent-driven-development 的 evals.json 仍含 `$grok-worker` 等旧断言，随 DSH provider 化后需迁移（登记，未执行）。
