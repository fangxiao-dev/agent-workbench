# Talk To Boss Patterns

Use this reference when the status is messy, too technical, or needs examples before rewriting.

## Functional Slices

Good functional slices are product capabilities or rules:

- `Inventory Item Threshold 管理`
- `包装/计量定义保护`
- `Product SKU 显式字段规则`
- `Derived Products / Linked Products 可见性`
- `结账价格锁定`
- `审批流退回规则`

Bad status slices are process or implementation buckets:

- `T1/T2/T3`
- `Service 层`
- `Action seam`
- `i18n`
- `Chrome 验证`
- `Subagent review`

Engineering artifacts can appear as evidence, but they should not become section titles unless the user explicitly asks for an engineering report.

## Spec Sentence Examples

- `Admin 可以在 Inventory Item 上修改 Safety Stock Threshold，保存后该阈值进入库存更新链路。`
- `当 Inventory Item 已被 active Product Components 引用时，Admin 不能修改 measurement / packaging 定义，系统会拒绝保存并避免破坏已上线产品配置。`
- `当只修改 threshold 时，即使该 Inventory Item 已被产品引用，系统仍允许保存，因此补货阈值维护不会被包装定义保护误伤。`
- `Product SKU Workbench 只展示显式 Product SKU；没有显式 SKU 时，不再用 Supplier Product Code 兜底伪装。`

## Evidence Translation

| Engineering evidence | Boss-readable meaning |
|---|---|
| service test passed | 后端规则有自动化保护，绕过 UI 也会被拦 |
| action test passed | 页面提交到服务层的参数链路已覆盖 |
| integration test passed | 关键更新路径能端到端写入本地测试后端 |
| i18n check passed | 多语言文案 key 没有缺口 |
| tsc passed | 类型层面没有发现断裂 |
| Chrome verification pending | 真实页面交互和视觉状态还没验收 |
| Lark smoke pending | 外部 Test Environment 写入/读回还没证明 |
| reviewer pending | 还缺独立最终把关 |

## Not-Run Fusion

Do not print a generic audit template. Mention missing checks only when they were part of the plan or required by the task.

Good:

- `真实 Chrome 页面验收还没完成，因为本轮浏览器验证被中断；因此页面交互和受保护字段状态还不能算验收通过。`
- `Lark Test Environment threshold 写入/读回 smoke 还没跑，因为真实 Test Env mutation 验收还未执行；因此外部数据源链路仍未 closed。`
- `邮件真实发信 smoke 没跑，因为本任务没有真实发信授权；因此通知送达仍只被本地逻辑覆盖。`

Bad:

- `Not run: Lark, Lexware, email, public deployment. Why not: not applicable.`
- `未跑 Lexware smoke。` when the task never touched Lexware.
- `Test-case gap judgment: none.` when there is no abnormal gap.

## Test-Case Gap Reporting

Only report a test-case gap when follow-up work is needed. Keep it concrete:

- `现有 test-cases 只有本地集成路径，没有 Test Environment Lark 写入/清理 smoke；需要补一个可执行 smoke 或更新场景索引。`
- `真实邮件送达没有现成 smoke case，本次只能证明 payload 生成，不能证明外部投递。`

If there is no gap, omit the section entirely.

## Completion Language

Use precise closure language:

- `代码和本地测试层面已完成`
- `真实浏览器验收未完成，所以不能宣称需求 closed`
- `外部数据源 smoke 未完成，所以 Lark 链路仍是剩余验收项`
- `最终 reviewer 未确认前，整体 issue 仍处于收口阶段`

Use percentage only when it helps, and make it obviously approximate:

```text
当前完成度：约 70%。核心行为已实现并通过本地测试；剩余是 Chrome 真实 UI 验收、Test Environment Lark smoke 和最终 review。
```

## Sample Output

```markdown
**整体判断**
核心代码和本地测试已经收口；需求还不能关，因为真实 Chrome UI 和 Lark Test Environment 还没验收。

**功能 Slice 进度**

**1. Inventory Item Threshold 管理**
目标：Admin 能维护库存安全阈值，不被包装定义保护误伤。

已实现，待验收：
- Admin 可以更新 Inventory Item 的 Safety Stock Threshold，保存后该值进入库存更新链路。
- 当只修改 threshold 时，即使 Inventory Item 已被 active Product Components 引用，系统仍允许保存。

还缺：
- 真实 Chrome 页面保存流程还没验，因为本轮浏览器验收未完成。
- Lark Test Environment 写入、读回和清理还没验，因为真实 Test Env smoke 尚未执行。

**2. 包装/计量定义保护**
目标：防止已经被产品使用的 Inventory Item 被改坏基础定义。

已实现，待验收：
- 当 Inventory Item 已被 active Product Components 引用时，Admin 不能修改 measurement / packaging 定义。
- 即使绕过 UI 直接提交更新，服务层也会拒绝该修改，因此不会写坏后端数据源。

还缺：
- 需要真实页面验证受保护字段的禁用状态和提示是否符合预期。
```
