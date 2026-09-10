# 执行行为诊断（基线 `d25c584`）

## 交付状态

- 诊断交付：`DONE`
- 证据状态：`EVIDENCE_SUFFICIENT`（规则、投影、准入边界和事件顺序）；`EVIDENCE_GAP`（历史主控为何作出错误动作、无法恢复的 live worker 状态）。
- 范围：四种表现各取一个代表；每类只做一次隔离条件检查；没有 runtime、Skill、业务环境、真实 worker 或用户配置修改。
- 验收边界：本轮执行了真实 renderer/准入检查，没有恢复历史 live worker 或让模型重放完整长上下文后实际选择工具。fixture 结果只证明当前投影边界，不能证明历史执行行为已复现或根因已解决；基线源码核对也不等于每个历史事件均已加载完全相同的插件内容。
- 原始日志只读窗口：
  - B2：`C:\Users\Xiao\.codex\sessions\2026\09\09\rollout-2026-09-09T16-03-55-01a0867b-7f00-79f1-9d83-d8e11b075c4e.jsonl`
  - B3：`C:\Users\Xiao\.codex\sessions\2026\09\10\rollout-2026-09-10T02-18-25-01a088ae-14a2-7c23-bbb6-76cd593fef0f.jsonl`

## 规则与基线核对

`d25c584` 的 `skills/dispatcher/SKILL.md:13,16,34` 要求在等待事件扫描剩余路径、局部 barrier 只影响相关候选；running worker 继续等待，时长/timeout 只调整轮询，只有用户取消、越权/危险 mutation、不可恢复资源冲突或 carrier/tool 明确失败才允许中断。`situation-inputs.md:63,76,988` 明确投影只消费 package 输入、输出 `blocking/runnable/withheld/in_flight`，无关 in-flight 不压制 ready，投影不承诺主控发现的全部工作。`situations.yaml:153-171` 将 `ticket.investigate.no-carrier` 的 `dispatch-investigate` 与 `implement-direct` 分开；前者不因 implementation dependency 自动被挡。

相关实现证据：`situation.py:3161-3181` 只按未匹配 return 列在途 dispatch；`3192-3231` 只对 implement/fix 检查 Ticket implementation dependency，或同 candidate/同 work+resource；`3373-3383` 再把局部命中分为 runnable/withheld，只有四个 P0 清空 runnable。当前 worktree 相对基线唯一相关变更是 `situations.yaml` 的 evidence CLI 文案一行，未触及本诊断行或 renderer。

## 四类代表与验证

| 表现 | 原始事件与已核事实 | 一次隔离检查与观察 | 判断 |
| --- | --- | --- | --- |
| 已知候选被忽略 | B2 `L2891` 的真实 situation 输出列出 `ticket.investigate.no-carrier:TKT-03:dispatch-investigate` 为 runnable；B2 `L2904-L2905` 派发 TKT-02 implement；B2 `L2925-L3001` 说明 TKT-03 被保留并连续 wait，没有新的 render；下一次相关投影在 `L3278`。 | 临时复制 `p2-investigate-no-carrier`，补一个 PENDING TKT-02 和其 RUNNING dispatch，再执行 `python plugin-marketplace/plugins/impl-package/scripts/situation.py render --package <temp> --no-write-credential --json`，并调用 `situation.dispatch_admission` 检查 TKT-01 的 `dispatch-investigate`。结果：TKT-01 investigate runnable，TKT-02 在 `in_flight`，准入 `[]`。 | `EVIDENCE_SUFFICIENT` 证明 renderer/准入没有全局 wait；历史“看见后仍等待”可确证。为何主控把 TKT-03 的实现前置误套到调查、以及真实资源/授权是否还有未见约束，无法从可恢复材料确认，`OF-01` 保持 open。 |
| 关联候选未进入上下文 | B3 `L1638` 用户明确给出 `#301/#302/#303`，说无需加入 package、可提前准备；`L1642` 主控承诺读取关系。首次读取在 `L1661-L1783` 因 worktree 无 `glab`/远程凭据失败；`L1797-L1824` 用户纠偏后才从主工作区读取并得到依赖链。 | 临时复制 `p1-worker-still-running`，基线 render 无 intake、无 issue candidate；只做一次条件恢复，在 `.impl-package/intake.jsonl` 放入三条 issue 标识后再次真实 render。结果只出现泛化 `package.record.intake-backlog`/`drain-intake`，没有 `#301/#302/#303` 专项候选，原在途仍独立列出。 | `EVIDENCE_SUFFICIENT` 证明 package 投影不会从外部关联 Issue 自动建候选；这是输入边界，不是 renderer 漏算。外部候选应由主控发现职责/上下文入口承接；首次凭据与 worktree 失配是已知条件缺口，`OF-02` 保持 open。 |
| 无正当理由中断 | B2 `L320` 用户要求保留上下文并让 worker 总结；`L1244` 主控书面承诺 timeout 不再中断；约 1.5 小时后 B2 `L3022-L3023` 仍以“超过 30 分钟、无代码落盘、总结消息未处理”为理由调用 `interrupt_agent`，`L3026` 返回的 `previous_status` 是 `running`；后续仅向同 worker follow-up（`L3030`）。 | 对 `p1-worker-still-running` 执行真实 render：`blocking=[]`、`runnable=[]`、`withheld=[]`，仅有一个 `in_flight`。未操作真实 agent，也未伪造长时间等待。 | `EVIDENCE_SUFFICIENT` 确认历史中断不满足当前 Skill 已列的授权条件，属于 open finding；隔离投影支持等待语义，但不能复现模型在长上下文中的实际 interrupt 选择。根因 `EVIDENCE_GAP`，`OF-03` 保持 open。 |
| 收尾误作主线前置 | B3 `L3344` 开始 `backfill-stable-docs`；`L3355` 检查发现 `.stable-docs-backfill.json` 缺失；`L3373-L3425` 改走直接文档回刷；`L3651-L3707` 在主线仍有完整 suite/Issue 收口时继续并行回刷。用户在 `L3719` 要求先发布 Issue，主控在 `L3729-L3730` 才调整为先发 `#301-#303`、backfill 不再是前置。 | 对 `p4-all-terminal-durable-missing` 执行真实 render，得到并列的 `audit-completion-claim`、`dispatch-terminal-review`、`record-durable-delta`；没有 Issue 发布或外部依赖信息。 | `EVIDENCE_SUFFICIENT` 证明 package projection 只给 durable-delta/Gate 局部动作，不能决定外部 Issue 顺序。事件中的主线阻塞和用户纠偏已确证；是主控优先级/交付边界判断，非 backfill runtime 强制，具体机制 `EVIDENCE_GAP`，`OF-04` 保持 open。 |

## 可复跑命令与验证结果

以下命令可重跑源码检查和仓库既有 situation 回归；表中临时 fixture 改造没有作为独立重放产物交付，其观察作为本次隔离检查记录，不宣称这些命令能重现历史主控行为。

- `python plugin-marketplace/plugins/impl-package/scripts/situation.py check` → `check: PASS`，42 situations、51 implemented when keys。
- `python -m pytest -q -p no:cacheprovider tests/test_situation_render.py -k "situation_render or dispatch_outcomes_stay_bound_to_candidate_and_incomplete_is_recoverable or business_actions_are_runnable_without_registration or historical_registration_is_readable_but_not_projected or inflight_identity_distinguishes_independent_review_tracks" --disable-warnings` → `97 passed in 57.25s`。
- 四次临时 fixture 均使用 `--no-write-credential`；临时目录创建后立即删除。交付文档未写入 token、secret 或加密 brief。

## 建议、缺口与停止证明

暂不新增 hook 或改 runtime。下一轮若要推进，应先提供可重放的长上下文/worker 状态和主控实际工具选择；基线未在该链路重新变红前，不做“动作前提示”与“额外投影注入”的效果声明。对 #301–#303，保留“外部候选不属于 package projection”的边界，另行决定主控读取 Issue 线索的入口；对 backfill，显式来源 apply 与 Issue 发布保持两个可独立推进的交付动作。

停止证明：已读取收敛文档规定的 §5 第四项与 §7 停止规则、`report.md`/`second-opinion-codex.md` 的既有定位；四类各一代表、每类最多一次条件检查；未全量扫描五份日志、未执行真实 training/业务环境、未中断用户 worker、未进行第二次干预或任何 runtime 修改。当前结论是“诊断已交付”，不是“历史 open finding 已销案”。
