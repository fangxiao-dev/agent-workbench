# Eval Assertions

Use these objective checks when reviewing skill/script changes.

## create-current-bug

- `operation` is `create`.
- Command uses `upsert --project shop-web` in dry-run first.
- Payload includes `projectId=shop-web`.
- Generated frontmatter includes `项目名称` from `00_Config/projects.yml` when the project name is configured.
- Payload includes `sourceType=source-note`.
- Payload includes `sourceRelativePath=docs/bugs/cart-drawer-refresh.md`.
- `status` is `计划中`.
- `priority` is `当前`.
- `taskType` is `bug`.
- `verificationPath` is `不涉及`.
- `workspace` is `主工作区`.

## create-future-feature

- `operation` is `create`.
- Uses a project source note/discussion workflow for `supplier-admin`.
- Command uses `upsert --project supplier-admin` in dry-run first.
- Payload includes `projectId=supplier-admin`.
- Generated frontmatter includes configured `项目名称` when available.
- Payload includes valid `sourceType` and `sourceRelativePath`.
- `status` is `计划中`.
- `priority` is `未来规划`.
- `taskType` is `新增功能`.

## start-worktree

- `operation` is `update`.
- Command uses `upsert --project prj-supplyer-webapp`.
- `status` is `实施中`.
- `workspace` is `worktree`.
- Existing priority is not cleared.
- Source metadata is included or already present and valid on the existing task.

## verification-partial-real

- `operation` is `update`.
- Command uses `upsert --project prj-supplyer-webapp`.
- `status` is `验证中`.
- `verificationPath` is `部分真实链路`.
- Body includes `### 验证状态` and `### 残余风险`.

## complete-merged

- `operation` is `update`.
- Command uses `upsert --project prj-supplyer-webapp`.
- `status` is `已完成`.
- `workspace` is `主工作区`.
- `priority` is `null` or omitted only if already absent.
- Body includes final verification and residual-risk text.

## blocked-credentials

- `operation` is `update`.
- Command uses `upsert --project integrations`.
- `status` is `阻塞`.
- Priority is preserved unless explicitly changed.
- Next step states the unblock condition.
- Existing source metadata remains valid.

## source-capture-discussion

- Uses the Source Capture + Dashboard Workflow.
- Drafts a source note under `20_Sources/checkout-app/discussions/`.
- Creates or updates a linked `10_Tasks/checkout-app/` dashboard task.
- Command uses `upsert --project checkout-app`.
- Payload includes `projectId=checkout-app`.
- Payload includes `sourceType=discussion` or `source-note`.
- Payload includes `sourceRelativePath` pointing to the source note.
- The dashboard task has `状态=计划中`, `验证链路=不涉及`, and `工作区=主工作区`.
- The dashboard task source/body links back to the project `20_Sources/` note.
- Draft includes discussion summary, confirmed decisions, open questions, possible next actions, and related paths.

## dashboard-task-explicit

- Uses the task upsert workflow.
- `operation` is `create`.
- Target path is under `10_Tasks/checkout-app/`.
- Command uses `upsert --project checkout-app`.
- Payload includes `projectId=checkout-app`.
- Payload includes valid `sourceType` and `sourceRelativePath`.
- `status` is `计划中`.
- `priority` is `当前`.

## existing-markdown-source-to-task

- Uses the Existing Markdown source workflow.
- Reads or summarizes the existing Markdown source.
- Creates or updates a `10_Tasks/prj-supplyer-webapp/` dashboard task.
- Command uses `upsert --project prj-supplyer-webapp`.
- The task `来源` points to the provided Markdown path.
- Payload includes `sourceType=impl-plan`.
- Payload includes `sourceRelativePath=docs/impl-plans/2026-06-17-business-event.md`.
- Does not create a new `20_Sources/` note.

## project-task-from-existing-impl-plan

- Uses an existing implementation plan as the Markdown source.
- Runs dry-run first.
- Command uses `upsert --project billing-api`.
- Payload includes `projectId=billing-api`.
- Payload includes `sourceType=impl-plan`.
- Payload includes `sourceRelativePath=docs/impl-plans/2026-06-18-invoice-retry.md`.
- Target path is under `10_Tasks/billing-api/`.

## source-note-task

- Drafts a source note under `20_Sources/support-portal/`.
- Creates a linked task under `10_Tasks/support-portal/`.
- Command uses `upsert --project support-portal`.
- Payload includes `projectId=support-portal`.
- Payload includes `sourceType=source-note` or `discussion`.
- Payload includes `sourceRelativePath` pointing to the new note.

## missing-source-metadata-rejection

- Does not create/apply a project task without source metadata.
- Explains that project task create requires `sourceType` and `sourceRelativePath`.
- Either asks for the missing source metadata or offers to create a source note first.

## import-impl-plans-nonrecursive-skip-existing

- Uses `import-impl-plans --vault D:\CodeSpace\TaskManager --project prj-supplyer-webapp --limit 5`.
- Runs dry-run first.
- Import selection is non-recursive: direct `*.md` files in configured `sourceRoot` only.
- `README.md` is skipped.
- Nested folders such as `archive/` are not imported.
- Existing tasks are skipped unless `--overwrite-existing` is explicitly requested.

## validate-project-consistency

- Uses `validate --vault D:\CodeSpace\TaskManager --project prj-supplyer-webapp`.
- Validation recursively scans `10_Tasks/prj-supplyer-webapp/`.
- Validation fails when the containing folder, `项目ID`, and single `项目` value do not match.
- Validation fails when project tasks omit or misuse `来源类型` or `来源相对路径`.

## vault-migration-baseline

- Uses `init-vault-repo` dry-run before apply.
- For existing vault content, uses `baseline-commit` before broad migration/import changes.
- Mentions tracked `00_Config/projects.yml` and ignored `00_Config/projects.local.yml` after project setup.

## legacy-single-project-migration

- Uses `migrate-legacy-project --vault <vault> --project <project-id> --repo <repo-root>` dry-run before apply.
- Direct `10_Tasks/*.md` files are planned for `10_Tasks/<project-id>/`.
- Direct `20_Sources/*.md` files are planned for `20_Sources/<project-id>/discussions/`.
- The command refuses target overwrites and refuses unclassified legacy `来源` values before applying.
- Migrated task frontmatter includes scalar `项目ID`, single-item `项目`, single-item `来源类型`, and scalar `来源相对路径`.
- Migrated task frontmatter includes scalar `项目名称` when `00_Config/projects.yml` has a name for the target project.
- Repo-root absolute `来源` values become `来源类型=impl-plan` with repo-relative POSIX `来源相对路径`.
- Legacy direct source-note `来源` values become `来源类型=source-note` with the moved vault-relative note path.
- After apply, `validate --project <project-id>` passes for the migrated project.

## Script-Level Checks

- Lifecycle label fields in generated Markdown are YAML arrays.
- `项目ID` is a scalar string.
- `项目` is a single-item YAML list matching the project folder.
- `项目名称` is a scalar string copied from configured project `name`.
- `来源类型` is a single-item YAML list with a valid source type.
- `来源相对路径` is a scalar relative path.
- `validate` reports completed tasks with priority as an error.
- `validate` reports completed tasks outside `主工作区` as an error.
- `validate --project <project-id>` recursively checks files under that project task folder.
- `validate` reports project tasks whose folder, `项目ID`, and `项目[0]` do not match.
- `validate` reports project tasks whose `项目名称` does not match configured project `name`, and skips only that comparison if config is missing.
- `validate` reports missing source metadata on project tasks.
- `refresh-project-metadata` can dry-run all projects or one project and updates generated project identity frontmatter without changing task bodies.
- `refresh-bases` can dry-run all projects plus global or one project plus global, regenerates Bases from templates, and refreshes `.obsidian/types.json`.
- `refresh-dashboards` can dry-run all projects plus global or one project plus global and regenerates dashboard Markdown from templates.
- `refresh-project-metadata --project <project-id>`, `refresh-bases --project <project-id>`, and `refresh-dashboards --project <project-id>` reject project IDs that are not present in `00_Config/projects.yml`.
- `refresh-project-metadata` only replaces or inserts generated `项目ID`, `项目`, and `项目名称` frontmatter blocks; it does not re-render unrelated frontmatter fields.
- Generated project Bases do not expose `项目` or `来源相对路径` in properties, order, or pillProperties.
- Generated global Base maps `note.项目名称` to displayName `项目` and includes `项目` in the main orders and pillProperties.
- Generated project dashboards explicitly embed both `![[30_Bases/<project-id>.base#进行中]]` and `![[30_Bases/<project-id>.base#已完成]]`.
- Dry-run does not modify the vault.
- Project `upsert --apply` only writes under `10_Tasks/<project-id>/`.
- `import-impl-plans` is non-recursive, skips `README.md`, and skips existing tasks by default.
