# DAG 与 Ownership

画任务图和分配文件 ownership 时读本文件。

## 任务记录

每个任务都要具体到无需再做决策即可派发：

```markdown
### Task <ID>: <名称>
- Depends on:
- Can run with:
- Primary owned files/modules:
- Conditional seam files/modules:
- Forbidden files/modules:
- Input contract:
- Output contract:
- Focused tests:
- Done when:
```

存在 `dev-with-track` workspace 时，把这些字段镜像进 `dag.md` 的
`Task Contracts`。只为有持久局部状态的任务创建 `tasks/Tn-progress.md`：
独立 owner/subagent、外部 gate 证据、blocker、review finding 或跨 session
继续。

## 任务编号续编

落入已有 implementation slug 时，任务编号从该 slug 的最高 `T<number>` 之后
继续。画图前检查 `dag.md`、根目录 `*.patch-dag.md`、`tasks/T*-progress.md`、
`tasks/T*-handoff.md`、`plan.md` 和根目录 `*.patch-plan.md`。不复用、不重排
已有编号。

旧 `dag.md` 已标记 `Retired / gate passed` 时，把新任务图写入新的
`YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`（见 `dev-with-track` 的 patch
模式），不要把新任务追加进已 retired 的旧 DAG。

## Ownership 规则

- DAG ownership map 是 worker prompt 的唯一事实来源。派发时不要手动收窄或
  放宽 ownership，除非同时更新 DAG。
- **Primary owned files/modules**：worker 的正常写入范围。
- **Conditional seam files/modules**：仅在点名的 seam 条件发生时可改。
  worker 必须上报条件和实际改动的文件。
- **Forbidden files/modules**：禁改。需要时 worker 返回 `NEEDS_SEAM` 并
  写明所需的精确改动。
- 共享 seam 文件归 main session，除非明确指派了一个 seam worker。
- 两个 worker 不应写同一个组件、词典块、生成产物、本地数据存储、dev
  server 端口或外部 smoke 记录。
- 横向前置任务要记录哪些 vertical slice gate 消费它。不要凭横向 worker
  单独完成就把 slice 标为已验收。

## Seam 状态

用状态标签区分预期内的集成工作和真正的阻塞：

- `DONE`：主体工作和聚焦测试完成。
- `DONE_WITH_CONCERNS`：工作完成，但 worker 上报了 main session 在 review
  前必须读的风险。
- `NEEDS_SEAM`：worker 需要另一任务或 main session 所属的改动；不需要人类
  决策。
- `BLOCKED`：缺上下文、缺权限、数据不可用、计划需要修正或需要人类决策。

可预见的 seam 在派发前就记入 DAG。执行中，更广的测试只因另一个计划内任务
未落地而失败时，标 `Needs seam` 而不是 `Blocked`。

### Worker 返回状态与 DAG 板状态的映射

| Worker 返回 | DAG 板状态 |
| --- | --- |
| `DONE` | seam 合并后 `Integrated`；本地验证即任务终态时 `Verified local` |
| `DONE_WITH_CONCERNS` | 保持 `Running`，concern 处理或 review 后再推进 |
| `NEEDS_SEAM` | `Needs seam` |
| `BLOCKED` | `Blocked` |

## 常见任务形状

- **数据/来源/就绪 worker**：拥有一个契约的 service/types/source/就绪
  测试；不碰 UI。
- **Read-model worker**：拥有派生展示数据的 source/service/types/测试；
  除约定的 prop seam 外不碰面板实现。
- **UI worker**：拥有组件/面板和组件测试；消费冻结的 DTO；不碰 source
  内部。
- **i18n worker 或 reviewer**：拥有指定词典 namespace 或约定 key 的语义
  review；新 key 通过 main session 协调。
- **Seam owner**：通常是 main session；拥有 route/page prop 接线、共享
  导出、中央词典合并和最终冲突解决。
- **外部 smoke worker**：在本地/浏览器 gate 通过并确认目标身份之后运行。

## Cohort 模式

用 cohort 最大化并行而不隐藏依赖：

1. **契约 cohort**：数据/来源/就绪、read model 和只依赖冻结契约的独立
   清理任务。
2. **UI/i18n cohort**：DTO/文案形状足够稳定后的 UI 骨架和文案工作。
3. **集成 cohort**：main session 解决 seam 文件并跑 slice 级测试。
4. **外部 cohort**：本地证据之后的浏览器验证和外部 smoke。
5. **最终 review cohort**：对集成结果做 whole-slice review。

## 示例：一个列表增强 Slice

```markdown
Task A: 核心实体阈值 数据/来源/就绪
- Primary owned files/modules: 该实体的 types/service/source/就绪测试。
- Conditional seam files/modules: none。
- Forbidden files/modules: 全部 UI。

Task B: 相邻实体 read model + UI 清理
- Primary owned files/modules: 相邻实体的 service/types/面板/测试。
- Conditional seam files/modules: 共享 read-model 类型，仅当 DAG 把该 seam
  指派给本任务。
- Forbidden files/modules: 核心实体的紧凑 UI。

Task C: 派生数据 0-N source/read model
- Primary owned files/modules: 派生配置的 source/service/types/测试。
- Conditional seam files/modules: none。
- Forbidden files/modules: UI 实现。
- 产出冻结的展示 DTO 契约。

Task D: 紧凑 UI 骨架
- Primary owned files/modules: 列表面板和测试。
- Conditional seam files/modules: 词典 namespace，仅当 UI 文案 key 指派在此。
- Forbidden files/modules: source 内部。
- 消费 A/C 冻结的 DTO。

Task E: i18n 文案 pass/review
- Primary owned files/modules: 指派的词典 namespace。
- Conditional seam files/modules: UI 测试，仅当文案改动需要更新断言。
- Forbidden files/modules: service/source 内部。
- 新 key 经 main session 与 UI worker 协调。

Task F: 外部系统就绪/smoke
- Depends on: 本地测试和浏览器证据。
- 只 mutate 已确认的测试环境目标。

Final: whole-slice review
- 检查跨模块一致性、缺失验收项、测试缺口和外部 smoke 风险。
```
