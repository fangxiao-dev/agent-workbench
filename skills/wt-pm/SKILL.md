---
name: wt-pm
description: WT-PM 全流程编排入口。Use when the user wants the full tracked task workflow but the repo may use different trunk branches or task branch prefixes. It routes the user to wt-plan and wt-dev without doing git or file mutations itself.
user-invocable: true
---

# wt-pm: 全流程编排入口

**REQUIRED SUB-SKILL CHAIN:**
- Stage 1 规划阶段必须进入 `wt-plan`
- `wt-plan` 在生成 task plan 时必须调用 `planning-with-files`

WT-PM 工作流的导航层。只做引导，不做执行。

## Trigger Phrases

- `wt-pm`
- `开始新任务`
- `我要做一个新功能`
- `走完整流程`
- `从头开始`
- `不知道从哪开始`

---

## 职责边界

**wt-pm 做：**
- 识别用户当前处于哪个阶段
- 告知应该在哪个终端执行什么 skill
- 在阶段转换时给出明确的下一步指令
- 明确提示当前阶段应遵循的规则来源（`rules/*`）
- 明确区分“方案级 plan”和“WT-PM 任务级 plan”的用途
- 明确提示 `planning-with-files` 是 WT-PM 规划阶段的必经执行层

**wt-pm 不做：**
- 不执行任何 git 命令
- 不读写任何文件
- 不重复 wt-plan / wt-dev 的内容

## Plan 分层规则

WT-PM 内默认存在两层计划：

1. 方案级 plan
   - 通常位于仓库自己的 `docs/plans/` 或同类目录
   - 用于冻结产品、设计、架构、数据模型等上层方向
   - 可以覆盖一个或多个具体任务
2. 任务级 plan
   - 位于仓库自己的 `plans/workplans/<task_id>/`
   - 目录内固定为 `task_plan.md`、`findings.md`、`progress.md`
   - 与 `plans/todo_current.md` 中的 task 一一绑定
   - 用于驱动 trunk 规划、worktree 实施、验证和 closure

规则：

- 方案级 plan 可以作为 WT-PM 任务规划的输入材料
- 方案级 plan 不能替代 `plans/todo_current.md` 和 `plans/workplans/` 中的任务级 plan
- 如果用户只想快速执行简单工作，且不想进入 WT-PM，可以直接按已批准的方案级 plan 开工
- 一旦用户选择进入 WT-PM，执行层必须以任务级 plan 为准
- 在 WT-PM 中，任务级 plan 的生成必须通过 `planning-with-files` 完成，而不是手工跳过该层
- 若两层 plan 同时存在，任务级 plan 必须服从已批准的方案级 plan，除非用户显式修改设计

## 规范来源（被引用）

- 工作流主参考：`references/wt-pm-workflow.md`
- 规则定义库：`rules/collaboration-boundaries.md`、`rules/planning-with-files.md`、`rules/dod-and-safety.md`

原则：从 `wt-pm` 进入流程；`rules` 提供定义并被引用，不单独作为主入口。

---

## Phase 0: 识别当前状态

首先确认用户的情况：

```bash
git branch --show-current
```

根据结果判断：

| 当前分支 | 情况 | 行动 |
|----------|------|------|
| 检测到的 trunk（如 `master` / `main` / `dev`） | 在 trunk，准备开始新任务 | → 进入 Stage 1 |
| 检测到的 task 分支（如 `codex/<task_id>-<slug>` / `feat/<task_id>-<slug>`） | 在 worktree，任务已创建 | → 进入 Stage 2 |
| 其他 | 不明确 | → 询问用户意图 |

如果用户已经明确说明情况（如"我已经写好 plan 了，现在要开发"），跳过检查直接导航到对应阶段。

---

## Stage 1: 规划阶段（Trunk 终端）

**前提：** 用户在检测到的 trunk 终端。

输出：

```
📋 Stage 1 — 规划阶段（当前终端）

在这个终端中，调用 wt-plan 完成以下步骤：
  1. 任务定义对话（目标、范围、验收标准）
  2. 结合已有方案级 plan，通过 planning-with-files 生成当前 task 的 workplan 三文件
  3. Commit plan 到 trunk
  4. 生成 branch / worktree handoff 指引

触发方式：直接说 "wt-plan" 或 "确认task" 即可开始。

如果仓库中已经存在 `docs/plans/` 这类方案文档，先把它们视为上层约束；`wt-plan` 的职责是把这些约束翻译成当前 task 的执行计划，而不是跳过任务级 planning。
```

等待用户确认 Stage 1 完成。确认信号：用户说"plan 好了"、"wt 创建好了"、"准备开发"等。

---

## Stage 2: 进入 Task Worktree（切换环境）

**前提：** wt-plan 已完成。

输出：

```
🧭 Stage 2 — 切换到 task worktree（需要切换环境）

请不要在 trunk 目录里直接 checkout task 分支。
你需要先进入该 task 的 worktree。创建或进入 worktree 的方式有两种：

  A. Codex app handoff
     - 在 trunk 线程里使用 handoff
     - 输入 repo 检测到的 task branch 名，例如 `codex/<task_id>-<slug>` 或 `feat/<task_id>-<slug>`

  B. 手动 git worktree
     - 在 trunk 终端执行 `git worktree add ...`
     - 分支名应复用 repo 已有 task branch 前缀，而不是默认假设 `feat/`

如果该 task 的 worktree 已存在，直接打开那个目录，不要重复 handoff，也不要在 trunk 目录里切 branch。
进入 task worktree 后，再说 "开工" 触发 wt-dev。
```

---

## Stage 3: 开发阶段（Task Worktree）

**前提：** 已经位于 task worktree 目录。

输出：

```
🛠  Stage 3 — 开发阶段（task worktree）

然后说 "开工" 触发 wt-dev，wt-dev 将完成：
  1. 自动检测当前任务
  2. 加载 plan 上下文（三文件）
  3. 在当前 worktree 内完成环境初始化（首次）
  4. Sync trunk + regression gate
  5. 实现功能
  6. [PAUSE] 等待你的人工测试确认
  7. 重新同步 trunk 后再做 final regression gate
  8. 更新 plan 证据文件
  9. Merge 回 trunk
  10. 标记 DONE + 清理 worktree

注意：
- “实现完成” 只表示代码和验证在 task worktree 中已经完成。
- 人工测试通过后，仍然必须先同步最新 trunk 并重跑最终回归，之后才允许 merge。
- “任务完成” 只在 merge 回 trunk 且 `plans/todo_current.md` 已标记为 `DONE` 后成立。
- 在 Phase 8 到 Phase 10 结束前，不要把 task 对用户表述为“已完成”。
```

---

## Stage 4: 完成确认

wt-dev 输出 `✅ wt-dev complete` 后，输出：

```
✅ 全流程完成

任务已合并到 trunk，状态标记为 DONE。

建议：在 trunk 终端做一次手动 smoke test 确认端到端行为正常。
如需开始下一个任务，在 trunk 终端说 "wt-pm" 或 "开始新任务"。
```

只有在看到 `✅ wt-dev complete` 之后，才可以把该 task 视为 WT-PM 意义上的真正完成。

---

## 异常处理

**用户不确定当前处于哪个阶段：**

询问：
1. `git branch --show-current` 的输出是什么？
2. `plans/todo_current.md` 里这个 task 的状态是什么（UNPLANNED / PLANNED / DONE）？
3. 当前目录是否已经是该 task 的独立 worktree？
4. `plans/workplans/<task_id>/` 和三文件是否已经存在？

根据回答导航到对应阶段。

**需要了解完整模型设计：**

 Read `references/wt-pm-workflow.md` for the full WT-PM model rationale, concurrency model, and adaptation guide.

**需要验证兼容性压力场景：**

Read `references/wt-compat-pressure-tests.md`.
