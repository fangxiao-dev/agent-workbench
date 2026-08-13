---
target: plugin-marketplace/plugins/impl-package/skills/req-align
updated: 2026-08-13
---
## 原则

- [待验证] Spec Gate 仍保护实质 contract；只有明确请求或高不确定性/高风险信号才附加 Grill，对清晰局部 delta 不增加对抗审查。（证据: R1）
- [待验证] 会改变 Decision、Spec、authority、delivery path 或 Acceptance Semantics 的未知项，在 Decision Gate 通过前必须由允许的 investigation 关闭；不得降级为 plan risk。（证据: R2）
- [待验证] Focused PRD 只固化跨场景的产品问题与业务可读性标准；UI、多角色、自动决策、外部交接、MVP/POC 等案例结构按需求信号条件触发，不因单一成功案例升级为通用必填模板。（证据: R3）
- [待验证] 初版把已确认的口头/文档产品承诺固化进当前 D/S；后续请求默认是 current D/S 的 delta，未再次提及不构成删除，只有显式替换、修改或废弃才改变现行承诺。（证据: R4）
- [待验证] Spec 在正式写入前先重建 current contract surfaces 并完成所需设计；Gate 主要检查完成性、一致性与验收覆盖。详细合同只有在能保持主线可读或服务多个消费者时才拆到与 `spec.md` 同生命周期的 `contract-design.md`。（证据: R5）
- [待验证] Contract 漏检优化先收敛在 Spec 阶段，不因单次事故同时扩张 Plan、Task 验收或其他下游流程。（证据: R6）
- [待验证] Spec Gate 规则表达跨业务场景成立的 contract invariant；具体事故只作为 eval，不进入正式流程规则。（证据: R6）

## 决策记录（滚动，最近 ≤5 轮）

### R2 · 2026-07-23

- 采纳「blocking decision uncertainty」— feasibility / architecture-fit 的未知项只要反向答案会改变合同，就在 Decision Gate 关闭；read-only 调查直接执行，需授权或副作用的调查则持久化 BLOCKED。D/S gate 与已记录下游证据只推导 handoff 展示状态，不升级 schema。

### R3 · 2026-07-25

- 待验证「业务可读 Focused PRD」— 通用模板回答受益者/情境、问题/触发、结果/价值、核心行为、边界和成功信号；产品深挖由需求信号路由，字段合同、状态机、错误合同与实施步骤仍分别留在 Spec/Plan。

### R4 · 2026-07-25

- 待验证「零样本承诺捕获与演进」— 第一版从已确认的口头、文档、截图和仓库输入提取产品承诺；后续版本先读取 current D/S，将新输入按 delta 合并，避免跨 session 因未重复口述而丢失有效承诺。

### R5 · 2026-08-11

- 待验证「前置合同设计与实时范围」— 每次 Spec 创建或更新首先整体重建当前 API、persistence、seam 与 public read-model 范围，只保存 current truth；设计中新发现 surface 立即更新范围。普通领域变化保持单一 `spec.md`，只有精确结构遮蔽行为/验收主线或 canonical model 被多个 operation/module 消费时才 earned `contract-design.md`。Gate 不把首次设计 DTO/schema 当作常规职责。

### R6 · 2026-08-13

- 否决同时增强 Plan、Task 验收与独立 reviewer — 用户原话：不要过度设计，暂时只需要做 Spec。
- 要求优化面向通用设计 — 用户原话：尽量不要只面向这一个 case。
