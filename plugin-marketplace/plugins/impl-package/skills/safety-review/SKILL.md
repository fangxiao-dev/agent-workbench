---
name: safety-review
description: >
  当固定 comparison point 之后的变更触及 data integrity、security boundary、concurrency、
  external side effect 或类似 safety signal 时使用。
---

# Safety Review

审查变更是否会破坏数据、权限、并发正确性或外部系统；implementation-level review：只报告有证据的风险和缺失的保护，不实施修复，不创建新的风险登记面。

## 触发信号（判断）

任一可观察信号出现必须运行：diff 触碰 auth/permission/payment/webhook/migration/external mutation 路径；需求/设计/发布约束声明外部写入、数据迁移或不可逆影响；已声明验证计划选择 Data Safety/real-route/external-mutation policy。信号只复用现有 diff/spec/plan/DAG 字段；本 skill 不新增 ticket、登记表或长期风险队列；无信号时明确记录“不触发”及检查过的信号——“不触发”不等于“安全”。

## 收缩型 focused path（判断）
若 delta 只删除未执行的 destructive authorization、把 classification 改为 retain/no-delete、移除外部写入路径，或以其他方式收缩 authority，且 `execution impact` 非 `destructive-external`，不运行完整五类审查，只核对三点：实际 diff 没有引入新的 mutation 路径；既有安全保护没有随减法被误删；runtime authorization/execution eligible count 没有增加。把 focused monotonicity check 写入现有 review evidence，不创建 change map 或新 artifact；任一点不能证明则回到完整审查。

## 输入与范围
调用者必须给 comparison ref（commit、branch、tag 或 merge-base）及目标范围；开始时立即解析为不可变的 base/head commit SHA，后续命令和 review evidence 只记录不可移动的 SHA/range，不记录 branch/tag 名作为证据。语义锚定命令为 `git rev-parse <comparison-ref>^{commit}`、`git rev-parse HEAD^{commit}`、`git diff <base-sha>...<head-sha>`、`git log <base-sha>..<head-sha> --oneline`。若 ref 不能解析为 commit SHA、diff 为空或无法取得声明的 spec/plan/DAG 输入，fail fast 请求补充，不用当前工作树猜 change map；项目 `AGENTS.md`、安全规范和服务协议可加严 P1/P2，但不能放宽 P0。涉及状态/轨迹机制时，以语义 CLI 的 `--help`、`choices`、校验/错误输出和处境注入/CLI 尾注作为机械证据。

## 严重性（fail-closed 定级）
P0 — block/fail-closed：外部 mutation 无 idempotency/可行 compensation；可绕过 auth/permission 边界；可致数据丢失的 migration 无 rollback；任一 P0 阻止变更进入下一阶段，直到实现保护或明确撤回风险路径。P1 — required follow-up：可信风险但现有保护降低立即破坏性，合入前须修复或 owner 明确接受缓解计划。P2 — evidence gap：重要失败/恢复路径无法确认或 change map 缺证据；不把猜测升格为缺陷，要求补证或记录明确接受决定。项目可以定义额外 P0；本 skill 不把项目特定条目硬编码进通用规则。

## 五类审查（完整审查按需加载）

完整审查逐项覆盖 **Data integrity、Security boundary、Concurrency、External side effects、Change map**，并按以下顺序执行；前四类检查实现与测试证据，Change map 列出受影响入口、写入点、存储、外部 adapter、异步消费者、迁移和验证证据并标出未审计/无法确认路径。

1. **Data integrity**：检查数据写入、schema/data migration、事务边界、校验、重试与 rollback。报告可能重复写、部分写、丢失、损坏或无法恢复的路径，以及证据是否覆盖失败恢复；否则数据错误可能在审查只看成功写入时被漏掉。
2. **Security boundary**：检查认证、authorization/permission、tenant 或数据隔离、secret 处理、输入信任边界和 webhook 签名验证。重点是调用是否能绕过应有的 auth 或 permission 检查；否则安全边界会被当成普通实现细节。
3. **Concurrency**：检查竞态、重复投递、at-least-once handler、锁/版本控制、幂等键和重试交互。不要因“目前串行执行”而忽略外部回调、队列或用户并发；否则重复执行和竞态只会在真实并发下暴露。
4. **External side effects**：检查 payment、webhook、邮件、供应商 API、数据库外写入和其他 external mutation。每项写入应有可核实的 idempotency、去重或 compensation/rollback 语义；报告其失败和重试路径，否则不可逆副作用可能无法恢复。
5. **Change map**：列出受影响的入口、写入点、数据存储、外部 adapter、异步消费者、迁移及验证证据，并标出未审计或无法确认的路径。change map 是本次报告的一部分，不是新 artifact；没有它就无法判断前四类是否覆盖完整变更。

详细专项 checklist 见 [five-categories.md](references/five-categories.md)，收缩型 focused path 不加载。

## 工作流与输出（leaf 结构化输出）

1. 解析并固定 base/head SHA，验证范围及触发信号，先判断收缩型 focused path；完整审查才收集 diff、当前需求/设计/验证合同、测试和项目安全规范。
2. 先生成 change map，再沿五类逐项审查实现和测试证据。
3. 每条 finding 写明 P0/P1/P2、文件/行或稳定来源、风险路径、缺失保护/证据和建议动作；没有 finding 也要说明审查过的范围和未能验证的边界。
4. 将完整审查结果交给调用者保存为稳定 review evidence；本 skill 不自行关闭 release gate，也不调度实现。
5. 输出 canonical evidence：`## Trigger evidence`、`## Change map`、`## Findings`、`## Coverage gaps` 和一行 gate 建议；P0 必须在 evidence 区最前且明确写 `BLOCKED`。
