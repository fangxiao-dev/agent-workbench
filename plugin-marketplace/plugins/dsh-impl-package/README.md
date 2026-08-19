# dsh-impl-package — Impl-Package 的 DSH 原生适配

薄而原生的 DSH adapter：**保留现有 Python core 不动**，把主 session 的机械负担下沉到 DSH 原生机制里。

- Python core（`plugin-marketplace/plugins/impl-package/scripts/`）、`state.json`、Git 锚点、Ticket/evidence/Gate 语义继续是**唯一权威**；
- 本插件只做三件事：**处境注入（agent/pre-step hook）**、**typed CLI 工具**、**原生 subagent 派发（Codex / Grok-ACP）**；
- DSH session 只记执行轨迹，不成为 package 事实源（不双写）。

## 组件

```
plugin-marketplace/plugins/dsh-impl-package/
├─ package.json               # dsh.bundle.patch 声明，profile bundle
├─ cordis.patch.yml           # 把 host half 插入 profile roster
├─ lib/index.mjs              # host half：启动时把 presets/ 同步到 ~/.dsh/.agent-presets/
├─ presets/impl-package/      # 「Impl-Package 主控」agent preset（自包含）
│  ├─ preset.yml
│  ├─ agent.cordis.yml        # standard 基座 + 下述两行 + subagent 工具行
│  ├─ situation-hook.mjs      # agent/pre-step：validate → situation render → 注入
│  └─ impl-tools.mjs          # 9 个 typed 工具，直接调用 impl_package_state.py CLI
└─ test/smoke-test.mjs        # 纯逻辑冒烟测试（node 直接跑，无需 DSH）
```

## 安装

```powershell
# 1. 注册 profile bundle（会在 package.json 的 dsh.profile.bundles 追加 dsh-impl-package，
#    并把 provider 行挂到 host plane——见 cordis.patch.yml）
dsh plugin --profile desktop add "link:D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\dsh-impl-package"

# 2. 安装官方 subagent provider 包（provider 行由 dsh-impl-package 的 patch 挂载，
#    这里只需要把 npm 包装进 profile 依赖）
cd "$env:USERPROFILE\.dsh\profiles\desktop"
pnpm add "@deepseek-ai/dsh-subagent-codex" "@deepseek-ai/dsh-subagent-acp"
pnpm add "@openai/codex@0.147.0"   # codex provider 的固定平台 payload（一次性大下载）

# 3. 重启 DSH Desktop（bundle 生效；host half 启动时同步 preset；安装事务收口）
```

> 说明：`subagent_codex` / `subagent_grok` 工具行在 preset 中保持启用；`dsh-tool-subagent`
> 会在 provider 挂载后**自动注册**（`subagent/provider-added`），缺 provider 也不会破坏 preset。
> 验证组合树：`dsh --profile desktop --dump-config` 应包含 `subagent-codex` 与 `subagent-grok` 行。

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
| `impl_evidence_add` / `impl_evidence_invalidate` | `evidence add/invalidate`（stdin JSON） |
| `impl_recovery_checkpoint` / `impl_recovery_judgment` | `recovery checkpoint/judgment` |
| `impl_gate_commit` | `gate <verdict> --comparison-commit --reason …` |
| `impl_trail_append` | `trail append`（escape/fact/dispatch/worker-return，CLI 校验 schema 与 digest） |

5. Worker 派发：`subagent_codex`（官方 Codex provider，ephemeral thread，复用本机登录）/ `subagent_grok`（ACP 驱动
   `grok agent --always-approve stdio`）。两者均为 one-shot：收最终答案文本，不回传子进程内部轨迹；envelope 与
   fallback 规则沿用 `subagent-driven-development` 的 worker-resolver 合同（逻辑角色 → provider，不再硬编码宿主名）。

## 处境注入的设计决策

- **digest 未变不注入**：DSH 的 pre-step 每步触发，重复注入会污染上下文；只在 digest 变化（或 session 冷启动/压缩后）注入完整处境。内存按 session 缓存，重启后首步自动重新注入。
- **处境驱动协议注入**：`presets/impl-package/protocols.json` 为全部 59 个 situation slug 提供 2-4 行协议片段（判断/处理规则，来源 dev-with-track / do-review / worker-resolver 合同），hook 在选中 slug 时把对应片段附加到处境消息。模型每步只见「当前处境 + 当前动作的规则」，不再读整套 SKILL/references。`default` 兜底未覆盖 slug。
- **注入是导航，不是 gate**：模型仍可偏离，按 `dev-with-track` 合同写 `kind=escape` 轨迹行（`impl_trail_append`）。
- **compaction pressure 未接**：renderer 缺省时 `attempt.compaction_pressure_high` 保持不可判定；后续可读 DSH 原生压缩观测接入。
- **脚本定位**：`situation.py` / `impl_package_state.py` 通过最近祖先树的 `plugin-marketplace/plugins/impl-package/scripts` 解析，或 preset 配置 `implScriptsRoot` 显式指定；package 目录解析优先级：`packagePath` 配置 → cwd 向上最近含 state.json → git root 下 `docs/implementations/<topic>/`。

## 原生命令（0 token 路由）

`/impl-req-align`、`/impl-grill-me-smartly`、`/impl-grilling`、`/impl-impl-planning`、`/impl-plan-review`、
`/impl-to-tickets`、`/impl-create-task-dag`、`/impl-execution-preflight`、`/impl-standing-bookkeeper`、
`/impl-subagent-driven-development`、`/impl-dev-with-track`、`/impl-do-review`、`/impl-review-code`、
`/impl-review-code-by-standards`、`/impl-review-code-by-spec`、`/impl-safety-review`、
`/impl-verification-before-completion`、`/impl-backfill-stable-docs`。

用户输入斜杠命令 → 命令向 agent steer 一条路由指令（`source.kind='impl-package-command'`），命令本身
不进模型历史（0 token）。`recordInput: false`——steered 消息就是权威领域记录，避免 command/run 重复记录。
原 `/impl-package:*` 路由表（impl-package/SKILL.md）从主 session 上下文里消失。

## 边界与暂缓（对应 GPT 收敛方案）

- **不做双重 runtime**：不重写 Python core；不用 DSH Goal 替代 Ticket；不用 session event 替代 trail。
- **外部 subagent 只读边界**：Codex/Grok 是一发式 out-of-process，宿主无法 toolFilter/persona；reviewer 若用它们需独立 worktree/只读 sandbox。进程内 `spawn`/`fork` 子代理才支持 `toolFilter`/`persona`/`outputSchema`。
- **暂缓**：只读 reviewer preset、do-review 固定 orchestrator、commands 注册（`/impl-package:*` 原生命令）、progress/gate 的 Web UI 投影、pre-step 读 DSH 原生压缩压力。
- DSH 仍为 Developer Preview：薄适配，破坏性变更影响面小；本插件全部文件可随时 `dsh plugin --profile desktop remove dsh-impl-package` 撤销。

## 测试

```powershell
node plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs
```

覆盖：package/scripts 解析、处境消息合成（对 `tests/fixtures/situations/` 真实 fixture）、ticket argv 构建、
host half 的 preset 同步（含 stamp 幂等）。
