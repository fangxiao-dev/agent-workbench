# Registry 规范

`registry/` 是第三方资产的人工清单。它只回答“哪些资产是第三方、从哪里来、如何重新获取”，不记录宿主路径和机器状态。

## Third-party Skills

`registry/third-party-skills.md` 是第三方 skills 的唯一仓库内登记入口。

格式：

```markdown
# Third-party Skills

| Skill | 来源 | 获取方式 | 备注 |
|-------|------|----------|------|
| frontend-design | `anthropics/skills` | `npx skills add anthropics/skills@frontend-design -g -y` | 已放入 `skills/frontend-design/` |
```

规则：

- 只登记第三方 skill，不登记本仓库自建 skill。
- 独立第三方 skill 放在 `skills/<name>/`；plugin-owned skill 放在 `plugin-marketplace/plugins/<plugin>/skills/<name>/`。
- `获取方式` 写 `npx skills add ...`、来源说明或人工迁移说明，保证未来能重新获取。
- 不登记本地路径、宿主、安装状态、更新时间或机器可读 JSON。
- 根目录 `skills-lock.json` 如果由 `npx skills` 生成，属于工具状态，继续保持 ignored。

## Plugins

`registry/plugins.md` 保留为插件和 MCP 类资产清单。插件按安装单位登记，不展开插件内部附带的每个 skill、agent 或 command。

插件清单可以包含状态列，因为插件是否启用通常取决于宿主配置，不等同于仓库内 skill payload 的正式内容。

## 不再使用

旧的 skills lock JSON 不参与当前 registry 设计。第三方 skills 只通过 `registry/third-party-skills.md` 做人工登记。
