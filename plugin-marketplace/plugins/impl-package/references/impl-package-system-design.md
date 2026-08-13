# Impl-Package System Design

Impl-Package 是一条可按复杂度裁剪的实施链：Decision/Spec → Plan → 可选 Ticket → current state → verification → Gate → stable-doc backfill。DAG/Task 只为旧 package 的恢复与迁移保留。

设计目标是保留会影响行动的事实，而不是复制 Git 已经提供的审计能力：

- contract 文档保存行为、验收和执行选择；
- `.impl-package/state.json` 保存唯一活动 Attempt 的 Ticket、evidenceIndex 和 activeCheckpoints；3.5 不再有 `tasks` 或 `resume` 字段；
- `progress.md`、Ticket Runtime 表是 machine-owned projection；新 package 不生成 DAG Runtime 表；
- `execution/<attempt>/execution-record.md` 保存 judgment/审计上下文；active checkpoint 由 state index 管理，Task Handoff 只为迁移输入保留；
- `gate.md` 保存当前判决和 Git comparison commit；
- Git 保存内容历史、旧状态和责任边界。

体系当前使用 `state.json` 的 `formatVersion: "3.5"`，不维护长期双读器或多代格式迁移链。3.4/Task package 通过一次性 migration prompt/runbook 和只读 validator 切换；迁移完成后新 runtime 只读 3.5。

所有跨文件引用使用仓库相对路径。已知 artifact 使用固定目录或显式路径。
