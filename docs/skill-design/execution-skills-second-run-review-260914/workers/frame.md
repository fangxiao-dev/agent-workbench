# 共同分析框架（所有 worker 用同一把尺子，不要自行改分类）

## 背景

agent-workbench 仓库（`D:\CodeSpace\agent-workbench`）维护一套 Codex skill/plugin：Impl-Package 套件（req-align / impl-planning / to-tickets / dev-with-track / do-review / backfill-stable-docs 等，安装在 `C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\`）+ Dispatcher（`D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md`，直接从仓库工作区加载）+ 若干载体 skill（call-grok、handoff-to-new-session、learn-lessons 等）。

09-06～09-08 做过一轮「打薄 + 合并」改造；09-09～09-10 做过第一次实战复盘（结论见 `D:\CodeSpace\agent-workbench\docs\skill-design\execution-skills-first-run-review-260910\next-round-handoff.md`，**开工前先读它的第 2、4、5、6 节**，尤其是 4 个 open finding OF-01..04 和「已否决、不要重提」清单）。复盘后 09-10～09-13 又落了四项：evidence 批量登记（`evidence add` 接受数组）、req-align 下游兼容性验收范围、delta review 衔接（每个代码 return 一名 reviewer 独立 delta review，不是每次都跑 formal 多轨 do-review）、有界诊断。另外 09-12 起工作区新增了「Implementer executor」：`implementer` 是逻辑角色，前后端用具象 profile `frontend-worker` / `backend-worker`（`agents/*.toml`），同一 profile 可并行派发多次；全局 `~/.codex/AGENTS.md` 规定默认 subagent 是 `@luna-worker`。

09-12～09-14 这批 rollout 是这些规则下的**第二次实战**，覆盖 3 个业务仓库、5 个任务包，其中两个包含设计阶段（req-align → impl-planning → to-tickets → handoff-to-new-session）。你要分析的就是这批记录。

用户在这批 session 里反复用同一段「调度行为补充 / 授权补充」纠偏主控，原话要点（这是本轮最强的用户意图信号，判定时以此为准）：

- impl（含前后端两个 role）、fix、call-grok、frontend-worker、backend-worker 都是**角色/身份，不是载体本身**，可按需并行创建多个
- 载体允许有自己的 worktree；业务可分割但物理文件不可分割时，开多个 wt 保证主线最高并行度，impl 和 fix 同理
- Ticket 的 ready 只是 ticket 粒度，**不是执行 dependency**，可以提前调研甚至先做无依赖的 lane——但要**先分析前置 foundation/seam 再 fan-out**，避免补丁式并行和返工
- 本产品是 poc，主控拥有本地 fixture、凭证、真实服务、github/gitlab 访问权限；**禁止一切因为授权、formality 而停止开发的行为**；只有方案不明且 Decision/Spec 无法回答时才可以停下来问
- 不是每次 return 都要跑全套 do-review；共享 foundation 重点审，但别忘了 delta review
- 长测试脚本可以包在 luna-worker 里跑，主控只要进度和结果，不要污染自己的 context
- 子代理只做被交代的事（例如只检查 CI），主控才是主控

## 你的产出

在 `<OUTPUT_FILE>` 写一份 Markdown 报告，**固定使用下面 7 个一级小节**，顺序不变。分阶段写：每完成一节立刻追加落盘，不要攒到最后一次性写。

### 1. 会话事实（先算数字，再写判断）

用脚本统计，不要靠印象。至少给出：

- 时间跨度（首末 timestamp）、user turn 数、assistant message 数、`compacted` 事件数
- 协作工具调用次数：`spawn_agent` / `wait_agent` / `send_message` / `followup_task` / `interrupt_agent` / `list_agents` / `request_user_input` / `create_thread` / `send_message_to_thread` 各多少次
- **spawn 的 agent_type 分布**（`spawn_agent` 的 arguments 里 `agent_type` 字段是明文的，`message` 是密文）：luna-worker / frontend-worker / backend-worker / 默认（与主控同 profile）/ 其他各多少次；`followup_task` 复用同一 agent 的次数分布（一个 agent 最多被 followup 多少次、存活多久）
- **并发度**：按时间重建 agent 生命周期（spawn → FINAL_ANSWER 或 interrupt），给出「同时在途 agent 数」分布（最多几个、多数时间几个）
- **等待占比**：连续只有 `wait_agent` 而没有新 `spawn_agent`／主控自己没动手的时间段，累计多长、最长一段多长
- shell 命令分类计数：pytest/测试、git、impl-package 语义 CLI（`state.py` / `situation.py` / `evidence` / `ticket` / `trail` / `gate` / `package` 等）、构建/typecheck、容器/服务、其他；其中 **evidence 登记：单条 vs 批量（数组）各几次**
- **重复执行**：同一条验证命令（归一化后）跑了 ≥3 次的，列出命令与次数，并判断输入是否变化（输入不同不算重复）

### 2. 清单 A 逐条判定 · 执行阶段设计意图

对下面每条给 `已执行 / 部分执行 / 本 slice 无相关场景 / 现场被违反`，**必须附 jsonl 行号**和一句现场描述。没有证据就写「本 slice 无相关场景」，**不许推测补齐**。判定「违反」要看动作内容，不看关键词。

1. 角色≠载体：同一角色（impl/fix/frontend/backend/grok）按需派了多个并行 worker，而不是每角色一个
2. 派发用了正确 profile：默认 `luna-worker`，前后端用 `frontend-worker` / `backend-worker`，用户指定 grok 时用 call-grok；没有派「与主控同 profile」的默认 agent
3. ready≠dependency：下游 ticket 在上游未验收时已提前调研/部分开工；同时是先分析 foundation/seam 再 fan-out，不是为并行而并行
4. 没有因授权/formality 停下来问用户；只在真正的方案决策上返回
5. 每个含代码的 return 派了独立 delta review（一名 reviewer）；没有对每个 return 都跑 formal 多轨 do-review；派不了时记了待派审欠项
6. evidence 登记走批量（数组）而不是逐条；登记没有挤占业务推进（对照用户纠偏「快速收尾不要再因为登记证据浪费时间」）
7. 局部 barrier 只扣住受影响候选；有 worker 在跑时其他互不依赖工作仍被派发（OF-01 复发检查）
8. 没有无正当理由中断 worker：每一次 `interrupt_agent` 都要单独列出，给中断理由与当时 worker 状态，判定是否符合「用户取消 / 越权或危险 mutation / 不可恢复资源冲突 / carrier 明确失败」之一（OF-03 复发检查）
9. 收尾动作（backfill / 登记 / 文档）没有挡住主线交付（OF-04 复发检查）
10. worker 有自己的 worktree（写集不能精准切割时先分 wt 再集成）
11. 主控 context 卫生：长测试/长脚本包给 worker 跑；主控没有把大段输出读进自己 context
12. 子代理没有越权（只做被交代的事）；主控没有把裁决权让给子代理
13. 汇报形态：每次向用户汇报有没有说清 worktree/branch/comparison head 是什么；有没有用内部术语（如「业务比较点」）让用户看不懂
14. 跨 session 通信（`create_thread` / `send_message_to_thread` / 问原 session）：是否按用户要求做、有没有多余汇报
15. model/profile 档位：用户降级指令（luna/max、sol/medium）有没有被后续派发遵守
16. 长寿命 subagent：有没有一个 agent 被 followup 太多次、跨太长时间以致输出退化（用户原话「降智」）；退化的证据是什么

### 3. 清单 B 逐条判定 · 设计阶段设计意图（只有 slice 含设计阶段时填；否则写「本 slice 不含设计阶段」并跳过）

1. req-align：是否先判 contract impact、走了 fast path 还是 Decision/Spec gate；花在写材料上的 turn/时钟 vs 花在真正定位业务问题上的
2. Spec 范围识别是否区分「修改范围」与「兼容性验收范围」（沿既有消费者到可观察终态）
3. impl-planning / to-tickets：Ticket 之间的依赖写成什么粒度——是 implementation 依赖还是 acceptance 依赖？这直接决定执行阶段能否提前开工（执行阶段用户纠偏「阻断最终验收，不阻断开发」的根源在这里）
4. 验收设计有没有过度收集（claim 数量 vs 实际需要的证据线数量；同一份证据能否支持多个 claim）
5. 设计讨论中的用户纠偏：agent 提出的约束/默认值来源是否可追溯、是否引入不必要限制、是否复用旧包 vs 新包等
6. 独立审阅（如 ponytail-review 或 luna-worker 二审）的成本与实际采纳率
7. handoff-to-new-session：花了多长时间、交接内容里有多少是重复交代已有事实、在途 worker 上下文与 canonical ready ticket 有没有被保留（这项设计从未被实战检验过）
8. 设计阶段的 subagent 使用（读原始仓库、查参考值等）：派发时机是 agent 主动还是用户提示

### 4. 绕远路事件表（本报告的重点）

逐条列出让这个 session 明显变慢的事件。每条给：

| 字段 | 要求 |
| --- | --- |
| 触发行号 | 能回读的 jsonl 行号 |
| 类型 | `重复取证` / `形式化无业务收益` / `打补丁式返工` / `先做后推翻` / `等待串行` / `工具环境失败` / `范围理解偏差` / `派发拓扑错误` / `汇报不清` |
| 现场描述 | 两三句，讲清楚做了什么、为什么算绕路 |
| 代价 | turn 数 + 时钟跨度（用 timestamp 算），二者都给 |
| 一步到位应该怎么做 | 具体动作，不要写「应该更仔细」 |

### 5. 用户纠偏事件

每次用户 push back（含 response annotations 里的批注、含情绪化的原话），给：行号、用户原话摘要、agent 之前正在做什么、**这次纠偏暴露了哪条规则缺失 / 哪条规则写了但没被遵守 / 哪条规则加载的版本不对**。用户批注是最强的信号，一条都不要漏。特别注意：同一条纠偏在这批 session 里被用户重复了多少次（例如「角色不是载体」），说明规则是否已经在 skill 正文里、主控有没有读到。

### 6. 规则加载核对

用户消息里 `[$dispatcher](...)` 之类引用会把 skill 正文以 `<skill>...</skill>` 块注入到后续 user message 里。找出本 slice 实际加载的 dispatcher / impl-package 各 skill 的正文（记行号），核对：

- dispatcher 正文里有没有「Implementer executor」段（frontend-worker / backend-worker）；有则用户后来还要重复「角色不是载体」说明什么
- impl-package 各 skill 是从 plugin cache `0.4.2` 加载的；抽一两条关键规则（如 delta review 一名 reviewer、evidence 批量）看 cache 版本是否与仓库当前版本一致（对照 `D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\skills\<name>\SKILL.md`）
- 主控在 spawn 时用的 agent_type 与已加载规则要求的是否一致

### 7. 新发现的可优化点

不在清单 A/B 里、但本 slice 反复出现的成本。每条要能追到具体行号，并说明「改什么能省下什么」。按预计节省的时间/turn 排序。次数是线索不是结论。

## 方法要求

- rollout 文件很大（几 MB 到 77 MB），**不要 `cat` 整个文件、不要用 Read 工具整读**。用 Python 逐行流式解析：每行一个 JSON，字段 `timestamp` / `ordinal` / `type` / `payload`。
  - `type=response_item` 且 `payload.type=message`：`payload.role` 为 `user` / `assistant` / `developer`，`payload.content[].text`
  - `payload.type=reasoning` 是模型思考
  - `payload.type=custom_tool_call` 且 `payload.name=exec`：shell 调用，命令在 `payload.input`（一段 JS，内含 `tools.exec_command({"cmd": ...,"shell":"powershell"...})`），结果在下一条 `custom_tool_call_output` 的 `payload.output[].text`
  - `payload.type=function_call`：协作工具，`payload.name` ∈ spawn_agent / wait_agent / send_message / followup_task / interrupt_agent / list_agents / wait / js / request_user_input；`payload.arguments` 是 JSON 字符串，其中 `agent_type`、`task_name`、`target`、`timeout_ms` 明文，`message` 密文（无法读 brief 内容）
  - `payload.type=function_call_output` 且 `payload.name` ∈ create_thread / send_message_to_thread：跨 session 通信，`payload.output` 明文
  - `payload.type=agent_message`：子代理回信，`payload.author` 是 agent 路径，`payload.content[].text` 以 `Message Type: FINAL_ANSWER` 开头的是最终结果（明文可读）
  - `type=compacted`：上下文被压缩；`type=world_state` 首条含加载的 AGENTS.md；`type=turn_context` 含 cwd / model
  - `type=event_msg` / `token_usage_record` 是遥测，可跳过
- 先做全局统计和「事件骨架」（行号 + timestamp + 类型/工具名 + 简短摘要，user/assistant message 取前 200 字），落一份 `<SKELETON_FILE>`，再基于骨架回读关键区段原文。
- **不要再开自己的 subagent**（机器资源有限），也不要并行跑多个重脚本。
- 行号一律指原 jsonl 的 1-based 行号。引用前用 Python 抽该行验证一次，**不许编造行号**。
- 只读分析。除了 `<OUTPUT_FILE>`、`<SKELETON_FILE>` 和你自己的临时文件（都放在 `<WORK_DIR>` 下），不要写任何其他位置，尤其不要动 rollout 文件和任何 git 仓库；不要运行 git 写命令。
- 中文输出。结论要能被独立复核：每条判断挂证据，没证据就明说没有。文档正文不要按 80 字符硬换行。
