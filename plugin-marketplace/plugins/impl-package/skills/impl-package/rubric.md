---
target: plugin-marketplace/plugins/impl-package/skills/impl-package
updated: 2026-08-06
---

## 已确认原则

- 只持久化会改变下一动作、阻止高影响 false PASS 或约束危险 mutation 的 current facts。
- D/S/P 保留为人类可读别名，但不绑定文件内容；Git commit ID 是唯一版本锚点。
- 文件和 evidence 只保存仓库相对路径；已知 artifact 使用固定目录或显式路径。
- Git 承担历史与回滚，不为审计完整性建立第二套状态。
- 小团队/个人改动按实际复杂度选择 Composition，不为完整感创建 Ticket 或 DAG；所有 active Attempt 仍有统一 Progress/Execution Record 层。
- 计划变化只复验实际受影响的 contract/artifact；只有行为、验收、Composition、安全或 mutation authority 实质变化时才扩大复验。
- Task 与 Ticket 保持两条状态轴；Task 完成不自动通过 Ticket。
- Gate 保存当前可读判决，旧判决由 Git 历史保留。

## 当前决策

### R12 · 2026-08-06

- 以“必要 current facts”为状态准入标准，删除只服务审计对账的状态与流程。
- 跨 session 比较使用批准/验证所在的 Git commit 和实际 diff。
- 活动 attempt 统一使用 `.impl-package/state.json` 的 `formatVersion: "3.4"`、attempt、tasks、tickets、resume 五个顶层字段。
- 根 `progress.md` 是完整恢复投影；Execution Record 与 Task Handoff 按 Attempt 分区但保持不同生命周期，不抽象成通用记录。
- 外围 review、handoff、preflight 和 stable-doc backfill 复用相同原则。
