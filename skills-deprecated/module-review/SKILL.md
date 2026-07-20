---
name: module-review
description: >
  Deprecated compatibility archive. Do not invoke for new reviews; use `do-review`
  with `standards-review` and `spec-review` instead.
deprecated: true
disable-model-invocation: true
---

# Module Review (Deprecated)

This is the preserved pre-three-track module-review workflow. It is retained only for historical compatibility and auditability; it is not an active reviewer and is not registered in the canonical reviewer registry.

审查 `HEAD` 与用户指定固定点之间的 diff，并保持两个判断轴独立：

- **Standards**：代码是否符合仓库已有的编码规范。
- **Spec**：代码是否忠实实现来源 issue、PRD 或 spec。

两个轴使用并行 subagent，避免彼此的上下文污染；主 session 只负责准备输入和汇总结果。

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

1. commit message 中的 issue 引用（如 `#123`、`Closes #45`、GitLab `!67`），按当前仓库的 issue tracker 规则获取完整内容；
2. 用户传入的路径；
3. `docs/`、`specs/`、`.scratch/` 中与 branch 或 feature 匹配的 PRD/spec；
4. 都找不到时询问用户。用户确认没有 spec 时跳过 Spec reviewer，并明确报告 `no spec available`。

### 3. 定位 Standards 来源

收集仓库中所有描述代码应如何编写的文件，例如 `AGENTS.md`、`CODING_STANDARDS.md`、`CONTRIBUTING.md`。

在仓库规范之外，Standards 轴始终带上 Fowler code-smell baseline。它只是启发式，不是第三个审查轴；仓库规范优先，smell 始终是 judgement call，工具已经可靠执行的规则不重复报告。

Standards reviewer 还必须使用 `/codebase-design` 的 deep module vocabulary：检查 module interface 的 depth / leverage、seam、locality 和 adapter 是否有真实依据；interface 包含调用方必须知道的 invariants、错误模式和顺序约束。

逐项匹配 diff：

- **Mysterious Name**、**Duplicated Code**、**Feature Envy**、**Data Clumps**、**Primitive Obsession**、**Repeated Switches**。
- **Shotgun Surgery**、**Divergent Change**、**Speculative Generality**、**Message Chains**、**Middle Man**、**Refused Bequest**。

### 4. 并行运行两个 Reviewer

同时派发两个 general-purpose subagent。

Standards reviewer 输入完整 diff、commit 列表、Standards 来源、上述 smell baseline 与 codebase-design 基线；逐 file/hunk 报告仓库规范硬性违规和 judgement call，控制在 400 words 内。

Spec reviewer 输入完整 diff、commit 列表和 spec 路径或完整内容；报告遗漏需求、部分实现、scope creep、错误行为，以及 interface/seam、module boundary、兼容窗口、状态机和跨 slice seam 的 contract fidelity，控制在 400 words 内。

Spec reviewer 已承担 contract/interface/seam drift；不得额外派发第三个 drift reviewer，也不得把这项检查转移到 Standards 轴。

没有 spec 时不派发 Spec reviewer。

### 5. 汇总

随后在 `## Standards` 和 `## Spec` 下分别呈现两个 canonical evidence 报告，不合并或跨轴重新排序 finding。

最后汇总每个轴的 finding 数量以及各轴内部最严重的问题，不选出跨轴的单一“最严重问题”。

## 为什么必须分成两轴

- 完全符合编码规范、但实现了错误需求：**Standards pass，Spec fail**。
- 完全实现需求、但破坏仓库约定：**Spec pass，Standards fail**。

并列报告可以防止一个轴的好结果掩盖另一个轴的问题。
