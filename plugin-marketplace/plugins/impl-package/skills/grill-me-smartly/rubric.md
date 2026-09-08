---
target: plugin-marketplace/plugins/impl-package/skills/grill-me-smartly
updated: 2026-09-08
---

## 原则

- [待验证] 提问节奏直接复用 grilling，frontier 完整性通过持续跟踪和按协议分批保证。（证据: R1）
- [待验证] Questioner 与 Answerer 直接完成每轮事实问答并保存记录，主控后处理并向 Owner 汇报与提请裁决。（证据: R1）
- [待验证] 主控按设计主题跨轮整合规则、例外与冲突，Review 和 Apply 的结构由设计及目标文档决定，保留来源追溯。（证据: R2）
- [待验证] JSON ledger 是唯一权威状态，Markdown 只保存紧凑状态、计数、首 20 条待处理索引和命令；恢复按 summary→分页索引→选中详情执行。（证据: R3）
- [待验证] 批原件保持原路径和哈希不可变，详情解析失败不阻塞状态/索引；旧嵌入 JSON 只读，首次 mutation 备份原字节并原子发布新 JSON 后再生成索引。（证据: R3）
- [待验证] 直接答案与决策保留必要的前一版本供 history 查询，不能以通用事件日志代替；提问数量和跨轮整合不设配额。（证据: R3）

## 决策记录（滚动，最近 ≤5 轮）

### R3 · 2026-09-08
- Owner 批准 ledger slimming：`grill-<slug>.ledger.json` 为权威状态，`.ledger.md` 仅为短状态/计数/前 20 条 pending 索引和命令；提供分页 `list-questions` 与按需 `get-question`，不在 status 或索引中展开完整 JSON/QAs。
- 批原件保留原路径、哈希和引用；详情读取显式报告缺失/变更来源但不阻塞 status/index。旧嵌入 JSON 只读，首次 mutation 备份 `.legacy.md`，原子提交 JSON 后生成索引；索引失败不回滚 JSON，不做批量迁移。
- 直接答案/决策保留必要历史版本；新增 67 问 legacy、多轮整合和失败来源场景 eval，不把问题数量当作提问配额。

### R2 · 2026-09-08
- 用户要求“需要整合而不是抄写”，并明确批准实施《将问答整合为设计》计划：Ledger 保留问答，主控整合 Review，Apply 吸收到目标文档。
- 用户批准取消逐 Q 自动生成 Review；不设规则数或篇幅配额，保留重要边界、失败语义与未裁决冲突。

### R1 · 2026-09-08
- 采纳直接问答与记录下放 — 用户同意让两个 subagent 每轮自行对话，由主控后处理问答结果。
- 修正题数与追问限制 — 用户原话：“不做限制，其实说白了就是让 grilling 按自己本来的节奏提问，然后 answerer 只是先代替 owner 去做回答，最后由主控处理好了找 owner 汇报”。
