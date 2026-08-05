---
name: plain-language-check
description: "Use whenever the user asks to scan or clean project documents for invented, pseudo-standard, jargon-heavy, or hard-to-understand terms. Check English phrases, Chinese calques, mixed Chinese-English wording, headings, and filenames, especially in architecture, implementation plans, module knowledge, ADRs, specs, and task packages. Separate ordinary wording fixes from useful technical tokens and contract-impacting decisions before rewriting anything."
---

# 说人话检查

审查项目文档中的英文术语、中文直译词和中英混搭短语，找出“像业界标准、实际是当前作者临时拼出来”的表达。标题、文件名和链接文字也在范围内，因为伪术语常会沿这些位置固化。目标是提高可理解性，不是把所有英文翻译成中文，也不是禁止项目使用英文。

## 先读实例

开始扫描前，先阅读 [`references/plain-language-examples.md`](references/plain-language-examples.md)。

实例用于帮助你形成判断，不是固定黑名单或白名单。遇到新短语时，要类比实例背后的语言问题；不要因为新短语没有出现在实例里就自动放行，也不要因为它含有相同单词就自动判定有问题。

## 启发式判断

把一个短语列为候选，至少要有两个信号同时成立：

1. **名词堆叠**：多个抽象词拼在一起，例如运行时、权威、证据、就绪、接缝、账本、能力、采用等词没有明确对象。
2. **伪专名感**：标题式大小写、连字符或大写组合让它看起来像业界固定名称，但项目没有稳定外部含义。
3. **说不清边界**：读者不能仅凭短语判断它描述的对象、动作、责任边界或验收结果。
4. **可以自然拆开**：用普通中文、一个已有技术术语，或“对象 + 动作 + 结果”就能说清楚。

单纯“两个以上英文单词”不构成问题。常见技术术语、明确的产品/模块/字段/API/命令名、skill 名称和用户已经认可的项目术语，不要仅因长度而标记。

`adoption` 在“复用现有计划/规格”或项目内部接入验证中尤其需要检查，但不是看到这个词就机械判错。`Domain Event` 与 `Business Event` 不得擅自合并；`Typed Domain Event` 可以理解，但不应伪装成统一标准术语；`Business Event Runtime` 要拆成具体的记录、持久化、投递、查询或追踪能力。

## 三种处理结果

候选短语不等于“一律翻译”。先判断它属于哪种处理：

1. **直接替换**：短语的边界含糊或伪专名感明显，用普通中文或“对象 + 动作 + 结果”可以完整表达，而且替换不改变业务承诺、authority、验收条件或 Gate。
2. **保留专业 token，并用中文说明**：`session`、`identity` 等专业 token 本身准确，问题只在周围句子像拼装术语。保留 token，把主体改成中文动作和对象，例如“从 session 解析并重验当前身份”“环境 identity 与实际资源绑定”。
3. **涉及合同决策**：短语背后实际固定了 scope、authority、验收条件、兼容承诺或 Gate。此时不要把它当文案悄悄改掉；标记被隐藏的决策及影响，等待 Owner 裁决，并在获批后交给拥有该合同的 requirement/spec 流程。

删除短语后若行为承诺也随之改变，它就是第三类。语言检查负责暴露这个选择，不负责代替 Owner 作出选择。

## 扫描流程

1. **确定范围**：记录绝对路径、分支/HEAD、worktree 状态、目标目录、文件总数和排除项。扫描正文、标题和目标目录中的文件名；若用户指定一个问题包作为例子，使用它校准其他文档，不重复把已知样本计入候选。
2. **保留原文**：记录短语实际出现的大小写、连字符、中英文混排形式、文件和行号；文件名候选记录完整路径。不要先自行改写再判断。
3. **应用启发式并分类**：结合实例判断是否至少有两个信号；区分高疑似、中疑似和暂不列出，再标记为“直接替换”“保留并说明”或“合同决策”。不要把“疑似”写成行业定论。
4. **隔离合同影响**：如果建议会改变 scope、authority、验收条件、兼容承诺或 Gate，说明被隐藏的选择和 blast radius，不提供会让它看似纯编辑的替换稿。普通语言项不因此升级流程。
5. **分批反馈**：默认每批最多 20 个候选，每项给出原文、位置、疑似等级、处理类型、具体疑点和一种说人话的方向；合同决策项给出需要裁决的问题而不是默认答案。
6. **吸收校准**：用户对当前批次有批注时，按批注调整启发式；用户明确说“未批注表示同意”时，当前批次未批注项视为同意。不要把一次批次校准扩张成永远适用的词表。
7. **保持只读**：除非用户另行授权，不修改文档、不批量替换、不提交、不发布。
8. **按批准批次回写**：用户明确授权修改后，先读取 [`references/apply-approved-changes.md`](references/apply-approved-changes.md)，只处理已批准的当前批次和批注，不顺手扩大扫描。

## 输出与完成标准

首段说明总范围、当前 `scan/extract` 阶段、已处理量、候选量、剩余量、整体是否 closed，以及等待的 owner 决定。不要把扫描完成写成术语清理完成。

使用紧凑表格：

```markdown
| # | 原文短语 | 位置 | 等级 | 处理 | 疑点与说人话方向 |
|---:|---|---|---|---|---|
| 1 | `...` | `path:line` | 高 | 直接替换 | ... |
```

当用户只是校准上一批时，只回应批注和校准结论，不顺手扩大扫描范围。一个批次完成的条件是：数量可对账、每个候选有证据位置和判断理由、实例已读取、没有把疑似候选写成行业结论、没有未经授权的文件修改。
