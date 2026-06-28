# [Project / Slice] 进度记录

状态：[活跃 / 暂停 / 已关闭]
创建：[YYYY-MM-DD]
对应 roadmap：[path-or-link]
配套 findings：[findings.md](findings.md)
配套 gate：[gate.md](gate.md)

本文只记录 roadmap 走到哪一步、gate 状态和下一步；不替代具体 issue、PR、实现计划或截图证据。

## 当前阶段

当前处于：[Phase A - Preview Alignment / Phase B - Real Route Absorption / Backlog]

[用 1-2 句话说明本阶段目标。]

## 最新进度快照

- [YYYY-MM-DD] [已完成/已确认的事实]
- [YYYY-MM-DD] [已建立的 preview/harness/evidence 路径]
- [YYYY-MM-DD] [验证命令和结果]
- [YYYY-MM-DD] [人工 review 状态]

## Gate 状态

- [ ] Scope：目标 route / component / surface 已明确。
- [ ] Data safety：fixture-only，无生产数据，无外部 mutation。
- [ ] Preview evidence：desktop + constrained viewport 证据已保存。
- [ ] Findings：截图 / 测试 / review 暴露的问题已记录。
- [ ] Verification：最小自动验证已通过，或阻塞原因已记录。
- [ ] Manual review：人工确认“第一眼看得懂”或明确延后。
- [ ] Follow-up：后续问题已拆成 checklist / issue / backlog。

当前结论：[不能关闭 / 可进入下一阶段 / 已关闭]

## 下一步

1. [下一步动作]
2. [下一步动作]
3. [下一步动作]

## 记录规则

- 每次推进 phase 或 gate 时更新本文。
- 新发现写入 `findings.md`。
- 关闭切片或阶段时更新 `gate.md`。
- 如果验证失败或跳过，写明原因和后续动作。
