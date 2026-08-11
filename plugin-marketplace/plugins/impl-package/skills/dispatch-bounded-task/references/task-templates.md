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

## Verifier

```text
角色：执行既定动作并返回压缩证据；主 session 拥有资源顺序、证据采信与最终 claim。
目标/来源：<bounded claim；批准的 Plan/Ticket/DAG pointer 与 source unit>
边界：workdir=<绝对路径>；actions=<顺序命令/检查>；禁改=<范围>
调度：<scheduling contract>
证据：<结果/exit、关键计数、首个失败、cleanup/residue、artifact pointer>
```

两类 worker 都按父 Skill 的返回合同回报，并在自己的执行上下文保留过程细节。
