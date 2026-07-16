---
target: skills/backfill-stable-docs
updated: 2026-07-15
---
## 原则

- [已确认] Audit/apply 失效必须按 item-local evidence 和语义影响收缩；同 repository 的方法版本或 descendant Source HEAD 漂移不能迫使未受影响 item 重做。

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-15
- 采纳「以 item-scoped fingerprint 替代全局 method commit/Source HEAD 等值门」— 用户原话：改为 item-scoped fingerprint；只让受影响 item 失效。

### R2 · 2026-07-16
- 采纳「agent-first 重设计」— 用户原话：初期使用较复杂 canonical design 显得笨重，阻止 agent 发挥主观能动性，也不方便人介入；先让 agent 判断，稳定后再上更 deterministic 的机制。
- 双锚点（Method Activation Ref + Project Source Watermark）、item-scoped fingerprint、`configSha256` fail-closed 校验降级为可选机器辅助，不再是唯一事实形态；真正的事实来源改为 agent 对 `_pending.md`、design/spec、代码和 stable docs 的实际阅读。
- 采纳「`_pending.md` 定为 audit 主要输入源」— 消费 `dev-with-track` Stage 7 已登记的 durable-delta 队列，不从零重新发现；只有 gate 已 terminal 但无对应登记的遗留 package 才走 gap-catching 兜底。
- 新增 Package Retirement Workflow：已完全吸收、gate 已终态、只剩过程性目录的空壳 package 可识别为清理候选，但清理属于独立于普通 apply 的 destructive-apply 授权，不在常规 audit/apply 里顺带做掉。
- `ignore` 从扁平字符串数组改为按 owner 分组的条目（`{ paths, owner, reason }`），解决单一仓库级配置下多 domain 历史排除项归属不清的问题，仍保持「每个 repo 一个配置」不变。

### R3 · 2026-07-16
- 采纳「机械识别不到不等于流程终点」— 用户原话：这是我流程设计上的一个疏漏，不是有意保留人工卡点；规则本来就是"能读懂就能判断"，格式识别只是加速手段，不是能力上限。
- 起因：litmus dry-run 在 prj-supplyer-webapp 上跑出 22 个 legacy 格式 `gate.md`（verdict 写成自由文本，不是新模板 heading），最初实现把它们标成"需要人工读"就停手了；用户指出 agent 自己完全有能力读懂这些自由文本并给出正常分类，不该在脚本认不出来时就把流程晾在那里。
- 落地：`audit-runbook.md`、`package-retirement-runbook.md`、`SKILL.md` 的 Agent-First 前提都补充了"机械信号只是脚本能力上限、不是 agent 能力上限"的明确要求——脚本标出"无法机械解析"时，agent 必须在同一轮 audit 里读完并给出正常分类，只有真正证据矛盾或缺失时才升级 owner 决策。

### R4 · 2026-07-16
- 采纳「代码落地优先于 checklist 打勾」— 用户原话：这个计划有没有进代码里？如果已经进代码里了，那就算完成；对于还有一些遗留问题，可以通过 issues 的方式跟踪，不要再把它放在这里，成一个一直没有完成的包。
- 起因：litmus dry-run 人工读完 22 份 legacy gate.md 后，10 个内容有歧义的 package 里有 8 个其实代码已经合并主干、只是仓库级技术债/外部 mutation 待审批/业务验收这类遗留项没打勾，最初的分类误判为"仍开放"。
- 落地：`package-retirement-runbook.md` 新增"Gate 终态判断"一节，明确用 `git merge-base --is-ancestor` 或直接核对源文件是否存在于目标分支来判断代码是否落地，而不是逐项 checklist；遗留项拆成 GitHub issue 单独跟踪；有多轮 patch gate 时以最新一轮为准；同时明确"代码真没合并"（含分支落后主干太多且内容已通过别的路径独立落地的 stale 分支）和"实现根本没开始"这两种才是真正未完成。

### R5 · 2026-07-16
- 采纳「gate.md 顶部说明性 prose 和账本 entry 分开对待」— 用户原话：append-only 这套对两三人团队价值不大，我们也不会真的回去看那个 ledger，这可能更适合全自动场景，一次性迁移已经做完，后续可以轻量操作；对抗后收敛为：不可变性本身保留（今天的 litmus dry-run 全程靠读多轮 gate 历史才能分清 `order-document-completion-workflow` 的 5 轮 patch 里哪份权威、`module-specs-restructure` 是否真的 stale），但 gate.md 顶部允许一行可变的"当前状态一览"，与下面严格 append-only 的判决/证据内容分开处理。
- 落地：`impl-package-composition-contract.md` §7、`dev-with-track` 的 gate.md 模板与 SKILL.md、`package-retirement-runbook.md` 都补充了这条区分——顶部一行摘要可随时改写以对齐最新 entry/结论，但不能单独携带 entry 里没有的判断或证据；entry 本身（含存量旧格式 gate.md 里的 Gate Decision/Verification 段落）继续严格 append-only。
