# <NN> — <Ticket 标题>

**Ticket ID：** <ticket-id>
**Publication Status：** Draft
**Attempt ID：** <attempt-id>

> Ticket 定义验收边界；运行时验收状态保存在 `.impl-package/state.json`。Ticket 直接属于当前 Attempt，不需要手工 revision。

## Runtime Acceptance

<!-- impl-package:projection runtime-acceptance begin -->
- Runtime Acceptance Status: UNRECORDED
- Acceptance evidence: none
<!-- impl-package:projection runtime-acceptance end -->

## 建设内容

<一个范围窄、边界完整、用户可见的交付与验收切片。>

## Contract references

- `<repo-relative-path>#<major-section-anchor>` — `<该章节约束本 Ticket 的内容>`

引用必须定位到一级或二级大章节；不得只写整个文档路径或使用行号。

## 验收标准

- **AC-1：** <可观察结果或约束>
  - 证据：<计划证据或人工验证 owner>

## 阻塞依赖

- <implementation|acceptance|release>: <ticket-id>

没有阻塞边时填写 `None`。依赖类型只允许 `implementation | acceptance | release`。不要添加 worker ownership、文件级步骤或 Task 进度。
