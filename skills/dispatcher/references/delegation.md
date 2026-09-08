# Delegation

形成 worker brief 或消费 worker 返回时读取本页。Dispatcher 不规定 provider、model、固定字段数或序列化 envelope。

## Brief

每次委派提供：

- 单一目标、已知事实、关键 entry point 与必须遵循的合同章节；
- 成功行为、边界状态、不变量和具体返回条件；
- write ownership、禁改范围、实际工作目录、前置 dependency 与运行资源；
- 走真实路径的 focused verification，以及该验证不能证明什么；
- 已确认 finding 的原始意见、定位和裁决；
- 返回实际改动或结论、验证证据、未完成项、residue 与 cleanup 状态。

`investigate` 回答一个会改变执行判断的问题；`implement` 交付已裁决的有界产物；`fix` 处理已确认且已边界化的 finding；`verify` 执行既定的无写副作用检查。会重写 snapshot 或 generated file 的验证按实际副作用使用 `implement` 或 `fix`。

同一结果所需的 focused test、format、普通重跑和机械 cleanup 留在本次委派。需要新的业务裁决、授权、资源 owner 或独立 acceptance 的工作回到主控重新选择。

## 返回与 lifecycle

worker 以 `DONE | BLOCKED | INCOMPLETE` 返回局部 outcome；调查附 `EVIDENCE_SUFFICIENT | EVIDENCE_GAP`。主控核对可归因 diff、证据和残留后才消费，返回不会自动授权后续动作。

review receipt 确认审查已派发；主控消费该固定增量的独立审查结果后，才依据结论记录 `PASSED`。

同一范围的实现或修复在上下文可信且 ownership 不变时可以复用 worker。reviewer 与 implementer 保持独立；同一 review scope 可复用 reviewer 并输入新的固定增量。有界 test campaign 可在环境和 comparison point 不变时复用执行上下文。

错误 cwd、缺少本地 binary、format 或普通测试载体故障，在边界仍可信时属于当前动作 recovery。关键前提失效、遗漏 caller/producer 家族、实际 write-set 外溢或结果无法归因时返回事实，由主控重新调查边界。

完成标准：worker 能从 brief 唯一确定目标、ownership、真实验证和返回边界；主控能把返回关联到唯一派发，并知道剩余工作和 cleanup 状态。
