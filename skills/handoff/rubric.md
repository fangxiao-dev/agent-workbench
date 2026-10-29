---
target: skills/handoff
updated: 2026-10-28
---
## 原则

- [已确认] 主干承载共同要求，Impl-Package与普通任务的恢复方式按需读取reference；harness可恢复的信息由主控决定省略。
- [已确认] 固定保留尚未进入长青文档的session经验章节，遵循learn-lessons筛选，但不自动沉淀。
- [已确认] Skill只产出交接内容；会话创建由用户当次prompt单独指示，默认不落临时文件、不强制checkpoint或两阶段协议。

- [待验证] handoff 的阅读顺序应由下一 session 的首个判断及认知依赖决定，不固定以 snapshot、authority 或最新文档优先；snapshot 只在会改变下一动作时进入主线（证据: R2）
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

### R2 · 2026-08-11
- 修正「snapshot / authority 优先」— 用户明确指出新 session 应先从问题来源和采用摘要理解“现在的问题与 Probe 是什么”，再读 Decision/Spec 判断已完成和剩余问题。
- 采纳「形成通用方法论，不按场景逐个 patch」— 用户原话：做成通用的方法论，不要来一种情况 patch 一种。

### R3 · 2026-10-28
- 用户批准合并为handoff主干与两份模式reference，工程状态复用harness，普通任务只传必要背景与下一步。
- 用户明确要求固定携带尚未沉淀经验，并删除创建新session流程；已批准实施。
