---
name: module-review
description: >
  Impl-Package 体系的 implementation-level module review：当固定比较点以来的改动
  需要分别检查 Standards（仓库规范）与 Spec（来源需求/contract fidelity）时使用。
  两个轴由并行 reviewer 独立审查并并列汇报；适用于 branch、PR、work-in-progress
  或 “review since X”。
---

# Module Review

审查 `HEAD` 与用户指定固定点之间的 diff，并保持两个判断轴独立：

- **Standards**：代码是否符合仓库已有的编码规范。
- **Spec**：代码是否忠实实现来源 issue、PRD 或 spec。

两个轴使用并行 subagent，避免彼此的上下文污染；主 session 只负责准备输入和汇总结果。

## Impl-Package 触发映射

对 implementation package，出现任一条件时必须选择 module-review：

- `spec.md` 的 Composition 声明 `tickets=true` 或 `dag=true`；
- 即使两者都为 false，spec 明确声明 interface、state machine、module boundary 或 seam 变化。

这是调用者的触发映射，不是第三个 reviewer 或自动调度器。调用者仍必须提供 fixed point；本 skill 不会因 package 目录、当前分支或工作树状态静默猜测比较基线。纯局部且没有上述契约变化的单切片可以不触发，但仍适用其余必要 review。

项目应通过 `/setup-matt-pocock-skills` 提供 issue tracker 规则；缺少 `docs/agents/issue-tracker.md` 时先补 setup。

## 工作流

### 1. 固定比较点

用户给出的 commit SHA、branch、tag、`main`、`HEAD~5` 等就是 fixed point。用户没有指定时必须询问，不能自行猜测。

只确定一次 diff 命令：

```text
git diff <fixed-point>...HEAD
```

同时记录：

```text
git log <fixed-point>..HEAD --oneline
```

继续前用 `git rev-parse <fixed-point>` 确认引用有效，并确认 diff 非空。错误引用或空 diff 在这里 fail fast，不要等到并行 reviewer 内部才发现。

### 2. 定位 Spec 来源

按顺序查找：

1. commit message 中的 issue 引用（如 `#123`、`Closes #45`、GitLab `!67`），按 `docs/agents/issue-tracker.md` 获取完整内容；
2. 用户传入的路径；
3. `docs/`、`specs/`、`.scratch/` 中与 branch 或 feature 匹配的 PRD/spec；
4. 都找不到时询问用户。用户确认没有 spec 时跳过 Spec reviewer，并明确报告 `no spec available`。

### 3. 定位 Standards 来源

收集仓库中所有描述代码应如何编写的文件，例如 `AGENTS.md`、`CODING_STANDARDS.md`、`CONTRIBUTING.md`。

在仓库规范之外，Standards 轴始终带上以下 Fowler code-smell baseline。它只是启发式，不是第三个审查轴，并受两个规则约束：

- **仓库规范优先。** 仓库明确认可的写法覆盖 baseline，不报告冲突 smell。
- **始终是 judgement call。** Smell 只能标为可能的问题，不能当作硬性违规；工具已经可靠执行的规则不重复报告。

Standards reviewer 还必须使用 `/codebase-design` 的 deep module vocabulary：检查 module 的 interface 是否以小表面承载足够行为（depth / leverage），变更是否把知识与验证保持在合适的 seam 以维持 locality，以及新增 adapter 是否有真实的可变性依据。这里的 interface 包含调用方必须知道的 invariants、错误模式和顺序约束；不要把它缩窄成类型签名。将这些作为 repository standards 的设计基线，而不是新增一个 drift reviewer。

逐项匹配 diff：

- **Mysterious Name**：名称无法说明职责或内容。→ 重命名；若无法诚实命名，说明设计仍含糊。
- **Duplicated Code**：多个 hunk 或文件出现相同逻辑形状。→ 抽取共享形状。
- **Feature Envy**：方法访问其他对象的数据多于自身数据。→ 把行为移到它依赖的数据一侧。
- **Data Clumps**：相同字段或参数组合反复同行。→ 提炼为一个类型。
- **Primitive Obsession**：primitive/string 代替值得命名的领域概念。→ 建立小型领域类型。
- **Repeated Switches**：同一类型的 `switch`/条件链重复出现。→ 用多态或共享映射集中表达。
- **Shotgun Surgery**：一个逻辑变化迫使许多文件分散修改。→ 把共同变化收进一个 module。
- **Divergent Change**：一个文件因多个无关原因被修改。→ 按变化原因拆分。
- **Speculative Generality**：加入 spec 未要求的抽象、参数或 hook。→ 删除并收回到真实需求。
- **Message Chains**：调用者依赖很长的 `a.b().c().d()` 导航。→ 在起点隐藏导航细节。
- **Middle Man**：class/function 主要只是向后转发。→ 移除中间层，直接调用真正目标。
- **Refused Bequest**：子类或实现者忽略、覆盖了大部分继承合同。→ 放弃继承，使用组合。

### 4. 并行运行两个 Reviewer

同时派发两个 general-purpose subagent。

Standards reviewer 输入：

- 完整 diff 命令和 commit 列表；
- Standards 来源文件；
- 上述 smell baseline 全文；
- `/codebase-design` 的 deep module、interface、seam、adapter、depth、leverage 和 locality 基线；
- 要求逐 file/hunk 报告：仓库规范硬性违规要引用规则文件，baseline smell 要点名并引用 hunk；区分 hard violation 与 judgement call；仓库规范覆盖 baseline；跳过工具已执行的规则；控制在 400 words 内。

Spec reviewer 输入：

- 完整 diff 命令和 commit 列表；
- spec 路径或完整内容；
- 要求报告：缺失或部分实现的需求、diff 中未被要求的 scope creep、看似实现但行为错误的需求；并检查 implementation 的 interface/seam 是否忠实遵守 spec、plan 或 dag 声明的 contract fidelity（包括兼容窗口、状态机和跨 slice seam）。每项引用 spec 原文；控制在 400 words 内。

Spec reviewer 已承担 contract/interface/seam drift；不得额外派发第三个 drift reviewer，也不得把这项检查转移到 Standards 轴。

没有 spec 时不派发 Spec reviewer。

### 5. 汇总

面向 owner 的开场遵循 [Owner-Facing Reporting Contract](../../references/owner-facing-reporting.md)：先说明审查的功能范围、Standards/Spec 两轴是否各自通过、阻塞项数量、整体能否进入 gate，以及需要 owner 决定什么。不要用轴名、finding code 或文件路径代替合入判断。

随后在 `## Standards` 和 `## Spec` 下分别呈现两个 canonical evidence 报告，可轻微清理格式，但不要合并或跨轴重新排序 finding。

最后用一行汇总：每个轴的 finding 数量，以及各轴内部最严重的问题。不要选出跨轴的单一“最严重问题”。

## 为什么必须分成两轴

- 完全符合编码规范、但实现了错误需求：**Standards pass，Spec fail**。
- 完全实现需求、但破坏仓库约定：**Spec pass，Standards fail**。

并列报告可以防止一个轴的好结果掩盖另一个轴的问题。
