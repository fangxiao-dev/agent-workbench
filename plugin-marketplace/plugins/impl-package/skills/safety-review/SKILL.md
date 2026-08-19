---
name: safety-review
description: >
  当固定 comparison point 之后的变更触及 data integrity、security boundary、concurrency、
  external side effect 或类似 safety signal 时使用。
---

# Safety Review

审查变更是否会破坏数据、权限、并发正确性或外部系统；implementation-level review：只报告有证据的风险和缺失的保护，不实施修复，不创建新的风险登记面。

## 触发信号（判断）
任一信号出现必须运行：diff 触碰 auth/permission/payment/webhook/migration/external mutation 路径；需求/设计/发布约束声明外部写入、数据迁移或不可逆影响；已声明验证计划选择 Data Safety/real-route/external-mutation policy。信号只复用现有 diff/spec/plan/DAG 字段；无信号时明确记录"不触发"及检查过的信号——"不触发"≠"安全"。

## 收缩型 focused path（判断）
delta 只删除未执行的 destructive authorization、把 classification 改为 retain/no-delete、移除外部写入路径，或以其他方式收缩 authority，且 `execution impact` 非 `destructive-external` → 不运行完整五类审查，只核对三点：实际 diff 没有引入新的 mutation 路径；既有安全保护没有随减法被误删；runtime authorization/execution eligible count 没有增加。任一点不能证明 → 回完整审查。

## 输入与范围
调用者必须给 comparison ref；立即解析为不可变 commit SHA，后续证据只记录 SHA/range，不记录可移动 branch/tag 名。ref 不能解析、diff 为空或拿不到声明的 spec/plan/DAG 输入 → fail fast 请求补充，不用工作树猜 change map。项目 AGENTS.md/安全规范可加严 P1/P2，不能放宽 P0。

## 严重性（fail-closed 定级）
P0 — block：外部 mutation 无 idempotency/可行 compensation；可绕过 auth/permission 边界；可致数据丢失的 migration 无 rollback。P1 — required follow-up：可信风险但现有保护降低立即破坏性，合入前须修复或 owner 明确接受的缓解计划。P2 — evidence gap：重要失败/恢复路径无法确认或 change map 缺证据；不把猜测升格为缺陷，要求补证或记录明确接受决定。

## 工作流与输出（leaf 结构化输出）
1. 解析固定 base/head SHA、验证范围与触发信号，先判收缩型 focused path；完整审查才收集 diff/需求/设计/验证合同/测试/项目安全规范。2. 先生成 change map 再逐类审查——五类清单（Data integrity/Security boundary/Concurrency/External side effects/Change map）见 references/five-categories.md，按需加载。3. 每条 finding 写 P0/P1/P2、文件/行或稳定来源、风险路径、缺失保护/证据、建议动作。4. 结果交调用者保存为稳定 review evidence；不自行关 gate、不调度实现。输出 canonical evidence：`## Trigger evidence`、`## Change map`、`## Findings`、`## Coverage gaps` + 一行 gate 建议；P0 必须最前且明确写 `BLOCKED`。
