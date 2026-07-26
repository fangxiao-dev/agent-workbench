# Issue Workflow Runtime 规格

状态（Status）：Spec Gate Passed
创建时间（Created）：2026-07-26
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D2
规格修订（Spec Revision）：S2
<!-- impl-package:projection revision-set end -->
需求来源（Requirement source）：[decision.md](decision.md) 与已批准运行时设计
主题 slug（Topic slug）：issue-workflow-runtime
任务包 ID（Package ID）：260726-issue-workflow-runtime
规范任务包路径（Canonical package）：`docs/implementations/260726-issue-workflow-runtime/`
决策（Decision）：[decision.md](decision.md)

## Decision 门记录（Decision Gate Record）

- 结果（Result）：PASSED
- 目标落点与预期结果：为 KaiSpan 的两人团队提供可确认写入的 triage 与严格只读 reporter。
- 权威来源 / 当前状态证据：已批准的三份 issue workflow 设计稿和现有 skill 结构。
- 选定方向与理由：YAML 提供机器合同，Python 处理确定性读模型，skill 保留业务判断。
- Blocking-uncertainty triage / 开放问题处理结果：无 blocking 问题。
- Owner 决策（已解决 / 未解决）：已解决。
- 证据位置：decision.md
- 评估人 / 日期：Codex / 2026-07-26。

## Spec 门记录（Spec Gate Record）

- 结果（Result）：PASSED
- 八个章节完整：是。
- 验收证据已映射：见第 7 节。
- 阻塞决策 / 歧义：无。
- 批准人 / 日期：fangxiao-dev / 2026-07-26。

## 1. 范围 / 权威来源 / 非目标

- 范围：建立 `skills/issue-workflow/` 的 contract、templates、Python CLI、`$issue-triage` 和 `$issue-reporter`；更新 `$write-issue` 的模板引用和旧 triage 生态的冲突词汇。
- 权威来源与优先级：`issue-contract.yaml` 是机器规则唯一来源；运行时设计解释实现边界；GitHub 的当前 Issue/PR 数据是报告事实源。
- 非目标：GitHub Project、bot/webhook、数据库、Python 写 GitHub、自动分支/评论/关闭、KaiSpan label migration。
- 需要确认的假设：运行环境存在已认证的 `gh`；否则只返回 unknown。

## 2. 术语 / 数据合同

- 领域术语：snapshot 是由 `gh` 返回并规范化的 Issue/PR/关系 JSON；intent 是 agent 已作出的结构化业务意图；plan 是由 Python 计算的 `operations[]`。
- 输入、输出、身份与不变量：snapshot 含 `schemaVersion`、`contractVersion`、repository、fetchedAt、issues、pullRequests、unknowns，不含 token；contractVersion 不匹配的 plan 不得执行。
- Schema、归一化、精度与 ownership 语义：YAML 定义 label set、基数、handoff、hard violation、advisory 与 unknown；`.agents/issue-workflow.yaml` 仅定义 repo-local aliases 与 GitHub login。
- 条件化 evidence-integrity 合同：不适用；本包不发布外部证据或可变公共输出。

## 3. 行为 / 状态机 / 工作流

| Actor / 系统 | 条件 / 状态 | 动作 / 事件 | 结果 / 下一状态 |
| --- | --- | --- | --- |
| `$issue-triage` | 用户给出工作或现有 Issue | 调用 snapshot/validate，完成最小澄清 | 输出 read-only proposal |
| 用户 | proposal 完整 | 明确确认 | triage 通过 `gh` 执行已列 operation |
| `$issue-triage` | 未确认或新增范围 | 任意写入候选 | 不执行 `gh` 写命令，重新提案 |
| `$issue-reporter` | 用户请求状态 | 调用 snapshot/validate/report | 输出事实、分类、违规、提示与 unknown |
| 当前行动者 | Draft PR 可 review | 调用 triage 交接 | `ready-for-agent` 转 `ready-for-human` |
| 当前行动者 | review 要求修改 | 调用 triage 交接 | `ready-for-human` 转 `ready-for-agent` |

## 4. 模块边界 / 依赖

- Owning 模块及其职责：`references/` 拥有合同，`templates/` 拥有正文起点，`scripts/` 拥有确定性计算，两个 leaf skill 拥有交互。
- Core 不变量与 Capability 暴露边界：Python 没有 `apply`；`gh` 是唯一远程适配器；triage 是唯一写入 skill。
- 接口与 seam：Python 以 stdout JSON 与 skill 交接；`gh` 认证和私库权限透传，失败返回 unknown。
- 上游 / 下游依赖：KaiSpan 的 repo-local identity config、tracker 文档与 labels 由协调 package 负责。
- 兼容或迁移窗口：旧 `skills/triage/` 在同一变更中迁移；不得保留两个 `$issue-triage`。

## 5. 错误边界 / 失败恢复

| 失败模式 | 可观察影响 | 隔离方式 | 重试 / 补偿 / 恢复 | Owner |
| --- | --- | --- | --- | --- |
| `gh` 不可用或无权限 | snapshot 缺字段 | 输出 unknown，不判为合规 | 修复 `gh auth` 后重新 snapshot | 当前调用者 |
| contract/alias 无效 | contract check 失败 | 不生成 plan | 修正 YAML 或项目配置后重跑 | workbench maintainer |
| snapshot 版本过期 | plan 拒绝执行 | 不调用写命令 | 重新 snapshot 和 proposal | triage 调用者 |
| 未确认的 mutation | 无远端副作用 | Python 无 apply，triage 阻断写入 | 获得确认后重新执行 | 用户 |

## 6. 约束合同

- 禁止行为：Python 不读取 token、不直接调用 GitHub API、不执行写命令；reporter 不产生 mutation。
- Trust 与 permission 边界：`gh` 当前账户决定可读范围；未知 alias 不 @ 人、不分配、不请求 review。
- 精度 / 归一化义务：label 与 relation 以 YAML 列出的规范字符串比较；身份 alias 规范化为配置中的 GitHub login。
- 外部 provider 义务：只依赖本机 `gh`，不新增 provider。
- 负向依赖：不依赖 GitHub Project、webhook、后台服务或持久数据库。

## 7. 验收语义 / 验证证据

| AC ID | 承诺结果 / 约束 | 证据 producer 或 manual owner | 通过证据 |
| --- | --- | --- | --- |
| AC-1 | contract check 验证 YAML、模板固定标题和 alias 无冲突 | Python fixture | 测试通过 |
| AC-2 | snapshot/validate/report/plan 不调用 `gh` 写命令 | mock `gh` fixture | 调用记录断言通过 |
| AC-3 | triage 确认前不写入，确认后只执行 proposal 内 operation | triage fixture | 前后命令与 diff 断言通过 |
| AC-4 | reporter 解释 Issue/PR、parent 子树、hard violation 与 unknown | reporter fixture | 六类场景报告断言通过 |
| AC-5 | `@同事` 解析为 `haisapan`，并区分 mention/assignee/reviewer | identity fixture | 结构化 operation 断言通过 |

## 8. 合同一致性

- 跨章节一致性：YAML 约束 Python；Python 结构化输出约束 skill，不替代其业务判断。
- 接口 / seam ownership：workbench 拥有 runtime；KaiSpan 拥有 repo-local identity 和 tracker materialization。
- 验收覆盖：五个 AC 覆盖合同、读模型、写入确认、报告与身份边界。
- 剩余非阻塞假设：无。

## 修订记录

| 前一修订 | 新修订 | 合同变化 | 原因 / 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| 无 | S1 | 初始运行时合同 | owner 批准设计 | 2026-07-26 | 无 |
| S1 | S2 | 同步 `$issue-triage` 调用名 | owner 批准 rename | 2026-07-26 | S1 |
