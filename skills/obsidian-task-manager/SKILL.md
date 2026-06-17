---
name: obsidian-task-manager
description: Use this whenever the user asks to create, record, update, sync, validate, or inspect tasks in the local Obsidian TaskManager vault. This skill turns natural-language manual triggers like "新建任务", "更新任务", "标成完成", "进入验证", "阻塞", or "加到任务面板" into correct Obsidian task Markdown updates, with dry-run first and explicit apply only.
user-invocable: true
---

# Obsidian TaskManager

Use this skill to maintain the local Obsidian TaskManager vault as the task source of truth.

Default vault:

```text
D:\CodeSpace\TaskManager
```

Default behavior is dry-run. Only mutate the vault when the user explicitly asks to apply, write, create, or update the task file.

## Trigger Workflow

1. Identify whether the user wants to create a new task or update an existing task.
2. Convert the user's natural-language intent into the JSON shape from `templates/task-update.json`.
3. Apply the lifecycle and field rules from:
   - `rules/task-lifecycle.md`
   - `rules/field-semantics.md`
4. Run the script in dry-run mode first:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py upsert --vault D:\CodeSpace\TaskManager --input <task-update.json>
```

5. Review the dry-run output. If the user asked for actual writing, run again with `--apply`.
6. For broad checks, run:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py validate --vault D:\CodeSpace\TaskManager
```

## Manual Trigger Interpretation

Prefer natural-language interpretation. Do not ask for every field when the rules can infer it.

Common phrases:

- "新建任务", "记录任务", "加到任务面板" -> `operation=create`
- "更新任务", "同步任务", "修正任务" -> `operation=update`
- "开始做", "开工", "进 worktree" -> `status=实施中`; usually `workspace=worktree`
- "进入验证", "跑测试", "等人工验收" -> `status=验证中`
- "已合回主干", "完成了", "归档" -> `status=已完成`, `workspace=主工作区`, `priority=null`
- "卡住", "缺权限", "凭据不行", "外部系统阻塞" -> `status=阻塞`
- "暂时不做", "方向变了", "搁置" -> `status=搁置`, usually `priority=null`

When user wording and field values conflict, prefer lifecycle semantics. Example: a task cannot remain `worktree` after it is described as merged back to trunk and complete; use `主工作区`.

## Required Task Body Sections

Task notes use these exact third-level headings:

```markdown
### 来源链接/路径
### 当前进度
### 下一步建议
### 验证状态
### 残余风险
```

Plan-phase tasks only need the first three sections to be meaningful. Once implementation or verification starts, fill verification and residual-risk sections when information exists.

## Script Contract

The script accepts a normalized JSON object:

```json
{
  "operation": "create",
  "taskName": "Task Name",
  "status": "计划中",
  "priority": "当前",
  "taskType": "新增功能",
  "verificationPath": "不涉及",
  "workspace": "主工作区",
  "source": "",
  "progress": "",
  "nextStep": "",
  "verificationStatus": "",
  "residualRisk": ""
}
```

Omit unknown fields. Use `null` for intentionally clearing `priority`.

## Safety Rules

- Default to dry-run unless the user explicitly asked to write/apply.
- Do not change files outside the configured vault and this skill's own workspace.
- Do not rewrite unrelated task body sections during an update.
- Preserve existing task content whenever the update input does not mention that section.
- If multiple task files could match a task name, stop and ask the user which one.

## Evals

Use `evals/evals.json` and `evals/assertions.md` to sanity-check behavior after changing this skill or script.
