---
name: backfill-stable-docs
description: 当需要审计 durable knowledge delta、把 owner 批准的子集写入 stable docs、验证结果或退休已完全吸收的 implementation package 时使用。
---

# Backfill Stable Docs

把 implementation package 中仍有长期价值的事实回刷到稳定文档。流程分为只读 audit、显式批准后的 apply、只读 verify；三阶段不可混写。配置校验、worktree 基准、inventory/gap-catching、Gate 识别、item ID 与 verify 的机械部分一律走 `scripts/` 与 config schema，skill 只保留 disposition、授权、冲突和收口判断。

## 配置与工作区基准

仓库根 `.stable-docs-backfill.json` 或显式的仓库内配置必须列出 `targetBranch`、implementation 根目录、stable-doc 文件/目录、ignore 条目和 done record；pending 文件可选，默认为空。报告通过 CLI 输出或显式 output path 生成，不要求 reports 目录。所有路径是仓库相对路径；ignore 每项必须有 `path`、`owner`、`reason`，不接受 wildcard 或仓库外配置。路径拒绝规则由 `config/repository-config.schema.json` 承接，配置由 `scripts/validate_config.py` 校验。

默认使用 `git worktree list --porcelain` 的第一条主工作区，记录路径、branch、HEAD 和 dirty 状态；调用发生在 linked worktree 时不把未合入内容混入当前事实。Source HEAD 定义本轮读取快照，`targetBranch` 独立用于判断 Gate comparison commit 是否已进入目标分支；target Git commit 的验证细节由 `references/verify-runbook.md` 承接。

## Audit（只读）

1. 运行 `validate_config.py`、`contract_preflight.py` 和 `collect_sources.py`，再按需使用 `gate_recognition.py` 与 `make_item_id.py`；机械操作不改 stable docs、pending 或 package。
2. 读取 optional pending（`pending-registry`）与 `records.done`，检查 terminal Gate Durable Deltas 是否已进入 `targetBranch` 的 gap-catching；pending 不抑制 gap-catching，done 是唯一机器去重依据。脚本只列 inventory，不决定 disposition。
3. 对每项给出 `candidate | already-covered | conflict | no-delta`，引用 current code/tests/stable docs 的直接证据；代码能证明 current behavior，不能单独证明 product intent，发生冲突时报告 owner decision，不猜。
4. item ID 使用 `<source-relative-path>::<delta-id>`，由来源提供稳定且可读的 delta ID。
5. 输出 report 和 audit JSON；不修改 stable docs、pending 或 package。

Gate 不存在表示没有 Gate 证据；字段不完整、comparison commit 不可用或尚未进入 `targetBranch` 时不得形成 gap-catching/retirement 候选，但 pending-registry 仍可人工审计。Gate Durable Deltas 为 `none` 时不产生候选。

`contract_preflight.py` 委托当前 Impl-Package 状态引擎校验活动 package，因此间接执行 `state.json` 的 `formatVersion: "3.5"` 检查；3.4 package 必须先完成一次性迁移，backfill 不复制或另行维护格式版本。

## Apply

只有 owner 明确批准 report/CLI 输出中的精确 item ID 才 apply。只修改批准 item 的 destination、对应 pending 项（如有）和 done record；gap-catching 不伪造 pending，不顺手处理同文件其他候选。移动、重命名、删除 stable docs 或退休 package 需要额外 destructive-apply 授权，精确到路径/package ID，不接受“这批全部”。保持改动最小，随后运行 verify。

## Verify

运行 `verify_stable_docs.py`，检查显式路径、target Git commit、stable-doc 本地链接、audit shape 和 inventory；失败只报告，不自动修复。具体 target commit/version 与本地链接检查按需读 `references/verify-runbook.md`。

## Retirement

仅当 package Gate terminal、实现已到达 target branch、所有 durable delta 已吸收/关闭，且没有 inbound reference 或剩余活动材料时，才列为删除候选；删除仍需要 owner 明确授权。

先由本 skill 根据权威结果确定 audit/apply/verify/retirement 各阶段、计数、剩余项和是否收口；若 active skill catalog 存在 `talk-to-boss`，再用它组织这些已经确定的结论，不参与状态判断。可选 skill 缺失不阻塞流程。
