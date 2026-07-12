# DAG 与 Ownership

画任务图和分配文件 ownership 时读本文件。Composition、acceptance target 语法、seam 的三类 owner、no-DAG seam 限制与关闭 gate 均以 `skills/impl-package/references/impl-package-composition-contract.md` 为准；本 reference 只定义 DAG 的执行分解记录方式。

## 任务记录

每个任务都要具体到无需再做决策即可派发：

```markdown
### T<n>: <名称>
- Depends on:
- Can run with:
- Primary owned files/modules:
- Conditional seam files/modules:
- Forbidden files/modules:
- Input contract:
- Output contract:
- contributes-to: <acceptance-target>[, ...]
- enables: <acceptance-target>[, ...] # 仅基础设施任务；不可与空的消费方并存
- seam: none | <seam-id>
- seam execution owner: <main session | named owner>
- Focused tests:
- Done when:
```

每个任务必须使用 `contributes-to` 或 `enables` 至少一个 acceptance target；task 不是 ticket 的子项。只为基础设施工作使用 `enables`，并指向消费其证据的最终 AC。只有 `seam: none` 时可省略 seam execution owner；其余格式、target 解析和 seam 的 contract/acceptance owner 由共享 contract 校验。

`<acceptance-target>` 必须使用共享 grammar：`ticket-id:AC-id | spec:AC-id`。有 tickets 时使用前者；`tickets=false, dag=true` 时使用后者。不要在 DAG 中发明 ticket、AC 或另一套 target 语法。

存在 `dev-with-track` workspace 时，把这些字段镜像进 `dag.md` 的 `Task Contracts`。只为有持久局部状态的任务创建 `tasks/Tn-progress.md`：独立 owner/subagent、外部 gate 证据、blocker、review finding 或跨 session 继续。

## 任务编号续编

落入已有 implementation package-id 时，任务编号从该 package-id 的最高 `T<number>` 之后继续。画图前检查 `dag.md`、根目录 `*.patch-dag.md`、`tasks/T*-progress.md`、`tasks/T*-handoff.md`、`plan.md` 和根目录 `*.patch-plan.md`。不复用、不重排已有编号。

旧 `dag.md` 已标记 `Retired / terminal gate` 时，把新任务图写入新的 `YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`（见 `dev-with-track` 的 patch 模式），不要把新任务追加进已 retired 的旧 DAG。

## Ownership 规则

- DAG ownership map 是 worker prompt 的唯一事实来源。派发时不要手动收窄或放宽 ownership，除非同时更新 DAG。
- **Primary owned files/modules**：worker 的正常写入范围。
- **Conditional seam files/modules**：仅在点名的 seam 条件发生时可改。worker 必须上报条件和实际改动的文件。
- **Forbidden files/modules**：禁改。需要时 worker 返回 `NEEDS_SEAM` 并写明所需的精确改动。
- 共享 seam 文件归 main session，除非 DAG 中明确指派了 seam execution owner。
- 两个 worker 不应写同一个组件、词典块、生成产物、本地数据存储、dev server 端口或外部 smoke 记录。
- 横向前置任务必须以 `contributes-to` 或 `enables` 点名受影响 acceptance target；横向 worker 完成不代表任何 ticket 已验收。

## Seam 状态

用状态标签区分预期内的集成工作和真正的阻塞：

- `DONE`：主体工作和聚焦测试完成。
- `DONE_WITH_CONCERNS`：工作完成，但 worker 上报了 main session 在 review 前必须读的风险。
- `NEEDS_SEAM`：worker 需要另一任务或 main session 所属的改动；不需要人类决策。
- `BLOCKED`：缺上下文、缺权限、数据不可用、计划需要修正或需要人类决策。

可预见的 seam 在派发前就记入 DAG。执行中，更广的测试只因另一个计划内任务未落地而失败时，标 `NEEDS_SEAM` 而不是 `BLOCKED`。seam 是否可关闭、哪些 acceptance target 受其约束，均按共享 contract 处理。

### Worker 返回状态与 DAG 板状态的映射

Worker 返回与可释放 DAG 状态的映射、`Depends on` 的 readiness 判定，以及返工后的 `NEEDS-REVALIDATION` 传播，全部引用 shared contract 第 4 节。不要把 worker `DONE`、`Integrated` 或 `Verified local` 文案本身当作未验证的依赖释放；只有 shared contract 定义的 dependency-releasing DAG 状态才允许其 dependent 开始。

## 常见任务形状

- **数据/来源/就绪 worker**：拥有一个契约的 service/types/source/就绪测试；不碰 UI。
- **Read-model worker**：拥有派生展示数据的 source/service/types/测试；除约定的 prop seam 外不碰面板实现。
- **UI worker**：拥有组件/面板和组件测试；消费冻结的 DTO；不碰 source 内部。
- **i18n worker 或 reviewer**：拥有指定词典 namespace 或约定 key 的语义 review；新 key 通过 main session 协调。
- **Seam execution owner**：通常是 main session；拥有 route/page prop 接线、共享导出、中央词典合并和最终冲突解决。
- **外部 smoke worker**：在本地/浏览器 gate 通过并确认目标身份之后运行。

## Cohort 模式

用 cohort 最大化并行而不隐藏依赖：

1. **契约 cohort**：数据/来源/就绪、read model 和只依赖冻结契约的独立清理任务。
2. **UI/i18n cohort**：DTO/文案形状足够稳定后的 UI 骨架和文案工作。
3. **集成 cohort**：main session 解决 seam 文件并跑 integration 测试。
4. **外部 cohort**：本地证据之后的浏览器验证和外部 smoke。
5. **Implementation review**：调用 `module-review` 的 Spec 轴，并提供固定的 commit 或 diff comparison point。

## 示例：跨 ticket seam

```markdown
### T12: 冻结共享展示 DTO
- Depends on: none
- Can run with: T13
- Primary owned files/modules: service/types/contract tests
- Conditional seam files/modules: none
- Forbidden files/modules: UI implementation
- Input contract: approved plan contract
- Output contract: stable display DTO
- contributes-to: catalog-readiness:AC-1
- seam: none
- Focused tests: contract tests
- Done when: DTO and focused tests are ready for consumers

### T13: 实现消费 DTO 的面板
- Depends on: T12
- Can run with: T14
- Primary owned files/modules: panel and component tests
- Conditional seam files/modules: locale namespace when assigned
- Forbidden files/modules: source internals
- Input contract: T12 display DTO
- Output contract: rendered panel behavior
- contributes-to: catalog-readiness:AC-2
- seam: catalog-panel-wiring
- seam execution owner: main session
- Focused tests: component tests
- Done when: panel behavior and evidence are ready

### T14: 集成 route 与共享 exports
- Depends on: T12, T13
- Can run with: none
- Primary owned files/modules: route wiring and shared exports
- Conditional seam files/modules: central locale merge
- Forbidden files/modules: worker-owned source internals
- Input contract: T12/T13 outputs and spec seam contract
- Output contract: integrated entry point
- enables: catalog-readiness:AC-2
- seam: catalog-panel-wiring
- seam execution owner: main session
- Focused tests: integration route test
- Done when: seam evidence is available to the acceptance owner
```
