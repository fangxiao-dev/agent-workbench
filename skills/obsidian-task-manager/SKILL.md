---
name: task-manager
description: Use this whenever the user asks to create, record, update, sync, validate, or inspect tasks or discussion notes in the local TaskManager vault. This skill turns natural-language manual triggers like "新建任务", "更新任务", "标成完成", "进入验证", "阻塞", "加到任务面板", "先记录讨论", "先记一下这个任务/想法", or "把这段先留档" into correct TaskManager Markdown updates, with dry-run first and explicit apply only.
user-invocable: true
---

# TaskManager

Use this skill to maintain the local TaskManager vault as the task source of truth and the default local place for early discussion/source capture. The vault is now multi-project and project-aware: normal task operations happen under `10_Tasks/<project-id>/`, and each project task records both lifecycle fields and source metadata.

Task creation remains source-driven. Use an existing Markdown file as the task source when one exists, or create a `20_Sources/<project-id>/` note first when the discussion has not yet landed in Markdown.

Default behavior is dry-run. Only mutate the vault when the user explicitly asks to apply, write, create, update, or record the note.

## Vault And Project Setup

Use the default vault unless the user names another vault:

```text
D:\CodeSpace\TaskManager
```

Initialize or migrate the vault with dry-run first:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py init-vault-repo --vault D:\CodeSpace\TaskManager
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py init-vault-repo --vault D:\CodeSpace\TaskManager --apply
```

For an existing vault, create a baseline commit before migration or broad generated changes:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py baseline-commit --vault D:\CodeSpace\TaskManager
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py baseline-commit --vault D:\CodeSpace\TaskManager --apply
```

Add each tracked project before importing or upserting project tasks:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py init-project --vault D:\CodeSpace\TaskManager --project <project-id> --repo <repo-root> --name "<Project Name>"
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py init-project --vault D:\CodeSpace\TaskManager --project <project-id> --repo <repo-root> --name "<Project Name>" --apply
```

`init-project` writes tracked metadata to `00_Config/projects.yml` and machine-local repository roots to ignored `00_Config/projects.local.yml`. It also creates project task/source folders, a project Base, and a dashboard that embeds the Base with an Obsidian wikilink.

To move a legacy single-project vault into one project namespace, use the reusable migration command in dry-run first:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py migrate-legacy-project --vault D:\CodeSpace\TaskManager --project <project-id> --repo <repo-root>
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py migrate-legacy-project --vault D:\CodeSpace\TaskManager --project <project-id> --repo <repo-root> --apply
```

The migration moves direct `10_Tasks/*.md` files into `10_Tasks/<project-id>/`, moves direct `20_Sources/*.md` files into `20_Sources/<project-id>/discussions/`, and refuses to apply if a target exists or any legacy `来源` cannot be classified.

Project Base files filter by task directory (`10_Tasks/<project-id>`). The `项目` field is used for grouping and validation, not for narrowing the Base query.

## Trigger Workflow

1. Identify the target project id. For project work, all create/update/import/validate commands should pass `--project <project-id>`.
2. Identify the Markdown source for the task:
   - If the work is already captured in a project Markdown file such as a Func Design, Implementation Plan, PRD/ARD note, or handoff, use that file path as `source`.
   - If the work only exists in the current session discussion, first create a `20_Sources/<project-id>/` source note, then use that note path as `source`.
3. Identify whether the user wants to create a new task or update an existing task.
4. Convert the user's natural-language intent into the JSON shape from `templates/task-update.json`.
5. Include project source metadata for project tasks:
   - `projectId`: scalar project id, matching `--project`.
   - `sourceType`: one of `impl-plan`, `source-note`, `discussion`, or `handoff`.
   - `sourceRelativePath`: scalar relative path to the source.
6. Apply the lifecycle and field rules from:
   - `rules/task-lifecycle.md`
   - `rules/field-semantics.md`
7. Run the script in dry-run mode first:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py upsert --vault D:\CodeSpace\TaskManager --project <project-id> --input <task-update.json>
```

8. Review the dry-run output. If the user asked for actual writing, run again with `--apply`.
9. For project checks, run recursive validation:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py validate --vault D:\CodeSpace\TaskManager --project <project-id>
```

## Markdown Source To Dashboard Workflow

Every dashboard task should point back to a Markdown source. Existing repo Markdown and newly captured `20_Sources/<project-id>/` notes are equivalent as sources for task creation.

Use this path when the user is discussing work that is not yet a formal task or implementation plan, but still wants it recorded for follow-up. Natural phrases include:

- "先记录讨论", "先把这个讨论记下来", "把这段先留档"
- "先保留上下文", "先存一下这个方向", "先落一下计划以后继续"
- "先记一下这个任务/想法", "后面可能要做"

Default project source destination:

```text
D:\CodeSpace\TaskManager\20_Sources\<project-id>
```

Use `20_Sources/<project-id>/discussions`, `specs`, `references`, or `handoffs` for the full session discussion, requirement draft, long context, source excerpt, or pre-task plan capture.

### Existing Markdown source

Choose this when the source already exists as Markdown in the project or vault.

1. Read the source Markdown enough to summarize current status and next action.
2. Create/update a dashboard task in `10_Tasks/<project-id>/` with `来源` pointing to that Markdown path.
3. Set `项目ID=<project-id>`, `项目=[<project-id>]`, `来源类型`, and `来源相对路径`.
4. Use the source content and repo evidence to infer lifecycle fields. If it is only a plan/discussion source and no implementation has started, default to `状态=计划中`, `验证链路=不涉及`, `工作区=主工作区`.
5. Dry-run `task_manager.py upsert --project <project-id>` before applying.

For implementation plans, prefer `import-impl-plans` when importing a batch:

```powershell
python D:\CodeSpace\agent-workbench\skills\obsidian-task-manager\scripts\task_manager.py import-impl-plans --vault D:\CodeSpace\TaskManager --project <project-id> --limit 5
```

`import-impl-plans` scans only direct `*.md` files under the project's configured `sourceRoot`, skips `README.md`, does not recurse into folders such as `archive/`, and skips existing task files unless `--overwrite-existing` is explicitly provided.

### Session discussion source

Choose this when the source does not exist yet as Markdown.

1. Pick a concise topic and target path like `20_Sources/<project-id>/discussions/YYYY-MM-DD-<topic>.md`.
2. Draft the source Markdown using `templates/source-note.md`.
3. Create/update a dashboard task in `10_Tasks/<project-id>/` with `来源` pointing to the source note path.
4. Set `sourceType=source-note` for a written note or `sourceType=discussion` for discussion capture, and set `sourceRelativePath` to the source note's relative path.
5. Default the task to `状态=计划中`, `验证链路=不涉及`, `工作区=主工作区`; infer `任务类型` and `优先级` from wording. If the wording says it is not ready for formal planning or "后面可能要做", prefer `优先级=下一批` unless urgency is stated.
6. Dry-run both artifacts: show the source note target/summary and run `task_manager.py upsert --project <project-id>` for the dashboard task before writing.
7. Apply only when the user explicitly asks to record/write/save/update it.
8. If a later Func Design or Implementation Plan is created, keep the source note as context, update the source note "关联路径", and update the task `来源`, `来源类型`, `来源相对路径`, or body if needed; do not copy the whole raw discussion into repo docs.

### Source-only exception

Only skip the dashboard task when the user explicitly says the material is for context only and should not be tracked, for example "只留档，不进任务面板", "不要加 dashboard", or "只进 Sources".

## Manual Trigger Interpretation

Prefer natural-language interpretation. Do not ask for every field when the rules can infer it.

Common phrases:

- "新建任务", "记录任务", "加到任务面板" -> `operation=create`
- existing Markdown source, such as a Func Design or Implementation Plan -> create/update a dashboard task with `来源`, `来源类型`, and `来源相对路径` pointing to that Markdown
- "先记录讨论", "把这段先留档", "先保留上下文", "先存一下这个方向", "先落一下计划以后继续", "先记一下这个任务/想法", "后面可能要做" -> create/update a source note under `20_Sources/<project-id>/` and a linked dashboard task under `10_Tasks/<project-id>/`
- "只留档，不进任务面板", "不要加 dashboard", "只进 Sources" -> create/update only a source note under `20_Sources/<project-id>/`
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
  "projectId": "project-id",
  "status": "计划中",
  "priority": "当前",
  "taskType": "新增功能",
  "verificationPath": "不涉及",
  "workspace": "主工作区",
  "sourceType": "impl-plan",
  "sourceRelativePath": "docs/impl-plans/example.md",
  "source": "",
  "progress": "",
  "nextStep": "",
  "verificationStatus": "",
  "residualRisk": ""
}
```

Omit unknown fields. Use `null` for intentionally clearing `priority`.

Project tasks require `sourceType` and `sourceRelativePath` on create. Updates may omit them only when the existing task already has valid source metadata. `--project` and `projectId` must match when both are supplied.

The script writes project frontmatter as:

- `项目ID`: scalar string.
- `项目`: single-item YAML list matching `项目ID`.
- `来源类型`: single-item YAML list.
- `来源相对路径`: scalar relative path.

Legacy non-project task notes can still be maintained without `--project`, but new work should use the project-aware workflow.

## Safety Rules

- Default to dry-run unless the user explicitly asked to write/apply.
- Do not change files outside the configured vault and this skill's own workspace.
- Do not rewrite unrelated task body sections during an update.
- Preserve existing task content whenever the update input does not mention that section.
- If multiple task files could match a task name, stop and ask the user which one.

## Evals

Use `evals/evals.json` and `evals/assertions.md` to sanity-check behavior after changing this skill or script.
