# W1b 分析报告 — finance-document-review-rules 主执行后半段到收口

分析区间：jsonl `rollout-2026-09-13T20-21-39-01a09c00-e64b-7dd0-8c45-e7757ff0c462.jsonl` 的 **L7873–L16546**（09-14 04:07:21 → 14:14:05，约 10h07m）。行号均为原始 jsonl 1-based 行号，已用 Python 逐行流式解析验证（未整读原文件）。

## 1. 会话事实（先算数字，再写判断）

**时间跨度**：首条 2026-09-14T04:07:21.698Z（L7873，用户「旧进程可杀」）→ 末条 2026-09-14T14:14:05.529Z（L16543，assistant 交接文档收尾）。跨度约 **10 小时 7 分**。

**消息计数**（`response_item.payload.type=message`，按 role）：
- user：**9** 条（含 L7873「旧进程可杀」、L14505「继续」、L15553 附近「本次 terminal 后再有问题 closure 就够了」类、L15744「卡住了？」、L15838「用 luna-worker 刷…」、L16295「快速收尾…」、L16538「写个交接文档你写12min？？？？」等，见第 5 节逐条列出）
- assistant：**58** 条
- developer：**7** 条（技能/上下文注入，含 L14500 附近的 skills_instructions 重注入、L14504 Ponytail 模式声明）

**`compacted` 事件数**：**4** 次，行号 L8482、L11003、L13400、L15765。

**协作工具调用次数**（`function_call`，本 slice 内）：

| 工具 | 次数 |
| --- | --- |
| spawn_agent | 61 |
| wait_agent | 145 |
| send_message | 26 |
| followup_task | 23 |
| interrupt_agent | 4 |
| list_agents | 40 |
| request_user_input | 0 |
| create_thread | 0 |
| send_message_to_thread | 0 |
| wait（非 wait_agent 的独立工具）| 3 |
| js（浏览器 Computer-Use 工具，非清单内）| 171 |

**spawn_agent 的 `agent_type` 分布**（61 次）：luna-worker 22、backend-worker 20、frontend-worker 7、review-track-code / review-track-standards / review-track-spec / review-track-safety 各 3（合计 12，均为 do-review 4 轨工具，非通用 worker profile）。**没有出现「与主控同 profile 的默认 agent」**。

**`followup_task` 复用同一 agent 次数分布**（target → 次数，本 slice 内全部非零目标）：`/root/fix_receiver_approved_backend`=4、`/root/review_unit_profile_ui_delta`=3、`/root/verify_ev2_postgres_rerun`=3、`/root/fix_receiver_approved_frontend`=3、`/root/fix_enrolled_receiver_mutation`=3；其余（`verify_ev3_accounting`、`integrate_backend_residuals`、`fix_unit_ui_workspace`、`research_ev4_ui_preflight`、`review_receiver_runtime_delta_retry`、`fix_ev2_f1_integration`、`fix_terminal_workbench_consumer`）各 1。**被 followup 最多的是 `/root/fix_receiver_approved_backend`（4 次）**，生命周期 L9250(05:39:44)→L10183(06:33:33)，存活约 **54 分钟**。

**并发度**（基于 `event_msg.item.type=SubAgentActivity` 的 started/completed/interrupted 事件重建，66 个不同 `agent_path`，覆盖时长约 581 分钟）：
- 时间加权分布：并发 0 个占 11.9%（69min）、1 个 14.2%（83min）、2 个 19.9%（116min）、3 个 19.3%（112min）、4 个 23.4%（136min，**最多时间落在这一档**）、5 个 6.0%、6 个 1.7%、7 个 1.4%、8 个 0.2%、9 个 1.3%、10 个 0.7%
- **最高并发 10**，出现在 2026-09-14T10:09–10:22（L13915–L14182 附近），一次性拉起 8 个 `fix_terminal_*` worker（accounting_gates / review_core / provisioning / migration_preflight / workspace_gross / enrollment_fence / web_ocr_idempotency / action_filter）
- 多数时间维持在 2–4 个并发，符合「角色可并行多个」的设计意图；高并发（8–10）只在 terminal 修复/复核 fan-out 时短暂出现

**等待占比**（连续只有 `wait_agent`/`list_agents`/其输出/reasoning，没有新 `spawn_agent`、没有 exec、没有实质 assistant 文本的时间段，共 116 段）：
- 累计 **16768 秒 ≈ 279.5 分钟**（占本 slice 总时长的约 46%；其中大部分是等待 worker 正常返回，不全是空转）
- **最长一段 1735 秒 ≈ 28.9 分钟**，L14472(10:41:31)→L14500(11:10:26)：期间 `/root/fix_terminal_billing_spec_closure` 在 L14495 报 `Agent errored: You've hit your usage limit`，随后主控没有任何动作直到 L14500 出现整段 skills/world_state/turn_context 重注入（模型切到 `gpt-5.6-sol`、Ponytail lite 模式），紧接 L14505 用户「继续」。**这段 29 分钟空转是撞到 usage limit 后的会话中断/重连，不是「主控在傻等 worker」**，与 L14505 用户「继续」直接对应（详见第 4 节）。

**shell 命令分类计数**（`custom_tool_call.name=exec`，692 次，按完整命令文本分类）：

| 类别 | 次数 |
| --- | --- |
| git | 207 |
| impl-package 语义 CLI（`trail append`/`situation.py render`/`ticket satisfy`/`evidence add`/`gate pass`/`package validate`/`package refresh-progress` 等）| 182 |
| 其他（主要是 `Get-Content` 直读 spec/situation/ticket/日志/源码片段、`Get-Date`、`Get-Process`）| 120 |
| 进程/端口/HTTP 诊断（`Get-NetTCPConnection`/`Get-CimInstance`/`Start-Sleep`/`curl` 等）| 84 |
| worktree/node_modules 维护（`git worktree add`、`Move-Item`/`Remove-Item` 处理跨 worktree 的 `node_modules` junction）| 30 |
| `pnpm`/`npm`/`node` 其他 | 24 |
| 文件补丁（`apply_patch` / `Begin Patch`）| 23 |
| dev-server 轮询（`write_stdin` 读运行中会话输出）| 15 |
| **test**（真正的 pytest/vitest 关键词命中）| **7** |

**主控自己几乎不跑测试**：692 次 exec 中只有 7 次命中测试关键词，抽样确认这 7 次实际是「检查 vitest 二进制是否存在 / 冲突标记检查」等前置检查，**没有一次是主控自己跑完整测试套件并读长输出**——测试确实被推给了 worker，符合用户「长测试脚本给 luna-worker 跑」的要求（对应清单 A 第 11 项，判「已执行」，见第 2 节）。

**impl-package CLI 子命令调用频次**（在语义 CLI exec 中细分，一次 exec 可能命中多个关键字）：`trail append` 128 次、`situation.py render` 26 次、`ticket satisfy` 12 次、`evidence add` 6 次、`gate pass` 5 次、`package refresh-progress`/`package validate` 各 3 次、`checkpoint` 1 次。

**evidence 登记：单条 vs 批量**（本 slice 关键发现，详细证据见第 4 节与第 2 节第 6 项）：
- 全 slice 内 9 次含 `evidence add` 字样的 exec 调用中，**2 次（L15659、L15699）是正确的批量调用**——先在 PowerShell 循环里把记录攒进 `$rows` 数组，再 `$rows | ConvertTo-Json | ... evidence add` 一次性提交；
- 但约 34 分钟后，**L16128** 退化为 `foreach($ticketProp){foreach($claimProp){ ... | evidence add }}`——对 39 条 (ticket,claim) 记录**逐条单独起一次 CLI 子进程**（L16169 输出 `covered=39/39` 印证记录总数），随后用户在 **L16295**「快速收尾不要再因为登记证据浪费时间了」介入。

**重复执行（同一命令 ≥3 次，且输入未变化）**：`trail append`（128 次）与 `situation.py render`（26 次）本身是「一次 dispatch/return 一次」的正常记账开销，不算重复。但 evidence 覆盖率轮询命令（`Get-Content state.json | ConvertFrom-Json; ... "covered=$covered/39"` + `Get-CimInstance` 查 `evidence add` 存活子进程）在 **L16169(13:39:50)、L16190(13:44:44)、L16204(13:48:14)** 被原样重跑 **3 次**，只是在等待后台 39 个逐条 `evidence add` 子进程收敛——这是上面「逐条循环退化」的直接代价，不是独立的重复劳动。

## 2. 清单 A 逐条判定 · 执行阶段设计意图

1. **角色≠载体：同一角色并行多个worker，不是每角色一个** —— **已执行**。L13903–L13963（2026-09-14T10:07:57–10:10:35）在约 2 分半内连续 spawn 了 **8 个 `backend-worker`**（`fix_terminal_receiver_authority`/`fix_terminal_accounting_gates`/`fix_terminal_review_core`/`fix_terminal_provisioning`/`fix_terminal_migration_preflight`/`fix_terminal_workspace_gross`/`fix_terminal_enrollment_fence`/`fix_terminal_action_filter`）+ 1 个 `frontend-worker`（`fix_terminal_web_ocr_idempotency`），全局并发峰值达到 10（见第 1 节）。同一角色被拆成多个并行载体，不是「一个角色一个 agent」。

2. **派发用了正确 profile** —— **已执行**。全 slice 61 次 spawn_agent 分布为 luna-worker 22 / backend-worker 20 / frontend-worker 7 / review-track-*（do-review 专用）12，没有出现「与主控同 profile 的默认 agent」。用户在本 slice 内未提及 grok，call-grok 分支**本 slice 无相关场景**。

3. **ready≠dependency：先分析 foundation/seam 再 fan-out** —— **已执行**。L13836（2026-09-14T10:02:34）assistant 明确写出「终验发现的是同一组承重边界，不会拆成入口补丁：优先修复 OCR 幂等副作用、receiver/accounting authority、Accounting forbidden gates 与 Web 双 authority」——先把多个 finding 归到共享 foundation，再在 L13889–L13963 逐个开独立 worktree（`git worktree add -b codex/0914-terminal-*`）fan-out 8 个 worker。没有出现「先并行、后发现共享前置」的补丁式返工证据。

4. **没有因授权/formality 停下来问用户** —— **已执行**。本 slice `request_user_input` 调用 **0 次**；9 条用户消息里没有一条是回应主控的授权/formality 提问（均为主控主动汇报或用户主动纠偏，见第 5 节）。

5. **delta review vs formal 多轨 do-review** —— **已执行，但代价需要单独看**。执行期间的单笔代码 return 走的是**单一 reviewer 的 delta review**（如 `/root/review_unit_profile_ui_delta`：L7887 spawn、L9447 completed；`/root/review_receiver_runtime_delta`：L12986 spawn），符合「一名 reviewer」原则；`review-track-code/spec/standards/safety` 4 轨 formal do-review 只在 terminal-final 阶段使用，但**在本 slice 内跑了 3 轮完整 4 轨**：第一轮 L13396–L13430（09:37 spawn a/b/c/safety）、closure 轮 L14780–L14799（11:42）、recheck 轮 L15320–L15340（12:32）。每轮之间确有真实修复提交（OCR 幂等、receiver authority、accounting gates、web authority 等），不是空转重复，但 3 轮全轨审查本身是一笔不小的固定成本（详见第 4、7 节）。

6. **evidence 登记走批量、不挤占业务推进** —— **部分执行，L16128 处现场退化为逐条**。L15659、L15699 两次是正确批量（数组一次性 `evidence add`）；L16128 退化为 `foreach` 循环内逐条起 39 个 CLI 子进程，随后 L16169/16190/16204 反复轮询覆盖率等待收敛，直到用户在 **L16295**「快速收尾不要再因为登记证据浪费时间了」介入。判定：**现场被违反**（同一 session 内先做对、后做错）。

7. **局部 barrier 只扣受影响候选，不为并行而并行（OF-01 复发检查）** —— **本 slice 无法排除**。8-worker 的 `fix_terminal_*` fan-out（L13896–L13963）确实是先做了 foundation 归类后才并行（见第 3 项），没有观察到「明知某候选 runnable 却连续 wait 不再 render」的 OF-01 典型模式；但本 slice 也没有出现足以证明「局部 barrier 精确」的反例场景（例如某个 worker 卡住时，其他互不依赖工作是否仍被派发）。判定：**已执行**（就 fan-out 决策本身而言），OF-01 场景本身未复现。

8. **没有无正当理由中断 worker（OF-03 复发检查，逐次列出全部 4 次）** ——
   - **L7886**（04:07:47.946，target=`/root/review_unit_profile_ui_delta`）：中断前刚发现比较分支的 HEAD 被后台集成改写到 `96b7685f`（L7878-7882），该 reviewer 的比较基准已失效。判定：**符合「不可恢复资源冲突」**——reviewer 输入（comparison head）已经过期，继续跑没有意义。
   - **L8946**（05:31:17.082，target=`/root/fix_unit_ui_workspace`）：中断前已 `send_message` 提醒一次（L8887，05:27:05）、两次用 `Get-CimInstance`/`Get-Process` 核实进程仍 `Responding:True`（L8894-8904、L8932-8935），之后又等了 120s+60s 才中断。判定：**存疑**——进程确认仍存活且在响应，中断理由更像「累计等待超预算」而非「carrier 明确失败」，比 L7886 弱，接近 OF-03 的「规则写了、承诺了，长 session 里仍按超时中断」模式，但已经比 B2 案例多做了一步存活核实。
   - **L9650**（06:02:25.945，target=`/root/fix_receiver_approved_backend`）：中断前只有一次 `send_message`（L9636）+ 一次 60s `wait_agent` 超时（L9643-9646），**没有做进程存活核实**就直接中断，随即 `followup_task` 重新派发同一 target（L9655）。判定：**较可能是 OF-03 复发**——纯粹按等待超时中断，没有确认 carrier 是否真的失败。
   - **L13099**（09:19:35.562，target=`/root/review_receiver_runtime_delta`）：中断前 30s wait 超时（L13085-13088）+ 检查预期证据文件是否已落盘（`Test-Path`，结果 `False`，L13092-13095），中断后紧接着的新 dispatch 事件里 `chosen` 字段写明「replace the interrupted delta reviewer with a bounded in[vocation]」（L13113），即换成有限定范围的重试。判定：**符合「carrier 明确未产出」**——有具体产出缺失证据（文件不存在）支撑中断决定，且书面记录了替换理由。
   - 小结：4 次中断里 2 次（L7886、L13099）有明确证据支撑，1 次（L8946）做了核实但结论存疑，1 次（L9650）证据最弱、接近纯超时驱动。**不是全部符合四类正当理由**。

9. **收尾动作没有挡住主线交付（OF-04 复发检查）** —— **现场被违反，且是本 slice 最大的一笔**。L15659 起（13:00:43）到用户 L16295（13:53:53）介入，主控在 evidence/稳定文档回刷/covered-count 轮询上花了约 **53 分钟**，其中 L16128 起的逐条循环单独占用约 19 分钟（13:35–13:53，见第 1 节）。这段时间里没有新的业务修复被派发（对照第 1 节「等待占比」统计，这段期间的动作全部是 `evidence add`/`trail append`/覆盖率检查），直到用户明确要求「不要再因为登记证据浪费时间」才转为直接写 Gate。判定：**OF-04 在本 slice 复现**——收尾（evidence backfill）事实上挤占了本该更早发生的 Gate/closure 收口。

10. **worker 有自己的 worktree** —— **已执行**。8 个 `fix_terminal_*` worker 均先 `git worktree add -b codex/0914-terminal-*`（如 L13889 为 `fix_terminal_ocr_idempotency` 建 `0914-terminal-ocr-idem`）再 spawn，写集不能精准切割时靠独立 worktree 隔离。

11. **主控 context 卫生：长测试/长脚本给 worker，主控不读大段输出进自己 context** —— **已执行**。692 次 exec 中只有 7 次命中测试关键词，抽样确认全部是「检查 vitest 二进制是否存在 / 冲突标记检查」等前置探测，**没有一次是主控自己跑完整测试套件**；真正的测试执行（1,222 个后端 focused、314 个 Web focused 等，见 L15749）全部在 worker 里跑，主控只读 FINAL_ANSWER 摘要。

12. **子代理没有越权；主控没有把裁决权让给子代理** —— **已执行，且有强证据**。L13164（09:24:41）`/root/review_receiver_runtime_delta_retry` 的 FINAL_ANSWER 结论是 `PASS`；主控在 L13177（09:25:28）明确写「delta review 的"PASS"与真实 DB/代码不一致，我不接受该结论」，随即在 L13178（09:25:43）删除该 reviewer 写的证据文件，自己重新判定为存在真实 authority 缺口并改派修复。这是主控保留最终裁决权、不盲信子代理结论的直接证据。

13. **汇报形态：worktree/branch/comparison head 讲清楚，不用内部术语** —— **已执行**。抽样 assistant 消息（L8302、L8382、L8461、L9844、L9993、L10165、L15749、L15775 等）均用业务语言描述根因和范围（如「依赖恢复已成功」「回刷稳定文档、合入最终分支、写 Gate PASS」），未发现「业务比较点」一类内部术语外泄给用户。

14. **跨 session 通信** —— **本 slice 无相关场景**。`create_thread`/`send_message_to_thread` 在本 slice 均为 0 次。

15. **model/profile 档位遵守用户降级指令** —— **本 slice 无相关场景**。本 slice 内用户没有给出 luna/max、sol/medium 一类档位指令；`turn_context` 抽样显示模型始终是 `gpt-5.6-sol`（L8484、L10188、L11005、L13402、L14503、L15689、L15767、L16401），无档位切换需要核对。

16. **长寿命 subagent 是否退化（「降智」）** —— **本 slice 无法证实，但有一个候选**。被 followup 最多的是 `/root/fix_receiver_approved_backend`（4 次 followup，存活 L9250→L10183 约 54 分钟），期间出现 3 轮「点击暴露新根因」（L9844→L9993→L10165，见第 4 节），但每轮都是**真实 UI 点击发现新的、此前未覆盖的代码路径**（follow-up 锁 → Unit/row 锁 → legacy 完成审核的 `else` 分支），根因逐轮变得更清晰而不是重复犯错或答案退化，不构成「降智」证据；更像是问题本身的范围在通过真实点击逐步显现。判定：**未发现退化证据**，该 worker 生命周期长是问题复杂度导致，不是模型质量下降导致。

## 3. 清单 B 逐条判定 · 设计阶段设计意图

**本 slice 不含设计阶段，跳过。** L7873-L16546 全程是 dev-with-track 执行/收口（trail append / evidence add / ticket satisfy / gate pass / package validate），没有出现 req-align / impl-planning / to-tickets / handoff-to-new-session 相关的语义 CLI 调用或对应 skill 引用。设计阶段属于前半段（W1a 区间）。

## 4. 绕远路事件表

| 触发行号 | 类型 | 现场描述 | 代价 | 一步到位应该怎么做 |
| --- | --- | --- | --- | --- |
| L16128-L16295 | 打补丁式返工 / 形式化无业务收益 | 已在 L15659/L15699 用批量数组正确登记过一次 evidence，约 34 分钟后同一收口流程里又退化为 foreach 循环内逐条起 39 个 evidence add 子进程；随后 L16169/16190/16204 三次重跑同一覆盖率轮询命令等子进程收敛，直到用户 L16295 介入才停止。 | 约 19 个 exec/reasoning 条目，时钟 13:34:24 到 13:53:53，约 19.5 分钟 | 复用刚用过的 $rows 累积模式：先把 39 条记录全部 append 进一个数组，一次 ConvertTo-Json -Depth 5 管道给 evidence add 提交；不要为同 revision 重新登记单独写一个逐条循环。 |
| L14472-L14505 | 工具环境失败 | fix_terminal_billing_spec_closure 在 L14495 报 Agent errored: You've hit your usage limit，随后没有任何补救动作，直到 L14500 出现整段 skills/world_state/turn_context 重注入（模型仍是 gpt-5.6-sol，新增 Ponytail lite 声明），用户 L14505 才输入继续。 | 1 个空转区间，时钟 10:41:31 到 11:10:26，约 28.9 分钟，是本 slice 单段最长等待 | 子代理报 usage limit 错误时应立刻 list_agents 核对其余在途 worker 状态并汇报给用户某 worker 因用量限制失败、其余 N 个仍在跑，而不是让会话空转到自动重连；重连后第一句话就该说明这次中断原因，不必等用户问。 |
| L13396-L15340 | 形式化无业务收益（部分） | Terminal 4 轨 do-review（A=code、B=standards、C=spec、Safety）在本 slice 内整轮跑了 3 次：初轮 L13396-L13430（09:37）、closure 轮 L14780-L14799（11:42）、recheck 轮 L15320-L15340（12:32）。每轮之间确有真实修复，但用户在 L15553（12:48:15）本次 terminal 后再有问题 closure 就够了 直接要求停止再开新一轮全轨。 | 3 轮乘 4 track 等于 12 次 review-track spawn；时钟跨度 09:37 到 12:48，约 3 小时 11 分（含大量真实修复穿插，非纯浪费，但审查本身的固定开销可观） | 第一轮全轨发现的 4 个共享 authority/idempotency 问题本可以在 fan-out 修复之前先做一次跨 ticket 的 foundation 扫描（grep 所有 queryRawUnsafe/authority 判断点），一次性列全后修复，只需 1 次 closure 轮验证，不需要 3 轮。 |
| L9250-L10183 | 打补丁式返工 / 先做后推翻 | fix_receiver_approved_backend 连续 3 轮通过真实 UI 点击才定位到真正根因：第一轮只移除 follow-up 锁（L9844，06:08:54）、第二轮发现 Unit/row 锁未覆盖（L9993，06:18:41）、第三轮才发现是 legacy 完成审核走的另一个 else 分支复用同一个 raw Unit fence（L10165，06:30:19）。 | 4 次 followup_task，时钟 05:39:44 到 06:33:33，约 54 分钟 | 第一次发现 queryRawUnsafe 被 tenant guard 拒绝时，应先在整个 billing.service.ts（及其调用的 updateReviewRow）里搜索所有 raw tenant-unsafe 查询调用点，一次性列全再统一改成 tenant-safe CAS，而不是逐条点击发现一个换一个。 |
| L16408-L16536 | 范围理解偏差 / 工具环境失败 | 用户只要总结一下本任务包做的事情、写一个环境重启加简单的手测说明 handoff 文档（L16402），主控读了 handoff SKILL.md、references/task-execution.md、local-development.md（857 行输出）、test-cases/registry/cases.json（427 条，读了前 150 行）、scripts/local-auth/run.ts（220 行）、dev.ts（240 行），还两次因 JS 反引号转义写错 apply_patch 触发 SyntaxError（L16478、L16515）返工重写。 | 12 turn 级别（L16408 到 L16536），时钟 14:01:14 到 14:13:54，约 12.7 分钟；用户随即在 L16538 吐槽「你写12min？？？？」 | 简单手测说明不需要读完整 test-case registry 和两个 local-auth 脚本全文，只需已知的 3 个 UI 场景加已验证过的 local-test 启动命令；apply_patch 内容含反引号或美元符号时先用 String.raw 加转义一次写对，不要边写边试错。 |
| L7873 附近（跨区起点） | 等待串行 | 本 slice 整体等待/wait_agent 累计占比高（第 1 节：116 段合计 279.5 分钟，约占本 slice 46% 时钟），其中多段是等待真实浏览器/dev-server 冷启动或多 worker 并行收尾，非纯粹空转，但仍是本 slice 最大的时间池。 | 累计 279.5 分钟，最长单段 28.9 分钟（即上表 usage-limit 行） | 已通过并发分析确认多数等待期同时有 2 到 4 个 worker 在途（第 1 节并发分布），本身合理；主要可省的是上面两条已单独列出的 usage limit 空转与 evidence 逐条循环。 |

## 5. 用户纠偏事件

| 行号 | 用户原话摘要 | agent 当时在做什么 | 暴露的问题 |
| --- | --- | --- | --- |
| L7873（04:07:21） | 旧进程可杀 | 主控刚汇报要停掉两个旧 worktree 的前端进程 | 属于确认性指令，不是纠偏；确认主控识别到的清理范围正确。 |
| L14505（11:10:28） | 继续 | 会话刚从 usage-limit 错误引发的 29 分钟空转中恢复（skills/world_state 重注入） | 暴露子代理报 usage limit 错误后没有主动汇报中断原因，规则缺失：没有「carrier 因资源限制失败时立即告知用户」的动作要求。 |
| L15553（12:48:15） | 本次terminal 后再有问题closure就够了 | 主控正在跑第 3 轮全轨 terminal recheck（A/B/C/Safety），B/C/Safety 刚返回 PASS | 直接对应清单 A 第 5 项：不是每次 return 都要跑全套 do-review 这条规则在 terminal-final 阶段被执行到了第 3 次才被用户明确摁停，说明规则本身没有对同一 terminal 允许重跑几轮全轨设上限，主控靠自己判断，判断偏保守（每次有新 finding 就整轮重跑而不是只重跑受影响 track）。 |
| L15744（13:13:55） | 卡住了？ | 主控刚回复完一条状态消息（L15749），随即触发了一次 compacted 事件（L15765，13:17:29），中间有 3 分半没有可见产出 | 暴露 context 压缩发生在关键收口期、压缩本身不产出任何面向用户的进度信号，不是执行卡住，是上下文重建过程对用户不可见，需要一条正在重建上下文、稍后继续的最小提示。 |
| L15838（13:22:26） | 用 luna-worker 刷然后你验收，或者反过来你刷完lunaworker验收 | 主控正在自己直接 git grep 加 apply_patch 回刷稳定文档（L15803-L15833） | 对应清单 A 第 11 项延伸：用户认为稳定文档回刷这类收尾工作也该交给 worker 做，主控只做验收；主控采纳了反过来的版本（自己做最小回刷、派 luna-worker 独立验收），说明主控 context 卫生规则目前只覆盖长测试脚本，没有覆盖收尾文档写作这一类同样可以外包的工作。 |
| L16295（13:53:53） | 快速收尾不要再因为登记证据浪费时间了 | 主控正卡在 L16128 起的逐条 evidence add 循环加覆盖率轮询 | 直接对应清单 A 第 6/9 项：evidence 批量登记规则在同一 session 里被自己先做对（L15659/L15699）又做错（L16128），说明规则不是没读到，是执行期在压力下退化为更直觉的逐条写法；这是本轮最强的一条纠偏，且与 09-10 复盘里已经记录的重复登记成本线索（next-round-handoff.md 第 2 节）同类，说明这条 09-10 到 09-13 已经落地的规则（批量 evidence，commit 32bb5d7）在工具能力层面已经具备，但没有变成主控在长收口流程下的默认动作。 |
| L16402（14:01:14） | 总结一下本任务包做的事情，写一个环境重启+简单的手测说明 handoff 文档 | 主控准备开始写 handoff | 请求本身很小，但引出了下一条纠偏（L16538），暴露 handoff skill 的执行方式默认会做全量材料重读（读 SKILL.md 加 references 加 test registry 加两个脚本全文），没有一个 lite/简单模式的分支。 |
| L16538（14:13:54） | 写个交接文档你写12min？？？？ | 刚完成 handoff 文档并搬到 TEMP 目录 | 直接对应上一条：handoff 请求缺少一个按简单手测说明这种小范围请求缩短材料收集步骤的判断；agent 自己也承认是，写过度了（L16543），说明这是执行判断问题，不是规则未加载问题。 |

**重复纠偏识别**：本 slice 内**没有**出现「角色不是载体」一类在前半段反复出现的纠偏——本 slice 观察到的 spawn 行为本身已经正确使用 frontend-worker/backend-worker/luna-worker，说明该规则在前半段建立后，在本 slice 的执行期保持住了，没有复发。本 slice 内**新出现且值得跟踪是否会重复**的是「收尾/登记类工作挤占主线」（L15838 稳定文档回刷、L16295 evidence 登记、L16538 handoff 写作过度）——三次纠偏指向同一类问题：collateral/收尾工作的默认执行方式偏重，需要用户手动摁停，与 09-10 复盘 OF-04（收尾误作主线前置）同源。

## 6. 规则加载核对

- **本 slice 内没有出现 dispatcher 或任何 impl-package skill 正文的显式注入**：全文搜索 `<skill` 标签和「Implementer executor」字样，命中数均为 0。本 slice 唯一出现的技能相关注入是两次 skills_instructions 菜单列表（L10186、L14500），内容只是名称加一句描述加相对路径的清单，不含任何 SKILL.md 正文，例如 L10186 开头即为 `### Available skills` 逐条列出 imagegen/openai-docs/plugin-creator 等技能简介，不包含 dispatcher 的「Implementer executor」段。**结论**：主控在本 slice 的执行行为（正确使用 frontend-worker/backend-worker/luna-worker、正确的 delta review 单 reviewer 模式）依赖的是更早（前半段 session 或更早）已经加载并内化的规则记忆，本 slice 内没有重新读取正文的动作——这本身是好事（没有为了确认规则反复重读文档），但也意味着本 slice 无法从正文行号直接验证 dispatcher 当前版本是否真的写了「Implementer executor」段；仓库当前状态里 `skills/dispatcher/SKILL.md` 在本次分析所用的 agent-workbench 仓库里显示为未提交修改，属于另一条工作线，与本 rollout 分析的 kaispan-dev 任务包无直接关系，这里不做跨仓库推断。
- **impl-package 各 skill 的 cache 版本与仓库当前版本一致**：对 dev-with-track、do-review、backfill-stable-docs、impl-package、impl-planning 五个 SKILL.md 做 diff，`C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\skills\<name>\SKILL.md` 与仓库 `D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\skills\<name>\SKILL.md` 逐字节完全一致（diff 无输出）。关键规则「delta review 一名 reviewer」在两处的 dev-with-track/SKILL.md 第 14/22 行文本完全相同（主控直接实现时遵守相同 write ownership、自证和独立 delta review 要求；`$dispatcher` 是通用执行协作入口，拥有候选选择、委派合同、资源隔离、receipt、return、delta review 和 idle）。evidence add 支持数组批量的实现同样在 cache 侧的 impl_package_runtime/engine.py::command_evidence_add（第 1195 到 1225 行）里确认：`isinstance(payload, list)` 时整批合法才一次写入。**结论**：cache 与仓库源码没有漂移，L16128 的逐条循环退化不是因为装的是旧版本 CLI，而是执行期的写法选择问题（第 4/5 节已定性）。
- **spawn 时的 agent_type 与已加载规则要求一致**：61 次 spawn_agent 全部落在 luna-worker / backend-worker / frontend-worker / review-track-* 四类里（第 1 节），与「默认 luna-worker，前后端用具象 profile」的规则描述一致，没有出现与规则要求不符的 agent_type。

## 7. 新发现的可优化点

按预计节省时间排序：

1. **收尾/登记类工作缺少「lite 模式」判断，反复被用户摁停** —— 涉及 L15838（稳定文档回刷）、L16295（evidence 登记退化为逐条）、L16402 到 L16538（handoff 写作过度，12.7 分钟）。三次独立场景、三次用户手动介入，累计可辨识的超额时间约 19.5 加 12.7 分钟，外加一次未量化的文档回刷返工，合计 35 分钟以上。改法：给「收尾类」动作（evidence 批量登记、稳定文档回刷、handoff 撰写）建立一个默认「先用已有信息一次成文/一次提交，需要更多材料时才展开二次检索」的执行顺序，而不是先展开检索再收敛。
2. **apply_patch 两次因 JS 反引号/String.raw 转义写错触发 SyntaxError（L16478、L16515）**——两次都是同一类转义错误（patch 正文里含反引号或美元符号，第一次没转义直接失败），第二次仍然在同一份 handoff 文档编辑里踩了第二次。改法：在生成含代码块/路径变量的 patch 正文之前，固定先用 String.raw 加 String.fromCharCode(96) 组合模板，不要先试普通模板字符串再回头修。预计每次省 1 次失败往返（约 1 到 2 分钟加 1 turn）。
3. **Get-CimInstance/Get-NetTCPConnection 类进程诊断命令高频出现（84 次，占全部 exec 的 12%）**，多次是为了在 interrupt_agent 前确认 worker 存活状态（如 L8894、L8901、L8932），但确认之后仍然选择中断（如第 2 节第 8 项 L8946 的存疑案例）。改法：若诊断已确认 carrier 存活且 Responding:True，除非有更强证据（产出文件缺失、明确报错），不应仅因等待超时而中断——这条本身也是 OF-03 在本 slice 的具体触发条件，值得下一轮补一条「存活确认后不得仅因超时中断」的执行提示。
4. **trail append 128 次全部逐次单独 exec 调用**，每次都要单独起一个 PowerShell 进程拼 JSON 再 pipe 给 CLI（如 L7902、L7909、L7917），虽然每次单独调用是必要的（记录发生的时间点不同），但脚本模板高度重复。这里没有批量空间（每条 trail 事件对应一个独立的 dispatch/return 时刻），故不算浪费，只是提示：若未来要优化，方向是减少每次 exec 里重复的 `$ErrorActionPreference='Stop'; $cli='...'; $pkg='...'` 样板（可考虑用环境变量或短别名固化路径），而不是合并调用本身。
