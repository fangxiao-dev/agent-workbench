# Custom Rules（个人经验积累）

这个文件存放从实践中提炼出来的判断标准。
它不是官方文档的复述，而是你在多 agent 协作里反复验证过的经验。

每次你发现某个 agent setup 特别好或特别差，都把结论收敛到这里。
这个文件会随 workbench 版本迭代，形成你自己的审查基线。

---

## Rule C1: 先写宿主无关规则，再补宿主差异

**原则**：优先把 instruction 文件写成“通用行为规则 + 宿主差异说明”的结构，而不是从一开始就绑定某个宿主的专有术语。

**来源**：同一项目往往同时给 Codex、Claude、Gemini 使用。若规则全部写死在某个宿主术语里，迁移和审查成本会快速上升。

✅ 好的写法：
```markdown
## Required verification
- Run the project test command before claiming completion.
- If a host requires a special verification wrapper, document it in a host-specific note.

## Host notes
- Codex: prefer `rg` for repo search when available.
- Claude: check project and global instructions for conflicts.
```

❌ 差的写法：
```markdown
Always follow Claude memory rules.
Use Claude subagents for every task.
If Claude says X, do X.
```

**差在哪**：前者先表达项目真正想要的行为，再补充宿主差异；后者把项目规范错误地等同于某一个工具的品牌规范。

---

## Rule C2: 指令文件要优先服务执行，不要写成宣言

**原则**：instruction 文件应该优先包含项目上下文、执行命令、验证步骤、禁区和边界，而不是口号式价值观。

**来源**：很多低质量配置写满“be helpful”“follow best practices”，但对 agent 实际没有可操作价值。

✅ 好的写法：
```markdown
## Verification
- Run `npm test`
- Run `npm run build`
- Do not claim completion unless both exit with code 0.
```

❌ 差的写法：
```markdown
Write clean code.
Be thoughtful.
Make sure everything works.
```

**差在哪**：差的写法无法转化为可执行行为，也无法在 review 中稳定判断是否满足。

---

## Rule C3: 验证规则必须包含目录、命令和成功条件

**原则**：验证要求必须让 agent 知道在哪里运行、运行什么、什么结果才算通过。

✅ 好的写法：
```markdown
## Verification
- From `web/`, run `npm test`.
- From `web/`, run `npm run build`.
- Do not claim completion unless both commands exit with code 0.
```

❌ 差的写法：
```markdown
Run the tests and make sure the build is fine.
```

**差在哪**：差的写法没有工作目录、命令或完成标准；不同 agent 会猜出不同流程。

---

## Rule C4: 把事实、规则、工具偏好和安全禁区分开

**原则**：instruction 文件应该按用途分区。项目事实、行为规则、工具偏好、验证步骤、安全禁区混在一起时，重要约束会被淹没。

✅ 好的分区：
```markdown
## Project structure
## Commands
## Verification
## Safety boundaries
## Host notes
```

❌ 差的写法：
```markdown
The app uses Next.js. Be polite. Never delete data. Use pnpm.
The API is in src/api. Ask before risky work. Tests are important.
```

**差在哪**：agent 必须自己分类，审查者也难以判断哪些是事实、哪些是强制规则。

---

## Rule C5: 宿主专属能力只能写在宿主说明里

**原则**：Claude subagents、Codex workspace rules、Gemini activation tools 等宿主能力应该放在 host-specific notes 中。项目规则本身应该先表达宿主无关的意图。

✅ 好的写法：
```markdown
## Required behavior
- Read project instructions before editing code.

## Host notes
- Claude: use subagents for independent research tasks when available.
- Codex: use the repo search rule from AGENTS.md before falling back to other search tools.
```

❌ 差的写法：
```markdown
Always use Claude subagents. All agents must follow Claude memory rules.
```

**差在哪**：其他宿主无法执行这些规则，且项目政策被错误绑定到某个品牌工具。

---

## Rule C6: 安全边界要明确到操作类别

**原则**：涉及 secrets、生产环境、外部系统、删除、迁移、部署、sudo/admin 权限时，指令必须明确允许条件和禁止条件。

✅ 好的写法：
```markdown
## Safety boundaries
- Never commit `.env*` or credentials.
- Do not run production migrations without explicit user approval.
- Do not delete user data or stop unrelated local services.
```

❌ 差的写法：
```markdown
Use sudo when needed.
The production database password is prod123.
Clean up anything that looks stale.
```

**差在哪**：差的写法暴露 secrets，并鼓励高权限或破坏性操作但没有审批边界。

---

## Rule C7: 审查建议要改行为，不只改措辞

**原则**：agent setup 审查的价值在于降低执行风险。建议应该说明要新增、删除、移动或收紧哪类规则，而不只是把文字润色得更好看。

✅ 好的建议：
```markdown
Add a Verification section with exact commands and success criteria.
Move Claude-only subagent guidance under Host notes.
Remove the hardcoded API key and replace it with "read from environment".
```

❌ 差的建议：
```markdown
Make the file clearer.
Use better wording.
Add more best practices.
```

**差在哪**：差的建议不能直接指导实现，也不能在后续复查中判定是否完成。
