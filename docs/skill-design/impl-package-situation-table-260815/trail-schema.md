# 决策轨迹字段集

位置：`execution/<attempt>/trail.jsonl`。随 attempt 分段，terminal Gate 后冻结，历史由 Git 保存。
本文件与 `plugin-marketplace/plugins/impl-package/references/situation-inputs.md` 的 3.1、4.3
共同定义 situation renderer 消费的 trail 形状。

## 轨迹轮换

交接时若活动文件已满，把 `trail.jsonl` 原样移为下一个归档序号并新建活动文件：

```text
execution/<attempt>/trail.jsonl
execution/<attempt>/trail.001.jsonl
execution/<attempt>/trail.002.jsonl
```

归档序号是三位十进制，从该 attempt 目录已有最大序号递增；归档文件内容不得改写。renderer
只读取未编号的当前 `trail.jsonl`，所以当前 situation 的 fact 和扫描型输入都在交接时重新
基线化；仍成立的 fact 必须在新文件重新声明。`dispatch_audit.py` 是例外：它发现并按序
读取所有 `trail.NNN.jsonl`，最后读取当前 `trail.jsonl`，用于完整历史审计和回放；归档缺失
时按只有一份活动 trail 处理。

## 公共字段

每个非空行都是一个 JSON object。规范公共字段如下：

| 字段 | 作用 | 要求 |
| --- | --- | --- |
| `v` | schema 版本 | 可选；旧 trail 缺失时保持兼容 |
| `seq` | attempt 内单调序 | 可选；fact 同 timestamp 时作覆盖顺序 |
| `ts` | ISO 8601 事件时间 | `kind=fact` 必填；普通旧事件可缺失 |
| `subject` | 事实作用域 | 推荐必填：`attempt`、`ticket:<id>`、`finding:<id>` |
| `kind` | 事件语义 | 规范值见下表；旧 kind 仍可承载兼容字段 |
| `head` | 事件时的 Git SHA | 用于 trail/Git rework 对账 |

`situation`、`chosen`、`alt`、`reason`、`worker`、`outcome`、`review_state`、`of`、`ref`、
`situation_digest`
是按事件出现的条件字段。`basis` 不进轨迹；它是 situation table 的属性，事后按 `situation`
join。

## 统一 event schema

| `kind` | 正式形状 | renderer 语义 |
| --- | --- | --- |
| `decision` | `subject`、`seq/id/decision_id/decisionId` 至少一个、`chosen` | 旧 decision 发起事件；由 result-like event 的 `of/decision/...` 关闭 |
| `dispatch` | `subject`、`outcome: "RUNNING"`、`returned: false/true`、`worker`；建议带 `seq` 或 `id`；可选 `situation_digest` | `returned:false` 本身就是 worker 未返回；有 id 时可由后续 return 关闭；`situation_digest` 是本次派发所依据的 renderer 12 位 digest，缺失只产生审计信号 |
| `result` | `subject`、`outcome`；可带 `of`；direct evidence 放在 row 或 payload alias | 旧结果事件；与 `worker-return` 归一 |
| `worker-return` | `subject`、`outcome`、可选 `of`、worker 返回 payload | 新 worker 返回事件；`EVIDENCE_SUFFICIENT` + `evidence` 建立 direct evidence |
| `fact` | `subject`、`key`、`value`、`ts`，可选 `seq` | 只声明不能从 package artifact 推导的事实；在当前活动 trail 内同 subject/key 取最新 |

`checkpoint`、`handoff`、`judgment`、`integration`、`review` 等历史 kind 仍可存在，尤其是
已有 fixture；它们不再通过 prose/negative marker 产生 typed fact。需要声明事实时写
`kind=fact`。

### 规范示例

```jsonl
{"v":1,"seq":10,"ts":"2026-08-15T12:00:00Z","subject":"attempt","kind":"fact","key":"attempt.integration_carrier_available","value":false}
{"v":1,"seq":11,"ts":"2026-08-15T12:01:00Z","subject":"ticket:TKT-01","kind":"worker-return","outcome":"EVIDENCE_SUFFICIENT","evidence":{"artifact":"evidence/returned.md#result","claim":"AC-1","revision":"5f299f3","environment":"fixture"}}
{"v":1,"seq":12,"ts":"2026-08-15T12:02:00Z","subject":"attempt","kind":"dispatch","outcome":"RUNNING","worker":"worker-01","returned":false,"situation_digest":"a1b2c3d4e5f6"}
```

### result-like 归一

以下消费统一把 `kind=result` 和 `kind=worker-return` 当作 result-like：

- `last_outcome` 和连续 `INCOMPLETE` 计数；
- decision/dispatch 的返回关联；
- direct evidence payload；
- worker 返回的 finding source、mode、envelope 字段。

旧的 `kind=result` 形状不会失效。新 worker 返回推荐使用 `worker-return`，不应为了旧
parser 把自然返回改写成 `result`。

## direct evidence tuple

result-like 行可以在自身或 `ref`、`evidence`、`artifact`、`evidence_ref`、`direct_evidence`
中放 payload。要让 `evidence.indexed` 继续判定，最终必须得到完整 tuple：

```json
{
  "artifact": "evidence/returned.md#result",
  "claim": "AC-1",
  "revision": "5f299f3",
  "environment": "fixture"
}
```

`subject` 必须是目标 Ticket，例如 `ticket:TKT-01`；写在 `attempt` scope 不会成为 Ticket
的 direct evidence。旧 `result` direct-evidence tuple 保持兼容。

## fact 通道

### 单条 fact 形状

```json
{"v":1,"seq":12,"ts":"2026-08-15T12:00:00Z","subject":"attempt","kind":"fact","key":"attempt.handoff_or_long_task","value":true}
```

新 fact 必须使用单个顶层 `key`、`value`、`ts`。同一活动 trail 中同一 subject、同一 key 的多个 fact 按以下
顺序取最新：

1. `ts` 较新者优先；
2. `ts` 相同则 `seq` 较大者优先；
3. 仍相同则 trail 文件中较后者优先。

这是当前文件内的可见顺序，不是过期规则：renderer 不会因为 fact 陈旧而自动否定它，返回 JSON 的
`when_values` 会暴露所选 fact 的 `ts`（以及有值时的 `seq`）。

### 封闭 key 集合与缺省语义

以下是唯一允许的 canonical fact key。显式 fact 优先；在 trail 可读取但该 key 没有声明时，
按下表取缺省值。`unknown` 表示不作值猜测，依赖该 key 的 situation 会进入 undetermined。
如果 trail 缺失或读取失败，仍按输入不可用处理，不把读取错误伪装成缺省值。

| fact key | 缺省语义 | 理由 |
| --- | --- | --- |
| `package.validate.projection_drift` | `unknown` | 没有 validation 结果或 fact 不能证明发生漂移，默认 false 会少提醒刷新。 |
| `attempt.session_resumed` | `unknown` | 没有恢复声明不能证明会话未恢复，默认 false 会少提醒检查 checkpoint。 |
| `attempt.in_flight` | `unknown` | 没有 in-flight 信号不能证明 worker 已返回，默认 false 还可能错误放行 ready Ticket。 |
| `attempt.handoff_or_long_task` | `unknown` | 没有声明不能区分短动作与长任务，默认 false 会少提醒写 checkpoint。 |
| `attempt.integration_carrier_available` | `unknown` | 没有可用性声明不等于 carrier 不可用，默认 false 会凭空触发 blocker。 |
| `attempt.integration_evidence_available` | `unknown` | 没有可用性声明不等于 integration evidence 不可用，默认 false 会凭空触发 blocker。 |
| `attempt.manual_verification_owner` | `unknown` | 没有 owner 声明不能证明不需要人工复核，默认 false 会少提醒人工验证。 |
| `attempt.manual_verification_result_present` | `unknown` | 没有结果声明不能证明结果不存在，默认 false 会把未登记结果误报为缺失。 |
| `attempt.completion_claim_pending` | `unknown` | 没有 pending 声明不能证明完成声明已审计，默认 false 会少提醒完成前检查。 |
| `attempt.terminal_coverage_complete` | `unknown` | 没有 coverage 声明不能证明覆盖不完整，默认 false 会把不适用的场景误报成 blocker。 |
| `ticket.blocker_maybe_resolved` | `unknown` | 没有变化声明不能判断 blocker 是否已解除，默认 false 会少提醒重新评估。 |
| `ticket.no_longer_needed` | `unknown` | 没有处置声明不能授权退休 Ticket，默认 false 会少提醒需要的处置判断。 |
| `ticket.release_edge_rechecked` | `false` | 未声明时默认就是“尚未复核”，保留 release-edge 提醒属于 fail-closed。 |
| `ticket.review_required` | `unknown` | 没有要求声明不能证明不需要 reviewer，默认 false 会少提醒派发复核。 |
| `ticket.review_trigger` | `unknown` | 没有触发声明不能证明没有 review trigger，默认 false 会少提醒必要复核。 |
| `ticket.post_fix_regression_pending` | `unknown` | 没有 pending 声明不能证明回归检查已完成，默认 false 会少提醒复验。 |
| `evidence.sources_uniquely_decide` | `unknown` | 没有唯一性裁决不能证明单一来源足以决定路径，默认 false 会少提醒路由判断。 |
| `git.comparison_head_fixed` | `unknown` | 没有 fixed 声明不能区分未固定与未记录，默认 false 会误触发重开复核。 |
| `trail.anchor_mismatch` | `unknown` | 没有 mismatch 声明不能证明锚点一致，默认 false 会少提醒锚点恢复。 |
| `trail.bookkeeper_partial_write` | `unknown` | 没有 partial-write 声明不能证明写入完整，默认 false 会少提醒轨迹完整性检查。 |
| `trail.checkpoint_projection_race` | `unknown` | 没有 race 声明不能证明不存在竞态，默认 false 会少提醒 checkpoint 对账。 |
| `trail.checkpoint_refresh_needed` | `unknown` | 没有 refresh 声明不能证明不需要刷新，默认 false 会少提醒更新 checkpoint。 |
| `trail.envelope_valid` | `unknown` | 没有结构化 validity 声明不能证明 envelope 无效，默认 false 会把无 envelope 误报为 invalid。 |
| `trail.handoff_in_flight` | `unknown` | 没有 in-flight 声明不能证明 handoff 已结束，默认 false 会少提醒继续处理。 |
| `trail.handoff_recovery_needed` | `unknown` | 没有 recovery 声明不能证明 bootstrap 正常，默认 false 会少提醒恢复动作。 |
| `trail.handoff_target_corrected` | `unknown` | 没有 corrected 声明不能证明目标未修正，默认 false 会少提醒重发或取消。 |
| `trail.judgment_unfiled` | `unknown` | 没有 unfiled 声明不能证明判断已归档，默认 false 会少提醒补录判断。 |
| `trail.reviewer_unavailable` | `unknown` | 没有 unavailable 声明不能证明 reviewer 可用，默认 false 会少提醒重新派发。 |
| `finding.closure_review_pending` | `unknown` | 没有 pending 声明不能证明 closure review 已完成，默认 false 会少提醒收口复核。 |

未知 key 是硬失败；不会落入 `unknown`，也不会被相邻 prose、dependency、chosen 或
negative substring 猜测。历史 trail 中的 `ticket.judgment_unfiled` 是唯一接受的兼容 alias，
读取时归一为 `trail.judgment_unfiled`；新行必须使用 canonical key。

迁移期为保持既有 50 个 renderer fixture 可读，任意旧 kind 的 `facts` object 仍被读取；
其中的 key 也必须属于上面的闭合集合。该兼容入口不是新写法。

### scope

- `attempt` facts 只作用于 `subject=attempt`、空 subject 或缺失 subject 的 attempt scope；
- Ticket facts 作用于 `ticket:<id>` 或裸 Ticket ID；
- finding facts 作用于 `finding:<id>` 或裸 finding ID。

把 fact 写入错误 subject 不会跨 scope 提升。

## projection validation result

`package.validate.projection_drift` 不再通过执行另一个 CLI 或解析错误文本得到。renderer
接受只读结构化 result：

```json
{"projection_drift":true}
```

通过 `render --validation-result '<json-object>'` inline 传入，或传入包含该 JSON object 的
文件路径；只允许 `projection_drift` 布尔字段和可选 `source` 字符串。错误结构/未知字段是
硬失败。该 result 优先于 trail fact；没有传入时才读 trail fact。因此 `render --at <commit>`
可以用同一个 validation result 判定快照，而不依赖当前 worktree 的 runtime CLI。

## 写入分工

**凡以 CLI mutation 收尾的动作，由 CLI 自己追加轨迹行。** 主控无额外成本，且这些行天然
是地面真相：

```text
package init / validate / refresh-progress
evidence add / invalidate
ticket satisfy | block | needs-revalidation | pending | retire
recovery checkpoint / judgment
gate <verdict>
```

**没有其它载体的声明动作写 `kind=fact` 或对应事件：**

```text
dispatch 的发起与返回
escape
B1 选哪个 Ticket
E4 finding 定级
E5 findings 分流
C3 / C5 的来源路由判断
carrier/evidence/comparison/release-edge/manual/review/source facts
```

轨迹记选择和机读事实；Execution Record 记长期判断。两者通过 `ref` 关联，不互相复制。
