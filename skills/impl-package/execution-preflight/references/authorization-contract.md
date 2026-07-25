# Authorization Bundle Contract

只在 `SKILL.md` 判定需要 execution preflight 后读取本文件。它承载完整扫描表、协作模式、输出模板和低频失败边界；主路径与完成条件以 `SKILL.md` 为准。

## 生命周期扫描表

只纳入 active request 或授权来源实际涉及的类别：

- **Subagents：** delegation 是否允许；owner 是否要求充分利用；哪些 task-scoped 权限可随派发传递；哪些共享资源或未决决策必须由主 session 串行化。
- **实现与数据 mutation：** 本地文件、生成物、schema、migration、fixture、reset、cleanup、删除和其他不可逆或 production-like 操作。
- **验证：** 依赖安装、code generation、测试、build、dry-run、browser automation、desktop GUI、manual/native verdict，以及失败是否阻止 acceptance。
- **外部系统：** read-only/smoke、真实 provider、network call、owner-supplied credentials/config、staging/production、database、Azure/Lark/email 等来源明确提及的系统及其成本或速率副作用。
- **临时资源：** local DB、temporary storage/files、browser context、test order/fixture 的创建与确定性清理。
- **Git 与协作面：** worktree/branch、staging、commit、push、PR、merge、deployment、Issue edit 和 thread handoff。
- **HITL：** 产品/schema/UX 选择、验收例外、人工步骤、native tool verdict 和 owner sign-off。

最后按顺序做一次 permission-stop sweep：实现写入与生成物 → schema/migration → local DB/fixture/temp/browser cleanup → install/codegen/test/build → provider/network/credential → desktop GUI/manual verdict → Issue/Git/PR/merge/deploy。该扫描用于防遗漏，不授权引入来源未提及的相邻系统。

## Subagent 模式

### 调度优先（推荐）

主 session 负责 authorization record、Task/DAG 选择与依赖排序、业务/安全决策、实际跨 Task seam、冲突处理、共享验证、Ticket acceptance 和最终集成。subagent 承担所有目标可声明、写入可隔离、结果可复核、失败可回收的代码实现、测试、迁移适配、文档、验证、错误复现和已决策闭合的集成工作。

- 不得仅因工作叫 integration/seaming 就收回主 session；只有接口未冻结、业务语义未决、写入无法隔离或风险无法复核时，主 session 才先解除阻碍。
- 已授权对象、环境、数据和副作用可随明确 Task 派发传递，不逐 subagent 重复申请，也不允许 subagent 扩大 ownership。
- 独立且写入不冲突的切片按 wave 并行；真实依赖、shared migration/codegen、同文件核心写入和单实例外部资源必须串行。
- 主 session 不重复实现 subagent 已交付切片；通过 diff、测试、证据和必要抽查复核，只在实际 seam、finding 或返工时接管。
- 默认模型（除非 task、owner 或 host 另有指定）：实施 `gpt-5.6-terra` / `high`；review `gpt-5.6-sol` / `medium`。

### 普通使用

subagent 只承担有界辅助，主 session 是主要实现者。仅在 owner 明确偏好时采用，不得把模糊回答自动降级到此模式。

### 不允许

禁止使用 subagent。host 禁止或 owner 明确选择时采用。

不得在模式确认前启动 subagent；owner 已明确说“充分利用”等同调度优先，不需要再次确认。

## 一次性授权包模板

```markdown
一次性 Execution authorization bundle：
- 当前已授权：<本 session 已明确允许的范围，或“无”>
- 本次请求授权：
  1. <必需操作；精确对象、环境、数据与副作用边界>
  2. <验证、外部工具和清理；精确边界>
  3. <Git、Issue 或 PR 收口；精确边界>
- 明确禁止/不适用：<来源排除的系统、环境或数据>
- HITL / owner decisions：<开放决策，或“无”>
- Subagents：调度优先（推荐） / 普通使用 / 不允许；调度优先时，已授权权限按明确 Task 边界传递

可以回复“全部批准”，或只列出不批准/需要缩小的例外；未列例外即按上述精确边界授权当前任务，不再逐项追问。
```

授权包必须具体到让“全部批准”具有有界含义；不得询问宽泛的“可以做一切吗”。

## 执行授权记录模板

```markdown
Execution authorization for this task:
- Subagents: <调度优先 / 普通使用 / 不允许>；<主 session 保留职责、subagent 可执行范围、授权传递和必须串行化资源>
- Allowed by plan/user: <task-scoped 的实现、验证、外部工具、清理及 Git/Issue 权限>
- Blocked unless separately authorized: <plan/user 禁止或要求另行授权的边界>
- HITL decisions: <resolved/pending>
```

## 边界与失败模式

- 不做 readiness、implementation planning、issue ordering 或 code reconnaissance；不创建 worktree、不运行测试、不编辑、不提前派发。
- 不从一般知识补充来源未提及的系统；来源只为禁止或单独授权而提到的系统，原样记录该边界。
- 不把 read-only/staging 权限扩大成 mutation，也不复用无关任务的旧权限。
- 不把计划已禁止事项变成反向确认问题。
- 不按实现顺序逐项申请权限，或遗漏 migration、provider、browser/GUI、cleanup、Git/Issue、acceptance tool 后中途停顿。
- owner 已要求充分利用 subagent 时，不得记录为普通使用、再次询问模式，或把 subagent 限制为调研/审查。
- 不以 integration/seaming 为名拒绝可隔离委派，不重复实现 subagent 已交付内容，也不把一次性授权解释成仅主 session 可用。
- 充分利用不等于无边界并发；不得忽略依赖、共享写入和单实例外部资源。
- 新权限 blocker 若仍在已授权对象/环境/数据/副作用范围内，直接继续；只有跨出该 envelope 才重新申请。
