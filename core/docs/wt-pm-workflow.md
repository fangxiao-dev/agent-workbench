# WT-PM: Task-Centric Worktree Development Model

> 一种面向 AI Agent 多任务并行开发的轻量协作框架。
> 核心理念：**一个 task = 一个 worktree = 一个闭环**。

---

## 1. Model Overview

WT-PM（Worktree + Project Management）是一种基于 Git worktree 的任务隔离开发模型。它将项目管理职责（任务创建与优先级）和执行职责（规划与实现）分离到不同的分支环境中，通过结构化的 planning 文件和 contract guardrail 实现多任务并行推进。

```
                    WT-PM (main branch)
                    ┌──────────────────┐
                    │   Create Tasks   │
                    │  (todo_current)  │
                    └────────┬─────────┘
                             │ assign task_id
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  WT-Task-A  │ │  WT-Task-B  │ │  WT-Task-C  │
        │ ┌─────┐     │ │ ┌─────┐     │ │ ┌─────┐     │
        │ │Plan │→Impl│ │ │Plan │→Impl│ │ │Plan │→Impl│
        │ └─────┘     │ │ └─────┘     │ │ └─────┘     │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               │  sync main    │  sync main    │
               │  regression   │  regression   │
               ▼               ▼               ▼
        ┌──────────────────────────────────────────────┐
        │              Merge to main                   │
        └──────────────────────────────────────────────┘
```

### 适用场景

- AI Agent（如 Claude Code）驱动的多任务并行开发
- 前后端一体仓库（monorepo）中需要减少跨角色协调开销
- 需要 contract 冻结保护的 API-driven 项目
- 需要完整审计轨迹的持续迭代项目

---

## 2. Roles

### PM（Project Manager）

| 属性 | 说明 |
|------|------|
| 工作分支 | `main`（仅限） |
| 职责 | 创建任务、分配 `task_id`、确认优先级 |
| 禁止 | 直接编码、修改 worktree 内文件 |
| 产出物 | `plans/todo_current.md` 中的任务条目 |

### Executor（执行 Agent）

| 属性 | 说明 |
|------|------|
| 工作分支 | `feat/<task_id>-<slug>`（独立 worktree） |
| 职责 | Planning → Implementation → Testing → Integration |
| 范围 | 可修改任意文件（前端、后端、文档），受 scope guidance 约束 |
| 产出物 | 代码、plan 三文件（task_plan / findings / progress） |

---

## 3. Core Concepts

### Task ID

任务的唯一标识符，贯穿整个生命周期。

- 格式约定：`TC-NNN`（或项目自定义前缀）
- 来源：`plans/todo_current.md`
- 用途：分支名、commit 前缀、plan 绑定

### Worktree

每个 task 对应一个独立的 Git worktree，提供文件系统级的隔离。

```bash
git worktree add -b feat/TC-007-batch-delete ../wt-TC-007 main
```

执行约束（Windows/Agent 环境）：
- worktree 默认放在与主工作目录同级的可见目录（如 `../wt-TC-007`）
- 如果仓库元数据或目标路径不在当前沙箱可写范围，需先申请提权再执行 `git worktree add/remove`。
- `scripts/sync_worktree_config.sh` 若在 Windows 无法用 `bash` 执行，需使用等价 PowerShell 同步流程。
- `sync_worktree_config` 的同步方向是“当前目录 -> 其他 worktree”；因此要把 `dev/main` 的 `.env` 等配置同步到任务 worktree 时，**必须在 trunk 目录执行**脚本。
- 若任务是“续做已有 worktree”（非新建），也必须先在 trunk 执行 `sync_worktree_config`（dry-run + apply），再进入该 task worktree 开发。

### Plan

结构化的任务规划，由三个持久化文件组成：

| 文件 | 用途 |
|------|------|
| `task_plan.<plan_id>.md` | 任务规划：目标、步骤 |
| `findings.<plan_id>.md` | 调研发现：技术决策、风险记录、现有代码分析 |
| `progress.<plan_id>.md` | 执行进度：已完成/进行中/阻塞项/下一步 |

`plan_id` 格式：`YYYYMMDD-HHmm`（同分钟重复追加 `-02`、`-03`）。

Plan 三文件同时承担 session 续接和审计功能——恢复执行时读取这三个文件即可恢复完整上下文。

### Contract

API schema 作为前后端（或模块间）的集成边界。Contract 一旦冻结，在当前里程碑内禁止 breaking change。

---

## 4. Two-Environment View

以**运行环境**为维度理解整个生命周期，可以划分为两个阶段。每个环境对应一个专属 SKILL：

```
┌─────────────────────────────────────────────────────────────────┐
│ Environment 1: Trunk (dev/main) — 规划          [SKILL: wt-plan]│
│                                                                  │
│  task 定义对话 → 更新 todo_current → quick-plan 三文件          │
│  → commit 规划产出物到 trunk → git worktree add → sync config   │
└──────────────────────────────┬──────────────────────────────────┘
                               │ git worktree add
┌──────────────────────────────▼──────────────────────────────────┐
│ Environment 2: Task Worktree — 开发              [SKILL: wt-dev] │
│                                                                  │
│  恢复 plan 上下文 → 初始化环境 → Sync trunk → 实现              │
│  → [PAUSE 人工测试] → Regression gate → 更新计划证据            │
│  → git -C <trunk_path> merge --no-ff → 标记 DONE（无需切终端）  │
│  → 清理 worktree                                                 │
└─────────────────────────────────────────────────────────────────┘
```

> **终端映射**：`wt-plan` 在主干终端执行；`wt-dev` 在 task worktree 终端执行，包含从 wt 直接操作主干 merge 的能力（`git -C <trunk_path>`），全程无需切换终端。

**关键设计意图：**
- **规划先于 worktree**：plan 文件必须 commit 到 trunk 后再创建 worktree，确保 worktree 天然携带最新规划快照，也使规划有独立的审计轨迹。
- **人工测试暂停节点**：`wt-dev` 在实现完成后输出测试清单并等待确认，自动化测试不替代人工验证。
- **自动化 vs 手动验证分离**：Regression gate（自动化）在 worktree 内完成；人工测试是合并前必经门，不可跳过。

---

## 5. Task Lifecycle

```
 ┌──────────┐    quick-plan    ┌──────────┐    set-status    ┌──────────┐
 │UNPLANNED │ ──────────────→ │ PLANNED  │ ──────────────→ │   DONE   │
 └──────────┘                  └──────────┘                  └──────────┘
       ↑                            │
       └── (plan 作废时可回退) ──────┘
```

**约束**：`PLANNED` 和 `DONE` 状态必须绑定 `plan_id`。一个 `task_id` 同时只允许一个活跃 plan。

### 十阶段 Worktree 生命周期

| 阶段 | 环境 | SKILL | 操作者 | 说明 |
|------|------|-------|--------|------|
| 1. Task Definition Dialogue | Trunk | `wt-plan` | PM/Executor | 多轮对话确认任务目标、范围、验收标准 |
| 2. Task Creation & Planning | Trunk | `wt-plan` | Executor | 更新 `plans/todo_current.md`；`quick-plan` 生成三文件；状态升为 `PLANNED` |
| 3. Commit Plan to Trunk | Trunk | `wt-plan` | Executor | `git commit` 规划产出物（`todo_current.md` + 三 plan 文件）到 trunk，形成独立审计节点 |
| 4. Worktree Setup | Trunk | `wt-plan` | Executor | 新建：`git worktree add -b feat/<id>-<slug>`；续做：跳过 add；两种情况都执行 `sync_worktree_config` |
| 5. Environment Init | Worktree | `wt-dev` | Executor | `uv sync` + `pnpm install`；最小可运行检查（首次运行时执行） |
| 6. Sync Trunk + Regression | Worktree | `wt-dev` | Executor | `git merge dev`，解决冲突；`pytest` + `pnpm test` |
| 7. Implementation | Worktree | `wt-dev` | Executor | 编码、单元测试、迭代；每子步骤后更新 `progress.md` |
| 8. [PAUSE] Manual Testing | Worktree | `wt-dev` | Human | SKILL 输出测试清单后等待；人工确认通过后继续 |
| 9. Final Regression + Plan Evidence | Worktree | `wt-dev` | Executor | 全量回归；更新 `progress/findings`，保持任务为 `PLANNED` |
| 10. Merge + Mark DONE + Cleanup | Worktree → Trunk | `wt-dev` | Executor | `git -C <trunk_path> merge --no-ff feat/<id>-<slug>` 成功后 `set-status DONE`；清理 worktree |

---

## 6. Branch & Commit Convention

### 分支命名

```
feat/<task_id>-<slug>
```

示例：`feat/TC-007-batch-delete`、`feat/TC-012-i18n-support`

### Commit 前缀

```
<task_id>: <描述>
```

示例：`TC-007: add batch delete endpoint and confirmation dialog`

### 跨范围 Commit

允许单个 commit 同时包含前端和后端改动，前提是：
- 围绕同一 `task_id`
- 改动是原子的（一个逻辑单元）

建议在可能时拆分为多个 commit 以保持历史清晰，但不强制。

---

## 7. Planning Subsystem

### Task Tracker

`plans/todo_current.md` 是任务状态的唯一来源（Single Source of Truth）。

| 字段 | 说明 |
|------|------|
| `task_id` | 唯一标识 |
| `task` | 任务描述 |
| `status` | `UNPLANNED` / `PLANNED` / `DONE` |
| `plan_id` | 绑定的 plan（`PLANNED`/`DONE` 必填） |
| `updated_at` | 最后更新时间 |
| `note` | 备注（含跨 task 依赖声明，如 `blocked by TC-008`） |

### CLI 管理命令

```bash
# 列出所有任务
plan_tracker.py list

# 创建 plan 并绑定 task
plan_tracker.py quick-plan --task-ids TC-007,TC-008

# 恢复执行
plan_tracker.py quick-resume [--plan-id <id> | --task-id <id>]

# 更新状态
plan_tracker.py set-status --task-id TC-007 --status DONE
```

### 三文件 Workplan 结构

每个 plan 在 `plans/workplans/` 下创建三个文件：

```
plans/workplans/
├── task_plan.20260215-1030.md     # 规划：目标、步骤
├── findings.20260215-1030.md      # 调研：技术决策、风险、现有代码
└── progress.20260215-1030.md      # 进度：完成/进行中/阻塞/下一步
```

**恢复执行前必须先读取对应 plan 的三文件**，确保上下文不丢失。

### 信息职责分工

| 信息类型 | 记录位置 |
|----------|----------|
| 做了什么 / 做到哪了 | `progress.<plan_id>.md` |
| 为什么这样做 / 技术决策 | `findings.<plan_id>.md` |
| 已知风险 | `findings.<plan_id>.md` "Risks" section |
| 跨 task 依赖 | `todo_current.md` 的 `note` 字段 |
| Breaking change 记录 | `findings.<plan_id>.md` |

---

## 8. Contract Guardrail

Contract guardrail 是 WT-PM 模型中防止跨模块 breaking change 的核心机制。

### 原则

1. **Contract 来源唯一**：指定目录（如 `models/`）为唯一 schema 来源
2. **变更顺序固定**：先更新 schema，再更新调用方（即使在同一 worktree）
3. **冻结期禁止**：禁止删除、重命名、改类型已发布字段
4. **升级路径明确**：breaking change 必须版本升级（如 `v1` → `v1.1`/`v2`），并在 `findings` 文件中标注风险和迁移建议

### 实现方式

- Contract 测试：自动化验证 schema 一致性
- Commit 顺序：schema commit 先于 consumer commit
- 冻结声明：在项目文档中明确标注当前冻结的 contract 版本

---

## 9. Regression Gate

每个 worktree 合并回 main 前必须通过回归门禁：

```bash
# Step 1: 同步 main 最新代码
git merge main

# Step 2: 运行回归测试（按项目定制）
<backend-contract-test>     # e.g. pytest tests/test_api_schema.py
<frontend-test>             # e.g. pnpm test / vitest run
<e2e-smoke-test>            # e.g. pytest tests/test_e2e_smoke.py（可选）

# Step 3: 确认通过后合并
git checkout main
git merge feat/<task_id>-<slug>
git worktree remove <path>
```

### Definition of Done

一个 task 标记为 `DONE` 前必须满足：

- Contract 一致性验证通过（schema + tests）
- 功能可运行（最小命令验证）
- 有日志和错误提示（可观测性）
- 不破坏既有流程
- 新代码有必要的注释
- 如涉及 API model 更新，contract 测试必须通过
- Plan 三文件已更新（progress 反映最终状态，findings 记录决策和风险）

---

## 10. Concurrency Model

WT-PM 天然支持多任务并行，隔离机制如下：

### 隔离层级

| 层级 | 机制 | 说明 |
|------|------|------|
| 文件系统 | Git worktree | 每个 task 独立目录，互不干扰 |
| 分支 | `feat/<task_id>-*` | 独立分支历史 |
| 状态 | Task tracker CLI | 原子操作，避免手动编辑冲突 |
| 集成 | Regression gate | 合并前强制测试，捕获冲突 |

### 并行约束

- 一个 `plan_id` 可绑定多个 task（关联任务打包处理）
- 一个 `task_id` 同时只允许一个活跃 `plan_id`
- 恢复执行前必须先读取 plan 三文件（防止上下文丢失）
- 多个 worktree 可同时工作，通过 main 分支做最终集成

### 冲突预防

```
  WT-Task-A ──────────── merge main ──── regression ──── merge to main
                              ↑                              │
  WT-Task-B ─────────────────────────── merge main ──────────┤── regression ── merge to main
                                             ↑               │
                                             └───────────────┘
                                          (B sees A's changes after A merges)
```

---

## 11. Adaptation Guide

将 WT-PM 移植到新项目时，需要定制以下内容：

### 必须定制

| 项目 | 说明 | 参考位置 |
|------|------|----------|
| File scope 定义 | 项目的目录范围划分（如 `frontend/`, `backend/`, `shared/`） | `collaboration-boundaries.md` |
| Regression 命令 | 项目的测试命令（pytest / vitest / cargo test 等） | `collaboration-boundaries.md` |
| Contract 来源 | API schema 所在目录 | `api-contract.md` |
| Task ID 前缀 | 如 `TC-`、`FEAT-`、`BUG-` | `plans/todo_current.md` |

### 可选定制

| 项目 | 说明 |
|------|------|
| Plan 文件模板 | 可在三文件基础上增加如 `risks.<plan_id>.md` |
| Commit 前缀格式 | 可改为 `[TC-007]` 或 `feat(TC-007):` 等 |

### 需要准备的基础设施

```
<project-root>/
├── plans/
│   ├── todo_current.md          # Task tracker（表格格式）
│   ├── todo_future.md           # 未来里程碑备忘（可选）
│   └── workplans/
│       └── README.md            # Workplan 操作说明
├── scripts/
│   └── plan_tracker.py          # Task 状态管理 CLI
├── .claude/
│   └── rules/
│       ├── collaboration-boundaries.md
│       ├── api-contract.md
│       ├── planning-with-files.md
│       └── dod-and-safety.md
└── CLAUDE.md / AGENTS.md        # 项目级 Agent 指令
```

### 移植步骤

1. 复制 `scripts/plan_tracker.py`
2. 创建 `plans/` 目录结构（`todo_current.md` + `workplans/`）
3. 编写项目专属的 `.claude/rules/*.md`（基于本文档各章节定制）
4. 在 `CLAUDE.md` / `AGENTS.md` 中引用规则文件
5. 定义项目的 regression gate 命令
6. 定义项目的 contract 来源和冻结策略

---

## Appendix: Design Rationale

### 为什么用 Worktree 而不是普通分支？

Git worktree 提供**文件系统级隔离**——每个 task 有独立的工作目录。对于 AI Agent 而言，这意味着：
- 不会意外修改其他 task 的文件
- `git status` / `git diff` 天然只反映当前 task 的变更
- 可以同时在多个 task 间切换而不需要 stash/checkout

### 为什么需要 Planning 三文件？

AI Agent 的上下文窗口有限，长时间任务容易出现上下文漂移。三文件结构提供了持久化的"外部记忆"：
- `task_plan` = 做什么（不变）
- `findings` = 发现了什么（累积）
- `progress` = 做到哪了（实时）

恢复执行时读取这三个文件，等同于"加载存档"。这一机制同时替代了传统的 session handoff 协议——无需额外的交接文件，plan 三文件本身即是完整的上下文载体。

### 为什么不区分前后端 Agent？

分离前后端 Agent 会导致 2×N 个 worktree（每个 task 需要前端和后端各一个），带来：
- 跨 Agent 对齐开销（交接记录往返）
- API 变更时需要双方同步
- 无法在一个原子操作中完成端到端功能

统一 Agent + scope guidance 是更轻量的方案：通过文档指导 Agent 关注特定范围，而非硬性禁止跨范围修改。
