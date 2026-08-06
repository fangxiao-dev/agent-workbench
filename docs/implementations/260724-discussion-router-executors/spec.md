# 讨论路由与通用模型执行器规格

状态（Status）：Spec Gate Passed
创建时间（Created）：2026-07-24
决策修订（Decision Revision）：D1
规格修订（Spec Revision）：S3
需求来源（Requirement source）：用户确认的 Blind Opening、Discuss Ledger 与通用 executor 设计
主题 slug（Topic slug）：discussion-router-executors
任务包 ID（Package ID）：260724-discussion-router-executors
规范任务包路径（Canonical package）：`docs/implementations/260724-discussion-router-executors/`
决策（Decision）：[decision.md](decision.md)

## Decision 门记录（Decision Gate Record）

- 结果（Result）：PASSED
- 目标落点与预期结果：提供可独立使用的 Blind Opening，并可选择性地将其结果交给现有 Ledger 收敛；提供可复用的 Codex/Claude executor。
- 权威来源 / 当前状态证据：`decision.md` 第 3 节及项目级 `discuss-ledger-orchestrator-mcp.md`。
- 选定方向与理由：三模式 Router 保持成熟 Ledger 隔离；executor 从业务 prompt 和角色策略中解耦。
- Blocking-uncertainty triage / 开放问题处理结果：无阻塞项；输出适配细节由实现和测试验证。
- Owner 决策（已解决 / 未解决）：三项关键决策均已解决，无未解决项。
- 证据位置：decision.md
- 评估人 / 日期：Codex / 2026-07-24。

## Spec 门记录（Spec Gate Record）

- 结果（Result）：PASSED
- 八个章节完整：是。
- 验收证据已映射：是。
- 阻塞决策 / 歧义：无。
- 批准人 / 日期：用户 / 2026-07-24。

## 1. 范围 / 权威来源 / 非目标

- 范围：新增 `call-codex`、`call-claude`、Blind Opening 和 Discuss Ledger 的三模式 Router；将现有 orchestrator 的模型执行适配迁出到 executor。
- 权威来源与优先级：用户已确认的 Decision、当前 `discuss-ledger` 实现、根 `AGENTS.md`、已更新的项目级设计文档；冲突时以用户 Decision 为准。
- 非目标：改变 Ledger 状态机、通过 MCP 调模型、修改既有 MCP server、增加角色预设、重做 loop mode、在本次为未来调用方添加业务抽象。
- 需要确认的假设：Codex 与 Claude CLI 在当前环境可继续接受上游提供的 prompt 与结构化输出配置；若任一 CLI 不可用，executor 返回可诊断失败而不改变 Ledger。

## 2. 术语 / 数据合同

- 领域术语：Blind Opening 是各参与者互不可见的独立首轮；Ledger 是现有的争点、收敛和僵局状态机；Router 是选择编排模式的 `discuss-ledger` 入口；executor 是单一模型 CLI 的下游调用边界。
- 输入、输出、身份与不变量：Router 接收明确模式意图或询问歧义；Blind Opening 中每位 participant 仅接收原始目标、Blind Opening prompt 与输出 schema；正常 Ledger 接收当前 ledger；组合模式只将归并后的初始开放争点交给 Ledger。每次 executor 调用都启动一个短生命周期的新 CLI agent 进程；不得假定跨调用的 agent 会话、内存或 standing process，所需状态仅能由上游 prompt、结果工件或 ledger 显式传递。Blind Opening 的用户可见结果是 `%TEMP%/discuss-ledger/blind-<slug>-<run-id>.md`；同目录 JSON 仅供组合编排或诊断使用。
- Schema、归一化、精度与 ownership 语义：每个 executor 接收 cwd、prompt 或 prompt file、timeout 与调用方模型配置，输出统一 JSON envelope，最小含 `ok`、`status`、`text`、`usage`、`exit_code`、`error`。业务输出 schema 由调用者提供并由调用者验证；executor 不解释 Ledger 或 Blind Opening 的业务字段。
- 条件化 evidence-integrity 合同：不适用；本变更不发布外部权威证据或产生跨状态公共数据投影。

## 3. 行为 / 状态机 / 工作流

| Actor / 系统 | 条件 / 状态 | 动作 / 事件 | 结果 / 下一状态 |
| --- | --- | --- | --- |
| Router | 用户明确请求独立发散 | 选择 Blind Opening reference/workflow | 所有参与者独立执行；汇总结果后结束 |
| Router | 用户请求讨论/收敛或沿用既有触发 | 选择正常 Ledger | 调用原有 Ledger 工作流，语义保持不变 |
| Router | 用户请求先独立再收敛 | 先运行 Blind Opening | 归并独立发现为初始开放争点 |
| Combined workflow | 初始争点已建立 | 调用现有 Ledger orchestrator | 原有轮询、收敛、僵局与退出规则生效 |
| 上游 skill | 需要调用模型 | 调用 `call-codex` 或 `call-claude` | 收到统一 envelope，并按自身 schema/策略处理 |
| executor | CLI、认证、超时或输出解析失败 | 返回错误 envelope | 调用方获得可诊断失败，不将失败伪装为有效模型结果 |

## 4. 模块边界 / 依赖

- Owning 模块及其职责：`skills/call-codex/` 和 `skills/call-claude/` 分别拥有本模型 CLI 适配；`skills/discuss-ledger/` 拥有 Router、Blind Opening、Ledger prompt/状态机和组合 hand-off。
- Core 不变量与 Capability 暴露边界：executor 不持有 prompt 模板、role、默认权限策略或业务 schema；讨论 capability 明确提供这些配置。
- 接口与 seam：executor 以稳定的命令行输入与 JSON envelope 为 seam；Blind Opening 以独立结果/归并结果为 seam；组合模式以初始化后的 ledger 为 seam。
- 上游 / 下游依赖：Router 依赖其模式 references；Blind Opening 与 Ledger 依赖 executors；executors 依赖本机 Codex/Claude CLI。
- 兼容或迁移窗口：现有 `discuss_orchestrator.py` 保持 CLI 表面和 fake mode；其内部改为调用 executor 后，旧 adapter 逻辑不再重复维护。

## 5. 错误边界 / 失败恢复

| 失败模式 | 可观察影响 | 隔离方式 | 重试 / 补偿 / 恢复 | Owner |
| --- | --- | --- | --- | --- |
| 单一模型 CLI 不可用、认证失败或超时 | 该 participant 无有效结果 | executor 返回分类错误 envelope | 上游决定重试、缩小任务、换 participant 或停止 | 上游 skill |
| 模型输出不符合调用方 schema | 该回合不能写入有效结果 | executor 仅交付 text；调用方验证业务 schema | 沿用调用方现有修复/重试策略 | Blind Opening 或 Ledger |
| Blind Opening 归并失败 | 不进入 Ledger | 保留独立结果，报告归并失败 | 调用方修正归并后再初始化 Ledger | Router |
| Ledger 回归失败 | 正常讨论能力受影响 | 新能力不替代旧路径 | 修复 executor seam 或回退内部调用迁移 | Discuss Ledger owner |

## 6. 约束合同

- 禁止行为：Blind Opening 不得把任何参与者的结果传给另一参与者；组合模式不得修改 Ledger 的已有状态机规则；executor 不得注入业务 prompt 或 role。
- Trust 与 permission 边界：模型工具/写入权限完全由上游模型配置和 prompt 决定；executor 透明传递获支持的调用配置，不自行强加只读或可写默认值。
- 精度 / 归一化义务：executor 对其稳定 envelope 做严格 JSON 输出；模型文本与调用方 schema 不被 executor 语义改写。
- 外部 provider 义务：CLI 不存在、认证失败、非零退出或超时必须明确返回，不能静默降级。
- 负向依赖（不得依赖）：新机制不得依赖 MCP server、不得依赖 `call-grok` 的 role preset、不得要求编辑用户级 host 配置。

## 7. 验收语义 / 验证证据

| AC ID | 承诺结果 / 约束 | 证据 producer 或 manual owner | 通过证据 |
| --- | --- | --- | --- |
| AC-1 | 未指定 Blind Opening 时，现有 Ledger 入口和 fake smoke path 保持可用 | 自动化测试 | 既有 fake-mode 测试及新增回归测试通过 |
| AC-2 | Blind Opening 的所有 participant 在首轮互不可见 | 自动化测试 | fake executor 记录的 prompt 不含其他 participant 输出或 ledger 内容 |
| AC-3 | Blind Opening 可单独结束并产出可读的独立发现汇总 | 自动化测试 | fake-mode 输出含每位 participant 的结果与汇总 |
| AC-4 | 组合模式仅在首轮归并后调用原有 Ledger | 自动化测试 | 测试证明初始化争点后进入正常 orchestrator，且其状态机断言不变 |
| AC-5 | `call-codex` 与 `call-claude` 可接收上游 prompt/config 并在成功/失败时输出统一 envelope | 自动化测试 | adapter fixture 覆盖成功、非零退出、超时及解析失败 |
| AC-6 | executor 不定义 role、业务 prompt 或权限默认策略 | 代码审查与测试 | public help/reference 无 role 参数；调用参数由上游传递 |
| AC-7 | 新机制不改动或注册 MCP | diff 审查 | `mcp_server.py` 与 MCP installer 无本任务修改 |
| AC-8 | 每次 executor 调用均使用新进程，跨调用状态只经上游显式传递 | 自动化测试与代码审查 | fake runner 记录独立调用；public contract 不声明会话复用或 standing agent |

## 8. 合同一致性

- 跨章节一致性：三模式选择、Blind Opening 隔离和 executor 透明性在行为、边界、错误及验收章节一致。
- 接口 / seam ownership：CLI 适配归 executor；业务 schema 与 prompt 归调用方；争点状态归 Ledger。
- 验收覆盖：AC-1 至 AC-8 分别覆盖兼容、隔离、独立使用、组合、通用调用、无 role、MCP 非范围和短生命周期调用。
- 剩余非阻塞假设：不同 CLI 的实际原生输出细节会在各 executor 适配测试中固定，不改变这份合同。

## 修订记录

| 前一修订 | 新修订 | 合同变化 | 原因 / 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| 无 | S1 | 初始三模式 Router 与通用 executor 合同 | 用户确认的设计与 Decision D1 | 2026-07-24 | 被 S2 澄清 |
| S1 | S2 | 明确每次 executor 调用均为新的短生命周期 agent 进程，状态显式传递 | 用户确认 | 2026-07-24 | 被 S3 澄清 |
| S2 | S3 | 明确 Blind Opening 仅交付用户临时目录 Markdown，JSON 为同目录内部中间件 | 用户确认 | 2026-07-24 | 当前 |
