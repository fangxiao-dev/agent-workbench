# 双锚点与来源选择

Stable Docs Backfill 固定两种不可互换的锚点：

- `Method Activation Ref`：公共 Skill 所在 `agent-workbench` Git top-level 的 portable `repository + commit`。脚本从自身路径解析该 root，且要求同一 commit 同时包含 `skills/backfill-stable-docs/SKILL.md` 和 `skills/impl-package/SKILL.md`；它锁定方法与 Impl Package 的原子版本。
- `Project Source Watermark`：目标项目中上次已安全压实的 source commit，用来确定本轮 delta 的扫描下界。

每份 audit 还固定一个目标项目 `Source HEAD`。watermark 必须是 audit Source HEAD ancestor，否则 fail closed。apply 可在 audit Source HEAD 本身或其 descendant 上运行，但不得使用无祖先关系的 HEAD；更晚的 HEAD 只会通过逐项 item fingerprint 使实际受影响 item 保持 pending。watermark 最多推进到 audit 的 Source HEAD。Method Activation Ref 不参与目标项目 Git range，Project Source Watermark 也不能代替方法版本。

旧 Plugin-era audit 或 state 只作为 migration provenance；其 `plugin + version` 锚点不能用于 public Skill 的 apply。必须先重新 audit，以当前 repository+commit 生成新报告；迁移动作本身不得推进项目水位线。

## 稳态 eligible source

稳态 eligible source 是 watermark 后有 activity 的 implementation package 与 state 中未处置 carry-forward package 的并集。默认 semantic source 只有 package 内 `design.md` 与 `spec.md`；tracked `findings.md` 只在 design/spec 明确引用或出现 evidence gap / authority conflict 时作为 supplemental evidence。`gate.md`、pending 和 commits 只对账 closure / coverage，不作为语义来源。plan、DAG、tickets、progress 与 command logs 默认排除。

Bootstrap 不是全量迁移：只能处理 owner 明确给出的有界 source manifest。没有可信 watermark 时 audit 必须报告 blocker，不得猜测扫描下界。

## Collector 合同

- project root 和 method root 都必须为 Git top-level；project origin 和 method origin 都必须解析为 portable `owner/repository`；
- 配置可经 `--config` 指定，也可取 project root 的 `.stable-docs-backfill.json`；配置摘要与 project-relative paths 可进入 inventory，绝对 config path 不得持久化；
- 任何 output 必须留在 project root 内；
- inventory 记录方法 repository/commit、项目 repository、commits、配置 digest、package IDs、Git tree/blob identities 与项目相对路径；
- 清 watermark 不代表 carry-forward 已处置；未应用、冲突或 evidence 变化的 package 必须继续 carry-forward。
