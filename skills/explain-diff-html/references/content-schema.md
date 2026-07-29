# Explain Diff HTML content schema

The renderer accepts one UTF-8 JSON object. Content is data only; it must not contain HTML tags intended for execution. Markdown is not parsed: use plain text, code text, and the structured blocks below. If an idea does not fit a supported block, explain it in a paragraph or list item rather than inventing HTML or a new block type.

```json
{
  "title": "Short lesson title",
  "summary": "One-paragraph summary of the change.",
  "assumption": "Optional assumption, or an empty string.",
  "lang": "en",
  "sections": [
    {
      "id": "background",
      "title": "Background",
      "blocks": [
        {"type": "paragraph", "text": "..."},
        {"type": "callout", "label": "Invariant", "text": "...", "role": "neutral"},
        {"type": "code", "language": "ts", "code": "...", "role": "retained"},
        {"type": "list", "items": ["Plain legacy item", {"text": "Tagged item", "role": "removed"}]},
        {"type": "table", "headers": ["Old", "New"], "rows": [[{"text": "Lark", "role": "removed"}, {"text": "Postgres", "role": "added"}]]},
        {"type": "flow", "steps": [{"label": "Request", "text": "...", "role": "retained"}]},
        {"type": "comparison", "before": {"label": "Before", "text": "...", "role": "removed"}, "after": {"label": "After", "text": "...", "role": "added"}}
      ]
    },
    {"id": "intuition", "title": "Intuition", "blocks": []},
    {"id": "code", "title": "Code", "blocks": []}
  ],
  "quiz": [
    {
      "question": "What changes when ...?",
      "options": [
        {"text": "A plausible answer", "correct": false, "feedback": "This would be true only if ..."},
        {"text": "The correct answer", "correct": true, "feedback": "Correct: ..."},
        {"text": "Another plausible answer", "correct": false, "feedback": "This confuses ... with ..."}
      ]
    },
    {"question": "Question 2", "options": [{"text": "A", "correct": true, "feedback": "Correct."}, {"text": "B", "correct": false, "feedback": "Not this one."}, {"text": "C", "correct": false, "feedback": "Not this one."}]},
    {"question": "Question 3", "options": [{"text": "A", "correct": true, "feedback": "Correct."}, {"text": "B", "correct": false, "feedback": "Not this one."}, {"text": "C", "correct": false, "feedback": "Not this one."}]},
    {"question": "Question 4", "options": [{"text": "A", "correct": true, "feedback": "Correct."}, {"text": "B", "correct": false, "feedback": "Not this one."}, {"text": "C", "correct": false, "feedback": "Not this one."}]},
    {"question": "Question 5", "options": [{"text": "A", "correct": true, "feedback": "Correct."}, {"text": "B", "correct": false, "feedback": "Not this one."}, {"text": "C", "correct": false, "feedback": "Not this one."}]}
  ]
}
```

Required values:

- `title` and `summary` are non-empty strings.
- `lang` is optional and defaults to `en`. When present, use a simple BCP 47 tag such as `en`, `de`, or `zh-CN`; the renderer uses it for the document language and built-in role labels.
- `sections` contains exactly one section with each ID `background`, `intuition`, and `code`, in that exact order; Quiz remains top-level and is not included in this array.
- Every block uses one of `paragraph`, `callout`, `code`, `list`, `table`, `flow`, or `comparison`.
- `quiz` contains exactly five questions.
- Each question has three or four non-empty options, every `correct` value is a JSON boolean, exactly one `correct: true` option, and feedback for every option.

## Semantic visual roles

Use the optional `role` field when a visual element has a lifecycle meaning. Supported values are:

- `removed` — leaves the target runtime.
- `retained` — remains in place, even if its responsibility narrows.
- `added` — exists in the target architecture.
- `transition` — only exists as a migration environment, gate, or temporary control.
- `neutral` — context without a lifecycle claim.

Roles are supported on `callout` and `code` blocks, individual `flow.steps`, each side of a `comparison`, and annotated `list` items or `table` cells. Existing string-only lists and tables remain valid. When at least one role is present, the renderer adds a legend automatically and renders both color and a visible text chip, so meaning never depends on color alone.

Use roles consistently across the explanation. If a legend would not help distinguish actual nodes, steps, or cells, omit roles instead of adding a decorative legend.

The renderer escapes all values. Use plain text and code, not raw HTML or Markdown that expects to be interpreted.
