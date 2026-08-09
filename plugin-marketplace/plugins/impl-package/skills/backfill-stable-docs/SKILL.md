---
name: backfill-stable-docs
description: 当需要审计 durable knowledge delta、把 owner 批准的子集写入 stable docs、验证结果或退休已完全吸收的 implementation package 时使用。
---

# Backfill Stable Docs

把 implementation package 中仍有长期价值的事实回刷到稳定文档。流程分为只读 audit、显式批准后的 apply、只读 verify；三阶段不可混写。

## 配置

仓库根 `.stable-docs-backfill.json` 或显式的仓库内配置文件必须列出：targetBranch、implementation 根目录、stable-doc 文件/目录、ignore 条目和 done record；pending 文件可选，默认为空。报告通过 CLI 输出或显式 output path 生成，不要求 reports 目录。所有路径都是仓库相对路径；ignore 每项必须有 `path`、`owner`、`reason`；不接受 wildcard 或仓库外配置。

## 工作区基准

默认使用 `git worktree list --porcelain` 的第一条主工作区，记录其路径、branch、HEAD 和 dirty 状态。调用发生在 linked worktree 时也不把未合入内容混入当前事实。Source HEAD 定义本轮读取快照；`targetBranch` 独立用于判断 Gate comparison commit 是否已进入目标分支。

## Audit

1. 运行 `validate_config.py`、`contract_preflight.py` 和 `collect_sources.py`。
2. 读取 optional pending（`pending-registry`）、`records.done`，再检查 terminal Gate Durable Deltas 已进入 targetBranch 的 `gap-catching`；pending 不抑制 gap-catching，done 负责已处理 item 的去重。脚本只列 inventory，不决定 disposition。
3. 对每项给出 `candidate | already-covered | conflict | no-delta`，并引用 current code/tests/stable docs 的直接证据。
4. item ID 使用 `<source-relative-path>::<delta-id>`，由来源自己提供稳定且可读的 delta ID。
5. 输出 report 和 audit JSON；不修改 stable docs、pending 或 package。

Gate 不存在表示没有 Gate 证据；字段不完整、comparison commit 不可用或尚未进入 targetBranch 时不得形成 gap-catching/retirement 候选，但 pending-registry 仍可人工审计。Gate Durable Deltas 为 `none` 时不产生候选。

`contract_preflight.py` 委托当前 Impl-Package 状态引擎校验活动 package，因此会间接执行 `state.json` 的 `formatVersion: "3.4"` 检查；backfill 不复制或另行维护格式版本。

## Apply

只有 owner 明确批准 report/CLI 输出中的精确 item ID 才 apply。仅修改批准 item 的 destination、对应 pending 项（如有）和 done record；gap-catching 不伪造 pending。不顺手处理同文件其他候选。移动、重命名、删除 stable docs 或 retirement 需要额外 destructive-apply 授权，精确到路径/package ID。保持改动最小，随后运行 verify。

## Verify

运行 `verify_stable_docs.py`，检查显式路径、target Git commit、stable-doc 本地链接、audit shape 和 inventory。失败只报告，不自动修复。

## Retirement

仅当 package Gate terminal、实现已到达 target branch、所有 durable delta 已吸收/关闭、且没有 inbound reference 或剩余活动材料时，才列为删除候选。删除仍需要 owner 明确授权。

汇报时使用 `talk-to-boss`，区分 audit/apply/verify/retirement 各阶段和计数。
