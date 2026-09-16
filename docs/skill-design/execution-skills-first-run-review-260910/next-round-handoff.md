# 交接：执行 Skill 套件下一轮优化的起点

日期：2026-09-14。给新 session 的交接材料：到目前为止改了什么、什么已确认、什么还开着、什么已否决。末尾附启动 prompt。

## 1. 三轮的时间线

| 轮次 | 日期 | 做了什么 | 落点 |
| --- | --- | --- | --- |
| 打薄 | 09-06 → 09-08 | 删 22 个 fact 声明入口、bookkeeper 角色、Ticket 激活 preflight、自动换 session；Gate 按 Attempt 归属 | `a0a33b2`…`cb906e6`；[决策记录](../impl-package-astra-thinning-decisions-260906.md) |
| 合并 | 09-08 | Dispatcher 吸收 SDD；投影四分区 `blocking/runnable/withheld/in_flight`；候选清单建了又删（+259/−1212，净减 953） | `3e89ece` → `dd6ed27` → `6bd78a4`；[提案](../dispatcher-dev-with-track-sdd-consolidation-proposal-260908.md) |
| 首次实战复盘 | 09-10 | 两个真实任务包、5 个 session、34k 行 rollout 检验设计；Codex 独立审核；三轮往复收敛为四项 | `3672f78` → `1ddb1f2` → `d25c584`；本目录 [report](report.md) / [second-opinion](second-opinion-codex.md) / [converged](converged-recommendation.md) |
| 四项落地 | 09-10 → 09-13 | 批量 evidence、下游兼容性验收、delta review 衔接、有界诊断 | `32bb5d7`、`d874a20`、`ccfb7bf`、`7a9eb7e`；[实施结果](implementation-results.md) / [诊断](execution-behavior-diagnosis.md) |

## 2. 实战检验确认了什么

**确认对的**（5/5 切片、零反例）：Dispatcher 单一执行入口、候选无需预登记、outcome 按 dispatch 归属、删 22 个 fact 入口、删 bookkeeper、删自动换 session。**本批没有找到确凿的「砍错了」案例**——这是对打薄那轮最强的肯定，新一轮不要再讨论恢复旧机制。

**唯一系统性失效**：换 worker 的依据。5 切片零干净通过；最硬的证据是 B2 主控读完最新 Dispatcher、书面承诺不按 timeout 中断（`L1244`），1.5 小时后照样按「超过 30 分钟」中断（`L3022`）。**规则写了、读了、承诺了，长 session 里仍失效。** 这条已诊断但未解决（OF-03）。

**从未被检验的设计**：#12「handoff 保留在途 worker 上下文」——三次 handoff 都恰好发生在无 worker 在途时。`e150587` / `8d21780` 至今零实战证据。

**成本线索**（经 Codex 审核后降级为线索，不是已证实的可省时间）：重复登记（两次独立用户纠偏 `L13303` / `L4414`）、验收边界遗漏（B2 `L3897` 立项时漏了 training 是 DatasetVersion 的下游消费者）、环境/凭据没先盘点、便宜命令重复确认同一状态。

## 3. 四项落地后的现役状态

| 项 | 现在的行为 | commit |
| --- | --- | --- |
| Evidence 批量登记 | `evidence add` 接受单对象或数组；数组全部合法才一次保存 state、一次刷新投影；非法批次不部分写入。claim / revision / environment / Gate 语义**不变** | `32bb5d7` |
| 下游兼容性验收 | req-align 的 Spec 范围识别步骤区分「修改范围」与「兼容性验收范围」，沿实际受影响的既有消费者到可观察终态；无新矩阵、无新 Ticket 流程 | `d874a20` |
| Delta review 衔接 | 每个代码 return 仍有独立审查；无 formal requirement 时一名 reviewer，有则走 owning workflow；return 原因分流（已知未实现 / 证据缺口 / 真实缺陷）归 dev-with-track；terminal-final 启动条件唯一落在 do-review | `ccfb7bf` |
| 有界诊断 | 四类表现各一代表，真实 renderer/准入检查全部通过（`EVIDENCE_SUFFICIENT`）；**历史主控为何做错动作**无法从可恢复材料复现（`EVIDENCE_GAP`）；未新增 hook | `7a9eb7e` |

验证：`tests/test_impl_package_state.py` 67 passed；35 项直接合同 passed；四个 Skill validator valid；19 条记录单条/批量对照完全一致。版本仍 `0.4.2`，**未安装、未发布**——安装缓存与仓库源码不一致过一次（埋了 DSH 入口失效），这是单独决定。

## 4. 开着的问题（新一轮的种子）

诊断留下 4 个 open finding，都是「现象已确证、机制未解释」：

| OF | 现象 | 已排除 | 还缺什么 |
| --- | --- | --- | --- |
| OF-01 已知候选被忽略 | B2 `L2891` 投影已列 TKT-03 investigate 为 runnable，主控派了 TKT-02 后连续 wait、没再 render | renderer/准入没有全局 wait（隔离检查通过） | 主控为何把 TKT-03 的实现前置误套到调查 |
| OF-02 关联候选未进上下文 | B3 用户 `L1638` 给出 #301–#303，首次读取因 worktree 无 `glab`/凭据失败 | 投影按设计不从外部 Issue 建候选（输入边界，非漏算） | 主控读取外部 Issue 线索的入口；worktree 与主工作区凭据分层 |
| OF-03 无正当理由中断 | 上文 `L1244` → `L3022` | 隔离投影支持等待语义 | 模型在长上下文里的实际 interrupt 选择无法复现 |
| OF-04 收尾误作主线前置 | B3 `L3344`–`L3730` backfill 挡住 Issue 发布，用户 `L3719` 纠偏 | 投影只给 durable-delta/Gate 局部动作，不决定外部顺序 | 主控的优先级/交付边界判断机制 |

**诊断的明确结论**：下一轮若要推进这四条，**先要有可重放的长上下文/worker 状态和主控实际工具选择**；基线未在该链路重新变红前，不做「动作前提示」与「额外投影注入」的效果声明。这是 Codex 与 Claude 双方确认的实验纪律，不要绕过。

## 5. 已否决、不要重提的

- 恢复 15/30 分钟观察门槛（删掉后行为没变，说明问题不在门槛）
- 恢复候选清单 / 22 个 fact 入口 / bookkeeper / 自动换 session
- 恢复或调整 do-review Loop 十轮上限（从未删除；本批最多 7 轮，没触及）
- 通用 `PreToolUse` 参数校验 hook（约 15 次参数错误跨四类，一个校验器覆盖不了；改具体入口反馈）
- 全 lane 同一 comparison head 的提交门槛（resource-isolation 已覆盖，加门槛只扩大串行）
- E4「全量检查单一 owner」落地（次数不等于浪费，B3 五次全量测试 pass 数 2059→2592，每次都在验新状态）
- backfill 全局不阻塞条款（规则已存在，属于 OF-04 诊断对象）

## 6. 方法论教训（这轮复盘自己犯的错）

Codex 审核指出 8 处错误，5 处事实、3 处方法，全部成立。类型只有一种：**从可复现的次数/措辞直接推结论**——命令次数当浪费、同一个词当机制复活、「规则都写了」当同一根因、不可证伪的实验当验证路径。新一轮做分析时：次数是线索不是结论；判定「违反」要看动作内容不看关键词；合并调查可以、预判共同根因不行；基线复现不了先查缺失条件、再报证据不足，不跳干预实验。

## 7. 在途、未提交的工作（另一 session）

工作区当前有未提交改动：[dispatcher/SKILL.md](../../../skills/dispatcher/SKILL.md) 新增「Implementer executor」段——`implementer` 保留为逻辑角色，前后端用具象 `backend-worker` / `frontend-worker`（`agents/*.toml`，gpt-5.6-terra），契约只读、冲突返回 `CONTRACT_CHANGE_REQUEST`；配套 `tests/test_dispatcher_contract.py`、`install_codex_agents.py`。**新 session 启动前先 `git status` 确认这批是否已提交**，不要和它冲突。

## 8. 新 session 启动 prompt

```text
先读 docs/skill-design/execution-skills-first-run-review-260910/next-round-handoff.md，这是上一轮的交接：三轮改造的 commit、实战检验确认了什么、四项落地后的现役状态、4 个 open finding（OF-01..04）、已否决清单和方法论教训。按需 refer 里面的 commit。

启动前 git status 确认工作区是否有另一 session 未提交的 Implementer executor 改动（dispatcher/SKILL.md、agents/*.toml），不要和它冲突。

本轮目标：[在这里写本轮要优化的方向]

约束：
- 不重提第 5 节已否决的项
- 涉及 OF-01..04 的，遵守诊断文档的实验纪律：先要可重放的长上下文/worker 状态与主控实际工具选择；基线复现不了先查缺失条件，仍不足报证据不足，不跳干预实验
- 分析时次数是线索不是结论；判定违反看动作内容不看关键词
- 版本 0.4.2 与安装/发布是单独决定，改 runtime 后不自动 bump
- 调研派 /call-codex（gpt-5.6-luna + effort max，允许 subagent，分阶段落盘）；先固定判定清单再 fan out
- 汇报按关心点组织，贴可点路径与 commit
```
