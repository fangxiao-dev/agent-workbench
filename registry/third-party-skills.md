# Third-party Skills

| Skill | 来源 | 获取方式 | 备注 |
|-------|------|----------|------|
| research | `mattpocock/skills` | `npx skills add mattpocock/skills@research -g -y` | 已放入 `skills/research/` |
| cso | `garrytan/gstack` | `npx skills add garrytan/gstack --skill cso --full-depth -y --copy` | 已放入 `skills/gstack/cso/` |
| office-hours | `garrytan/gstack` | `npx skills add garrytan/gstack --skill office-hours --full-depth -y --copy` | 已放入 `skills/gstack/office-hours/` |
| plan-ceo-review | `garrytan/gstack` | `npx skills add garrytan/gstack --skill plan-ceo-review --full-depth -y --copy` | 已放入 `skills/gstack/plan-ceo-review/` |
| plan-design-review | `garrytan/gstack` | `npx skills add garrytan/gstack --skill plan-design-review --full-depth -y --copy` | 已放入 `skills/gstack/plan-design-review/` |
| qa | `garrytan/gstack` | `npx skills add garrytan/gstack --skill qa --full-depth -y --copy` | 已放入 `skills/gstack/qa/` |
| qa-only | `garrytan/gstack` | `npx skills add garrytan/gstack --skill qa-only --full-depth -y --copy` | 已放入 `skills/gstack/qa-only/` |
| review | `garrytan/gstack` | `npx skills add garrytan/gstack --skill review --full-depth -y --copy` | 已放入 `skills/gstack/review/` |
| frontend-design | `anthropics/skills` | `npx skills add anthropics/skills@frontend-design -g -y` | 已放入 `skills/frontend-design/` |
| skill-creator | `anthropics/skills` | 人工迁移 | 本地副本作为 `write-skill-smartly` 的内部方法论保留在 `skills/write-skill-smartly/sub-skills/skill-creator/`，不单独暴露给宿主；Codex `.system` 版本不受影响 |
| ask-matt | `mattpocock/skills` | `npx skills add mattpocock/skills@ask-matt -g -y` | 已放入 `skills/ask-matt/`；已同步上游（phase boundaries / wayfinder 路由） |
| diagnosing-bugs | `mattpocock/skills` | `npx skills add mattpocock/skills@diagnosing-bugs -g -y` | 本地维护副本位于 `skills/diagnosing-bugs/`；已 cherry-pick 上游 Redact + Phase 1 脱敏展示 |
| bug-fix-tdd | `obra/superpowers` | 人工迁移并打薄 | 上游 skill 名为 `test-driven-development`；本地作为 `diagnosing-bugs` 的修复执行器，位于 `skills/diagnosing-bugs/sub-skills/bug-fix-tdd/SUB-SKILL.md`；原版保存在 deprecated Superpowers 归档 |
| grill-me (retired) | `mattpocock/skills` | 历史登记 | 上游仅一行 `Run a /grilling session`；主仓不保留副本，由 `grilling` / `grill-me-smartly` 覆盖 |
| grill-with-docs | `mattpocock/skills` | `npx skills add mattpocock/skills@grill-with-docs -g -y` | 已放入 `skills/grill-with-docs/`；`agents/openai.yaml` 禁止隐式调用 |
| triage (retired) | `mattpocock/skills` | 历史登记 | 主仓不装 Matt `triage`；issue 路由由本地 `issue-workflow` 等承接 |
| prototype | `mattpocock/skills` | `npx skills add mattpocock/skills@prototype -g -y` | 已放入 `skills/prototype/`；已同步上游（HTML 单文件 demo / primary source） |
| setup-matt-pocock-skills | `mattpocock/skills` | `npx skills add mattpocock/skills@setup-matt-pocock-skills -g -y` | 已放入 `skills/setup-matt-pocock-skills/`；已同步上游 |
| tdd | `mattpocock/skills` | `npx skills add mattpocock/skills@tdd -g -y` | 已放入 `skills/tdd/`；已同步上游（reference-only red→green / seam） |
| to-spec | `mattpocock/skills` | 人工迁移上游 `skills/engineering/to-spec` | Vendored 只读参考（上游 `391a270`），不进入 Impl-Package 主链；repo facts、testing seam 与 user-semantics synthesis 方法已吸收进 `req-align` |
| to-tickets | `mattpocock/skills` | 基于上游 `skills/engineering/to-tickets` 本地分叉 | Impl-Package 本地 fork，位于 `plugin-marketplace/plugins/impl-package/skills/to-tickets/`（上游基线 `391a270`）；上游更新只做人工 diff/选择性合并，不直接覆盖 |
| domain-modeling | `mattpocock/skills` | `npx skills add mattpocock/skills@domain-modeling -g -y` | 已放入 `skills/domain-modeling/` |
| codebase-design | `mattpocock/skills` | `npx skills add mattpocock/skills@codebase-design -g -y` | 已放入 `skills/codebase-design/` |
| standards-review | `mattpocock/skills` | 人工迁移上游 `skills/engineering/code-review` | 基于 `391a270` 的原 module-review Standards 轴拆分并中文化后放入 `plugin-marketplace/plugins/impl-package/skills/standards-review/` |
| spec-review | `mattpocock/skills` | 人工迁移上游 `skills/engineering/code-review` | 基于 `391a270` 的原 module-review Spec 轴拆分并中文化后放入 `plugin-marketplace/plugins/impl-package/skills/spec-review/` |
| module-review (deprecated) | `mattpocock/skills` | 历史本地归档 | 原双轴 reviewer 已移至 `skills-deprecated/module-review/`，不在 active registry、preflight 或默认 topology 中 |
| improve-codebase-architecture | `mattpocock/skills` | `npx skills add mattpocock/skills@improve-codebase-architecture -g -y` | 已放入 `skills/improve-codebase-architecture/`；已同步上游（YAGNI 范围 + harness-neutral subagent） |
| grilling | `mattpocock/skills` | `npx skills add mattpocock/skills@grilling -g -y` | 已放入 `plugin-marketplace/plugins/impl-package/skills/grilling/`；上游 frontier-rounds 基线 + 本地吸收原 `grilling-waves` 的文档主体/upper-level context/延后 writeback |
| handoff | `mattpocock/skills` | `npx skills add mattpocock/skills@handoff -g -y` | 已放入 `skills/handoff/` |
| teach | `mattpocock/skills` | `npx skills add mattpocock/skills@teach -g -y` | 已放入 `skills/teach/`；`agents/openai.yaml` 禁止隐式调用 |
| writing-for-agents | `mattpocock/skills` | `npx skills add mattpocock/skills@writing-for-agents -g -y` | 上游自 `writing-great-skills` 重命名；已放入 `skills/writing-for-agents/`；`write-skill-smartly` 已改引用 |
| resolving-merge-conflicts | `mattpocock/skills` | `npx skills add mattpocock/skills@resolving-merge-conflicts -g -y` | 已放入 `skills/resolving-merge-conflicts/` |
| wait-what | `mattpocock/skills` | `npx skills add mattpocock/skills@wait-what -g -y` | 已放入 `skills/wait-what/` |
| vercel-react-best-practices | `vercel-labs/agent-skills` | `npx skills add vercel-labs/agent-skills@vercel-react-best-practices -g -y` | 已放入 `skills/vercel-react-best-practices/` |
| find-skills | `vercel-labs/skills` | `npx skills add vercel-labs/skills@find-skills -g -y` | 已放入 `skills/find-skills/` |
| powershell-windows | `davila7/claude-code-templates` | `npx skills add davila7/claude-code-templates@powershell-windows -g -y` | 已放入 `skills/powershell-windows/` |
| continuous-learning | `affaan-m/everything-claude-code` | 人工迁移 | 已退役，保留在 `skills-deprecated/continuous-learning/` |
| api-integration-builder | `daffy0208/ai-dev-standards` | `npx skills add daffy0208/ai-dev-standards@api-integration-builder -g -y` | 已放入 `skills/api-integration-builder/` |
| code-review | `supercent-io/skills-template` | `npx skills add supercent-io/skills-template@code-review -g -y` | 已放入 `plugin-marketplace/plugins/impl-package/skills/code-review/` |
| git-workflow | `supercent-io/skills-template`（历史来源） | 历史命令：`npx skills add supercent-io/skills-template@git-workflow -g -y` | 本地维护分叉位于 `skills/git-workflow/`；上游在 2026-07-22 不可解析，后续不直接覆盖本地版本。 |
| documentation-generator | `jorgealves/agent_skills` | `npx skills add jorgealves/agent_skills@documentation-generator -g -y` | 已放入 `skills/documentation-generator/` |
| prompt-optimizer | `daymade/claude-code-skills` | `npx skills add daymade/claude-code-skills@prompt-optimizer -g -y` | 已放入 `skills/prompt-optimizer/` |
| test-generator | `oimiragieo/agent-studio` | `npx skills add oimiragieo/agent-studio@test-generator -g -y` | 已放入 `skills/test-generator/` |
| explain-diff-html | `geoffreylitt/a29df1b5f9865506e8952488eac3d524` | 人工迁移并本地改良 | 基于 Gist 的本地 fork，已放入 `skills/explain-diff-html/`；固定渲染器、schema 校验与离线安全边界为本地改动 |

## 说明

- 只登记第三方 skills，不登记本仓库自建 skills。
- 独立第三方 skill 放在 `skills/<name>/`；plugin-owned skill 放在 `plugin-marketplace/plugins/<plugin>/skills/<name>/`。
- 如需修改第三方 skill，直接修改正式副本；更新上游时先拉到临时位置，再人工对比合并。
