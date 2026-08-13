# 实测数据汇总

本页只放数字与口径。结论在 [../README.md](../README.md)。

## 0. 数据源

| 来源 | 说明 |
| --- | --- |
| DATEV 包 | `kaispan-dev` → `docs/domains/finance-assistant/implementations/2026-08-11-datev-mandant-profile-import`，执行中（`tickets=true, dag=true`） |
| AccountingScope 包 | `kaispan-dev` → `docs/implementations/2026-08-10-accounting-scope-policy-ownership`，已完成（`tickets=true, dag=false`，`tasks: {}`，gate `pass`） |
| 5 个 Codex rollout | `~/.codex/sessions/2026/08/{11,12,13}/`，2026-08-11 13:51 ~ 08-13 09:42，约 44 小时跨度 |

复现脚本在 [../scripts/](../scripts/)。token 估算统一按 CJK 字符 ×0.9 + 其余字符 ÷3.6，误差约 ±20%。

## 1. 终点状态

DATEV：**Task 7/9 `DONE`，Ticket 0/5 `SATISFIED`，Gate open**。全程没有出现一次「文件解析 → staging 入库 → 读回」的端到端证据。

AccountingScope：两个 attempt 均 gate `pass`，8 张 Ticket。

## 2. 任务包纸面规模

| artifact | DATEV | AccountingScope |
| --- | ---: | ---: |
| spec.md | 18,600 | 14,611 |
| contract-design.md | 14,800 | — |
| decision.md | 5,200 | 7,036 |
| plan（含 patch） | 7,700 | 8,738 |
| tickets/ | 6,000（5 张） | 7,128（8 张） |
| **execution-record** | 4,300（1 attempt，执行中） | **16,575（2 attempt，已完成）** |
| task-handoffs/ | **16,300（7 个）** | 0 |
| dag.md | 2,400 | 0 |
| progress + gate | 860 | 631 |
| **合计** | **~76,000** | **~54,700** |

两个观察：

- DATEV 的 Task Handoff 总量是全部 Ticket 之和的 **2.7 倍**。合同规定 handoff 是条件式产物，实测 7 个完成 Task 全部创建，且每个 Task 的 `DONE` evidence 指针就是它自己的 handoff。
- **完成包里 ER 是最大的单项产物**（16,575），超过 spec.md（14,611）。ER 只增不减，是长期主要增长项。

## 3. 工具调用分类

两套独立分类法，分母口径不同：

| 口径 | 分母 | 状态机 CLI | 方法论·合同文档读取 | 明确实现动作 | 读文档 : 实现 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `exec` only（[classify_calls.py](../scripts/classify_calls.py)） | 1,308 | 121 (9.3%) | 455 (34.8%) | 143 (10.9%) | **3.2 : 1** |
| 全部函数调用（Codex 口径） | 2,178 | 98 (4.5%) | 223 (10.2%) | 64 (2.9%) | **3.5 : 1** |

分类边界不同（前者正则更宽，可能高估文档读取），但比值收敛在 **3.2–3.5 : 1**。

方法论·合同文档读取产生约 1.8 MB 输出。按 target 统计（一次调用可命中多个，纵向不可求和）：

| target | hit | 输出字节 |
| --- | ---: | ---: |
| `SKILL.md` | 110 | 945,985 |
| `plan.md` | 66 | 685,268 |
| `progress.md` | 48 | 179,161 |
| `handoff` / `task-handoffs` | 47 | 392,552 |
| `dag.md` | 42 | 381,145 |
| `tickets/*.md` | 30 | 256,945 |

orchestration 调用 870/2,178（40%）：`wait_agent` 496、`send_message` 106、`list_agents` 92、`spawn_agent` 61、`wait` 57、`followup_task` 52、`interrupt_agent` 6。

## 4. 恢复税与会话概况

[session_summary.py](../scripts/session_summary.py)、[recovery_tax.py](../scripts/recovery_tax.py)：

| Session | thread | 到首次真实 dispatch 的调用数 | patch 应用 | context 压缩 | 累计 token |
| --- | --- | ---: | ---: | ---: | ---: |
| S1 | user | 1（规划 session） | 95 | 6 | 90.9 M |
| S2 | subagent | 16 | 13 | 2 | 60.1 M |
| S3 | subagent | 25 | 5 | 1 | 36.1 M |
| S4 | subagent | 31 | 68 | 4 | 70.0 M |
| S5 | subagent | 25 | 10 | 1 | 39.8 M |
| 合计 | | | 191 | **13** | **~297 M** |

累计 token 是逐轮重发上下文的账单累加，不是内容体积。

## 5. 上下文占用

[context_profile.py](../scripts/context_profile.py)，读 `token_count` 事件的 `last_token_usage.input_tokens`（该次请求实际发出的上下文）：

| Session | 请求数 | 峰值占用 | 窗口 | >100k | >150k | >200k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S1 | 703 | 233,358 | 258,400 | 68.8% | 36.4% | 10.2% |
| S2 | 464 | 223,883 | 258,400 | 72.8% | 36.0% | 9.5% |
| S3 | 253 | 214,592 | 258,400 | 81.8% | 48.2% | 19.4% |
| S4 | 516 | 233,819 | 258,400 | 71.5% | 46.1% | 12.8% |
| S5 | 308 | 225,833 | 258,400 | 68.2% | 36.4% | 9.7% |

**36–48% 的模型请求发生在 150k 以上。**自动压缩实测在约 226k（87%）触发。

占用轨迹呈锯齿（S3 采样：24→92→133→150→161→195→203→213→**61**→103→120→160），谷底为压缩重置。

产出量与占用峰值不相关：S3 出 5 个 patch 达 213k，S4 出 68 个 patch 达 234k。**主导项是合同阅读与代码探索，不是产出量**——这是规划时估算不可靠的直接证据。

## 6. 上下文增量与交接 headroom

[headroom.py](../scripts/headroom.py)，2,183 个正增长样本：

| 分位 | 每请求增量 |
| --- | ---: |
| p50 | 583 |
| p75 | 1,720 |
| p90 | 4,379 |
| p95 | 7,441 |

两次压缩之间的段：中位 101–155 次请求，涨幅 160k–198k。

按 p75 估算，警告发出后还需 R 次请求收尾时的落地占用：

| 警告线 | R=10 | R=20 | R=30 |
| --- | ---: | ---: | ---: |
| 45% (116k) | 133k | 151k ⚠ | 168k ⚠ |
| 50% (129k) | 146k | 164k ⚠ | 181k ⚠ |
| 60% (155k) | 172k ⚠ | 189k ⚠ | 207k ⚠ |
| 70% (181k) | 198k ⚠ | 215k ⚠ | 232k ⚠⚠ |

⚠ = 已过 150k 智能区；⚠⚠ = 已触发自动压缩。

## 7. Execution Record 结构

### subject 分布

| 包 / attempt | Composition | checkpoint | judgment | `attempt` | `ticket:*` | `task:*` |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| DATEV / initial | tickets+dag | 13 | 12 | 13 | **0** | 12 |
| ASP / initial | tickets only | 8 | 13 | 8 | **13** | — |
| ASP / patch（findings closure） | tickets only | 9 | 6 | **15** | 0 | — |

judgment 总量在有无 Task 两种结构下几乎相同（12 vs 13），只是挂靠 subject 改变。findings closure 类横跨 Ticket 的工作自然落在 `attempt`。

### checkpoint / judgment 的 token 拆分

[er_split.py](../scripts/er_split.py)：

| 包 / attempt | ckpt tokens | judg tokens | ckpt 占比 |
| --- | ---: | ---: | ---: |
| ASP / initial | 874 | 8,925 | 9% |
| ASP / patch | 3,401 | 3,191 | 52% |
| DATEV / initial | 1,933 | 2,856 | 40% |
| **合计** | **6,208** | **14,972** | **29%** |

checkpoint 占 ER 体积 29%（波动 9%–52%），judgment 占 71%。

## 8. Typed dependency 实况（AccountingScope，已完成）

| Ticket | Typed dependencies |
| --- | --- |
| ASP-01 | None |
| ASP-02 | `implementation: ASP-01` |
| ASP-03 | `implementation: ASP-01` · `acceptance: ASP-02` |
| ASP-04 | `implementation: ASP-03` · `acceptance: ASP-02` |
| ASP-05 | `implementation: ASP-01` · `implementation: ASP-03` · `acceptance: ASP-02` · `acceptance: ASP-04` |
| ASP-06 | None |
| ASP-07 | None |
| ASP-08 | None |

**ASP-02 被引用三次，全部为 `acceptance` 型，无一次 `implementation` 型。**8 张票中 4 张无任何依赖。

## 9. Ticket × Task 贡献关系（DATEV）

由 `dag.md` 的 contributes-to 列还原。链深：T1/T2/T3 = 1，T4/T5 = 2，T6 = 3，T7 = 4，T8 = 5，T9 = 6。

| Ticket | 贡献 Task | 最深 Task 链深 |
| --- | --- | ---: |
| DMI-01 确定性 source admission | T1, T2, T3, **T7** | 4 |
| DMI-02 版本化 gap form 与批准 | T1, T3, T4, T5 | 2 |
| DMI-03 verified canonical publication | T3, T5, T6 | 3 |
| DMI-04 安全 onboarding API/Web | T4, T6, T7, **T8** | 5 |
| DMI-05 完整旅程与回归 | T1–T9 | 6 |

Ticket 阻塞边（DATEV）：DMI-01 = None；DMI-02/03/04 之间为 `implementation` 型；DMI-05 四条边全为 `acceptance` 型。

## 10. 状态机与投影的写放大

`command_set_state` 无转换表，仅五道守卫：目标在词汇表内、`--expect` 匹配当前（CAS）、非 `PENDING` 必须带 evidence、Task→`READY/RUNNING` 要求前驱在 `{DONE, WAIVED, SUPERSEDED}`、Ticket→`SATISFIED` 要求 `implementation`/`acceptance` 前驱在 `{SATISFIED, WAIVED, SUPERSEDED}`。

`_refresh_projections` 每次重写**全部** ticket 文档 + `dag.md` + `progress.md`。DATEV 为 5 张票，即**一次 `set-state` 写 7 个文件**。`_validate_projections` 逐个比对，任一漂移抛 `projection mismatch`（S1 实测触发过，需 `refresh-progress` 后重新 `validate`）。

`state.json` 只保存当前 attempt 的 Ticket：AccountingScope 完成后其 state 中只有 ASP-06/07/08，`progress.md` 因此只显示 3 张票，看不到 ASP-01~05。
