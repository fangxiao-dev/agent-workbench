# W7 分析报告 —— tinymlops JP-308 configurable Original Training 主执行

rollout: `C:/Users/Xiao/.codex/sessions/2026/09/12/rollout-2026-09-12T21-33-16-01a0971c-1aaa-7210-862e-e1d057299cab.jsonl`（7959 行）
cwd: `D:\CodeSpace\dbe_jp\tinymlops-team-server-project`；worktree: `C:\Users\Xiao\.codex\worktrees\4afb\tinymlops-team-server-project`

方法说明：全部数字由 Python 流式解析脚本统计（脚本与中间产物见本目录 `build_skeleton.py`/`stats.py`/`stats2.py`/`stats3.py`），事件骨架见 `skeleton-w7.md`（3481 行）。行号均为原 jsonl 1-based 行号，引用前均已用脚本单独抽取验证。

---

## 1. 会话事实（先算数字，再写判断）

**时间跨度**：首行 `2026-09-12T19:33:17.774Z`（L1），末行 `2026-09-13T08:50:36.477Z`（L7959）。总时长约 **13 小时 17 分**。

**turn/message 计数**：
- `response_item(message)` role=user：16 条，其中 4 条是系统注入的 `<environment_context>`（L6、L2335、L7343、L7710），**真正的人类自然语言 turn 共 12 条**：L246、L833、L1063、L1502、L1508、L2051、L3696、L3747、L7347、L7375、L7714、L7935（逐条见第 5 节）
- role=assistant：147 条；role=developer：11 条
- `compacted` 事件：3 次，行号 L2079（2026-09-12T21:53:21）、L4849（2026-09-13T00:17:13）、L7246（2026-09-13T01:42:09）

**协作工具调用次数**（`function_call`，`namespace=collaboration`）：

| 工具 | 次数 |
| --- | --- |
| `wait_agent` | 144 |
| `spawn_agent` | 87 |
| `send_message` | 48 |
| `list_agents` | 31 |
| `followup_task` | 20（其中 4 次因 JSON/参数拼装错误被环境拒绝，见 L3477/L3483/L3489/L3495，最终在 L3501 才成功） |
| `js`（自定义脚本） | 17 |
| `wait` | 1 |
| `request_user_input` | 1（L3716，**被环境拒绝**：`request_user_input is unavailable in Default mode`，未真正送达用户） |
| `interrupt_agent` | **0**（全篇未出现一次真实调用；文本中出现的 4 处 "interrupt_agent" 字样均是系统 developer 消息里对该工具的说明文字或 `compacted` 事件里重放的历史，见 L4、L2079、L4849、L7246） |
| `create_thread` / `send_message_to_thread` | 各 1 次，L10 / L38，即设计 session `01a09693-c844` 的交接明文（这两次通信只在会话最开始出现一次，之后没有再和原 session 交互） |

**spawn_agent 的 agent_type 分布**（87 次全部为明文 `agent_type`，无一次缺省或与主控同 profile）：

| agent_type | 次数 |
| --- | --- |
| `backend-worker` | 36 |
| `review-track-standards` | 11 |
| `review-track-code` | 8 |
| `review-track-spec` | 8 |
| `review-track-safety` | 8 |
| `luna-worker` | 12 |
| `frontend-worker` | 4 |

`followup_task` 复用同一 agent 的分布（按去除 `/root/` 前缀后的 `target` 归并，剔除 4 次参数错误的失败调用）：`tkt01_frontend`(1)、`tkt01_backend`(1)、`tkt01_fix_partition_order`(1)、`review_tkt01_fix_state`(1)、`tkt01_remove_legacy_frontend`(1)、`tkt01_remove_legacy_state`(1)、`review_no_compat_code/spec/standards/safety`(各 1)、`tkt02_snapshot_command_attempt`(1)、`tkt02_terminal_harness`(1)、`review_tkt02_code/spec/standards/safety`(各 1)。**没有任何一个 agent 被 followup 超过 1 次**——即每个存活 agent 最多"初次任务 + 1 次追加任务"，随后即以新 agent 收尾。存活时间最长的是 `tkt01_backend`（L347 spawn → L492 首次 FINAL → L552 followup → L591 二次 FINAL，共 19:56:23→20:22:40，约 26 分 17 秒，2 轮）和 `tkt01_frontend`（L369→L444→L547→L566，19:57:08→20:18:34，约 21 分 26 秒，2 轮）。

**并发度**（按 spawn/成功 followup 为起点、下一次匹配 `FINAL_ANSWER` 为终点重建的粗粒度时间线，`concurrency_timeline.pkl`）：
- 时间加权分布（覆盖约 43718 秒有效区间）：并发 0 个（空闲）占 5.3%，**并发 1 个占 65.9%**，2 个占 14.5%，3 个占 3.2%，4 个占 4.6%，5 个占 3.1%，6 个占 1.6%，7~10 个合计约 1.7%。
- 最高并发 11，出现在 L4928（2026-09-13T00:18:35，`fix_tkt02_replay_identity_closure` 起点），是当时多条 fix/review 尾声任务短暂叠加所致。
- 4-way 并发的规律性尖峰对应每次 `review-track-{code,spec,standards,safety}` 四轨同时派发（如 L722/744/759/781、L4166/4172/4178/4184 等），是常态设计而非异常。
- **多数时间只有 1 个 agent 在跑**，说明尽管框架允许高并行，实际执行仍以串行为主（细节见第 7 节）。

**等待占比**：对 144 次 `wait_agent` 调用逐次量 `function_call → function_call_output` 的墙钟耗时求和，**主控被阻塞等待的总时长约 9464 秒（2.63 小时）**，占全篇 13.28 小时的约 19.8%；`list_agents` 阻塞可忽略（5 秒）。最长的单次 `wait_agent` 集中在 180 秒超时上限（约 15 次命中满 180s，例如 L434、L449、L469 等），说明主控习惯性用满超时窗口轮询而非缩短轮询间隔。

**夜间空档 vs 串行等待**（对全篇任意两条相邻事件的时间差 >5 分钟的缺口排序）：
1. **L7339 → L7340，01:44:00 → 07:36:04，长达 352.1 分钟（约 5.87 小时）**：紧接在第 3 次 `compacted`（L7246，01:42:09）之后，是用户离开（很可能就寝）造成的整夜空档，**不是**主控对 agent 的串行等待——`wait_agent` 单次超时上限只有 60~180 秒，无法解释这么长的间隔。恢复点正是用户带着 response annotation 回来的 L7347。
2. **L7705 → L7706，07:50:08 → 08:42:37，长达 52.5 分钟**：同样是用户离开造成的空档，紧接其后是 L7714 的补验收指令（08:42:42，与缺口结束时间几乎同秒），说明主控在这段时间里没有可推进的动作，是在等用户而非等 agent。
去掉这两段共约 6.72 小时的用户空档后，会话的"有效工作时段"约 6.56 小时，其中前述 2.63 小时的 `wait_agent` 阻塞占有效工作时段的 **约 40%**——这才是真正意义上的"等待串行"占比，量级明显高于夜间空档掩盖下的表观印象。

**shell 命令分类计数**（对 650 次 `custom_tool_call(name=exec)`，按其内部可提取的 `cmd` 做调用级主分类；`stats2.py` 输出）：

| 分类 | 调用次数（call 级） |
| --- | --- |
| impl-package 语义 CLI（`impl_package_state.py`/`evidence`/`ticket`/`trail`/`gate` 等） | 188 |
| 其他（JS 胶水代码、`write_stdin` 轮询长驻进程、apply_patch 等） | 176 |
| 读文件/查找（`Get-Content`/`Select-String`/`git grep` 等） | 122 |
| pytest/测试 | 91 |
| git | 137（子命令级 138，含大量 `git status --short; git diff --stat` 自检） |
| 容器/服务 | 17 |
| 构建/typecheck | 8 |

（注：因为很多 `custom_tool_call` 用 `Promise.all` 一次打包多条命令，"其他"类里混有对长驻前台进程的 `write_stdin` 轮询，这部分属按补充要求跳过的业务验证/训练跑批范畴，未展开分析。）

**evidence 登记：单条 vs 批量**：在 impl-package 语义 CLI 调用中，明确识别到的 evidence 写入事件约 52 次为**单条**（每次一个 JSON payload 管道进 CLI），仅 **1 次尝试走批量数组**（`$items=@(...)` 形式，见第 4 节"绕远路事件表"L6979/L6985）且**两次批量尝试均失败**（PowerShell 语法错误 + 进程创建被拒绝），最终仍退回到逐条注册（L6992/L6999/L7006/L7012/L7019）。也就是说，**"evidence 批量登记"这条 09-10～09-13 的改造在本 slice 实际执行层面没有真正生效过一次**。

**重复执行（同一归一化命令 ≥3 次）**：
- `git status --short` + `git diff --stat`（+ 有时 `git diff --check`）：在 L425/462/600/1224/1293/1299/1305/1312/1730/1820/2932/3372/4076 等处反复出现（同类合计 ≥8 次），属于每次派发/消费前后的例行自检，输入环境在变化（不同 revision），**不算重复劳动**，只是流程开销。
- `python impl_package_state.py ... ticket satisfy --help`：出现 3 次（L2595/L3992/L4027），是在不确定 CLI 用法时反复查 `--help`，其中 L2993/L6395/L6402 一带同样反复查询 `evidence add --help`/grep 源码，**在 07:43~07:46（L7510~L7578）又完整重演了一遍**——这次紧跟在夜间 compaction 之后，是"恢复记忆成本"，已计入第 4 节。
- 多个 `tools.write_stdin({session_id:...})` 轮询循环（如 session 63500 被连续 write_stdin 8 次、82726 被 7 次、96064 被 5 次）：这些是对话内直接轮询长驻前台训练/服务进程的输出，按补充要求属于业务验证范畴，不展开分析，只在第 4 节用于解释等待/中断相关的调度决策时提及。

## 2. 清单 A 逐条判定 · 执行阶段设计意图

1. **角色≠载体（同角色并行多个 worker）——已执行。** `backend-worker` 全篇 36 次派发，多处同角色并行：L4131/L4137/L4143/L4149（2026-09-12T23:35:23~23:35:54，31 秒内连续派出 4 个 backend-worker 分别清理 mock edge/canonical demo seams/legacy async/full path）；L3153/L3158/L3163/L3169（22:34:03~22:34:35，4 个 backend-worker 并行做 tkt02 realized state 各分片）；L1150/L1165（20:52:48/20:53:13，2 个 backend-worker 并行修 tkt01 的两个独立 finding）；L2195/L2201（21:57:16/21:57:25，2 个 backend-worker 并行删两处 legacy）。同样 `review-track-*` 四种角色也反复在不同审查轮次里各自被多次派发（standards 11 次、code/spec/safety 各 8 次），未见"每角色只派一次"的收紧现象。

2. **派发 profile 正确性——已执行（call-grok 部分本 slice 无相关场景）。** 87 次 `spawn_agent` 的 `agent_type` 全部是明文且落在 `{luna-worker, backend-worker, frontend-worker, review-track-code/spec/standards/safety}` 集合内，未发现任何一次缺省、空值或"与主控同 profile"的默认派发。用户在本 slice 内没有指定过 `call-grok`，因此这部分没有可判定的现场。

3. **ready≠dependency——部分执行。** TKT-02 的只读 `tkt02_scope_map`（L1543，21:21:18）派发时，TKT-01 的修复仍在进行（上一条 TKT-01 fix 是 L1475 `tkt01_fix_partition_order`，21:17:15；随后 L1580/L1595/L1613/L1786 又持续到 21:29:59），说明下游确实在上游未最终验收时就先做了只读调研，且遵守"先分析再 fan-out"（先派只读 `luna-worker` scope_map，而不是直接派 backend-worker 实现）。但这一步是被用户在 L1502（21:18:37 "既然没有阻塞了，是否可以开始先做一些 ticket 02 的事情了"）点名之后才发生的——**主控自己没有在无阻塞时主动提前开工**，属于"规则理解到位、执行依赖外部提醒"的部分执行。

4. **不因 formality 停下问用户——已执行（含一次工具失败但优雅降级）。** 全篇仅 1 次 `request_user_input`（L3716，23:06:20），且被环境直接拒绝："request_user_input is unavailable in Default mode"（L3718）。主控没有反复重试或转而在聊天里生硬地问用户，而是在 13 秒内（L3722，23:06:28）改用 Execution Record 记录自己的判断（`purpose='judgment'`，`recordId=initial-ER-002`）并继续推进，没有阻塞主线。另一处真正的方案决策——`client/physical-rover/` 是否在本 ticket 内删除（L4051，23:31:34）——则是通过普通 assistant 消息正确地把decision留给用户，而不是用工具生硬打断，属于该条款鼓励的行为。

5. **delta review vs formal 多轨——现场被违反。** TKT-01 首轮实现在同一时间窗口内被**同时**派了 2 个 delta review（L667 `review_tkt01_backend_delta`、L682 `review_tkt01_frontend_delta`，均为 luna-worker）**和** 4 轨 formal review（L722/744/759/781 `formal_tkt01_track_a/b/c/safety`）——delta 和 formal 叠加对同一增量重复审查。后续更严重：TKT-02 一个 ticket 在收尾阶段先后跑了 **4 轮完整的 4 轨 formal review**（`review_tkt02_*` 初始 L4166-4184；`review_tkt02_final_*` L5275-5295；`review_tkt02_terminal_*` L6118-6136；`review_tkt02_terminal_closure_*` L6283-6301），TKT-03 也跑了 2 轮（初始 L4872-4899；`review_tkt03_closure_*` L5761-5788）。这与"delta review 是常态，formal 多轨只在关键节点"的设计意图明显不符（细节与代价见第 4 节）。

6. **evidence 批量登记——现场被违反。** 见第 1 节：仅 1 次尝试批量（L6979/L6985 的 `$items=@(...)` PowerShell 数组写法），两次都失败（`SyntaxError: Unexpected identifier 'rez'` / `CreateProcess ... Rejected`），随后放弃批量、退回到 5 次逐条注册（L6992/L6999/L7006/L7012/L7019，其中 L7006 还因引号问题再失败一次）。全篇其余 ~47 次 evidence 写入也全部是单条形式。批量登记这条改造在本 slice 里没有一次真正跑通。业务推进本身没有被明显卡住（每条注册几秒到 30 秒），但完全违背了"批量登记"的设计初衷。

7. **局部 barrier 不误挡独立候选（OF-01 复发检查）——部分执行，证据不完全指向具体误挡候选。** 第 1 节的并发时间线显示：全篇 65.9% 的时间只有 1 个 agent 在跑，4/5/6 并发的尖峰全部对应设计好的"四轨并行 review"批量派发，而不是主控主动把多条互不依赖的实现/调研任务同时铺开。没有找到具体某个可独立推进却被无谓挡住的候选（未见到"某任务已就绪但被无关 barrier 拖住"的直接证据），但整体并行利用率低于框架能力，值得在第 7 节继续讨论。

8. **无正当理由中断 worker（OF-03 复发检查）——本 slice 无相关场景。** `interrupt_agent` 在全篇 87 次 spawn、144 次 wait 中**零次**被调用；文本里出现的 4 次 "interrupt_agent" 字样都只是系统 developer 消息对工具能力的说明或 `compacted` 事件里重放的历史文本（L4、L2079、L4849、L7246），不是真实调用。没有可判定的中断事件。

9. **收尾动作不挡主线交付（OF-04 复发检查）——已执行，未发现明显阻塞。** 第 4 节记录的"07:43~07:46 CLI 用法重新摸索"（L7510-7578）发生时，`review_tkt03_physical_snapshot_final`（L7477 已 spawn）仍在独立跑，两者没有互相阻塞；结尾处 TKT-03 evidence 重新绑定到最终 revision（L7635/L7644）与状态转 SATISFIED（L7644 后）都发生在会话尾声、已无其他候选可并行，不算"挡住主线"。

10. **worker 自有 worktree——本 slice 无相关场景。** 全篇 `git worktree add` 字样仅出现在系统 developer 消息/`compacted` 重放的工具能力说明里（L7、L2080、L4850、L7247），没有一次是主控或 worker 真实执行的 `git worktree add`。前后端划分完全靠目录（`frontend/` vs `server/`），没有出现"写集无法精确切割"从而需要开多个 wt 的场景。

11. **主控 context 卫生（长测试/长脚本包给 worker 跑）——现场被违反。** 主控自己（root 的 `custom_tool_call`，不是委派给 worker）直接对多个长驻前台进程反复 `write_stdin` 轮询，例如 session_id 63500 被连续轮询 8 次（L3588/3594/3600/3606/3612 等）、82726 被 7 次（L7062/7070/7076/7082/7088）、96064 被 5 次（L3916/3922/3928/3934/3940）。这些内容属于补充要求里明确排除的业务验证/服务调试范畴，本报告不展开其内容，但"谁在做轮询"这件事本身就是调度层面的证据——是**主控自己**长时间占用自己的上下文做轮询，而不是包给 `luna-worker` 跑、只要进度和结果，与用户纠偏"长测试脚本可以包在 luna-worker 里跑，主控只要进度和结果，不要污染自己的 context"直接相悖。

12. **子代理不越权——已执行（未发现反例）。** 抽查到的 `agent_message` FINAL_ANSWER 内容（如 L324 `EVIDENCE_SUFFICIENT`、多处 `CONTRACT_CHANGE_REQUEST`/`DONE`/`BLOCKED` 等）均落在被交代的任务范围内返回结构化结论，没有发现子代理自行扩权、越俎代庖做主控裁决的证据。囿于时间，本条判断基于抽样而非逐条通读全部 171 条 `agent_message`，结论保守。

13. **汇报形态清晰（worktree/branch/comparison head）——已执行。** 用户在 L7935（08:49:54 "wt/branch报告一下"）问询后，主控在 L7940-7956 只读核对 worktree 路径、分支、相对 `dev-fang`/`origin/dev` 的 ahead/behind 数（ahead 37、behind 1）并直接把结论说清楚，没有使用"业务比较点"之类的内部术语。"comparison point" 一词在全篇确有出现（如系统提示与内部 review 产物中），但没有观察到它被直接甩给用户导致用户看不懂的实例。

14. **跨 session 通信——已执行。** `create_thread`（L10）与 `send_message_to_thread`（L38）在会话最开始各出现 1 次，是消费设计 session `01a09693-c844` 的交接内容；之后全篇再没有对原 session 发起过任何通信，没有"多余汇报"的痕迹。

15. **model/profile 档位降级指令——本 slice 无相关场景。** 12 条真实用户 turn（第 5 节列出）里没有一条提到模型档位（如 luna/max、sol/medium）的降级或调整，AGENTS.md 里的默认档位设置（`@luna-worker (luna/max)`）在本 slice 期间没有被用户改动过，因此无可判定的"遵守/违反"现场。

16. **长寿命 subagent 降智——现场证实。** `tkt01_backend`（L347 spawn → L492 首次 FINAL → L552 followup → L591 二次 FINAL，19:56:23→20:22:40，约 26 分钟 2 轮）与 `tkt01_frontend`（L369→L444→L547→L566，19:57:08→20:18:34，约 21 分钟 2 轮）是全篇唯二被 followup 复用过的"实现类"worker。紧随其后，L923（20:41:13）主控自己报告"四条 formal leaf 已全部返回 FAIL"（对应 L722/744/759/781 四轨 review 全部判定这两个 worker 交付的代码不合格），随后用户在 L1063（20:48:42）质疑"这些问题是不是说明你的 subagent 用太久了，已经开始降智了"。证据链完整：同一 worker 两轮任务、随后 4/4 审查全部 FAIL，时间点高度吻合用户的怀疑。但需注意：本 slice 里其余所有 followup 复用（review 类、legacy 删除类等）都只发生 1 次追加任务且没有观察到类似的批量 FAIL，无法从本 slice 单独证明"复用次数与质量下降"之间存在普遍因果关系——这里只能确认这一具体实例的时间相关性，不构成统计规律。

## 3. 清单 B 逐条判定 · 设计阶段设计意图

本 slice 不含设计阶段。开篇 `create_thread`/`send_message_to_thread`（L10/L38）明确是消费设计 session `01a09693-c844` 已完成的 req-align/impl-planning/to-tickets 交接内容（"全新独立 local session；不继承旧会话历史"），本 rollout 从 L10 起就是纯执行阶段（dev-with-track/do-review）。中途 L3747 新增的 TKT-03（legacy 清理）是在既有 Decision/Spec 之下走 no-contract fast path 直接补 Ticket（L3752 "这个清理与 TKT-02 的训练产物链路没有实现依赖，我会把 GitLab work item #320 作为 TKT-03 的需求来源，更新当前 Impl-Package 的 Plan/Ticket 后立刻并行启动"），没有触发 req-align 的 Decision/Spec gate 或独立 impl-planning 评审，因此不构成第 3 节要判定的"设计阶段"。

## 4. 绕远路事件表（本报告的重点）

| 触发行号 | 类型 | 现场描述 | 代价 | 一步到位应该怎么做 |
| --- | --- | --- | --- | --- |
| L2044→L2051→L2195/2201/2207→L3040 | 范围理解偏差 / 先做后推翻 | 主控把内部自研 training worker 产出的历史记录当成"外部遗留格式"处理，提出 F-002（L2044，21:50:21）请求批准"历史 normalization-only run 继续返回既有七字段 `effectiveConfig`、前端按 legacy union 安全展示、新字段显示'未记录'"这一兼容层方案。用户在 L2051（21:51:46）纠正："如果你说的历史是我们自己实现的 training worker，那我认为没有必要兼容，直接改就行了，poc而已"。主控随即派 2 个 backend-worker + 1 个 frontend-worker（L2195/2201/2207，21:57:16-21:57:33）删除刚建立的 legacy 兼容代码，再派 2 个 backend-worker 修复衍生问题（`fix_no_compat_canonical_validator`/`fix_no_compat_projection_fail_closed`，L2807/2813），并对这次"去兼容"重新跑了 2 轮完整 4 轨 formal review（L2655-2673 初始 + L2954-2969 followup，共 8 个 review-track spawn）。 | 时钟：21:51:46→22:28:55（review_no_compat 最终一轨返回）约 **37 分钟**；turn/派发：3 个删除 worker + 2 个修复 worker + 8 个 review-track spawn，共 **13 次派发**用于清理一个本可以在最初实现阶段就不引入的兼容层。 | 在设计/首次实现阶段先判断"历史数据的生产方是否受本包控制"——本包本身就是这个 training worker 的实现方，POC 阶段默认不做向后兼容，除非 Decision/Spec 明确要求；避免先落一层兼容代码再等用户裁决是否需要它。 |
| L1150→L1165→L1475→L1580→L1595→L1613→L1786→L1927 | 打补丁式返工 | TKT-01 首轮实现（`tkt01_backend`/`tkt01_frontend`，L347/369，含各 1 次 followup）完成后，4 轨 formal review 全部 FAIL（L923，20:41:13："四条 formal leaf 已全部返回 FAIL"）。随后主控连续派出 **7 个**独立 backend-worker 逐个修：`tkt01_fix_state_contract`(L1150)、`tkt01_fix_split_fixtures`(L1165)、`tkt01_fix_partition_order`(L1475)、`tkt01_fix_request_schema`(L1580)、`tkt01_fix_openapi_union`(L1595)、`tkt01_fix_projection_identity`(L1613)、`tkt01_fix_inherited_null`(L1786)，直到 L1927（21:45:26）`tkt01_fixed_findings_closure` 才最终收口。 | 时钟：20:52:48→21:45:26，约 **52 分 38 秒**；turn/派发：**7 次**独立 fix worker 派发（外加更早的 2 次 delta review + 4 轨 formal review 已在第 5 项单独计入）。 | 4 轨 formal review 一次性把 6 个 blocker 去重列出后，尽量合并成 1~2 个 fix worker 按受影响文件分片并行修，而不是发现一个 finding 派一个 worker；同时第一轮实现前就该把 formal review 覆盖的核心契约（状态机、分片、schema）过一遍，减少首轮 4/4 FAIL 的概率。 |
| L1165 / L2524 / L3646 → L3696 | 打补丁式返工 | fixture 问题被反复单独打补丁：`tkt01_fix_split_fixtures`(L1165, 20:53:13) → `tkt01_refresh_projection_fixtures`(L2524, 22:08:06) → `tkt02_refresh_runtime_fixtures`(L3646, 23:03:27)，三次独立派发分别修 TKT-01/TKT-02 阶段各自暴露的 fixture 问题。用户在 L3696（23:05:51，紧接在第三次 fixture 修复之后）明确叫停："如果有fixture的问题，我建议不要再修，而是直接按正确的，直接修复共享 fixture builder 一次，而只属于legacy的东西则直接删除"。 | 跨度：20:53:13→23:05:51，约 **2 小时 13 分**（期间穿插大量其他工作，不能全部归因于 fixture，但 fixture 相关派发本身有 **3 次**独立触发）。 | 第一次 fixture 问题出现时就定位到共享 fixture builder（而不是分散在各消费点打补丁），一次性重构掉，后续 ticket 直接复用，不需要每个 ticket 各自再触发一轮 fixture 修复。 |
| L4166→L4321(初始) / L5275→L5422(final) / L6118→L6322(terminal) / L6283→L6471(terminal_closure) | 形式化无业务收益 | TKT-02 收口阶段先后跑了 **4 轮完整的 4 轨 formal review**（`review_tkt02_*` 初始 L4166-4184；`review_tkt02_final_*` L5275-5295；`review_tkt02_terminal_*` L6118-6136；`review_tkt02_terminal_closure_*` L6283-6301），每轮之间穿插 11 次独立 `fix_tkt02_*` worker（`fix_tkt02_adapter_integrity`/`_execution_context`/`_publisher_residue`/`_fullpath_acceptance`/`_terminal_fixtures`/`_realized_validation`/`_deepfreeze_closure`/`_replay_identity_closure`/`_adapter_seam_closure`/`_wizard_rendered_proof`/`_mlflow_search_method`），形成"formal review → 发现问题 → fix → 再跑一次完整 formal review"的循环，而不是"delta review 跟进 fix，只在真正终态才跑一次 formal"。 | 时钟：L4166 首次 spawn 23:36:19 → L6471 最后一轨返回 01:05:56，约 **1 小时 30 分**；派发：**16 次** review-track spawn（4 轮 × 4 轨）+ **11 次** fix worker，共 **27 次**派发只为关闭 1 个 ticket。 | 只在首次实现完成和"认为已经可以收口"两个节点各跑 1 次完整 4 轨 formal review；中间每次 fix 之后用 1 名独立 reviewer 做 delta review（对照固定 code_delta），有交叉影响再局部追加 formal 轨，不要每次"自认为改完了"就重新起 4 轨。 |
| L6979 / L6985 / L6992-7019 | 工具环境失败 | 主控尝试用 PowerShell 数组 `$items=@(...)` 一次性批量登记 TKT-01 的多条 evidence（L6979，01:27:10），失败：`SyntaxError: Unexpected identifier 'rez'`；重试一次（L6985，01:27:20）又失败：`CreateProcess ... Rejected("Failed to create unif...`。随即放弃批量思路，改成 5 次逐条 JSON-pipe 单条注册（L6992/6999/7006/7012/7019），其中 L7006 还因引号问题再失败一次，L7012 重试才成功。 | 时钟：01:27:10→01:29:20，约 **2 分 10 秒**；派发不涉及 worker，纯主控自身 exec 调用，共 **7 次** exec（2 次失败批量 + 5 次单条，含 1 次单条失败重试）。 | evidence 批量登记应该走 impl-package CLI 原生支持的 JSON 数组入参（通过临时文件或 stdin 传入整段 JSON，避免在 PowerShell 里现场拼 hashtable 字面量），而不是现场用 PowerShell 语法构造数组；批量语法应作为固定模板复用，不必每次临场拼。 |
| L7477(spawn)→L7510-7578 | 打补丁式返工（压缩后记忆丢失） | 第 3 次 `compacted`（L7246，01:42:09）后紧跟长达 5.87 小时的用户夜间空档，用户于 07:36 回来。主控在 07:43-07:46（L7510/7517/7547/7554/7561/7568/7575，共 7 次 exec）反复查 `evidence add --help`、`grep` CLI 源码（`impl_package_state.py`/`command_groups.py`）来重新确认 evidence 登记与"多条证据重新绑定到同一 revision"的用法——而这套用法它在 01:25-01:29（L6959-7019）已经完整用过一次。 | 时钟：07:43:05→07:46:03，约 **3 分钟**；派发：0（纯自身 exec），但反映的是 compaction 导致的过程性知识丢失，后续 07:47-07:48 重新绑定 8 条证据的实际操作（L7635/7644）又各花 15.6 秒 / 10.0 秒，明显慢于此前同类调用（对比 L6961/6967 的 30.8s/30.7s 是首次探索，L7638/7647 应该更快但反而更慢，侧面印证"重新学习"而非"复用记忆"）。 | compaction 时把"已验证可用的 CLI 调用模板"（尤其是 evidence add 单条/批量的准确语法）作为结构化摘要保留，而不是整体压缩成叙述性摘要；或在 execution-findings.md/trail 里显式记一条"CLI cheatsheet"，下次直接读文件而不是重新试错。 |
| 全篇 144 次 `wait_agent` | 等待串行 | 主控对绝大多数 `wait_agent` 调用使用 120s/180s 的固定超时并等满（约 15 次命中 180s 满超时，如 L434/449/469/571/854/897/1231/1867/1880/3546/3729/4579/4665/4679），而不是更短间隔轮询或在 `list_agents` 侧显示子任务已完成时立即消费。 | 累计阻塞 **约 9464 秒（2.63 小时）**，占刨除夜间空档后"有效工作时段"（约 6.56 小时）的约 40%。 | 缩短首次轮询间隔（例如 30-45s）并在收到 `MESSAGE`（非 FINAL）时降低后续轮询超时，而不是固定用满 120/180 秒；或在等待期间见缝插针派发其他互不依赖的候选，而不是纯粹阻塞等待。 |

## 5. 用户纠偏事件

全篇 12 条真实用户 turn 逐条列出（含 1 条 response annotation）。

1. **L246（19:44:48）**"[$dispatcher](...)按 impl 的角色控制两种profile去做业务实现，`luna-worker`仍然是通用的，已派发的本轮不打扰"。主控之前正在核对 server/frontend 依赖、准备派 backend/frontend-worker（L226-241）。暴露：dispatcher SKILL.md 的"Implementer executor"段（含 `frontend-worker`/`backend-worker`）其实已在 **19:35:01（L59）就被主控完整读入上下文**，比这条用户消息早 9 分钟——规则**已加载**，但用户仍选择在真正派发前抢先重申一次。说明"规则在上下文里"不等于"模型会在正确的决策点主动应用它"，用户用显式提醒兜底。
2. **L833（20:31:39）**"补充：前后端并不是只能各有1个subagent"。此时主控只派过 1 个 frontend-worker + 1 个 backend-worker（各自 1 轮实现 + review 在途）。暴露：与第 1 条同一主题（role≠carrier）在 47 分钟内被**重复提醒第 2 次**；已加载的 dispatcher 正文里"Implementer executor"一节描述的是"前后端按 ownership 拆成两个 brief"，**没有显式写"同一角色可以并行派多个实例"**这一句——很可能是规则文本本身对"多实例"这层没有写清楚，而不是主控没读到。
3. **L1063（20:48:42）**"这些问题是不是说明你的subagent用太久了，已经开始降智了"。直接原因：`tkt01_backend`/`tkt01_frontend` 各被 followup 复用 1 次（2 轮任务，19:56~20:22 / 19:57~20:18），随后 L923（20:41:13）主控自己报告 4 轨 formal review **全部 FAIL**。暴露：dispatcher 正文"并行、复用与恢复"一节只说"worker 复用取决于相关上下文仍准确...不按固定等待时间或 INCOMPLETE 次数机械换人"，**没有给出复用轮次/时长的硬上限或质量哨兵**，把风险判断完全交给模型自己的主观判断——这是一处规则设计上的真空，不是版本没读到。
4. **L1502（21:18:37）**"既然没有阻塞了，是否可以开始先做一些ticket 02的事情了"。当时 TKT-01 fix 循环仍在推进（最近一次 L1475，21:17:15）。暴露：dispatcher"并行、复用与恢复"一节明确写"未来可能交叉的 Topic/Ticket 不提前串行当前独立工作"——**规则写了，但主控没有主动据此提前起 TKT-02 只读调研，等到用户点名才做**，属于"规则加载了但执行时机依赖外部触发"。
5. **L1508（21:20:17）**"retry."。紧接在两个 worker 因 "Unable to verify model access right now. Please retry." 断线失败之后（L1523/1525）。这不是设计规则缺失，而是**真实 carrier/工具失败**触发了用户的手动兜底；随后主控的处理（L1530"这是 carrier failure，不是代码 blocker，也不换 scope"，followup_task 原地续接）正确应用了 dispatcher 的"carrier/tooling recovery由同一 worker完成"条款——本条更多反映环境不稳定，而非规则遵从问题。
6. **L2051（21:51:46）**"如果你说的历史是我们自己实现的training worker，那我认为没有必要兼容，直接改就行了，poc而已"，针对主控在 F-002（L2044）里提出的历史数据 legacy-union 兼容方案。暴露：这不是 dispatcher/impl-package 规则缺失，而是**全局 `~/.codex/AGENTS.md` 里已经写明的原则被违反**——该 AGENTS.md 在会话一开始（world_state，L7）就完整加载，其中"思考方式"一节写"拒绝打补丁"，"简洁优先"一节写"如果有可复用的模块或组件，优先复用而不是新增补丁"、"不写防御性冗余文案"。主控为自己实现的 training worker 建兼容层，正是这几条已加载规则应该拦住但没拦住的场景（详细代价见第 4 节）。
7. **L3696（23:05:51）**"补充：我们后续会清理掉所有legacy代码...所以如果有fixture的问题，我建议不要再修，而是直接...修复共享 fixture builder 一次，而只属于legacy的东西则直接删除"。此前 fixture 问题已被独立打了 2~3 轮补丁（L1165/L2524/L3646，详见第 4 节）。暴露：同样对应 AGENTS.md"拒绝打补丁"/"优先复用而不是新增补丁"这条已加载规则，在具体执行层面被绕过——主控倾向于"哪里报错修哪里"而不是先定位共享根因。
8. **L3747（23:12:15）**"按这个清理的task补充为第3个ticket，由于这是清理，我理解完全可以马上开始"。暴露：与第 4 条同一模式——"ready≠dependency，无依赖的清理工作可以立即开始"这条原则又一次需要用户明确授权才被执行（主控在 L3752 才响应式地说"我会...立刻并行启动"），而不是主控自己判断出这条新 Ticket 与 TKT-02 无实现依赖后主动开工。
9. **L7347（07:36:08，response annotation）**引用"source-only snapshot"问"干嘛的，现在已经确认没有用了吗"。这是用户回来后针对**主控自己**在 L4051（23:31:34，夜间空档前）提出但一直悬而未决的问题（`client/physical-rover/` 是否在本 ticket 删除）的追问，不是对主控错误行为的纠偏，而是长达 5.87 小时的夜间空档导致一个合法的方案决策悬置了一整夜，只能靠用户第二天翻记录才捡起来。反映的是"真正需要用户决策时正确停下来问了"，但没有把这类悬置决策以更醒目的方式（而非埋在助手消息里）留给用户异步处理。
10. **L7375（07:37:05）**"删除"。对第 9 条问题的直接答复，主控在 L7380 立即执行，无延迟。
11. **L7714（08:42:42）**"直接补就行，无需再打开任务包，有问题也先本地记下，除非遇到阻塞，不要有任何问题就返回"。暴露：与背景材料里贯穿整批 09-12～09-14 rollout 的"禁止因授权/formality 停下来问"是同一主题的**第三次**重申（前两次分别是隐含在 L2051/L3696 等纠偏里的"不要犹豫，直接改"精神）——说明主控倾向于比用户预期更频繁地想要"回来确认"，即使 request_user_input 本身在这个环境里经常直接失败（第 1 节：唯一一次调用被拒绝）。
12. **L7935（08:49:54）**"wt/branch报告一下"。普通信息请求，非纠偏；主控回复清晰（worktree 路径、分支、ahead 37/behind 1），未发现问题。

**重复纠偏主题小结**：role≠carrier（L246→L833，2 次）、"不要为形式/授权停下"（L2051/L3696 精神一致→L7714，贯穿整个 slice）是本 slice 里被用户重复最多次的两条规则；前者更像"规则文本本身对多实例场景没写清楚"，后者更像"规则写了（AGENTS.md 全局原则 + dispatcher 的 POC 授权条款）但主控在具体决策点没有严格执行"。

## 6. 规则加载核对

**dispatcher 正文的加载方式与内容**：本 slice 里 `[$dispatcher](D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md)` 这种 `[$xxx](path)` 引用**没有**触发"把 skill 正文以 `<skill>...</skill>` 块自动注入后续 user message"这种机制——L246 那条用户消息全文只有 133 字符，就是纯文本链接 + 一句话，没有任何注入内容跟在后面（已用 Python 直接抽取该行 `content[].text` 验证，长度 133）。真正让 dispatcher 正文进入上下文的，是主控自己在会话最开始主动发起的一次批量文件读取：L55（19:34:57）的 `custom_tool_call` 用 `Promise.all` 一次性 `Get-Content` 了 4 个 SKILL.md ——
`impl-package/0.4.2/skills/execution-boundaries/SKILL.md`、`impl-package/0.4.2/skills/dev-with-track/SKILL.md`、`C:\Users\Xiao\.codex\skills\dispatcher\SKILL.md`、`ponytail/ponytail/4.9.0/skills/ponytail/SKILL.md`，对应输出在 L59 等一串 `event_msg(item_completed)` 里（19:35:01 附近）。dispatcher 正文里确实包含"## Implementer executor"一节（`frontend-worker`/`backend-worker` 具象 executor、"implementer 保留为逻辑角色"），**在 19:35:01 就已完整进入主控上下文**，比用户 L246（19:44:48）的显式提醒早 9 分钟——即"用户后来还要重复'角色不是载体'"这件事，发生在规则文本本身已经加载完毕之后，说明问题不在"没读到"，而在"读到了但没有在决策点被稳定应用"（且 dispatcher 正文对"role≠carrier"这条本身的表述其实落在"Implementer executor"一节里描述的是前后端两个具象 executor 的 ownership 拆分，并没有一句话明确写"同一 executor 角色允许并行多个实例"——这是文本本身可能需要补的一处，而不是加载版本问题）。

**impl-package 各 skill 的加载版本核对**：全篇引用的 impl-package 脚本/技能路径全部指向 `C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\`（如 L55 的 `dev-with-track/SKILL.md`、反复被调用的 `scripts\impl_package_state.py`、L1000 附近的 `scripts\review_track_stats.py` 等），与本仓库当前 `plugin-marketplace/plugins/impl-package/.claude-plugin/plugin.json` 里记录的 `"version": "0.4.2"` **版本号一致**。抽查两条关键规则文本，cache 与仓库当前版本**逐字一致**：
- `evidence add` 支持数组批量登记的官方用法——cache 版 `dev-with-track/situations.yaml:223` 与仓库当前 `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml:223` 都是同一行：`printf '<evidence-object-or-non-empty-array-json>' | python impl_package_state.py --package <package> evidence add`。**但这一行具体文本在本 rollout 全篇里从未被读到过**（全文 grep `evidence-object-or-non-empty-array-json` 零命中）——situations.yaml 虽然在 L104、L2062 附近被读取过（用于查别的 situation 条目），但显然没有覆盖到 evidence-add-array 这一条。这直接解释了第 4 节里 L6979/L6985 为什么会现场发明一套脆弱的 PowerShell `$items=@(...)` 写法去拼批量参数，而不是用文档里现成的"`printf` 整段 JSON 数组 | 管道进 CLI"这个更简单、本该更稳的形式：**规则确实存在且版本一致，只是这次执行没有真正读到它**。
- delta review "一名独立 reviewer 检查该固定增量"——这条规则实际写在 dispatcher（而非 dev-with-track）正文里（L55/L59 读到的原文："新增实现代码的 return 在同次消费中固定 `code_delta={base,head}` 并安排独立 delta review...没有[额外 formal requirement]时由一名独立 reviewer 检查该固定增量及直接受影响路径...已有真实 formal review 覆盖同一增量且输入与归属可核验时直接复用其结果，不叠加同范围轻量审查"）。这条规则**已加载**，但第 2/4 节记录的现场（TKT-01 首轮 delta+formal 叠加、TKT-02 收口跑 4 轮完整 formal）表明主控没有严格执行"不叠加同范围轻量审查"和"formal 只在关键节点"的部分。

**当前仓库状态提示**：本次分析开始时的 git status 显示 `skills/dispatcher/SKILL.md` 在仓库当前工作区里是**未提交的修改状态**（`M skills/dispatcher/SKILL.md`），`agents/backend-worker.toml`/`agents/frontend-worker.toml` 是**未跟踪的新文件**。也就是说，仓库当前对 dispatcher 正文和 Implementer executor 的 toml profile 定义可能已经在本轮实战复盘的基础上做了调整，**与本 rollout（09-12~09-13）实际读到的版本不完全相同**——上面关于 dispatcher 正文的引用均以 rollout 里实际读到的文本为准，不代表仓库当前 HEAD 状态。

**spawn 时使用的 agent_type 与已加载规则的一致性**：第 1/2 节已确认 87 次 `spawn_agent` 的 `agent_type` 全部落在 `{luna-worker, backend-worker, frontend-worker, review-track-*}` 集合内，与 L55-59 加载的 dispatcher"Implementer executor"一节（frontend/backend 具象 executor）以及 review 相关 skill 对 `review-track-{code,spec,standards,safety}` 四轨命名完全对应，没有发现 agent_type 拼写、profile 选择与已加载规则不一致的情况。

## 7. 新发现的可优化点

按预计节省的时间/turn 排序（次数是线索，不是结论）：

1. **主控自己直接跑长驻前台进程轮询与 pytest，而不是委派给 worker——预计可省下最多的主控自身 context/token 预算。** 全篇统计到主控（root 自身的 `custom_tool_call`，不经过任何 `spawn_agent`）直接发起 `tools.write_stdin` 轮询长驻进程 **53 次**（如 L3588/3594/.../3612 对 session 63500 连续 8 次、L7062/7070/.../7088 对 session 82726 连续 7 次），以及直接执行 `pytest` **24 次**（未委派给 `luna-worker`）。这些调用的原始输出（训练/服务日志、测试详情）会直接进入主控自身的对话历史，逐条累积消耗它自己的上下文预算——这正是用户在背景材料里强调"长测试脚本可以包在 luna-worker 里跑，主控只要进度和结果，不要污染自己的context"要防的场景。改法：凡是预期输出较长或需要多次轮询才能收敛的前台进程/测试套件，一律先 `spawn_agent(luna-worker)` 把"启动+轮询+摘要"整体包进去，主控只消费其 `FINAL_ANSWER` 的摘要而不是原始 stdout。
2. **CLI/脚本用法现场摸索（`--help`、grep 源码）贡献了约 6% 的 shell 调用量，且有明确的"同一知识被摸索两次"的证据。** 全篇 650 次 `custom_tool_call(exec)` 里有 **41 次**是在查 `--help` 或 grep skill/脚本源码来确认调用格式（`ticket satisfy --help`、`evidence add --help`、grep `impl_package_state.py`/`command_groups.py`/`situations.yaml` 等），其中 L7510-7578（第 4 节）是对 L6959-7019 已经摸索过的同一套 evidence 用法的**重复摸索**，直接原因是中间隔了一次 `compacted`（L7246）。改法：把已验证成功的 CLI 调用模板（尤其是 `evidence add` 单条/`printf '<...>' | ... evidence add` 批量数组这两种形态）作为固定 cheatsheet 写进 `execution-findings.md` 或 trail 里，需要时直接读文件而不是重新 `--help`/grep 源码；compaction 时优先保留"已验证可行的命令模板"而不是把它们压缩进叙述性摘要。
3. **evidence 批量登记机制存在但从未被正确调用（见第 4/6 节），是本 slice 里代价最集中的单一改造缺口。** 09-10～09-13 已经把 `impl_package_state.py evidence add` 改造成支持"单对象或非空数组 JSON"，官方推荐写法是 `printf '<json>' | python impl_package_state.py ... evidence add`，但本 slice 的唯一一次批量尝试（L6979/L6985）用了更脆弱的 PowerShell `$items=@(...)` 现场拼数组，两次都失败后放弃、退回逐条注册。改法：既然 CLI 已原生支持数组，dispatcher/dev-with-track 的调用范例应该直接给出这行 `printf` 命令模板（而不是只在 situations.yaml 里一处出现，容易在长会话里读不到），降低主控现场发明拼接方式的概率。
4. **`followup_task` 的参数拼装本身不够稳，4 次里有一次连续失败 4 回才成功。** L3477/L3483/L3489/L3495 连续 4 次 `followup_task` 调用因为 JSON 字段名/引号错误被环境直接拒绝（`unknown field` / `missing field message`），直到 L3501 第 5 次才成功，耗时约 22 秒。虽然单次代价很小，但这类"工具调用参数格式本身不稳"的失败在整批 8 个 worker 的 rollout 里如果是共性，值得在 dispatcher 或工具描述里补一个固定的 `followup_task({target, message})` 调用范例，减少现场拼错的概率。
5. **`git status --short` / `git diff --stat` 例行自检次数较多（≥8 次），是流程开销而非重复劳动，但仍有压缩空间。** 这类自检发生在几乎每次消费 worker 返回前后（L425/462/600/1224/1293/1299/1305/1312/1730/1820/2932/3372/4076 等），单次很轻（1-2 秒），但累积起来也占了一部分 exec 调用配额。改法：可以只在"即将做有副作用的操作（commit/派下一个 worker）之前"做一次核验，而不是每次消费 return 都重复跑一遍，尤其是相邻两次自检之间明知没有其他并行 worker 修改过工作区时。
