# W6 分析报告 —— tinymlops #304 Edge Agent / Harness 主执行

rollout: `C:/Users/Xiao/.codex/sessions/2026/09/12/rollout-2026-09-12T21-39-10-01a09721-7e95-7dd3-8dc6-0de5fa34888e.jsonl`（7047 行）
cwd: `D:\CodeSpace\dbe_jp\tinymlops-team-server-project`（L8 turn_context 确认，全程未变）

任务包确认：这就是 #304。L10 `create_thread` 的 inbound 消息明确写「这是 GitLab #304 Physical Rover Edge Client Foundation 的全新独立 local session」，权威入口 `docs/implementations/2026-09-12-physical-rover-edge-client-foundation/progress.md`，worktree `C:\Users\Xiao\.codex\worktrees\3617\tinymlops-team-server-project`，来源 thread `01a09693-c83f-7930-b0fd-238c27226854`（即设计 session）。本 session 是纯**执行阶段**：L10 明确「本轮仅做 anchor 检查，不开始实现」，随后 L88 的第二条 inbound 消息（`send_message_to_thread`）才正式授权接管实现。全程未见设计阶段动作（无 req-align/impl-planning/to-tickets 相关 shell 或 spawn）。

---

## 1. 会话事实（先算数字，再写判断）

### 时间跨度

- 首条事件：L1 `2026-09-12T19:39:14.168Z`
- 末条事件：L7047 `2026-09-13T08:53:55.755Z`
- 总墙钟跨度：约 13h14m41s
- **但主控在 L7000（`2026-09-13T02:38:46.228Z`）已完成收尾汇报**「Gate 已正式 PASS...任务 closed，无需 owner 决策」，随后到 L7007（`2026-09-13T08:53:03.835Z`）之间**零事件**——这是用户离开约 6h14m 的空档，不是主控在等待任何东西。真正的主控活跃区间是 L1–L7000，约 `19:39:14 → 02:38:46`，**6h59m32s**。
- `compacted` 事件 2 次：L2407（`22:16:35.698Z`）、L6972（`02:38:10.679Z`，紧跟在收尾提交之后）。

### user turn / assistant message 数

- `response_item.message` role 统计：`assistant` 195 条，`user` 9 条（原始计数），`developer` 8 条。
- 9 条 `user` 消息中，L8（`<recommended_plugins>` 系统自动注入）与 L2168（`<environment_context>` 日期/时区跨天自动注入）是**系统消息不是真人输入**；真正的人类 push back / 指令共 **7 条**：L188、L665、L989、L1537、L1630、L7011、L7041。

### 协作工具调用次数

| 工具 | 次数 |
| --- | --- |
| `spawn_agent` | 54 |
| `wait_agent` | 119 |
| `send_message` | 18 |
| `followup_task` | 40 |
| `list_agents` | 15 |
| `wait` | 3 |
| `interrupt_agent` | 0 |
| `request_user_input` | 0 |
| `create_thread`（本 session 主动发起） | 0（仅在 L10 被动接收 1 条 inbound） |
| `send_message_to_thread`（本 session 主动发起） | 0（仅在 L88 被动接收 1 条 inbound） |

`send_message` 18 次经核对均为 `collaboration` 命名空间对 sub-agent 的消息（不是跨 session 通信）。

### spawn 的 agent_type 分布（明文，`spawn_agent.arguments.agent_type`）

| agent_type | 次数 |
| --- | --- |
| `backend-worker` | 27 |
| `review-track-spec` | 6 |
| `luna-worker` | 9 |
| `review-track-code` | 4 |
| `review-track-safety` | 4 |
| `review-track-standards` | 3 |
| `explorer` | 1 |
| `frontend-worker` | 0 |
| 默认（与主控同 profile） | 0 |

54 次全部落在上述 7 个显式类型里，没有一次是"默认同 profile"派发。`frontend-worker` 为 0 次有明确上下文依据（见 §2 第 2 条）：L193 主控自述「TKT-01 是 Python 生产 Edge Client、没有 frontend write-set」——这是纯后端/嵌入式包，本 slice 无前端场景，不是遗漏。

`review-track-*` 4 种是 do-review 内部四轨审查子代理（Track A/B/C/D），不是用户清单里点名的 impl/fix/frontend/backend/grok 五类角色，但同样受"角色可并行多个"约束，见 §2 第 1 条。

### followup_task 复用同一 agent 次数分布（按目标 task_name 精确匹配 spawn_agent 输出）

| task_name | followup 次数 | 存活时长（spawn→最后一次 FINAL_ANSWER） |
| --- | --- | --- |
| `/root/terminal_fix_harness` | 6 | L4006→L6264，8018s（2h13m） |
| `/root/terminal_review_a` | 5 | L3851→L6834，10615s（2h57m） |
| `/root/terminal_review_b` | 5 | L3857→L6845，10623s（2h57m） |
| `/root/terminal_review_c` | 5 | L3863→L6853，10623s（2h57m） |
| `/root/terminal_review_d` | 5 | L3869→L6861，10620s（2h57m） |
| `/root/f035_closure` | 3 | L5389→L6410，4030s（67min） |
| `/root/tkt01_backend_implementation` | 2 | L357→L1004，2380s（40min） |
| `/root/tkt01_evidence_edge_client` | 2 | L1265→L1719，1556s（26min） |
| `/root/tkt01_evidence_runtime` | 2 | L1277→L1709，1492s（25min） |
| 其余 5 个 agent | 各 1 | — |
| 其余约 40 个 agent | 0（一次性完成） | — |

最长寿命、被 followup 最多的是 `terminal_review_a/b/c/d`（do-review 终轮四轨）与 `terminal_fix_harness`——它们贯穿了 23:35→02:32 的整个"找问题→修→重验"收尾循环，见 §4。

### 并发度（spawn→最后一次 FINAL_ANSWER 区间做 sweep line）

- 活跃 agent 区间总覆盖时长：24518s（约 6h49m，覆盖了绝大部分主控活跃期）
- 最大同时在途 agent 数：**7**
- 并发时间分布：0 个在途 9.8%、1 个 26.4%、2 个 7.8%、3 个 5.9%、4 个 11.5%、5 个 13.2%、**6 个 22.4%**、7 个 2.9%
- 换言之：约 55% 的活跃时间里同时有 ≥4 个 agent 在途，多数时段不是串行单 worker。

### 等待占比（连续只有 wait_agent/list_agents/wait、无新 spawn_agent、主控自己没有 EXEC 动作的时间段）

- 累计纯等待时间：**5297s（88.3 分钟）**，共 58 段
- 占主控活跃期（6h59m≈25172s）约 **21%**
- 最长单段：457s（L2137–L2186，`21:55:06.899Z→22:02:44.019Z`），其次 411s（L1978–L2015）、379s（L3087–L3182）
- 说明：这是纯技术口径的"没有新动作"窗口，多数对应"多个 worker 并行跑长测试，主控确实无事可做只能等"，不是主控偷懒；真正的问题不是等待本身，而是有没有在等待期间漏派可以并行的独立工作（见 §2 第 7 条、§4）。
- 夜间 09-12 23:00→09-13 08:00 的活动：23:00–02:38 主控持续在跑收尾循环（do-review 终轮四轨 + terminal_fix_harness 反复 followup，详见上表和 §4）；02:38–08:53 是纯**用户空档**（零事件），不计入等待占比。

### shell 命令分类计数（共 413 条独立命令，来自 exec 里的 `tools.exec_command({cmd:...})`）

| 分类 | 次数 |
| --- | --- |
| impl-package 语义 CLI（`impl_package_state.py`/`situation.py`/evidence/ticket/trail/gate/package） | 198 |
| git | 95 |
| 其他（读文件、grep、PowerShell 数据整理等） | 87 |
| pytest/测试 | 27 |
| 容器/服务（关键词命中多为 `server/tests` 路径误命中，本 slice 未见真实 docker/nats 进程启停，未细究） | 6（存疑） |

evidence 登记：**单条 39 次（100%），批量数组 0 次**。核实方式：所有 `evidence add` 调用都是 PowerShell `foreach($row in $rows){ ...; $event|python $state ... evidence add }` 形式——即使 `$rows` 本身是数组，也是逐条构造单个 JSON 对象、逐次单独调用 CLI 子进程；从未把整个数组一次性传给 stdin。`impl_package_runtime/engine.py:1195-1229`（`command_evidence_add`）明确支持 `payload` 为 JSON 数组时一次性批量写入（`is_batch=True`，一次 `_write_json` + 一次 `_refresh_projections`），但这批 19 次相关 exec 调用（L384/1890/1909/3680/3686/3701/3717/3724/3731/4046/4086/4461/4716/4729/5280/6032/6221/6424/6915）没有一次用上，累计 wall time 373.0s。详见 §2 第 6 条、§4、§7。

### 重复执行（归一化后 ≥3 次的命令）

| 命令模式（归一化） | 次数 | 行号样本 | 输入是否变化 |
| --- | --- | --- | --- |
| `python situation.py render --package <X> \| Select-String ...` | 34 | 2873,2901,2915,... | 是——每次 `--validation-result`/`Select-String` pattern 不同，是常规状态核对，不算浪费 |
| `Get-Content -Raw -LiteralPath <X>` | 14 | 16,16,49,390,... | 是，读不同文件 |
| `git rev-parse HEAD` | 12 | 2590,3219,3397,... | 命令本身不变，但服务于不同时刻的状态核对，不是同一次查询重复问 |
| `$trailEvent=@{...dispatch...}\|...trail append` | 12 | 3418,3844,4322,... | 是，字段值（dispatch_id/candidate_id等）逐次不同 |
| `Get-Content -Tail <X>` | 11 | 2471,2887,3635,... | 是，读不同日志/文件尾部 |
| `ticket satisfy TKT-<X> --expect PENDING ...` | 11 | 4191,4522,4556,... | 是，不同 ticket/revision，但**这批本身就是 TKT-01 反复因终局 HEAD 前移被打回又重新 satisfy 的证据**，见 §4 |
| `foreach($p in evidenceIndex.<ticket>...){evidence add}` | 10 | 4473,4529,4817,... | 是，不同 revision——但结构完全相同，是"重新登记全部 claim"这一模式的重复出现，本身就是 §4 的核心证据 |
| `python -m pytest -q server/tests`（全量套件） | 5 | 2653,3445,4349,... | 是——每次验的是不同 HEAD 的新状态（本轮次全量重跑，pass 数持续增长），符合"E4 全量检查单一 owner"已否决结论，不列为浪费 |
| `git add ...harness/provisioning... && git commit -m <X>` | 5 | 4914,5342,5543,... | 是，不同文件/commit message |

**方法论口径**：按补充要求，本报告不为 pytest/环境/Docker/UI 手测等业务验证内容建表计时；上表里的重复命令均只服务于"调度行为本身是否绕路"的判断，不是给业务验证计数。

---

## 2. 清单 A 逐条判定 · 执行阶段设计意图

**1. 角色≠载体：同一角色按需派多个并行 worker，而不是每角色一个**
判定：**已执行**。证据：TKT-02 fix 阶段 L2977/L2992/L3000/L3008/L3023（`22:45:08→22:46:26`）5 秒级密集并行 spawn 了 5 个 `backend-worker`（`tkt02_fix_foundation`/`_deployment`/`_knn`/`_telemetry`/`_callers`），各自独占能力域；TKT-01 evidence 阶段 L1265/1271/1277（`20:56:55→20:57:18`）并行 3 个 `backend-worker`。do-review 四轨（review-track-code/standards/spec/safety）在 L689/695/701/707、L2627/2633/2639/2645、L3851/3857/3863/3869 三轮里每轮都是 4 个并行子代理。

**2. 派发用了正确 profile：默认 luna-worker，前后端用对应 worker，没有默认同 profile 派发**
判定：**已执行**。luna-worker 9 次全部用于"通用调查/验证/finding-closure"（如 L194 `tkt01_boundary_investigation`、L1067 `tkt01_finding_closure`）；backend-worker 27 次全部是业务实现/修复；本包无前端 write-set（L193 主控自述），`frontend-worker` 0 次不是遗漏；54 次 spawn 无一次落在"未指定/默认同主控 profile"。

**3. ready≠dependency：下游 ticket 在上游未验收时已提前调研/部分开工；先分析 foundation/seam 再 fan-out**
判定：**部分执行**。证据：L1537 用户主动问"ticket 02 不能先开始做点什么嘛？"之前，主控没有对 TKT-02 做任何调研或 render 核对（L1440–L1537 区间无 `situation.py render` 调用，纯粹在等 TKT-01 evidence recheck 的 wait_agent）。被问到后 L1542 主控立刻正确回答"TKT-02 的 `implementation` 依赖尚未释放...但 Plan 明确允许提前做只读 caller inventory"，随即 L1570 并行起 `luna-worker` 做只读 inventory。**根因不在主控误判，而在 Plan 文档本身**：L1560 读到的 `tickets/02-cut-over-edge-test-harness.md` 明确引用 `plan.md#global-scheduling — TKT-01 implementation dependency and one-shot caller order`——这是设计阶段（非本 slice）把 Ticket 间依赖写成了字面的"implementation dependency"而不是纯 acceptance 依赖，本 slice 只能在这个既定文档措辞下工作。"先分析 foundation 再 fan-out"这半条本身做到了：TKT-02 真正大规模 fan-out（7 个 backend-worker）发生在 TKT-01 SATISFIED 之后（L1954 起），不是补丁式抢跑。

**4. 没有因授权/formality 停下来问用户；只在真正的方案决策上返回**
判定：**已执行**。全程 0 次 `request_user_input`；7 次真人 user turn 里没有一次是主控主动发起的"能不能授权"式提问，全部是用户主动插话纠偏或追问（L188/665/989/1537/1630/7011/7041）。L606-618 一度纠结 do-review 是否要用未经验证的 snapshot workaround，但没有停下来问用户，而是自行退回正常提交（见 §4）。

**5. 每个含代码的 return 派独立 delta review；没有对每个 return 都跑 formal 多轨 do-review**
判定：**已执行**（对 return 级别）。TKT-01 fix return（L1004 DONE）之后是"一个独立 closure reviewer 只验这 7 项"（L1008 原话），不是四轨；formal 四轨 do-review 只在 TKT-01 初版实现完成（L689 起）、TKT-02 初版实现完成（L2627 起）、以及最终 terminal-final（L3851 起）这三个大里程碑各跑一次，中间大量 backend fix return（tkt02_fix_*、terminal_fix_harness 的历次 followup）都是单 reviewer 或直接由主控自己 diff 核对，没有逢 return 必四轨。

**6. evidence 登记走批量（数组）而不是逐条；登记不挤占业务推进**
判定：**现场被违反**（登记形式）+ 部分满足（没有阻塞主线）。批量数组机制存在（`engine.py:1195` `command_evidence_add` 原生支持 JSON 数组一次性写入），但本 slice 39 次 evidence 登记全部走 PowerShell foreach 单条循环调用 CLI，0 次真正用数组 stdin，累计多花 373s wall time（详见 §1、§4、§7）。"没有挤占业务推进"这半条满足：登记动作都穿插在等待 worker / 已完成阶段之间执行，没有证据显示它挡住了新 dispatch。

**7. 局部 barrier 只扣住受影响候选；有 worker 在跑时其他互不依赖工作仍被派发（OF-01 复发检查）**
判定：**部分执行**，证据不完整。TKT-02 大规模并行 fan-out（L2977 起 5 个 backend-worker 同时起）证明"多个独立候选可以同时派"这条本身没有被系统性违反。但 §2 第 3 条已指出：L1440–L1537 期间主控没有主动 render 投影去检查"是否有其他独立候选可派"，是被用户提醒才想起来查——这不完全等价于 OF-01（已知候选被忽略），因为**没有证据显示当时的投影确实把 TKT-02 只读候选标记为 runnable 而被无视**（该窗口内没有任何 `situation.py render` 调用可查）。判定为"证据不足以证实是 OF-01 复发，但确认存在同类风险模式：等待期间不主动复核投影"，写入 §7 而非直接扣上 OF-01 标签。

**8. 没有无正当理由中断 worker（OF-03 复发检查）**
判定：**本 slice 无相关场景**。全程 `interrupt_agent` 调用次数为 0。L1630"retry."不是中断——L1647/1649/1651 三个 agent（`tkt01_evidence_edge_client`/`tkt02_early_inventory`/`tkt01_evidence_runtime`）同时报 `Agent errored: stream disconnected before completion: Unable to verify model access right now`，是 carrier 级别断连（模型访问验证失败），不是主控主动中断；主控在 L1656 正确诊断"三个 agent 都是同一类 carrier/model-access 断连，不是业务失败"并按 dispatcher 恢复规则复用原 agent、换新 dispatch id 重试（继续对同一 task_name followup，没有另开新 spawn），符合"carrier 明确失败"这一条允许中断/重试的场景（虽然这里连中断都没做，只是被动收到错误后重试）。

**9. 收尾动作没有挡住主线交付（OF-04 复发检查）**
判定：**已执行**，无反例。收尾提交（L6942/6966 两次 `git commit -m "docs(impl): close issue 304 attempt"`）都发生在 Gate 已 PASS（L6905-6915）之后，没有证据显示 backfill/登记/文档动作提前挡住了业务代码推进；evidence 批量登记问题（第 6 条）是**效率**问题，不是**顺序/阻塞**问题。

**10. worker 有自己的 worktree（写集不能精准切割时先分 wt 再集成）**
判定：**本 slice 无相关场景**。本包全程只有一个 worktree（`C:\Users\Xiao\.codex\worktrees\3617\tinymlops-team-server-project`），所有 backend-worker/luna-worker 并行实例共享同一 worktree、靠 write-set 隔离（L1305"三个 backend lane 正在并行补证，write-set 已隔离...共享只读 HEAD，但没有共同写文件"），没有出现"物理文件不可分割、需要开多个 wt"的场景，所以没有测试到"该不该开多 wt"这条规则。

**11. 主控 context 卫生：长测试/长脚本包给 worker 跑，主控没有把大段输出读进自己 context**
判定：**已执行**。全量 `pytest server/tests`（5 次全量重跑，2000+ passed）均在 backend-worker/luna-worker 内部执行，主控自己只在 EXEC 里跑过零星 focused 测试（如 L311 两个文件）和 `git`/`impl_package_state.py` 短命令；custom_tool_call_output 摘录到 skeleton 的文本没有出现主控直接吞下几千行 pytest 输出的情况。

**12. 子代理没有越权；主控没有把裁决权让给子代理**
判定：**已执行**，未发现反例。各 review-track 子代理的 FINAL_ANSWER 都是"报告 verdict/finding"，最终 Gate pass/fail 判定动作（`impl_package_state.py ... gate pass`）都是主控自己在 EXEC 里跑的（如 L6905、L6912）；L6816"汇总 fact 已写，但 coverage 仍拒绝...让原 reviewer 只补元数据，不重跑 review、不改业务"——主控在纠正 reviewer 产出格式问题时也没有替 reviewer 做实质判断，只要求补元数据。

**13. 汇报形态：worktree/branch/comparison head 说清楚；没有用内部术语让用户看不懂**
判定：**现场被违反**。L7000（02:38:46）的最终收尾汇报只说"Gate 已 PASS...任务 closed...未执行 push 或 merge"，**完全没提 worktree 路径、分支名、HEAD**，导致用户在 L7011 另开一轮追问"wt/branch报告一下"。主控在 L7034 补的汇报里又用了"业务比较点为 `b74de2d3`"这种内部黑话，用户直接批注"这啥意思"（L7041），需要 L7044 额外解释。**对照早期汇报**：L154（19:42:59 preflight 阶段）反而把 worktree/branch/HEAD 说得很清楚——"Preflight: READY worktree: `...` branch/HEAD: `...`"。也就是说规则不是从未被遵守，而是**任务快结束、状态变成"只剩文档收尾"时松懈了**，同一 session 内前后不一致。

**14. 跨 session 通信：按用户要求做、没有多余汇报**
判定：**已执行**。本 session 全程没有主动发起 `create_thread`/`send_message_to_thread`，只在开场被动接收了来自设计 session（`01a09693-c83f`）的 2 条 inbound 消息（L10 锚点交接、L88 正式接管），此后没有再回读或汇报给原 session，符合"不复制旧聊天、不做多余汇报"的 handoff-to-new-session 定位。

**15. model/profile 档位：用户降级指令有没有被后续派发遵守**
判定：**本 slice 无相关场景**。全程 7 条真人 user turn 里没有一条是 model/profile 降级指令（luna/max、sol/medium 之类），`turn_context` 里 model 始终是 `gpt-5.6-sol`，没有观察到相关指令与遵守情况。

**16. 长寿命 subagent：有没有被 followup 太多次、跨太长时间以致输出退化（"降智"）**
判定：**本 slice 无相关场景，但有构成同类风险的长寿命样本**。最长寿命的是 `terminal_review_a/b/c/d`（10615-10623s，各 5 次 followup）和 `terminal_fix_harness`（8018s，6 次 followup），跨越 23:35→02:32 约 3 小时；但**没有证据显示这些 agent 的输出质量随 followup 次数下降**——它们每轮 FINAL_ANSWER 仍然给出具体 finding/verdict（如 L6834/6845/6853/6861 四轨终轮各自独立给出结论），没有出现空洞、重复或前后矛盾的回复，用户全程也没有说过"降智"一类的话。判定为"无关键词证据、无行为证据"，不认定复发。

---

## 3. 清单 B 逐条判定 · 设计阶段设计意图

**本 slice 不含设计阶段。** 本 session 是从设计 session（`01a09693-c83f-7930-b0fd-238c27226854`）交接而来的纯执行任务（L10/L88 两条 inbound 消息已确认），全程没有出现 req-align/impl-planning/to-tickets/handoff-to-new-session 相关的 shell 命令或 spawn。跳过。

---

## 4. 绕远路事件表（本报告重点）

| # | 触发行号 | 类型 | 现场描述 | 代价 | 一步到位应该怎么做 |
| --- | --- | --- | --- | --- | --- |
| 1 | L606–L670 | 形式化无业务收益 | do-review 需要 immutable review head，主控先设想"用独立临时 Git index 建一个不挂任何 ref 的 snapshot commit"这种复杂方案（L606），执行时命令被拒绝（L609 `exec_command failed: ... Rejected`），又试了一次仍失败（L628），才在 L618 改口"缓存脚本未实现该模式，改用正常本地提交"；用户在此期间插话 L665「直接提交了review不行嘛？」，其实主控此时已经在做同一件事。 | 3 个 assistant turn（L606/618/670）+ 8 次 EXEC（其中 2 次失败）；时钟 L606(20:09:47)→L670(20:11:59) 共 2m12s | 遇到"文档要求 A 但工具只支持 B"时，先用一次轻量探测确认 A 是否可行，不可行就直接按 B（本地 commit）走，不用先完整设计一遍不挂 ref 的临时 index 方案 |
| 2 | 全程 19 次相关 exec（L384/1890/1909/3680/3686/3701/3717/3724/3731/4046/4086/4461/4716/4729/5280/6032/6221/6424/6915） | 形式化无业务收益 | `evidence add` 支持 JSON 数组一次性写入（`engine.py:1195-1229`，一次 state save + 一次 projection refresh），但全部 39 次登记都是 PowerShell `foreach` 循环逐条单独调用 CLI 子进程（如 L3684 一次性登记 9 条 claim，仍是 9 次独立子进程调用，wall 30.6s）。 | 19 次 exec 累计 wall time 373.0s（约 6.2 分钟）；分散在 09-12 19:54 到 09-13 02:35 之间 | 把 `$rows` 直接 `ConvertTo-Json -Compress` 整体传给 `evidence add` 的 stdin，一次子进程完成一批登记，`is_batch=True` 路径本来就是为这个场景做的 |
| 3 | L3437–L6915（`23:11:18→02:35:14`） | 打补丁式返工 + 等待串行 | terminal-final 收尾循环：`tkt02_finding_closure`（L3437）开始，此后 TKT-01/TKT-02 的最终 HEAD 因 F-020 系列到 F-038 共约 10+ 个 finding 反复前移（`d7999a6`→`867d778`→`d3b364e`→`0aa5e0d`→`b74de2d`），每次 HEAD 前移都要把两张 Ticket 全部 claim（TKT-01 18 个 + TKT-02 10 个）重新跑一次「读 evidenceIndex → 逐条 evidence add」流程（对应上面 #2 的命令模式），并配一次全量 `pytest server/tests` 和一轮四轨 review。 | 跨度 3h24m（12250s）；期间 101 次 assistant turn、86 次协作工具调用（spawn/wait/followup 等）、383 次 EXEC | 本身多轮 finding-fix-revalidate 是 terminal-final 设计允许的（不算违反已否决清单第 6 条「全量检查单一 owner」），但**证据重登记**这一步可以做到"只重登记这一轮真正变化的 claim"而不是无差别全量重登记两张 Ticket 的全部 claim——尤其配合 #2 的数组批量，能把每轮的登记成本从 30s×N 降到几秒 |
| 4 | L6816–L6861 | 汇报不清 / 形式化无业务收益 | terminal-final 四轨 reviewer 的最后一轮报告没有按 do-review 模板在正文前给出 `verdict/reviewed-head/review-run/review-track` 四行元数据，导致 L6816 主控要单独再开一轮 followup，让四个 reviewer 只补 4 行元数据、不重跑审查。 | 4 个 agent 各多 1 轮 followup；时钟 52.5s（问题发现到四份报告补齐） | 在 spawn review-track brief 时把输出模板（4 行必填元数据）写进 brief 本身的硬性验收条件，而不是等 coverage 校验失败后再回头要求补 |
| 5 | L7000 / L7011 / L7034 / L7041 / L7044 | 汇报不清 | L7000 收尾汇报（"Gate 已 PASS...任务 closed"）完全没提 worktree/branch/HEAD，用户隔了一夜在 L7011 追问「wt/branch报告一下」；L7034 补的汇报又用"业务比较点为 `b74de2d3`"这种内部术语，用户直接批注"这啥意思"（L7041），需要 L7044 再解释一轮。对照 L154 preflight 阶段本来是把 worktree/branch/HEAD 说清楚的。 | 2 次额外用户交互轮次（用户侧的隔夜空档不计入代价）；主控侧响应耗时约 50s | 收尾汇报模板固定包含 worktree 路径、分支名、HEAD 三项；出现 `comparison commit`/`业务比较点` 这类内部术语时，同一句里直接用大白话说明它和"当前 HEAD"的关系，不要等用户追问才解释 |
| 6 | L1440–L1537（`21:04:53→21:15:32`） | 等待串行（轻微） | TKT-01 的 evidence source-recheck 在跑（L1510 起），主控纯粹在 `wait_agent`，没有主动 `situation.py render` 检查是否有其他独立候选（例如 TKT-02 只读 inventory）可以顺带派发，直到用户在 L1537 提醒「ticket 02 不能先开始做点什么嘛？」才想起来。 | 约 3–4 分钟等待窗口内本可并行发起 TKT-02 只读 inventory 而未发起；用户多问一轮 | 每次进入较长 `wait_agent`（如 timeout ≥120s）之前，先跑一次 `situation.py render` 确认当前是否还有其他互不依赖的候选可以顺路派发 |

**未发现足够证据的类型**：本 slice 没有找到"先做后推翻"（做完一段业务实现后因为方向错误被整体丢弃重做）的确凿案例——F-0XX 系列 finding-fix 是审查驱动的正常迭代修复，不是推翻重做；也没有找到"派发拓扑错误"（agent_type 用错）的案例，见 §2 第 2 条。按"没有证据就写没有"，不在表中列出。

---

## 5. 用户纠偏事件

| # | 行号 | 用户原话摘要 | agent 当时在做什么 | 暴露的规则缺口 |
| --- | --- | --- | --- | --- |
| 1 | L188 | 「$dispatcher 按 impl 的角色控制两种 profile 去做业务实现，luna-worker 仍然是通用的」 | 刚接管任务、读完 handoff-to-new-session 与 talk-to-boss 两个 skill，准备读 dispatcher 委派合同 | 用户用 `[$dispatcher](path)` 这种 markdown 链接引用**没有**触发系统自动把 skill 正文注入后续 user message（本 rollout 全文只有 4 处 `skills_instructions`，且都只是技能目录/描述清单，不含 SKILL.md 正文，见 §6）；主控自己此后也没有 `Get-Content` dispatcher/SKILL.md 主体——只读了两份 references（L107）。规则存在（`dispatcher/SKILL.md:20-27` "Implementer executor" 段，"同一 profile 可并行派发多次"）但**从未被真正加载读取**，这是 L989 还要再纠偏一次同一件事的根因。 |
| 2 | L665 | 「直接提交了review不行嘛？」 | 主控刚为 do-review 设计了一个不挂 ref 的临时 git index snapshot 方案（见 §4 #1），且此时其实已经改口选择了正常本地提交 | 不是规则缺失，是主控自己一度选择了过度复杂的路径；本质是「优先选最简单可行方案」这条隐性原则的执行纪律问题，不对应清单里任何一条"规则没读到"。 |
| 3 | L989 | 「提醒：前后端并不是只能各有1个subagent」 | 刚为 TKT-01 的 7 项 fix finding 派了单个 `backend-worker` 并进入 `wait_agent`（180s） | 与 L188 是**同一条规则**（角色≠载体，同一 profile 可并行多个）的第二次纠偏，间隔 47 分钟（19:43:46→20:31:29）。证明 L188 的引用没有让主控真正吸收这条规则——直到用户用大白话直接重复，行为才在之后（L2977 起 TKT-02 fix 阶段 5 个并行 backend-worker）真正改变。 |
| 4 | L1537 | 「ticket 02 不能先开始做点什么嘛？」 | 纯粹在等 TKT-01 的 evidence source-recheck 返回，没有查过 TKT-02 是否有可提前做的候选 | 不是规则文本缺失——主控被问到后立刻答对了"ready≠dependency，Plan 允许提前做只读 inventory"（L1542）。暴露的是**执行纪律**缺口：长等待窗口里没有主动 `situation.py render` 复核是否有其他独立候选（见 §4 #6），而不是规则没读到。 |
| 5 | L1630 | 「retry.」 | 三个 sub-agent（`tkt01_evidence_edge_client`/`tkt02_early_inventory`/`tkt01_evidence_runtime`）同时因 carrier 断连报错 | 不构成"纠偏"——是对基础设施故障的直接指令，主控随后的处理（L1656 判定为 carrier 故障、复用原 agent 换 dispatch id 重试）符合 dispatcher 恢复规则，不涉及规则缺口。 |
| 6 | L7011 | 「wt/branch报告一下」 | 已在 L7000 汇报"任务 closed"，未提 worktree/branch/HEAD | AGENTS.md「决策优先的状态汇报」章节要求"首段必须能独立阅读，并说明总范围...需要 owner 做出的决定"，但没有把 worktree/branch/HEAD 列为收尾汇报的**硬性字段**；L154 preflight 阶段其实做到了，说明不是不会写，是收尾阶段的汇报 checklist 里没有强制这三项，导致同一 session 前后不一致（见 §2 第 13 条）。 |
| 7 | L7041 | response annotation：「业务比较点为 `b74de2d3`」→「这啥意思」 | 在 L7034 的补充汇报里用了"业务比较点"这一内部术语 | AGENTS.md 要求默认中文、"只有必要时再附带英文专业术语"，但没有规则要求**把内部黑话（comparison commit / 业务比较点）翻译成用户能懂的说法**——这是规则覆盖的盲点，不是没被遵守的已有规则。 |

**重复纠偏统计**：「角色不是载体」这条被用户明确重复了 **2 次**（L188、L989），是本 slice 里唯一被重复纠偏的规则，直接对应 §6 里"dispatcher 正文从未被读取"的结论。

---

## 6. 规则加载核对

**dispatcher 正文是否含"Implementer executor"段**：含。仓库 `D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md:20-27`：

```
## Implementer executor
`implementer` 保留为逻辑角色，前后端工作使用具象 executor：
- frontend implementation → `frontend-worker`
- backend implementation → `backend-worker`
- 同时跨越前后端 → 沿共享契约按可独立验收的候选和 write ownership 拆分 brief；每个 brief 选择对应 executor profile，同一 profile 可并行派发多次
```

**本 slice 实际加载了哪些 skill 正文**（按是否被 `Get-Content`/`Get-ChildItem` 读取过判定，逐条核对行号）：

- `C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\skills\impl-package\SKILL.md`（路由器）：L49 读取，**完整正文**
- `C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\skills\do-review\SKILL.md`：L390 读取，**完整正文**
- `C:\Users\Xiao\.codex\skills\dispatcher\references\delegation.md`：L107 读取（与 resource-isolation.md 一起）
- `C:\Users\Xiao\.codex\skills\dispatcher\references\resource-isolation.md`：L107 读取
- `C:\Users\Xiao\.codex\skills\handoff-to-new-session\SKILL.md`：L16 读取
- `C:\Users\Xiao\.codex\skills\talk-to-boss\SKILL.md`：L16 读取
- `C:\Users\Xiao\.codex\skills\git-commit\SKILL.md`：L619 读取（触发于 §4 #1 那次纠结）
- **`dispatcher/SKILL.md` 主体（含"Implementer executor"段）：全程 413 条 shell 命令里没有一次 `Get-Content` 它——一次都没有读取。**
- **`dev-with-track/SKILL.md`、`req-align`、`impl-planning`、`to-tickets`、`backfill-stable-docs` 各 SKILL.md 主体：全程零次读取**（L93 主控自称"将依次使用 execution-boundaries、dev-with-track、dispatcher"，但没有证据显示真的 `Get-Content` 过 dev-with-track 正文；不排除是靠 impl-package 路由器 SKILL.md 里内嵌的指引间接了解，但这属于推测，未验证）。

**`[$dispatcher](...)` 引用机制核实**：用户在 L188 用 `[$dispatcher](D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md)` 这种 markdown 链接引用，**没有**在该消息或后续消息里触发系统自动注入 `<skill>...</skill>` 正文块——全文搜索 `<skill>` 标签命中 0 次；唯一出现的 `skills_instructions` 标签（L3、L2407 附近、L6972、L7007，共 4 处）都只是"可用技能名称+一句话描述"的目录清单，不含任何 SKILL.md 正文内容。也就是说，本框架方法论里假设的"链接引用会自动注入正文"这一机制，在本 slice 里**没有观察到发生**；主控要么靠自己主动 `Get-Content`，要么就是没读到。L188 之后主控没有主动去读 `dispatcher/SKILL.md`，这直接解释了 L989 为什么还要再纠偏一次同一条规则。

**cache 0.4.2 与仓库源码版本一致性**：对 `impl-package/SKILL.md`、`do-review/SKILL.md` 做 `diff`，cache（`C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\...`）与仓库源（`D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\...`）**完全一致，无差异**；`dispatcher/SKILL.md` 是 junction 直接指向仓库工作区（`C:\Users\Xiao\.codex\skills\dispatcher` 与 `D:\CodeSpace\agent-workbench\skills\dispatcher` 逐字节一致）。`evidence add` 批量数组支持（`impl_package_runtime/engine.py:1195-1229`）与 delta-review-per-return 的衔接逻辑（`command_evidence_add` 的 `is_batch` 分支）在 cache 和仓库源里都已经是最新版本——**版本本身没有滞后，问题不是"读了旧版本"，而是"该读的文件根本没读"**。

**主控实际 spawn 的 agent_type 与已加载规则是否一致**：结果上一致（backend-worker/luna-worker 的角色划分、TKT-02 阶段的多实例并行都符合 `dispatcher/SKILL.md:20-27` 的要求），但达成这个一致**不是靠加载规则文件**，而是靠用户两次口头纠偏（L188、L989）现场教会的。这是本节最主要的发现：规则写对了、版本也对齐了，但传递链条在"用户引用 → 主控真正读取正文"这一步断掉了。

---

## 7. 新发现的可优化点

按预计节省时间排序：

1. **evidence 登记全程零次使用批量数组接口**（§4 #2、§2 第 6 条）：19 次相关 exec 累计 373s wall time，如果全部改用 `$rows | ConvertTo-Json -Compress | python state.py ... evidence add` 一次性数组提交，按"单次子进程 + 单次 state save/projection refresh"估算每次能降到 3-5s，19 次可省约 4-5 分钟。改法明确、低风险：CLI 已经原生支持，不需要改代码，只需要改主控自己生成 PowerShell 命令的习惯（或者把这个模式写进 dev-with-track 的 evidence 登记参考片段里，附一个可直接抄的 foreach→array 模板）。行号：L384/1890/1909/3680/3686/3701/3717/3724/3731/4046/4086/4461/4716/4729/5280/6032/6221/6424/6915。

2. **dispatcher/SKILL.md 主体全程零次被读取，只读了它的两份 references**（§6）：直接后果是同一条规则被用户重复纠偏 2 次（L188、L989），间隔 47 分钟。如果主控在收到 `[$dispatcher](...)` 引用后自动追加一次 `Get-Content` 该文件本体（不只是 references 子目录），可以把这类重复纠偏至少减少一次——省下的不是时钟时间（L989 那次纠偏响应很快），而是省下"用户需要用大白话再讲一遍"这个信任成本。改法：把"收到 `[$skill-name](path)` 形式的引用时，若该路径此前未被完整读取过，先读一次主体 SKILL.md 而不只是 references/"写成一条通用习惯。行号：L188、L107、L989。

3. **terminal-final 循环里证据重登记不做增量过滤**（§4 #3）：TKT-01/TKT-02 的证据在 HEAD 前移的每一轮（`d7999a6`→`867d778`→`d3b364e`→`0aa5e0d`→`b74de2d` 共 5 次可数的完整重登记，行号 4473/4529/4817/5059/5128/5792/5876/6121/6436/6520）都是「遍历 evidenceIndex 里全部 claim，取最后一条 supporting 记录，换新 revision 重新写一遍」，而不是只重登记这一轮 finding-fix 实际影响到的 claim。结合优化点 1（批量数组），单次登记成本能从约 30s 降到几秒；如果同时做"只登记受影响 claim"的增量过滤，还能进一步减少要登记的条目数量，但这一步需要先能可靠判断"这轮 fix 影响了哪些 claim"，改动成本更高，暂列为线索而非明确方案。

4. **收尾汇报缺失 worktree/branch/HEAD 且用了未翻译的内部术语**（§4 #5、§2 第 13 条）：造成 2 次额外用户交互轮次（L7011、L7041）。对照 L154 preflight 阶段的汇报格式，行为标准其实已经存在于同一 session 里，只是任务进入"只剩文档收尾"状态后没有沿用。改法：把"worktree 路径 / 分支名 / HEAD"三项定为收尾汇报的硬性必填字段，和"内部术语出现时同句给大白话翻译"一起写进 talk-to-boss 或 dev-with-track 的收尾汇报 checklist。

5. **长等待窗口里不主动复核投影**（§4 #6、§2 第 7 条）：证据有限（仅 L1440-1537 一个约 3-4 分钟的窗口），代价不大，但这是一个可以低成本预防的模式——在进入 `timeout_ms ≥ 120000` 的 `wait_agent` 之前先跑一次 `situation.py render`，成本是一次几秒的命令，收益是不用等用户提醒才想起还有别的候选可以并行推进。
