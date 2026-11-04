# <NN> — <Ticket 标题>

Ticket ID: <ticket-id>
Publication Status: Draft
Attempt ID: <attempt-id>

> Ticket 定义稳定验收边界；运行时验收状态保存在 `.impl-package/state.json`，不会回写 Ticket。Ticket 直接属于当前 Attempt，不需要手工 revision。

## 建设内容

<一个范围窄、边界完整、用户可见的交付与验收切片。>

## Contract references

- `<repo-relative-path>#<major-section-anchor>` — `<该章节约束本 Ticket 的内容>`
- 引用 `contract-design.md` 时追加 entry point：`<repo-relative-path>#<major-section-anchor> · <Operation/Aggregate/Seam/Projection 名或函数/类名>` — `<该 entry point 约束本 Ticket 的内容>`

引用必须定位到一级或二级大章节；不得只写整个文档路径或使用行号。引用 `contract-design.md` 时不得只停在章节级，必须命名具体 entry point。

## 验收标准

- **AC-1：** <可观察结果或约束>
  - Arrival path: <跨模块 AC 填写；entry → EXISTS: <existing-symbol> → NEW: <new-symbol> → arrival；规则见下方“到达路径规则”>
  - 证据：<计划证据或人工验证 owner>

## Coverage

- Journey steps: <J1-S1[, J1-S2 ...] | none>
- Suites: <suite id[, ...] | none>
- Required review: <none | review 范围与原因>

Coverage 是 step 与套件归属的唯一来源，Spec 不点名 Ticket。steps 与 suites 不同时为 `none`；每个 step 和每个 ticket 级套件至少由一张 Ticket 认领。AC 写本票独有的可观察结果，Journey 与套件已覆盖的承诺引用 Spec，不在此复述。

## 到达路径规则

AC 文字里出现两个以上模块/边界的名字时 Arrival path 必填（缺失时 `package validate` 返回 finding）。除 `entry` 与 `arrival` 外，每个路径段都标成 `EXISTS: <symbol>` 或 `NEW: <symbol>`；`EXISTS` 表示 comparison commit 上先找到的标识符，`NEW` 表示本包将新建的标识符。`package validate` 对缺失标注报错，对 `EXISTS` 未找到只返回 finding。到达路径中与当前 AC 无关的依赖可以使用 mock / fake / in-memory 替身；但替身不得替代该 AC 所承诺的真实行为或移除关键因果机制。真实 UI、provider、完整用户旅程仍须按真实环境验收。一条路径写不完这个 AC 时写两条，不要压成一条——AC 有两个独立入口（例如既有直接调用又有 HTTP 请求）时就是这种情况，压成一条会逼出一次伪造。

早期路径可以缩小格式、入口或已授权主体范围，但只能做到“纵切窄、属性不薄”。

## Blocking Dependencies

- <implementation|acceptance|release>: <ticket-id>

没有阻塞边时填写 `None`。依赖类型只允许 `implementation | acceptance | release`：默认 `acceptance`（只挡正式验收，不挡开工）；只有没有上游产物就无法实现、也无法做 child-local 验证时才写 `implementation`，并在该行后一句话写出所依赖的产物。不要添加 worker ownership、文件级步骤或 Task 进度。
