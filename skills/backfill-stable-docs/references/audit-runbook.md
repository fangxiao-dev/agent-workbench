# Audit Runbook

Audit 对 source 只读；唯一允许写入是配置 `records.reports` 目录（默认 `docs/_backfill/reports/`）下的新报告。

1. 读取单 repo 配置，展开 `implementations`、必需的 `stableDocs.systemKnowledge`/`stableDocs.moduleKnowledge`、可选的 `stableDocs.contextKnowledge` 和按 owner 分组的 `ignore` 条目。记录主工作区路径、分支、Source HEAD/dirty 状态；另以 `git rev-parse <targetBranch>` 解析 package completion 的目标 commit，不自动 fetch。`targetBranch` 无法解析时报告 config gap，但继续完成不依赖 package closure 的只读盘点。
2. 按 [来源选择与 pending 消费](source-selection-and-pending-consumption.md) 的发现规则定位三层 pending register：system 默认 `docs/_pending.md`，首次不存在时记为非阻塞 `cold-start` owner decision、不自动创建；context/module root 的 `missing` 或 `ambiguous` 记为 config gap并只停止该 root。多个 root 指向同一文件时按 `pendingPath` 去重。
3. 枚举每个已发现 `_pending.md` 中尚未关闭的登记条目——这是主渠道候选种子，每条已经带 destination、delta-id、statement 和来源 package 指针。对每条：回到来源 package 核对 `design.md`/`spec.md`/`plan.md`/gate entry 确认 statement 仍准确；核对当前代码和测试确认设计仍落地；核对 destination 处的 stable docs 判断是否已被别的 apply 覆盖。任一冲突写入报告并标注需要 owner 裁决；不自行改写 `_pending.md` 登记内容本身。
4. 补充做 gap-catching 扫描：枚举 gate ledger 有 terminal entry、相关实现 commit 已进入 `targetBranch`、但对应 `_pending.md` 里没有登记的 package。只有这类 package 才需要重新读 `design.md`、`spec.md`、`plan.md`、review、handoff、tickets 和 Git commit 去发现候选；`findings.md` 仅在 design/spec 明确引用或出现 evidence gap / authority conflict 时作为 supplemental evidence。
   - 机械识别 terminal entry 只对新模板的 `## <attempt-id>-G<n> · <pass|fail|blocked|defer>` 这类固定 heading 有效。存量 package 的 `gate.md`（在这次重设计之前写的）几乎全部不是这个格式——verdict 常常写成正文里的一句「Verdict：PASS」「Decision：closed」，脚本机械扫描不到。这类 package 会被脚本标成"gate.md 存在但 verdict 无法机械解析"，不能当作"没有 terminal、跳过即可"，也不能停在"标记为需要人工"就算完成本轮 audit——机械识别不到只是脚本的能力上限，不是 agent 的能力上限。agent 必须在同一轮 audit 里把这些 `gate.md` 全部打开读完，给出和其他 package 一样的正常分类（candidate / already-covered / conflict / no-delta，或 Package Retirement 候选），并入 audit report 的正常表格，不单独留一个"待人工"清单晾着不处理。真的证据矛盾或缺失、读不出结论时，才升级为需要 owner 裁决。
5. 对 gap-catching 候选，解析相关 Git commit/diff（缺少显式 commit 时按 package 日期、相关文件、plan execution record 和 Git history 做有界确认），使用 Git ancestor/reachability 证据确认实现已进入解析后的 `targetBranch` commit，再对照主工作区 Source HEAD 的当前代码和测试确认没有被后续改动推翻；两者角色不能混用。代码与短期设计冲突时以当前实现和最终 evidence 为准，冲突写入报告。
6. 对照 stable docs，判断每条候选（无论来自主渠道还是 gap-catching）是否已覆盖、需要回刷、应 pending，或不属于 stable docs。
7. 顺带识别 [Package Retirement](package-retirement-runbook.md) 候选：`gate.md` 已 terminal、该 package 在所有 `_pending.md` 里的登记都已关闭、且 design/spec 内容已被 stable docs 完全吸收的 package，列入报告的 `retirementCandidates`，不在 audit 里清理。
8. 生成 audit report，明确区分"来自 `_pending.md` 登记的候选"和"gap-catching 发现的候选"，列出 candidate、pending proposal、already-covered、rejected-with-reason 和需要 owner 决策的 item。

`gate.md` 和 `_pending.md` 都不作为唯一判定依据，只回答"这个 package 声称完成了什么、已经登记了哪些 durable delta"；是否能回刷仍由 agent 阅读证据后判断。报告不能推进任何 watermark、清 `_pending.md`、改 canonical docs 或修复链接。
