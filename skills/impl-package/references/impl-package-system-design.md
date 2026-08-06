# Impl-Package System Design

Impl-Package 是一条可按复杂度裁剪的实施链：Decision/Spec → Plan → 可选 Tickets/DAG → current state → verification → Gate → stable-doc backfill。

设计目标是保留会影响行动的事实，而不是复制 Git 已经提供的审计能力：

- contract 文档保存行为、验收和执行选择；
- `.impl-package/state.json` 保存唯一活动 Attempt 的 Task/Ticket/resume current state；
- `progress.md`、Ticket/DAG Runtime 表是 machine-owned projection；
- `execution/<attempt>/execution-record.md` 保存公共 checkpoint/judgment，Task Handoff 保存条件式局部接手上下文；
- `gate.md` 保存当前判决和 Git comparison commit；
- Git 保存内容历史、旧状态和责任边界。

体系只保留当前 `state.json` 的 `formatVersion: "3.4"`，不维护多代格式迁移链、文件内容身份或并行审计状态。未来结构不兼容时提升格式号，同时修改 validator、模板和测试；仍需继续使用的旧 package 由 agent 直接 reshape，不建立兼容读取路径。

所有跨文件引用使用仓库相对路径。已知 artifact 使用固定目录或显式路径。
