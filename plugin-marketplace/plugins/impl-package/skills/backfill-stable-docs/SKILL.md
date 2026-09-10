---
name: backfill-stable-docs
description: 当需要审计 durable knowledge delta、把 owner 批准的子集写入 stable docs、验证结果或退休已完全吸收的 implementation package 时使用。
---

# Backfill Stable Docs

把 implementation package 中仍有长期价值的事实回刷到稳定文档。流程分为只读 audit、显式批准后的 apply、只读 verify；三阶段不可混写。标准自动路径下，配置校验、worktree 基准、inventory/gap-catching、Gate 识别、item ID 与 verify 的机械部分一律走 `scripts/` 与 config schema；显式来源兼容分支只保留 disposition、授权、冲突和收口判断。

阶段顺序：

1. **配置与工作区基准**：先固定本轮配置、source HEAD 和 dirty 状态。
2. **Audit（只读）**：建立 inventory、gap-catching 和 disposition 候选，但不写入。
3. **Apply**：将 owner 对已展示且未变化报告的明确批准解析为精确 item ID 集合后写入。
4. **Verify（只读）**：在 apply 后检查路径、target commit、链接和 audit shape。
5. **Retirement（如适用）**：只有 package 已完全吸收且没有 inbound reference 时才列删除候选。

## 配置与工作区基准

标准包的仓库根 `.stable-docs-backfill.json` 或显式的仓库内配置必须列出 `targetBranch`、implementation 根目录、stable-doc 文件/目录、ignore 条目和 done record；pending 文件可选，默认为空。报告通过 CLI 输出或显式 output path 生成，不要求 reports 目录。所有路径是仓库相对路径；ignore 每项必须有 `path`、`owner`、`reason`，不接受 wildcard 或仓库外配置。路径拒绝规则由 `config/repository-config.schema.json` 承接，配置由 `scripts/validate_config.py` 校验。显式来源兼容分支以用户或 Manager 指定的来源为最小输入，不因缺失上述配置阻塞人工审计。

默认使用 `git worktree list --porcelain` 的第一条主工作区，记录路径、branch、HEAD 和 dirty 状态；调用发生在 linked worktree 时不把未合入内容混入当前事实。Source HEAD 定义本轮读取快照，`targetBranch` 独立用于判断 Gate comparison commit 是否已进入目标分支；target Git commit 的验证细节由 `references/verify-runbook.md` 承接。配置与基准提醒按需读取 [Audit Runbook](references/audit-runbook.md)；source/target、pending 与 done 的边界按需读取 [Source Selection](references/source-selection-and-pending-consumption.md)。

## 显式来源兼容分支

当 Project Knowledge Manager 或用户明确指定一项已完成工作、任务包或来源时，若没有 Gate、使用旧 schema 或包布局非标准，进入显式来源兼容分支。标准包仍优先使用现有配置和脚本自动发现；兼容分支只替代自动候选发现：

- 记录可取得的 source HEAD 与 dirty 状态，直接读取指定的 Decision、Spec、Plan、当前代码/测试和 canonical docs；
- 沿用下方的事实校准、disposition、冲突处理、apply、verify 与 retirement 边界；
- 不补造 Gate 或状态，不迁移 schema，不新增中间 JSON、manifest 或 package 记录。

缺少事实证据或设计与当前事实冲突仍须交给 owner 决策；兼容分支不把它们变成候选，也不绕过任何收口条件。

## Audit（只读）

1. 标准包运行 `validate_config.py`、`contract_preflight.py` 和 `collect_sources.py`，再按需使用 `gate_recognition.py` 与 `make_item_id.py`；显式来源兼容分支可直接读取指定来源，自动发现脚本缺失、报旧 schema 或不识别布局不构成阻塞；机械操作不改 stable docs、pending 或 package。
2. 标准包读取 optional pending（`pending-registry`）与 `records.done`，检查 terminal Gate Durable Deltas 是否已进入 `targetBranch` 的 gap-catching；pending 不抑制 gap-catching，done 是唯一机器去重依据。兼容分支仅在指定来源中已有这些记录时读取，不要求补齐。脚本只列 inventory，不决定 disposition。
3. 对每项给出 `candidate | already-covered | conflict | no-delta`，引用 current code/tests/stable docs 的直接证据；代码能证明 current behavior，不能单独证明 product intent，发生冲突时报告 owner decision，不猜。
4. 标准包 item ID 使用 `<source-relative-path>::<delta-id>`，由来源提供稳定且可读的 delta ID；兼容分支在现有报告中使用同样可追踪的来源路径和 delta 标识，不要求包 schema 提供字段。
5. 标准包输出 report 和 audit JSON；兼容分支复用已有输出形状（如有），不新增中间 JSON、manifest 或 package 记录；任何路径均不修改 stable docs、pending 或 package。

审计阶段的判断提醒按需读取 [Audit Runbook](references/audit-runbook.md)、[Audit JSON](references/audit-json-contract.md)、[Source Selection](references/source-selection-and-pending-consumption.md) 与 [Constraint Routing](references/constraint-extraction-and-routing.md)。

在标准脚本路径下，Gate 不存在表示没有 Gate 证据；字段不完整、comparison commit 不可用或尚未进入 `targetBranch` 时不得形成 gap-catching/retirement 候选，但 pending-registry 仍可人工审计。Gate Durable Deltas 为 `none` 时不产生候选。显式来源兼容分支不要求 Gate 证据，但仍须按指定来源和 current evidence 人工形成候选并完成同样的校准。

`contract_preflight.py` 在标准脚本路径下委托当前 Impl-Package 状态引擎校验活动 package，因此间接执行 `state.json` 的 `formatVersion: "3.5"` 检查；旧 schema 在兼容分支中只作为审计信号，不要求迁移，backfill 不复制或另行维护格式版本。

## Apply

1. 将 owner 对 report/CLI 输出的明确批准，或对指定来源的明确“回刷”授权，解析为本轮审计产生的精确 item ID；来源或集合不明确时才询问。
2. 只修改批准 item 的 destination、对应 pending 项（如有）和 done record；gap-catching 不伪造 pending，不顺手处理同文件其他候选。
3. 移动、重命名、删除 stable docs 或退休 package 需要额外 destructive-apply 授权，精确到路径/package ID，不接受“这批全部”。
4. 保持改动最小，随后运行 verify。

Project Knowledge Manager 的明确“回刷”调用或用户明确请求本次“回刷”，可作为本轮审计候选的非破坏性 apply 授权；该授权仍不包含移动、重命名、删除、retirement 或解决语义冲突。明确 `audit-only` 的调用始终只读。

Apply 的批准集合、写集与 destructive 边界提醒按需读取 [Apply Runbook](references/apply-runbook.md)。

## Verify

1. 运行 `verify_stable_docs.py`，检查显式路径、target Git commit、stable-doc 本地链接、audit shape 和 inventory；验证器只读；本轮 apply 在已批准 destination 内造成的链接、格式等机械错误，回到同一授权 apply 修复并重验。新增语义、destination、无关问题或破坏范围变化交回 owner。具体 target commit/version 与本地链接检查按需读 `references/verify-runbook.md`。

## Retirement

仅当 package Gate terminal、实现已到达 target branch、所有 durable delta 已吸收/关闭，且没有 inbound reference 或剩余活动材料时，才列为删除候选；删除仍需要 owner 明确授权。
Retirement 的终态、目标分支、delta 吸收和入站引用核对按需读取 [Package Retirement Runbook](references/package-retirement-runbook.md)。

先由本 skill 根据权威结果确定 audit/apply/verify/retirement 各阶段、计数、剩余项和是否收口；若 active skill catalog 存在 `talk-to-boss`，再用它组织这些已经确定的结论，不参与状态判断。可选 skill 缺失不阻塞流程。
