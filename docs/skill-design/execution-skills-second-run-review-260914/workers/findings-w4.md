# W4 分析报告 — tinymlops #309 Artifact Runtime Gap（09-13 rollout）

rollout: `C:/Users/Xiao/.codex/sessions/2026/09/13/rollout-2026-09-13T16-07-26-01a09b18-2679-7ef3-b22c-73a409aa0580.jsonl`（8069 行）。全部行号为该文件 1-based 行号，已用 Python 逐行流式解析验证，未整读原文件。

## 1. 会话事实（先算数字，再写判断）

**时间跨度**：首行 `L1 2026-09-13T14:07:27.252Z` -> 末行 `L8069 2026-09-14T08:21:26.380Z`，跨度约 18 小时 14 分（其中 `L7729`(23:28:38) MR 全绿之后到 `L7739`(次日 06:28:10) 用户才回来，中间约 7 小时是用户离场，不计入 agent 效率）。

**消息计数**（`type=response_item, payload.type=message`）：`role=assistant` 134 条，`role=user` 22 条（其中 2 条是 `<environment_context>`/`<codex_delegation>` 之类的自动注入壁纸，真正的人类发言 20 条，逐条见第 5 节），`role=developer` 11 条（ponytail 模式声明 + skill 正文注入等）。`compacted` 事件 3 次：`L2597`(17:56:14)、`L5118`(19:56:00)、`L7928`(07:49:28，learn-lessons 阶段中途)。

**协作工具调用次数**（`function_call.name`）：

| 工具 | 次数 |
| --- | --- |
| wait_agent | 254 |
| js | 54 |
| followup_task | 29 |
| spawn_agent | 28 |
| list_agents | 24 |
| send_message | 5 |
| interrupt_agent | 4 |
| wait | 2 |
| request_user_input | 1（`L1210`，唯一一次） |
| create_thread | 1（`L10`） |
| send_message_to_thread | 132（`function_call_output`，见下方说明） |

注：`send_message_to_thread` 从未以 `function_call` 形式出现，132 次全部是 `function_call_output`——因为这条通道被两种方式复用：(a) `L1528` 那种主控用裸 JS 直接调 `tools.mcp__codex_app__send_message_to_thread`（跨 session 问另一个 thread，仅 1 组，对应 `L1515` 那次"问另一个 session"）；(b) 大量的 grok 载体进度轮询/续接（`codex_delegation` 里 `source_thread_id` 各不相同，对应不同的 bounded grok 会话），这部分才是 132 次里的绝大多数。真正意义上的"跨 session 通信"（问另一个 codex thread）只发生了 2 组：`L1515->1521->1528->1537->1556->1561`（问 F-001 方案），以及收尾时 `L7739->7744->7751->7761`（发总结给同一个 thread `01a09244-23ce-7281-afd4-cd948967fc21`）。

**spawn_agent 的 agent_type 分布**（28 次全部核对，`arguments.agent_type` 明文）：

| agent_type | 次数 | task_name 示例 |
| --- | --- | --- |
| review-track-code | 5 | review_tkt01_a / review_tkt02_a / terminal_tkt02_code / closure_tkt02_code |
| review-track-spec | 5 | review_tkt01_c / review_tkt02_c / terminal_tkt02_spec / closure_tkt02_spec / review_tkt01_source_recheck |
| review-track-standards | 4 | review_tkt01_b / review_tkt02_b / terminal_tkt02_standards / closure_tkt02_standards |
| review-track-safety | 4 | review_tkt01_safety / review_tkt02_d / terminal_tkt02_safety / closure_tkt02_safety |
| luna-worker | 5 | review_tkt01_closure / review_tkt01_manifest_closure / investigate_tkt02 / backfill_stable_docs / mr127_ci_followup |
| grok-monitor | 1 | grok_monitor（唯一一次，之后全靠 followup_task 续用） |
| 无 agent_type 字段（用 model+reasoning_effort 直派） | 4 | final_tkt02_a_sol(gpt-5.6-sol/medium)、final_tkt02_b_luna/c_luna/d_luna(gpt-5.6-luna/max) |

没有出现"与主控同 profile 的默认 agent"（主控自身是 `gpt-5.6-sol` pragmatic，没有任何 spawn 直接复用这个身份）。也没有出现 `frontend-worker`/`backend-worker` 作为 `spawn_agent` 的 `agent_type`——所有前后端实现都是通过裸 JS 调 `tools.mcp__codex_app__*`（走 grok 载体的 thread 机制）完成的，不经过 `spawn_agent`。

**followup_task 复用分布**（`arguments.target`，`/root/` 前缀不影响同一 agent 判定）：`grok_monitor` 被 followup 17 次（`grok_monitor` 5 次 + `/root/grok_monitor` 12 次，同一 agent，前缀写法中途变化），存活 `L161`(14:13:34) 首次 spawn -> 首个 FINAL_ANSWER `L660`(15:06:03) -> 一路续到 `L7718` 附近仍在轮询，实质跨度约 9 小时，是本 slice 里最长寿的 subagent。其余 followup 目标均为 1~2 次：`mr127_ci_followup` 2 次、`closure_tkt02_*`/`final_tkt02_*` 各 1 次。

**并发度**（按 `spawn_agent` 起点 / 首次 `FINAL_ANSWER` 或 `interrupt_agent` 终点重建生命周期）：最多同时 4 个 agent 在途（四轨 review：`review_tkt01_a/b/c/safety`、`terminal_tkt02_*`、`closure_tkt02_*`、`final_tkt02_*` 各自的四个同时段）。按时间加权：0 个在途占 50.6%、1 个占 37.1%、2 个占 1.6%、3 个占 7.0%、4 个占 3.7%。多数时间是 0~1 个 agent 在途，4 并发只在四轨 review 窗口短暂出现。

**等待占比**：`wait_agent`/`wait` 的 253 次输出里，109 次是 `"timed_out": true`（等满全部 timeout_ms 什么都没等到）、144 次是 `"Wait interrupted by new input"`。另有两段肉眼可定位的"纯等待"区间：`L6811->L6821->L6826` 两次 240s 超时轮询（约 8 分钟）后用户在 `L6826` 主动打断说"似乎已经卡住了"；`mr127_ci_followup` 生命周期（`L6727` 21:38:26 -> 首次 FINAL_ANSWER `L7460` 22:58:00，约 80 分钟）是全 session `wait_agent` 密度最高的一段。

**shell 命令分类计数**（`custom_tool_call name=exec`，共 623 条；其中 261 条不是 `tools.exec_command` 而是 `apply_patch` 式补丁操作或直接调 `tools.mcp__codex_app__*`，已排除；剩余 362 条真正 shell/PowerShell 命令）：

| 分类 | 次数 |
| --- | --- |
| impl-package 语义 CLI（`impl_package_state.py`/evidence/ticket/trail/gate/package） | 120 |
| git | 96 |
| pytest/测试 | 17 |
| 容器/服务（docker/seaweedfs 等） | 24 |
| 其他（文件读取、脚本拼装等） | 105 |

**evidence 登记：单条 vs 批量**：全 slice 只出现 5 个 `evidence add` 调用块（不含 2 次 `--help`）：

- `L1998`：TKT-01，5 条记录用 `$records` 数组一次性 `ConvertTo-Json` 管道进单次 python 调用，**真批量**，1.7 秒内 `added:5`。
- `L6247`：TKT-02，单条记录，1 次调用。
- `L6261`：TKT-02，`foreach` 循环对 9 条记录逐条各起一次 python 子进程（壁钟 30.2 秒），**不是真批量**，只是把 9 次单条调用包进 1 个 exec 块。
- `L6274`：同上模式，对剩余 4 条记录再循环（12.0 秒）。
- `L6356`：TKT-01 revalidation，读 `state.json` 历史 claim 后再次 `foreach` 逐条注册（30.2+30.0 秒，两个 exec 块）。

只有 `L1998` 这一次真正用上了"evidence add 接受数组"的批量能力；其余 4 次全部退化成循环单条调用，详见第 7 节。

**重复执行（同一验证命令 ≥3 次，归一化后）**：`git status --short`（`L773/1121/1376` 等）、查看某 grok PID stderr 的 `Get-Content -Tail 8`（`L312/417/555` 等）、读取 `GITLAB_TOKEN` 的同一段脚本（`L6867/7250/7683`）各出现 3 次以上，但每次输入/上下文都不同（不同快照、不同 PID、不同新 shell 会话），属于合理轮询节奏，未发现"输入相同、纯粹又跑一遍"的浪费性重复。

## 2. 清单 A 逐条判定 · 执行阶段设计意图

1. **角色≠载体（同一角色按需并行创建多个）**：已执行。grok 载体在全 slice 出现 20 个不同 PID（`shell_cmds.tsv`/输出里 grep `pid=` 得到 20 个不同进程号），覆盖 TKT-01 两次实现 + 多次 finding 修复、TKT-02 实现 + 多次 finding 修复、MR CI 修复等，不是"一个 ticket 一个 grok"。审阅角色（review-track-*）也在同一批次里并行开 4 个（`L699/705/711/717` 四个同时 spawn）。

2. **派发用了正确 profile**：部分执行。审阅侧完全正确：`luna-worker`、`review-track-*` 按角色对应使用（见第 1 节表）；`final_tkt02_*` 四个终审严格按 `L5596` 指定的 sol/medium、luna/max 分派（见条目 15）。但前后端实现侧全程没有出现 `spawn_agent(agent_type=frontend-worker|backend-worker)`——TKT-01/TKT-02 都只有 backend scope，所以没触发 frontend-worker，这本身不算违反；但直到 `L473` 主控自己承认"dispatch 未显式记录 backend-worker profile"，说明即使只有一个 profile 需要标注，第一次也没有做到，靠用户在 `L468` 追问才补上（`L485`）。

3. **ready≠dependency（提前开工 + 先分析 foundation/seam 再 fan-out）**：现场被违反后纠正。`L2010` 主控自己已经判断"TKT-02 的 typed edge 应从 implementation 更正为 acceptance"，但在用户于 `L2016` 明确指出"阻断最终验收，不阻断开发，现在的阻断来自 Ticket 写成了 implementation: TKT-01，粒度过严"之前，主控没有主动放行 TKT-02 的开发——即已经看到了问题（`L2010`）却停在原地等确认，直到用户直接给出结论才在 `L2021` 改掉。这说明主控**有能力诊断粒度问题，但没有能力/没有被授权自行放行**，需要用户点头。foundation 分析先行方面：`L2775`（`L2770` 之后）主控把 TKT-02 的 finding 按"存储/恢复""NATS intake/ACK""runtime supervision"三类先分析再拆分派发，符合"先分析再 fan-out"。

4. **没有因授权/formality停下来问**：现场被违反，后纠正。`L1644` 主控为一个已经 3/3 写入的书面合同再次停下问"确认这版书面合同通过吗"，被 `L1651` 用户教训"我已经授权了，以后除了方案决策以外，不要因为这些形式化的东西返回"。这是本 slice 里最直接的一次"因formality停下"违反，纠正后 `L1658` 起未再复发同类模式（后续 TKT-02 investigation、finding 修复均未见形式化返回）。

5. **每个含代码return派了独立delta review（一名reviewer），不是每次都跑formal多轨do-review**：本 slice 呈现出的是相反模式——凡是有代码增量的收口点，全部是四轨（code/standards/spec/safety）full do-review：`review_tkt01_*`（`L699-717`，TKT-01 初次实现后）、`review_tkt02_*`（`L2453-2470`，TKT-02 初次实现后）、`terminal_tkt02_*`（`L4553-4571`）、`closure_tkt02_*`（`L4996-5014`）、`final_tkt02_*`（`L5632-5650`，同一批 TKT-02 finding 的第 4 次四轨复核）。同一个 TKT-02 增量在约 3 小时内被四轨审了 4 轮（初次、终版、closure、独立终审），**没有观察到任何一次"单 reviewer 做 delta review"的轻量模式**。这些多轨审阅发生在 Ticket 级别的收口/终审节点，背景材料允许"共享 foundation 重点审"，但 4 轮四轨对同一个 TKT-02 增量连续复核，超出"不是每次return都跑全套"的精神，应判定**部分违反**——审阅强度没有随收口的临近而收敛。

6. **evidence登记走批量、不逐条**：部分执行。见第 1 节：5 次 `evidence add` 调用块中只有 1 次（`L1998`）用了真批量（数组一次管道进单次调用），其余 4 次全部退化为 PowerShell `foreach` 循环单条调用，是"接口支持批量但执行时没用批量"的典型案例。登记本身没有挤占业务推进的证据：`L1998`/`L6247` 等evidence登记都在几秒到几十秒内完成，穿插在正常收口流程里，未观察到用户"别再为登记证据浪费时间"式的纠偏（本 slice 无此类用户原话，不代表其他 slice 没有）。

7. **局部barrier只扣受影响候选（OF-01复发检查）**：已执行，未见复发。`L2021` TKT-02 implementation 被放行后立即并行推进（`L2069` investigate_tkt02 与 grok_monitor 同时在途），`L2375` 之后主流程本地训练与 TKT-02 Grok 修复也是两条并行 lane（`L2392`："我会并行推进两条互不冲突的 lane"）。未发现某个 ticket 卡住时把无关工作也一起挂起的证据。

8. **无正当理由中断worker（逐次判定，OF-03复发检查）**：4 次 `interrupt_agent` 全部有据可查：
   - `L5608/5613/5618`：中断 `closure_tkt02_code/standards/safety`。理由：`L5596` 用户明确改变审阅口径（"track a 用 sol/medium，其余用 luna/max"），旧的三个 review-track 是用默认 profile 跑的，与用户新指令不符，主控在 `L5607` 明确说明"刚返回的旧 Track C 只保留为旁证，不作为最终终审 receipt"。判定：符合"用户直接指令改变执行方式"，等价于**用户取消**，正当。注意 `closure_tkt02_spec` 没被中断，因为它在 `L5603`（20:14:59）已先出了 FINAL_ANSWER，中断只打在还在跑的三个上，粒度正确。
   - `L7009`：中断 `mr127_ci_followup`。理由：`L6971` 用户指出"不要再让subagent自己调用，它只是个负责检查ci的，你才是主控"，`L6996` 用户进一步说"你决定如何拆和修"。判定：**subagent越权**（该 luna-worker 被赋予的 brief 原本只是检查 CI，但实际行为触发了用户纠正，暗示它在自行决定/派发修复），中断正当。
   四次中断全部落在 OF-03 允许的"用户取消/越权"两类里，没有发现无正当理由的中断。

9. **收尾动作没有挡住主线交付（OF-04复发检查）**：已执行。backfill（`L6445`spawn->`L6520`FINAL_ANSWER，约 12 分钟）、亲自验收、删任务包、合并 dev-fang、建 MR、CI 跟踪全部在 `L5690` 五步指令后的约 3 小时 8 分内（20:20->23:28）顺序完成，backfill 本身没有单独拖慢链路；CI 跟踪阶段的耗时主要来自 `L6826` grok卡住和 `L6971` 越权返工（见第 4 节），不是 backfill/登记环节本身的问题。

10. **worker有自己的worktree**：部分执行，且有滞后。`L2256` TKT-02 两个共享实现面（`deployment.py`/`real_runtime.py`）明确选择"保持单 writer"，没有给 Grok 开独立 worktree；直到 `L2770` 用户提示"worker 是可以有自己的worktree的...impl和fix都一样"之后，才在 `L2812`（紧跟在提示后几十行、几分钟内）出现 worktree 相关操作，随后 CI 修复阶段 `L6817` 明确用了独立隔离 worktree `.worktrees/mr127-ci-edge-runtime` + 独立分支 `codex/mr127-ci-edge-runtime`。判定为"用户提醒后才做"，不是主控主动应用该规则。

11. **主控context卫生**：已执行。长测试/长脚本（如 CI 跟踪、grok进度检查、evidence批量脚本）全部通过 `custom_tool_call exec` 在独立 shell 里跑，输出经 `max_output_tokens` 截断后摘要读回；长期监控用 `grok-monitor`/`luna-worker`（`mr127_ci_followup`）常驻，主控自身没有把大段原始日志整段读入。

12. **子代理没有越权；主控没有让渡裁决权**：现场被违反 1 次，随后纠正。见条目 8 的第二次中断（`L6971/6996/7009`）：`mr127_ci_followup` 出现了让主控收回裁决权的必要性，`L6996` 用户明确要求"你决定如何拆和修"，`L7001` 主控随后自己裁决拆分方案。纠正后未见复发。

13. **汇报形态：worktree/branch/comparison head是否讲清楚**：已执行，且用语通俗。`L7729` 收尾汇报直接给出分支名 `dev-fang`、commit `48c2b183`、MR 链接、Pipeline 链接和结果，没有使用"业务比较点"一类内部术语；`L1506`/`L2010` 等中间汇报也是用 commit hash + 测试通过数 + 待办清单的形式，用户能看懂。

14. **跨session通信按要求做、没有多余汇报**：已执行。`L1515` 用户要求问 `codex://threads/01a09244-...`，主控只做了这一件事（`L1520`说明目的、`L1536`说明已发出、`L1550`说明还没返回、`L1561`汇报结论），没有多问或多做；`L7739` 同理，用户要求发总结，`L7751`汇报已发送，`L7761`汇报对方确认。两次跨 session 通信都精确对应用户指令，无多余动作。

15. **model/profile档位遵守用户降级指令**：已执行，且可用 spawn_agent 的明文参数直接验证。`L5596` 用户说"track a 用 sol/medium，其余用 luna/max"，随后 `L5632 final_tkt02_a_sol` 的 `arguments` 里 `model:"gpt-5.6-sol", reasoning_effort:"medium"`；`L5638/5644/5650` 的 `final_tkt02_b_luna/c_luna/d_luna` 全部是 `model:"gpt-5.6-luna", reasoning_effort:"max"`。四个 spawn 参数与用户指令逐字对应，是本 slice 里"用户指令->明文参数"可验证性最强的一条。

16. **长寿命subagent退化（"降智"证据）**：本slice无直接的用户"降智"投诉原话，但有客观指标：`grok_monitor` 被 followup 17 次、存活约 9 小时（`L161`->`L7718` 附近），是全 session 最长寿的 subagent。未找到用户或主控明确指出其输出质量下降的文字证据；跨 3 次 `compacted` 事件（`L2597/5118/7928`）期间 `grok_monitor` 仍在被 followup，理论上存在上下文压缩后早期细节丢失的风险，但没有可引用的"退化"实证，如实判定为**证据不足，不能定性**。

## 3. 清单 B 逐条判定 · 设计阶段设计意图

本 slice **不含独立开工的完整设计阶段**：package `docs/implementations/2026-09-13-artifact-to-runtime-compatibility` 在本 rollout 开始时（`L38`continuation checkpoint）已经处于"Attempt initial active，TKT-01 PENDING"状态，说明 req-align/impl-planning/to-tickets 的主体在更早的会话里就完成了。但本 slice 中途触发了两次局部设计动作，可以用清单 B 的部分条目衡量：(a) `L1515-1658` 针对 F-001 storage-scope 的一次合同修订（走了完整 req-align 形态）；(b) `L2016-2021` 针对 TKT-02 依赖粒度的一次 Ticket 修订（更接近 impl-planning/to-tickets 的收敛）。

1. **req-align：是否先判contract impact、走fast path还是Decision/Spec gate**：已执行（针对F-001小周期）。`L1506` 主控先说明现状（F-001 BLOCKED，需要 Owner 选 storage-scope 模型）并给 3 个候选方案，`L1515` 用户把决策外包给另一个 session 做只读比较，`L1561` 该session给出推荐并列出合同变更面，`L1570` 用户批准，`L1577` 主控确认走 **Decision/Spec gate**（"接下来先由 req-align 修订 Decision/Spec/contract-design"），不是 fast path——因为这次改动涉及 credential/scope 这种合同级变更，选 gate 是合理的。耗时：`L1506`(16:08:48)到`L1644`(书面合同写完)大约 30~35 分钟，多数时间花在等待被问询的另一个 session 返回（`L1536`发出到`L1561`收到结论，约 25 分钟），主控自身写材料的时间不长。

2. **Spec范围识别：修改范围 vs 兼容性验收范围**：本slice无充分证据判定。`L1561` 那次跨 session 回复里提到了"不改 #308 publisher，不引入多 prefix，也不迁移 artifact layout"，划定了不动的边界，但没有看到显式的"沿既有消费者到可观察终态"的兼容性验收范围枚举，判定为**证据不足**。

3. **impl-planning/to-tickets：依赖粒度写成implementation还是acceptance**：**现场被违反后纠正**，这是本 slice 最核心的设计缺陷。见第 2 节条目 3 的详细描述：Ticket 文件把 TKT-02 相对 TKT-01 的依赖写成了 `implementation: TKT-01`（实现级依赖），但实际业务语义应是 `acceptance: TKT-01`（验收级依赖）——TKT-02 的开发不需要等 TKT-01 的 Pi/S3 最终验收，只有最终 SATISFIED 才需要。这个过严粒度直到 `L2016` 用户明确指出才被修正为 `acceptance: TKT-01`（`L2021`）。这直接对应执行阶段那次"阻断最终验收，不阻断开发"的纠偏——根源在设计阶段（更早的 to-tickets 环节，不在本 slice 内）把依赖粒度定得太粗，本 slice 只是执行阶段的补救。

4. **验收设计是否过度收集**：证据不足，本 slice 未见对既有 Ticket 验收 claim 数量的重新盘点或精简动作，无法判定。

5. **设计讨论中的用户纠偏：约束/默认值来源是否可追溯**：已执行。F-001 三个候选方案（`L1506`）都写明了各自的机制和取舍，用户选择走外部 session 核验而非直接拍板，推荐方案的理由链（`L1556`长文本："device-bound command -> manifest URI + checksum -> verified manifest -> exact result-bundle URI + checksum"）可追溯，未见凭空引入限制。

6. **独立审阅（如二审）的成本与采纳率**：`L1515-1561` 这次"问另一个 session"本质上就是一次独立二审：耗时约 25 分钟等待，采纳率 100%（`L1570` 用户直接同意其推荐，没有被拒绝或部分采纳的情况）。

7. **handoff-to-new-session**：本slice无相关场景。本 rollout 内没有出现新开 session 做设计接力的动作（`create_thread` 唯一一次在 `L10`，用途是"只读 anchor 检查"，不是设计接力 handoff）。

8. **设计阶段subagent使用时机**：本slice无相关场景。F-001 决策使用的是跨 session 委托（另一个已存在的 thread），不是新 spawn 的 subagent，且是用户在 `L1515` 主动提示要去问，不是主控自主发起。

## 4. 绕远路事件表（本报告的重点）

范围说明：按第二轮指示，本节只收 impl-package 设计/实现与 Dispatcher 调度行为本身的绕路；训练、Docker/SeaweedFS、CI 排障等业务验证内容不单独计时或建表，仅在其触发调度/等待/中断/返回决策时顺带一句带过。

| 触发行号 | 类型 | 现场描述 | 代价 | 一步到位应该怎么做 |
| --- | --- | --- | --- | --- |
| `L1644`->`L1651` | 形式化无业务收益 | 用户在 `L1651` 之前已多次明确授权（`L1570`"同意"），但主控在 3/3 份合同文件写完后仍在 `L1644` 停下来问"确认这版书面合同通过吗"，触发用户教训"以后除了方案决策以外不要因为这些形式化的东西返回"。 | 1 个用户回合、约 7 分钟（16:28:02->16:35:22），多花 1 次 request-confirm 往返。 | 书面合同写完后直接进入下一步（同步 Ticket/Plan），只在真正出现多个业务方案分叉时才停。 |
| `L652`->`L2375` | 范围理解偏差（调度层面：主控把 TKT-01 acceptance lane 当成外部依赖阻塞，长期未主动 dispatch 自助验证工作） | `L652` 起主控把"Pi/native 与只读 S3 验收"记为缺失输入，此后 `L1506`/`L2021` 反复复述同一假设，直到 `L2375` 用户指出应自行启动仓库自带的 Original Training + 本地 SeaweedFS，不必等外部设备/文件/S3。期间 TKT-01 的真实验收工作没有被派发，直到 `L2784`(18:03:17) 才实际跑起本地训练。 | 约 2 小时 57 分（15:05:56->18:03:17）的 TKT-01 acceptance lane 未被 dispatch；同一窗口内主控的 34 条 assistant 消息大多花在 TKT-02/评审等其他工作上，不是纯空等，但 TKT-01 这条 lane 本可以提前近 3 小时开始。 | 遇到"验收需要外部资源"的结论前，先检查仓库内是否已有可以自助拉起的等价能力（本地训练/本地存储服务），把"缺输入"和"没检查过能否自建"分开判断，再决定是否真的要等 Owner。 |
| `L5596`->`L6237` | 打补丁式返工（Dispatcher 拓扑：临时改派模型档位导致 3 个在途 agent 被整体作废重派） | `L5596` 用户要求"track a 用 sol/medium，其余用 luna/max"做独立终审，主控在 `L5608/5613/5618` 中断 3 个仍在跑的默认档位 `closure_tkt02_code/standards/safety`（各自已运行约 27~28 分钟），随后 `L5632-5650` 重新以正确档位起 4 个新 agent（`closure_tkt02_spec` 已提前出结果，被降级为"旁证"）。 | 约 82.5 个 agent-分钟被作废重跑（3 个 agent x 约 27.5 分钟），加上重派后新一轮再耗时 6~15 分钟不等（`L5632`->`L6237` 共 56 分钟）；这段内主控只发了 3 条 assistant 消息，不算主控自身话多，代价主要在 agent 算力浪费。 | 四轨审阅默认就该带上"各轨位固定模型档位"的策略（例如 do-review 默认 track A 用低档、其余用高档），而不是等收口时才由用户现场指定，减少"先跑默认档位再返工"的窗口。 |
| `L6811`->`L6826` | 等待串行 | 主控对同一个在途 grok worker 连续发起两次 `wait_agent(timeout_ms=240000)`（`L6811`/`L6821`），均无新进展，用户在 `L6826` 主动打断"似乎已经卡住了"，主控随后才在 `L6833` 改为"我来接管，不继续空等"并主动核对 PID/diff/pipeline。 | 约 4 分半（21:56:29->22:00:57）纯轮询，2 次满额 240s 超时轮询未换动作。 | 单个 worker 连续 2 次 wait 超时即应主动切换到"核对 PID/进程存活+读结果文件"的主动检查，不再无脑重复同一等待，不必等用户提醒。 |
| `L6727`->`L7009` | 派发拓扑错误（子代理越权，主控让渡了裁决权） | `mr127_ci_followup` 这个 luna-worker 的 brief 本应只是"检查 CI、返回失败证据"，但运行中出现了让用户判断其"自己调用/自己决定修复"的迹象，`L6971` 用户明确划界"它只是个负责检查ci的，你才是主控"，`L6996` 进一步要求"你决定如何拆和修"，主控随即在 `L7009` 中断该 agent 并亲自裁决（`L7001`）。 | 该 agent 存活约 36 分钟（21:38:26->22:14:45）后被中断，此后主控亲自处理到 `L7729`(23:28:38) 收口，中间约 74 分钟由主控主导；此段主控自身发了约 4+6=10 条 assistant 消息，属于主控接管后必须承担的正常工作量，不是纯浪费，但派发 brief 一开始就该把"只读检查、禁止自行发起修复/重派"写清楚，避免事后收权。 | 派给 luna-worker 做 CI 跟踪时，brief 里显式写明"只允许读操作（读日志/读 pipeline 状态），任何 fix/重派/push 决策一律返回主控"，不要留"检查+跟进"这种含糊边界。 |
| `L1998` vs `L6261`/`L6274`/`L6356` | 重复取证（impl-package evidence CLI 用法不一致） | 同一套"evidence add 接受数组"批量能力，`L1998` 用对了（数组一次管道进单次调用，1.7 秒注册 5 条），但 `L6261`/`L6274`（TKT-02，共 13 条）和 `L6356`（TKT-01 revalidation）三次都退化成 PowerShell `foreach` 循环、每条记录单独起一次 python 子进程。 | 3 次循环合计壁钟约 100 秒（30.2+12.0+30.2+30.0 秒，四个 exec 块），对比 `L1998` 的效率，本可缩短到十余秒；且循环内每条都是一次独立进程启动，资源开销数倍于批量调用。 | 把"$records 数组一次性 ConvertTo-Json 管道进单次 evidence add 调用"固化成主控自己的标准片段/小函数，后续遇到多条 evidence 一律复用，不再现场重新写 `foreach`。 |

## 5. 用户纠偏事件

逐条为真正的"纠正错误动作"类用户发言（不含单纯的批准/收尾指令）：

- **`L355`**（14:29:20）"若要求严格走默认工作流，缺少一次正式的 `EVIDENCE_SUFFICIENT/EVIDENCE_GAP` 返回，属于流程缺口。下次记得"。此前主控走的是 `implement-direct`（`L360` 承认"本轮已经选择 implement-direct"）。暴露：**规则写了但没被遵守**——dispatcher 正文里 `investigate/implement/fix/verify` 固定 worker 答案形态、`EVIDENCE_SUFFICIENT/EVIDENCE_GAP` 是标准返回之一，但本轮一开始选择跳过 investigate 直接 implement，跳过了该步骤。
- **`L468`+`L480`**（14:44:38/14:45:31）"你有按前后端去派发worker吗？"+"注意impl要用grok，frontend-worker 只是身份，不是载体"。暴露：dispatcher 正文里"Implementer executor"一节已经写明 frontend-worker/backend-worker 是 profile，但 profile 与 call-grok 载体的绑定关系（哪个 profile 走哪个载体）是靠 `L38` continuation checkpoint 里的一段动态注入文本("Owner-confirmed implementer executor override...都使用 call-grok 作为 $grok-worker")临时补的，不在静态 skill 正文里，说明**规则加载的版本/位置不对**——身份与载体的绑定应该固化进 dispatcher 或 call-grok 的正文，而不是每个 checkpoint 现场重申。
- **`L1651`**（16:35:22）"我已经授权了，以后除了方案决策以外，不要因为这些形式化的东西返回。"暴露：dispatcher 正文第 5 步已写"消费完成后继续安排工作"的完成标准，理论上不需要为已授权的形式化确认再返回，但主控在 `L1644` 仍然这样做了，属于**规则写了但没被遵守**。
- **`L2016`**（17:06:12）"TKT-02 不需要等 TKT-01 的 Pi/S3 最终验收...现在的阻断来自 Ticket 写成了 `implementation: TKT-01`，粒度过严。"暴露：**上游设计阶段的规则缺失**——Ticket 依赖粒度本该在 to-tickets 阶段就区分 implementation/acceptance，本 slice 里这是设计遗留问题的执行期爆发；同时也说明执行阶段主控没有能力/权限自行把 `implementation:` 依赖降级为 `acceptance:` 依赖，必须用户点头。
- **`L2220`**（17:26:45）"提醒：grok 只是载体，不是一个ticket只能创建一个"。这是"角色≠载体"规则第二次被提醒（第一次是 `L480`），说明该规则虽然在 dispatcher 正文里以"同一 profile 可并行派发多次"的形式存在，但主控对**载体（grok）本身**是否可以在同一 Ticket 内并行开多个，理解上仍有滞后，直到这次提醒后才在 `L2225` 明确复述规则并在后续实践中体现（20 个不同 grok PID）。
- **`L2375`**（17:47:59）"不再等待提供设备、文件或外部S3...真正需要解决的只是现有验收runner对tflite_runtime的环境绑定。"暴露：**禁止因授权/formality停止开发**这条规则被隐性违反——主控把"缺少外部设备/S3"当作既成事实的阻塞输入，而不是先检查仓库内是否已有自助路径，属于对"本产品是 poc，主控拥有本地 fixture...禁止一切因为授权、formality而停止开发"这条规则的**理解偏差而非未加载**（`L360`等处能看到主控确实知道有这条规则，只是把这次具体场景误判成了"需要等待"而非"formality"）。
- **`L2770`**（18:02:47）"worker 是可以有自己的worktree的，如果不能精准切割write set，也可以先去不同wt实现后集成，impl和fix都一样"。暴露：这条规则此前没有被应用（`L2256` 明确选择"单 writer"而非分 worktree），提醒后约几分钟内（`L2812`）即生效，说明规则本身可执行、只是**没有被主动想起**，不是能力缺失。
- **`L5596`**（20:14:53）"独立终审，使用track a用sol/medium，其余用luna/max即可"。这不是对错误的纠正，而是一条新增调度指令，但因为落在 3 个已在途 agent 之后，直接导致第 4 节的打补丁式返工。暴露：do-review/最终终审环节缺少"按 track 固定模型档位"的默认策略，需要用户每次现场指定。
- **`L6826`**（22:00:57）"似乎已经卡住了，修复后重新触发CI"。暴露：主控对"同一 wait_agent 连续超时"缺少自动升级为主动核查的阈值规则，需要用户观察到卡顿才提醒。
- **`L6971`**（22:13:58）+**`L6996`**（22:14:31）"不要再让subgaent自己调用，它只是个负责检查ci的，你才是主控"+"你决定如何拆和修"。暴露：派发 brief 的读写权限边界（只读检查 vs 可以自行决策修复）没有在派发时显式约束，属于**规则存在但派发时没有把边界具体化到这次 brief 里**（第 2 节条目 12）。

跨 slice 重复度：**"角色/载体不是绑定关系"这条规则在本 slice 内被提醒了 2 次**（`L480` 针对 frontend-worker、`L2220` 针对 grok），是本 slice 复发率最高的单一规则，说明该规则虽然在 dispatcher 正文中以"同一 profile 可并行派发多次"存在，但没有被主控稳定内化为"每一种角色（含 grok 这个载体本身）都可以按需开多个"的通用直觉。

## 6. 规则加载核对

本 slice 在 `L46`（14:09:39）一次性读取了 `dev-with-track`、`dispatcher`、`call-grok`、`execution-boundaries`、`ponytail` 五个 skill 正文，`L53` 又追加读取了 `impl-package-composition-contract`、`impl-package-current-state`、`progressive-system-evidence`、`dispatcher/delegation`、`dispatcher/resource-isolation`、`call-grok/caller-contract`、`dev-with-track/runtime-protocol` 等 references。逐条核对：

- **dispatcher 正文里的"Implementer executor"段**：存在，位于当前加载版本第 20 行起，明确写"frontend implementation -> frontend-worker；backend implementation -> backend-worker；同一 profile 可并行派发多次"。用 `diff` 直接比对本次会话实际加载的 `C:\Users\Xiao\.codex\skills\dispatcher\SKILL.md` 与仓库当前 `D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md`，**逐字节一致，无 diff**——说明规则本身没有过期或加载错版本。但该段落**没有**写明这两个 profile 具体通过什么载体（call-grok）落地——这个绑定关系只出现在 `L38` 的动态 continuation checkpoint 里，不在静态正文里，这是 `L468/480` 反复被提醒的根因（详见第 5 节）。
- **impl-package plugin cache 0.4.2 与仓库当前版本一致性**：对 `dev-with-track`、`execution-boundaries` 两个 skill 做了 `diff C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\skills\<name>\SKILL.md` vs `D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\skills\<name>\SKILL.md`，**两者均无 diff**，cache 与仓库现版本一致，不存在"用户已经改了仓库但 session 还在用旧 cache"的版本漂移问题。`call-grok` 同样对比 `C:\Users\Xiao\.codex\skills\call-grok\SKILL.md` 与仓库版本，**无 diff**。（受时间限制未逐一 diff 全部 references 文件，已抽查的 4 个文件全部一致，抽样范围内未发现版本漂移。）
- **spawn 时 agent_type 与已加载规则要求是否一致**：一致。第 1/2 节已逐条核对 28 次 spawn 的 `agent_type`/`model` 参数，除了"frontend-worker/backend-worker 走 call-grok 载体"这条绑定信息不在静态正文（已如上说明）外，其余审阅角色（review-track-*/luna-worker）的选用都能在 dispatcher 正文与 do-review 相关 reference 里找到对应依据。

## 7. 新发现的可优化点

按预计节省时间/turn 排序：

1. **evidence add 批量能力没有固化成主控自己的可复用片段**（`L1998` vs `L6261/6274/6356`）：同一能力一次用对、三次退化成循环，累计多花约 100 秒 shell 壁钟、多启 20+ 次 python 子进程。改法：把"`$records | ConvertTo-Json -Compress | python impl_package_state.py ... evidence add`"固定成主控自带的标准脚本片段（哪怕只是自己记住这一种写法），后续任何多条 evidence 一律复用，不再现场手写 `foreach`。
2. **frontend-worker/backend-worker 与 call-grok 的载体绑定关系只活在动态 checkpoint 文本里**（`L38`，对应用户纠偏 `L468/480`）：这条信息每次新 session/新 continuation 都要重新在 checkpoint 里手打一遍，且不保证每次都写全，本 slice 就因为没在 `L46` 读到的静态正文里找到这条信息而被用户纠正了 2 次（`L468/480` 之外，`L2220` 的"grok只是载体"本质是同一条规则的另一次复发）。改法：把"profile 通过 call-grok 载体落地，同一 profile 可并行开多个 grok session"这句话直接写进 dispatcher 的"Implementer executor"小节正文，不必每次靠 checkpoint 现场重申。
3. **四轨 do-review 在同一个 TKT-02 增量上短时间内完整跑了 4 轮**（`review_tkt02_*`初次 `L2453-2470`、`terminal_tkt02_*L4553-4571`、`closure_tkt02_*L4996-5014`、`final_tkt02_*L5632-5650`，约 3 小时内），且其中一轮（closure）还被中途作废重跑（第 4 节第 3 行）。改法：do-review/dev-with-track 的收口规则应更明确地区分"哪些节点必须四轨"和"哪些节点复用已有 review receipt 就够"，减少同一增量被反复整套重审的次数。
4. **wait_agent 高频轮询、109/253 次纯超时无新信息**：说明轮询节奏（不少是 120~240 秒）偏短或没有随"agent 明显还在正常跑"而自适应拉长。改法：连续 1~2 次超时后自动把下一次 `timeout_ms` 拉长或改为主动核查 PID/结果文件（已在第 4 节 `L6811-6826` 行验证过这样做更快），减少纯等待轮询次数。
