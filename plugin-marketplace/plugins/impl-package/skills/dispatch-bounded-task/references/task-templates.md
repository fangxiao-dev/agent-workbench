# Bounded Task 模板

只选择一个模板，并删除当前 Task 不适用的可选字段。caller 负责给出真实边界；模板不补写缺失的 Task 设计。

## Implementer

```text
角色：在既定 primary ownership 内完成实现，不改变需求、架构、授权或 Ticket 验收。
目标/来源：<bounded outcome；批准的 Plan/Ticket/DAG pointer 与 source unit>
边界：workdir=<绝对路径>；ownership=<写集>；禁改=<范围>；depends/tickets=<引用>
调度：<scheduling contract>
输入：<必要 contract/files>；集成性 Task 另列冻结接口与正反向行为
验证：<局部命令或检查>
```

## Fixer

```text
角色：修复已确认且已边界化的 review finding；不重新裁决 finding、不扩大范围、不宣称 closure，也不以未证实的替代解释撤销既有修复。
目标/来源：<bounded fix outcome；批准的 Plan/Ticket/DAG pointer 与 source unit；finding ID/ledger/reviewer>
比较点：<review target revision/comparison point>
已确认事实：<broken invariant/failure evidence；finding disposition/owner acceptance>
边界：workdir=<绝对路径>；ownership=<写集>；禁改=<范围>；depends/tickets=<引用>
调度：<scheduling contract>
输入：<必要 contract/files>；集成性修复另列冻结接口与正反向行为
验证：<局部命令或检查>
```

## Verifier

```text
角色：执行既定动作并返回压缩证据；主 session 拥有资源顺序、证据采信与最终 claim。
目标/来源：<bounded claim；批准的 Plan/Ticket/DAG pointer 与 source unit>
边界：workdir=<绝对路径>；actions=<顺序命令/检查>；禁改=<范围>
调度：<scheduling contract>
证据：<结果/exit、关键计数、首个失败、cleanup/residue、artifact pointer>
```

三类 worker 都按父 Skill 的统一结果合同回报：`Outcome: DONE | BLOCKED | INCOMPLETE`，并附该 outcome 所需的直接证据或恢复事实；过程细节留在自己的执行上下文。
