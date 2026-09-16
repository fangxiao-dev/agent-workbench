# W5 分析报告 — 两个并行设计阶段 session

- F1 = `rollout-2026-09-12T19-04-22-01a09693-c83f-7930-b0fd-238c27226854.jsonl`（283 行，cwd `worktrees\3617`，#304 Edge Agent/Test Harness 拆分）
- F2 = `rollout-2026-09-12T19-04-22-01a09693-c844-7121-8972-54036990f657.jsonl`（2042 行，cwd `worktrees\4afb`，JP-308 configurable Original Training）

行号格式：`F1:123` / `F2:456`，均为原始 jsonl 1-based 行号，已逐条用 Python 抽取原文验证。

---

## 1. 会话事实（先算数字，再写判断）

### 1.1 时间跨度与轮次

| 指标 | F1 | F2 |
| --- | --- | --- |
| 首条 timestamp | 2026-09-12T17:04:24.182Z | 2026-09-12T17:04:24.033Z |
| 末条 timestamp | 2026-09-12T17:49:01.094Z | 2026-09-12T19:35:55.993Z |
| 时钟跨度 | 44分37秒 | 2小时31分32秒 |
| user turn 数（含系统/skill 注入消息） | 5（F1:6,214,237,251,279） | 14（F2:6,552,564,613,715,738,752,777,823,835,1067,1240,1758,1760） |
| 真人自然语言 turn 数（剔除系统注入） | 4 | 13 |
| assistant message 数 | 9 | 48 |
| compacted 事件数 | 0 | 1（F2:1511，19:18:54，紧跟在 full_review_config_plan 第一次返回 revise 之后） |
| 结束方式 | turn_aborted（F1:283，用户在说完"去 req-align"后主动打断当前 turn，session 到此为止，续篇在另一个未在本 slice 范围内的文件） | 正常收尾（handoff 完成后 assistant 最后一条消息 F2:2039，无 turn_aborted） |

### 1.2 协作工具调用次数（仅统计 type=response_item 且 payload.type=function_call，不含 event_msg 里的重复回声）

| 工具 | F1 | F2 |
| --- | --- | --- |
| spawn_agent | 0 | 5 |
| wait_agent | 0 | 17 |
| send_message | 0 | 9 |
| followup_task | 0 | 2 |
| interrupt_agent | 0 | 0 |
| list_agents | 0 | 4 |
| request_user_input | 0 | 0 |
| create_thread（作为 function_call_output，见1.5） | 1（F1:10） | 1（F2:10） |
| send_message_to_thread（作为 function_call_output） | 0 | 10 |

F1 全程零协作工具调用：45 分钟内没有 spawn/wait/send_message，只有 25 次 custom_tool_call(name=exec)（本地 shell/glab/web 检索）和纯对话。这与 prompt 提示的"45 分钟内没有任何工具调用之外的东西吗"完全对应——F1 的设计决策收敛不是靠子代理调研，而是靠用户在 F1:214 直接贴出一份完整的"已确认 8 项决策 + 3 个待确认"清单，agent 全程只做解释（F1:237 起）和确认（F1:251、F1:279），从未主动发起过一次 spawn_agent。

### 1.3 spawn_agent 的 agent_type 分布（F2）

全部 5 次 spawn_agent 的 agent_type 均为 luna-worker（100%），没有 frontend-worker / backend-worker / 默认同 profile agent / 其他类型：

| 行号 | task_name | 时间 | 用途 |
| --- | --- | --- | --- |
| F2:633 | inspect_original_training_bounds | 17:52:06 | 只读调研原始仓库的训练参数取值范围 |
| F2:998 | config_grill_questioner | 18:26:13 | Grill 流程提问方 |
| F2:1004 | config_grill_answerer | 18:26:24 | Grill 流程回答方 |
| F2:1256 | ponytail_review_config_package | 18:47:07 | 独立精简审阅（ponytail-review） |
| F2:1463 | full_review_config_plan | 19:00:01 | plan-review 全量审阅 |

followup_task 复用同一 agent 共 2 次：config_grill_questioner 被 followup 1 次（F2:1207，18:43:42），full_review_config_plan 被 followup 1 次（F2:1701，19:24:10）。没有任何 agent 被 followup ≥2 次，也没有观察到"降智"迹象——两次 followup 后的回复都在合理时长内给出结构化结果（config_grill_questioner 二次收敛于 F2:1243；full_review_config_plan 二次审阅于 F2:1729 给出 clear）。

### 1.4 并发度

按 spawn_agent → FINAL_ANSWER/超时重建生命周期：

- inspect_original_training_bounds：F2:633（17:52:06）到 F2:678 FINAL_ANSWER（18:05:17），独立运行，期间无其他 agent。
- config_grill_questioner + config_grill_answerer：F2:998/F2:1004（18:26:13~24）到分别在 F2:1243（18:46:39）/F2:1142（18:40:47）+F2:1194（18:43:20）收尾，这是本 slice 唯一出现 2 个 agent 同时在途的窗口（18:26:24~18:46:39，约 20 分钟），list_agents（F2:1042，18:30:24）证实两者同时 running。
- ponytail_review_config_package：F2:1256（18:47:07）到 F2:1271（18:52:11），独立运行。
- full_review_config_plan：F2:1463（19:00:01）到首次 F2:1500（19:17:22），followup 后 F2:1729（19:26:46），独立运行。

同时在途 agent 数分布：多数时间 = 1（4/5 个任务都是单独运行），仅 1 段时间 = 2（grill 问答对）。全程未出现 3 个以上并发。

### 1.5 等待占比

F2 中所有 wait_agent 调用（call到result）累计等待时长约 53 分钟，占 F2 总时钟跨度（151 分钟）的约 35%。最长的连续"只等待、主控未动手"区间：

- F2:1471~F2:1497（19:00:06~19:12:11，两次 wait_agent 各 6 分钟超时 + 一次 5 分钟等到结果，共约 17 分钟），期间只有 wait_agent/list_agents 交替，无任何 shell 命令——对应 full_review_config_plan 第一轮审阅。
- F2:643~F2:675（17:52:12~18:05:17，约 13 分钟，两次 6 分钟超时 + 最后等到），对应 inspect_original_training_bounds 调研。

F1 因为没有任何 wait_agent，等待占比 = 0（agent 全程自己执行 shell/对话，没有派发也就没有等待）。

### 1.6 shell 命令分类计数

以 custom_tool_call(name=exec) 为单位统计，F1 全部 25 次都是主控自己直接执行（无子代理）；F2 的 190 次里有 34 次是纯 apply_patch 文件编辑（不含 shell cmd）、33 次是浏览器/mcp 调用（无 cmd 字段），其余含 cmd 字段的片段用正则抽取分类：

| 类别 | F1（31条cmd片段） | F2（124条cmd片段） |
| --- | --- | --- |
| pytest/测试 | 0 | 0 |
| git | 10 | 52 |
| impl-package 语义 CLI（state.py/ticket/gate/package 等） | 0 | 23 |
| 构建/typecheck | 0 | 0 |
| 容器/服务 | 8（注：均是 web__run 检索 NATS JetStream 官方文档命中关键字"nats"，并非真实启动容器/服务，F1 全程没有真实服务操作） | 1 |
| 其他（Get-Content/git grep/glab/Select-String 等只读探查） | 13 | 48 |

两个 session 都零 pytest/测试执行、零构建/typecheck——这是设计阶段（req-align/impl-planning/to-tickets）应有的形态：不写代码，只读探查+写文档。

evidence 登记：单条 vs 批量——F2 全程 0 次 evidence add 调用（无论单条还是批量）；唯一一次字符串命中"evidence"关键词的命令（F2:1935）实际是 git commit 消息正文里出现"evidence"单词，非真实的 evidence CLI 调用。这与设计阶段的性质一致：evidence 登记发生在 dev-with-track 执行阶段，本 slice 两个 session 都止步于 to-tickets/handoff-to-new-session，从未进入执行阶段，因此该项框架指标在此不适用。

### 1.7 重复执行

F1：无重复命令（25 次 exec 各不相同，都是首次探查不同文件/接口）。

F2：把 apply_patch 计入后，唯一稳定命中"同一条命令跑了 3 次以上"的是 F2:1824 / F2:1863 / F2:1905，命令均为调用 impl_package_state.py（不同子命令：package init 缺参数报错到查看 --help 到再次调用），这是同一条 CLI 的探索式试错（先不带参数看 usage，再补参数），不是同一输入重复跑——输入在变化，不构成"重复执行"。除此之外没有发现真正意义上"同输入被重复跑 3 次以上"的验证命令。

---

## 2. 清单 A 逐条判定 · 执行阶段设计意图

本 slice（F1、F2）两个 session 都止步于设计阶段（req-align 到 impl-planning 到 to-tickets 到 handoff-to-new-session），从未进入 dev-with-track/do-review 执行阶段，因此清单 A 里绝大多数条目（delta review、evidence 批量登记、ready≠dependency 的实际执行、worktree 隔离用于并行实现、interrupt_agent、汇报 worktree/branch/comparison head 等）没有可判定的现场。以下只填有证据的条目，其余统一标"本 slice 无相关场景"。

1. 角色≠载体：本 slice 无相关场景。F2 的 5 次 spawn 全部是 luna-worker（研究/审阅角色），没有出现 impl/fix/frontend/backend 角色，因此"同一角色按需并行开多个 worker"无法判定。
2. 派发用了正确 profile：已执行。F2 全部 5 次 spawn 都用 luna-worker（AGENTS.md 全局默认，F2:7 world_state 内文本"默认使用 @luna-worker（luna/max）"），且 F2:613 用户明确建议"按需使用 @luna-worker"后，agent 才在 F2:633 发起唯一一次调研派发，没有出现"与主控同 profile 的默认 agent"。
3. ready≠dependency：本 slice 无相关场景（这是执行阶段语义，F2 止于 handoff，TKT-02 从未进入实际开工判断；相关的 Ticket 依赖粒度写法见清单 B 第 3 条）。
4. 没有因授权/formality 停下来问用户：已执行。全 slice 未观察到一次"因为授权/形式化原因暂停"，唯二的两次真正停下来都是方案本身需要 owner 决策：F2:752（response annotation，询问"部分 overrides"语义是否同意）、F1:214到F1:237/251（用户主动贴出决策清单，非 agent 主动叫停）。
5. 每个含代码 return 派了独立 delta review：本 slice 无相关场景（F1、F2 均未产出代码，无 code return）。
6. evidence 登记走批量：本 slice 无相关场景（见1.6，全程0次 evidence CLI 调用）。
7. 局部 barrier：本 slice 无相关场景（无执行阶段并行候选）。
8. 没有无正当理由中断 worker：已执行（正向）。F1、F2 全程 interrupt_agent = 0 次，5 个 spawn 的 agent 都跑到自然结束（FINAL_ANSWER）或被 followup_task 续接，没有一次中途打断。
9. 收尾动作没有挡住主线交付：已执行。F2 的收尾（commit、handoff 双阶段消息）只花了约 7.7 分钟（F2:1758到F2:2039，见4.4），未见收尾动作本身造成额外返工。
10. worker 有自己的 worktree：本 slice 无相关场景（5 个 luna-worker 都是只读调研/审阅任务，没有涉及写文件，未观察到 worker 侧 worktree 分配信息——spawn_agent 的 arguments 里没有 worktree 字段，且这些任务性质本身不需要独立工作区）。
11. 主控 context 卫生：已执行。F2 明确把"长审阅"外包给 luna-worker：ponytail_review_config_package（F2:1256，5 分钟审阅产出 9 条精简建议）、full_review_config_plan（F2:1463，17+2.5 分钟两轮审阅）都是主控只等结果（wait_agent）、只读最终 FINAL_ANSWER 摘要（F2:1271、F2:1500、F2:1729），没有把审阅过程中的原始探查输出读进主控自己的上下文。
12. 子代理没有越权：已执行。5 个 luna-worker 的 FINAL_ANSWER 都严格落在被交代的任务范围内（调研数值来源、grill 问答、精简审阅、plan 审阅），裁决权（是否采纳、是否需要 owner 决策）始终留在主控手里——例如 F2:1281 主控明确写"独立 ponytail-review 给出 9 项，主控采纳 8 项"，是主控做取舍，不是子代理自己决定要不要改。
13. 汇报形态：部分执行，偏正向但有个术语瑕疵。F2:2039 最终汇报给用户："已完成提交与新 session 交付；handoff 已 closed...Commit：1f3186170d7f6ed1793868a29bd20149885ae6b2"——清楚给出了 commit hash；但没有显式点名 worktree 路径或 branch 名（用户如果不追问看不到 worktrees\4afb 这个物理位置），也没有使用让用户看不懂的内部术语（比如没有出现"业务比较点"这种黑话），措辞总体是自然语言。
14. 跨 session 通信：已执行，且做得比较克制。create_thread（F2:10，会话被上级创建时的回声）+ 主控自己发起的 create_thread（F2:1982，创建下游执行 session）+send_message_to_thread（F2:2011，发送 continuation）共 2 次主控发起的跨 session 通信，都直接对应用户在 F2:1758 的显式指令"批准，提交，然后去新 session...正式开始实现"，没有观察到多余的、未被要求的跨 session 汇报。
15. model/profile 档位：本 slice 无相关场景。F1、F2 全程用户从未给出过"luna/max"或"sol/medium"这类显式降级指令，因此无法判定"后续派发有没有遵守降级"。（F2:1963 读到的主控自身模型是 gpt-5.6-sol + reasoning_effort: high，是会话默认值，不是用户临时降级指令。）
16. 长寿命 subagent：已执行（正向，未发生）。见1.3，followup 最多 1 次，没有观察到输出退化的证据。

---

## 3. 清单 B 逐条判定 · 设计阶段设计意图

### 3.1 req-align：fast path 还是 Decision/Spec gate；写材料 vs 定位业务问题的时间分配

F2 走的是完整的 Decision/Spec gate，不是 fast path：从用户 F2:738（18:10:01，"同意，还有什么需要讨论的嘛？没有的话 $req-align"）到 agent 在 F2:1399（18:56:11）宣布"Req-align 已收口：Decision/Spec/contract-design 3/3 完成，Grill 10/10 收敛，Ponytail 8/9 建议已吸收，blocking decision 为 0"，共约 46 分钟。这 46 分钟里：

- 约 8 分钟（18:10~18:18）是响应用户的 response annotation（F2:752，询问"部分 overrides"语义）和"不要复用用新包"的纠偏（F2:823，见3.5）；
- 约 20 分钟（18:26~18:46，F2:998~F2:1243）是派 config_grill_questioner/config_grill_answerer 做独立对抗式收敛（10 个问题 R1-Q1..R1-Q10，全部收敛，0 pending）；
- 约 9 分钟（18:47~18:56）是 ponytail_review_config_package 精简审阅 + 主控采纳并应用编辑。

也就是说，"写材料"本身（改 decision.md/spec.md/contract-design.md 的具体 apply_patch 次数）散布在整个过程里，真正用来"定位业务问题"（grill 问答 + 精简审阅）占了约 63%（29/46 分钟）的 req-align 时间——这是一个业务验证密度较高的 req-align，不是走过场。

F1 相反：从 F1:214（用户贴出决策清单）到 F1:279（"没有对齐的就开始 req-align"）只用了约 13 分钟（17:36~17:49），而且这 13 分钟里 agent 没有做任何独立验证（没有 spawn grill/ponytail），纯粹是解释+确认用户已经想好的方案。F1 甚至没能真正开始 req-align 就被 turn_aborted（F1:283）——所以 F1 在本 slice 范围内没有真正走完 req-align，无法比较其 fast path/gate 选择。

### 3.2 Spec 范围识别：修改范围 vs 兼容性验收范围

F2 的 ticket 01 文本（F2:1440 patch 内）明确写了"AC-10 的 #309 兼容性验收"曾被 ponytail-review 建议删除（"delete: AC-10's #309 compatibility acceptance. #309 owns consumer compatibility; AC-08/AC-09 prove this package's artifact completeness"），最终被采纳——即 agent 主动在设计材料里区分了"本包该证明什么"（artifact 完整性）和"下游消费者兼容性该由谁证明"（#309 单独 own），没有把兼容性验收范围混进本包 Spec。这是清单 B 第 2 条要求的"区分修改范围与兼容性验收范围"的正向例证（F2:1271 ponytail 输出中的 spec.md:L265 条目）。

F1 本 slice 未进入 Spec 编写阶段，无法判定。

### 3.3 impl-planning/to-tickets：Ticket 依赖粒度——implementation 还是 acceptance

关键证据：F2:1440（apply_patch 创建 tickets/02-propagate-config-into-real-training-artifacts.md）里 TKT-02 的依赖段原文是：

    ## Blocking dependencies
    - implementation: TKT-01

同一个 patch 里紧接着写道："Execution is linear at the integration boundary because TKT-02 consumes the canonical persisted output of TKT-01. Child-local tests may be prepared early, but no TKT-02 implementation or acceptance claim..."（F2:1440）。

即：依赖粒度被显式标注为 implementation:，不是 acceptance:——这是一个真实的数据/集成依赖（TKT-02 要消费 TKT-01 落盘的 snapshot），agent 同时留了口子允许"child-local 测试可以提前准备"（不是完全锁死，只锁"完整实现/验收 claim"）。这与本轮框架背书的用户原话"Ticket 的 ready 只是 ticket 粒度，不是执行 dependency，可以提前调研甚至先做无依赖的 lane"并不矛盾——因为这里锁的不是"grooming/调研"，而是"TKT-02 的实现产出物在 TKT-01 落盘前物理上不存在"，是一个真实的数据依赖，不是形式主义的 gate。

同时官方语义 CLI 的 readyTickets 输出（F2:1908："readyTickets": ["TKT-01"]）与 ticket 正文的 implementation: TKT-01 依赖描述是一致的——TKT-02 没有出现在 readyTickets 里。

（Prompt 提到执行阶段 W7 slice 用户在下游 session 问"既然没有阻塞了，是否可以开始先做 ticket 02"——那个问题发生在下游执行 session，不在本 F2 范围内；但从 F2 自身的 ticket 文本看，根源不是"设计阶段随意加了限制"，而是这条 implementation: 依赖本身就是一个真实集成边界，是否该在执行阶段允许"child-local 测试提前做"是下游的判断题，不是本 slice 该纠偏的对象。）

### 3.4 验收设计有没有过度收集

F2 的 plan candidate 在 F2:1462 汇报"2 个 Ticket、22 个唯一 stable claims"。plan-review 审阅（full_review_config_plan）第一轮返回 revise（F2:1500），说明存在需要修正的地方；agent 据此在 F2:1613~F2:1715 做了多处 ticket AC 编辑（可见的编辑点包括 TKT-02-AC-7-realized-lifecycle 拆成 TKT-02-AC-7-realized-persistence + TKT-02-AC-8-stale-realized-suppression，以及把 TKT-02-AC-9-real-flow2 合并进 TKT-02-AC-10-real-flow2-terminal），第二轮返回 clear（F2:1729，"Material findings: 0"）。这说明过度收集在第一轮确实存在（同一个 stable claim 被拆得过细或有遗漏合并的机会），经审阅后被修正——审阅本身发挥了它该发挥的作用，不是走过场。

### 3.5 用户纠偏：约束/默认值来源、复用旧包 vs 新包

- F2:564（"这些值是哪里来的参考？"）到 agent 提出的默认值来源不可追溯，触发 F2:613 用户建议派 luna-worker 去原始仓库核实，agent 在 F2:633 派出 inspect_original_training_bounds，最终 F2:678 返回"EVIDENCE_SUFFICIENT"。默认值来源问题被真实地补上了证据链，不是靠猜。
- F2:715（"除了组合关系以外，有必要做这个限制嘛？...没必要额外花功夫去限制，如果未来要改还得维护"）到 agent 此前在 Spec 里给某些配置值加了额外的取值范围限制，用户纠偏"没必要额外限制、增加未来维护成本"，这是清单 B 第 5 条明确要求分析的"agent 引入了不必要限制"的直接证据。
- F2:823（"不要复用，用新包"）到 agent 在 F2:802~F2:821 探查了一个既有的、不相关的 implementation package（2026-09-10-multi-label-per-label-space）的 decision.md，似乎在评估是否可以复用其结构/内容，用户当场否决，明确要求新建独立包。agent 随即在 F2:828 确认"不复用任何现有 implementation package"。

### 3.6 独立审阅的成本与实际采纳率

| 审阅 | 派发到FINAL_ANSWER耗时 | 提了几条 | 采纳几条 |
| --- | --- | --- | --- |
| ponytail_review_config_package（F2:1256到F2:1271） | 约5分4秒 | 9条（均为delete/shrink类精简建议） | 8条（F2:1281:"主控采纳8项；唯一不采纳的是..."），采纳率89% |
| full_review_config_plan第一轮（F2:1463到F2:1500） | 约17分21秒 | verdict=revise（未单独列条数，但触发了F2:1613~1715多处AC拆分/合并编辑） | 编辑被应用后二轮通过 |
| full_review_config_plan第二轮（F2:1701到F2:1729） | 约2分36秒 | verdict=clear，Material findings: 0 | 无 |

两种审阅的成本效益都不错：ponytail 花 5 分钟换来 9/9 条具体、可执行、有行号定位的精简建议，8 条被直接采纳；plan-review 花约 20 分钟（两轮合计）换来一次真实的 AC 粒度修正，避免了验收粒度错误被带进执行阶段。没有发现"审阅了但没被采纳/审阅走过场"的证据。

### 3.7 handoff-to-new-session：耗时、重复度、canonical ready ticket 是否被保留

从用户指令 F2:1758（19:28:15）到最终汇报 F2:2039（19:35:55），共约 7 分 40 秒。设计是两段式：

1. create_thread（F2:1982，19:33:16）只做"anchor 检查"：给下游 session 的 prompt 只包含 worktree 路径、expected HEAD、authority/entry 文件路径，明确要求"本轮只在上述 worktree 做只读 anchor 检查...不要读取恢复记录或开始工作"——刻意不在第一条消息里塞完整上下文。
2. send_message_to_thread（F2:2011，19:34:31）等下游回报 anchor PASS（F2:1999）后才发送完整 continuation：authority/entry 路径、checkpoint（commit hash + package validate 状态）、canonical readyTickets=["TKT-01"]、authorization/blocker（"Owner 已批准...named blockers=none"）、WIP 保护提示、外部边界（push/merge/部署仍需单独授权）、下一步用哪些 owning skill（execution-boundaries 到 dev-with-track）。

两条消息之间只有 worktree/authority 路径这类必要的校验性重复（先验证环境对不对，再喂完整状态），没有观察到"重复交代同一批已有事实"的浪费；canonical readyTickets（["TKT-01"]）被完整保留并传递到下游，这是 prompt 里提到"这项设计从未被实战检验过"的关键点——本次实战验证是成功的：readyTickets、checkpoint commit、blocker 状态都被一次性、准确地带到了下游 session。

### 3.8 设计阶段的 subagent 使用：派发时机是 agent 主动还是用户提示

四次里三次是用户先提示、agent 才照做：

- inspect_original_training_bounds（F2:633）：用户先在 F2:613 说"我建议去原始仓库看一下，按需使用 @luna-worker"，agent 随后派发。
- ponytail_review_config_package（F2:1256）、full_review_config_plan 的审阅动作：用户在 F2:1240 明确要求"单独 subagent 审阅 [$ponytail-review]...如果你可以审视后觉得有道理则采用，然后继续 [$impl-planning]"，两次 spawn 都是执行这条指令。

唯一看起来像 agent 主动决定的是 config_grill_questioner/config_grill_answerer（F2:998/1004）——这是 req-align skill 本身内置的 Grill 收敛流程（不是用户临时提示），属于"skill 规定要做"而非"agent 灵机一动"。没有观察到 agent 在没有 skill 规定、也没有用户提示的情况下，自主决定派发子代理去查资料。

---

## 4. 绕远路事件表

| 触发行号 | 类型 | 现场描述 | 代价 | 一步到位应该怎么做 |
| --- | --- | --- | --- | --- |
| F2:1824到1827 | 形式化无业务收益 | package init 时被官方语义 CLI 拦住：Plan 里写的是语义正确的 Predecessors: None，但状态工具要求固定标签"前置包（Predecessors）"，报错"plan must declare 前置包（Predecessors）exactly once"。agent 随即在 F2:1835 定位模板、F2:1856 打 patch 改成固定标签。 | 约5分钟（19:29:18到19:29:52，F2:1824~1859），4次shell调用 | CLI 的错误信息应该直接给出期望的精确字符串（"前置包（Predecessors）"）而不是让 agent 反查模板文件才能猜出固定标签；或 CLI 本身兼容英文 Predecessors: 写法，不强制中文标签精确匹配 |
| F2:1863到1866 | 形式化无业务收益 | 紧接上一条，package init 又报"Ticket TKT-01 has no stable claim IDs"，agent 需要再查 engine.py 源码定位 stable claim ID 的正则要求（F2:1877~1894），然后才能改对 ticket 正文格式。 | 约4分钟（19:29:52到19:31:06，F2:1863~1894），5次shell调用 | 同上：CLI 报错应直接给出"缺少形如 Stable claim ID: ... 的行"这类可执行提示，而不是让 agent 翻源码猜格式 |
| F2:1319/1325/1352 | 工具环境失败 | 应用 ponytail-review 的编辑建议时，3 次 apply_patch 因为上下文行没匹配上而失败（"Failed to find expected lines"/"invalid hunk"），agent 重新读文件片段（F2:1296~1313）后才改对。 | 约1分钟（18:53:20到18:54:31），3次失败重试+3次读文件 | 应用建议前先用 Select-String/Get-Content 精确锚定要改的原文片段再生成 patch，而不是凭 ponytail 输出里给的粗略行号直接猜 hunk 内容 |
| F2:1471~1497 | 等待串行 | full_review_config_plan 第一轮审阅耗时约17分钟（两次6分钟超时+1次等到），期间主控没有做任何其他工作（既没有并行推进别的独立任务，也没有主动检查进度以外的事）。 | 17分钟时钟，0turn推进其他工作 | 17分钟的独立审阅期间，主控本可以并行做一些不依赖审阅结果的收尾准备（比如提前核对 commit 前置条件、准备 handoff 素材），而不是纯粹串行等待——不过这属于"能不能榨出更多并行度"的优化建议，不是错误 |
| F1:279到283 | 汇报不清（偏结构性，非agent责任） | 用户刚说完"没有对齐的就开始 req-align"，agent 的响应刚开始（F1:280 item_completed）就被 turn_aborted（F1:283）——F1 session 在真正进入 req-align 之前就结束，后续工作在另一个未纳入本 slice 分析范围的续篇文件里进行。 | 该session损失的时间无法计入agent效率问题（是外部主动切换session，不是agent卡住），但造成"设计决策已经收敛却没能在本文件内看到req-align落地"的分析盲区 | 不适用（这是用户主动的session切换动作，不是agent该改进的地方；仅记录以避免误判"F1没做完req-align是agent的问题"） |

说明：本 slice 两个 session 整体绕远路的绝对代价都不大——F2 最大的一笔（两次 CLI 格式报错共约9分钟）发生在设计阶段收尾时的 package init，属于"官方语义 CLI 的报错提示不够可执行"这一类工具体验问题，不是 agent 决策失误；没有发现"打补丁式返工""先做后推翻""派发拓扑错误""重复取证"类型的绕远路事件。

---

## 5. 用户纠偏事件

| 行号 | 用户原话摘要 | agent当时在做什么 | 暴露的问题 |
| --- | --- | --- | --- |
| F1:237 | "第一个再解释一下，后两个我同意" | 刚汇报完对用户8项决策清单的理解/确认 | 不是纠偏，是正常的澄清请求；说明agent第一次复述某项决策时不够清楚，需要用户追问才讲明白 |
| F1:251 | "同意，另外，edge agent 是否改成 edge client 更好？" | 已经进入确认阶段 | 命名建议，非规则缺失；用户在最后一刻还在调整命名，说明前面的收敛过程没有把命名分歧提前暴露出来讨论 |
| F2:564 | "这些值是哪里来的参考？" | agent刚提出一批默认配置值（如学习率/PCA相关的取值范围建议） | 暴露"agent提出默认值时没有主动标注证据来源"——规则缺失：agent给数值建议时应该像给结论一样自带引用，而不是等用户反问才去查 |
| F2:613 | "我建议去原始仓库看一下，按需使用 @luna-worker" | 刚被问到值的来源、尚未主动核实 | 同上，用户在补agent没做的动作（主动派发调研）；不是规则没写（AGENTS.md里确实写了默认用luna-worker做调研），而是agent没有主动触发这条规则，靠用户提醒才想起来用——这是"规则写了但没被主动遵守"的一个例子 |
| F2:715 | "除了组合关系以外，有必要做这个限制嘛？我们可以把当前的值作为默认/推荐值，但我感觉也没必要额外花功夫去限制，如果未来要改还得维护" | Spec草案里给某些配置字段加了额外的取值范围硬限制 | 直接对应框架里的用户原话规则"没必要额外限制、增加未来维护成本"；这条规则在框架背景里是本轮最强信号之一，但从F2的现场看，agent在设计Spec时依然默认倾向"加约束更安全"，规则没有被内化，靠用户当场纠偏才拿掉 |
| F2:752（response annotation） | "为什么必填？其他字段不是直接填上，而是通过'预览举例'的形式填上...我不认为应该预填参数" | agent提出"inputNormalization必填，其他字段可用推荐默认值省略"的方案 | 同一类"平台不应该帮用户预填默认值"的立场，与F2:715是同一条规则的两次重复触发——说明这条"别加不必要默认/限制"的偏好，agent在同一个req-align会话里被纠正了至少2次，还没有变成agent自己的默认判断 |
| F2:823 | "不要复用，用新包" | 正在查看一个既有的、不相关的implementation package的decision.md，似有复用其结构的意图 | 对应框架里"不是每次都要复用旧包"的原则；F2:823是本slice里唯一一次关于"复用vs新建"的纠偏，只出现1次，尚不能判断规则是否已经被agent吸收 |
| F2:1067 | "agents之间是可以直接通信的把 collaboration.send_message" | 当时正在通过主控中转config_grill_questioner和config_grill_answerer之间的消息（主控收到一方的输出后手动send_message转给另一方，见F2:1033/1073/1078/1094/1101等） | 暴露"agent不知道/没有使用子代理间可以直接通信的能力，全部消息都要走主控中转"。查看F2:1067前后的send_message调用目标（target字段），提示前后主控确实一直是手动转发（target: /root/config_grill_answerer 和 target: /root/config_grill_questioner 交替出现），提示之后同一批grill流程仍然继续由主控转发（F2:1073、1078、1094、1101都还是主控发的send_message，不是子代理直接互相collaboration.send_message）——这条提示在本slice内没有被落实到行为变化上，可能是因为grill流程本身就设计成"主控做仲裁中转"（每次转发前主控会看一眼内容），也可能是agent没有意识到可以让子代理直接互聊。需要在下游/其他session里确认这条能力有没有真正被用起来 |

重复度统计：框架强调的"角色不是载体"这条规则在本slice没有被触发（F2全程只用了luna-worker这一种角色，没有出现impl/fix/frontend/backend的载体化误用），所以无法评估"该规则是否已被写入skill正文并被主控读到"。但"别加不必要默认值/限制"这条规则被用户在同一个F2 session里重复纠正了至少2次（F2:715、F2:752），说明这条偏好还没有变成agent在设计Spec阶段的默认直觉，值得考虑写进req-align或相关skill的正文提醒里。

---

## 6. 规则加载核对

### 6.1 dispatcher 正文与 Implementer executor 段

D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md 第20~25行确实存在"Implementer executor"段，列出 frontend-worker/backend-worker 两个具象 profile。

但是——dispatcher 的 SKILL.md 正文在 F1、F2 全程都没有被以 <skill> 块注入过（对两个文件分别搜索 <name>dispatcher</name> 均为0命中）。原因是合理的：dispatcher 是"派发实现worker"的调度入口，只在 dev-with-track 执行阶段才会被加载/调用，而 F1、F2 两个 session 全程止步于设计阶段（req-align/impl-planning/to-tickets/handoff），从未进入需要挑选implementer profile的场景，因此dispatcher没有被加载不是bug，是阶段未到。这也解释了为什么F2全部5次spawn都是luna-worker——不是"忘记了frontend/backend-worker的存在"，而是这个slice压根没有触发需要它们的场景。

### 6.2 impl-package 各 skill 的加载与 cache 版本核对

用户在 F1:279、F2:738、F2:1240 引用的 $impl-package:req-align、$impl-package:impl-planning、$ponytail:ponytail-review 三个链接，都没有自动触发 <skill>...</skill> XML块注入（对F2全文搜索 <name>req-align</name>/<name>impl-planning</name>/<name>ponytail-review</name> 均0命中）；agent是靠自己手动执行 Get-Content/Select-String 去读取 C:\Users\Xiao\.codex\plugins\cache\...\SKILL.md 文件内容的（例如F2:798读取req-align的reference材料）。只有 handoff-to-new-session（F2:1758引用的仓库路径 D:\CodeSpace\agent-workbench\skills\handoff-to-new-session\SKILL.md，不在plugin cache里而是直接指向仓库工作区）在下一条user message（F2:1760）被自动注入了 <skill> 块。

推测：Codex对"插件市场安装的plugin skill（.codex\plugins\cache\...）"和"直接指向仓库工作区的skill文件路径（D:\CodeSpace\agent-workbench\skills\...）"采用了不同的引用解析机制——只有后者会被自动展开注入，前者需要agent自己去读文件。这与框架预设的"用户消息里[$dispatcher](...)之类引用会把skill正文以<skill>...</skill>块注入"不完全一致：至少对plugin-cache里的impl-package/ponytail系列skill，自动注入没有发生。

cache版本核对：直接diff C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\skills 与仓库 D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\skills，结果完全一致（0差异），且plugin.json声明的版本号同为0.4.2——本slice使用的cache版本与仓库当前版本没有漂移，evidence批量、delta review一名reviewer等最新规则（如果已经写进0.4.2）在本slice理论上是可读到的最新版本；只是因为F1/F2从未进入执行阶段，这些规则条目本身没有被实际触发验证。

### 6.3 spawn 时的 agent_type 与已加载规则是否一致

F2全局AGENTS.md（F2:7 world_state，"默认使用@luna-worker（luna/max）"）与实际5次spawn_agent的agent_type=luna-worker完全一致；且用户在F2:613显式点名"@luna-worker"，进一步确认了这条默认规则被正确遵守，没有出现"该用frontend/backend-worker却仍用luna-worker"的错配场景（因为本slice根本没有前后端实现任务）。

---

## 7. 新发现的可优化点

按预计节省时间排序（次数是线索，不是结论）：

1. 官方语义CLI的报错信息不可执行，迫使agent反查源码/模板（F2:1824~1866，两次报错共约9分钟，4+5=9次shell调用）。改成"报错信息直接给出期望字符串或指向模板文件路径"，或者放宽中文固定标签的精确匹配（接受英文Predecessors:），可以直接省掉这9分钟和9次探查调用。这是本slice里单笔代价最大的可优化点。
2. agent提出数值/默认值建议时不主动标注来源，等用户反问才去核实（F2:564到613到633，从提问到派发调研间隔约1分38秒，调研本身花了13分钟）。如果agent在第一次提出配置默认值建议时就同步给出来源引用（或主动标注"待核实"），可以省掉一整轮"用户反问到用户建议派工到agent才派工"的来回，直接把13分钟调研提前到第一次提案里做完。
3. 主控在grill流程里手动中转子代理间消息（F2:1033/1073/1078/1094/1101等至少5次send_message转发），用户在F2:1067提示"agents之间可以直接通信"后没有观察到行为变化。如果grill的两个子代理可以用collaboration.send_message直接互聊，主控只需要偶尔抽查而不是每条都手动转发，可以省掉这至少5次转发动作里主控读取+转述的开销（虽然单次开销不大，但贯穿整个grill阶段，是本slice里出现频率最高的一类可省动作）。
4. 应用外部审阅建议（ponytail-review）时3次apply_patch因为行号/上下文不精确而失败（F2:1319/1325/1352，约1分钟）。审阅工具如果在给建议时同时给出可用于精确匹配的原文片段（不只是行号），可以让agent一次性生成正确的patch，省掉这3次失败重试。
5. F1全程没有一次子代理调研，设计决策收敛完全靠用户自己在F1:214把方案写全后贴给agent。这本身不是"错误"（用户愿意自己想清楚方案是好事），但从"节省用户时间"的角度看，如果agent在收到F1:214的清单后，能像F2那样主动用一次轻量级luna-worker调研去验证清单里的技术假设（比如"生产目录不得反向依赖server.*"这条约束在现有代码里是否已经有反例），可能可以在F1:237/251之前就先排除掉需要用户再解释的点，减少一轮"用户贴清单到agent追问到用户再解释"的来回。这条建议的收益不如前4条确定（F1因turn_aborted提前结束，无法验证是否真的会有反例被发现），排在最后。
