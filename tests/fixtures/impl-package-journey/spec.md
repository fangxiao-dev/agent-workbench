# Spec

### Journeys

#### J1 纠正后下一张账单用新科目

| Step | 操作入口 | 观察表面 | 预期 |
| --- | --- | --- | --- |
| J1-S1 | 税务端 Review 页确认账单 | 门店答案读取 API | 答案为 4982 |
| J1-S2 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签“本门店记忆” |

### Rule Matrix

| Rule | Suite | Oracle |
| --- | --- | --- |
| R1 | S-resolver | 解析表每行来源与状态正确 |

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |
| S-resolver | rule | ticket | pnpm test resolver | local-test |
| S-workflow | rule | ticket | pnpm test workflow | local-test |
| S-safety | safety | package | pnpm test:integration tenant | local-pg |
