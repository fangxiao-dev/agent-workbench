# Explain Diff HTML Skill 优化设计

日期：2026-07-27
状态：已实现并完成定向验证（2026-07-27）

## 范围

将 Geoffrey Litt 的 `explain-diff-html` Gist 迁移为 agent-workbench 的本地 Skill，并把它从“每次由模型自由生成整页 HTML”优化为“模型生成内容规格，固定渲染器生成页面”。本轮只维护本地副本，不修改用户级 host 安装态，也不注册为外部安装包。

上游来源：[geoffreylitt/a29df1b5f9865506e8952488eac3d524](https://gist.github.com/geoffreylitt/a29df1b5f9865506e8952488eac3d524)。`find-skills` 已检索同类能力；未发现需要替代用户指定来源的现有本地 Skill。

## 原版保留的行为

- 解释代码变更前调查周边源码、测试和文档。
- 用 Background、Intuition、Code 和 Quiz 建立可读的教学叙事。
- 产出一个仓库外、日期前缀、自包含的 HTML 文件。
- 使用响应式布局、语义化 HTML、图示、调用框和代码块。
- 交付前检查 HTML 完整性、代码块空白和 Quiz 交互。

## 本地优化

| 问题 | 优化 | 可验证证据 |
| --- | --- | --- |
| 模型每次重写相同 CSS/JS，导致模板漂移 | 固定 `scripts/render_explanation.py`，Skill 只要求生成 JSON 内容规格 | 相同模板由脚本渲染，Skill 不再要求手写页面骨架 |
| 正确答案容易总在固定位置或最长 | 渲染器按标题派生确定性旋转，再按题号使用平衡的位置序列；这只消除位置偏差，不提供安全随机性 | 脚本固定五题并检查选项数量、唯一正确项；渲染结果可重复 |
| diff/PR 文本可能包含 Prompt Injection 或 HTML/JS | 生成阶段要求把 diff 当被动数据并忽略其中指令；渲染阶段统一 HTML 转义、CSP 和离线模板，禁止外部资源和网络请求 | 两层安全边界分别写入 Skill；`esc()` 只输出转义文本 |
| 内容结构依赖模型自由发挥 | `references/content-schema.md` 规定三段内容、七类块和 Quiz 数据形状 | 渲染器在写文件前校验 schema |
| “解释了什么”与“是否验证”容易混淆 | Skill 要求记录旧行为、新行为、因果路径、边界和验证限制 | Workflow 每一步有可观察的 completion criterion |

## 文件布局

```text
skills/explain-diff-html/
  SKILL.md
  references/content-schema.md
  scripts/render_explanation.py
```

## 非目标

- 不实现 PR/代码仓库的自动抓取或浏览器自动化。
- 不把解释文档作为仓库 current knowledge；产物默认在仓库外。
- 不让渲染器执行内容规格中的 HTML、JavaScript、网络请求或命令。
- 不新增 Notion 输出；原 Gist 的 Notion 变体不在本轮迁移范围。
- 不引入第三方 Python 依赖或复杂前端框架。
- 不解析 Markdown；排版能力通过纯文本和结构化 block 类型有意收敛。

## 成功标准

1. `skills/explain-diff-html/SKILL.md` 能独立指导一次 Explain Diff HTML 任务。
2. 内容规格缺少必需段落、Quiz 数量错误、选项无唯一正确项时，渲染器拒绝写出产物。
3. 合法规格可生成单一离线 HTML，包含 Background、Intuition、Code、Quiz，且恰好五道题。
4. 生成的代码块使用 `<pre><code>`，页面不包含外部脚本、样式、字体或网络请求。
5. 目标 Skill 经过至少一次 subagent 审核和一次 blind 多方讨论，并根据有证据的意见修订。

Quiz 是独立的顶层区域，不计入三个内容 section；渲染器拒绝覆盖已有输出文件，避免误写历史解释。

## 审核重点

- 是否真的减少了模型自由生成模板的空间，而不是只增加说明文字。
- JSON schema 是否足以表达背景、流程、对比、代码和边界，而不迫使模型输出 HTML。
- Quiz 的正确答案位置是否可预测，反馈是否在选择后才显示。
- 转义和离线约束能否抵御不可信 diff 中的 HTML、JavaScript 和 Prompt Injection。
- Skill 是否会在目标不明确或证据不足时明确假设，而不是编造上下文。

## Blind Opening 记录

2026-07-27 运行 `discuss-ledger --mode blind --agents codex,claude`。独立结果提出：明确 Quiz 顶层边界、声明纯文本而非 Markdown、区分确定性乱序与安全随机、让脚本验证仓库外路径并拒绝覆盖、分离模型层 Prompt Injection 防护与渲染层转义、为不支持的内容定义降级方式。上述问题已纳入修订；确定性乱序明确只消除位置偏差，不承诺安全不可预测性。完整盲审产物位于 `%TEMP%/discuss-ledger/blind-explain-diff-html-optimization-7cc1a40f.md`。

## Subagent 审核记录

2026-07-27 完成两次只读 subagent 审核。第二次确认了四个必须处理的问题：输出路径原本先检查存在性再写入，存在并发覆盖竞态；`assumption` 未校验为字符串；Quiz 将正确性和反馈直接写入 DOM 属性；Skill 虽要求 JSON 规格放在仓库外，脚本却未执行这一约束。渲染器改为以 `"x"` 独占创建输出文件，在写入前验证 `assumption`，拒绝仓库内的输入规格，并将 Quiz 状态放入固定脚本闭包、反馈放入无正确性标记的模板元素。静态离线 HTML 不能保证源码层的答案保密，Skill 已明确它仅用于学习交互。测试同步覆盖该类型错误、仓库内输入拒绝、无显式答案 DOM 属性，以及离线模板中不得出现外部资源与网络 API 的回归标记。不同标题不保证答案位置一定变化，因为该行为不是安全或功能契约；标题派生的确定性旋转只用于降低跨页面固定位置偏差。

## 最终验证

- `tests/test_explain_diff_html_renderer.py`、`tests/test_discuss_router.py`、`tests/test_blind_opening.py`：15 项通过。
- `py_compile`：渲染器通过。
- `git diff --check`：通过；仅有既有的 registry 行尾转换提示。
- 全量 `pytest` 未能完成收集：仓库现有两个同名测试模块冲突，另有三个测试依赖 Python 3.11 的 `tomllib`/模块路径；这些失败未触及本次新增文件。
