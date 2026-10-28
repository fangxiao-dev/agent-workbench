# Spec

## 1. 核心目标

在账单更正后将稳定的判定结果用于下一张同类账单。

## 2. 业务规则

更正确认后，后续同类账单应读取门店记忆。

### 2.1 账单标识

后续账单通过账单 ID 关联到记忆。

## 3. 实施边界

该 Spec 不规定界面布局。

## 7. 验收

### Journeys

#### J1 纠正后下一张账单用新科目

准备：同一门店、三张同条件票据。

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J1-S1 | 税务师 | 页面 | 完成 | 税务端 Review 页点击“完成” | Review 页记录 | 答案为 4982 | — |
| J1-S2 | 企业端用户 | 页面 | 科目 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签“本门店记忆” | 账单 ID |

### Rule Matrix

| Rule | Source | Suite | Oracle |
| --- | --- | --- | --- |
| R1 | §2 | S-resolver | 解析表每行来源与状态正确 |

- 无需验收的章节： §1, §3

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |
| S-resolver | rule | ticket | pnpm test resolver | local-test |
| S-workflow | rule | ticket | pnpm test workflow | local-test |
| S-safety | safety | package | pnpm test:integration tenant | local-pg |
