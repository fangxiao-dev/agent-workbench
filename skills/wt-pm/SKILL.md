---
name: wt-pm
description: WT-PM 全流程编排入口。当用户说"开始一个新任务"、"我要做一个新功能"、"走完整流程"、"不知道从哪开始"、或使用 wt-pm 时触发。负责引导用户在正确的终端环境中依次调用 wt-plan 和 wt-dev，自身不执行任何 git 或文件操作。
user-invocable: true
---

# wt-pm: 全流程编排入口

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

**wt-pm 不做：**
- 不执行任何 git 命令
- 不读写任何文件
- 不重复 wt-plan / wt-dev 的内容

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
| `dev` / `main` | 在 trunk，准备开始新任务 | → 进入 Stage 1 |
| `feat/<task_id>-<slug>` | 在 worktree，任务已创建 | → 进入 Stage 2 |
| 其他 | 不明确 | → 询问用户意图 |

如果用户已经明确说明情况（如"我已经写好 plan 了，现在要开发"），跳过检查直接导航到对应阶段。

---

## Stage 1: 规划阶段（Trunk 终端）

**前提：** 用户在 trunk 终端（`dev` / `main` 分支）。

输出：

```
📋 Stage 1 — 规划阶段（当前终端）

在这个终端中，调用 wt-plan 完成以下步骤：
  1. 任务定义对话（目标、范围、验收标准）
  2. 生成 plan 三文件
  3. Commit plan 到 trunk
  4. 创建任务 worktree + 同步配置

触发方式：直接说 "wt-plan" 或 "确认task" 即可开始。
```

等待用户确认 Stage 1 完成。确认信号：用户说"plan 好了"、"wt 创建好了"、"准备开发"等。

---

## Stage 2: 开发阶段（Worktree 终端）

**前提：** wt-plan 已完成，worktree 已创建。

输出：

```
🛠  Stage 2 — 开发阶段（需要切换终端）

请打开一个新终端，进入任务 worktree 目录：
  cd ../wt-<task_id>

然后说 "开工" 触发 wt-dev，wt-dev 将完成：
  1. 自动检测当前任务
  2. 加载 plan 上下文（三文件）
  3. 环境初始化（首次）
  4. Sync trunk + regression gate
  5. 实现功能
  6. [PAUSE] 等待你的人工测试确认
  7. Final regression gate
  8. 更新 plan 证据文件
  9. Merge 回 trunk
  10. 标记 DONE + 清理 worktree

注意：
- “实现完成” 只表示代码和验证在 task worktree 中已经完成。
- “任务完成” 只在 merge 回 trunk 且 `plans/todo_current.md` 已标记为 `DONE` 后成立。
- 在 Phase 8 到 Phase 10 结束前，不要把 task 对用户表述为“已完成”。
```

---

## Stage 3: 完成确认

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

根据回答导航到对应阶段。

**需要了解完整模型设计：**

Read `references/wt-pm-workflow.md` for the full WT-PM model rationale, concurrency model, and adaptation guide.
