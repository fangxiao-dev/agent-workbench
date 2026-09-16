# 执行 Skill 套件的第二次实战复盘（含设计阶段）

日期：2026-09-14
状态：调研报告。只给证据与判定；末尾的候选方向是给 Owner 挑选的清单，不是决定。

## 0. 这份文档是什么

[首次实战复盘](../execution-skills-first-run-review-260910/README.md)之后，09-10～09-13 落了四项改进（evidence 批量登记 `32bb5d7`、下游兼容性验收 `d874a20`、delta review 衔接 `ccfb7bf`、有界诊断 `7a9eb7e`），09-12 起工作区又加了 Implementer executor（`frontend-worker` / `backend-worker`）。09-12～09-14 有 5 个真实任务包在这套规则下跑完，其中两个从设计阶段（req-align → impl-planning → to-tickets → handoff）开始。本文用这 8 个 rollout 检验：上轮四项有没有生效、四个 open finding 有没有复发、设计阶段留下了什么给执行阶段。

材料是 8 个 Codex session 的完整 rollout（约 200 MB / 5.2 万行），切成 8 个切片，由 8 个 sonnet worker 用同一套判定清单（[workers/frame.md](workers/frame.md)）分头取证，本文合成。所有行号是原始 jsonl 的 1-based 行号，时间是 UTC。各 worker 的原始报告在 [workers/](workers/)。

| 切片 | 任务包 | session | 规模 | 时段（UTC） | 阶段 |
| --- | --- | --- | --- | --- | --- |
| W1a | KaiSpan finance-document-review-rules | `01a09c00` L1–7872 | 7.9k 行 | 09-13 18:21 → 09-14 04:07 | 主执行前半 |
| W1b | 同上 | `01a09c00` L7873–16546 | 8.7k 行 | 09-14 04:07 → 14:14 | terminal / 收口 / 交接文档 |
| W2 | prj-supplyer-webapp 260914-pre-lieferschein-order-revisions | `01a0a000` | 3.4k 行 | 09-14 12:59 → 15:37 | 主执行（短） |
| W3 | tinymlops Flow5 v1.2 evidence / KNN（call-grok 作 impl 载体） | `01a09f9f` | 5.7k 行 | 09-14 11:13 → 15:13 | 主执行 |
| W4 | tinymlops #309 artifact-to-runtime-compatibility | `01a09b18` | 8.1k 行 | 09-13 14:07 → 09-14 08:21 | 主执行 → MR/CI → backfill → learn-lessons |
| W5 | #304 Edge Client 设计（F1）+ JP-308 configurable Training 设计（F2） | `01a09693-c83f` / `01a09693-c844` | 0.3k + 2.0k 行 | 09-12 17:04 → 17:49 / 19:35 | 设计阶段 |
| W6 | #304 physical-rover-edge-client-foundation | `01a09721` | 7.0k 行 | 09-12 19:39 → 09-13 02:38（用户 08:53 回来） | 主执行（F1 的下游） |
| W7 | JP-308 configurable Original Training | `01a0971c` | 8.0k 行 | 09-12 19:33 → 09-13 08:50 | 主执行（F2 的下游） |

## 1. 上轮四项落地的实战检验

| 项 | 实战结果 | 判定 |
| --- | --- | --- |
| Evidence 批量登记 | 6 个执行 session 里真正走数组批量的 `evidence add` 共 **3 次**（W1b L15659/L15699、W4 L1998；W2 L2400 另有一次 findings 批量登记，走的是 `review_track_stats.py`），逐条登记约 **150 次**。W1b 同一 session 先批量后退化为 39 条 foreach 循环，用户 L16295「快速收尾不要再因为登记证据浪费时间了」；W6 39 次全部逐条，累计 373 秒；W7 唯一一次批量尝试用 PowerShell `$items=@(...)` 现场拼，两次失败（L6979/L6985）后退回逐条；W4 1 次批量、3 次循环。W1a/W3 全程没用 `evidence add`（走 `record-event` / `trail append`）。 | **能力在、没被用上。** 文档里的范例只在 `dev-with-track/situations.yaml:223` 一行，写的是 `printf '<json>' \| ... evidence add`——8 个 rollout 全文没有一次读到这一行（W7 grep 零命中），Windows 主控每次现场发明 PowerShell 写法。 |
| 下游兼容性验收 | W5 F2：ponytail 审阅指出 AC-10 的 #309 兼容性验收应由 #309 自己 own，主控采纳（F2:1271/1281）；W3 L5152 合同 patch 时只重验受影响的 TKT-01/02 runtime-integration 子集。没有反例。 | **有正向证据，无反例。** |
| Delta review 衔接 | 单 reviewer 的 delta review 在 W1a（L1253 用户提醒后）、W1b、W2、W6 都成立。但 **formal 四轨在同一增量上反复整轮重跑**：W1b terminal 3 轮（用户 L15553 摁停）、W4 TKT-02 4 轮（其中一轮因 L5596 改档位作废重跑，浪费 82.5 agent-分钟）、W7 TKT-02 4 轮 + TKT-03 2 轮 + TKT-01 delta 与 formal 叠加、W6 terminal 循环 3h24m 里 5 次全量重登记。 | **每次 return 一名 reviewer 做到了；「formal 只在关键节点」没做到。** 上轮把 terminal-final 启动条件归到 do-review，但没有约束同一 terminal 重跑几轮、每轮是否要整套四轨。 |
| OF-01..04 复发 | OF-03（无正当理由中断）：KaiSpan 16 次 `interrupt_agent`（W1a 12、W1b 4），10 次理由不可读但形态一致是「wait 超时 → interrupt → 立即 followup」，W1b L9650 纯超时中断、L8946 确认存活仍中断；其他 5 个 session 的 13 次中断全部是用户取消或 carrier 失败。OF-04（收尾挡主线）：W1b L15659→L16295 约 53 分钟 evidence/回刷/覆盖率轮询挤在 Gate 之前。OF-01：W6 L1440–L1537 长等待期间没有 render 投影，用户问「ticket 02 不能先开始做点什么嘛」才起只读调研；W7 全程 65.9% 时间只有 1 个 agent 在跑。 | **OF-03、OF-04 在 KaiSpan session 复发；OF-01 有同类风险模式。** 本文只记录复发证据，不做机制推断，诊断纪律不变。 |

## 2. 设计意图逐条判定（执行阶段）

`✓` 已执行 · `△` 部分执行或用户提醒后才执行 · `✗` 现场被违反 · `–` 无相关场景。每格的证据在对应 worker 报告第 2 节。

| # | 意图 | W1a | W1b | W2 | W3 | W4 | W6 | W7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 角色≠载体，同角色按需并行多个 | ✓（4 backend） | ✓（8 backend + 1 frontend） | ✓（3 backend） | ✓（grok ×3） | ✓（grok 20 PID） | △（L989 后才 5 backend） | △（L833 后才 4 backend） |
| 2 | 派发 profile 正确（默认 luna-worker，前后端具象 profile） | ✗→✓（L732/L777 两次纠偏，L786 后稳定） | ✓ | △（POLR-02 用旧名 `backend`/`frontend`，一次缺 `task_name` 失败） | ✓ | △（L468 后才补 profile） | ✓ | ✓ |
| 3 | ready≠dependency，先 foundation 后 fan-out | ✓ | ✓ | ✓（POLR-02 先只读调研，seam 稳定后 fan-out） | ✓（TKT-02/03 提前调研） | ✗→✓（L2010 已看出粒度问题仍等用户 L2016） | △（L1537 提醒） | △（L1502、L3747 提醒） |
| 4 | 不因授权/formality 返回 | ✗（L3933 非阻塞提问被当回合终点） | ✓ | ✓（L2410 只锁局部） | ✓（L1471 局部锁定，其余 lane 继续） | ✗（L1644 已授权仍确认；L652→L2375 等外部设备 3 小时） | ✓ | ✓（request_user_input 被环境拒绝后优雅降级） |
| 5 | 每 return 一名 reviewer delta；formal 只在关键节点 | △（L1253 前 foundation 全四轨） | △（terminal 3 轮） | ✓（formal 仅收口 1 次） | △（轨数 2/3/4 不一） | ✗（TKT-02 4 轮四轨） | ✓（return 级）/ △（terminal 循环） | ✗（4 轮 + delta/formal 叠加） |
| 6 | evidence 批量登记 | –（走 record-event） | ✗（先批量后退化） | △（findings 批量 1 次，无 evidence add） | – | △（1 批 3 循环） | ✗（0/39） | ✗（0/52，2 次失败） |
| 7 | 局部 barrier 只扣受影响候选 | ✓ | ✓ | ✓ | ✓ | ✓ | △（等待期不 render） | △（并行度低） |
| 8 | 无正当理由不中断 | ✗（12 次，10 次不可读） | △（4 次：2 正当 1 存疑 1 弱） | ✓（用户取消） | ✓（用户取消） | ✓（用户改档/越权） | –（0 次） | –（0 次） |
| 9 | 收尾不挡主线 | ✓ | ✗（53 分钟） | ✓ | ✓ | ✓ | ✓ | ✓ |
| 10 | worker 有自己的 worktree | ✓（15+） | ✓ | ✓ | ✓ | △（L2770 后） | – | – |
| 11 | 主控 context 卫生 | ✗→✓（L2808 自跑 vitest，L2884 后不再） | ✓ | ✓（0 次自跑测试） | ✗（escape 后自跑 pytest 4 次） | ✓ | ✓ | ✗（53 次 write_stdin 轮询 + 24 次 pytest 由主控自己跑） |
| 12 | 子代理不越权 | ✓ | ✓（L13177 主控拒绝 reviewer 的 PASS） | ✓ | ✓ | ✗（CI worker 越权，L6971） | ✓ | ✓ |
| 13 | 汇报说清 wt/branch/HEAD，无黑话 | △ | ✓ | ✓ | ✓ | ✓ | ✗（L7000 缺三项；L7034「业务比较点」） | ✓ |
| 14 | 跨 session 通信克制 | ✓ | – | ✗（L1340 纠偏后 L1450/L1602 又发两次） | – | ✓ | ✓ | ✓ |
| 15 | 档位降级指令被遵守 | – | – | – | ✓（10/10 luna-worker） | ✓（参数逐字对应） | – | – |
| 16 | 长寿命 subagent 退化 | 证据不足 | 未见 | 未见 | 未见 | 证据不足（grok_monitor 17 次 followup / 9 h） | 未见 | ✓ 一例（tkt01_backend/frontend 各 2 轮后四轨 4/4 FAIL，L1063） |

**读表的两个提醒**：第 1 行 7/7 最终做到了，但 6 个执行 session 里 5 个是用户先说了才做（见第 5 节）；第 8 行 KaiSpan 的 16 次中断里只有 2 次有明文理由，其余靠行为形态判断，不能坐实为违反。

## 3. 设计阶段：做了什么、留下了什么

### 3.1 两个设计 session 的形态（W5）

| | F1 · #304 Edge Client | F2 · JP-308 configurable Training |
| --- | --- | --- |
| 时长 / turn | 45 分钟 / 4 个真人 turn | 151 分钟 / 13 个真人 turn |
| 派发 | 0 次；25 次 shell 全是主控自己探查 | 5 次 luna-worker：原仓库取值调研、grill 问答对、ponytail 精简审阅、plan-review 两轮 |
| 推进方式 | 用户 F1:214 贴出「8 项已确认 + 3 项待确认」清单，agent 只解释确认，F1:283 被 turn_aborted | req-align 46 分钟，其中 63% 花在 grill + ponytail（真正定位业务问题），不是写材料 |
| 独立审阅 | 无 | ponytail 9 条采纳 8 条（F2:1281）；plan-review 第一轮 revise → AC 拆并 → 第二轮 clear（F2:1729） |
| handoff | 不适用 | 两段式：先 anchor 检查（F2:1982），PASS 后再发完整 continuation（F2:2011），7 分 40 秒，`readyTickets=["TKT-01"]` 完整传到 W7 |

设计阶段本身的绕路很小：最大一笔是 `package init` 两次被 CLI 拦住（F2:1824 要求固定标签「前置包（Predecessors）」、F2:1863 要求 stable claim ID 格式），共约 9 分钟，靠翻模板和源码才猜出格式。

### 3.2 设计阶段留给执行阶段的四个问题

1. **Ticket 依赖粒度默认写成 `implementation:`。** JP-308 的 TKT-02 写 `implementation: TKT-01`（F2:1440），W5 判定这是真实数据依赖（TKT-02 消费 TKT-01 落盘产物），但同一份 ticket 又写「child-local tests may be prepared early」，执行阶段 W7 用户仍要问 L1502「既然没有阻塞了，是否可以开始先做一些 ticket 02 的事情」。#309 的 TKT-02 也写 `implementation: TKT-01`，W4 L2016 用户裁定「阻断最终验收，不阻断开发」改成 `acceptance:`；主控 L2010 已经看出粒度过严，但没有自行放行。#304 的 plan.md 写「TKT-01 implementation dependency and one-shot caller order」，W6 L1537 用户提醒才起只读调研。三个包一个形态：to-tickets 没有区分「实现依赖」与「验收依赖」，执行阶段主控也不认为自己有权把非依赖子工作放行。
2. **验收 claim 膨胀。** KaiSpan 包 39 个 stable claim 被写成像 39 组独立测试，用户在执行阶段 L594 自己收缩（共享规则跑一次矩阵、各入口只做 smoke）；JP-308 的 22 个 claim 在 plan-review 第一轮被要求拆并。膨胀直接推高了 terminal 阶段的登记量（第 1 节）。
3. **Spec 里加不必要的限制/默认值。** F2:715「除了组合关系以外有必要做这个限制嘛…未来要改还得维护」、F2:752「我不认为应该预填参数」——同一偏好在同一 req-align 里被纠两次；F2:564「这些值是哪里来的参考？」→ 用户提示后才派 luna-worker 去原仓库核实（13 分钟）。
4. **handoff 保留在途 worker 上下文仍未被检验。** 本批可核实的两次交接（F1→W6、F2→W7）发生时都没有 worker 在途（F1 全程零派发，F2 的 5 个 agent 在 L1758 之前全部结束）；W1a、W2 的上游 session 不在本批材料内。这项设计连续两轮零实战证据。

W5 还核实了一件事：`[$impl-package:req-align](plugin cache 路径)` 这种引用在设计 session 里**没有**触发 `<skill>` 正文注入（F1、F2 零命中），agent 靠自己 `Get-Content` 读；只有指向仓库工作区路径的 `handoff-to-new-session` 被注入。见第 6 节。

## 4. 时间去哪了

按跨切片复现的次数和单笔代价排序。只列与 impl-package / Dispatcher 调度行为相关的；Docker、usage limit、训练跑批、CI 排障不计。

### 4.1 同一增量上 formal 四轨反复整轮（5/7 切片）

W1b terminal 3 轮（09:37 → 12:48，12 次 review-track spawn），W4 TKT-02 4 轮（其中 closure 轮 3 个 agent 跑了 27 分钟后因 L5596 改档位被作废，L5632 起重跑），W7 TKT-02 4 轮 + TKT-03 2 轮（L4166 → L6471 约 1.5 小时，16 次 review-track + 11 次 fix worker 只为关一个 ticket），W6 terminal 循环 23:11 → 02:35（101 个 assistant turn、383 次 exec），W3 七条 lane 全四轨。每轮之间确有真实修复（不是纯重跑），但形态都是「formal → 发现 finding → fix → 再起整套 formal」，而不是「fix 后一名 reviewer 做 delta，只在真正终态再跑一次 formal」。上轮否决了「恢复 Loop 十轮上限」，本轮最多 4 轮，没触及上限；问题不在上限，在每轮是否必须整套四轨。

### 4.2 evidence 登记：能力闲置 + terminal 全量重登记（5/7 切片）

第 1 节已给出数字。补两点：W6 每次 HEAD 前移（`d7999a6`→`867d778`→`d3b364e`→`0aa5e0d`→`b74de2d`）都把两张 Ticket 全部 28 个 claim 重新逐条登记一遍（L4473/4529/4817/5059/5128/5792/5876/6121/6436/6520），而不是只登记本轮 fix 影响的 claim；W7 在 compaction 后花 3 分钟重新 `--help` / grep 源码摸索 01:25 已经用过的 evidence 用法（L7510–L7578）。

### 4.3 等待与中断（7/7 切片，KaiSpan 最重）

纯等待占比：W1a 122 分钟（21%）、W1b 279 分钟（46%，多数时段 2–4 个 worker 在途，不全是空转）、W2 19 分钟（12%）、W3 67 分钟（28%）、W6 88 分钟（21%）、W7 刨除夜间空档后 2.63 小时占有效时段 40%、W4 253 次 wait 里 109 次满超时无新信息。形态一致：`timeout_ms` 用 120–240 秒且等满，等满后要么再等一轮（W1a L2460/L2467、W4 L6811/L6821 用户「似乎卡住了」），要么直接 interrupt + followup（W1a 10 次）。W1b L8946 是最能说明问题的一例：`send_message` 提醒过、`Get-Process` 两次确认 `Responding:True`，仍然在再等 180 秒后中断。

### 4.4 角色≠载体的信任成本（6/6 执行切片）

这条规则被用户在 6 个执行 session 里说了 12 次（W1a 3、W2 1、W3 2、W4 2、W6 2、W7 2），其中 W1a L777 带情绪「我已经 $dispatcher 两次了你到底有没有看啊」。单次纠偏响应都很快（分钟级），成本不在时钟，在用户每开一个 session 都要先把同一段「调度行为补充」贴一遍。根因拆开看是三件事，见第 6 节。

### 4.5 该自己动手时停下、不该停时返回（4/7 切片）

W4 L652 → L2375：主控把「Pi/S3 验收」记为缺外部设备/文件，反复复述这个假设，直到用户 L2375 指出仓库自带 Original Training + 本地 SeaweedFS 可以自己拉起，TKT-01 验收 lane 晚开约 2 小时 57 分。W4 L1644 合同 3/3 写完还问「确认通过吗」（用户 L1570 已批准）。W1a L3933 用户标注「非阻塞提问」，assistant 回答完直接结束回合，L3945 再纠。W7 L2044 为自研 training worker 建兼容层（F-002），用户 L2051「poc 而已没必要兼容」，删干净并重审花 37 分钟、13 次派发；L3696 fixture 三次分别打补丁后用户要求「修共享 fixture builder 一次」。

### 4.6 call-grok 载体失效（W3、W4）

W3：TKT-02 Server 一段实现交给 grok，46 次模型调用、790 万 token、48 分钟后被 `max_tokens` 截断（L2956），靠 recovery prompt 续接；随后两条 lane 各跑 10 分钟撞 HTTP 402 余额耗尽（L3892、L4144），用户 L4128 改回 `frontend-worker` / `backend-worker`。三次合计约 70 分钟「跑了才知道白跑」，grok_task.py 没有派发前的额度探测。W4 的 grok 用法（20 个 PID、grok-monitor 17 次 followup）没有出这类问题，但 profile → call-grok 的绑定关系只写在 continuation checkpoint 文本里（L38），不在任何 skill 正文，是 L468/L480 纠偏的直接原因。

### 4.7 汇报与交接（W6、W1b、W5）

W6 L7000 收尾汇报「Gate 已 PASS…任务 closed」没有 worktree/branch/HEAD，用户隔夜 L7011「wt/branch 报告一下」；补的汇报用「业务比较点为 b74de2d3」，用户批注「这啥意思」——同一 session 的 L154 preflight 汇报本来把三项写得很清楚，是收尾阶段松了。W1b L16402 用户要一份「环境重启 + 简单手测说明」，主控读 handoff SKILL、两份 reference、427 条 test registry、两个脚本全文，两次 apply_patch 转义失败，12.7 分钟，用户 L16538「写个交接文档你写 12min？？？？」。W5 F2:2039 最终汇报给了 commit 但没给 worktree 路径。

### 4.8 工具调用本身的失败（多切片，单次小、总量不小）

W1a 17 次 `Script failed`，至少 10 次是 exec 包装层的 JS 语法错误（`Promise.all` / 数组拼接手滑），每次一个 turn；W1b、W5 apply_patch 反引号/上下文匹配失败 2 + 3 次；W7 `followup_task` 连续 4 次参数错误（L3477–L3495）；W2 压缩后「失忆」CLI 参数与路径，5 次报错 2 分钟；W7 压缩后重新摸索 evidence 用法 3 分钟。上轮否决了通用 `PreToolUse` 校验 hook，这里不重提；记录的是具体入口（exec JS 包装、apply_patch 转义、followup_task 参数）各自反复出错。

## 5. 用户纠偏汇总

按主题合并 8 个切片的纠偏事件（用户主动给的「调度行为补充」开场白算一次）：

| 主题 | 次数 | 分布 | 暴露的是什么 |
| --- | --- | --- | --- |
| 角色≠载体 / 同角色可开多个 | 12 | W1a L453/L732/L777、W2 L145、W3 L312/L339、W4 L480/L2220、W6 L188/L989、W7 L246/L833 | 正文有（Implementer executor 段）但只说 frontend/backend「同一 profile 可并行派发多次」，对 investigate/fix/grok 这类通用角色没有明说；主控赋 `agent_type` 时没有对照检查 |
| 禁止因授权/formality 返回 | 8 | W1a L453/L3945/L3964、W2 L145、W3 L312、W4 L1651/L2375、W7 L7714 | 规则已加载（poc 授权条款、AGENTS.md「拒绝打补丁」），决策点没守住；「非阻塞提问」被当回合终点是新形态 |
| ready≠dependency，提前开工 | 6 | W1a L453、W4 L2016、W6 L1537、W7 L1502/L3747、W2 L145 | to-tickets 默认 `implementation:`；主控看出来也不自行放行 |
| 派发 profile 错 | 4 | W1a L732/L777、W4 L468/L480 | 同上第一行；另外 `backend.toml`/`frontend.toml` 旧文件仍在（W2 L3170/L3182 用了旧名） |
| review 粒度 | 3 | W1a L1253、W1b L15553、W6 L665 | formal 何时重跑没有边界；W6 为 do-review 设计不挂 ref 的临时 index（L606）被用户问「直接提交了 review 不行嘛」 |
| 收尾/登记挤主线 | 3 | W1b L15838/L16295/L16538 | 收尾类动作默认走重路径（先展开检索再收敛） |
| 不必要兼容 / 限制 / 补丁 | 5 | W7 L2051/L3696、W5 F2:715/F2:752/F2:823 | AGENTS.md 已写「拒绝打补丁」「简洁优先」，Spec/实现阶段仍倾向多加约束和兼容层 |
| 验收膨胀 | 2 | W1a L594/L3393 | impl-planning 阶段没有「同一份证据支持多个 claim」的收缩动作 |
| 主控 context 卫生 | 1 | W1a L2884 | 规则原本没有（本批首次引入），W1a 之后遵守；W3、W7 仍有违反但用户没说 |
| 子代理越权 / 降智 | 3 | W4 L6971/L6996、W7 L1063 | brief 没写死「只读检查、修复决策回主控」；复用轮次没有质量哨兵 |
| 汇报形态 | 4 | W6 L7011/L7041、W7 L7935、W2 L1340 | 收尾汇报没有硬字段；跨 session 汇报在承诺停止后仍发生（W2 L1450/L1602 紧跟 trail append 0.02–0.14 秒，疑似自动中继） |
| 档位调整 | 2 | W3 L4799、W4 L5596 | 都被精确遵守；但 W4 在 3 个 agent 跑了 27 分钟后才给，导致作废重跑 |
| worktree | 1 | W4 L2770 | 提醒后几分钟内生效 |
| 卡住 | 2 | W1b L15744、W4 L6826 | 一次是 compaction 对用户不可见，一次是两轮 240 秒满超时 |

## 6. 规则加载核对

八个 worker 各自 diff 了 plugin cache `0.4.2` 与仓库 `plugin-marketplace/plugins/impl-package/` 对应文件，以及 `~/.codex/skills/dispatcher`（是指向仓库的 junction）与 `skills/dispatcher/SKILL.md`：**全部逐字节一致，没有版本漂移。** 本批所有违反都不是「读了旧版本」。

但「有没有读到」这一步链条是断的：

- `[$dispatcher](path)` / `[$impl-package:xxx](cache path)` 这类引用**不会稳定注入 `<skill>` 正文**。W5（两个设计 session）、W6、W7 全文零 `<skill>` 命中；只有 `handoff-to-new-session`、`learn-lessons` 这两个仓库路径 skill 被注入过。主控靠自己 `Get-Content`：W1a L112/L544、W2 L143、W3 L135、W4 L46、W7 L59 都读了 dispatcher 正文；**W6 全程没读 SKILL.md 本体，只读了两份 references（L107）**，这直接解释 L188 → L989 同一条规则被纠两次。
- 读到了也不等于用上：W1a 两次读完 Implementer executor 段之后还是先派 `explorer`（L475）再把 frontend/backend 折叠进 luna-worker（L737）；W7 在 L59 读到正文 9 分钟后用户仍要重申 L246。
- 正文本身有两处缺口：（a）「同一 profile 可并行派发多次」只挂在 frontend/backend 下，没有一句通用的「任何角色（含 investigate/fix/verify/grok）按需多实例」；（b）profile → 载体的绑定（哪个 profile 走 call-grok）只在 checkpoint 动态文本里（W4 L38），不在 dispatcher 或 call-grok 正文。
- `evidence add` 批量的唯一范例 `situations.yaml:223` 用的是 `printf`，Windows 主控没有一个能直接抄的 PowerShell 形态。

## 7. 候选方向（给 Owner 挑）

按证据强度和单笔代价排，不含上轮已否决项（15/30 分钟门槛、候选清单、bookkeeper、自动换 session、Loop 十轮上限、通用 PreToolUse hook、全 lane 同 HEAD 门槛、E4、backfill 全局不阻塞条款）。

1. **formal 四轨的重跑边界**（4.1）：do-review / dev-with-track 区分「首次实现完成」「认为可收口」两个节点跑整套 formal，中间每次 fix 后由一名 reviewer 做 delta；有交叉影响再局部追加轨。另外把「各轨默认档位」写进 do-review（W4 L5596 是用户现场指定的）。
2. **evidence 登记的可抄模板 + terminal 增量重登记**（4.2）：给 dev-with-track 登记入口一个 PowerShell 可直接用的数组 stdin 模板（临时文件或 here-string，不要现场拼 hashtable）；terminal 每次 HEAD 前移只重登记受影响 claim——后者要先能判断「本轮 fix 影响了哪些 claim」，暂列线索。
3. **角色≠载体写成通用一句 + 绑定进正文 + 删旧 profile**（4.4、第 6 节）：dispatcher 正文加「任何角色按需多实例」；profile → 载体的绑定从 checkpoint 文本移进 dispatcher 或 call-grok；删除或标记 `agents/backend.toml` / `frontend.toml`。
4. **to-tickets 的依赖粒度二选一**（3.2）：Ticket 显式写 `implementation:` 还是 `acceptance:`，默认 acceptance，只有真实数据依赖才写 implementation；执行阶段主控可以自行放行非依赖子工作（只读调研、child-local 测试）而不等 Owner。
5. **收尾汇报硬字段 + 交接 lite**（4.7）：worktree / branch / HEAD 三项进收尾汇报；内部术语同句翻译；小范围 handoff 请求先用已有信息一次成文。
6. **call-grok 派发前额度探测 + 增量提交**（4.6）：grok_task.py 起跑前一次轻量余额检查；brief 要求每完成一个子步骤 commit 一次。
7. **引用即读取**（第 6 节）：收到 `[$skill](path)` 引用时，若该 SKILL.md 本体此前没读过就先读一次本体（不只是 references）。
8. **OF-03 / OF-01 复发证据已补**：KaiSpan 16 次中断、W1b L8946「存活确认后仍超时中断」、W6 等待期不 render。按上轮诊断纪律，是否做「动作前提示」仍要先有可重放的长上下文与工具选择；本批只增加了复发证据，没有新的机制证据。

## 附：调研方法与证据边界

- 8 个 sonnet worker 各读一个切片（W1 按 L7873「旧进程可杀」拆前后半），使用同一套 16 条执行意图 + 8 条设计意图清单和固定 7 节骨架；两两并行，分四批完成。W3、W4 中途撞 API 限额，从已落盘的骨架和前几节续跑，没有重来。
- `spawn_agent` / `send_message` / `followup_task` / `interrupt_agent` 的 `message` 字段是密文，`reasoning` 也是密文，brief 内容和中断理由都不可读；`agent_type`、`task_name`、`target`、`timeout_ms` 明文，子代理的 `FINAL_ANSWER` 明文。所以「派发合同写得好不好」仍不可取证，中断理由只能凭前后明文和行为形态判断。
- 时长按 rollout 时钟算，包含用户空档；W6、W7 已把夜间空档单独剔除。等待占比各 worker 口径略有差异（是否把 `list_agents` 算进去），只用于切片内排序，不做切片间精确比较。
- 用户在 W2 的 session 抓取时仍在增长（我列的 2306 行、W2 分析时 3400+ 行），W3 同理（4800 → 5704 行）；数字以 worker 报告为准。
- 「本 slice 无相关场景」不等于设计未落地，要看同一条在 7 个执行切片的分布（第 2 节的表就是为此排的）。
