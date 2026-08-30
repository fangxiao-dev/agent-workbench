---
name: screenshot-to-ui
description: 仅供用户显式调用 `$screenshot-to-ui` 的截图驱动 UI/UX 迭代入口。
---

# 截图到真实 UI

这是 user-invoked Skill。仅当用户在当前消息中显式调用 `$screenshot-to-ui` 时执行；截图附件、自然语言 UI 请求、继承历史或其他 Skill 引用均不构成调用。没有显式调用时立即停止，不读取引用文件，也不执行以下步骤。

1. **先描述。** 对照截图和真实页面，简要说明问题、改进方向、保持不变的行为，以及 viewport / locale 风险。
2. **选路线。** 局部排版、样式或文案直接进入真实前端；布局、层级或交互方向不确定时，读取 [`../prototype/SKILL.md`](../prototype/SKILL.md) 和 [`../prototype/UI.md`](../prototype/UI.md)，制作 2–3 个 standalone HTML 方案。进入真实实现前，等待用户确认文字方向或原型方案。
3. **按 surface 实现。** 进入真实实现前，若用户尚未明确承载位置，先确认使用当前 worktree 还是独立 worktree；未经明确选择，不创建或切换 worktree。用户已经指定当前或独立 worktree 时直接沿用，不重复询问。基于真实前端实现，先复用现有组件；同一语义模式多处重复时优先抽 UI 模板。保持业务逻辑、权限、数据和副作用边界不变。
4. **处理多语言。** 像素级复刻只绑定参考 viewport 和 locale；其他 locale 保持结构、design token、可读性和无溢出。
5. **验证并交付。** 按仓库要求运行 focused tests、typecheck 或 affected build。使用当前 worktree 时，验证后直接交给用户热加载验收；使用独立 worktree 时，提交限定路径，并在确认目标 worktree、未提交改动和合入路径后合入正在运行的 dev 环境。把 URL 交给用户热加载验收，后续反馈继续使用用户已选择的同一承载位置。

浏览器验收由用户负责；除非用户明确要求，不打开或控制浏览器，也不宣称视觉验收完成。
