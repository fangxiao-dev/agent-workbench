# W3 分析报告 —— tinymlops 任务包（09-14，call-grok 作 impl 载体的主执行）

rollout: `C:/Users/Xiao/.codex/sessions/2026/09/14/rollout-2026-09-14T13-13-46-01a09f9f-83e7-7f53-a1a0-ff73612c2297.jsonl`（实测 5704 行，非任务书里的 4800 行估计；cwd `D:\CodeSpace\dbe_jp\tinymlops-team-server-project`）。全部数据由 Python 流式解析产生，脚本与中间产物见同目录 `build_skeleton.py` / `analyze1.py` / `events.pkl` / `agents.pkl`；行号均为原 jsonl 的 1-based 行号，引用前已用脚本抽取该行验证。

## 1. 会话事实（先算数字，再写判断）

**时间跨度**：首条 `2026-09-14T11:13:49.290Z` → 末条 `2026-09-14T15:13:52.072Z`，约 4 小时（240 分钟）。

**turn / message 统计**：
- user turn 数：9（行 6、312、339、4128、4799、4818、5379、5442、5649；行 6 是系统附带的插件推荐 + 初始任务说明，不是纠偏）
- assistant message 数：84
- `compacted` 事件数：2（行 2029、行 5179）

**协作工具调用次数**（`function_call`，namespace `collaboration`）：

| 工具 | 次数 |
| --- | --- |
| `spawn_agent` | 78 |
| `wait_agent` | 121 |
| `list_agents` | 24 |
| `send_message` | 28 |
| `followup_task` | 7 |
| `interrupt_agent` | 6 |
| `request_user_input` | 0 |
| `create_thread` | 0 |
| `send_message_to_thread` | 0 |

`request_user_input`/`create_thread`/`send_message_to_thread` 本 slice 全程为 0——没有跨 session 通信，也没有用结构化 `request_user_input` 打断用户（用户的介入全部是主动发消息，见第 5 节）。

**spawn_agent 的 agent_type 分布**（78 次，`agent_type` 明文字段）：

| agent_type | 次数 |
| --- | --- |
| `luna-worker` | 21 |
| `review-track-spec` | 16 |
| `review-track-code` | 14 |
| `review-track-safety` | 12 |
| `review-track-standards` | 10 |
| `backend-worker` | 3 |
| `grok-monitor` | 1 |
| `frontend-worker` | 1 |

关键限定：**这 78 次里没有一次 `agent_type=call-grok`**。`call-grok` 全程是通过 `custom_tool_call`(`exec`) 调 PowerShell 拉起 `grok_task.py` 的**后台 Windows 进程**（`Start-Process ... -PassThru` 拿 PID，输出重定向到临时 `result.json`/`stderr.log`），不是 `spawn_agent` 协作节点；主控用 `grok-monitor`（`spawn_agent` 1 次 + `followup_task` 3 次续接同一个 monitor）去轮询多个 grok 进程的完成状态。详见第 2 节特别关注部分。

`followup_task` 复用分布（按 `target`）：`/root/tkt01_grok_monitor` 3 次（同一个 grok 监控 agent，存活 11:39→12:44 约 65 分钟，行 563 spawn → 行 1027 FINAL_ANSWER 前反复续接）；`/root/review_tkt02_frontend_a` 1 次；`tkt01_evidence_backend_luna`、`tkt03_edge_rollback_fix_luna`、`tkt03_server_projection_fix_luna` 各 1 次（同名 luna-worker 续接一次，用于消费自己上一轮的 fix 结果）。没有 agent 被 followup 超过 3 次。

**并发度**（对 78 个 agent 按 spawn→FINAL_ANSWER/interrupted 重建生命周期，78 个全部有明确结束时间，无缺失）：
- 至少 1 个 agent 在途的时间累计约 160 分钟（占 240 分钟总时长的 67%）
- 同时在途数分布（占"有 agent 在途"时间的百分比）：1 个 21.0%、2 个 20.9%、3 个 23.4%、4 个 17.1%、5 个 8.4%、6 个 2.8%、7 个 2.7%、8 个 2.7%、9 个 1.2%
- **最高同时在途 9 个 agent**；多数时间处于 2～4 个并发

**等待占比**：把"连续只有 `wait_agent`/`list_agents`，中间没有新 `spawn_agent` 或 `custom_tool_call`"的区间算作纯等待，全程共 60 段，累计约 67.4 分钟（约占总时长 28%）。最长一段 391.8 秒（约 6.5 分钟，行 1549→1593，12:24:49→12:31:21，等待 TKT-03 rollback 调查/评审收尾），第二长 384.5 秒（行 657→701，11:43:06→11:49:30）。等待期间主控没有自己动手替代，符合"等待超时只调整轮询，不触发中断/换人"的预期（对照第 2 节 checklist #16）。

**shell 命令分类计数**（`custom_tool_call` 且 `name=exec`，共 473 次；分类为脚本粗分类，边界不完全精确，"其他"里混有 `apply_patch`、临时 prompt 文件写入、`Get-Content` 读 SKILL/参考文档、进程状态查询等）：

| 分类 | 次数 |
| --- | --- |
| impl-package 语义 CLI（`impl_package_state.py`/`situation.py`） | 246 |
| 其他（patch/临时文件/文档读取/进程查询等） | 189 |
| git | 20 |
| 构建/typecheck | 10 |
| 测试（主控直接跑 `pytest`） | 8 |
| 容器/服务（docker） | 0（本 slice 未见主控直接调用 docker，只在用户话里提到 docker 不可用，见第 5 节） |

**evidence 登记：单条 vs 批量**——本 slice **没有出现任何一次 `evidence add` 调用**（对 `evidence add` 等模式做过全文匹配，命中的两处都是加载 SKILL.md 文档正文时提到这个命令，不是实际执行）。实际登记全部走 `trail append`（148 次，dispatch/worker-return/fact/escape 混合），其次是 `checkpoint`（6）、`recovery checkpoint`（5）、`recovery judgment`（3）、`ticket pending`（1）。**没有一次 `ticket satisfy`/`gate pass` 调用**——这与会话末尾主控自报"3 个 Ticket 尚未 closed"（行 5701）一致：本 slice 内没有 Ticket 被正式验收关闭，trail 只记录到 worker-return/finding 层。`trail append` 本身不支持数组入参（已用本机 `impl_package_state.py --package x trail append --help` 核对，命令要求单个 JSON 走 stdin）；多条 trail 事件是靠 PowerShell `foreach` 在一次 `exec_command` 里循环调用多次 CLI 子进程（例如行 253、1048、1269），减少的是主控与 exec 工具的往返次数，不是 CLI 层面的批量接口。`evidence add` 的批量数组能力（`isinstance(payload, list)` 分支，已在本机 `impl_package_runtime/engine.py:1195-1231` 核对存在）在本 slice 里完全没被触发——不是"该批量却逐条"，而是这条登记路径全程未被使用。

**重复执行**：用归一化命令文本查重（剔除临时路径/PID/时间戳后按完整命令去重，而非仅按前缀），能找到的真正"同一条命令连续跑 ≥3 次"案例是：

- `python -m pytest server/tests/test_flow5_v12_evidence.py -q --tb=short`：行 3912、3947、4061 三次跑同一测试文件（14:04:11→14:09:33，约 5 分钟），**但每次之间主控都在改代码**（第 4 次行 4082 换成多文件联跑），是"改一次跑一次"的修复-验证循环，不是盲目重试同一失败；仍计入第 4 节"绕远路"表，因为这段是主控亲自消费 pytest 失败输出（单次输出最长 10822 字符），而不是委托给 worker。
- 其余 `impl_package_state.py`/`situation.py` 前缀重复很高（如 92 次共享同一个 `$state=...` 变量赋值开头），但每次的 JSON 事件体不同，属于同一 CLI 高频合法使用，不算"重复执行"。

（第 2～7 节按此数据继续判定，随完成随追加落盘。）

## 2. 清单 A 逐条判定 · 执行阶段设计意图

1. **角色≠载体，按需并行多个** —— **已执行**。`luna-worker` 以 21 个不同 `task_name` 反复派发（如行 233/239/245 的三个并行 investigate）；`review-track-code` 被 14 次不同工况复用；`call-grok` 一次并行开 2～3 个 Windows 后台进程（行 503：`controlled-input`+`runtime-core` 两个；行 1823：`tkt02-server-v12`+`tkt02-frontend-v12`+`tkt02-edge-knn` 三个，均在同一次 `exec_command` 里用 `Start-Process` 循环拉起）；`backend-worker` 3 次分别对应 `tkt03_edge_rollback_backend`(4162)/`tkt03_server_projection_backend`(4383)/`tkt01_controlled_runtime_backend`(4433) 三个不同战线。没有观察到"一个角色只派一个 worker"的情况。

2. **派发用了正确 profile** —— **已执行**。默认调查/收口用 `luna-worker`（21 次）；前后端实现用 `frontend-worker`/`backend-worker`（各 1/3 次，均在行 4128 用户切换指令之后才出现）；用户显式要求时走 `call-grok`（shell exec，非 spawn_agent，见第 1 节与下方特别关注）。78 次 `spawn_agent` 里没有一次的 `agent_type` 是"与主控同 profile 的默认 agent"。

3. **ready≠dependency，且先分析 foundation/seam 再 fan-out** —— **已执行**。证据链：
   - 会话最开始先并行派 3 个只读 investigate（行 233/239/245，11:18:53～11:19:08，覆盖 runtime/evidence/tests 三个面），等它们收齐（365/409/487 FINAL_ANSWER）后才开始第一批 implement（481 起 apply_patch/call-grok），符合"先分析 foundation/seam，后 fan-out"。
   - TKT-02 的 investigate（行 616/622/628，11:42:18～11:42:33）在 TKT-01 尚未 closed（TKT-01 的 closure lane 在行 1668 起，12:33 才开始）时就已启动——提前调研不依赖 ready 状态。
   - TKT-03 的 investigate（行 1528/1534，12:24:19～12:24:27）同样在 TKT-02 尚未 closed（TKT-02 closure 在行 3168 起，13:39 才开始）时启动。
   这两处"下游提前调研"都发生在对应上游已完成只读调查、拿到可信的 seam 认知之后，不是无脑抢跑。

4. **没有因授权/formality 停下来问，只在真正方案不明时返回** —— **已执行**，且有一次高质量正例：行 1471（12:22:48）主控明确写道"evidence-core 出现了唯一真实的业务歧义，已按 Track C source recheck 证实：当前 Spec 没定义'新 logical run vs 崩溃续跑'的边界，也没明确 drift/related-metrics 是否 byte-exact 重放……请确认采用这条语义，或指出不同边界；**其余 lane 会继续，不因这个局部问题停摆**。"——这是先用一个独立 reviewer（`recheck_evidence_sources`，行 1415 起）核实过 Decision/Spec 确实答不了，才停下来问，并且明确声明只锁局部候选。用户在行 4818（14:37:41，约 2 小时后）才正式确认语义；期间行 3905 还发生一次 `escape` 事件——Grok 返回 HTTP 402 后，主控援引用户"禁止因授权/formality 停止开发"的规则，**自己接管**完成 bounded 修复而不是停下来问或干等，这正是规则要求的行为。全程 0 次 `request_user_input`。

5. **每个含代码的 return 派独立 delta review，不是每次都跑全套 do-review** —— **部分执行，证据显示有差异化但无法逐一验证是否都必要**。观察到的轨数并不统一：`review_controlled_input_a/b/c/d`、`review_runtime_core_a/b/c/d`、`review_evidence_core_a/b/c/d`（TKT-01 三条 foundation 线，行 902 起）、`review_tkt02_edge_knn_a/b/c/d`、`review_tkt02_server_a/b/c/d`、`review_tkt03_handover_a/b/c/d`、`review_tkt03_edge_rollback_a/b/c/d`（行 2386～4522）都是完整 4 轨（A 代码/B 规范/C 规格/D 安全）；而 `review_tkt02_frontend_a/c`（仅 2 轨，行 2223/2229）、`review_tkt03_frontend_projection_a/c`（2 轨，行 4582/4588）、`review_tkt03_server_projection_a/c/d`（3 轨，无 B，行 4610/4616/4631）、`review_tkt01_controlled_wiring_a/c/d`（3 轨，无 B，行 4697/4762/4772）是精简轨数。这说明主控确实在按 material risk 做取舍（前端类改动更常见地被砍掉 B/D 轨），但由于 TKT-01/02/03 全部涉及"设备本地 KNN 治理 + rover 运行时状态机 + drift 证据"这类天然 shared-seam/并发/数据完整性场景，本分析无法在不逐份核对 do-review ledger 的 material-risk 判定依据前提下断言哪些 4 轨是"该省的全套"。没有发现无代码变更的纯调查/纯收口被套上多轨审查的反例。

6. **evidence 登记走批量而不是逐条；登记不挤占业务推进** —— **本 slice 无相关场景**。见第 1 节：全程 0 次 `evidence add` 调用（无论单条还是批量），实际登记走 `trail append`（148 次，每条一次子进程调用，靠 PowerShell foreach 打包进同一次 exec 减少往返，而不是 CLI 层批量）。无法判定"批量 vs 逐条"这条规则在本 slice 的执行情况，因为这条登记路径根本没被触发。

7. **局部 barrier 只扣受影响候选（OF-01 复发检查）** —— **已执行**，证据同第 3 条：TKT-02/TKT-03 的调查与部分实现在上游未 closed 时就已推进；行 1471 的业务歧义只锁住 evidence-core 这一条线，TKT-02/TKT-03 的其他 lane（如行 1823 起的 `tkt02-server-v12`/`tkt02-frontend-v12`/`tkt02-edge-knn` 三个 Grok 实现）在等待期间照常并行推进，没有被这个局部 barrier 拖住。

8. **没有无正当理由中断 worker（OF-03 复发检查）** —— **已执行**。全程仅 6 次 `interrupt_agent`，全部集中在行 5655～5680（15:12:47～15:13:04），逐一列出：

   | 行号 | target | 当时状态 | 理由 |
   | --- | --- | --- | --- |
   | 5655 | `closure_tkt03_server_projection_a` | running | 用户"我要重启电脑了，这一批回来先停下来"（行 5649，用户取消） |
   | 5660 | `review_tkt01_evidence_final_a` | running | 同上 |
   | 5665 | `review_tkt01_evidence_final_b` | running | 同上 |
   | 5670 | `review_tkt01_evidence_final_c` | running | 同上 |
   | 5675 | `review_tkt01_evidence_final_d` | running | 同上 |
   | 5680 | `tkt03_edge_rollback_fix_luna` | running | 同上 |

   6 次全部对应"用户取消"这一允许类别（行 5649 用户明确要求停），没有因超时/换人/机械判断而中断的案例。

9. **收尾动作没有挡住主线交付（OF-04 复发检查）** —— **部分执行**。没有发现 backfill/文档动作直接阻塞主线交付的证据（trail/checkpoint 调用普遍在 1～3 秒内完成，行 4289/4307/4316 等 worker-return 记账都是即时追加）；但 `impl-package` 语义 CLI 调用占了全部 473 次 shell 调用的 52%（246 次），量级偏高，计入第 7 节作优化建议而非本条违反。

10. **worker 有自己的 worktree** —— **已执行**。观察到 `.worktrees\tkt01-controlled-input`、`tkt01-runtime-core`、`tkt01-evidence-core`、`tkt02-server-v12`、`tkt02-frontend-v12`、`tkt02-edge-knn`、`tkt03-edge-handover`、`tkt03-edge-rollback` 等按 candidate 分的独立 worktree（如行 474 的 `Preparing worktree (new branch 'codex/tkt01-controlled-input')`），物理写集按 lane 隔离。

11. **主控 context 卫生：长测试/脚本包给 worker 跑** —— **现场被违反（一处，情有可原）**。行 3905 的 `escape` 事件里主控决定亲自接管 Grok 因 402 中断的 bounded 修复（理由："owner explicitly forbids stopping development…and the partial write-set is isolated to four reviewed files"），随后主控自己连续 4 次直接跑 `pytest server/tests/test_flow5_v12_evidence.py`（行 3912/3947/4061/4082，14:04:11～14:10:12，约 6 分钟），把失败堆栈直接读进自己的 context（单次最长 10822 字符，行 3912→3915 的输出）。这段调试本可以委托给一个 luna-worker 去跑并只回报结论，主控此处选择自己动手，理由是 grok 已经两次因账户余额耗尽失败、且写集很小——是权衡后的合理选择，但确实与"主控只要进度和结果，不要污染自己 context"的要求不完全一致。

12. **子代理没有越权** —— **已执行（样本内）**。抽查到的 `agent_message` FINAL_ANSWER 都聚焦在被交代的 investigate/review/fix 范围内（如行 4715/4725/4744/4768 的四份 review 报告只报告 finding 而不擅自修复），没有发现子代理越权改写决策或扩大范围的证据。受限于 `spawn_agent`/`followup_task` 的 `message` 字段是加密文本，无法验证 brief 原文，只能从 FINAL_ANSWER 输出侧核实。

13. **汇报形态：worktree/branch/comparison head 讲清楚，没有内部术语** —— **已执行（样本内）**。抽查的几条状态汇报都具体且不含晦涩内部术语，例如行 4804："从现在起新派发的 Backend、Frontend、Track A/B/C/D reviewer 统一使用 `luna-worker`（Luna / max）……已经在运行、且在此消息前启动的 reviewer 不重启，避免丢失进度"；行 5447："Docker 相关验证先标记为延后，不会阻塞代码开发、单元/集成测试或审查；我已通知所有在途 lane 禁止启动/依赖 Docker"；收尾消息行 5701 列出具体 commit（`ce063aac`、`f3e05d0a`）并说明"Edge rollback 未提交改动已原样保留"。没有发现"业务比较点"一类让用户看不懂的内部黑话。

14. **跨 session 通信** —— **本 slice 无相关场景**。`create_thread`/`send_message_to_thread` 全程 0 次。

15. **model/profile 档位遵守用户降级指令** —— **已执行**。已用本机 `agents/*.toml` 核对：`luna-worker`=`gpt-5.6-luna`/`max`，`backend-worker`/`frontend-worker`=`gpt-5.6-terra`/`high`，`review-track-*`=`gpt-5.6-sol`/`high`(code)或`medium`(standards/spec/safety)。行 4799（14:36:16）用户下达"backend、frontend、review 各轨全部降级为 luna/max"后，行 4804 主控立即确认改用 `luna-worker`；此后所有 spawn（行 5190/5308/5314/5505/5511/5517/5567/5573/5579/5586，共 10 次）的 `agent_type` 无一例外全部是 `luna-worker`，没有出现降级指令后仍派 `backend-worker`/`frontend-worker`/`review-track-*` 的反例。

16. **长寿命 subagent 退化** —— **证据不足，本 slice 未见确证**。本 session 最长寿命 agent 是 `grok-monitor`（行 563 spawn，`followup_task` 续接 3 次，行 1027 FINAL_ANSWER 前存活约 65 分钟），但 9 条用户发言里没有一条提到"降智"或类似质量下降的抱怨；抽查到的 FINAL_ANSWER 内容也没有表现出结构性退化的迹象。样本有限（未逐条通读 grok-monitor 每次 followup 的中间输出），不排除更细粒度的退化，但没有直接证据支持"发生过"。

## 3. 清单 B 逐条判定 · 设计阶段设计意图

**本 slice 不含完整设计阶段。** 会话开场（行 15）主控明确表述"我会只读核验指定 worktree 的目录、HEAD、分支、package entry、active checkpoint 与 validate 锚点；任一不符立即停止"，随后加载的是 `handoff-to-new-session`（行 60）与 `dev-with-track`/`dispatcher`（行 131）——说明这个 session 是**从既有 checkpoint/handoff 恢复后直接进入执行**（`dev-with-track`），package、Decision、Spec、Ticket 在本 rollout 开始前就已存在（行 200 读到的 Implementation Plan 标注 `Created: 2026-09-14`，但那是同一天更早的另一次 req-align/impl-planning/to-tickets 会话产出，不在本文件内），本 slice 没有出现过 `req-align`/`impl-planning`/`to-tickets` 的**初始**全套流程，也没有出现 `handoff-to-new-session` 被**主动调用去交接给别的 session**（只在开场读取了这个 SKILL.md，像是核对自己是不是该走恢复路径，不是本 slice 在做交接）。

唯一例外：行 1471～5152 之间出现了一次**局部 req-align patch 循环**——`recheck_evidence_sources`（行 1415 起）核实 Decision/Spec 确实没有定义 logical run 语义和 drift/related-metrics 重放语义，主控据此在行 1471 向用户提出确认请求，用户在行 4818 回复权威语义后，主控在行 4942 显式声明"`req-align` 现在开始执行：先加载其 Decision/Spec 更新规则，再把你确认的 logical-run 与 byte-exact replay 语义写入权威合同；这一步只更新合同，不夹带实现"，随后在行 5014/5021/5028/5039/5053 对 `decision.md`/`spec.md`/`contract-design.md` 做了针对性 patch，行 5152 提交为 commit `93b2607d`。按这一次局部循环可以回答清单 B 里少数几条：

1. **是否先判 contract impact，走 fast path 还是 Decision/Spec gate**：这次是先由 reviewer（`recheck_evidence_sources`）核实"Spec 确实答不了"，再触发 Decision/Spec gate（不是走 fast path 直接改代码），花的时钟集中在**等用户确认**（1471→4818，约 2 小时15分，期间主控没有闲置，其余 lane 照常推进），而不是花在写材料本身（req-align 自己动手只用了 4942→5152 约 10 分钟）。
2. **Spec 范围识别是否区分"修改范围"与"兼容性验收范围"**：行 5152 的助手消息提到"记录了只需重验 TKT-01 与 TKT-02 runtime-integration 的 affected subset；其他已通过证据保留"——这说明这次 patch 明确做了兼容性验收范围的收窄判断，而不是无差别要求全量重验。
3～8 条（Ticket 依赖粒度、验收证据是否过度收集、约束来源可追溯性、独立审阅成本/采纳率、handoff 交接质量、设计阶段 subagent 派发时机）：**本 slice 不含完整设计阶段，没有对应的原始设计素材可供判定**，不做推测性回答。

## 4. 绕远路事件表（本报告的重点）

| # | 触发行号 | 类型 | 现场描述 | 代价 | 一步到位应该怎么做 |
| --- | --- | --- | --- | --- | --- |
| 1 | 1823（launch）→ 2956（失败）→ 2983/2990（恢复） | 工具环境失败 | TKT-02 Server Flow5 v1.2 的首次实现整段交给 `call-grok`；这一个 Grok 会话跑了 46 次模型调用、累计 790 万 token（含缓存读 743 万）、耗时约 48 分钟后被 `max_tokens_truncation` 直接打断，留下一个未提交的 dirty diff。主控随后写 recovery prompt（行 2983）："The previous Grok exhausted its output-token budget after implementing an uncommitted bounded diff. Do not restart or discard it. Inspect the current dirty worktree and finish the same lane with minimal narration."，靠同一 worktree 里续接一个新 grok 进程才把这条 lane 捞回来。 | 主控侧交互次数不多（约 3～4 次：launch/写 recovery prompt/relaunch），但这条 lane 的 wall time 从 12:43:40 到 13:32:34 约 49 分钟全部耗在"跑到失败才发现"上，且失败只能靠主控事后读 `result.json` 里的 `error.message` 才能确诊。 | `call-grok` 派发前就该给单轮任务设更保守的 `--max-run`/输出预算上限，或者要求 Grok 每完成一个子步骤就提交一次（增量 commit），这样即使中途被截断也能从最近一次 commit 续接，不必等 48 分钟才知道整段白跑。 |
| 2 | 3583（launch）→ 3892（失败,402）；3853（launch）→ 4144（失败,402） | 工具环境失败 | Grok Build 账户余额耗尽（HTTP 402 "usage balance exhausted"），先后打断两条不同 worktree 的 grok 进程：TKT-02 Server v1.2 findings-fix（行 3583 launch，约 10 分钟后行 3892 失败）和 TKT-03 Edge rollback 实现（行 3853 launch，约 11 分钟后行 4144 失败）。第一次失败后主控援引用户授权规则自行接管收尾（行 3905 escape 事件，合规行为，见第 2 节 #4/#11）；第二次失败几乎与用户在行 4128 决定改用 `frontend-worker`/`backend-worker` 同时发生。 | 两条 lane 各损失约 10～11 分钟 grok wall time；更大的代价是这直接促成了本 session 唯一一次载体级架构调整（call-grok → frontend/backend-worker，行 4128），此前投入在 call-grok 载体上的 prompt 编写、进程管理脚本全部要为剩余 Ticket 重做一套派发方式。 | `call-grok`/`grok_task.py` 应该在真正下发大任务前先探测账户余额/额度（wrapper 起跑前一次轻量余额检查），临界时提前把 quota 风险汇报给主控，而不是等两条并行 lane 同时把账户烧穿才用 402 报错的方式发现。 |
| 3 | 3905（escape）→ 3912/3947/4061/4082（主控自跑 pytest） | 派发拓扑错误 | 主控接管上面第 2 条里断供的 TKT-02 Server v1.2 findings-fix 之后，没有把"改代码 + 跑测试"这段收尾工作重新委派给 `luna-worker`，而是自己连续 4 次直接跑 `python -m pytest server/tests/test_flow5_v12_evidence.py`（14:04:11→14:10:12），把测试失败堆栈直接读进自己的对话 context（单次输出最长 10822 字符）。 | 主控 context 里吃进至少 13639 字符的测试输出；6 分钟内 4 轮改码-验证循环全部占用主控自己的 turn。 | 即便是范围很小的接管修复，也应该用一个 `fork_turns=all` 的 `luna-worker` 去跑完整的"改代码 + 跑测试"闭环，主控只消费最终的 DONE/PASS 摘要，不需要把中间失败堆栈吃进自己 context（对照第 2 节 #11）。 |

补充说明：本 slice 里还有一段长达约 2 小时 15 分钟的等待（行 1471 提问 → 行 4818 用户确认 logical-run 语义），以及若干次 6 分钟级别的 `wait_agent` 连续调用（如行 657→701），但经核实这些时间段内主控确实有 3～4 个 investigate/review agent 在真实并行运行（见第 1 节并发度数据），不是"无事可做的纯等待"，因此没有计入本表。

## 5. 用户纠偏事件

本 slice 共 9 条用户发言（行 6/312/339/4128/4799/4818/5379/5442/5649）。行 6 是插件推荐 + 初始任务说明，行 4818 是回答主控的语义确认请求，行 5379 是被打断后的"继续"，行 5442/5649 是操作性约束通知（docker 不可用/要重启电脑），都不属于对 agent 行为的纠偏，不列入下表。真正的纠偏/行为补充是以下 4 条：

| 行号 | 用户原话摘要 | agent 之前在做什么 | 暴露的问题 |
| --- | --- | --- | --- |
| 312（11:23:51） | "使用 `$call-grok` 代替 Impl/Fix 原来的 subagent……`$dispatcher` 定义的 impl（含两个 role）、fix 都是角色，不是载体本身，可按需并行创建多个……Tickets 的 ready 状态只是 ticket 粒度，不是 dependency……禁止一切因为授权、formality 停止开发……只有方案不明且 decision/spec 均无法提供答案才能停下来" | 刚完成 3 条只读 investigate（行 233/239/245），还没有开始任何 implement/fix 派发 | 这是一条主动的"调度行为补充"，不是纠正已发生的错误，但它把角色≠载体、ready≠dependency、禁止因授权停工三条规则一次性显式摆出来——说明这三条规则即使已经写在 `dispatcher`/`dev-with-track` SKILL.md 正文里（第 6 节会核对版本），用户仍然认为需要在会话里再明说一遍，可能是因为 SKILL 正文的表述是隐含的（"按 effect footprint 判断并行"）而不是用户期望的显式"角色可按需建多个"措辞。 |
| 339（11:24:49） | "`call-grok` 同样是逻辑角色定义，实际可以分多个" | 刚读完 `call-grok` 的 SKILL.md 和 caller-contract.md（行 318-330），并回复"改由 `$call-grok` 作为载体"（行 317，用词是"作为载体"，单数语气） | 这是对行 312 规则的**同一会话内二次重复**，间隔仅约 1 分钟。根因很具体：主控把用户临时指定的"用 call-grok 代替 subagent"这条覆盖指令，理解成"call-grok 这个技能本身就是唯一载体"，而没有把它套进"角色可以按需并行开多个实例"的同一套框架——说明 312 的规则在措辞上是针对 `dispatcher` 定义的 impl/fix 角色，模型没有自动泛化到用户刚指定的替代载体上。这不是"规则没读到"，是"规则的适用范围没有正确泛化"。 |
| 4128（14:12:15） | "改用 `@frontend-worker` `@backend-worker`" | 前一小时里两次遭遇 Grok Build 账户 402（usage balance exhausted，行 3892、4144）和一次 max_tokens 截断（行 2956），其中一次已经让主控自己接管收尾（行 3905 escape） | 这不是"规则缺失"，而是**载体本身失效**（外部 API 账户余额耗尽）触发的用户决策：把 Impl/Fix 的载体从 `call-grok` 换回仓库默认的 `frontend-worker`/`backend-worker`。值得注意的是 `dispatcher` SKILL.md 正文（行 135 已加载）本来就有"## Implementer executor"一节明确写着"前后端使用具象 executor：`frontend-worker`/`backend-worker`……同一 profile 可并行派发多次"——这条规则从会话第 11:16 分起就在 context 里，只是被用户在 312 的临时覆盖指令（"用 call-grok 代替 Impl/Fix 原来的 subagent"）盖住了，4128 是**撤回 312 的临时覆盖指令，回到 SKILL 正文本来就写好的默认值**，不是模型忘记读规则。 |
| 4799（14:36:16） | "之后的 backend、frontend、review 各轨全部降级为 luna/max" | 刚完成 TKT-01 controlled-wiring 的完整 4 轨 review（行 4697-5007，用的是 `review-track-*`/`gpt-5.6-sol` 档位） | 这是一条效率/成本导向的指令，不对应某条已写规则被违反；执行结果是合规的（第 2 节 #15：4799 之后 10 次 spawn 全是 `luna-worker`）。列入本表是因为它和 312/339/4128 一样属于"用户在执行过程中临时调整调度参数"的模式，值得和前三条一起看：这个 session 里用户至少 4 次要主动介入调度层参数（载体选择、并行语义、profile 档位），而不是让系统按预设规则自动收敛，说明当前 SKILL 正文对"何时该用哪个载体/档位"这件事留给主控的自主判断空间还是需要用户频繁校准。 |

**重复度**："角色不是载体"这条规则在本 slice 内被用户在 1 分钟内连续讲了两次（312 泛化版本 + 339 针对 call-grok 的具体版本），是本 session 复现频率最高的纠偏；4128 虽然表面是同一主题的第三次出现，但触发原因已经变成外部工具失效，不是规则理解问题。

## 6. 规则加载核对

本 slice 实际加载的相关 skill 正文（均已用行号定位并读取全文，见第 1～3 节引用）：

- `dispatcher`：行 131-135（`Get-Content` 并行读取），来源路径是 `C:\Users\Xiao\.codex\skills\dispatcher\SKILL.md`（不是任务书背景里说的"直接从仓库工作区加载"的 `D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md`，而是同步到 `~/.codex` 的安装副本）。
- `dev-with-track`：同一次调用，行 131-135，来源 `C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\skills\dev-with-track\SKILL.md`。
- `call-grok`：行 318（SKILL.md）、行 327（`references/caller-contract.md`），来源 `D:\CodeSpace\agent-workbench\skills\call-grok\`（这个是直接从仓库工作区读的，路径与用户消息里给的链接一致）。
- `do-review`：行 853（SKILL.md）、行 863（`references/reviewer-registry.json`），来源同样是 `...\impl-package\0.4.2\...`。
- `handoff-to-new-session`：行 60（SKILL.md），来源 `C:\Users\Xiao\.codex\skills\handoff-to-new-session\SKILL.md`。

**版本核对结果（用 `diff -q` 逐一核对本机文件，全部一致，无需展示 diff 内容）**：
- `C:\Users\Xiao\.codex\skills\dispatcher\SKILL.md` 与当前仓库 `D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md`（47 行）**逐字节一致**。
- `impl-package` cache `0.4.2` 里的 `dev-with-track/SKILL.md`、`do-review/SKILL.md`、`scripts/impl_package_runtime/engine.py` 与仓库 `D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\` 对应文件**逐字节一致**（plugin.json 标注版本号 `0.4.2`）。
- 结论：**本 slice 加载的所有 impl-package/dispatcher 规则都是当前版本，没有发现缓存滞后于仓库改动的情况。**

**"Implementer executor" 段与用户重复纠偏的关系**（呼应第 5 节）：行 135 读到的 `dispatcher` SKILL.md 正文里，"## Implementer executor" 一节原话就是"`implementer` 保留为逻辑角色，前后端工作使用具象 executor：frontend implementation → `frontend-worker`；backend implementation → `backend-worker`……同一 profile 可并行派发多次"——这条规则从会话第 11:16 起就已经在 context 里，且措辞已经很明确。用户仍在行 312/339/4128 三次谈到"角色不是载体"，但仔细看内容并不是同一件事：
- 312/339 谈的是 `impl/fix`（investigate/implement/fix/verify 四个通用角色）和用户当时临时指定的 `call-grok` 覆盖载体要不要按同一套"可并行多个"的原则处理——`dispatcher` 正文对通用角色的并行性表述是隐含的（"按当前动作的实际 effect footprint 判断"），没有 `Implementer executor` 那样点名式的"可并行派发多次"，所以用户在这里是在**补全一条 SKILL 正文里写得不够显式的规则**，不是模型没读到已有规则。
- 4128 谈的是 `frontend-worker`/`backend-worker` 本身，这条规则原文已经写得很明确，4128 纯粹是**撤回 312 的临时覆盖指令**（call-grok 因外部账户 402 失效），回到 SKILL 正文默认值，不涉及规则理解问题。

**主控 spawn 时用的 agent_type 与已加载规则的一致性**：`dispatcher` 正文要求"frontend implementation → frontend-worker；backend implementation → backend-worker"，本 slice 里 `backend-worker`(3 次)/`frontend-worker`(1 次) 的 4 次 spawn 全部发生在行 4128 之后（即用户把 call-grok 覆盖指令撤回、回到 SKILL 默认值之后），与正文要求一致；`review-track-*` 的 4 次 spawn 全部对应 `do-review` 的 Track A/B/C/D 命名，与 `reviewer-registry.json` 的 `default_tracks` 定义一致；`luna-worker` 用于 investigate/closure/降级后的 backend/frontend/review，与 `dev-with-track`"没有前后端归属的实现候选……继续沿用现有候选、上下文与资源判断"及用户 4799 的降级指令一致。没有发现 spawn 的 `agent_type` 与已加载规则要求不符的案例。

## 7. 新发现的可优化点

按预计节省的时间/turn 排序（均只涉及 impl-package 设计/实现与 Dispatcher 调度行为本身，不含业务验证/环境/Docker/训练跑批内容）：

1. **`call-grok` 载体没有派发前的余额/预算健康检查，失败只能靠"跑到一半才 402/截断"来发现**。第 4 节已量化：一次 max_tokens 截断浪费约 49 分钟 lane 时间（行 1823→2956），两次 402 各浪费约 10～11 分钟（行 3583→3892、3853→4144），三次合计约 70 分钟纯粹的"跑了才知道白跑"。`grok_task.py` wrapper 完全可以在真正下发大任务前先做一次轻量余额探测（或者复用同一账户最近一次调用的 usage 字段做粗略预判），账户临界时提前把风险告诉主控，而不是等两条并行 lane 同时把账户烧穿。这是本 slice 里单项预计可节省时间最大的一条，而且直接触发了行 4128 的载体级架构调整，影响面不止这 70 分钟。

2. **`trail append` 类记账调用全部靠主控手写内联 JSON 字符串拼接，样板量大**。246 次 impl-package CLI 调用里，`trail append`（148 次）和各类 dispatch/worker-return 事件都是主控在 PowerShell 里手写形如 `$event='{"subject":...,"kind":"dispatch",...}'` 的完整 JSON 字符串（例如行 260、494、556、1327、1474、1768、1785 等），每次都要重复 `subject`/`dispatch_id`/`candidate_id`/`resource_keys`/`receipt` 等固定字段名和转义规则。如果 `impl_package_state.py` 提供一个更薄的"从当前 situation 自动派生 dispatch_id/candidate_id 骨架，只需要填 diff 字段"的辅助子命令，或者 `dispatcher`/`dev-with-track` 的委派合同模板里内置一个可直接套用的 PowerShell 片段，可以省掉主控每次手搓 JSON 转义字符串的 token 和出错概率（本 slice 未观察到 JSON 转义出错的案例，但样板量本身就是成本）。

3. **`grok_task.py` 的启动样板（存在性校验 + 参数拼接）在每次 launch 里重复书写**。12 次 launch（行 503/549/1252/1369/1497/1823/2299/2490/2702/2990/3255/3583/3853）里，多次都带一段几乎相同的"检查 `$out`/`$err` 是否已存在，存在就 `throw`"前置校验（如行 2490/2702/2990/3255/3583/3853），以及固定的 `--cwd`/`--prompt-file`/`--max-run` 参数拼接。可以把这段前置校验和参数拼接收进 `call-grok/scripts/grok_task.py` 自身（wrapper 内部做幂等检查），或者提供一个更薄的 PowerShell 封装函数，减少主控每次 launch 都要重新写十几行 `exec_command` cmd 文本的 token 开销。

（次数是线索不是结论：第 1 条虽然只出现 3 次具体失败事件，但单次代价最大，排第一；第 2、3 条出现频率高但单次代价小，主要体现在 token/turn 的累积消耗上。）
