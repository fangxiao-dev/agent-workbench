# Spec

## 1. 核心目标

稳定地从 source 产出可验证结果。

## 7. 验收

### Journeys

#### J1 source 到结果

准备：同一租户的一份输入。

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J1-S1 | 操作员 | 文件 | — | 下载结果文件 | 结果文件 | 文件含 projection | — |

### Rule Matrix

| Rule | Source | Suite | Oracle |
| --- | --- | --- | --- |
| R1 | §1 | S-safety | 租户、授权与幂等不变量成立 |
| R2 | §1 | S-source | source snapshot 可由授权主体读回 |

- 无需验收的章节： none

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |
| S-source | rule | ticket | pytest tests/source | local-test |
| S-safety | safety | package | pytest tests/safety | local-test |
