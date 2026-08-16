# Slow-path 试运行读数说明

本页替代原来为“常驻 bookkeeper 负责日常记账”设计的 R1–R4。原读数及其阈值现在作废：日常 evidence、checkpoint、state transition 和 Gate 已由主 session 直接调用 CLI，正常写入不会产生 bookkeeper receipt；继续用旧分母会把 fast path 混入 slow path，既测不出异常处理质量，也无法比较真实的关键路径成本。

当前数据源仍是 `<package>/execution/<attempt>/bookkeeper-receipts.jsonl`，但只记录 slow-path 调用；由 bookkeeper 每次异常回执追加一行，格式见 [`role.md`](../../../plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/references/role.md) 更新循环第 6 步。需要计算耗时和派发成本时，再对照 `execution/<attempt>/trail.jsonl` 中的 dispatch/result 事件、主 session 执行的 CLI 结果和同一 revision 的 `package validate`。未来 session 不需要依赖聊天记录或 session id。

## 旧 R1–R4 的处置

旧 R1（定位错误率）、R2（握手频率/阻塞时长）、R3（越界写入次数）和 R4（落盘漏记率）都不再作为 slow path 的正式读数。它们假设每次 package 写入都会经过一个能独占物理写入的常驻 agent；这一假设已被本次 practicality 复盘否定。旧 rollout 中没有可用的 receipt 配对，且其 93.3% 的结构化目标本应走 CLI，因此旧读数最多保留为历史背景，不能迁移成新形态的样本或阈值。

## Slow path 的四个新读数

| # | 读数 | 怎么算 | 指向什么 |
| --- | --- | --- | --- |
| R1 | **触发准确率** | slow-path 调用中确实属于证据矛盾、恢复、部分写入补齐、跨 stage 对账或异常排查的次数 ÷ slow-path 总调用数；把 routine fast-path 误路由计为 false positive | 触发边界是否清楚，是否又把日常记账塞回 agent |
| R2 | **异常闭环率** | slow path 返回结构化对账/修复输入后，主 session 能在一次调用内接受、直接执行 CLI 并通过 focused validation 的次数 ÷ slow-path 总调用数；重复派发、二次解释或仍需人工裁决的单独计数 | slow path 是否真的减少异常处理往返，而不是制造新的握手 |
| R3 | **边界违例次数** | 记录 bookkeeper 直接修改 `state.json`、越出本次异常范围，或主 session 依据其建议写入不属于 package 的路径的次数；按实际路径和 diff 交叉校验 | single-writer、package scope 和修复建议边界是否守得住；任一 confirmed violation 都是阻断信号 |
| R4 | **异常处理成本** | 对每次 slow path 记录 dispatch 到 result 的 wall time、`dep=true` 的关键路径阻塞、spawn/wait/retry 次数，并与同批直接 CLI 的调用数和验证成本对照；报告中位数和 p95 | slow path 的知识收益是否值得其冷启动、等待和同步成本 |

R1–R3 以 receipt、trail、state diff 和 validation 交叉确认，不把“聊天里说过”当作事实。R4 不把 `dep=false` 的后台处理算成主线阻塞，但要保留总耗时，避免把异步成本完全隐藏。

## 样本量与阈值

旧的 `R1 > 20%`、`R1 < 10%`、`R2 dep=true > 50%` 和 `R4 > 30%` 阈值全部退休，不适用于按需 slow path。新试运行至少收集 20 次 slow-path 调用后再下正式结论；不足 20 次只报告计数、具体异常和定性反馈。R3 的边界违例保持零容忍；R1、R2、R4 的业务阈值须在下一轮试运行开始前单独批准，不能根据既有结果事后倒推。
