---
name: feishu-whiteboard
version: 1.0.0
description: >
  飞书画板：查询和编辑飞书云文档中的画板。支持导出画板为预览图片、导出原始节点结构、使用多种格式更新画板内容。
  当用户需要查看画板内容、导出画板图片、编辑画板时使用此 skill。不负责：飞书云文档内容编辑（feishu-doc）、文档内嵌电子表格/Base（feishu-sheets / feishu-base）。
metadata:
  requires:
    bins: ["lark-cli"]
  cliHelp: "lark-cli whiteboard --help"
---

> [!IMPORTANT]
> - 运行 `lark-cli --version`，确认可用，无需询问用户。
> - 运行 `npx -y @larksuite/whiteboard-cli@^0.2.11 -v`，确认可用，无需询问用户。

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../feishu-shared/SKILL.md`](../feishu-shared/SKILL.md)，其中包含认证、权限处理**

---

## 快速决策

**身份**：画板操作默认使用 `--as user`。仅当需要以应用身份上传时使用 `--as bot`。

| 用户需求                                    | 行动                                                                                            |
|-----------------------------------------|-----------------------------------------------------------------------------------------------|
| 查看画板内容 / 导出图片                           | [`+query --output_as image`](references/feishu-whiteboard-query.md)                             |
| 获取画板的 Mermaid/PlantUML 代码               | [`+query --output_as code`](references/feishu-whiteboard-query.md)                              |
| 检查画板是否由代码绘制                             | [`+query --output_as code`](references/feishu-whiteboard-query.md)                              |
| 修改节点文字/颜色（简单改动）                         | `+query --output_as raw` → 手动改 JSON → `+update --input_format raw`                            |
| 用户**已提供** Mermaid/PlantUML 代码，或明确指定用该格式 | 自己生成/使用代码 → [`+update --input_format mermaid/plantuml`](references/feishu-whiteboard-update.md) |
| 新建/创作复杂图表（架构/流程/组织等）                    | → **[§ 创作 Workflow](references/feishu-whiteboard-workflow.md#创作-workflow)**                     |
| 修改/重绘已有画板                               | → **[§ 修改 Workflow](references/feishu-whiteboard-workflow.md#修改-workflow)**                     |

## Shortcuts

| Shortcut | 说明 |
|---|---|
| [`+query`](references/feishu-whiteboard-query.md) | 查询画板，导出为预览图片、代码或原始节点结构 |
| [`+update`](references/feishu-whiteboard-update.md) | 更新画板，支持 PlantUML、Mermaid 或 OpenAPI 原生格式 |

---

## 不在本 skill 范围
- 文档内容编辑 → feishu-doc [feishu-doc](../feishu-doc/SKILL.md)
- 在文档中创建画板 → [feishu-doc-whiteboard.md](../feishu-doc/references/feishu-doc-whiteboard.md)
- 表格 / Base 操作 → [feishu-sheets](../feishu-sheets/SKILL.md) / [feishu-base](../feishu-base/SKILL.md)
