---
name: wt-dev
description: Worktree-phase skill for WT-PM workflow. Auto-detects current task from branch name, loads plan context, runs environment init, implements features, pauses for manual testing, runs regression gate, merges back to trunk, then marks DONE — all from within the task worktree terminal.
user-invocable: true
---

# wt-dev: Task Implementation & Integration (Worktree Phase)

Worktree-side skill for the WT-PM lifecycle. Run this from the **task worktree terminal** (branch `feat/<task_id>-<slug>`).

Covers:
1. Auto-detect current task from branch name
2. Load plan context (three-files)
3. Environment initialization (first run only)
4. Sync trunk + regression gate
5. Implementation（含 BLOCKED 上报协议）
6. **[PAUSE]** Wait for manual testing confirmation
7. Final regression gate
8. Update plan files (pre-merge evidence)
9. Merge back to trunk (via `git -C`, no terminal switch needed)
10. Mark DONE + worktree cleanup

For the planning/setup phase (trunk terminal), use `wt-plan`.

## Trigger Phrases

- `开工`
- `继续开发`
- `开始`
- `start task`
- `resume wt`
- `wt-dev`
- `继续TC-<id>`

---

## Phase 0: Auto-Detect Current Task

Goal: 从当前环境自动识别 `task_id`、`slug`、`plan_id`，无需用户输入。

```bash
git branch --show-current
```

期望格式：`feat/<task_id>-<slug>`（如 `feat/TC-107-receiver-mapping-ui`）

解析：
- `task_id` = 如 `TC-107`
- `slug` = 如 `receiver-mapping-ui`

查找 `plan_id`：

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list
```

找到 `task_id` 对应行，提取 `plan_id`。

**Stop conditions:**
- 分支名不匹配 `feat/<task_id>-<slug>` 格式：停止，报告当前分支。
- `task_id` 不在 `plans/todo_current.md` 中：停止，报告。
- `task_id` 状态为 `DONE`：停止。任务已完成，建议切回 trunk。
- `task_id` 状态为 `UNPLANNED`：停止。请先在 trunk 终端运行 `wt-plan`。

---

## Phase 1: Load Plan Context

Goal: 在采取任何行动之前，恢复完整的任务上下文。

读取全部三个 plan 文件：

```
plans/workplans/task_plan.<plan_id>.md
plans/workplans/findings.<plan_id>.md
plans/workplans/progress.<plan_id>.md
```

无论是首次运行还是续做，必须始终读取这三个文件。这是"加载存档"步骤。

读取后输出简短上下文摘要：
- 任务目标（来自 task_plan）
- 当前阶段 / 最后完成的步骤（来自 progress）
- 已知阻塞项或风险（来自 findings）

同时检查是否存在 `plans/workplans/dev-status.<plan_id>.md`：
- 如果存在且 `status` 不是 `DONE`：**优先浮出该文件中的问题**，询问用户如何处理后再继续。
- 如果不存在或 `status` 为 `DONE`：正常继续。

---

## Phase 2: Environment Initialization（first run only）

Goal: 在任务 worktree 中准备可运行的后端和前端环境。

**跳过条件：** `progress.<plan_id>.md` 中记录了环境初始化已完成。

Commands:

```bash
uv sync --extra web
corepack enable
corepack prepare pnpm@latest --activate
pnpm --dir frontend install
```

最小验证：

```bash
uv run python -c "import bills_analysis"
pnpm --dir frontend test
```

**Stop condition:** 任何安装或验证命令失败时，停止并报告失败命令及其完整错误输出。不继续进入 Phase 3。

成功后更新 `progress.<plan_id>.md`。

---

## Phase 3: Sync Trunk + Initial Regression Gate

Goal: 集成最新 trunk 变更，验证无回归后再开始实现。

```bash
git fetch origin <trunk>
git merge origin/<trunk>
```

远端不可用时的 fallback：

```bash
git merge <trunk>
```

出现 merge conflict：执行 **Conflict Triage Protocol**（见文末）。不自动解决。

Regression gate（按顺序执行）：

```bash
uv run pytest tests/test_api_schema_v1.py -q
pnpm --dir frontend test
```

可选：

```bash
uv run pytest tests/test_api_e2e_smoke.py -q
```

**Stop condition:** 任何必须项失败时，停止。Regression 全绿前不进入 Phase 4。

更新 `progress.<plan_id>.md`，记录 sync + regression 结果。

---

## Phase 4: Implementation

Goal: 按顺序执行 task plan 中的各实现阶段。

Process:
1. 读取 `task_plan.<plan_id>.md` 获取实现阶段列表。
2. 对每个阶段：实现后立即更新 `progress.<plan_id>.md` 标记完成。
3. 发现新情况或决策时，同步记录到 `findings.<plan_id>.md`。
4. 遵守 API contract 规则：不破坏 `v1` 冻结字段。Schema 变更必须在 consumer 变更之前 commit。

实现阶段全部完成后，运行与改动相关的单元测试：

```bash
uv run pytest tests/test_api_schema_v1.py -q
pnpm --dir frontend test
```

测试失败时，修复后再进入 Phase 5。

### Implementation Escalation Protocol

在实现过程中遇到以下情况时，**不要自行决定**，写入 `plans/workplans/dev-status.<plan_id>.md` 后停止，等待用户指示：

| 情况 | status 值 |
|------|-----------|
| 测试失败超过 3 次且根因不明 | `BLOCKED` |
| 需求理解有歧义，无法推进 | `NEEDS_CLARIFICATION` |
| 发现改动范围超出 task_plan 定义的边界 | `SCOPE_EXCEEDED` |
| 存在方案 A vs 方案 B 的架构决策，无法自主判断 | `DECISION_NEEDED` |

**文件格式：**

```markdown
# dev-status.<plan_id>.md

status: BLOCKED | NEEDS_CLARIFICATION | SCOPE_EXCEEDED | DECISION_NEEDED
blocker: <具体描述问题>
options: |
  A: <方案 A 描述>（如有多方案时填写）
  B: <方案 B 描述>
last_completed_phase: <停在哪个子步骤，如 "Phase 4 - Step 2/5">
timestamp: <ISO 8601>
```

**可以自主解决（无需上报）：**
- 语法错误、类型错误
- 单元测试失败且根因明确
- 依赖缺失（可直接安装）

用户处理完问题后，更新 `dev-status.<plan_id>.md` 的 status 为 `DONE`，然后继续 Phase 4 剩余步骤。

---

## Phase 5: [PAUSE] Manual Testing Confirmation

Goal: 在合并前给人工提供明确的停止点，验证功能端到端可用。

重要口径：
- 用户在这里回复 `pass`，代表“实现完成并通过人工验证”，不代表 task 已经完成。
- 在完成 Phase 6 到 Phase 10 前，禁止使用“任务已完成”“可以开始下一个 task”这类闭环表述。

根据 `task_plan.<plan_id>.md` 中的验收标准，输出**测试清单**：

```
⏸  Implementation complete. Please test the following before I continue:

  Core flows:
  [ ] <验收标准 1>
  [ ] <验收标准 2>

  Adjacent regression check:
  [ ] <可能受影响的相关功能>

  To continue: reply with your test result (pass / fail / partial).
  To abort:    reply with "abort" and describe what failed.
```

**等待用户回复。** 未收到回复前不继续。

回复解读：
- 肯定（如"通过"、"OK"、"passed"、"没问题"、"looks good"）：进入 Phase 6。
- 否定或部分（如"有bug"、"failed"、"有问题"、"不对"）：停止，询问用户描述问题，协助修复，重新执行 Phase 4，再回到 Phase 5。
- "abort"：完全停止。更新 `progress.<plan_id>.md` 记录 abort 原因。

---

## Phase 6: Final Regression Gate

Goal: 实现完成 + 人工测试签字后，确认完整测试套件全绿。

```bash
uv run pytest tests/test_api_schema_v1.py -q
pnpm --dir frontend test
```

**Stop condition:** 任何测试失败，不进入 Phase 7。修复 → 重跑 → 全绿后继续。

---

## Phase 7: Update Plan Files（Pre-Merge）

Goal: 合并前持久化完成证据，但不提前标记 DONE。

必须更新：

1. `plans/workplans/progress.<plan_id>.md`：添加最终执行摘要、测试结果、完成时间戳。
2. `plans/workplans/findings.<plan_id>.md`：记录最终决策、发现的风险、值得注意的实现细节。
3. 确认 `plans/todo_current.md` 状态仍为 `PLANNED`（merge 成功前不改为 DONE）。

**Stop condition:** 任何 plan 文件未更新，Phase 8 被禁止执行。

此阶段完成后，最多只能表述为：
- “实现已完成，已通过人工验证，准备 merge”

禁止表述为：
- “task 已完成”
- “已经 done”
- “可以按 WT-PM 结束”

---

## Phase 8: Merge Back to Trunk（no terminal switch required）

Goal: 在 worktree 终端内直接将已验证的任务分支 merge 进 trunk。

### 8a. 找到 trunk worktree 路径

```bash
git worktree list
```

识别 trunk worktree 路径（branch 为 `dev` 或配置的 trunk 的条目）。记为 `<trunk_path>`。

### 8b. Commit 任何未提交变更

```bash
git status --short
```

如有未提交变更，stage 并 commit：

```bash
git add -p   # 或 stage 具体文件
git commit -m "<task_id>: <最终变更说明>"
```

### 8c. Merge 进 trunk

```bash
git -C <trunk_path> merge --no-ff feat/<task_id>-<slug>
```

出现 merge conflict：执行 **Conflict Triage Protocol**（见文末）。

**Stop condition:** Phase 6 regression gate 未全绿时，此步骤被禁止执行。

### 8d. 验证 trunk 上的 merge

```bash
git -C <trunk_path> log --oneline -5
git -C <trunk_path> status --short
```

确认 merge commit 出现，trunk 状态为干净。

---

## Phase 9: Mark DONE（Post-Merge Gate）

Goal: trunk merge 成功后才更新任务状态为 `DONE`。

Phase 8 merge 验证通过后执行：

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . set-status --task-id <task_id> --status DONE --plan-id <plan_id>
```

验证 `plans/todo_current.md` 中 `task_id` 显示 `DONE`。

**Stop condition:** Phase 8 merge 失败或未经验证时，此步骤被禁止执行。

---

## Phase 10: Worktree Cleanup

Goal: 干净 merge 后移除任务 worktree。

检查 worktree 状态：

```bash
git status --short
```

如状态干净：

```bash
git worktree remove ../wt-<task_id>
git -C <trunk_path> worktree prune
```

Windows fallback（symlinks 或 `node_modules` 阻止移除时）：

```bash
git worktree remove --force ../wt-<task_id>
cmd /c rmdir /S /Q ../wt-<task_id>
git -C <trunk_path> worktree prune
```

**Cleanup 是可选的：** 如果 worktree 不干净或用户希望保留，跳过 cleanup 并报告原因。

---

## Completion

Phase 10 后输出：

```
✅ wt-dev complete for <task_id>

  Task:     <task description>
  Status:   DONE
  Merged:   feat/<task_id>-<slug> → <trunk>
  Cleanup:  worktree removed / kept (reason)

Recommended next step: run a manual smoke test on trunk to confirm end-to-end behavior.
  uv run invoice-web-api   (or docker compose up for M2+)
```

## Completion Semantics

请始终区分以下两个状态：

- `implementation complete`
  - 含义：代码已经实现，自动化验证和人工测试已经通过，但尚未完成 merge / `DONE` 状态更新。
  - 允许出现的阶段：Phase 5 到 Phase 7 之间。

- `task complete`
  - 含义：Phase 8、9 已成功完成，也就是已经 merge 回 trunk，且 `plans/todo_current.md` 已标记为 `DONE`。
  - 唯一正式完成信号：输出 `✅ wt-dev complete for <task_id>`。

在 `✅ wt-dev complete for <task_id>` 之前，不要将任务描述为“完成”“done”“结束”，最多只能说“实现完成，等待 WT-PM 收尾”。

---

## Conflict Triage Protocol

`git merge` 报告冲突时，不自动解决。

必须执行的诊断步骤：

```bash
git status --short
git diff --name-only --diff-filter=U
git diff --merge
```

逐文件决策规则：

| 文件类型 | 决策 | 理由 |
|----------|------|------|
| 任务专属文件（当前 plan 的 progress/findings、主要在本分支的功能代码） | 采用 feature branch | 这是本任务的工作成果 |
| 共享基础/集成文件（CI 配置、lock 文件、非本任务的共享配置） | 采用 trunk | Trunk 版本更成熟 |
| Contract/Schema/Public API 文件 | 需要人工审查 | Breaking change 需要明确理由 |

禁止：
- 不得在逐文件分析前使用 `git merge -X ours` 或 `git merge -X theirs`。
- 不得对整个分支应用统一偏好。

必须输出：
- 列出每个冲突文件。
- 说明逐文件决策：`feature` / `trunk` / `manual`。
- 每个文件给出一行理由后再解决。

---

## Safety Rules

- 禁止 `git reset --hard` 或 `git checkout -- <path>`。
- 任何 commit 或 merge 前必须检查 `git status`。
- Phase 6 regression gate 未全绿前，不执行 Phase 8（merge）。
- Phase 8 merge 未验证前，不执行 Phase 9（标记 DONE）。
- 标记 DONE 前必须更新 `progress` 和 `findings` 文件。
- 不可跳过 Phase 5（人工测试暂停）。自动化测试不替代人工验证。
- Phase 10 时如果 worktree 有未提交内容，跳过 cleanup 而非强制删除。
