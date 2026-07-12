---
name: talk-to-boss
description: Use when reporting task status, completion, audit/backfill/apply progress, remaining work, merge readiness, final delivery, or multi-worktree sequencing to a decision-maker or stakeholder; also when a user says a status is too technical, incomplete, or misleading.
---

# Talk To Boss

Turn implementation progress into a boss-readable functional status. The deliverable is not a work log. It is a clear statement of what product behavior is now supported, what remains unproven, and whether the requirement can be called done.

Use Chinese by default when the user writes Chinese. Keep product vocabulary such as `Inventory Item`, `Product SKU`, `threshold`, `Lark`, `smoke`, and `review` when those are the domain terms.

## 决策者首段合同

决策者首先需要判断整体状态，而不是重建执行过程。回复的第一段必须可以脱离后文独立阅读，并明确回答：

- 总范围是什么。
- 哪个阶段已经完成。
- 还剩什么以及数量。
- 整体现在能否称为 completed / closed。
- 当前需要 owner 做什么决定；没有待决策时也要明确说明。

当任务有可计数对象时，在首段对齐总量、已处理量、待处理量和独立 pending 数量。技术实现、测试、文件、agent、worktree 和命令不得出现在这个结论之前。

推荐句式：`总范围为 X；Y 阶段已完成；还剩 Z；完成 Z 后整体才算 closed；当前需要 owner 决定 Q。`

## 阶段词不能混称

所有“完成”都必须带对象和阶段。区分 `audit / scan`、`extract`、`apply / implementation`、`verify`、`merge`、`release`；上游阶段完成不能被表述为整个任务完成。

例如：

- 错误：`backfill 已完成，报告里还有 22 条候选。`
- 正确：`63 篇历史计划已全部审计；提炼出的 22 条候选尚未 apply，因此本轮 backfill 尚未完成。完成这 22 条后才算真正补完。`

关键状态词容易让决策者误解时，紧接首段增加“准确含义”，解释阶段边界；之后才展开必要细节。

## Workflow

1. 先确定整体 closure。
   - 写出总范围、已完成阶段、剩余工作、整体是否 closed 与 owner decision。
   - 如果只能说某个局部阶段完成，主动写明为什么整体仍未完成。
   - Completion criterion：只读首段也不会误判任务状态。

2. Extract the functional contract from the available context.
   - Identify user-visible capabilities, rules, and protected behaviors.
   - Treat files, tests, agents, commits, and tools as evidence, not as the main story.
   - Completion criterion: every major engineering item is mapped to a product behavior or marked as internal evidence only.

3. Group by functional slice.
   - A functional slice is a product capability or rule a stakeholder can understand.
   - Do not group by DAG node, code layer, test type, file, or agent.
   - Completion criterion: each top-level slice could be used as a section title in a product spec.

4. Write each completed behavior as a spec sentence.
   - Use this shape: `[Actor/System] 在 [condition] 下 可以/不能 [action]，导致 [observable result or business impact]。`
   - Prefer capability and consequence over implementation detail.
   - Completion criterion: each bullet answers who can or cannot do what, under what condition, and what result follows.

5. Separate implementation completion from requirement closure.
   - Say `已实现，待验收` when code and local tests pass but real UI/data-source acceptance is missing.
   - Say `不能宣称 closed` when a required smoke, browser check, external data check, or final review is still pending.
   - Completion criterion: the reader can tell what is done, what is only locally proven, and what still blocks closure.

6. Fold missing planned checks into the relevant slice.
   - Only mention a not-run check when it was actually designed, required, or expected for this task and was not run.
   - Fuse `Not run` and `Why not` into one natural bullet under `还缺`, for example: `Lark Test Environment 写入/读回 smoke 还没跑，因为本轮还没完成 Test Env mutation 验收。`
   - Do not list unrelated external systems. If the task does not involve Lark, Lexware, email, public deployment, or another integration, omit them entirely.
   - Do not add a separate `Not run` / `Why not` template section unless the user explicitly asks for an audit template.
   - Completion criterion: every missing planned check has a concrete reason, and no irrelevant boilerplate checks appear.

7. Report test-case gaps only when abnormal.
   - If existing tests or smoke paths cover the task adequately, do not write a `Test-case gap judgment` section.
   - If there is a real gap, state it inside `风险/备注` or `剩余收口`, with the missing scenario and why it matters.
   - Completion criterion: test-case gap language appears only when it changes the follow-up work.

8. Translate evidence into confidence.
   - Convert service/action/integration tests, i18n checks, type checks, browser verification, Lark smoke, and reviews into stakeholder meaning.
   - Mention raw commands only when the user asks for audit detail.
   - Completion criterion: technical evidence explains confidence instead of becoming a tool chronology.

9. Produce a concise forwardable update.
   - Start with `整体判断`.
   - Then use `功能 Slice 进度`.
   - End with `剩余收口` when there are open gates.
   - Completion criterion: a non-implementer can understand whether the requirement is done and what remains.

## 工作安排类解释

当问题是「为什么这样安排 / 为什么需要 X」而答案涉及多条并行工作线、时序或合入门时，本 skill 同样适用：

- 第一句先给功能层全景：一共几条线、各自在做什么、各自到哪收口；机制推理（分支原子性、合入顺序论证、操作成本比较）只能出现在全景之后，作为理由而不是开场。
- 不用「不是…而是…」式反驳开场；先立地图，再讲为什么。
- 多线并行时使用下方的并行工作线形态。

## Output Shape

Use this shape unless the user asks for another format:

```markdown
**整体判断**
[One or two standalone sentences: total scope, completed stage, remaining work, whether the whole task is closed, and the owner decision needed.]

**准确含义**
[Only when stage terms may be confused: explain why audit/extract/apply/verify/merge/release do or do not constitute overall completion.]

**功能 Slice 进度**

**1. [Functional slice name]**
目标：[User-visible capability or rule.]

已完成/已实现，待验收：
- [Actor/System] 在 [condition] 下 可以/不能 [action]，导致 [observable result or impact].

还缺：
- [Planned or required acceptance evidence not run yet, fused with the reason. Omit unrelated checks.]

风险/备注：
- [Only include real residual risk or abnormal test-case gap.]

**剩余收口**
- [Short list of final gates.]
```

Skip empty sections. For a short answer, keep only `整体判断`, `功能 Slice 进度`, and `剩余收口`.

### 并行工作线形态

当状态或解释涉及多条并行工作线（多分支、多 worktree、多阶段）时，改用对照表，每行一条线：

```markdown
| 线 | 在哪 | 干什么 | 合入门/依赖 |
| --- | --- | --- | --- |
| [自解释名词，如「修正线」] | [worktree/分支/环境] | [功能层描述] | [什么条件下收口] |
```

表后用一两句话写清线间依赖链。行名必须是自解释名词；内部编号（Deliverable n、Tn、Cohort X 之类）不得裸用，首次出现必须伴随展开或改写为功能名词。

## Quality Gate

Before answering, rewrite if any check fails:

- 第一句是功能层结论（几条线、在做什么、到哪收口），不是机制推理，也不是「不是…而是…」式反驳开场。
- 首段单独回答总范围、已完成阶段、剩余工作、整体是否 closed 和待 owner 决策；不看后文也不会误判。
- 所有“完成”都带对象和阶段；audit、extract、apply、verify、merge、release 没有被混称。
- 有可计数对象时，总量、已处理量、待处理量和独立 pending 数量能够互相对账。
- 技术实现、测试、文件、agent、worktree 和命令没有出现在决策结论之前。
- 内部编号不裸用；每个编号伴随自解释名词或首次展开。
- Top-level sections are functional product slices, not status slices.
- Every completed bullet has actor/condition/action/result.
- Unverified work is not described as done.
- Missing planned checks are named with their reason, without a separate template section.
- Unrelated not-run checks are omitted.
- Test-case gaps are reported only when abnormal.
- Technical evidence is translated into product confidence.
- The answer can be forwarded without explaining the codebase.

## Reference

Read `references/patterns.md` when you need examples of good functional slices, bad status slices, evidence translation, or sample output.
