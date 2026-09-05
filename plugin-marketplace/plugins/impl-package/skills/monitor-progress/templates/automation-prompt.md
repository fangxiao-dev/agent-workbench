监控 `{{AUTOMATION_ID}}`；root=`{{WORKSPACE_ROOT_JSON}}`，cli=`{{MONITOR_CLI_PATH_JSON}}`，static=`{{STATIC_HASH}}`。

每轮：
1. read-cycle：packageStatus=正式，ticketPresentation=展示，targetUpdates=进展；ownerInputs 按 observations 顺序分类，items: []=不可见。
2. confirmed 生效；真实兜底按 observation 条件+turn 去重；steer前看上下文，idle≠block，讨论不发。dry-run 仅模拟，candidate 不授权。明确实例/一次决策=one-time；实例替换后仍约束同类=kind=pattern；混合拆分/topic 单轴，工具调试不入 sidecar。
3. progress=事实/必修问题，improvements=不影响收口的可选建议，next=动作，owner=裁决；不造字段。target语义变化、packageDiff/observationDiff/纠偏/健康变化→NOTIFY。
4. observationDiff 写 kind/增改删；更新含 before→after/全文。
5. NOTIFY 含“模拟纠偏”：触发写原因/全文/未发送，否则写“无”；空值不触发。
6. 保存 nextRolloutCursors、renderer/health、lastSimulationCorrection；write-cycle确认。无变化 DONT_NOTIFY；static异常 read-static。

只读两task；仅CLI写。
