# 审核员输入规定

只在耐久交接 Checkpoint 走到审核步骤时读取本文件。审核员同审两个对象：handoff 文件与 continuation prompt 草稿。

## 必须提供给审核员 subagent 的材料

1. handoff 文件路径（审核员自行读取全文）。
2. fresh git 输出原文：`git status --short --branch`、`git log -1 --oneline`，必须是 commit 之后采集的。
3. 外部状态清单：本会话已发生的 issue/PR/comment/邮件等外部动作及链接。
4. 用户协作偏好：明确给过的原话或要点，并标注哪些只是 inferred。
5. 审核规则：`rules/logger-handoff-quality-gate.md` 的路径，要求按其必查项和输出格式审核。
6. continuation prompt 草稿：内联文本提供，不落盘（continuation prompt 绝不写成第二个文件）。审核通过后，该草稿原样用于 `create_thread` 或 chat 移交，不再二次改写。

## 审核循环上限

- 最多 2 轮 NEEDS CHANGES，上限覆盖 handoff 与 prompt 草稿两个对象。
- 第 2 轮后仍有非阻塞意见时，把残余风险写进 handoff 的 Verified / Not Verified 或 Open Issues，带风险放行，不再循环。
- 审核员只评质量，不实现代码，不推进任务。
