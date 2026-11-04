# Spec

## 1. 核心目标

fixture 的验收合同。

This fixture references a live implementation package.

- Reference: `docs/implementations/260801-live-contract/`
- Self reference: `docs/implementations/p4-live-package-reference/`

## 7. 验收

### Journeys

#### J1 fixture journey

准备：fixture 数据。

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J1-S1 | 操作员 | 页面 | 完成 | fixture 页面点击“完成” | fixture 页面 | 看到结果 | — |

### Rule Matrix

| Rule | Source | Suite | Oracle |
| --- | --- | --- | --- |
| R1 | §1 | S-fixture | fixture 规则成立 |

- 无需验收的章节： none

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |
| S-fixture | rule | package | fixture test | local-test |
