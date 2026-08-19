---
name: backfill-stable-docs
description: 当需要审计 durable knowledge delta、把 owner 批准的子集写入 stable docs、验证结果或退休已完全吸收的 implementation package 时使用。
---

# Backfill Stable Docs

把 implementation package 中仍有长期价值的事实回刷到稳定文档；流程分只读 audit、显式批准后的 apply、只读 verify，三阶段不可混写。配置校验、worktree 基准、inventory/gap-catching、Gate 识别、item ID 与 verify 全部由 `scripts/`（validate_config、contract_preflight、collect_sources、gate_recognition、make_item_id、verify_stable_docs）与 config schema 强制；机械操作一律走脚本，仅保留以下判断。流程收口时本 skill 依权威结果确定各阶段结论；若 active skill catalog 存在 `talk-to-boss`，由它组织呈现，不参与状态判断。

**Audit（只读）**：对每项给出 `candidate | already-covered | conflict | no-delta` 并引用 current code/tests/stable docs 的直接证据；Gate 缺失、字段不完整或 `none` 不产生候选；pending 不抑制 gap-catching，done 是唯一机器去重；disposition 是判断，脚本只列 inventory。

**Apply**：只 apply owner 明确批准 report/CLI 输出中的精确 item ID，只改批准 item 的 destination、对应 pending 与 done record，不伪造 pending、不顺手处理同文件其他候选；移动/重命名/删除 stable docs 或 retirement 需额外 destructive-apply 授权（精确到路径/package ID，不接受"这批全部"）；保持改动最小，随后 verify。

**Verify**：运行 `verify_stable_docs.py`；失败只报告，不自动修复。

**Retirement**：仅当 package Gate terminal、实现已到 targetBranch、所有 durable delta 已吸收/关闭、且无 inbound reference 或剩余活动材料时列为删除候选；删除仍需 owner 明确授权。
