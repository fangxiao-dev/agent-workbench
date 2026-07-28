# Explain Diff HTML content schema

The renderer accepts one UTF-8 JSON object. Content is data only; it must not contain HTML tags intended for execution. Markdown is not parsed: use plain text, code text, and the structured blocks below. If an idea does not fit a supported block, explain it in a paragraph or list item rather than inventing HTML or a new block type.

```json
{
  "title": "Short lesson title",
  "summary": "One-paragraph summary of the change.",
  "assumption": "Optional assumption, or an empty string.",
  "sections": [
    {
      "id": "background",
      "title": "Background",
      "blocks": [
        {"type": "paragraph", "text": "..."},
        {"type": "callout", "label": "Invariant", "text": "..."},
        {"type": "code", "language": "ts", "code": "..."},
        {"type": "list", "items": ["...", "..."]},
        {"type": "table", "headers": ["Old", "New"], "rows": [["...", "..."]]},
        {"type": "flow", "steps": [{"label": "Request", "text": "..."}]},
        {"type": "comparison", "before": {"label": "Before", "text": "..."}, "after": {"label": "After", "text": "..."}}
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
- `sections` contains exactly one section with each ID `background`, `intuition`, and `code`, in that exact order; Quiz remains top-level and is not included in this array.
- Every block uses one of `paragraph`, `callout`, `code`, `list`, `table`, `flow`, or `comparison`.
- `quiz` contains exactly five questions.
- Each question has three or four non-empty options, every `correct` value is a JSON boolean, exactly one `correct: true` option, and feedback for every option.

The renderer escapes all values. Use plain text and code, not raw HTML or Markdown that expects to be interpreted.
