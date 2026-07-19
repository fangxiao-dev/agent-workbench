---
target: skills/improve-skill
updated: 2026-07-19
---
## 原则
- [待验证] 偏好优先修复会影响偏好闭环可靠性的机制缺口，再处理流程说明和 eval 运行文档（证据: R1）
- [待验证] 偏好用 Markdown 可读的证据引用列表表达状态，不为 rubric 引入额外计数器（证据: R1）
- [待验证] 已确认偏好必须保留被用户纠正或降级的路径，不能只进不出（证据: R1）

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-08
- 采纳「待验证原则证据列表」「已确认原则修正路径」「workbench 根路径基准」「updated 日期」「轮定义」— 用户原话：GO
- 暂缓「evals.json 配套运行说明」— 推断：当前不影响 skill 本体闭环，等正式 eval runner 流程再补

### R2 · 2026-07-19
- 采纳「fresh context、Worker dispatch、活跃写 worktree 与 assurance 是独立运行时事实；严格串行最多一个活跃写 worktree」— 用户明确指出：这不是偏好；因此只作为 canonical policy/schema 与测试不变量，不降级为 rubric 偏好。
- 采纳「正常 Broker、Orchestrator、Worker 不因时长自动 interrupt；每三分钟仅观察」— 用户确认：直接可观察的状态优先，控制面不新增 heartbeat history、thread/read 轮询或 scheduler。
- 采纳「Lite 优先 Luna/max，catalog 缺失时有证据地降至 Terra/high」— 用户确认：模型/推理能力必须来自 canonical 有序候选与实际 `model/list`，不能现场静默替换。
- 保持文档薄：运行时细节进入 JSON/Schema、snapshot 和 runner；Markdown 只说明角色、授权与失败闭环。
