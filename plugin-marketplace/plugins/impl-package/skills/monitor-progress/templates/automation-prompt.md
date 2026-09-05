监控 `{{AUTOMATION_ID}}`；root=`{{WORKSPACE_ROOT_JSON}}`，cli=`{{MONITOR_CLI_PATH_JSON}}`，static=`{{STATIC_HASH}}`。

每轮：
1. read-cycle：packageStatus=正式，ticketPresentation=展示，targetUpdates=进展；ownerInputs 按 observations 顺序分类，items: []=不可见。
2. confirmed 生效；真实兜底按 observation 条件+turn 去重；steer前看上下文，idle≠block，讨论不发。dry-run 仅模拟，candidate 不授权。明确实例/一次决策=one-time；实例替换后仍约束同类=kind=pattern；混合拆分/topic 单轴，工具调试不入 sidecar。
3. progress=事实/必修问题，improvements=可选建议，next=动作，owner=裁决；保存 cursors、renderer/health、lastSimulationCorrection 后调用 write-cycle。
4. 最终逐字输出 write-cycle.notification.reportText，不改写、不加标题或总结；static异常时 read-static。

只读两task；仅CLI写。
