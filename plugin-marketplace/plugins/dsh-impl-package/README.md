# dsh-impl-package — Impl-Package 的 DSH 原生适配

薄而原生的 DSH adapter：**保留现有 Python core 不动**，把主 session 的机械负担下沉到 DSH 原生机制里。

- Python core（`plugin-marketplace/plugins/impl-package/scripts/`）、`state.json`、Git 锚点、Ticket/evidence/Gate 语义继续是**唯一权威**；
- 本插件只做三件事：**处境注入（agent/pre-step hook）**、**typed CLI 工具**、**原生 subagent 派发（Codex）**；
- DSH session 只记执行轨迹，不成为 package 事实源（不双写）。

**适配目标**：dsh `latest`（npm `dist-tags.latest` = `0.1.5-rc.1`，`next` = `0.1.5-rc.2`）。`alpha` 线 0.1.6-alpha.1 的差异见文末「2026-09 重适配」——其中 workflow 执行器行名不兼容，切到 alpha 前必须先改那一行。

## SKILL 降载（2026-08 完成）

19 个 SKILL 主文件（~860 行）经压缩后恢复 standalone `grilling` 入口，现为 **14 个判断启发式文件**；references（~1,840 行）从"默认读"改"按需读"。逐文件行数见 [baseline-skill-sizes.md](baseline-skill-sizes.md)。降载判据：**流程题（可确定执行）→ 机制；判断题（需要模型判断）→ SKILL 启发式**。

| 降载去向 | 承接 |
| --- | --- |
| 每轮 validate→render→digest | pre-step 处境注入（消费 Python render 的 `protocol` 字段） |
| CLI 拼装 / JSON payload | 14 个 typed tools（impl_*） |
| 阶段路由表 | 16 个原生命令（15 个 impl-* + call-codex，0 token） |
| worker 派发 / 宿主名 | 原生 subagent（subagent_codex） |
| review topology / brief / 聚合 | do-review-orchestrator（resolveTopology / buildBrief / aggregateVerdicts / renderReport / orchestrate）+ `impl_review_run` 工具 |
| reviewer leaf 只读 | 派发组装：persona + `toolFilter: { allow: [read, grep, glob, skill, git_show] }`（非独立 preset） |

跨宿主：压缩版 SKILL 保持宿主无关（指针写"语义 CLI / 处境注入"），Codex/Claude/Grok 同样受益；机械细节在 DSH 由工具/机制承接，其他宿主按需读 references。压缩判定与逐段对照表见 `review-checklist.md` 与各 commit。

## 组件

```
plugin-marketplace/plugins/dsh-impl-package/
├─ package.json               # dsh.bundle.patch 声明，profile bundle
├─ cordis.patch.yml           # 把 host half + Codex provider 插入 profile roster
├─ lib/index.mjs              # host half：启动时把 presets/ 同步到 ~/.dsh/.agent-presets/（含路径代换）
├─ presets/
│  └─ impl-package/           # 「Impl-Package 主控」agent preset（自包含；唯一预设）
│     ├─ preset.yml
│     ├─ agent.cordis.yml     # standard 基座 + anchor/hook/tools/commands/orchestrator + subagent 工具行
│     ├─ situation-hook.mjs   # agent/pre-step：validate → situation render → 注入处境+协议
│     ├─ impl-anchor.mjs      # 两阶段恢复锚定（锁写工具，确认处境后放开）
│     ├─ impl-tools.mjs       # 14 个 typed 工具，直接调用 impl_package_state.py CLI
│     ├─ commands.mjs         # 16 个 0-token 阶段路由命令（15 个 impl-* + call-codex）
│     ├─ do-review-orchestrator.mjs  # review 编排（topology/brief/并行派发/聚合/报告 + impl_review_run）
│     └─ git-readonly.mjs     # git_show（leaf 继承，读不可变 contract source）
├─ baseline-skill-sizes.md    # SKILL 降载基线与维护操作
├─ review-checklist.md        # 审校清单（判断语义保留项）
└─ test/
   ├─ smoke-test.mjs          # 纯逻辑冒烟测试（node 直接跑，无需 DSH）
   └─ sync-now.mjs            # 手动触发 preset 同步（改 preset 源后立即生效）
```

> **reviewer leaf 不是预设**：4 个 leaf（Track A/B/C/Safety）由 `impl_review_run` 派发时组装——start request 带只读 persona + `toolFilter: { allow: [read, grep, glob, skill, git_show] }`（真只读）+ 从主 preset skill catalog 加载声明 skill。不创建独立 preset 目录，预设选择器只显示「Impl-Package 主控」。派发的子代理继承主 composition，故 `situation-hook` 对 `delegationDepth > 0` 的子代理跳过处境注入（leaf 上下文保持 scoped）。

## 安装

```powershell
# 0. dsh 本体（适配目标 = npm latest，即 0.1.5-rc.1；跨到 0.1.6-alpha.1 见文末迁移项）
npm install -g @deepseek-ai/dsh

# 1. 注册 profile bundle（会在 package.json 的 dsh.profile.bundles 追加 dsh-impl-package，
#    并把 host half + Codex provider 行挂到 profile roster——见 cordis.patch.yml）
dsh plugin --profile desktop add "link:D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\dsh-impl-package"

# 2. 安装官方 subagent provider 包（**硬依赖**，见下方说明；平台 payload 随包自带）
cd "$env:USERPROFILE\.dsh\profiles\desktop"
pnpm add "@deepseek-ai/dsh-subagent-codex"

# 3. 无头预检（可选但推荐）：一次性 headless 任务走完整 boot，
#    能抓 dump-config 查不出的缺包/坏行；通过标准是回答 BOOT-OK
dsh --profile desktop "Reply with exactly: BOOT-OK"

# 4. 重启 DSH Desktop（bundle 生效；host half 启动时同步 preset；安装事务收口）
```

> 说明：**provider 包是硬依赖**——`cordis.patch.yml` 把 `subagent-codex` 行插进 profile roster，
> 包未安装时（0.1.5-rc.1 实测）整个 profile **无法启动**（`plugin tree failed to load`），不是静默降级。
> preset 里的 `subagent_codex` 工具行才是在 provider 挂载后自动注册（`subagent/provider-added`）。
> 注意 `--dump-config` 只组树、**不 import 模块**：缺包/坏模块名它会照常 exit 0，boot 期才暴露——
> 组合问题用上面的无头预检抓，不要只看 dump-config。
> 工作区路径：preset 中的 `{{WORKBENCH_ROOT}}` 由 host half 在同步时按插件真实位置解析
> （`link:` 安装会穿过 junction 解析）；跨仓移动时设 `AGENT_WORKBENCH_ROOT` 覆盖。

## 使用

1. 重启后，新建会话 → 预设选择器选 **Impl-Package 主控**（`~/.dsh/.agent-presets/impl-package`）。
2. 会话 cwd 指向任一 Impl-Package 仓库（含 `docs/implementations/<topic>/.impl-package/state.json`）。
3. 每步 agent 会自动收到一行紧凑处境（digest 变化才注入，避免噪声）：

```
[impl-package 处境] digest=xxxxxxxxxxxx
选中: attempt.record.session-resumed · basis=prose · judgment=false
动作:
  - restore-checkpoint（默认）: /impl-package:dev-with-track restore from active checkpoint — 不读取完整历史
并列匹配: 0 | 未判定: 38 | 未匹配: 0
验证: package validate 通过
```

4. 机械写入走 typed 工具，不再拼 shell：

| 工具 | 对应 CLI |
| --- | --- |
| `impl_package_validate` | `package validate [--commit]` |
| `impl_situation_render` | `situation.py render --json`（可自动推导 validation-result） |
| `impl_ticket_transition` | `ticket satisfy/block/needs-revalidation/pending/retire`（按 action 校验必填项） |
| `impl_evidence_add` / `impl_evidence_add_batch` | `evidence add`（stdin JSON；batch 发数组，返回 {records, added, duplicates}） |
| `impl_evidence_invalidate` / `impl_evidence_retire_claim` | `evidence invalidate` / `evidence retire-claim` |
| `impl_recovery_checkpoint` / `impl_recovery_judgment` | `recovery checkpoint/judgment` |
| `impl_gate_commit` | `gate <verdict> --comparison-commit --reason …` |
| `impl_trail_dispatch` | `trail append`（$dispatcher 合同：dispatch_id/candidate_id/mode/chosen/receipt；digest/review 字段走具名 flag） |
| `impl_trail_escape` | `trail append`（escape；subject/deviation/reason） |
| `impl_trail_fact` | `trail append`（fact；subject/key/value） |
| `impl_trail_worker_return` | `trail append`（worker-return；of 指回 dispatch + 唯一 return_id；代码增量带 code_delta+consumption_id 配对） |

5. Worker 派发：`subagent_codex`（官方 Codex provider，ephemeral thread，复用本机登录）。
   One-shot：收最终答案文本，不回传子进程内部轨迹；brief 边界与 receipt 语义沿用
   `$dispatcher` 合同（dispatch 记录 dispatch_id/candidate_id/subject/mode/chosen/resource_keys/receipt，
   worker return 用 of 指回 dispatch 并带唯一 return_id）。

## 处境注入的设计决策

- **digest 未变不注入**：DSH 的 pre-step 每步触发，重复注入会污染上下文；只在 digest 变化（或 session 冷启动/压缩后）注入完整处境。内存按 session 缓存，重启后首步自动重新注入。
- **处境驱动协议注入**：`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/protocols.json` 是跨宿主唯一协议表，为 situation slug 提供 2-4 行协议片段（判断/处理规则，来源 dev-with-track / do-review / dispatcher 派发合同）；Python render 把命中的片段放进 `selected.protocol`，hook 只消费这个字段。模型每步只见「当前处境 + 当前动作的规则」，不再读整套 SKILL/references。`default` 兜底未覆盖 slug。
- **恢复锚定（impl-anchor）**：两阶段门控——Phase 1 工具收敛为只读白名单（read/grep/glob/skill/validate/situation_render/subagent/ask_user_question），写工具（ticket/evidence/recovery/gate/trail/write/edit/bash/pwsh）隐藏；模型首轮引用注入的 digest/slug（或 maxAnchorSteps=3 兜底）后晋升，全量工具放开。压缩后回落 Phase 1 重新锚定。**透明性**：无处境注入的会话（非 Impl-Package 任务）立即放开，绝不锁死。与梁神取向不同：梁神锁通用工具锚定推理轨迹，impl-anchor 锁状态写入锚定 package 心智模型。
- **注入是导航，不是 gate**：模型仍可偏离，按 `dev-with-track` 合同写 `kind=escape` 轨迹行（`impl_trail_escape`）。
- **compaction pressure 未接**：renderer 缺省时 `attempt.compaction_pressure_high` 保持不可判定；后续可读 DSH 原生压缩观测接入。
- **脚本定位**：`situation.py` / `impl_package_state.py` 通过最近祖先树的 `plugin-marketplace/plugins/impl-package/scripts` 解析，或 preset 配置 `implScriptsRoot` 显式指定（同步时由 host half 代换 `{{WORKBENCH_ROOT}}`）；package 目录解析优先级：`packagePath` 配置 → cwd 向上最近含 state.json → git root 下 `docs/implementations/<topic>/`。

## 原生命令（0 token 路由）

对齐 impl-package/SKILL.md 的现行 native entry 表（2026-09）：`/impl-req-align`、`/impl-grill-me-smartly`、
`/impl-impl-planning`、`/impl-plan-review`、`/impl-to-tickets`、`/impl-execution-boundaries`、`/impl-dispatcher`、
`/impl-dev-with-track`、`/impl-monitor-progress`、`/impl-do-review`、`/impl-review-code`、
`/impl-review-code-by-standards`、`/impl-review-code-by-spec`、`/impl-safety-review`、
`/impl-backfill-stable-docs`、`/call-codex`（Codex CLI 协作模式：resume 续接/流式隔离/及时调整 prompt/小步纪律/降级探针/review 回投修复）。

已合并/退役的旧入口不再注册：`execution-preflight` 与 `verification-before-completion` → `execution-boundaries`；
`subagent-driven-development` 与 `standing-bookkeeper` → `dispatcher`；`grilling`、`create-task-dag` 保持经由
skill catalog 可达（非 impl-package 阶段路由）。

用户输入斜杠命令 → 命令向 agent steer 一条路由指令（`source.kind='impl-package-command'`），命令本身
不进模型历史（0 token）。`recordInput: false`——steered 消息就是权威领域记录，避免 command/run 重复记录。
原 `/impl-package:*` 路由表（impl-package/SKILL.md）从主 session 上下文里消失。

## 进度可见性

长驻 worker（`subagent_codex` 一发式派发）无中途输出。进度查看走 Impl-Package 的
`monitor-progress` skill（`/impl-monitor-progress` 命令）：它打开 package 的实时进度页面，
并可选创建只读主控监控 automation。插件侧不重复实现取样——`progress.md` 由 Python core
的 `refresh-progress` 维护为 machine-owned 投影，`state.json` 的 Ticket/Gate 状态是唯一权威。

## 边界与暂缓

- **不做双重 runtime**：不重写 Python core；不用 DSH Goal 替代 Ticket；不用 session event 替代 trail。
- **外部 subagent 只读边界**：Codex 是一发式 out-of-process，宿主无法 toolFilter/persona；reviewer 若用它需独立 worktree/只读 sandbox。进程内 `spawn`/`fork` 子代理才支持 `toolFilter`/`persona`/`outputSchema`。
- **暂缓**：只读 reviewer preset（leaf 改由派发组装，不建独立 preset）、progress/gate 的 Web UI 投影、pre-step 读 DSH 原生压缩压力。
- DSH 仍为 Developer Preview：薄适配，破坏性变更影响面小；本插件全部文件可随时 `dsh plugin --profile desktop remove dsh-impl-package` 撤销。

## 压缩与 handoff 决策（防误接）

`attempt.record.handoff-due` 由 `attempt.compaction_pressure_high` 驱动，需要宿主传入 `--compaction-pressure`。DSH 压缩后在同一 session 继续，由 `impl-anchor` 重新锚定；situation-hook 保持不传此参数，压缩压力保持 unknown，不触发换会话建议。

DSH 的压缩感知归 `impl-anchor` 回落逻辑；轨迹轮换等包内恢复仍由跨宿主 harness 负责。交接内容统一使用 `handoff`，不在适配器中维护会话创建或重发协议。

**检查清单（未来改动时）**：
- [ ] 不要给 situation-hook 的 render 调用加 `--compaction-pressure`
- [ ] 压缩感知需求 → 改 `impl-anchor.mjs`（回落重锚定），不是接通 handoff-due
- [ ] 若 DSH 处境注入需要过滤某类 slug → 在 DSH 侧（hook/anchor）过滤，不动跨宿主处境表

## 2026-09 重适配（对齐 npm latest = dsh 0.1.5-rc.1）

上次适配冻结于 2026-08-26（上游 v0.1.0-rc.8 时代）；期间上游发布到 0.1.5 线，原插件演进约 140 提交。目标取 **npm `dist-tags.latest`**（`0.1.5-rc.1`），而非按发布日期最新的 `alpha`（`0.1.6-alpha.1`）——`npm install -g @deepseek-ai/dsh` 默认装 latest，适配面须与默认安装一致。逐项：

**上游破坏性变更（必须吃掉）**

- persona 配置拆分：`text` 键已废弃 → `prefix`（身份 + $dispatcher 合同导向）+ `suffix`（工作目录）。**0.1.5-rc.1 起已生效**，对齐其 builtin `standard` 预设形状。
- tool-web 对齐上游默认 `fetch: true`（0.1.2 起公开 WebFetch 默认开启）。
- 已确认无需改动：`agent/pre-step` 契约未变（payload `{agent, messages, turn, step, signal}` + `PreStepDecision`）；被 `agent/created` 取代的是 `agent/session-start`，本插件未使用；Session 格式 V3 只影响自写日志读取器，本插件不读 session 日志。

**Impl-Package 语义对齐（原插件 140 提交的漂移）**

- trail schema 对齐 engine `_validate_trail_event`（$dispatcher 合并带来的派发凭据语义）：dispatch 必填 `dispatch_id/candidate_id/mode(四值)/chosen/receipt`；worker-return 必填 `of/return_id`，代码增量带 `code_delta+consumption_id` 配对。impl-tools 构造器逐字段重写，smoke test 与 Python 源做 enum parity。
- evidence 新增 `impl_evidence_add_batch`（stdin 数组批量，幂等返回 {records, added, duplicates}）与 `impl_evidence_retire_claim`（`evidence retire-claim` 子命令），typed tools 12 → 14。
- 命令表按现行路由表重写（18 → 16）：+`/impl-dispatcher`、`/impl-monitor-progress`、`/impl-execution-boundaries`；移除已合并/退役的 6 个旧入口（含已知失效的 `/impl-subagent-driven-development`）。
- persona/hook 文案里的 worker-resolver envelope 引用更新为 `$dispatcher` 合同。
- do-review-orchestrator 无需改动：reviewer-registry.json、review phase/track 常量、review_ledger.py 均未变。

**机器路径与能力收敛**

- preset 中全部绝对路径改为 `{{WORKBENCH_ROOT}}` 标记，host half 在 preset 同步时按插件真实位置代换（`AGENT_WORKBENCH_ROOT` 可覆盖；解析失败时 hook/tools 优雅回落祖先树解析）。sync stamp 纳入代换结果，根变化触发重同步。
- 仓库根 `skills/` 的 customSkillDir 移除：dsh ≥ 0.1.2 默认发现项目 `.agents/skills`、用户 `~/.agents/skills`、`<dshHome>/skills`，workbench standalone skills 已由用户根覆盖；customSkillDirs 只保留 impl-package 插件 skills。
- Grok-ACP worker 全线移除（provider 行、tool 行、persona/文档引用）：worker 派发只保留 `subagent_codex`；`cordis.patch.yml` 不再含机器专属路径。
- 对齐 builtin standard 补充：spawn 子代理行 `modelSelectionSettings: true`、`command-goal`、`present`（文件交付）——三者包在 0.1.5-rc.1 均已发布并见于其 standard 预设。

### 0.1.6-alpha.1 迁移项（切到 alpha 线时）

只有 workflow 执行器行名不兼容，且**必须先改**（`dsh-workflow-ptc` 自 0.1.6-alpha.1 才发布，提前写会让整个 preset 变 broken）：

| 行 | 0.1.5（当前） | 0.1.6-alpha.1 |
| --- | --- | --- |
| workflow 执行器 | `@deepseek-ai/dsh-workflow-worker-thread` | `@deepseek-ai/dsh-workflow-ptc` |
| `tool-ralph` | 默认启用 | 上游默认 `disabled: true`（建议跟随） |

0.1.6 的其余变更（`agent/created`、PTC 运行时、E2B 移除、Messages 协议默认）对本适配层无影响；若手配过旧官方 API 根地址，需改为 `https://api.deepseek.com/anthropic`。

## 测试

```powershell
node plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs
```

覆盖：package/scripts 解析、处境消息合成（对 `tests/fixtures/situations/` 真实 fixture）、ticket argv 构建、
$dispatcher trail schema（dispatch/worker-return 构造器 + 与 Python engine 的 mode enum parity）、
evidence batch/retire-claim 工具注册、命令表与现行路由表一致性、persona prefix/suffix 与 workflow 执行器行、
`{{WORKBENCH_ROOT}}` 代换、host half 的 preset 同步（含 stamp 幂等）。
