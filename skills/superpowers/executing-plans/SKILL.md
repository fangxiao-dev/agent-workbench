---
name: executing-plans
description: Use when an approved written plan or handoff is ready for execution and the task needs disciplined progress, evidence capture, and blocker handling.
---

# Executing Plans

执行计划时，计划提供意图和顺序，当前仓库规则决定权限、状态 owner 和验证方式。不要建立第二套执行记录。

## 开始前

1. 读取计划、当前用户授权和适用的仓库规则。
2. 检查计划是否仍与当前代码、依赖和环境一致。
3. 识别 blocker、缺失决策和越权动作；真正阻止执行的问题先交给 owner。
4. 如果项目有专用执行 skill、DAG 或 progress ledger，交由它拥有执行状态。

## 执行

- 按依赖顺序选择下一可执行单元；可安全并行的单元才交给多个 agent。
- 每个单元只做计划授权的范围；发现 contract drift 时回到对应设计或计划 owner。
- 运行计划指定或仓库政策要求的验证，并记录实际结果而不是预期结果。
- 计划需要修订时更新其正式 revision 或 owner artifact，不在聊天中维护影子 checklist。

## 停止条件

在以下情况暂停并说明具体缺口：

- 权限或 owner decision 缺失；
- 计划与当前事实冲突；
- 执行暴露出新的行为或接口选择；
- 验证失败且尚未确定根因；
- 下一步会产生未授权的外部或破坏性副作用。

普通实现困难不是暂停理由；在授权范围内能够调查、修正或继续验证时，应持续推进。

## 收口

完成声明必须基于当前 revision 的验证证据。Git、PR、合并、发布和清理遵循项目自己的流程及用户授权，本 skill 不提供固定收口菜单。
