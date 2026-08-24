# s1：恢复步骤结构与 why

## review-code

- 编号步骤：0 步 → 5 步；把原先压成一段的 Review 流程恢复为“理解边界 → 追踪完整 diff → 检查风险边界 → 核对测试与复杂度 → 形成有证据的 finding”五步。
- why：第 1 步对应“证据不足时明确范围，不猜测未提供的事实”；第 2 步说明只看局部 hunk 会漏掉路径证据；第 3 步说明 happy path 正确不涵盖异常与副作用；第 4 步说明绿色测试不等于失败路径或隔离性已验证；第 5 步保留“按 Critical、Important、Nice-to-have 排序、不把偏好写成缺陷”的复核与定级约束。
- 行数：28 → 32。

## dev-with-track

- 编号步骤：4 步 → 8 步；Restore 恢复为 4 个有序动作（validate → 读取 current projection → 狭读当前 Ticket → 校验 package/approval），并保留主 session 控制循环的 Investigate、Decide & seam、Implement、Evaluate 4 步。
- why：第 1 步把 validator 结果结构化为 `projection_drift`，不解析 stdout/stderr；第 2 步只读当前 progress 投影，避免全量 state/situation JSON 变成推进依据；第 3 步不重播已完成历史，保持恢复边界；第 4 步防止恢复时悄然换合同，只有新 package 重新取得 approval。
- 行数：59 → 66。

## do-review

- 编号步骤：顶层 Gate 0–5 的 6 个阶段保持不变；补回各阶段的有序子步骤：Gate 0 为 4 步，Create ReviewRun 为 5 步，Resolve 为 4 步，Dispatch 为 3 步，Canonicalize 为 3 步，Report 为 2 步。
- why：固定 immutable ReviewRun 与 dirty scope，防止审查对象漂移；先定 topology/phase 再分配 capacity，防止资源反向删 track；fresh leaf 与 canonical context 防止跨轮污染；incomplete 不得当 PASS，防止缺证据伪收敛；先 canonicalize 再采信，防止 candidate 绕过 parent 验证；`finding-closure` 不冒充 `terminal-final`，防止有限核对支撑错误的 terminal 结论。
- 行数：64 → 74。

## plan-review

- 编号步骤：审查流程原有 6 步保持不变；第 3 步的 9 个维度由 1 个顿号枚举恢复为 9 个有序子步骤：完整性 → 范围 → 顺序 → 结构 → 验证 → 回退 → 归属 → 验收 → 授权。
- why：完整性防止只做 happy path 留下半套接线；范围防止真实消费者或非目标被静默遗漏/扩大；顺序防止依赖、迁移窗口和 gate 错位；结构防止 ownership 与生产失败到实施时才暴露；验证防止“增加测试”没有 oracle；回退防止恢复方案交给实施者猜；归属防止没有责任人承接依赖/发布；验收防止完成后无法判断 acceptance；授权防止执行先于 approval 或 integration gate。
- 行数：50 → 59。

## review-code-by-standards

- 编号步骤：无序 Fowler smell 枚举保持 1 个集合；恢复有序判断为“仓库规范优先 → Fowler/design 基线 → 深度选择”，其中深度选择拆为 3 步。
- why：先应用仓库认可写法，避免把 hard convention 冲突误报为 smell；先完成基线再决定深度，避免重构偏好遮蔽直接 evidence；明确深度信号才扩大检查面，避免局部 diff 被过度解读；由完整 diff、上下文和规范决定深度，避免固定行数或个人偏好成为门槛。
- 行数：33 → 36。

## review-code-by-spec

- 编号步骤：0 步 → 2 步（逐项对照合同与完整 diff → 为 finding 绑定稳定合同来源和 diff 证据）；其中 6 个合同检查维度保持无序一行枚举。
- why：把合同维度与 diff 证据同时固定，避免把缺少合同依据的仓库规范、smell 或个人偏好伪装成 Spec finding；状态/轨迹 CLI 只作实现接口的机械证据，不替代合同判断。
- 行数：17 → 17。

## safety-review

- 编号步骤：五类审查由 1 个压平枚举恢复为 5 步：Data integrity → Security boundary → Concurrency → External side effects → Change map；现有工作流 1–5 保持不变。
- why：数据完整性步骤防止只看成功写入而漏掉重复/部分写/不可恢复路径；安全步骤防止 auth/permission 被当成普通实现细节；并发步骤防止串行假设掩盖真实竞态；外部副作用步骤防止不可逆写入缺少 idempotency 或 compensation；Change map 为前四类提供完整覆盖边界，暴露未审计路径。
- 行数：35 → 43。

## subagent-driven-development

- 编号步骤：策略字段与 mode 枚举保持无序；Review/并行/失败恢复为 4 步，生命周期/结果为 3 步，并保留主 session 最终集成与 Gate 归属。
- why：review gate 只在 material risk 上启用，避免小动作 checkpoint 泛滥或高风险无 gate；fresh reviewer/fixer 防止同一角色自判自关；共享资源隔离或串行并在全部返回后集成，避免污染和提前集成；仅可安全重放的默认 worker 不完整才允许一次 fallback，业务 BLOCKED 和第二次 INCOMPLETE fail-closed；先 PENDING_REVIEW 再 PASSED，防止局部 DONE 被误当 package 完成；UNCERTAIN/BLOCKED 原样上交，避免编排层制造 PASS。
- 行数：48 → 52。
