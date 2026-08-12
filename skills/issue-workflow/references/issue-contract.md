# Issue Workflow 合同说明

机器可校验的 label、基数和交接边只在 [issue-contract.yaml](issue-contract.yaml) 定义；本文件只说明如何判断。`$issue-triage` 使用该合同生成并确认写入 proposal，`$issue-reporter` 使用同一合同作只读诊断。

普通 leaf 是默认交付工作，不带 `work:` label。`feature` 表示新的产品能力或首次可用业务流程；`enhancement` 只表示对既有能力的加强、扩展或体验改进。`work:investigation` 的交付物是事实、结论或决策；它和 leaf 一样需要一个 type 与一个 readiness。`work:initiative` 是协调父事项，默认不进入可执行队列，只有它自身等待 owner 决策或被阻塞时才带 readiness。

`needs-info` 是工作定义还不充分；`ready-for-human` 是定义充分但下一位是 owner（决策、授权或 review）；`blocked` 是定义充分但等待已知依赖，并且必须记录其依赖。高优先级但可以推进的工作仍按实际 readiness 处理，由 triage 简报说明优先次序；不使用 priority label。

PR 是既有 parent 或 leaf Issue 的交付证据。仅当工作需要独立验收、assignee、branch 或依赖时创建 sub-issue。Reporter 读取当前组合并将不合规项列为 Hygiene；它不自动修复。
