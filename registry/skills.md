# Third-party Skills

| Skill | 宿主 | 来源 | 状态 | 备注 |
|-------|------|------|------|------|
| find-skills | `.agents` skill manager | `vercel-labs/skills` | ✅ 已装 | 详细机器元数据见 `registry/skills.lock.json` |
| continuous-learning | `.agents` skill manager | `affaan-m/everything-claude-code` | ✅ 已装 | 详细机器元数据见 `registry/skills.lock.json` |
| skill-creator | `.agents` skill manager | `anthropics/skills` | ✅ 已装 | 详细机器元数据见 `registry/skills.lock.json` |

## 说明
- 机器可读元数据见 `registry/skills.lock.json`
- `skills.lock.json` 预期作为后续更新脚本的输入，`skills.md` 作为人工查阅入口
- ✅ 已装：当前机器上已可用
- ⬜ 待装：列入计划但尚未安装
- ⏸️ 暂停：保留记录但当前未启用
- 自建 skills 不登记在这里；这里只记录可独立安装的第三方 skill，且以“如何重装”为主
