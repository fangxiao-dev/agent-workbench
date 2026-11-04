---
name: grill-me-smartly
description: >
  用 Questioner 与 Answerer 两个 subagent 代 Owner 审问 plan 或 Spec：能由本地事实、代码、文档回答的问题由 Answerer 查证作答，
  只有新意图、偏好、风险取舍才回到 Owner。用于高风险 Spec gate，或希望审问不被等待 Owner 阻塞时。
---

# Grill Me Smartly

独立的 `/grilling` 由人回答每个问题；本 Skill 让 Answerer 代 Owner 回答一切可由本地事实、代码、文档查清的问题，只把真正的判断题（新意图、偏好、风险取舍）带回 Owner，工作不因等待 Owner 而停滞。

## 角色

- **Questioner subagent**：读取宿主 Skill 目录里的 `/grilling` 作为提问协议，按它的设计树、分批节奏和回复合同向 Answerer 提问，检查回答与证据，保留异议。`/grilling` 不可用时，每次提出下一个最高价值问题，点名分支并说明为何现在重要，最终报告“未加载 `/grilling`，本次使用简化降级”。
- **Answerer subagent**：先代 Owner 回答本地文件、代码、git 历史、文档、工具可解决的问题，每个答案引用证据；已确认的 Owner 决策可以引用。无法由事实回答的，写明事实基础与缺口，标 `needs_user`。
- **主控**：给两者目标材料快照、协议路径和已确认的 Owner 选择；审定 Answerer 的事实结论是否证据充分；把 `needs_user` 项按 `/grilling` 的 batch 与 reply contract 成批带回 Owner；Owner 的回答交还 Questioner 展开依赖分支。

## 完成标准

所有 material 分支满足其一：已有带证据的事实答案、已有 Owner 回答、或标为 `needs_user` 等待 Owner。未查清的事实与未处理的异议不算完成。

## Grill Review

完成后由主控交付一份短的中文 Grill Review，只含：

- 已解决的问题及其证据；
- `needs_user` 清单（含 Answerer 查到的事实基础）；
- 候选决策（附依据与影响）。

## Review Then Apply

Review 期间保持目标 plan、Decision、Spec 与源文档不变，过程材料只写 OS 临时目录。Owner 读过 Review 并明确批准后，才把已批准的决策写入 Decision/Spec，按目标文档已有章节吸收，合并重复表述，清理被替代的旧表述。subagent 共识只是候选，新产品意图、偏好或风险取舍须经 Owner 批准。
