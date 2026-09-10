---
name: project-knowledge-manager
description: 回刷已完成工作产生的长期项目知识：一次调度 hands-on 与 stable-docs 两条 lane，并统一去重、应用和验收。
disable-model-invocation: true
---

# Project Knowledge Manager

这是长期项目知识回刷的显式总入口。只有用户点名 `$project-knowledge-manager` 时运行；普通“沉淀经验”或“回刷稳定文档”继续走各自的单 lane Skill。

Manager 只代替用户发出固定的下一组指令。知识分类、证据、目标、写作和 metadata 规则分别由全局 `$learn-lessons` 与 `/impl-package:backfill-stable-docs` 拥有。

## 固定调度

1. 从参数或当前对话确定已完成工作的来源，记录仓库、branch、Source HEAD、dirty 状态，并读取仓库 instructions 与文档治理。
2. 读取两个 peer Skill；有相应来源时，按 `$dispatcher` 同时派出两个只读审计：
   - `$learn-lessons` 审计 hands-on knowledge；
   - `/impl-package:backfill-stable-docs` 审计稳定产品、架构与行为合同。
3. Codex 默认使用两个只读 `luna-worker`，其他宿主使用等价 worker；没有 subagent 能力时由主线程顺序完成同样的只读审计。brief 只需包含来源、Source HEAD、dirty 状态、目标 lane 和只读边界。
4. Gate 缺失、schema 旧或来源不是标准 package 时仍派发；具体兼容审计由 peer Skill 自己执行。没有相应来源的 lane 跳过，两条都无候选时返回 `no-delta`。
5. 主线程消费两个结果，按 peer Skill 规则复核、跨 lane 去重、应用非破坏性文档更新，并检查 diff、路径、链接、metadata 与最小验证。稳定合同不复制到 hands-on；冲突项停写并交给 Owner。

## 授权与结果

显式调用 Manager 即授权本轮非破坏性文档创建和更新。移动、重命名、删除、retirement、package 状态修改、代码或外部系统变更仍需独立授权。

最终报告来源数、各 lane 是否运行、候选与 `applied | already-covered | no-delta | source-insufficient | pending | conflict` 计数、跨 lane 去重数、修改文件及验证结果。无 durable delta 时只报告 `no-delta`，不制造文档。
