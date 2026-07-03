# [Implementation Name] Plan

状态：[计划中 / 活跃 / 暂停 / 已关闭]
创建：[YYYY-MM-DD]
来源：[existing impl-plan / handoff / issue / discussion]
配套 DAG：[dag.md](dag.md)
配套 Findings：[findings.md](findings.md)
配套 Gate：[gate.md](gate.md)

本文是 implementation 的唯一主控入口：记录目标、范围、验收、边界和实现策略。执行调度写入 `dag.md`，局部任务进度写入 `tasks/`。

## 背景与目标

- 背景：
- 目标：
- 非目标：

## Scope

- In scope：
- Out of scope：
- Safety / mutation boundary：

## Functional Slices

| Slice | What to build | User-visible result | Acceptance gate |
| --- | --- | --- | --- |
| [slice] | [work] | [result] | [gate] |

## Implementation Strategy

- Shared contracts：
- Key seams：
- Verification approach：

## Existing Plan Adoption

适用于中途接入；新计划可标记 N/A。

- Original plan/source：
- Adoption mode：[migrated into this file / linked as source / summarized from handoff]
- Legacy location handling：[left in place / indexed / archived later]

## Gate Checklist

- [ ] Functional slices implemented.
- [ ] DAG tasks integrated.
- [ ] Required local verification completed or deferred with reason.
- [ ] Required browser/external verification completed or deferred with reason.
- [ ] Cross-task findings handled or tracked.
- [ ] Final gate decision recorded in `gate.md`.

## Current Next

1. [next action]
2. [next action]
