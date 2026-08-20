---
name: dev-with-track
description: 当批准 implementation plan 正式开始或者恢复执行、选择下一 actionable unit、记录证据、处理返工失效、分流 findings 或写 Gate 时使用；新 package 以 Ticket 为执行轴，不重新定义 Decision/Spec/Plan/Ticket。
---

# Dev With Track

执行控制、finding 分流、验证与 Gate 的语义判断归本 skill；日常物理写入由主 session 直接走现有语义 CLI（SATISFIED 带 revision/environment、escape 带 subject/deviation/reason、轨迹只追加等校验由 CLI 强制），worker 只返回结构化 evidence 不直接写 state；只有证据矛盾、恢复、对账或异常排查才调 `/impl-package:execution-boundaries` slow path，它不成为第二个 state writer。

恢复：以处境注入为起点，读 progress.md 的 current Attempt/blocker/active checkpoint/next action/Gate，不读 state.json 全文，只沿当前动作读必要 Ticket 切片；initial bundle approval 与实际 diff 一致才继续同一 package。首次派发声明 Evidence Lane Contract 的 Ticket 前核 execution-preflight 四项 lane（target 唯一、端口 owner、库分离、cleanup owner），每 Ticket 首次激活一次，子代理不得判 lane 生死。循环 Investigate→Decide→Implement→Evaluate：每步落地前先看注入的处境与合法动作，仅作导航参考——Investigate 确认违约边界与权威来源；Decide 由现有 D/S 唯一裁决，存在多个合理业务结果才请求 owner；Implement 只修已证实、当前可归责范围；Evaluate 用最便宜且忠实的证据，昂贵重跑须有新修复、环境变化或决定性观察目标。步骤 1/3 的策略由 `/impl-package:subagent-driven-development` 形成，本 skill 只消费其结果；写入与派发无硬依赖时可并行发出。

状态与 checkpoint：状态变化、证据、judgment、checkpoint、gate 走语义 CLI；checkpoint 时机为 BLOCKED、retry、跨 session/owner、交接，只记下一动作与恢复证据，不授权派发、不释放依赖；长期判断写 judgment。证据必须是存在的仓库相对路径且足以解释状态变化；可从 Git/state 推导的事实不重复写入 Execution Record。

Escape 与 Gate：处境表未覆盖或偏离渲染建议时按判断行动，但每次 escape 写一行 kind=escape 轨迹（subject/deviation/reason），renderer 不是阻断器。Gate 三态：blocked 保持 active 并记录 gap/next action；pass 须全部 Ticket/验证/review/manual acceptance/finding closure 满足；fail|defer 如实终结，后续实现转 patch Attempt。terminal Gate 必做 Stage 7（记录 Durable Delta 及 _pending.md/truth pointer，或 --no-durable-delta-reason 说明无增量）并冻结 state/active checkpoint/Execution Record；长任务先落盘再输出叙述，断连后从幂等事实恢复，收口叙述工具（若存在）只组织已定事实、缺失不阻塞。
