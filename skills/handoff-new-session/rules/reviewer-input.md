# 审核员输入规定

只在耐久交接 Checkpoint 走到审核步骤时读取本文件。

## 必须提供给审核员 subagent 的材料

1. handoff 文件路径（审核员自行读取全文）。
2. fresh git 输出原文：`git status --short --branch`、`git log -1 --oneline`，必须是 commit 之后采集的。
3. 外部状态清单：本会话已发生的 issue/PR/comment/邮件等外部动作及链接。
4. 用户协作偏好：明确给过的原话或要点，并标注哪些只是 inferred。
5. 审核规则：`rules/logger-handoff-quality-gate.md` 的路径，要求按其必查项和输出格式审核。

## 审核循环上限

- 最多 2 轮 NEEDS CHANGES。
- 第 2 轮后仍有非阻塞意见时，把残余风险写进 handoff 的 Verified / Not Verified 或 Open Issues，带风险放行，不再循环。
- 审核员只评质量，不实现代码，不推进任务。
