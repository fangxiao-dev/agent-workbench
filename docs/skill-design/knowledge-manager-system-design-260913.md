# Knowledge Manager 系统设计

## 状态

- 日期：2026-09-13。
- 状态：已批准进入实现。
- 对外入口固定为三个：`learn-lessons`、`/impl-package:backfill-stable-docs`、`knowledge-manager`。
- `retro` 不是 Skill、alias 或独立入口；它只是 `knowledge-manager` 的内部 environment lane。

## 参考来源

- [Matt Pocock 的原始 `retro` Skill](https://github.com/mattpocock/skills/blob/main/skills/in-progress/retro/SKILL.md)：只吸收其 session retrospective 的观察维度，不复制其仓库结构、入口或 owner 假设。

## 用户模型

用户只需要根据期望的吸收范围选择入口：

| 入口 | 负责的问题 | 写入边界 |
| --- | --- | --- |
| `learn-lessons` | 未来 Agent 需要记住哪些实现、集成、验证、迁移或排障经验？ | hands-on knowledge 文档 |
| `/impl-package:backfill-stable-docs` | 哪些已确认的产品、架构、模块或行为语义应回刷到长期合同？ | stable product/architecture/behavior docs |
| `knowledge-manager` | 一次已完成工作同时带来了哪些 hands-on、stable semantics 和环境改进？ | 调度两条知识 lane；统一消费和写入；环境 lane 只报告 |

单 lane 入口仍可独立运行。`knowledge-manager` 是一键联动入口，不创建第四个可见入口，也不要求用户记住内部 lane 名称。

## 内部拓扑

```text
已完成工作 / 当前会话 / 用户指定来源
                    │
            knowledge-manager
          固定一次 Source Snapshot
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
 learn-lessons  backfill-stable-docs  environment retrospective
 只读 hands-on    只读 stable semantics   Manager 内部七类扫描
        └───────────┼───────────┘
                    ▼
          Manager 统一去重、裁决、写入、验证
```

三条 lane 的职责不同：

1. `learn-lessons` 和 `/impl-package:backfill-stable-docs` 是两个 peer audit。Manager 通过 `$dispatcher` 同时派发 `audit-only` 审计，不把 Manager 的 apply 授权传给 worker；知识分类、证据、写作和 metadata 规则仍由各自 Skill 拥有。
2. Environment retrospective 在 Manager 内部运行，不新增 sub-skill、reference、manifest、registry、sidecar 或候选队列。它只发现环境改进建议，不直接修改代码、指令、检查、工具或权限。
3. Manager 是唯一的结果消费与文档写入者。Worker 只返回候选和证据，不写仓库文档，也不改变业务状态。

## Source Snapshot 与输入

Manager 在任何 lane 开始前建立一次不可变的 Source Snapshot，至少记录：

- 来源范围及其类型；
- 仓库路径、当前指令与文档治理入口；
- branch、Source HEAD 和 working-tree dirty 状态；
- 当前代码、测试与 canonical docs 的证据位置；
- 可读取的 session/conversation/thread reference（如有）。

同一 Snapshot 传给两个 peer audit，避免各自重新猜测范围或把未提交改动误认为稳定事实。Snapshot 是本轮运行上下文，不是要写入仓库的新状态源。

Session 输入按以下优先级复用已有引用：

1. 当前宿主已提供的 conversation/thread reference；
2. 用户明确提供的 transcript、文件或链接；
3. 无可读取来源时，将 environment lane 标为 `source-insufficient`，继续运行有足够来源的知识 lane。

不得发明自定义 session ID、manifest、registry、sidecar、索引或指针格式，也不得因 environment 来源不可读而阻塞 hands-on/stable audit。

## Environment lane：七类观察维度

维度只用于发现摩擦，不预设最终修改位置；不要求每类都产生候选。

| 维度 | 观察问题 | 可能的干预 owner |
| --- | --- | --- |
| Navigation | 为找到入口、owner、命令或 source of truth 做了可避免的搜索？ | canonical docs、entry map、context pointer |
| Automated checks | 能否由确定性检查更早发现末端才暴露的问题？ | tests、lint、typecheck、验证脚本或 CI |
| Coding standards | review/实现是否反复漏掉同类质量、安全或维护性模式？ | 对应 leaf reviewer、review topology/caller 或标准文档 |
| Instruction placement | 规则是否重复、过期、放错层级或给 Agent 增加不必要负担？ | `AGENTS.md`、Skill 或按需 reference owner |
| Tool economy | 是否重复调用、输出过量、低价值轮询或选择了昂贵工具路径？ | command、adapter、MCP 或工具模块 owner |
| No-ops | 操作是否没有改变结果，只是一次偶发摩擦或已有覆盖？ | `no-delta`，不制造永久规则 |
| Information access | 是否缺少日志、状态、诊断命令或最小只读观察入口？ | observability、diagnostic 或基础设施 owner |

Environment lane 采用最小充分原则：不能为了覆盖七类而制造候选；一次命令拼写错误、偶发网络失败、已经被现有机制完整覆盖或只有“提醒 Agent 更小心”的建议，直接进入 `no-delta`。

## 三路 reconciliation

每个候选先回答同一个问题：**未来 Agent 必须知道这件事，还是环境可以让 Agent 不必再遇到它？** Manager 在合并两个 peer audit 与 environment scan 后按行动形态裁决：

| 事实/行动形态 | 唯一主归属 |
| --- | --- |
| 经当前代码、测试或 canonical owner 文档确认的非显然 implementation/integration/verification/migration/debug/recovery 经验 | `learn-lessons` |
| 稳定的 product/system/module/context 语义、behavior contract 或 canonical vocabulary | `/impl-package:backfill-stable-docs` |
| 可由检查、工具、信息入口、导航或指令布局机械消除的摩擦 | environment recommendation |
| 检查能发现症状，但恢复仍依赖非显然实践知识 | 拆分为 environment recommendation + 独立 hands-on lesson；不能重复写同一事实 |
| 发现与现有文档/检查/工具完全覆盖，或只有偶发低价值摩擦 | `already-covered` 或 `no-delta` |
| 有具体证据和推荐干预，但无法确定责任 owner | 独立 `owner-gap`，不是建议候选 |
| 当前证据冲突或不足以确认长期事实 | `conflict` 或 `source-insufficient`，停写并报告 |

“建议候选”必须同时具备具体证据、可观察的干预、明确 owner，以及足以覆盖维护成本的预期收益。`owner-gap` 保留证据和推荐干预，但不冒充已完成路由；它是独立结果桶，不能被完成条件误读为必须钉死 owner 的普通候选。

稳定语义不复制到 hands-on 文档；hands-on lesson 不承担产品或模块长期合同。目标 Skill 的既有耐久性、source-of-truth、metadata、audit/apply/verify 规则继续有效，Manager 不复制或削弱它们。

## 执行与授权

### 默认流程

1. 选择来源并建立 Source Snapshot。
2. 读取两个 peer Skill；有相应来源时通过 `$dispatcher` 并行派发只读 audit；宿主没有 subagent 能力时，由主线程顺序完成相同的只读审计。
3. Manager 在同一范围内运行 environment 的七类扫描；不可读取 session 时只标记该 lane 的 `source-insufficient`。
4. 主线程消费所有返回，按 source of truth、未来检索问题、行动形态和维护成本去重、分流、排序。
5. 在被授权范围内应用两条知识 lane 的非破坏性文档更新；environment recommendation 只进入报告。
6. 独立检查最终 diff、路径、链接、metadata、来源引用与最小验证，并汇总三条 lane 结果。

### 授权边界

- 显式调用 `knowledge-manager` 授权本轮两条知识 lane 的非破坏性文档创建或更新。
- Environment lane 默认 report-only；它不因发现候选而获得代码、测试、CI、工具、权限、指令或宿主状态的写权限。
- `audit-only` 使三条 lane 全部只读，不应用文档变更。
- 删除、移动、重命名、retirement、package 状态修改、代码/CI/工具/权限变更、用户级宿主状态修改和外部系统发布都需要独立明确授权。
- 冲突项停写并交给 Owner；不以代码猜意图，也不以旧设计覆盖当前事实。无关且证据充分的候选可继续处理。

## 输出合同

先给出总量与独立 pending：来源数、发现数、建议候选、已应用、已有覆盖、`no-delta`、`source-insufficient`、`owner-gap`、`conflict` 和仍待 Owner 决定数。

随后按 lane 报告：

- `learn-lessons`：是否运行、hands-on 候选、应用/覆盖/不写原因、验证结果；
- `/impl-package:backfill-stable-docs`：是否运行、stable semantics 候选、其 audit/apply/verify 状态与冲突；
- environment：七类扫描覆盖情况、建议干预、owner-gap 和明确的 report-only 状态。

每个建议候选至少包含 ID、来源维度、具体症状、证据与不确定性、推荐干预、预期效果、owner、影响/维护成本和优先级。最后列出跨 lane 去重、被拒绝候选及原因、修改文件和验证结果。三条 lane 都没有 durable delta 时正常返回 `no-delta`，不制造文档。

## 非目标

- 不新增独立 `retro` Skill、alias、manifest、registry、候选队列或常驻状态源。
- 不把 session 时间线、Agent 表现评价或普通任务状态变成长期知识。
- 不把稳定产品/系统语义写进 hands-on lesson，也不把偶发摩擦升级为永久环境规则。
- 不做全仓库 setup 审计；来源和读取范围由本轮 Snapshot 限定。
- 不替代两个 peer Skill 自己的耐久性、授权、验证或 package 生命周期合同。

## 验收场景

实现必须能通过以下场景：

1. 用户显式调用 `$knowledge-manager`，混合来源同时触发两个只读 peer audit，Manager 是唯一写者并报告三条 lane。
2. 只有实现验证捷径来源时运行 `learn-lessons`，稳定语义 lane 标为无候选；只有稳定合同来源时反之。
3. 同一稳定行为同时被两个 peer 发现时只保留 stable-docs 归属；额外的非显然实现陷阱才拆到 hands-on。
4. 类型错误可被提前检查发现时生成 environment recommendation，不增加泛化提醒。
5. Navigation、Coding standards、Instruction placement、Tool economy、Information access 各自能产生对应 owner 路由；No-ops 进入 `no-delta`。
6. Session 不可读取时 environment 为 `source-insufficient`，两个知识 lane 仍可按现有来源运行；不创建自定义指针。
7. 候选有证据和干预但无明确 owner 时进入独立 `owner-gap`，不计入建议候选。
8. `audit-only` 下三条 lane 都只读；默认 environment 只报告，不写代码、Skill、检查或宿主状态。
9. 当前证据与 Decision/Spec 冲突时停止该候选语义写入，保留证据并列出 Owner 决策；其他独立候选仍可完成。
10. 没有合格候选时以零候选、`no-delta` 正常完成。

## 完成条件

- 三个对外入口和三条内部 lane 的边界、授权与输出可被静态和行为测试验证。
- Source Snapshot 只建立一次；两个 peer audit 共享它；不可读取 session 不阻塞其他可行 lane。
- environment 七类扫描均可产生、合并或拒绝候选，但不要求每类都产生结果。
- 每个普通建议候选有具体证据、干预和 owner；`owner-gap` 为独立桶，不要求 owner 已确定。
- Manager 是唯一文档写者；environment recommendation 默认只报告；`audit-only` 全部只读。
- `no-delta`、`source-insufficient` 和 `conflict` 都是正常可报告结果，不被误报为整体失败。
- 不创建独立 Retro 入口，不扩大读取范围，不改变两个 peer Skill 的现有耐久性合同。
