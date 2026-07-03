---
name: talk-to-boss
description: Use when the user wants a boss-readable or stakeholder-readable progress update, final task report, asks for "给老板看/给人看的进度/任务进度", criticizes a status as too technical, or asks to rewrite progress by functional slice, spec, user impact, relevant not-run checks, test-case gaps, or "谁能/不能做什么，导致什么结果".
---

# Talk To Boss

Turn implementation progress into a boss-readable functional status. The deliverable is not a work log. It is a clear statement of what product behavior is now supported, what remains unproven, and whether the requirement can be called done.

Use Chinese by default when the user writes Chinese. Keep product vocabulary such as `Inventory Item`, `Product SKU`, `threshold`, `Lark`, `smoke`, and `review` when those are the domain terms.

## Workflow

1. Extract the functional contract from the available context.
   - Identify user-visible capabilities, rules, and protected behaviors.
   - Treat files, tests, agents, commits, and tools as evidence, not as the main story.
   - Completion criterion: every major engineering item is mapped to a product behavior or marked as internal evidence only.

2. Group by functional slice.
   - A functional slice is a product capability or rule a stakeholder can understand.
   - Do not group by DAG node, code layer, test type, file, or agent.
   - Completion criterion: each top-level slice could be used as a section title in a product spec.

3. Write each completed behavior as a spec sentence.
   - Use this shape: `[Actor/System] 在 [condition] 下 可以/不能 [action]，导致 [observable result or business impact]。`
   - Prefer capability and consequence over implementation detail.
   - Completion criterion: each bullet answers who can or cannot do what, under what condition, and what result follows.

4. Separate implementation completion from requirement closure.
   - Say `已实现，待验收` when code and local tests pass but real UI/data-source acceptance is missing.
   - Say `不能宣称 closed` when a required smoke, browser check, external data check, or final review is still pending.
   - Completion criterion: the reader can tell what is done, what is only locally proven, and what still blocks closure.

5. Fold missing planned checks into the relevant slice.
   - Only mention a not-run check when it was actually designed, required, or expected for this task and was not run.
   - Fuse `Not run` and `Why not` into one natural bullet under `还缺`, for example: `Lark Test Environment 写入/读回 smoke 还没跑，因为本轮还没完成 Test Env mutation 验收。`
   - Do not list unrelated external systems. If the task does not involve Lark, Lexware, email, public deployment, or another integration, omit them entirely.
   - Do not add a separate `Not run` / `Why not` template section unless the user explicitly asks for an audit template.
   - Completion criterion: every missing planned check has a concrete reason, and no irrelevant boilerplate checks appear.

6. Report test-case gaps only when abnormal.
   - If existing tests or smoke paths cover the task adequately, do not write a `Test-case gap judgment` section.
   - If there is a real gap, state it inside `风险/备注` or `剩余收口`, with the missing scenario and why it matters.
   - Completion criterion: test-case gap language appears only when it changes the follow-up work.

7. Translate evidence into confidence.
   - Convert service/action/integration tests, i18n checks, type checks, browser verification, Lark smoke, and reviews into stakeholder meaning.
   - Mention raw commands only when the user asks for audit detail.
   - Completion criterion: technical evidence explains confidence instead of becoming a tool chronology.

8. Produce a concise forwardable update.
   - Start with `整体判断`.
   - Then use `功能 Slice 进度`.
   - End with `剩余收口` when there are open gates.
   - Completion criterion: a non-implementer can understand whether the requirement is done and what remains.

## Output Shape

Use this shape unless the user asks for another format:

```markdown
**整体判断**
[One or two sentences: completion confidence, what is done, what blocks closure.]

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

## Quality Gate

Before answering, rewrite if any check fails:

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
