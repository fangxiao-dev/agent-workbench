# Impl-Package System Design

Impl-Package 是一条可按复杂度裁剪的实施链：Decision/Spec → Plan → 可选 Ticket → current state → verification → Gate → stable-doc backfill。DAG/Task 只为旧 package 的恢复与迁移保留。

设计目标是保留会影响行动的事实，而不是复制 Git 已经提供的审计能力：

- contract 文档保存行为、验收和执行选择；
- `.impl-package/state.json` 保存唯一活动 Attempt 的 Ticket/resume current state；阶段 A 的 3.4 兼容桥可能保留空 `tasks` 字段；
- `progress.md`、Ticket Runtime 表是 machine-owned projection；旧 package 才有 DAG Runtime 表；
- `execution/<attempt>/execution-record.md` 保存公共 checkpoint/judgment 和跨 session 判断；Task Handoff 只为旧 package 保存条件式局部接手上下文；
- `gate.md` 保存当前判决和 Git comparison commit；
- Git 保存内容历史、旧状态和责任边界。

体系只保留当前 `state.json` 的 `formatVersion: "3.4"`，不维护多代格式迁移链、文件内容身份或并行审计状态。阶段 A 只锁定 Ticket-only 合同和 fixture；阶段 B 才提升格式并修改 validator、模板和测试。旧 package 在迁移完成前继续走 3.4 兼容路径。

所有跨文件引用使用仓库相对路径。已知 artifact 使用固定目录或显式路径。
