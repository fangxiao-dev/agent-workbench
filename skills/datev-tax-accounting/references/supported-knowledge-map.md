# 公开规则与 KaiSpan owner 路由

## 稳定概念链

```text
Finance-visible OCR / structured source
  -> CanonicalAccountingFactsV1 + evidence + hash
  -> Reviewed facts
  -> versioned policy mapping
  -> resolver / grouping
  -> BookingCandidate
  -> serialized DATEV artifact
```

## 信息应由谁提供

| 问题 | Owner |
| --- | --- |
| 公开 DATEV 术语、格式与年度参考 | 此 Skill 的 glossary、source policy 与 versioned public references |
| 稳定领域概念、字段 authority、分类/税务边界 | `docs/domains/finance-assistant/context/datev-accounting/` |
| 当前产品行为、gate 与 UI 文案 | Finance module PRD / Spec |
| 当前实现、验证、外部验收与闭合状态 | Finance capability registry |
| 某个 Mandant 的账户、Kreditor、税务 mapping 与启用能力 | approved runtime profile / policy |
| 历史决策、变更过程与一次性证据 | implementation package |

本文件不维护任务编号、时间戳、测试计数、worktree、能力状态或 external-acceptance 结论。读取 capability registry 后才能对此类状态作出陈述。

## 当前知识入口

- `docs/domains/finance-assistant/context/datev-accounting/README.md`：领域知识入口与条件阅读路由。
- `docs/domains/finance-assistant/module-knowledge/datev-accounting/`：当前模块意图、行为和 capability registry。
- 相关 implementation package：仅在需要追溯某项决策或证据转变时读取。
