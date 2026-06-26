---
name: kaispan-ui-design
description: Thin router for KaiSpan and Supplier Admin (webshop) UI work — prototype absorption, business-area Overview-first layout, finance UI surfaces. Points to the repo-local source-of-truth docs and three guardrails. Use when asked to design/build/review KaiSpan or webshop admin UI, or to absorb the boss's prototype.
---

# KaiSpan UI Design (thin router)

> 2026-06-26:原 kaispan-ui-design 治理套件(ksui:// locator 协议、global/module/review 三个 child skill、readiness/slice/closure 模板、`.kaispan-ui-design.json` 指针)已**整套退役**——对 2 人小队过度设计,且仓库侧对应基础设施已删。本 skill 现在只做一件事:把你指到 repo 内的真实事实源 + 三条红线。不要再找 locator、模板或停机协议。

## 去哪读(事实源都在产品 repo,不在本 skill)

| 你要做的事 | 文件 |
| --- | --- |
| webshop 后台布局落地(唯一规范) | webshop repo `docs/top-level-knowledge/admin-layout-grammar.md` |
| webshop 执行节奏 | webshop repo `docs/epic-plans/2026-06-26-admin-layout-grammar-roadmap-lean.md` |
| webshop 需求背景 / 老板原始示例 | webshop repo `docs/epic-plans/2026-06-23-admin-canonical-ui-absorption-roadmap.md`(reference) |
| KaiSpan 财务 UI prototype 语义 | kaispan-dev repo `docs/kaispan-ui-design/finance-prototype-notes.md` |
| 实际写 UI 组件 | `frontend-design` skill |

进入某个 repo 时,以该 repo 的 `AGENTS.md` / `web/AGENTS.md` 为准。

## 三条红线(其余都交给上面的文档)

1. **prototype 是输入,真实 App 是 source of truth。** 不逐像素复刻 HTML;截图 + 业务语义对齐优先。
2. **钱 / 外部副作用没接通 = disabled,不伪装成已实现。** 金额需 Decimal/币种/provenance/审计;Lexware 等真实 mutation 边界不为布局重构搬动。
3. **committed 证据不含客户数据 / 密钥 / IBAN / token。**

## 想新增 skill 时(沉淀,不要预判)

只有当某个流程**手工跑过 2~3 次、每次重复同样的痛、且可泛化**,才用 `skill-creator` 抽成 skill;平时用 `continuous-learning` 收集提案、由用户审批。不要为"将来可能用到"提前搭治理套件——那正是本套件被退役的原因。
