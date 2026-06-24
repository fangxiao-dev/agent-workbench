
# docs +media-preview（预览文档素材）

> **前置条件：** 先阅读 [`../feishu-shared/SKILL.md`](../../feishu-shared/SKILL.md) 了解认证、全局参数和安全规则。

优先用于查看、预览文档中的图片或文件素材（`file_token`）。命令会把素材保存到本地路径，便于后续打开查看内容。

## 选择规则

- 用户说“看一下素材 / 图片 / 附件”“预览一下”时，优先使用 `docs +media-preview`
- 用户明确说“下载”时，使用 [`docs +media-download`](feishu-doc-media-download.md)
- 如果目标明确是画板 / whiteboard / 画板缩略图，不要使用 `+media-preview`，改用 `docs +media-download --type whiteboard`

## 命令

```bash
# 预览图片/文件素材
lark-cli docs +media-preview --token "Z1Fjxxxxxxxx" --output ./asset

# 指定输出文件名（带扩展名则不会自动补全）
lark-cli docs +media-preview --token "Z1Fjxxxxxxxx" --output ./asset.png
```

## 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--token <token>` | 是 | 素材 token，即 `file_token` |
| `--output <path>` | 是 | 本地保存路径；不带扩展名会自动补全 |

## token 从哪里来

- 若你是从文档内容里提取：`feishu-doc-fetch` 返回的 Markdown 里可能包含：
  - 图片：`<image token="..." .../>`
  - 文件：`<file token="..." name="..."/>`

## 参考

- [feishu-doc-fetch](feishu-doc-fetch.md) — 获取文档内容（用于提取 token）
- [feishu-doc-media-download](feishu-doc-media-download.md) — 明确下载素材，或下载画板缩略图
- [feishu-shared](../../feishu-shared/SKILL.md) — 认证和全局参数
