---
name: research
description: Investigate a bounded question against high-trust primary sources and return source-backed findings for synthesis. Use when the user wants a topic researched, official facts gathered, or a dispatcher routes a research lane; persist a Markdown note only when durable capture is requested.
---

# Research

The main controller owns the research boundary, execution routing, synthesis, and any durable repository artifact.

Durable capture applies when:

- the user asks to save, record, or produce a research document;
- the owning workflow requires a persistent artifact.

1. Frame the research question, its boundaries, and whether the result needs durable capture.
2. Read [`../dispatcher/SKILL.md`](../dispatcher/SKILL.md); the main controller decides how to route the research.
3. Investigate against **primary sources** — official docs, source code, specs, and first-party APIs. Follow each material claim back to the source that owns it, and record unresolved or conflicting evidence explicitly.
4. Return the findings, their sources, and remaining uncertainties to the main controller.
5. The main controller consumes every return, resolves cross-lane conflicts or gaps, and produces the final synthesis.
6. When durable capture was requested, the main controller writes the synthesis to one Markdown file, cites each material claim, follows the repository's existing note convention, and reports the saved path. Otherwise, return the synthesis in the conversation.

The research is complete when every in-scope question is answered or explicitly unresolved, every material claim is traceable to a primary source, and the main controller has consumed the findings into one synthesis.
