---
name: backfill-stable-docs
description: 当需要审计 durable knowledge delta、把 owner 批准的子集写入 stable docs、验证结果或退休已完全吸收的 implementation package 时使用。
---

# Backfill Stable Docs

把 implementation package 中仍有长期价值的事实回刷到稳定文档。流程分为只读 audit、显式批准后的 apply、只读 verify；三阶段不可混写。配置校验、worktree 基准、inventory/gap-catching、Gate 识别、item ID 与 verify 的机械部分一律走 `scripts/` 与 config schema，skill 只保留 disposition、授权、冲突和收口判断。

阶段顺序：

1. **配置与工作区基准**：先固定本轮配置、source HEAD 和 dirty 状态。
   - 常见误判：不先固定基准就收集 source，会把 linked worktree 或本轮未合入内容混进 audit 事实。
2. **Audit（只读）**：建立 inventory、gap-catching 和 disposition 候选，但不写入。
   - 常见误判：把 inventory 候选直接当成 owner 已批准的 durable delta，会越过冲突和意图判断。
3. **Apply**：将 owner 对已展示且未变化报告的明确批准解析为精确 item ID 集合后写入。
   - 常见误判：批准必须能唯一确定 item 集合；报告变化、冲突项或删除范围仍需单独裁决。
4. **Verify（只读）**：在 apply 后检查路径、target commit、链接和 audit shape。
   - 常见误判：验证器保持只读；本轮 apply 造成的机械缺陷回到同一授权 apply 修复后重验。
5. **Retirement（如适用）**：只有 package 已完全吸收且没有 inbound reference 时才列删除候选。
   - 常见误判：把 Gate terminal 或实现合入单独当成可删除证明，会丢掉未吸收的 durable delta 或活动引用。

## 配置与工作区基准

仓库根 `.stable-docs-backfill.json` 或显式的仓库内配置必须列出 `targetBranch`、implementation 根目录、stable-doc 文件/目录、ignore 条目和 done record；pending 文件可选，默认为空。报告通过 CLI 输出或显式 output path 生成，不要求 reports 目录。所有路径是仓库相对路径；ignore 每项必须有 `path`、`owner`、`reason`，不接受 wildcard 或仓库外配置。路径拒绝规则由 `config/repository-config.schema.json` 承接，配置由 `scripts/validate_config.py` 校验。

默认使用 `git worktree list --porcelain` 的第一条主工作区，记录路径、branch、HEAD 和 dirty 状态；调用发生在 linked worktree 时不把未合入内容混入当前事实。Source HEAD 定义本轮读取快照，`targetBranch` 独立用于判断 Gate comparison commit 是否已进入目标分支；target Git commit 的验证细节由 `references/verify-runbook.md` 承接。
   - 常见误判：把 source HEAD 和 target branch commit 当成同一个锚点，会把“本轮看到了”误报成“已经进入目标分支”。

## Audit（只读）

1. 运行 `validate_config.py`、`contract_preflight.py` 和 `collect_sources.py`，再按需使用 `gate_recognition.py` 与 `make_item_id.py`；机械操作不改 stable docs、pending 或 package。
   - 常见误判：让 inventory 脚本顺便写入文档，会把只读 audit 变成未经批准的 apply。
2. 读取 optional pending（`pending-registry`）与 `records.done`，检查 terminal Gate Durable Deltas 是否已进入 `targetBranch` 的 gap-catching；pending 不抑制 gap-catching，done 是唯一机器去重依据。脚本只列 inventory，不决定 disposition。
   - 常见误判：把 pending 当作 gap-catching 的屏蔽开关，或把其他摘要当去重依据，会重复候选或漏掉 target branch 已吸收的 delta。
3. 对每项给出 `candidate | already-covered | conflict | no-delta`，引用 current code/tests/stable docs 的直接证据；代码能证明 current behavior，不能单独证明 product intent，发生冲突时报告 owner decision，不猜。
   - 常见误判：用代码现状替代 product intent，或在 conflict 时猜一个 disposition，会把实现事实伪装成业务批准。
4. item ID 使用 `<source-relative-path>::<delta-id>`，由来源提供稳定且可读的 delta ID。
   - 常见误判：用位置或临时序号作 ID，下一轮 source 变化后就无法安全批准、去重或回溯。
5. 输出 report 和 audit JSON；不修改 stable docs、pending 或 package。
   - 常见误判：audit 输出顺手改变 package，会让后续 apply 无法区分原始 evidence 与 audit 副作用。

Gate 不存在表示没有 Gate 证据；字段不完整、comparison commit 不可用或尚未进入 `targetBranch` 时不得形成 gap-catching/retirement 候选，但 pending-registry 仍可人工审计。Gate Durable Deltas 为 `none` 时不产生候选。

`contract_preflight.py` 委托当前 Impl-Package 状态引擎校验活动 package，因此间接执行 `state.json` 的 `formatVersion: "3.5"` 检查；3.4 package 必须先完成一次性迁移，backfill 不复制或另行维护格式版本。
   - 常见误判：backfill 自己维护一套 format/version 兼容层，会与当前状态引擎分叉，迁移前后的 package 也会得到不同结论。

## Apply

1. 先将 owner 对 report/CLI 输出的明确批准解析为精确 item ID；已展示且未变化报告的明确批量批准可直接解析，集合不明确时才询问。
   - 常见误判：把 report 中出现的所有 candidate 当成批准，会把 owner 尚未裁决的冲突一起写回。
2. 只修改批准 item 的 destination、对应 pending 项（如有）和 done record；gap-catching 不伪造 pending，不顺手处理同文件其他候选。
   - 常见误判：借 apply 机会清理同文件其他候选，会让实际写集超出批准 item ID，且无法回放哪一项触发了修改。
3. 移动、重命名、删除 stable docs 或退休 package 需要额外 destructive-apply 授权，精确到路径/package ID，不接受“这批全部”。
   - 常见误判：把普通 item approval 当 destructive authorization，会使不可逆变更超出 owner 明确范围。
4. 保持改动最小，随后运行 verify。
   - 常见误判：先扩大改动再验证，会让失败结果无法归因到批准 item，也无法安全重试。

## Verify

1. 运行 `verify_stable_docs.py`，检查显式路径、target Git commit、stable-doc 本地链接、audit shape 和 inventory；验证器只读；本轮 apply 在已批准 destination 内造成的链接、格式等机械错误，回到同一授权 apply 修复并重验。新增语义、destination、无关问题或破坏范围变化交回 owner。具体 target commit/version 与本地链接检查按需读 `references/verify-runbook.md`。

## Retirement

仅当 package Gate terminal、实现已到达 target branch、所有 durable delta 已吸收/关闭，且没有 inbound reference 或剩余活动材料时，才列为删除候选；删除仍需要 owner 明确授权。
   - 常见误判：只看到 Gate terminal 或代码已合入就列删除候选，会把仍被其他材料引用或尚未回刷的 durable meaning 一并丢掉。

先由本 skill 根据权威结果确定 audit/apply/verify/retirement 各阶段、计数、剩余项和是否收口；若 active skill catalog 存在 `talk-to-boss`，再用它组织这些已经确定的结论，不参与状态判断。可选 skill 缺失不阻塞流程。
