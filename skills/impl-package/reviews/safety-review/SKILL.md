---
name: safety-review
description: >
  Use when changes since a fixed comparison point touch data integrity, security boundaries,
  concurrency, external side effects, or similar safety signals.
---

# Safety Review

审查变更是否会破坏数据、权限、并发正确性或外部系统。它是 implementation-level review：只报告有证据的风险和缺失的保护，不实施修复，也不创建新的风险登记面。

## 何时触发

当任一可观察信号出现时必须运行本 skill：

- diff 触碰 auth、permission、payment、webhook、migration，或 external mutation 路径；
- `dag.md` 的 `Verification Gates` 声明外部写入或副作用验证；
- 当前 spec 的 trust/provider/failure-recovery contract 声明外部写入、数据迁移或不可逆影响；
- 当前 attempt plan 的 `Planned Verification` 选择 Data Safety、real-route 或 external-mutation policy。

信号只复用现有 diff、spec、plan 和 DAG 字段：本 skill 不新增 ticket、ledger、登记表或长期风险队列。没有信号时可明确记录“不触发”及检查过的信号；不要把“不触发”推断为“安全”。

## 输入与范围

调用者必须给出 comparison ref（commit、branch、tag 或 merge-base）及目标 package/ 模块；不得静默猜测比较基线。review 开始时立即把 comparison ref 与 HEAD 都解析为完整 commit SHA；后续命令、plan ER 和 gate Comparison point 只记录不可变 SHA/range，不能记录可移动 branch/tag 名作为证据。

```text
git rev-parse <comparison-ref>^{commit}
git rev-parse HEAD^{commit}
git diff <base-sha>...<head-sha>
git log <base-sha>..<head-sha> --oneline
```

若 ref 不能解析为 commit SHA、diff 为空或无法取得声明的 spec/plan/DAG 输入，fail fast 并请求补充，而不是用当前工作树猜测 change map。项目 `AGENTS.md`、安全规范和服务协议是额外标准；它们可以加严本 skill 的 P1/P2，但不能放宽下列 P0。

## 五类审查

### 1. Data integrity

检查数据写入、schema/data migration、事务边界、校验、重试与 rollback。报告可能重复写、部分写、丢失、损坏或无法恢复的路径，以及证据是否覆盖失败恢复。

### 2. Security boundary

检查认证、authorization/permission、tenant 或数据隔离、secret 处理、输入信任边界和 webhook 签名验证。重点是调用是否能绕过应有的 auth 或 permission 检查。

### 3. Concurrency

检查竞态、重复投递、at-least-once handler、锁/版本控制、幂等键和重试交互。不要因“目前串行执行”而忽略外部回调、队列或用户并发。

### 4. External side effects

检查 payment、webhook、邮件、供应商 API、数据库外写入和其他 external mutation。每项写入应有可核实的 idempotency、去重或 compensation/rollback 语义；报告其失败和重试路径。

### 5. Change map

列出受影响的入口、写入点、数据存储、外部 adapter、异步消费者、迁移及验证证据，并标出未审计或无法确认的路径。change map 是本次报告的一部分，不是新 artifact。

## 严重性与 fail-closed

- **P0 — block / fail-closed：**外部 mutation 没有 idempotency 或可行的 compensation；可绕过 auth/permission 边界；可能导致数据丢失的 migration 没有 rollback。任一 P0 阻止 gate 关闭，直到实现保护或明确撤回风险路径。
- **P1 — required follow-up：**存在可信的完整性、安全、并发或副作用风险，但现有保护可降低其立即破坏性；在合入前必须有修复或经 owner 明确接受的缓解计划。
- **P2 — evidence gap：**无法确认一个重要失败/恢复路径，或 change map 缺证据；不把猜测升格为缺陷，但要求在 plan Execution Record 中补证或记录明确的接受决定。

项目可以定义额外 P0；本 skill 不把项目特定条目硬编码进通用规则。

## 工作流与输出

1. 解析并固定 base/head commit SHA，验证范围及触发信号；收集 diff、当前 spec contract、plan Planned Verification / Execution Record、相关 `dag.md` Verification Gates、测试和项目安全规范。
2. 先生成 change map，再沿五类逐项审查实现和测试证据。
3. 每条 finding 写明 P0/P1/P2、文件/行或稳定来源、风险路径、缺失的保护/证据和建议动作；没有 finding 也要说明审查过的范围和未能验证的边界。
4. 将完整审查结果交给调用者 append 到 plan Execution Record；后续 gate entry 只引用该稳定 ER anchor 并保存 verdict 摘要。本 skill 不自行关闭 gate，也不调度实现。

向 owner 汇报时使用 `talk-to-boss`：先说明审查覆盖的业务/数据/外部写入路径、是否存在阻止合入的风险、剩余证据缺口数量，以及 owner 是否需要接受缓解。严重性代码不能替代风险的业务含义。

随后输出 canonical evidence：`## Trigger evidence`、`## Change map`、`## Findings`、`## Coverage gaps` 和一行 gate 建议。P0 必须在 evidence 区最前且明确写 `BLOCKED`。
