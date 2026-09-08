---
target: plugin-marketplace/plugins/impl-package/skills/grill-me-smartly
updated: 2026-09-08
---

## 原则

- [待验证] 提问节奏直接复用 grilling，frontier 完整性通过持续跟踪和按协议分批保证。（证据: R1）
- [待验证] Questioner 与 Answerer 直接完成每轮事实问答并保存记录，主控后处理并向 Owner 汇报与提请裁决。（证据: R1）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-09-08
- 采纳直接问答与记录下放 — 用户同意让两个 subagent 每轮自行对话，由主控后处理问答结果。
- 修正题数与追问限制 — 用户原话：“不做限制，其实说白了就是让 grilling 按自己本来的节奏提问，然后 answerer 只是先代替 owner 去做回答，最后由主控处理好了找 owner 汇报”。
