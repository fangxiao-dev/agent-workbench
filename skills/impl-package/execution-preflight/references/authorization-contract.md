# Authorization Bundle Contract

只在 `SKILL.md` 将 execution preflight 分类为 `new/update` authorization bundle 后读取本文件；`restore` 与仅需核查冲突 control slice 的 anchor mismatch 不读取。它承载完整扫描表、输出模板和低频失败边界；主路径与完成条件以 `SKILL.md` 为准。

## 生命周期扫描表

只纳入 active request 或授权来源实际涉及的类别：

- **Subagents：** 哪些调研、实现、验证和记录工作可按 Task 委派；哪些 task-scoped 权限可随派发传递；哪些共享资源或未决决策必须由主 session 串行化。
- **实现与数据 mutation：** 本地文件、生成物、schema、migration、fixture、reset、cleanup、删除和其他不可逆或 production-like 操作。
- **验证：** 依赖安装、code generation、测试、build、dry-run、browser automation、desktop GUI、manual/native verdict，以及失败是否阻止 acceptance。
- **外部系统：** read-only/smoke、真实 provider、network call、owner-supplied credentials/config、staging/production、database、Azure/Lark/email 等来源明确提及的系统及其成本或速率副作用。
- **临时资源：** local DB、temporary storage/files、browser context、test order/fixture 的创建与确定性清理。
- **Git 与协作面：** worktree/branch、staging、commit、push、PR、merge、deployment、Issue edit 和 thread handoff。
- **HITL：** 产品/schema/UX 选择、验收例外、人工步骤、native tool verdict 和 owner sign-off。

最后按顺序做一次 permission-stop sweep：实现写入与生成物 → schema/migration → local DB/fixture/temp/browser cleanup → install/codegen/test/build → provider/network/credential → desktop GUI/manual verdict → Issue/Git/PR/merge/deploy。该扫描用于防遗漏，不授权引入来源未提及的相邻系统。

## 当前启动前置检查

只对当前即将开始的高风险单元、或 plan 明确标为启动前必须存在的资源检查；不因通用清单或后续验证步骤引入相邻系统。记录实际检查或精确 blocker，不创建独立状态表：

若当前请求仅为全锚点匹配 handoff 的 anchor/preflight 后暂停，启动前置只包含 worktree、HEAD、package、binding、sidecar digest、runtime/gate machine state、contract-status 与授权 envelope；未来 implementation/test wave 的 package manager、DB、`.env`、browser/provider identity 不在本轮检查。

- **环境与配置：** 必需环境变量存在；连接/endpoint 的 host、port、database-name、environment tag 与 plan allow-list 一致；日志只写存在性和安全分类，不写 secret 或完整 URL。
- **本地可变资源：** 已有 loopback test DB/container/service 是否存在、可启动、端口可达；fixture namespace、temporary storage 和 cleanup owner 是否明确。仅在当前授权覆盖时才启动既有资源，绝不自行创建数据库、云资源或共享环境。
- **执行工具：** package manager、generator、test runner、browser/desktop/native tool 是否可启动；版本或安装缺口是否需要额外 mutation/owner input。
- **身份与外部依赖：** 计划使用的 browser identity、provider credential/endpoint、manual/native verdict path 是否存在；除非已授权为 preflight smoke，不发送业务 payload、不调用外部业务操作。
- **顺序与隔离：** shared migration/codegen/singleton provider/browser/DB 是否有串行顺序、run identity 和 deterministic cleanup；不把“可启动”误写成正式 acceptance 已通过。

当前单元的明确启动前置缺口必须修复或阻止该单元；后续、可隔离的验证资源由 Planned Verification 按需处理。仅实际执行后才暴露的故障、真实数据冲突或外部工具临时失效才属于 runtime finding。

## Subagent 模式

模式定义、主 session 保留职责与串行化规则以 `SKILL.md` 的 `Subagent modes` 为准，本 reference 不重复。授权 bundle 只记录当前选择、owner/host 例外、可传递的 task-scoped 权限和实际共享资源顺序；具体模型只在 owner 或任务显式指定时记录。

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
- Subagents：`default-long`（默认） / `ordinary` / 无 delegation capability；`default-long` 下主 session 仅保留调度、授权记录、决策、跨 Task seaming、共享验证、Ticket acceptance、claim audit、gate 和最终集成，subagent 充分承担其余可隔离执行；`ordinary` 下主 session 可直接处理小型/紧耦合工作；已授权权限可随明确 Task 传递
- 当前启动前置：<只记录当前单元的实际检查、已授权低副作用修复或精确 blocker；均不得含 secret>

可以回复“全部批准”，或只列出不批准/需要缩小的例外；未列例外即按上述精确边界授权当前任务，不再逐项追问。
```

授权包必须具体到让“全部批准”具有有界含义；不得询问宽泛的“可以做一切吗”。

## 执行授权记录模板

```markdown
Execution authorization for this task:
- Subagents: <default-long / ordinary / 无 delegation capability>；<模式理由、主 session 保留职责、subagent 可委派范围、授权传递和必须串行化资源>
- Allowed by plan/user: <task-scoped 的实现、验证、外部工具、清理及 Git/Issue 权限>
- Blocked unless separately authorized: <plan/user 禁止或要求另行授权的边界>
- HITL decisions: <resolved/pending>
- Current start prerequisites: <当前单元的最小证据或 blocker；不含 secret>
```

## 边界与失败模式

- 不做 implementation planning、issue ordering 或 code reconnaissance；不创建 worktree、不运行 migration/正式测试/业务浏览器流程、不编辑代码或计划、不提前派发。当前启动前置检查仅允许最小只读检查，以及已授权的低副作用本地修复；不得形成全量 readiness inventory 或第二份执行合同。
- 不从一般知识补充来源未提及的系统；来源只为禁止或单独授权而提到的系统，原样记录该边界。
- 不把 read-only/staging 权限扩大成 mutation，也不复用无关任务的旧权限。
- 不把计划已禁止事项变成反向确认问题。
- 不按实现顺序逐项申请权限，或遗漏 migration、provider、browser/GUI、cleanup、Git/Issue、acceptance tool 后中途停顿。
- `default-long` 中保持普通执行切片由 subagent 承担，并将授权随明确 Task 边界传递。
- 跨 Task seam、未决决策和共享验证由主 session 收口；其余可隔离部分由对应 subagent 交付，主 session 以 diff、测试与证据完成验收。
- 充分利用不等于无边界并发；不得忽略依赖、共享写入和单实例外部资源。
- 新权限 blocker 若仍在已授权对象/环境/数据/副作用范围内，直接继续；只有跨出该 envelope 才重新申请。
