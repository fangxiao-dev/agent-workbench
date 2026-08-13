# Matt Pocock 关于 AI agent 编码工作流的公开理念

调研范围：他本人的 AI Coding Dictionary、AI Hero 博客 / skill 文档页、2026-04-24 工作坊逐字稿、X 帖、以及 `mattpocock/skills` README。  
不覆盖：仅存在于 `skills/engineering/*/SKILL.md`、而公开论证缺失的内部细则。  
日期：2026-08-13。

标记约定：

- **明确说过**：能追溯到他署名的原文、词典条目、演讲或帖子。
- **推断**：从他的做法、相邻条目或二次转述推出；文中单独成段标出。
- 找不到公开论证的条目，写「未找到公开论证」，不编造。

---

## 1. Smart zone

### 他的原话 / 核心主张

词典定义（当前正式表述）：

> Early in a session the agent is in a "smart zone" — sharp, focused, recall is good. As the session grows it drifts into a "dumb zone": sloppier, forgetful, more mistakes — and more faithfulness hallucinations. Same model, same harness — just more context.
>
> On frontier models, the dumb zone commonly begins around 125K-150K tokens — though this is debated.
>
> Plan around the smart zone, not the window — the practical budget for a task is the tokens the agent works well within, not the tokens it can technically hold.

来源：

- [Smart zone | AI Coding Dictionary](https://www.aihero.dev/ai-coding-dictionary/smart-zone)
- 同源文本：[dictionary/Smart zone.md](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Smart%20zone.md)

阈值在公开材料里有过演进，不要混成一个数：

| 时间 | 他说的数字 | 出处 |
| --- | --- | --- |
| 2026-04-24 工作坊 | 「大约 40%，我现在的新标记是大约 100k」；「不管窗口是 1M 还是 200k，都会在这里开始变蠢」 | [工作坊逐字稿](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md) |
| 同期 Ralph 文 | 表格写成「前 40% = smart zone」 | [Why the Anthropic Ralph plugin sucks](https://www.aihero.dev/why-the-anthropic-ralph-plugin-sucks) |
| 2026-07-23 推文 | 「~150K tokens is the smart zone」；可以提前 compact，「但只在到达 phase boundary 时」 | [X](https://x.com/mattpocockuk/status/2070191683279360079) |
| 2026-08-07 推文 | 「IMO smart zone ends around 150K tokens」 | [X](https://x.com/mattpocockuk/status/2085530959873515861) |
| 2026-08-11 推文 | 把任务总 token 估计值除以 **150k**（「SOTA agents 的大约 smart zone」）得到票数 | [X](https://x.com/mattpocockuk/status/2087111966854730148) |

机制层他绑定到 attention：

> Each token has a finite amount of influence to distribute across the rest of the context. … An instruction that was the loudest thing at 10k tokens of context is background hum at 150k. … the model doesn't forget; the signal gets lost in the noise.

来源：[Attention budget](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Attention%20budget.md)、[Attention degradation](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Attention%20degradation.md)

2026-04 工作坊里，他把这个想法归给 Dex Horthy / HumanLayer，并用足球联赛类比：每加一个 token，就像联赛里多一支球队，对阵关系按二次方增加。

来源：[工作坊逐字稿 · Smart Zone vs Dumb Zone](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)

### 他给出的论证

1. **质量悬崖不在窗口上限。** 窗口还空着时，已经可以深陷 dumb zone。1M 窗口对他来说是「多卖给你一段 dumb zone」：检索大文本有用，写代码不行。
2. **退化是渐变、无报错的。** 常见症状：忘掉二十轮前的约束、重复已纠正的错误、自信断言与上下文矛盾。人的本能是再解释一遍，这只会再加 context，让问题更糟。
3. **smart zone 是预算，无关工作也在花它。** 同一 session 开第二个任务，等于从更靠近 dumb zone 的地方起步。任务大于一个 smart zone，就该在自然边界 handoff / compact，让新 session 做下一块。
4. **dumb zone 更贵。** 「Working in the dumb zone is more expensive than working in the smart zone. Cached input tokens still cost money.」600k 输入每次请求都会迅速烧钱。

来源：[Smart zone 词典](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Smart%20zone.md)、[X · 2026-07-14](https://x.com/mattpocockuk/status/2077114685338366389)、[X · 2026-05-29](https://x.com/mattpocockuk/status/2060389049681014871)

工作单元大小的直接推论，他 2026-08-11 写成启发式：

1. 估这个任务大概要花多少 token（估高更安全）
2. 除以 150k
3. 得到票数  
例：一次大 refactor 约 1M token ≈ 6.66 个 smart zone → 7 张票。

来源：[X · 2026-08-11](https://x.com/mattpocockuk/status/2087111966854730148)

### 适用前提

- 明确写的是 **frontier / SOTA** 模型。小模型的 instruction budget 更窄（他转述 HumanLayer：frontier thinking 大约能稳定跟 150–200 条指令，小模型更少）。
- 阈值「有争议」，他自己从约 100k 调到约 150k；不要把它当物理常数。
- 他假设你能看见 token 用量（工作坊里强调 status line「绝对必要」）。

**推断（非原话）：** 他把「一个 ticket = 一个新鲜 context 里能做完、且不掉出 smart zone」当作可测试的尺寸标准，是把 attention 物理约束直接映射成项目管理粒度。

---

## 2. Tracer bullet / vertical slice

### 他的原话 / 核心主张

> The concept of a **tracer bullet** comes from *The Pragmatic Programmer*. It's a small, end-to-end slice of functionality that touches all the layers of your system at once.
>
> Instead of building horizontal layers in isolation, you build one tiny vertical slice: Build a small feature end-to-end → Test it immediately → Get feedback → Move to the next slice in a **fresh context window** → Repeat.
>
> Context window constraints make the discipline non-negotiable. You can't ignore tracer bullets with an AI agent the way you might with a human developer.

来源：[Tracer Bullets: Keeping AI Slop Under Control](https://www.aihero.dev/tracer-bullets)

`/to-tickets` 文档页把尺寸标准写死：

> Every ticket is a **tracer bullet**: a narrow but complete path through every layer of the change — schema, API, UI, tests — that can be demoed on its own the moment it lands.
>
> It also sizes each ticket to fit in a **single fresh context window**, because the thing that will pick the ticket up is a session that has never seen your spec.

来源：[The /to-tickets Skill](https://www.aihero.dev/skills-to-tickets)

词典对 ticket 的定义：

> The defining constraint is the size: one session. A ticket should be completable before the session drifts out of the smart zone — and that constraint is testable.

来源：[Ticket](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Ticket.md)

2026-04 工作坊：AI 天然爱横向编码（先整层 schema，再整层 API，再前端）。他要的第一枪尤其是：一部分 schema + 一个新 service + 前端上最小可见表示。检验句是：「这张票做完，我能 demo 什么？」答不上来的就是横向切片。

来源：[工作坊逐字稿 · PRD to Issues](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)

### 他给出的论证

1. **对抗 slop / 谄媚。** Agent 想一次交出完整方案，在黑暗里盖完整层，不验证关键路径。他借用 *Pragmatic Programmer* 的「outrunning your headlights」。
2. **反馈环是速度上限。** 横向切片要到最后一层才知道整条链路通不通；垂直切片让第一枪就能测通。
3. **给盲走的 agent 装准星。** 曳光弹比喻：普通子弹看不见弹道，曳光弹让你立刻看见瞄偏了没有。没有它，「the AI is kind of coding blind until it reaches the later phases」。
4. **水平切片有现场失败数据。** 他写过一个团队 26 张按层切的票：大约每关一张票要跑 20 次 agent，其中约 3/4 是返工；事后归因全是横向切片，不是实现能力。
5. **例外：wide refactor。** 机械改动爆破半径跨全库时，改用 expand–contract，而不是硬套垂直切片。

来源：[tracer-bullets 文](https://www.aihero.dev/tracer-bullets)、[to-tickets](https://www.aihero.dev/skills-to-tickets)、[工作坊](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)

「sized to fit a single fresh context window」的论证链，公开材料里是这样接起来的：

- smart zone 限制一次 session 能可靠做完的量
- 下一枪必须在 **fresh** window（Ralph 的 bash 循环、to-tickets 的「one ticket per fresh context」）
- 因此票不能假设读者见过 spec

他没有发表过单独的实验论文证明「正好一个 window」是最优；这是从 smart zone + 无状态 session 推出来的工程约束。

### 适用前提

- 系统有可横切的层（schema / API / UI / tests）。他的演示仓库是课程 / 视频 CMS，前后端都在。
- 存在可立即跑的反馈环（类型、测试、能点的 UI）。
- 人愿意在出票时做 quiz：模型会过度拆、也会偷偷横切，审批步是设计的一部分。

**推断：** 「fresh context window」比「一个垂直功能」更硬。同一垂直切片如果估起来超过一个 smart zone，按他 8 月启发式仍应再拆。

---

## 3. Primary source vs secondary source；为什么 `/compact` 是最后手段

### 他的原话 / 核心主张

> A source of truth in its original form — the code, the conversation transcript, the raw log, the actual API response. Not an account of the thing; the thing.

> An account of a primary source, one step removed — documentation describing code, a summary describing a transcript, a report describing search results. Cheaper to load … and **lossy by construction**.

来源：[Primary source](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Primary%20source.md)、[Secondary source](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Secondary%20source.md)

Compact 被他定义成一次有损转写：

> Lossy by design: the transcript is a primary source, the summary a secondary source — detail traded for headroom.
>
> Timing matters too — compact at a phase boundary, after the plan is settled, not mid-task.

来源：[Compaction](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Compaction.md)

Phase-boundary 决策树把 **Continue 排第一、`/compact` 排最后**：

> **Continue** … It is the only move that keeps the session as a primary source, so rule it out first.
>
> **`/compact`** … None of the above. The default, and it lands here often.

来源：[The /ask-matt Skill](https://www.aihero.dev/skills-ask-matt)、[The /handoff Skill](https://www.aihero.dev/skills-handoff)

handoff 文把三种压缩动作说死：

> `/compact` compresses this context … intent survives. `/clear` empties the window … `/handoff` writes a portable file … **Note that all three turn a primary source (the conversation as it happened) into a secondary source (a summary of it). Continuing is the only move that doesn't, which is why it's the first one to rule out.**

2026-04 工作坊里态度更狠：

> devs love compacting for some reason, but I hate it. I much prefer my AI to behave like the guy from *Memento* because this state is always the same.

来源：[工作坊逐字稿](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)

Autocompact 被单独点名为最差时机：

> A manual compact happens at a phase boundary, when you can tell the model what to preserve. Autocompact fires mid-task … possibly halfway through a refactor, with the summary deciding for itself which of your decisions were worth keeping.

来源：[Autocompact](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Autocompact.md)

### 他给出的论证

1. **降级代价是不可见的丢失。** 摘要作者替你决定「什么重要」；今天才变得关键的细节，上个月的摘要里不会有。Agent 会「自信地基于错误信息干活」。
2. **二次来源会漂移。** 代码变了，文档 / 摘要不会跟着变。
3. **补救是回主键，不是再写一层摘要。** 「The fix is sending it back to the primary source。」好的二次来源要带 **context pointer** 指回原件。
4. **Continue 是唯一不降级的动作。** 所以先排除它：下一阶段需要 verbatim 上下文，或 smart zone 还够。
5. **Clear 比 compact 更可预测。** 清掉后回到同一份 system prompt，状态每次相同；compact 留下一份你很难检查的摘要状态。
6. **Compact 仍经常发生。** 它是树底的默认项，不是禁止项。他后来说：为避免重新探索代码，可以先 compact；但必须在 phase boundary。

来源：上述词典 + [X · 2026-07-14](https://x.com/mattpocockuk/status/2077114685338366389)、[X · 2026-07-23](https://x.com/mattpocockuk/status/2070191683279360079)

### 适用前提

- 你能判断「下一阶段是否需要 verbatim」——这需要人在场，或至少有清晰的阶段切分。
- 关键决策已经写进磁盘上的 spec / ticket / ADR（clear 才安全）。
- 他后期比 4 月工作坊更接受 compact，但仍坚持时机。

**推断：** 「`/compact` 是最后手段」在 2026-07 决策树里是明确的排序，不是「永远不要 compact」。4 月「I hate compacting」是更强的个人偏好，后来被结构化成五选一树。

---

## 4. Phase boundary

### 他的原话 / 核心主张

> A phase is a chunk of work inside a session — the grilling, the implementation, the QA — and the **boundary between two of them is the only place the question "what do I do with this context?" belongs.** Mid-phase there is nothing to decide: continue, or split what is left into subagents.

五选项及触发条件：

| 选项 | 何时 |
| --- | --- |
| Continue | 下一阶段需要本阶段 verbatim，或 smart zone 还剩。唯一保持 primary source 的动作，先排除它 |
| `/clear` | 身后的一切都可丢。最便宜，判错则不可逆 |
| `/handoff` | 有东西必须旅行：新 harness、新目录、同事、中途分叉的副作用 |
| Subagent | 任务窄到可以 AFK 跑 |
| `/compact` | 以上都不是。默认项，经常落到这里 |

来源：[The /ask-matt Skill](https://www.aihero.dev/skills-ask-matt)、[X · 2026-07-22](https://x.com/mattpocockuk/status/2079879414297330146)

两个常被用错的点：`/handoff` 买的是 **portability** 不是更好的摘要；`/compact` 是树底，不是第一伸手。

### 他给出的论证

1. **阶段中途没有「上下文管理问题」，只有「做完或拆走」。** 中途 compact / clear 等于主动把主键变成摘要，还可能切在 refactor 一半。
2. **选项不是等价菜单，是有序树。** 先问「能否继续当主键」，再问「能否清空」，再问「是否要搬走」，再问「能否丢给子代理」，最后才压缩。
3. **Auto-compact 正是在错误时刻做正确动作的反面。** 阈值触发 ≠ 阶段边界。

### 适用前提

- 工作能被切成可命名的阶段（grill / implement / QA）。开放式探索、无阶段的 vibe session 很难套这棵树。
- 人（或 router skill）在边界上做一次显式选择，而不是交给 harness 自动压。

**推断：** 「只在 phase boundary 做上下文决策」是 2026-07 才被他写成公开原则；4 月工作坊已有「clear 优于 compact」，但还没有这棵五选项树。

---

## 5. AFK agent / ready-for-agent

### 他的原话 / 核心主张

> Away from keyboard. A working pattern where the user kicks off a session and leaves the agent to run unattended. The throughput multiplier of AI coding — many AFK sessions can run in parallel while you sleep, eat, or work on something else. Usually requires a permissive permission mode plus sandboxing to be safe.

特征性失败：

> The characteristic failure is coming back to hours of finished, confident work built on a wrong call made in the first ten minutes. The work isn't sloppy — it's coherent, just coherent about the wrong thing.

三拍补位：

- **之前：** grilling + 写好的 spec，减少它独自填空的缝
- **之中：** automated checks / automated review 代替你不在场的注意力
- **之后：** 产出必须是可审的 PR，不是已经 merge 的改动。AFK 不取消 human review，只是把它全部推迟到结尾

来源：[AFK](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/AFK.md)

对照 HITL：

> Well-specified, low-risk, easy-to-verify tasks suit AFK. Tasks that are ambiguous, irreversible, or where you'd struggle to review the finished result — a schema migration, a tricky design decision, anything touching production — suit staying in the loop.

来源：[Human-in-the-loop](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Human-in-the-loop.md)

`ready-for-agent` 是 triage 状态机里的一格：

> **ready-for-agent** — Fully specified, with an agent brief attached. An AFK agent can take it.
>
> **ready-for-human** — The same brief, plus why this can't be delegated — judgment, external access, manual testing.

来源：[triage: Turn Backlog Mess Into Agent-Ready Work](https://www.aihero.dev/burn-through-your-backlog-with-my-triage-skill)

工作坊把整条流水线说成日班 / 夜班：人做 grill → PRD → Kanban；实现阶段人离开，agent（或多个 agent）消化 backlog。规划必须 HITL，「I can't loop over this」。

来源：[工作坊逐字稿](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)

Issue tracker 作为队列：Ralph / AFK 循环只捡 AFK 票；`to-tickets` 发布时直接打 `ready-for-agent`，好让 runner 不用再 triage。他提醒：父 spec 也会被打上同一标签，AFK runner 可能整份 spec 一把做完——要在 prompt 里排除父 spec。

来源：[to-spec](https://www.aihero.dev/skills-to-spec)、[to-tickets](https://www.aihero.dev/skills-to-tickets)

### 他给出的论证

1. **吞吐来自并行无人值守，不来自把人留在循环里。**
2. **无人值守时，歧义会变成默认猜测，后面所有决策叠在错猜上。** 所以「能不能 AFK」= 歧义是否已经在开工前被烤干。
3. **环境必须替你看着。** AX（自动化检查、可导航架构、空闲 context）在 AFK 里最重要，「with no one watching, the environment is the only support the agent gets」。
4. **队列要简单到能查询。** 每个 issue 恰好一个 category + 一个 state；`ready-for-agent` 就是 runner 的入口谓词。

### 适用前提

- 有 sandbox + 可放宽的权限模式。
- 有快而确定的检查（类型、测试、lint）。
- 任务已 brief 到「fresh session 不需要你在场」。
- 产出形态是 PR，后面还有人审。
- 他承认：实现可以 AFK，但 QA / code review 不能整段卸掉；「I don't honestly know」如何消化暴增的 review 量。

**推断：** 「issue tracker = agent 队列」在工作坊和 triage 文里是操作模型，不是一篇独立论文。他没有论证过「所有公司都应把 Linear/GitHub 当成唯一调度器」；他论证的是：已经写好的、带依赖边的票，足够当夜班输入。

---

## 6. Spec / ticket 里为什么禁止写文件路径和行号

### 他的原话 / 核心主张

Triage brief：

> Briefs are written to be **durable rather than precise**, because an issue can sit in `ready-for-agent` for weeks while the code moves underneath it. So they name types, signatures and behavioural contracts, **and never file paths or line numbers**.

来源：[triage 文](https://www.aihero.dev/burn-through-your-backlog-with-my-triage-skill)

`/to-tickets` 验收标准里同一条：

> Nothing in a ticket body is a file path or a line number, except a snippet a prototype produced.

来源：[to-tickets](https://www.aihero.dev/skills-to-tickets)

AGENTS.md 文把同类腐烂写得更狠：

> This is especially dangerous when you document file system structure. File paths change constantly. If your `AGENTS.md` says "authentication logic lives in `src/auth/handlers.ts`" and that file gets renamed or moved, the agent will confidently look in the wrong place.
>
> Instead of documenting structure, describe capabilities. … Domain concepts … are more stable than file paths.

来源：[A Complete Guide To AGENTS.md](https://www.aihero.dev/a-complete-guide-to-agents-md)

`/init` 文把「文件和服务引用」称作最糟一类生成物：一改名就 **actively misleads**。

来源：[Never Run Claude /init](https://www.aihero.dev/never-run-claude-init)

需要同时记下他**允许**路径的地方，否则会过度概括：

- **Handoff artifact**（短命中转）：「Concrete file paths rather than "the file we discussed".」因为下一 session 从零开始，必须能立刻打开文件。来源：[Handoff artifact](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Handoff%20artifact.md)
- **Ticket 作为 context pointer**：词典说好票要有「context pointers to the relevant files and decisions」。来源：[Ticket](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Ticket.md)
- Prototype 产出的 snippet 可以带路径。

也就是：**会在 tracker 里躺几周的合同写类型与行为；几小时内要接棒的中转文件写具体路径。**

### 他给出的论证

1. **精度和寿命互斥。** 路径 / 行号在写下来的那一刻最准，但代码会在票被捡起之前移动。
2. **过期指针比没有更糟。** Agent 会自信地去错误地点。
3. **类型、签名、行为契约、领域名词更稳。** 文件可以搬家，`materialization cascade` 这种词如果进了 `CONTEXT.md`，还能被搜到。
4. **让 agent 在开工时自己生成 JIT 文档**，而不是继承一份腐烂地图。

### 适用前提

- 票可能在队列里待很久（他写的是 weeks）。
- 代码库移动频繁（AI 加速熵增时更是如此）。
- 领域词汇已经足够当定位器；若项目没有稳定类型名，这条会变空。

**推断：** 「durability over precision」这四个词是 triage 文的原句。把它推广到所有 spec 章节，是做法上的一致，不是另一篇专论。Handoff 与 ticket 的路径政策相反，说明约束跟**工件寿命**绑定，不是「永远禁止路径」。

---

## 7. 流程 / 规则 vs 让模型自主判断

### 他的原话 / 核心主张

总立场写在 skills 仓库门口：

> Developing real applications is hard. Approaches like GSD, BMAD, and Spec-Kit try to help by owning the process. But while doing so, they take away your control and make bugs in the process hard to resolve.
>
> These skills are designed to be **small, easy to adapt, and composable**. They work with any model. They're based on decades of engineering experience.

来源：[mattpocock/skills README](https://github.com/mattpocock/skills)

工作坊：

> you need to own as much of your planning stack as you possibly can. … I believe in inversion of control and you should be in control of the stack.
>
> this grill me skill is **wonderfully small, wonderfully tiny**.

同一场：编码标准分 **push** 与 **pull**——`CLAUDE.md` 是每轮都推送的 token；skill 是「agent 需要时再拉」。实现阶段标准应可拉；自动 review 则应把标准 **push** 给审查者。

来源：[工作坊逐字稿](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)（push/pull 后半场；二次整理见 [Sean Weldon 笔记](https://www.sean-weldon.com/blog/2026-04-27-workflow-for-ai-coding-matt-pocock)，后者不是他署名原文）

Instruction / context 预算：

- AGENTS.md 文转述 HumanLayer：frontier thinking 大约 **150–200 条指令**；「the ideal `AGENTS.md` file should be as small as possible。」来源：[A Complete Guide To AGENTS.md](https://www.aihero.dev/a-complete-guide-to-agents-md)
- `/init` 文：LLM 一次大约能跟 **300–400 条指令**，更大模型也许 500；他自己的 `CLAUDE.md` 只有一句 `you are on WSL on Windows`——门槛是 **undiscoverable 且 globally relevant**。来源：[Never Run Claude /init](https://www.aihero.dev/never-run-claude-init)
- 词典：skill 默认只占 name + description；「In AGENTS.md it'd burn tokens on every turn for something we use weekly。」来源：[Skill](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Skill.md)、[Progressive disclosure](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Progressive%20disclosure.md)

`writing-for-agents`：

> The packaging differs; the writing does not: the same levers make each one predictable, so the agent takes the **same process** every run rather than producing the same output.
>
> Its default move is **deletion**, not explanation. … every one of those lines is a **no-op**, paying context and changing no behaviour.
>
> You are writing for a reader who has already read everything, so **explanation is waste and precision is the entire job**.

两个预算：

- **Context load**：永远占窗口的东西
- **Cognitive load**：你当索引的成本——「Not a cost to minimise — it is the price of human agency.」

来源：[The /writing-for-agents Skill](https://www.aihero.dev/skills-writing-for-agents)

`/implement` 几乎没写成厚流程。changelog：

> The `/implement` skill mostly relies on the agent's priors and what your `agents.md` file teaches it. **I almost didn't create a skill for this because it's so simple**, but people kept asking "what's the flow?"

来源：[Skills changelog v1.1](https://www.aihero.dev/skills/skills-changelog-v1-1-wayfinder-to-spec-to-tickets-grilling-improvements)

`codebase-design` 是参考不是流程：没有 loop、没有产出物。硬拿它当 driver 会烧掉 100k token。他的补救是：driver skill 提问，参考 skill 只提供词汇。

来源：[The /codebase-design Skill](https://www.aihero.dev/skills-codebase-design)

### 他给出的论证

1. **厚框架拿走可观测性。** 流程出 bug 时你修不了。他要 inversion of control。
2. **规则有全局税。** 每条永远加载的指令占用 instruction budget 和 attention budget，且在无关 session 里是噪音。
3. **模型已经知道的解释是 no-op。** 写给 agent 的默认编辑动作是删。
4. **要稳定的是过程，不是输出。** Leading word（`tight`、`red`、`tracer bullet`）把预训练里已有的概念当成执行锚。
5. **人必须继续当索引。** 把路由从窗口里拿出来，代价是你得记得何时调用什么。
6. **实现应尽量交给先验。** 需要 skill 的是对齐、切片、审查这些模型会偷懒或横切的步骤。

### 适用前提

- 使用会遵守 skill 描述、会按需拉取的现代 harness。
- 作者愿意维护薄指针，而不是一份包罗万象的 CLAUDE.md。
- 团队能接受「流程在人脑 / ask-matt，不在一份静态清单」。

**推断：** 他没有一篇题为「何时规则是浪费」的专论。能拼出来的判据是：discoverable from source、only relevant sometimes、模型先验已覆盖、或加进去会与别的指令抢 attention。反过来说，grilling / 垂直切片 / 阶段边界这些，是他认为模型会系统性做错、必须写成纪律的点。

---

## 8. Issue tracker 作为状态源

### 他的原话 / 核心主张

他**明确说过**的是：

1. **跨 session 的工作必须住在 environment 里，tracker 是首选家。**
   > Anything that takes more than one context window of effort needs a home outside the context — somewhere in the agent's environment that survives clearing, whether that's a file in the repo, a GitHub issue, or an issue tracker the agent can reach.

   来源：[Spec](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Spec.md)

2. **地图 / 票 / 依赖边长在 tracker 上，tracker 不是装饰。**
   > The map and its tickets live on the repo's issue tracker … The tracker is not decoration. Blocking is what renders the frontier visually in the tracker's own UI.

   来源：[The /wayfinder Skill](https://www.aihero.dev/skills-wayfinder)

3. **地图是索引，不是仓库。** 每个决定只住在自己的票里；session 先低分辨率读地图，再按需 zoom。
4. **远程 tracker 便于共享和委派。** 「I prefer my issue tracker state to be remote so I can easily share it。」「The fact it uses a shared issue tracker means you can delegate tickets within the team。」

   来源：[X · 2026-08-05](https://x.com/mattpocockuk/status/2085024586706321637)、[X · 2026-07-30](https://x.com/mattpocockuk/status/2082918384606314949)

5. **本地单文件曾是 bug。** 根目录共享 `tickets.md` 会在并行 agent 写入时打架；后来改成每票一个文件。

   来源：[to-tickets](https://www.aihero.dev/skills-to-tickets)

6. **状态机要极小。** triage 只有 5 个 state；用户要 `blocked` / `deferred` / `implemented`，他承认 blocked 是真问题，但没扩状态机。

7. **反对另起一套拥有全过程的框架**（GSD / BMAD / Spec-Kit），理由是失控、流程 bug 难修。

### 他给出的论证

- Session 一次性，工作不是。状态必须落到 environment。
- 原生 blocking / sub-issue 让「frontier」在 tracker UI 里可见，多个 agent 才能安全并行。
- 共享远程状态才能把票分给同事或其他 wayfinder 地图。
- 自建在 git 里的规划文件容易「accidental persistence」；wayfinder 明确不推荐把地图物料长期堆在仓库里。
- 标签状态机保持可查询：「exactly one state role」是 runner 简单的前提。

### 未找到公开论证

他**没有**一篇公开文章论证「禁止自建状态机 / 状态文件，issue tracker 是唯一合法状态源」。

相反，公开文本允许：

- 本地 markdown（`.scratch/`）当 tracker
- 「You can roll your own issue tracker if you like」([X](https://x.com/mattpocockuk/status/2082918470103048413))
- research 笔记甚至可以不进 git

所以「唯一状态源」若理解成「必须用 GitHub/Linear、不许有别的文件」，**过强，不是他的原话**。

**推断：** 他真正反对的是第三套 *过程所有权*（BMAD 式编排器、自研 session 状态机、会与 tracker 抢权威的进度文件）。Tracker（或它的本地等价物）应是票、阻塞边、ready-for-agent 的权威；`CONTEXT.md` / ADR 是领域与设计的权威；代码是行为的主键。三层各管各的，不要再发明第四层运行时状态。

---

## 9. Ousterhout：deep module / design it twice

### 他的原话 / 核心主张

README 直接引 Ousterhout：

> "The best modules are deep. They allow a lot of functionality to be accessed through a simple interface."
> — John Ousterhout, *A Philosophy Of Software Design*

论证语境：agent 加速编码，也加速熵。「The Fix … is a radical new approach to AI-powered development: caring about the design of the code。」

来源：[skills README · #4 We Built A Ball Of Mud](https://github.com/mattpocock/skills)

`codebase-design` 文档页：

- 词汇：module / interface / depth / seam / adapter / leverage / locality
- **他故意不用 Ousterhout 原定义**（实现行数 / 接口行数），因为那会奖励把实现写胖。他改用 **depth = leverage at the interface**。
- `DESIGN-IT-TWICE.md`：「Based on "Design It Twice" (Ousterhout) — **your first idea is unlikely to be the best.**」做法：并行 3+ 个子代理，各自给出**极端不同**的接口，再按 depth / locality / seam 比较。

来源：[The /codebase-design Skill](https://www.aihero.dev/skills-codebase-design)、[DESIGN-IT-TWICE.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/codebase-design/DESIGN-IT-TWICE.md)

X：有人问来源时，他说「I'm taking it from 'strategic programming' via John Ousterhout, early 2000's」。

来源：[X · 2026-07-26](https://x.com/mattpocockuk/status/2081436341078839318)

工作坊：写 PRD 前先问「准备改哪些 modules」；「this is not specs to code… we actually keep the code in mind throughout」；「bad codebases make bad agents」。他把持续设计系统说成贯穿全程的纪律。

来源：[工作坊逐字稿](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)

AX 词典把架构写成 agent 体验的一维：

> A codebase the agent can navigate without reading everything: predictable structure, a lot of behaviour behind small interfaces, names that say what things do.

来源：[AX](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/AX.md)

### 他给出的论证

1. **Agent 让熵加速，所以每天都要投资设计**（同时引 Kent Beck）。
2. **深模块降低导航成本：** 小接口、行为藏在后面，测试缝清晰；浅模块导出一堆、边界不清，agent 要手搓依赖。
3. **第一次接口多半不是最好的** → 用并行子代理强迫出多方案，而不是在第一个想法上打磨。
4. **模块 ≠ 目录。** 有人要把 deep module 落实成分形目录树，他拒绝：「deep modules are about the design of the interface … no matter what the file system looks like。」
5. **执行层他给过三个选项**（GitHub issue 回复，经 codebase-design 文档页转述）：巨大 class / IIFE；monorepo package；dependency-cruiser。另说 Effect 是最好的机制，dependency-cruiser 第二。

### 适用前提

- 你愿意在实现前花 HITL 时间选缝、比接口。
- Design-it-twice 目前绑在 Claude Code 的 Agent tool 上；他承认别的 harness 「Not cleanly」。
- 词汇表刻意很小；connascence / module secrets 等提案未合并。

**推断：** 他把 Ousterhout 用在 *agent 可导航性* 上，不只是人类可维护性。公开论证到「深接口 + 先设计两次」为止；没有一篇把 *A Philosophy of Software Design* 全书映射到 agent 工作流的长文。

**未找到公开论证：** 他没有系统讲 Ousterhout 的 information hiding、comments、define errors out of existence 等其余章节如何用于 agent。

---

## 10. 多 agent 并行 / subagent

### 他的原话 / 核心主张

词典：

> An agent spawned by another agent via a tool call. Runs in its own session with its own context window, and reports a single tool result back. … **Cannot spawn further subagents — the tree is one level deep.** Subagents exist to isolate context, not to compose hierarchies.
>
> The report is a secondary source: the parent gets the subagent's account of what it found, not the raw results.
>
> Subagents also run concurrently — a parent can fan several out at once over independent pieces of work.

来源：[Subagent](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Subagent.md)

工作坊现场：explore 子代理烧掉约 93.7k Opus token，父窗口几乎没涨。「You're delegating a task … it drip feeds the important stuff back up。」

来源：[工作坊逐字稿](https://github.com/shanraisshan/claude-code-best-practice/blob/main/videos/claude-matt-pocock-24-apr-26.md)

并行的正统单位是 **独立 ticket / DAG 叶子**，不是任意分叉的子代理树：

> Independent tickets — the leaves of the graph — can each run in their own session at the same time. This is an effective way of running multiple agents at once.

来源：[Ticket](https://github.com/mattpocock/dictionary-of-ai-coding/blob/main/dictionary/Ticket.md)

Wayfinder 对并行更保守：

> The frontier is built to show you what is takeable … In practice **one-at-a-time is the safer default.** Users working two grilling tickets at once get asked in one session a question they just answered in the other, because the sessions share no context.

研究票是「一票一 session」的唯一例外（可在 charting 时并行烧掉）。

来源：[wayfinder](https://www.aihero.dev/skills-wayfinder)

Phase-boundary 树：subagent 仅当「任务窄到可以 AFK」。他回复：

> Yes, true, though deciding when to spawn a subagent is its own kind of decision tree.

来源：[X · 2026-07-22](https://x.com/mattpocockuk/status/2079919043780214917)

工作坊后半提到用沙箱给每个 issue 单独 branch、planner 看阻塞边、merger 合入（二次笔记里叫 Sand Castle）。这是他演示过的并行实现路径；公开词典没有把「必须用 Sand Castle」写成原则。

### 他给出的论证

1. **子代理的目的是隔离噪音，不是搭公司编制。** 深树会把二次来源再摘要一次。
2. **父窗口要保持 smart zone。** 大搜索留在父 session 会污染后半程。
3. **真正的吞吐来自 tracker 上的独立叶子**，各自新鲜 session + 沙箱。
4. **共享上下文的 HITL 票不能假装独立。** 两个 grilling 并行会互相问已经答过的题。
5. **子代理回报是二次来源。** 父代理看不见报告里丢掉的边角。

### 适用前提

- 票的阻塞边真实，frontier 上的叶子互不抢同一文件 / 同一决策。
- 有沙箱或至少分 branch。
- 并行 HITL 需要人自己先审依赖图。
- Review 量随并行线性涨；他承认还没好答案。

**未找到公开论证：** 他没有给出「最多 N 个并行 agent」的数字上限，也没有正式限制「何种业务域禁止并行」。限制条件都是定性的：独立叶子、一票一 window、HITL 默认串行、子代理一层。

---

## 适用边界

### 这套理念隐含的项目与资源条件

从他反复使用的例子、课程仓库和用词，可以还原出他默认的工作环境（以下前半是原话事实，后半是推断）：

**他明确展现过的条件：**

- 使用 **frontier / SOTA** 模型（工作坊里一个 explore 子代理就烧掉约 94k Opus token）。
- 个人或小团队、作者对仓库有完整控制（`course-video-manager` 上百张自产 issue）。
- 能给 AFK 开 **bypass permissions + Docker sandbox**。
- 有可自动跑的反馈环；实现阶段可以变成夜班。
- 产品形态接近他教的全栈应用：schema + service + 可见 UI，垂直切片能 demo。
- 人愿意把大量白天时间花在 grilling / wayfinder 上，用 token 换对齐。
- 规划资产可以进公开或半公开的 GitHub/Linear。

**推断出的隐含条件：**

- Token 账单不是第一约束；他优化的是 *质量单位 token*，不是 *绝对花费*。dumb zone 贵，是劝你别浪费，不是劝你换小模型。
- Review 人力跟得上 agent 产量，或至少接受「做更多 code review」。
- 领域专家可以进 grilling（他建议 mob / pair）。B2B 里这个人往往不在开发会话中。
- 合规、租户隔离、审计日志不是他演示的主约束。HITL 词典举的不可逆例子是 schema migration，不是权限矩阵或跨租户数据完整性。

### 预算受限时，哪些主张会失效或必须加强

| 主张 | 在预算受限下 |
| --- | --- |
| 150k smart zone / 一票一新鲜 frontier session | **部分失效。** 该数字绑的是 SOTA。便宜模型 attention 更差、instruction budget 更小，同一张「垂直切片」可能已经在 dumb zone。票要切得更碎，或接受更短 session。 |
| 子代理隔离探索 | **成本结构变差。** 工作坊一次 explore 就近 100k Opus。预算紧时应让父代理自己读少量主键文件，而不是默认开子代理。 |
| Design-it-twice 三个并行子代理 | **容易变成奢侈品。** 理念仍成立，但三次完整设计探索在弱模型 + 穷预算下会先烧光额度。更稳的是人先否决两个方向，只深挖一个。 |
| Wayfinder 多 session 规划 | **对小需求过重。** 他自己说单 session 用 grill 更便宜。预算紧时，这个「更便宜」还包括模型档位。 |
| Continue 优先于 compact | **仍然成立，甚至更要紧。** 弱模型在更低 token 数就变蠢；更不能靠「再解释一遍」续命。 |
| CLAUDE.md 尽量空、规则用 pull | **加强。** 小模型能跟的指令更少。厚规则集会比在 Opus 上更早变成噪音。 |
| AFK 夜班 | **缩小适用范围。** 弱模型更会在前十分钟猜错并自信做完。没有强测试网时，夜班产出审查成本可能高于白天 HITL。 |
| 「我几乎不读 PRD，只检查 LLM 摘要能力」 | **应当放弃。** 这是他对 frontier 摘要能力的信任。便宜模型的 spec 漂移必须人读。 |

### B2B 平台产品（合规 / 权限 / 多租户 / 数据完整性）下，哪些主张会失效或必须加强

| 主张 | 在 B2B 平台约束下 |
| --- | --- |
| 第一枪必须含最小 UI 的垂直切片 | **经常不适用。** 许多高风险工作停在权限、租户边界、账本、审计、后台 job，没有可点的 UI。垂直仍应横切「规则层 + 数据层 + 测试」，不要为了 demo 强行加一层皮。 |
| 实现默认 AFK | **必须收紧。** 他自己把 schema migration、生产相关、不可逆、难审的结果划给 HITL。多租户隔离、授权、财务一致性、删除/导出都属于这类。`ready-for-agent` 应变成少数派；`ready-for-human` 才是默认。 |
| 票上禁止路径 / 行号 | **对行为合同仍成立；对威胁模型要加强。** 权限矩阵、租户键、幂等键、审计事件名比路径更稳，也应写进 brief。但安全控制的 *位置* 有时就是需求（「必须走网关 X」）——这时要写稳定的模块名 / 接口名，而不是行号。 |
| Issue tracker 当队列 | **合规上要加闸。** 公开 GitHub 上堆 agent 规划票，他自己也提到开源维护者的反问题。B2B 还要处理：票里不能有客户数据、不能让 runner 看见未脱敏的 reproduction。Tracker 仍可当队列，但 brief 与附件的保密分级是他没写的一层。 |
| 人可以不读 spec | **失效。** 合规审查要的是可追责的决策记录。`to-spec` 说 spec 主要给 agent、对人只需看 seams 和 out-of-scope——在受监管环境里这不够。 |
| Grill 直到共享 design concept | **仍然极有价值，但参与者集合要扩大。** 工作坊已说：开发答不了的问题要把领域专家拉进来。B2B 还要法务 / 安全 / 客户成功能异步答（他的 `/to-questionnaire` 是相邻工具）。只开发 + agent 烤一遍，会漏租户与权限分支。 |
| 深模块 + 单一高缝 | **要加强，不是削弱。** 权限与租户规则若散落各层，agent 会在某一枪里绕过。把授权 / 租户作用域做成深模块、测试只打那条缝，比在每张票里重复「别忘了 tenant_id」更符合他的 AX 逻辑。 |
| 并行多 agent | **限制条件变硬。** 两张「独立」票若都碰同一授权表或同一迁移，frontier 看起来可并行，数据完整性上不可并行。他的「blocking edges 必须是真的」在这里要从类型依赖升级到数据依赖 / 锁依赖。 |
| Ralph 循环 + bypass permissions | **通常不能原样用。** 沙箱仍要，但生产凭证、客户数据、迁移权限不该进 bypass。他的 AFK 例子是只读文件系统、无网络——B2B 实现票几乎总会需要更细的工具权限。 |
| 「代码是战场，反对 specs-to-code」 | **仍然成立，但要补一层。** 他反对的是 *只改 spec、不看代码*。B2B 不能走到另一端：只看代码、规格里没有租户不变量。主键仍是代码与测试；规格必须能被审计员读懂。 |

### 一句收束

Pocock 这套理念的硬核是：**frontier 模型的有效注意力远小于广告窗口；所以工作必须切成能在新鲜 smart zone 里做完的垂直切片；跨 session 的状态放到 tracker 与代码里，而不是摘要里。**  
它在「强模型 + 可沙箱 + 可自动验证 + 作者控全栈」时自洽。预算一降，切片和 HITL 比例都要加码；B2B 平台一加上权限与数据完整性，AFK 队列和「第一枪必须有 UI」就会先裂开，而深模块、主键优于摘要、阶段边界才 compact，这些反而更该保留。
