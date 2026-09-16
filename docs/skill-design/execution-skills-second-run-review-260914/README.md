# 执行 Skill 套件的第二次实战复盘（2026-09-14）

上轮四项改进（`32bb5d7` / `d874a20` / `ccfb7bf` / `7a9eb7e`）落地后，用 09-12～09-14 的 5 个真实任务包、8 个 Codex session 做的第二次检验，这次包含两个设计阶段 session。

| 文档 | 内容 | 状态 |
| --- | --- | --- |
| [report.md](report.md) | 上轮四项的实战结果、16 条执行意图 × 7 切片判定、设计阶段留给执行阶段的四个问题、跨切片成本模式、用户纠偏汇总、规则加载核对、候选方向 | 调研报告，待 Owner 挑选候选方向 |
| [recommendations.md](recommendations.md) | 推荐优化范围：主项是让四条执行原则（角色≠载体、载体可有 worktree、先 foundation 后 fan-out、ready≠执行 dependency）在 dispatcher 里 stand out；另 6 项各给证据、现状文件行、改什么、验收；先查再定 3 项；本轮不做 5 项；5 个待 Owner 决定 | 待 Owner 挑选 |
| [implementation-results.md](implementation-results.md) | Owner 决定后的实施与验收：改了哪些文件、验证结果、未做项 | 已实施，未提交 |
| [workers/](workers/) | 8 个 worker 的原始取证报告（每条判定附 jsonl 行号）与共同分析框架 | 原文保留 |

一句话结论：规则版本没漂移、也基本读到了，但三件事在执行时没接住——formal 四轨在同一增量上反复整轮、evidence 批量登记能力闲置、「角色≠载体」要用户每个 session 重说；设计阶段留下的最大问题是 Ticket 依赖默认写成 `implementation:`。OF-03 / OF-04 在 KaiSpan session 复发，诊断纪律不变。
