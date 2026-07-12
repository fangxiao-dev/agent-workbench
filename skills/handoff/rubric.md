---
target: skills/handoff
updated: 2026-07-09
---
## 原则

- [待验证] handoff 应优先给当前 snapshot、权威 artifact 入口和 gate，不复写 plan/detail/test matrix（证据: R1）
- [待验证] 同目录 artifact 使用 base directory + filenames，只有跨仓库/临时目录/外部产物使用绝对路径（证据: R1）
- [待验证] 用户给出 focus 时，handoff 应主动收窄范围并排除无关历史（证据: R1）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-09
- 采纳「引用优先，避免复写已有 artifact 内容」— 用户原话：全部同意
- 采纳「区分 snapshot 和 plan detail」— 用户原话：全部同意
- 采纳「focus 参数必须收窄范围」— 用户原话：全部同意
- 采纳「路径粒度使用目录 + 文件名，减少重复绝对路径」— 用户原话：全部同意
- 采纳「增加推荐模板」— 用户原话：全部同意
- 采纳「敏感信息之外也做数据降噪」— 用户原话：全部同意
