# KaiSpan Preview Harness UI 迁移补充

状态：已提升为通用流程的领域补充
创建：2026-06-26
用途：记录 KaiSpan / Supplier Admin / finance billing 语境下，使用 `dev-with-track` 执行 UI 迁移时需要保留的领域判断。

> 通用执行控制已提升到 `dev-with-track` skill：preview / screenshot harness、fixture-only migration、process/findings/gate、Phase A/B、evidence 闭环均以 `dev-with-track` 为准。本文只保留 KaiSpan 相关语义和红线补充。

## 背景

老板 prototype、业务截图、文字语义和真实 App 往往不是同一种材料：

- prototype 提供设计意图和业务视觉方向。
- 真实 App 承载 auth、i18n、Server Action、data loading、external mutation availability 等工程边界。
- 直接在真实页面上改，反馈慢，且容易把 layout 改造和业务副作用混在一起。

因此采用 preview / screenshot harness 作为中间层：用真实 UI 组件 + 静态 fixture 数据，先验证页面语义和布局语法，再安全吸收到真实业务页面。

## 设计迁移流程

### 1. 页面抽取与预完善

从真实业务页面抽出可预览的 UI surface，建立 dev-only preview / screenshot harness。

要求：

- preview 使用真实 UI 组件或候选真实组件。
- 数据使用静态 fixture，不读取真实 backend service。
- 不触发 Lark、Lexware、Redis、Resend、付款、开票、邮件等外部副作用。
- dev-only route 必须有 production guard。
- 先做自检：首屏是否看得懂、窄屏是否可读、primary action 是否清楚、action 去向是否明确、有没有明显布局问题。

这一阶段的目标不是交付真实页面，而是快速暴露 UI 语义和布局风险。

### 2. 语义对齐

用户提供老板 prototype 截图和业务语义。对齐重点不是逐像素复刻，而是确认：

- 页面有哪些子模块。
- 哪些信息第一眼必须可见。
- 哪个是 primary action，哪些是 secondary action。
- action 应该进入列表、drawer、dialog、detail page，还是 disabled placeholder。
- 哪些真实能力尚未接通，必须 disabled，不能伪装成已实现。

语义对齐完成后，再进入具体页面打造。

### 3. 页面打造

在 preview / harness 中把页面打造成目标形态。

要求：

- preview 只负责组合和喂 fixture 数据。
- 真正的布局、组件、row/card 语法尽量沉到真实组件或 shared primitive。
- 避免让 preview 变成一次性假页面。
- 每次重要调整都用 desktop + constrained viewport 截图或 DOM geometry 验证。

到这一步，UI 设计迁移的形态基本定型，但还不能视为真实业务交付。

### 4. 真实页面吸收

将 preview 中验证过的结构接回真实业务 route。

注意：这不是单纯“接真实数据”。必须保留并验证真实业务边界：

- auth / permission boundary。
- dictionary / i18n wiring。
- Server Action 和 Route Handler 边界。
- data loading 和 service contract。
- external mutation availability。
- 已有 lifecycle action 的可用性规则。

布局重构不得扩大真实 mutation 范围，不得把 disabled 能力伪装成可用。

### 5. 验证与关 Gate

完成真实页面吸收后，按变更类型做验证：

- typecheck。
- focused tests。
- 必要 build。
- real route browser evidence：desktop + constrained viewport。
- i18n audit。
- 对外部集成、金钱、开票、邮件等能力，默认不跑真实 mutation smoke，除非用户明确批准。

截图、验证结果和发现必须回写到 process / findings。满足 gate 后，才进入下一页或下一阶段。

## 轻量控制流程

本流程借鉴 WT-style process tracking，但不引入完整 WT-PM 的任务表、分支合并、DONE 状态机。

核心文件分工：

- `roadmap`：定义总路径、phase、gate、红线。
- `process.md`：记录当前走到哪、gate 哪些已满足、下一步是什么。
- `findings.md`：记录过程中发现的问题、判断、候选后续动作。
- `gate document`：用一个可外链的 gate / checklist 文档承接阶段验收、待判断项和后续候选动作。
- `issue / PR`：只在 finding 已经拆到可直接执行的任务边界后再使用；不作为早期设计迁移的默认载体。

### 1. 从 Roadmap 进入

每次开工先看 roadmap：

- 当前 phase 是什么。
- 本 phase 的目标是什么。
- 本 phase 的 gate 是什么。
- 当前问题属于 preview、真实页面吸收，还是 backlog。

不要直接“看见问题就改”。先判断问题属于哪个阶段。

### 2. 从 Process 恢复现场

`process.md` 是状态入口。它回答：

- 当前在哪个 phase。
- 上次做到哪。
- 哪些 gate 已过。
- 哪些验证还没跑。
- 下一步推荐做什么。

如果聊天上下文丢失，应优先从 `process.md` 恢复，而不是依赖记忆。

### 3. 用 Preview / Harness 低成本迭代

Phase A 或设计迁移阶段先在 preview 里抽真实组件、喂 fixture、截图。

目标：

- 快速暴露布局语义问题。
- 降低登录、数据、外部服务、副作用带来的噪音。
- 让用户能拿截图与老板确认。

### 4. 发现写入 Findings

截图、测试、人工 review 暴露的问题必须写入 `findings.md`。

典型 finding：

- 某个 action column 在 desktop 下过窄。
- 某个表格在 390px 下不可读。
- 某个子模块的 primary action 不明确。
- 某个 disabled 能力容易被误解为已实现。

如果 finding 已经足够可执行，再考虑转成 issue / PR。

早期设计迁移阶段不要急着发布 issue。若 finding 还停留在“截图暴露的问题”“老板 review 待判断项”“可能在真实页面吸收时顺手处理”的粒度，先保留在 `findings.md`，并在 gate document 中外链它。只有当它具备清晰 scope、验收条件和执行边界时，才升级为 issue。

### 5. 用 Phase Gate 控制前进

不以“看起来差不多”进入下一阶段。

Phase gate 应回答：

- 目标 surface 是否覆盖到位。
- screenshot / evidence 是否存在。
- fixture 是否没有真实副作用。
- 发现是否记录到 findings,并被 gate document 外链。
- 自动验证是否通过或明确阻塞。
- 是否需要人工 review。

只有 gate 满足，才允许进入下一 phase。

### 6. 用 Gate Document 控制关闭

Roadmap gate 管阶段规则，gate document 管当前阶段的实际关闭证据和待判断项。

gate document 至少回答：

- Scope：目标 route / component / surface 是什么。
- Data safety：是否无生产数据和外部 mutation。
- UI evidence：是否有 desktop + constrained evidence。
- Real route safety：auth、Server Action、i18n、mutation availability 是否保持。
- Shared UI：是否更新 component inventory。
- Verification：是否跑过最小验证命令。
- Follow-up：风险是否记录到 findings / gate checklist,并标明先修、Phase B 处理或 backlog。

若某个 follow-up 已经变成可执行任务，再从 gate document 链到 issue / PR；在此之前不强制发布 GitHub issue。

### 7. 人工输入只放在关键点

用户不需要参与每次代码细节。

需要用户输入的关键点：

- 老板 prototype 截图和业务语义。
- preview 截图是否“第一眼看得懂”。
- 是否允许从 preview / Phase A 进入真实页面吸收 / Phase B。
- 某个真实页面吸收后是否符合老板预期。
- 涉及外部 mutation、金钱、开票、邮件等能力时是否批准真实 smoke。

### 8. 回写状态

每轮工作结束后：

- `process.md` 更新当前 phase、gate 状态、下一步。
- `findings.md` 更新新发现、风险、候选后续动作。
- gate document 更新阶段验收、人工判断项和外链 evidence。
- `roadmap` 只在阶段规则、gate、红线变化时更新，不写流水账。
- issue / PR 只在任务边界已经足够清晰时记录具体 Done Gate 和验证结果。

## 建议的 Phase 结构

### Phase A — Preview / 截图对齐

目标：用 fixture-only preview 验证页面语义和布局方向。

完成条件示例：

- 关键 surface 有 desktop + constrained viewport 截图。
- evidence README 或 checklist 记录截图判断。
- fixture route 无真实 backend 读取和外部副作用。
- 截图暴露的问题已进入 findings,并被 gate document 外链。
- typecheck / focused tests / 必要验证通过或记录阻塞。
- 用户确认方向可进入真实页面吸收。

### Phase B — 真实页面吸收

目标：把 preview 验证过的布局语法吸收到真实 route。

完成条件示例：

- 真实页面使用确认过的 Overview-first / action surface / detail page 语法。
- auth、i18n、Server Action、data loading、mutation availability 保持不变或变更被明确批准。
- 真实 route 有 browser evidence。
- shared primitive 和 component inventory 更新。
- focused tests、typecheck、必要 build 通过或记录阻塞。

## 红线

- prototype 是输入，真实 App 是 source of truth。
- preview / fixture 不得进入生产路径。
- 金钱、开票、付款、邮件、Lexware 等外部副作用未接通时必须 disabled，不伪装成已实现。
- committed evidence 不含客户数据、密钥、IBAN、token。
- 不用聊天记忆替代 process / findings。

## 什么时候考虑正式引用

只有当该流程在 2~3 个真实页面或项目中稳定跑通，并且每次都重复使用同样的 process / findings / gate 结构时，才考虑：

- 从 `kaispan-ui-design/SKILL.md` 引用本文。
- 或抽成更正式的子 skill。
- 或将通用部分提升为跨项目 UI design migration skill。
