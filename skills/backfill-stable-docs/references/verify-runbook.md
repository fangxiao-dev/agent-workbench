# Verify Runbook

Verify 是独立只读阶段，不创建报告，不改 canonical docs，不清 `_pending.md`，不隐式 apply。它检查：

- 已标记 `done` 的 item 是否仍能追溯到 implementation package 和代码证据。
- stable docs 是否存在断链、重复事实源或明显冲突。
- 各处 `_pending.md` 中的登记是否仍然有未解决 owner decision 或 evidence gap；system 级 `docs/_pending.md` 首次缺失记为非阻塞 `cold-start`，不自动创建、不算 config gap。
- 配置中的 `implementations`、必需的 system/module stable root 和可选的 context stable root 是否仍覆盖当前仓库布局，以及 `records.pending` 的自动发现是否仍能唯一定位 context/module root 对应的 `_pending.md`；多个 root 共用一个 pending 文件时按路径去重，`missing`/`ambiguous` 才报告 config gap。
- `targetBranch` 是否能通过 `git rev-parse <targetBranch>` 解析到本地 commit；不自动 fetch，不做陈旧性推断。主工作区 Source HEAD 是 current snapshot，target branch commit 是 package completion 目标，两者分别记录。
- 是否存在已完全吸收、gate 已终态、只剩过程性目录的空壳 package——标记为 [Package Retirement](package-retirement-runbook.md) 候选，不在 verify 里直接清理。
- inventory/Markdown 汇总必须分别给出 `indexed`、`legacy-heading`、`mismatch`、`manual` 四类计数，并对 indexed entry 报告是否适用于当前 D/S/P；合法历史 entry 保持 `indexed` 但没有当前 resolution。inventory 的 `gapCatchingStructuralCandidates` 仅表示尚未核验 Git reachability 的结构清单，verify 不得把它直接当 audit 的真实 `gapCatchingCandidates`。`mismatch`/`manual` 都进入人工复核且不得因 open pending reference 隐藏。没有 `gate.md`，或只有空 ledger 且尚无 allocation/entry，保持 open/no-verdict，不计入四类。

Verify 发现问题时只报告，不自动修复。
