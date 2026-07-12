# Owner-Facing Reporting Contract

Impl-Package 的 canonical identifiers、artifact 和状态字段服务于 agent 恢复、去歧义与审计；它们不是给 owner 的汇报主体。凡向 owner 汇报 proposal、阶段状态、review、gate、最终交付或剩余工作，都先使用 `talk-to-boss`，再附 canonical handoff。

## 决策主体

首段必须独立回答：本次功能范围是什么、哪个准确阶段已完成、还剩多少工作、整体是否 closed、当前需要 owner 决定什么。没有待决策也明确说明。

主体按功能或交付 slice 组织，解释用户能力、业务约束、验收结果和影响。不要按 task、文件、命令、agent、DAG cohort 或 artifact 分类。review 先说明是否阻止合入、影响什么行为、需要什么决定，再列 finding 证据。

## Canonical 证据与 handoff

`package-id`、Attempt / Design / Spec / Plan revision、Composition、ticket/task ID、Execution Record/gate anchor、commit、路径和命令只放在“技术证据 / 执行交接”之后，不能作为开场。若同一回复既面向 owner 又面向下游 agent，顺序固定为：

1. owner-readable decision summary；
2. 功能 slice、剩余工作与风险；
3. canonical handoff/evidence。

S/M/L/D 首次出现在人类汇报时必须展开，例如“M：需要多个可独立验收切片，但不需要执行依赖图”；不能只报字母或 `tickets=true, dag=false`。

stage skill 自己的 Output Contract 继续定义 machine/canonical payload，但不得覆盖本合同的人类汇报顺序。
