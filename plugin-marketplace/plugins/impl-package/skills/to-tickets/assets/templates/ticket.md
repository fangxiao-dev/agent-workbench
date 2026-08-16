# <NN> — <Ticket 标题>

Ticket ID：<ticket-id>
Publication Status：Draft
Attempt ID：<attempt-id>

> Ticket 定义稳定验收边界；运行时验收状态保存在 `.impl-package/state.json`，不会回写 Ticket。Ticket 直接属于当前 Attempt，不需要手工 revision。3.5 的 `dag=false` 是 Ticket-only 合同，不创建 Task。

## 建设内容

<一个范围窄、边界完整、用户可见的交付与验收切片。>

## Contract references

- `<repo-relative-path>#<major-section-anchor>` — `<该章节约束本 Ticket 的内容>`

引用必须定位到一级或二级大章节；不得只写整个文档路径或使用行号。

## 验收标准

- **AC-1：** <可观察结果或约束>
  - Stable claim ID：`AC-1`
  - 到达路径：<跨模块 claim 必填；entry → ... → arrival>
  - 证据时机：`early-falsification` | `remaining-completion`
  - 证据：<计划证据或人工验证 owner>

## 安全不变量

- tenant：<第一条可执行路径必须满足的租户边界>
  - Stable claim ID：`INV-tenant-isolation`
  - 到达路径：<跨模块 claim 必填；entry → ... → arrival>
- RBAC / privacy：<授权与隐私约束；早期路径不得关闭或弱化>
  - Stable claim ID：`INV-rbac-privacy`
  - 到达路径：<跨模块 claim 必填；entry → ... → arrival>
- 幂等 / 数据完整性：<第一条可执行路径必须保持的属性>
  - Stable claim ID：`INV-idempotency-integrity`
  - 到达路径：<跨模块 claim 必填；entry → ... → arrival>

到达路径规则：claim 文字里出现两个以上模块/边界的名字时必填；三条安全不变量均按跨模块 claim 填写。到达路径上任意一段被 mock / fake / in-memory 替身替换时，该 claim 的证据不成立。

早期路径可以缩小格式、入口或已授权主体范围，但只能做到“纵切窄、属性不薄”。Ticket 只有在全部 required claims 的当前 revision/environment evidence 齐全后才进入最终 acceptance。

## 阻塞依赖

- <implementation|acceptance|release>: <ticket-id>

没有阻塞边时填写 `None`。依赖类型只允许 `implementation | acceptance | release`。不要添加 worker ownership、文件级步骤或 Task 进度。
