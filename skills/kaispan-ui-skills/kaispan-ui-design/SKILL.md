---
name: kaispan-ui-design
description: KaiSpan and admin UI migration guide for prototype absorption, billing/finance UI surfaces, business-area Overview-first layout, preview/screenshot harness flow, and real-route absorption. Use when asked to design/build/review KaiSpan or admin UI, migrate a billing UI using the same preview harness pattern, or absorb the boss's prototype into the real app.
---

# KaiSpan UI Design

## 去哪读(事实源都在目标产品 repo,不在本 skill)

本 skill 是跨项目 UI 迁移流程规则。不要把某个具体产品 repo 的文档当成全局事实源。
进入任意目标项目时,先以该项目自己的 `AGENTS.md` / app-level instructions 为准,再读取该项目内的 UI grammar、`kaispan-ui-design/`、roadmap、process/findings 等文件。

推荐每个采用本流程的项目都维护下面这组结构;若项目使用不同文件名,以项目内 README / roadmap 指向为准。

| 你要做的事 | 文件 |
| --- | --- |
| 后台 / admin 布局落地(项目内唯一规范) | target repo `docs/top-level-knowledge/admin-layout-grammar.md` 或项目指定 UI grammar |
| UI 迁移机制(两层设计) | target repo `docs/kaispan-ui-design/ui-migration-mechanism.md` |
| 模块级 Phase A 结论 / Phase B contract | target repo `docs/kaispan-ui-design/module-contracts/<module>-<submodule>.md` |
| 执行节奏 / roadmap | target repo `docs/epic-plans/...` 或项目指定 roadmap |
| 需求背景 / 原始 prototype / 老板示例 | target repo 中记录为 reference 的 prototype / roadmap / snapshot 文档 |
| 财务 / billing UI prototype 语义 | target repo 或相关 source repo 的 `docs/kaispan-ui-design/...` 领域说明 |
| 基于 Phase A review / 截图证据制定 Module Contract | `kaispan-ui-module-contracts` |
| UI 迁移执行跟踪 / preview harness 控制 | `dev-with-track` skill |
| 实际写 UI 组件 | `frontend-design` skill |

进入某个 repo 时,以该 repo 的 `AGENTS.md` / app-level instructions 为准。

## UI 迁移流程路由

当任务是 KaiSpan / Supplier Admin / finance billing 或其它后台产品的 prototype absorption、UI 迁移、preview / screenshot harness、fixture-only migration、process/findings/gate 账本、Phase A 截图对齐或 Phase B 真实页面吸收时:

- 本 skill 负责 UI 迁移流程、领域语义、事实源和红线。
- `kaispan-ui-module-contracts` 负责把人工 review、截图证据和 findings 落成 `docs/kaispan-ui-design/module-contracts/<module>.md`。
- `dev-with-track` 负责轻量执行跟踪、gate 判断和状态回写。
- `frontend-design` 负责具体视觉和组件实现。

## UI 迁移流程

这套流程用于把老板 prototype、业务截图或 billing / finance UI 设想吸收到真实 App。核心原则是:prototype 是输入,真实 App 是 source of truth;先用 preview/harness 低成本对齐语义,再吸收到真实 route。

### 两层 UI 设计机制

后台 / admin UI 迁移必须分成两层记录:

1. **Layout Grammar**:跨模块通用语法,来源是 `docs/top-level-knowledge/admin-layout-grammar.md`。它回答 Overview-first、动作承载矩阵、detail workspace、tab 降级等共通规则。
2. **Module Contract**:模块级 Phase A 结论,来源是 `docs/kaispan-ui-design/module-contracts/<module>-<submodule>.md`。它回答某个模块的子模块优先级、primary / secondary CTA、状态区、drawer/dialog/detail/page 决策、Phase B 真实接入边界和待确认项。

`docs/kaispan-ui-design/ui-migration-mechanism.md` 解释这两层机制。Phase A 的截图不是最终交付物;截图必须配套 Module Contract。Phase B 真实 route absorption 以 Layout Grammar + Module Contract 为依据,而不是只照截图复刻。

当用户要求“根据 review 更新 contract”“制定 module contract”“沉淀 Phase A 结论”或“为 Phase B 准备契约”时,本 skill 只负责事实源和边界定位;contract 写作与更新交给 `kaispan-ui-module-contracts`。

### 1. 业务语义与事实源定位

先确认这个 UI 迁移属于哪个真实业务上下文:

- KaiSpan finance / billing surface;
- Supplier Admin business area;
- admin Overview-first layout;
- ERP / Lexware / Rechnung / billing document surface;
- 其它需要用户确认的 finance/admin 子模块。

需要读取对应 repo 的事实源和 `AGENTS.md`。不要只看 prototype 截图就开始改真实页面。

对齐问题:

- 页面有哪些子模块?
- 哪些信息第一眼必须可见?
- 哪个是 primary action,哪些是 secondary action?
- action 应该进入列表、drawer、dialog、detail page,还是 disabled placeholder?
- 哪些真实能力尚未接通,必须 disabled,不能伪装成已实现?

### 2. 页面抽取与预完善

从真实业务页面抽出可预览的 UI surface,建立 dev-only preview / screenshot harness。

要求:

- preview 使用真实 UI 组件或候选真实组件;
- 数据使用静态 fixture,不得读取真实 backend service;
- 不触发 Lark、Lexware、Redis、Resend、billing、payment、email、ERP mutation 或生产数据副作用;
- dev-only route 必须有 production guard;
- fixture 数据必须可识别为 fake/test data;
- 先做自检:首屏是否看得懂、窄屏是否可读、primary action 是否清楚、action 去向是否明确、有没有明显布局问题。

这一阶段的目标不是交付真实页面,而是快速暴露 UI 语义和布局风险。

### 3. Preview 中打造目标形态

在 preview / harness 中把页面打造成目标形态。

要求:

- preview 只负责组合和喂 fixture 数据;
- 真正的布局、组件、row/card 语法尽量沉到真实组件或 shared primitive;
- 不要让 preview 变成一次性假页面;
- 每次重要调整都用 desktop + constrained viewport 截图或 DOM geometry 验证;
- 截图暴露的 density、overflow、clipping、action 不清楚、disabled 容易误解等问题写入 findings。
- 人工 review 形成的业务优先级、CTA 承载方式和 Phase B 边界必须通过 `kaispan-ui-module-contracts` 写入对应 Module Contract。

到这一步,UI 设计迁移的形态基本定型,但还不能视为真实业务交付。

### 4. 真实页面吸收

将 preview 中验证过的结构接回真实业务 route。

注意:这不是单纯“接真实数据”。必须保留并验证真实业务边界:

- auth / permission boundary;
- dictionary / i18n wiring;
- Server Action 和 Route Handler 边界;
- data loading 和 service contract;
- external mutation availability;
- 已有 lifecycle action 的可用性规则。

布局重构不得扩大真实 mutation 范围,不得把 disabled 能力伪装成可用。新增或调整 shared primitive 时,更新项目的 component inventory。

### 5. 证据、发现与 Gate

完成 preview 或真实页面吸收后,按变更类型做验证:

- typecheck;
- focused tests;
- 必要 build;
- browser evidence:desktop + constrained viewport;
- i18n audit;
- 对外部集成、金钱、开票、邮件、ERP mutation 等能力,默认不跑真实 mutation smoke,除非用户明确批准。

状态回写由 `dev-with-track` 控制:

- `process.md`:当前 phase、gate 状态、验证结果、下一步;
- `findings.md`:截图 / 测试 / review 暴露的问题、风险、候选后续动作;
- `gate.md` 或 evidence README:scope、data safety、UI evidence、real route safety、verification、manual review、follow-up。

早期设计迁移阶段不要急着发布 issue。若 finding 还停留在“截图暴露的问题”“人工 review 待判断项”“可能在真实页面吸收时顺手处理”的粒度,先保留在 findings / gate checklist。只有当它具备清晰 scope、验收条件和执行边界时,才升级为 issue。

## 三条红线(其余都交给上面的文档)

1. **prototype 是输入,真实 App 是 source of truth。** 不逐像素复刻 HTML;截图 + 业务语义对齐优先。
2. **钱 / 外部副作用没接通 = disabled,不伪装成已实现。** 金额需 Decimal/币种/provenance/审计;Lexware 等真实 mutation 边界不为布局重构搬动。
3. **committed 证据不含客户数据 / 密钥 / IBAN / token。**

## 想新增 skill 时(沉淀,不要预判)

只有当某个流程**手工跑过 2~3 次、每次重复同样的痛、且可泛化**,才用 `skill-creator` 抽成 skill;平时用 `continuous-learning` 收集提案、由用户审批。不要为“将来可能用到”提前扩展治理层。
