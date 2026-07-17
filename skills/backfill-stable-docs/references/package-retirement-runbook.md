# Package Retirement Runbook

一次性迁移和历史 bootstrap 会留下大量 package：它们的 durable delta 已经被吸收进 stable docs、gate 已经 terminal 关闭，目录里剩下的只是 `evidence/`、`tasks/`、`tickets/`、`_compaction/` 这类过程性内容，不再提供任何仍需查阅的信息。这些"空壳" package 不应无限期占用 implementation root，但清理是破坏性操作，必须显式 owner 批准，不能在普通 audit/apply 里顺带做掉。

## Gate 终态判断：代码有没有落地，比 checklist 打没打勾更重要

判断一个 package 是否已经收口，核心问题是"这次改动的代码有没有真的进入配置的 `targetBranch`"，不是"gate 里的每一项 checklist 是不是都打勾了"。主工作区 Source HEAD 只定义 backfill 当前读取的 docs/code 快照，不自动等于 `targetBranch`；脚本只按 `git rev-parse <targetBranch>` 解析本地已有 ref，不自动 fetch。仓库级技术债（例如既有 typecheck/build baseline）、需要 owner 审批才能跑的外部 mutation smoke、业务方人工验收这类遗留项，不应该让整个 package 无限期"开放"——一旦用 `git merge-base --is-ancestor <commit> <resolved-target-commit>` 或等价 Git evidence 确认代码已经合并（不能只看 gate 文档自己怎么写），这些遗留项应该建议拆成独立 GitHub issue 跟踪，package 本身按已完成处理；创建 issue 必须在当前 session 获得 owner 对具体事项的明确授权。

只有以下两种情况才是真正的"未完成"，不能套用上面的豁免：

- 代码本身还没合并（例如 gate 明确写"ready on isolated branches, merge not executed"）——这种情况下还要核实一遍该分支相对当前主干是否已经过时（分支落后主干太多、且其独有内容已经通过别的路径独立落地时，应判定为 stale/superseded，而不是"仍待合并"；用 `git log <target>..<branch>` 看分支独有 commit，再逐个核实这些内容是否已经存在于当前主干）；
- 实现根本还没开始（gate 明确写 planning-only、尚未动代码）。

当前 package 永远只有一个 `gate.md`；initial/patch attempt 的 entry 都写入同一 append-only ledger，当前 attempt 与 D/S/P revision set 由 registry 和 canonical resolver 现场派生，不通过文件名或时间猜测。存量 `<slug>.patch-gate.md` 只可作为 legacy supplemental evidence，不能参与当前机械选择，也不得作为新 patch 的输出格式。

当前 `gate.md` 顶部状态由 `gate-status` machine-owned marker 投影，消费者不得手工编辑，也不得把 marker 外的人话摘要当判决来源。旧格式 package 在 marker 外遗留的"状态：xxx"只属于 legacy evidence；迁移时由 impl-package owning workflow 一次性转换或删除，backfill/retirement 不以改写这行来修复状态。真正 verdict 来自 content-bound finalized entry；旧 package 无 runtime-state 时才允许按 legacy heading 兼容读取。

## 识别 GC 候选

按以下条件识别候选，不自动清理：

1. append-only gate ledger 已可信 terminal：`indexed` 必须同时满足 `gateAppliesToCurrentRevision=true` 且 resolution 为 pass/fail/defer；无 runtime-state 存量 package 的 `legacy-heading` 可作为兼容 terminal evidence；fail 仍为 terminal。合法历史 indexed entry 不证明当前 D/S/P，不能列为结构候选；`mismatch`/`manual` 必须先由 agent 读证据并正常分类，不能由脚本列为结构候选。顶部投影、legacy 摘要或 checklist 只作导航，真正 Active（代码未合并或未开始）的 package 永不作为候选。
2. Git 已证明 package 声称的实现实际进入解析后的 `targetBranch` commit；`targetBranch` 无法解析或实现 commit 不可确认时不得列为候选。
3. 该 package 产生的所有登记在任何已发现的 `_pending.md` 里都已关闭（没有仍指向它的未决条目）。
4. package 目录下 `design.md`/`spec.md` 要么不存在，要么其内容已被判定为 already-covered（已被当前 stable docs 完整吸收），且没有其他文档的 inbound reference，不再提供任何仍需保留的信息。

满足以上四条时列为"可清理候选"，附上 gate 终态、target branch Git 证据、closure 时间、吸收去向（具体 stable doc 路径）、inbound reference 检查和目录当前剩余内容清单。四条缺一即保留，不因为"看起来只有 evidence"就放宽判断——必须真的核对过目标分支、`_pending.md`、stable docs 和 gate ledger。

脚本按 `indexed`、`legacy-heading`、`mismatch`、`manual` 四类报告 gate。runtime-state 完全不存在时才允许 legacy heading fallback；一旦 runtime-state 存在，缺 entry、entry/字段/content binding 不符、陈旧或损坏都按 `mismatch`，`gateResolution=null`，宁可人工判断也不信陈旧 JSON 或裸 heading。没有 `gate.md`，或只有空 ledger 且尚无 allocation/entry，是 open/no-verdict，不是第五类。`mismatch`/`manual` package 必须当场读完并按上面四条标准正常分类，不能因为脚本没有给出可信 terminal resolution 就跳过或搁置。

## 清理执行

清理属于 Destructive Apply（见 [apply runbook](apply-runbook.md)），需要 owner 在当前 session 对具体 package id 清单显式批准，先前 session 的授权不延续；不能用"全部清理"当批准。批准后：

- 确认待删除内容已经反映进当前 stable docs（逐条对照 `done.json` 或 `_pending.md` 关闭记录）；
- 确认没有其他 package 或 stable doc 仍在引用这里的具体文件（比如别的 `design.md` 链接到本 package 的截图或数据），有引用时改为暂缓清理并报告；
- 删除整个 package 目录，提交为一次独立 commit，不与其他内容变更混在一起，方便日后按 commit 找回；
- 在 `done.json`（或新增的轻量 `retired.json`）记录被删除的 package id、closure 证据（gate entry id）、吸收去向和删除 commit——这条记录本身就是新的 provenance 指针，替代原来的目录。

删除后 provenance 由 Git 历史承载（该 package 曾经存在、其内容和删除时间都在 commit log 里），不要求 package 目录本身永久保留才算"保留 provenance"。
