# W1a 分析报告 —— KaiSpan finance-document-review-rules 主执行前半段（L1–L7872）

rollout: `rollout-2026-09-13T20-21-39-01a09c00-e64b-7dd0-8c45-e7757ff0c462.jsonl`
本 slice 范围：L1（2026-09-13T18:21:41.122Z）～ L7872（2026-09-14T04:07:20.990Z），以 L7873 用户「旧进程可杀」为界（已核实：L7873 原文正是「旧进程可杀」）。

## 1. 会话事实（先算数字，再写判断）

统计脚本：`build_skeleton.py`（事件骨架）+ `stats1.py`（协作工具计数）+ `stats_shell.py`（shell 分类）+ `stats_wait.py`（等待占比）+ `stats_concurrency.py`（并发度，基于 `list_agents` 快照）。均只流式扫描 L1–L7872，未整读原文件。

**时间跨度**：L1 `2026-09-13T18:21:41.122Z` → L7872 `2026-09-14T04:07:20.990Z`，约 9 小时 46 分钟。

**消息计数**（`response_item`/`message`，按 `payload.role`）：
- user 消息：16 条
- assistant 消息：68 条
- developer 消息：8 条（含 app-context、多代理模式提示、ponytail 模式声明等系统级注入）
- `compacted` 事件：2 次

**协作工具调用次数**（`function_call`，`payload.name`）：

| 工具 | 次数 |
| --- | --- |
| spawn_agent | 88 |
| wait_agent | 218 |
| send_message | 45 |
| followup_task | 30 |
| interrupt_agent | 12 |
| list_agents | 44 |
| request_user_input | 0 |
| create_thread（主控发起） | 0 |
| send_message_to_thread（主控发起） | 0 |

注：`create_thread` / `send_message_to_thread` 作为 **`function_call_output`**（即本 session 是接收方）在本 slice 出现 3 次，均在开局（L10、L38、L87），是旧 session 通过 `codex_delegation` 向本 session 转交任务；本 slice 内主控自己没有发起过跨 session 通信。

**spawn_agent 的 agent_type 分布**（88 次里，明文可读）：

| agent_type | 次数 | 说明 |
| --- | --- | --- |
| luna-worker | 47 | fix / closure / review-delta / 长测试封装等默认载体 |
| backend-worker | 15 | 后端实现 |
| review-track-spec | 6 | do-review Track C（正式多轨复核的一部分） |
| explorer | 5 | 开局只读调研 fan-out（tkt01/02/03/04 map），**这批发生在 L732 用户纠偏之前** |
| review-track-code | 4 | do-review Track A |
| review-track-standards | 4 | do-review Track B |
| review-track-safety | 4 | do-review Safety 轨 |
| frontend-worker | 3 | 前端实现 |

**followup_task 复用同一 agent 的次数分布**（30 次，按 target 归并，取前几名）：
- `/root/review_api_entry_delta`：4 次（L3330, L4138, L4216, L4373）
- `/root/fix_api_entry_delta`：3 次（L3694, L3909, L4247）
- `/root/integrate_backend_residuals`：3 次（L7020, L7124, L7505）
- 其余目标各 1～2 次

单个 agent 存活时间最长的是 `/root/review_api_entry_delta`：从 L3208 spawn（2026-09-13T20:43:39Z）到最后一次 followup L4373（2026-09-13T22:42:01Z），跨约 2 小时（含中途 2 次 interrupt：L3308、L4211）。

**并发度**（基于 44 次 `list_agents` 快照，统计非 `/root` 的 `running` 数）：

| 同时在途 running 数 | 快照次数 |
| --- | --- |
| 1 | 5 |
| 2 | 13 |
| 3 | 7 |
| 4 | 9 |
| 5 | 5 |
| 6 | 2 |
| 7 | 1 |
| 8 | 2（峰值，L526，2026-09-13T18:35:44Z，5 个 explorer 调研 agent 各自还派了子 agent） |

多数时间落在 2～4 个并发（29/44 快照），符合"按依赖拆 lane 并行、但不无限制铺开"的预期。

**等待占比**（`stats_wait.py`：把连续的 `wait_agent`/`list_agents` 视为一段"主控自己没动手"区间，边界是任何 `custom_tool_call`（shell/patch）或新的 `spawn_agent`）：
- 共 182 段纯等待区间，累计 **7337 秒 ≈ 122 分钟**，占整个 slice 时钟跨度（586 分钟）约 **20.9%**。
- 最长单段：L3921→L3972，**415 秒**（约 6.9 分钟），发生在 2026-09-13T21:52～21:59，正是 F1-F4 讨论前后（同一时间窗口内也发生了 L3933/L3945/L3964 的用户纠偏，见第 5 节）。
- 次长：L556→L576，**314 秒**，发生在开局 explorer fan-out 等待期间（也是 L594 用户验收收缩批注插入的窗口）。

**shell 命令分类计数**（`custom_tool_call name=exec`，共 585 次，按命令文本粗分类）：

| 分类 | 次数 |
| --- | --- |
| impl-package 语义 CLI（`impl_package_state.py` / `situation.py` 等） | 213 |
| other（git worktree/patch/进程管理/pnpm 等未归类到下列的） | 175 |
| git（status/diff/log/add/commit/worktree 等含 `git` 关键字） | 146 |
| unknown（正则未提取到 cmd 文本，多为模板变量如 `Get-Content '${path}'`） | 42 |
| test（pytest/vitest/jest 等测试关键字直出现在命令行） | 5 |
| container | 4 |

`test` 类只有 5 次是因为大多数测试执行被包进复合 PowerShell 脚本或被派给 worker（脚本内部跑 `pnpm test`/`vitest`），root 自己直接敲的裸 `pytest`/`npm test` 很少；实际测试运行量远高于 5 次，只是大多不是 root 自己直接执行的裸命令。

**evidence 登记：单条 vs 批量**——本 slice 里 **没有一次**直接调用 `impl_package_state.py ... evidence add`（逐条或批量均无，已用正则核对 `state.py' --package '...' evidence` 零匹配）。证据的"登记"实际都走的是 `record-event`（`worker-return` / `judgment` kind），其中 `evidence` 字段本身就是一个数组（如 L951、L2994、L2240 的 `evidence=@(...)`），且 L798 把 **2 条 worker-return 事件**用同一次 PowerShell 调用（数组 `$events=@(...)`）一次性登记。也就是说：本 slice 的证据登记事实上是"批量友好"的（同一命令里带数组字段/多条事件），但走的是 `record-event`，不是文档里专门的 `evidence add` 子命令——两者不是同一件事，不能把"记录时用了数组字段"直接等同于清单 A 第 6 条问的"`evidence add` 批量 vs 逐条"。

**重复执行**（归一化后 ≥3 次的命令，已核对是否为真重复）：
- `situation.py render --package ... --json`（读 digest/状态）：**15 次**，分布在 L468～L7814 全程，属于低成本状态轮询（无副作用），不构成有意义的"重复取证"。
- `git status --short; git diff --stat; git log -N --oneline` 系列（N 从 1 到 8 不同）：合计 40+ 次，是每次 worker return 后的标准现场核对，命令模式相同但 `-N` 参数随进度变化，**不是同一验证的重复**，是常规节拍检查。
- `Get-Content -LiteralPath '${path}' -Raw` 命中 14 次：这是脚本模板，`${path}` 在真实调用前已被具体路径替换，归一化脚本在变量替换前提取了模板文本，**这不是真实重复**（已核实是 14 次读取 14 个不同的 skill/reference 文件），特此标注为方法局限而非结论。
- 未发现有实质意义的"同一条件的验证命令被重复跑 ≥3 次"的浪费型重复。

---
## 2. 清单 A 逐条判定 · 执行阶段设计意图

1. **角色≠载体：同一角色按需并多个并行 worker**——**已执行**。证据：L2908/L2914/L2920/L2926 四次连续 `spawn_agent(agent_type=backend-worker)`（`impl_api_entry`/`impl_unit_profile`/`impl_receiver_followup`/`impl_ocr_lineage`），同一 `backend-worker` 角色并行 4 个实例；L3139/L3196/L3202/L3208 四次连续 `spawn_agent(agent_type=luna-worker)` 做并行 delta review。没有出现"每角色只派一个"的收缩。

2. **派发用了正确 profile**——**现场被违反，随后纠正**。L475–L499：开局 5 次 `spawn_agent(agent_type=explorer)` 做只读调研 fan-out。L732 用户纠偏："subagent 默认是 `@luna-worker`，我看到你派送的是默认和自身一样的"。L737 assistant 承认"把调查职责误当成了载体 profile"，但给出的修正方案是"统一用 `@luna-worker` 作为默认载体，在 brief 中声明 `frontend impl / backend impl` 等逻辑角色"——这个修正本身仍然错误：dispatcher `SKILL.md` 的"Implementer executor"段明确前端/后端实现要用具体的 `frontend-worker`/`backend-worker` executor profile，不是塞进 luna-worker brief 里的文字角色。L777 用户第二次纠偏（情绪化）："`@frontend-worker` `@backend-worker` 这个不是默认的啊，我已经 `$dispatcher` 两次了"。L782 assistant 最终给出正确规则并从 L786 起严格执行：前端→`frontend-worker`、后端→`backend-worker`、其余→`luna-worker`。**L786 之后到 L7872，未再出现"默认与主控同 profile"或"前后端实现误用非专用 profile"的情况**——纠正是稳定的，没有反复。

3. **ready≠dependency，且先分析 foundation/seam 再 fan-out**——**已执行**。L622（AGENT_MSG `/root/tkt03_prep_map`，FINAL_ANSWER）："TKT-03 可提前拆出 4 条独立 lane；真正依赖 TKT-01/TKT-02 的只是 approval/profile 接线，不是整个 Ticket"——在 TKT-01/02 未验收时已完成调研并识别可提前的子集。L2227 用户 roadmap 本身要求"先结束两条 closure、合入 foundation、再并行业务 lane"，L2908 起的四条业务 lane 确实是在**foundation 合入+checkpoint 之后**才 fan-out（非补丁式为并行而并行）。

4. **没有因授权/formality 停下问用户；只在真正方案决策上返回**——**部分执行/现场被违反**。就"授权/formality"字面场景：全程未见因为凭证、GitHub 访问、任务包不匹配等借口而停止推进的证据，L453 用户已明确授权后这条被严格遵守。但"只在真正方案决策上返回"被违反：L3933 用户"非阻塞提问：F1-F4 只能线性解决吗？"，L3938 assistant 回答后**直接结束了该 turn**（L3944 `turn_context` 显示新 turn 开始，中间无任何 spawn/exec 动作，等了约 1 分 29 秒直到用户在 L3945 纠偏："我说了除了方案决策以外，禁止返回，也说了这是非阻塞提问"）。这不是"因授权/formality"停下，而是把一次非阻塞、非方案性质的提问误当作了回合终点——精神上仍是"不该停的时候停了"。

5. **每个含代码 return 派了独立 delta review，没有对每个 return 都跑 formal 多轨 do-review**——**已执行**。foundation 阶段（TKT-01 core、schema、TKT-04 accounting、TKT-02 contracts）跑了完整 `review-track-code/standards/spec/safety` 四轨（L1068–L1194、L1382–L1404、L1614–L1630）；L1253 用户纠偏"不是什么回来都要 do-review 全部的…别忘记 delta review"之后，后续业务 lane（`impl_api_entry`/`impl_unit_profile`/`impl_receiver_followup`/`impl_ocr_lineage` 等）全部只派单人 `luna-worker` 做 `review_*_delta`（L3139 起），未见任何一次业务 lane 代码 return 之后遗漏 delta review 直接进入下一步的情况。

6. **evidence 登记走批量而不是逐条；登记没有挤占业务推进**——**本 slice 无该子命令的直接使用场景**。已用正则核对：本 slice 全程**零次**直接调用 `impl_package_state.py ... evidence add`（单条或数组均无）。证据登记走的是 `record-event`（`worker-return`/`judgment` kind），其 `evidence` 字段本身即数组（如 L951、L2994），且 L798 一次调用批量写入 2 条 worker-return 事件。这条路径客观上做到了"不逐条"，但不是清单问的那个专用子命令，如实标注为"未使用该机制，但用等价手段避免了逐条登记"。登记动作本身都是几秒钟的单次 exec，未见挤占业务推进的证据。

7. **局部 barrier 只扣受影响候选（OF-01 复发检查）**——**已执行，但证据受限于加密推理**。L3293/L3298/L3303/L3308 四次连续 `interrupt_agent` 同时中断了 4 个 delta-review agent（`review_unit_profile_delta`/`review_receiver_followup_delta`/`review_ocr_lineage_delta`/`review_api_entry_delta`），乍看像"一次性大范围打断"；但这 4 个本身就是同一批次、需要同一次修正的对象（L3274/L3279 之前已经各自 `send_message` 过一次新上下文），不是牵连了无关的独立 worker。当时其余在途 agent（如仍在跑的实现 lane）未见被一并打断的证据。**模型推理内容加密（`encrypted_content`），无法验证打断的具体理由文本**，判定基于可观察行为模式，非确定性证据。

8. **12 次 `interrupt_agent` 逐一列出、判定理由**——见下表。**所有推理内容均加密不可读**，只能凭前后文本/行为模式判断；除标注★的 2 次外，其余 10 次只能看到"`wait_agent` 超时 → `interrupt_agent` → 立即 `followup_task` 带新指令"的行为模式，不满足清单四类理由（用户取消/越权危险 mutation/不可恢复资源冲突/carrier 明确失败）中任何一类的**直接文字证据**，如实标注"证据不足以判定"，不做主观补齐。

| 行号 | 目标 | 中断前状态 | 可观察理由 | 判定 |
| --- | --- | --- | --- | --- |
| L2467 | `/root/fix_tkt02_contracts` | running，60s wait 超时 | 无文字说明，紧接 followup 新 brief | 证据不足 |
| L2583 | `/root/closure_tkt02_contracts` | running | 无文字说明，紧接 followup | 证据不足 |
| L3293 | `/root/review_unit_profile_delta` | running，120s wait 超时 | 见第 7 条：批量重新对齐 4 个 review agent | 证据不足（但非无关牵连） |
| L3298 | `/root/review_receiver_followup_delta` | running | 同上 | 证据不足 |
| L3303 | `/root/review_ocr_lineage_delta` | running | 同上 | 证据不足 |
| L3308 | `/root/review_api_entry_delta` | running | 同上 | 证据不足 |
| L3689 | `/root/fix_api_entry_delta` | running，120s wait 超时 | 无文字说明，紧接 followup | 证据不足 |
| L3899 | `/root/fix_api_entry_delta` | running，120s wait 超时 | 无文字说明，紧接 followup（第二次对同一 target） | 证据不足 |
| L3904 | `/root/fix_ocr_lineage_delta` | running | 无文字说明，紧接 followup | 证据不足 |
| L4211 | `/root/review_api_entry_delta` | running | 无文字说明，紧接 followup | 证据不足 |
| L5834★ | `/root/assemble_backend_accounting` | running | assistant 明文：合并卡在同一组 `billing.service` 冲突，"已经明显超过正常 cherry-pick 时间"，中断后不回滚已合入 commit，改派新 fix 载体 | 符合"不可恢复资源冲突/carrier 明确失败" |
| L7691★ | `/root/integrate_backend_residuals` | running | assistant 明文：final carrier 已 clean 固定很久，合并已完成，剩余只是未收敛的验证等待，中断以免"重复 focused 占住时间" | 符合"worker 已达终态，继续等待无意义" |

10/12 次缺乏可读理由文本本身是个值得关注的模式：多数中断发生在 `wait_agent` 超时之后，而不是发生在能看到的"越权/危险 mutation"事件之后，提示实际触发条件更可能是"等太久没耐心" 而非清单列出的四类正当理由——但由于推理加密，不能坐实为违反，只能如实报告证据边界。

9. **收尾动作（backfill/登记/文档）没有挡住主线交付（OF-04 复发检查）**——**已执行**。checkpoint/commit/state 记录类 exec 调用均为几秒到十几秒（如 L755 耗时 7.9s、L2872 的 `git add`+`trail append` 耗时可从相邻时间戳推算在 10 秒量级），穿插在主线动作之间，未发现登记/文档动作单独阻塞主线推进超过一个正常节拍的证据。

10. **worker 有自己的 worktree**——**已执行**。至少 15 次 `git worktree add`（L768、L824、L867、L911、L2879、L3450、L4149、L4909、L5636、L5704、L5900、L5974、L6305、L6379、L6455、L6513、L6675 等），每条 fix/impl/review lane 基本各开一个独立 worktree，符合"写集不能精确切割时先分 wt"的要求。

11. **主控 context 卫生：长测试/长脚本包给 worker 跑**——**现场被违反一次，随后纠正并保持**。L2808/L2837：root 自己直接执行 `pnpm --filter @kaispan/contracts exec vitest run ...` 与 `pnpm --filter @kaispan/db exec vitest run ...`（合流级 focused 验证，L2769/L2788 assistant 消息描述的就是这次），是主控亲自吞测试输出。L2884 用户纠偏："长测试脚本也可以用 `@luna-worker` 包起来跑，你只需要知道大致进度和最终结果即可，不要污染你的 context"。L2893 assistant 承诺"PostgreSQL/EV-3/terminal-final 这类长验证统一交给 `@luna-worker`"。**已核实 L2884 之后到 L7872，root 再没有直接执行过 `pnpm ... vitest/test` 类命令**（`find_long_tests_after.py` 全区间扫描零命中），长验证转为 `research_unit_profile_ui`(L5053)、`verify_ev1_shared_rules`(L7713)、`verify_ev3_accounting`(L7719)、`verify_ev2_postgres`(L7806) 等 luna-worker 任务，纠正稳定。

12. **子代理没有越权；主控没有把裁决权让给子代理**——**本 slice 无明确违反场景**。抽查的 AGENT_MSG 返回（如 L622、L749、L2274、L2294 等）均是"只读结论/EVIDENCE_SUFFICIENT/PASS"这类事实性汇报，裁决动作（是否采纳、是否进入下一步）均由 root 通过后续 `send_message`/`spawn_agent`/`record-event` 完成，未发现子 agent 自行写 Gate 或自行判定 closure 的证据。

13. **汇报形态：worktree/branch/comparison head 是否说清楚；有无用户看不懂的内部术语**——**基本已执行，个别用语偏内部化**。多数状态汇报（如 L80 anchor PASS、L2637 TKT-02 closure 残留说明、L5833 中断说明）都带具体分支名/commit hash/文件路径，可核实。唯一偏内部化的例子：L7867 assistant 消息用了"独立 reviewer 固定比较点"这类内部术语描述 detached HEAD 问题，但同时给出了具体 commit hash（`79ed0e0a`/`4bd88896`）和修复动作，不算完全不可懂，只是术语选择不够口语化。

14. **跨 session 通信（`create_thread`/`send_message_to_thread`/问原 session）**——**已执行**。本 slice 内主控自己没有发起过 `create_thread`/`send_message_to_thread`（次数为 0，见第 1 节）；作为接收方收到的 3 次 `codex_delegation`（L10、L38、L87）都只做了只读 anchor 核对，符合 L352/L390 用户"直接问，不要 thread-harness"的精神（本 slice 里没有出现主控自己再发起 thread-harness 式跨 session 询问），未见多余汇报。

15. **model/profile 档位：用户降级指令是否被遵守**——**本 slice 无相关场景**。全文搜索未发现"luna/max"、"sol/medium"或类似模型档位降级指令。

16. **长寿命 subagent：followup 次数过多、跨时间过长导致输出退化**——**本 slice 无明确退化证据，但有观察点**。复用次数最高的是 `/root/review_api_entry_delta`（4 次 followup，含 2 次 interrupt，存活约 2 小时，L3208→L4373）和 `/root/integrate_backend_residuals`（3 次 followup，最终在 L7691 被以"carrier 已达终态"为由中断）。本 slice 内未见用户使用"降智"等字眼投诉这两个 agent 的输出质量，也未做输出前后对比核实是否真的退化——如实标注为"证据不足，值得后续 slice 关注"，不做推测性结论。

---
## 3. 清单 B 逐条判定 · 设计阶段设计意图

**本 slice 不含设计阶段，跳过逐条判定。**

依据：L58–L80 一开局的只读 anchor 核对已显示 `package validate` 返回 `active=true`，`.impl-package/state.json` 等权威文件已存在，说明 Decision/Spec/Plan/Ticket 在**更早的会话**中已经创建完毕；本 slice 从 L1 起就是纯执行阶段（`dev-with-track`），全程没有出现 `req-align`/`impl-planning`/`to-tickets`/`handoff-to-new-session` 的正式流程调用。

唯一的例外是 L600–L610：在 L594 用户对验收设计做出收缩批注后，assistant 读取了 `impl-planning` 的 `SKILL.md` 与 `common-misjudgments` 参考页——但这只是"编辑 plan.md 前先确认怎么改才不违反规则"的查阅动作，不是重新走一次 impl-planning 的正式流程（没有产出新的 Decision/Spec，也没有重新做 Ticket-only Composition 判断），因此不构成"本 slice 含设计阶段"。

---
## 4. 绕远路事件表（本报告的重点）

| 触发行号 | 类型 | 现场描述 | 代价 | 一步到位应该怎么做 |
| --- | --- | --- | --- | --- |
| L475–L786 | 派发拓扑错误 | 开局用 `agent_type=explorer` 做 5 个只读调研 fan-out，被用户在 L732 纠偏为"默认和自身一样"；assistant 第一次纠正（L737：统一用 `luna-worker`+brief 内声明角色）本身仍误判了 dispatcher 的"Implementer executor"规则，被用户在 L777 第二次（情绪化）纠偏后才在 L782/L786 落到正确规则（前端→`frontend-worker`、后端→`backend-worker`、其余→`luna-worker`）。 | 从 L475 到 L786 correct spawn 落地，时钟跨度 **15 分 1 秒**；期间用户发言 2 次（L732、L777），assistant 处理这两次纠偏各占 1 个 turn。 | 派发前一次性读完 `$dispatcher` 正文里的"Implementer executor"段（当时已在 L112/L544 被完整加载过两次），把"逻辑角色"与"载体 profile"的映射表当成派发前置检查项，而不是等用户发现错误后才现场纠正。 |
| L2432–L2744 | 等待串行 | TKT-02 fix→closure 出现两轮：第一次 closure（L2555 起）等待超时两次（L2460/L2467 与 L2569/L2583）才 `interrupt_agent`+`followup_task`，随后 closure 又在 L2637 发现 2 处残留（legacy 字段、格式问题），需要第二个极小 fix（L2659 起）与第二次 closure（L2723 起）才最终收口（L2744）。 | 从 L2432（发起 fix）到 L2744（第二次 closure 完成），时钟跨度 **22 分 43 秒**；含 2 次 `interrupt_agent`（L2467、L2583）与至少 4 次 `wait_agent` 超时（各 60s）。 | `wait_agent` 超时后不必再等第二个 60s 才判断——第一次超时即可用 `list_agents` 核实 worker 真实状态，若仍在正常工作就用短超时轮询，若确认卡住立即中断重派，省掉重复的整段超时等待。 |
| L2769–L2872 | 工具环境失败 | 合流级 focused 验证时发现主验收 worktree 未安装 `node_modules`（L2788："合流校验本身无代码失败；主验收 worktree 只是尚未安装 node_modules"），需要临时复用本机 pnpm store 补齐依赖后才能重跑验证。 | 从 L2769（宣布要做合流验证）到 L2908（真正开始业务 lane fan-out），时钟跨度约 **17 分钟**，其中环境修复本身占用数分钟。 | foundation 合入 checkpoint 之后、真正跑验证之前，先对目标 worktree 做一次 `node_modules`/依赖存在性检查（复用已有 pnpm store 的 hardlink 安装通常几秒钟），别等到验证命令报错才发现依赖缺失。 |
| L2808、L2837 | 范围理解偏差 | root 自己直接执行 `pnpm --filter @kaispan/contracts exec vitest run ...` 与 `pnpm --filter @kaispan/db exec vitest run ...`（合流级 focused 验证），把测试原始输出直接读进主控自己的 context；随后在 L2884 被用户纠偏"长测试脚本也可以用 `@luna-worker` 包起来跑…不要污染你的context"。 | 直接代价难以用 turn 数衡量（这次验证本身是必要的），但造成了主控 context 里多了两段测试原始输出，且需要用户明确指出规则才纠正——纠正后到 L7872 未再复发（已用全区间脚本核实）。 | 任何预期输出可能较长的验证命令，默认先经 `luna-worker` 包一层，只回收摘要/失败点/最终结论；这条规则本应在第一次合流验证前就适用，不必等用户提醒。 |
| L3921–L3972 + L3933–L3969 | 范围理解偏差 | 用户在 L3933 明确标注"非阻塞提问：F1-F4 只能线性解决吗？"；assistant 在 L3938 回答后**把这次回答当成了回合终点**（新 `turn_context` 在 L3944 出现，中途无任何动作），空等到 L3945 用户第二次纠偏"我说了除了方案决策以外，禁止返回，也说了这是非阻塞提问"才在 L3950/L3969 恢复推进。同一时间窗口内还叠加了本 slice最长的一段纯等待（L3921→L3972，415 秒）。 | 从 L3933 到 L3969 真正恢复并行推进，时钟跨度 **3 分 34 秒**的回合空转，叠加同窗口 415 秒的纯等待段；用户为此发言 2 次（L3933、L3945/L3964）。 | 收到"非阻塞提问"标注时，把回答当作本回合内的一段旁白而不是回合收尾——回答完立刻继续原有的派发/等待循环，不产生新的回合边界；"非阻塞"字面已经说明用户不期待因此停顿。 |

---
## 5. 用户纠偏事件

| 行号 | 用户原话摘要 | agent 当时在做什么 | 暴露了什么 |
| --- | --- | --- | --- |
| L352 | "问原sessoin" | 主控刚接手 delegation，处于开局 anchor 核对 | 用户要求向原 session 求证事实，而不是自己假设或走正式 thread-harness 流程——这是后续 L390 的前置铺垫。 |
| L390 | "直接问，不要thread-harness" | 同上 | 明确指出跨 session 求证应该走轻量直接问答，不必套用 thread-harness 那套正式协议——规则本身在这句之前没有被写清楚，是用户临场给的偏好。 |
| L453 | 大段"调度行为补充/授权补充"：impl（两个 role）/fix 是角色不是载体、可按需并行创建多个；载体可以有自己的 wt；ticket ready 只是 ticket 粒度不是 dependency；poc 授权全开，禁止因授权/formality 停；只有方案不明且 Decision/Spec 无法回答时才能停 | 刚从"问 issue 无关"的追问中转回业务话题 | 这是本 slice **最强的一次性规则注入**，后续 L732/L777/L2227/L3933 等多次纠偏本质上都是在检验这段话有没有被真正内化，而不是新规则。 |
| L535 | "调研之后，需要保证共同的前置条件先派发，切不可补丁式的为了并行而并行" + `$dispatcher` 引用 | 刚完成 5 个 explorer 只读调研的 fan-out，尚未决定下一步派发顺序 | 补充了 L453 里"可提前调研"与"先分析 foundation/seam"之间的优先级关系——调研可以先做，但派发实现仍要先共同前置条件。规则加载：本次带的 `$dispatcher` 链接会把 SKILL.md 正文注入（见第 6 节）。 |
| L594 | 验收设计中度收缩：39 个 stable claim 不变，但共享矩阵只跑一次、入口只做 smoke，同一证据支持多个 claim | assistant 正在等待 explorer 调研 agent 返回（`wait_agent` 途中被打断，`{"message":"Wait interrupted by new input.","timed_out":false}`） | 暴露的不是执行阶段的规则缺失，而是**设计阶段遗留的验收膨胀**（39 claim 写成像需要 39 组独立测试）在真正执行前被用户自己发现并现场收缩——执行阶段没有机制在早期自动发现这种膨胀，是靠用户手动介入。 |
| L732 | "subagent默认是@luna-worker，我看到你派送的是默认和自身一样的，这是不对的，我在全局AGENTS.md里都定义好了" | 刚完成 5 个 `explorer` 调研 agent 的 fan-out 与陆续的 return 消费 | 暴露"角色≠载体"规则（L453 已经说过一次）在具体派发时没有被正确应用——`explorer` 被当成了载体 profile，而不是把"调查"当逻辑角色塞进默认载体的 brief 里。这是该规则的**第一次现场违反**。 |
| L777 | "[@frontend-worker] [@backend-worker] 这个不是默认的啊，我已经 $dispatcher 两次了，你他妈到底有没有看啊？" | 刚在 L737 回应 L732 纠偏，声明"统一用 luna-worker 作为默认载体，在 brief 里声明 frontend/backend impl 逻辑角色" | 暴露的是**同一条"角色≠载体"规则的第二次违反**，且是在纠正第一次错误的过程中矫枉过正矫出的新错误——把 frontend-worker/backend-worker 这两个专用 executor profile 也错误地折叠进了"默认载体+文字角色"模型。`$dispatcher` 正文（含 Implementer executor 段）在此之前已被完整加载两次（L112、L544，见第 6 节），说明不是没读到，是读到了没有正确应用。 |
| L1253 | "非阻断小提示：不是什么回来都要do-review全部的，这几轮共享的foundation是重点我同意，不过也别忘记delta review" | 刚完成 TKT-01/schema/TKT-04/TKT-02 四条 foundation 的完整四轨 do-review | 暴露的是"共享 foundation 值得重审、但业务 lane 不必每次都跑全套"这条边界当时还没有被主控确认，用户主动画出这条线，随后被严格遵守（第 2 节第 5 条）。 |
| L2227 | roadmap 建议：先结束两条 closure、合入 foundation 再并行业务 lane；普通 lane 只做一次独立 delta review | 刚完成 TKT-01 rules core review 与 schema review 的第一轮 | 不是严格意义的"纠偏"（用户自己标注"非阻断，仅供参考"），而是把 L453/L535/L1253 三条规则揉合成一个具体执行顺序——本质上是用户在替主控做"先分析前置再fan-out"的排序工作，说明主控自己当时还没把这个顺序想清楚。 |
| L2884 | "长测试脚本也可以用@luna-worker包起来跑，你只需要知道大致进度和最终结果即可，不要污染你的context" | 刚在 L2808/L2837 亲自执行了两次 `pnpm ... vitest run`，把测试原始输出读进了自己的 context | 暴露"主控 context 卫生"这条规则在 L453 授权补充里完全没有被提及过——是本 slice **第一次**引入这条规则，随后被严格遵守到底（第 2 节第 11 条），说明这不是"读了没做"，而是"规则原本没有"。 |
| L3393 | 真实 UI 验收补充设计：两条证据线，但 EV-4 明确跑 3 个真实 UI 场景；"做轻量更新，不要打扰已派发的worker" | 业务 lane（Unit Profile/receiver follow-up 等）已在并行推进 | 明确要求"更新验收设计"和"不打扰在途 worker"两件事同时做到，是对 L594 那次验收收缩的进一步细化，同样属于设计阶段遗留、执行阶段承接的调整。 |
| L3933 | "非阻塞提问：F1-F4 只能线性解决吗？" | 处于 F1-F4 四个 finding 的修复排期讨论中 | 用户用"非阻塞"预先标注了这不该产生回合边界——assistant 仍然把回答当作了终点，见 L3945。 |
| L3945 | "我说了除了方案决策以外，禁止返回，也说了这是非阻塞提问" | 刚回答完 L3933 的问题并让 turn 结束 | 暴露 L453 "只有方案不明且 Decision/Spec 无法回答时才能停下来问"这条规则的**又一次违反**——这次不是没执行派发，而是把一次非方案性质的问答误判成了需要交还控制权的时刻。 |
| L3964 | "之后的impl和fix也是，注意并行" | 刚在 L3969 承诺"继续不再停"之后 | 再次强调 L453/L535 已经说过的并行原则，是对刚才那次"回合终止"事故的收尾提醒，而不是新规则。 |

**重复主题统计**：
- "角色≠载体"（impl/fix/frontend/backend 是逻辑角色，不是可以直接当 `agent_type` 用的载体名）在本 slice 里被用户明确讲了 **3 次**（L453 首次陈述、L732 第一次违反后重申、L777 第二次违反后重申，且第二次带有明显情绪："你他妈到底有没有看啊"）。规则本身在 `$dispatcher` 正文里始终存在且在两次违反之前都已完整加载过（L112、L544），说明问题不在"规则没写"或"版本不对"，而在**执行时的规则应用/自我核对环节缺失**——赋值 `agent_type` 之前没有一个"角色→载体映射表"式的检查步骤。
- "不该停的时候停了"（本应只在方案决策上返回）在本 slice 里出现 **2 次**同类违反（L732 之前的默认 profile 误用某种意义上也是"没有先确认规则就动手"，但严格意义上的"擅自结束回合"只有 L3933→L3945 这一起）。
- "主控 context 卫生"（L2884）与"验收设计膨胀"（L594/L3393）是本 slice **首次引入**的规则/调整，不属于"读了没做"，是"当时确实没有"或"设计阶段遗留问题在执行阶段被现场修补"。

---
## 6. 规则加载核对

**dispatcher 正文的加载位置与内容**：本 slice 里 `dispatcher` SKILL.md 被完整读取 **2 次**：
- L107→L112（输出）：从 `C:\Users\Xiao\.codex\skills\dispatcher\SKILL.md`（全局 codex skills 目录）读取，时间 2026-09-13T18:24:10Z。
- L541→L544（输出）：从 `D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md`（仓库工作区，即 L535 用户消息里 `[$dispatcher](...)` 链接指向的路径）读取，时间 2026-09-13T18:36:11Z。

两次读取的输出**都完整包含"## Implementer executor"一节**（原文："`implementer` 保留为逻辑角色，前后端工作使用具象 executor：frontend implementation → `frontend-worker`；backend implementation → `backend-worker`"）。已直接 `diff` 这两个文件本身：`C:\Users\Xiao\.codex\skills\dispatcher\SKILL.md` 与 `D:\CodeSpace\agent-workbench\skills\dispatcher\SKILL.md` **完全一致**（同字节数 6698、同 mtime，diff 无输出）。

这意味着 L732/L777 的两次"角色≠载体"违反（见第 2 节第 2 条、第 5 节）**不能归因于"规则没读到"或"读到的是旧版本"**——规则在两次违反发生之前都已经被完整加载过，且两处来源版本一致。问题出在加载之后的**应用环节**：赋值 `spawn_agent` 的 `agent_type` 参数时没有对照"Implementer executor"这张映射表做检查。

**impl-package 各 skill 的加载来源**：本 slice 里所有 impl-package 体系的 skill 读取全部来自 `C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.2\`（`impl-package`/L44、`execution-boundaries`/`dev-with-track`/L95 批量、`impl-planning`/L600、`do-review`/L1009、`backfill-stable-docs`/后续多次），没有出现从别处（例如仓库 `plugin-marketplace` 目录）直接加载 impl-package skill 的情况——与背景资料"impl-package 安装在 plugin cache 0.4.2"一致。

**cache 0.4.2 与仓库当前版本的一致性抽查**：
- `dev-with-track/SKILL.md`（含"主控直接实现时遵守相同 write ownership、自证和独立 delta review 要求"一句）：`diff` cache 版本与 `D:\CodeSpace\agent-workbench\plugin-marketplace\plugins\impl-package\skills\dev-with-track\SKILL.md` **完全一致**（无输出）。
- `do-review/SKILL.md`（含"main session 不是另一名 reviewer…普通代码 return 的 delta review 由 Dispatcher 安排"一句）：`diff` 同样**完全一致**。
- `evidence add` 批量能力：cache 版本的 `references/impl-package-current-state.md`（第 81 行）与 `skills/dev-with-track/situations.yaml`（第 223 行）都明确写着"`evidence add` 从 stdin 接受一个 evidence object 或一个非空 evidence object array"——文档层面批量能力是存在且是当前版本的，但本 slice 全程没有实际调用这个子命令（见第 1 节），无法从"是否被正确执行"的角度验证这条规则，只能确认"规则文本本身在缓存版本里是完整且最新的"。

**结论**：本 slice 抽查到的所有规则来源（dispatcher 正文两处、impl-package cache 0.4.2 三个 skill）与仓库当前版本**均无版本漂移**。第 2/5 节记录的执行违反（角色/载体混淆、非阻塞提问被当终点、主控自跑长测试）都不是"加载了错误/过期版本的规则"造成的，而是规则被正确加载后仍未在执行动作里被正确应用——这把问题精确定位在"执行时的自我核对步骤缺失"，而不是"skill 内容或版本管理"层面。

**主控 spawn 时用的 agent_type 与已加载规则的一致性**：L786 之后（即两次纠偏落地之后）逐一核对 spawn_agent 记录（第 1 节表格），未发现任何一次前端实现用了非 `frontend-worker`、后端实现用了非 `backend-worker`，或者非实现类任务用了非 `luna-worker` 默认载体的情况；`review-track-*` 系列只在 do-review 正式多轨复核里出现，与其角色匹配。一致性在纠偏落地后保持到 L7872。

---
## 7. 新发现的可优化点

按预计节省时间/turn 排序（次数是线索，不是结论）：

1. **`tools.exec_command` 的 JS 包装脚本语法错误反复出现，每次都要浪费一个完整 turn 重试**。在本 slice 里统计到 **17 次 `Script failed`**（L317、L619、L3114、L3452、L4401、L4487、L4706、L4712、L5277、L5283、L6088、L6109、L6115、L6168、L6174、L6180、L7231），其中至少 **10 次是纯 JS `SyntaxError`**（L4487"Unexpected identifier 'estrelas'"、L4712"Unexpected token ';'"、L5277/L5283"Missing initializer in const declaration"、L6088"Unexpected token '??'"、L6109/L6115"Unexpected token '='"、L6168"Invalid or unexpected token"、L6174"Unexpected identifier 'patch'"、L7231"Unexpected identifier 'need'"）——都是模型自己在拼多命令批处理脚本（`Promise.all([...])`、`const cmds=[...]` 这类数组/多语句包装）时手滑写错了 JS 语法。每次都要等一次 exec 失败反馈才能发现并在下一个 turn 改写，代价约"1 个 turn + 一次 exec round trip"。**改什么能省下什么**：涉及多命令批处理时，优先用简单的分号顺序拼接或单条命令，避免在 `tools.exec_command` 的包装层再嵌一层需要自己转义的 JS 数组/模板字符串；如果确实要批处理，先在纯文本里写好再一次性套進最外层 JS 字符串，减少手写转义出错的机会。预计可省下约 **10 个 turn**。

2. **常规"进度哨兵"检查（`git status`/`git diff --stat`/`git log -N --oneline`）大量作为独立 exec 调用出现，没有并入已经在跑的 `situation.py render`/`impl_package_state.py` 调用**。第 1 节已统计到这类组合命令（不同 `-N` 参数）合计 **40+ 次**，每次都是一次独立的"发起 exec → 等结果 → 读结果"完整 turn 循环，虽然每次执行本身只要 1 秒左右，但每次都会消耗一个模型 turn 的调度开销。**改什么能省下什么**：这些哨兵检查绝大多数紧跟在 `situation.py render --json` 或 `impl_package_state.py ... package validate` 之后（两者本身也是常规节拍检查），可以把 `git status --short; git log -N --oneline` 拼进同一条 PowerShell 复合命令里一次性跑完，省掉重复的独立 exec 调度。保守估计可以合并掉 **20～30 次**独立 turn。

3. **`wait_agent` 的超时设置普遍偏大（60000/120000/180000ms），且经常被打满整个超时时长才触发下一步动作**，累计造成本 slice 里 **122 分钟（占总时长约 21%）**的"纯等待"区间（第 1 节），其中最长单段 415 秒（L3921–L3972）、次长 314 秒（L556–L576）。**改什么能省下什么**：把默认 `timeout_ms` 收窄到 20000～30000，配合更频繁但更轻的 `list_agents` 探测（`list_agents` 本身几乎零延迟），可以把"发现 worker 已经卡住/已经返回但还在傻等"到"真正采取动作（interrupt/消费 return）"之间的延迟砍掉一大截——尤其是第 4 节里那种"等两轮 60s 超时才 interrupt"的模式（L2460–L2467、L2569–L2583），如果第一轮超时就查 `list_agents` 再决定，能省下至少 60～120 秒/次，多次叠加是本 slice 里最大的一块可优化时钟时间。

4. **`spawn_agent`/`send_message`/`followup_task`/`interrupt_agent` 的 `message` 字段全部加密（`gAAAAAB...` 形式），导致连事后复盘都无法确认 brief 内容或中断理由**——这直接体现在第 2 节第 8 条：12 次 `interrupt_agent` 里有 10 次因为推理内容（`encrypted_content`）和消息内容都不可读，只能凭"wait 超时→interrupt→立即 followup"这种行为模式去猜，无法坐实是否符合四类正当理由。**改什么能省下什么**：如果在 `record-event`/`trail.jsonl` 里对每次 `interrupt_agent`/关键 `followup_task` 额外落一条**明文摘要**（哪怕只是"中断原因：xxx；下一步：yyy"这一句话，不需要完整 brief），后续复盘或跨 worker 审计就不必再靠间接行为模式推测，可以直接读 trail 拿到确定结论——这条不影响本 slice 的执行效率，但会显著降低下一次类似复盘（比如本次 8-worker 分析）的调查成本。

---
