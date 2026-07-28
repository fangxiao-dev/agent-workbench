#!/usr/bin/env python3
"""Render a validated Explain Diff content spec into one offline HTML document."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import html
import json
import random
import re
from pathlib import Path
from typing import Any


SECTION_IDS = ("background", "intuition", "code")
BLOCK_TYPES = {"paragraph", "callout", "code", "list", "table", "flow", "comparison"}
DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def fail(message: str) -> None:
    raise ValueError(message)


def text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{field} must be a non-empty string")
    return value


def validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        fail("root must be an object")
    title = text(spec.get("title"), "title")
    text(spec.get("summary"), "summary")
    assumption = spec.get("assumption", "")
    if not isinstance(assumption, str):
        fail("assumption must be a string when provided")
    sections = spec.get("sections")
    if not isinstance(sections, list) or [s.get("id") for s in sections if isinstance(s, dict)] != list(SECTION_IDS):
        fail("sections must contain background, intuition, and code in that order")
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            fail(f"sections[{index}] must be an object")
        text(section.get("title"), f"sections[{index}].title")
        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            fail(f"sections[{index}].blocks must be an array")
        for block_index, block in enumerate(blocks):
            validate_block(block, f"sections[{index}].blocks[{block_index}]")
    quiz = spec.get("quiz")
    if not isinstance(quiz, list) or len(quiz) != 5:
        fail("quiz must contain exactly five questions")
    for index, question in enumerate(quiz):
        if not isinstance(question, dict):
            fail(f"quiz[{index}] must be an object")
        text(question.get("question"), f"quiz[{index}].question")
        options = question.get("options")
        if not isinstance(options, list) or len(options) not in (3, 4):
            fail(f"quiz[{index}].options must contain three or four options")
        correct = 0
        for option_index, option in enumerate(options):
            if not isinstance(option, dict):
                fail(f"quiz[{index}].options[{option_index}] must be an object")
            text(option.get("text"), f"quiz[{index}].options[{option_index}].text")
            text(option.get("feedback"), f"quiz[{index}].options[{option_index}].feedback")
            if not isinstance(option.get("correct"), bool):
                fail(f"quiz[{index}].options[{option_index}].correct must be boolean")
            if option["correct"]:
                correct += 1
        if correct != 1:
            fail(f"quiz[{index}] must have exactly one correct option")
    return spec


def validate_block(block: Any, field: str) -> None:
    if not isinstance(block, dict) or block.get("type") not in BLOCK_TYPES:
        fail(f"{field}.type must be one of {sorted(BLOCK_TYPES)}")
    kind = block["type"]
    if kind in {"paragraph", "callout"}:
        text(block.get("text"), f"{field}.text")
        if kind == "callout":
            text(block.get("label"), f"{field}.label")
    elif kind == "code":
        text(block.get("code"), f"{field}.code")
    elif kind == "list":
        if not isinstance(block.get("items"), list) or not block["items"]:
            fail(f"{field}.items must be a non-empty array")
        for index, item in enumerate(block["items"]):
            text(item, f"{field}.items[{index}]")
    elif kind == "table":
        headers = block.get("headers")
        rows = block.get("rows")
        if not isinstance(headers, list) or not headers or not all(isinstance(v, str) for v in headers):
            fail(f"{field}.headers must be a non-empty string array")
        if not isinstance(rows, list):
            fail(f"{field}.rows must be an array")
        for row in rows:
            if not isinstance(row, list) or len(row) != len(headers) or not all(isinstance(v, str) for v in row):
                fail(f"{field}.rows must match headers")
    elif kind == "flow":
        steps = block.get("steps")
        if not isinstance(steps, list) or not steps:
            fail(f"{field}.steps must be a non-empty array")
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                fail(f"{field}.steps[{index}] must be an object")
            text(step.get("label"), f"{field}.steps[{index}].label")
            text(step.get("text"), f"{field}.steps[{index}].text")
    elif kind == "comparison":
        for side in ("before", "after"):
            value = block.get(side)
            if not isinstance(value, dict):
                fail(f"{field}.{side} must be an object")
            text(value.get("label"), f"{field}.{side}.label")
            text(value.get("text"), f"{field}.{side}.text")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_block(block: dict[str, Any]) -> str:
    kind = block["type"]
    if kind == "paragraph":
        return f"<p>{esc(block['text'])}</p>"
    if kind == "callout":
        return f"<aside class=\"callout\"><strong>{esc(block['label'])}</strong><p>{esc(block['text'])}</p></aside>"
    if kind == "code":
        language = esc(block.get("language", "text"))
        return f"<pre><code class=\"language-{language}\">{esc(block['code'])}</code></pre>"
    if kind == "list":
        items = "".join(f"<li>{esc(item)}</li>" for item in block["items"])
        return f"<ul>{items}</ul>"
    if kind == "table":
        headers = "".join(f"<th>{esc(value)}</th>" for value in block["headers"])
        rows = "".join("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in block["rows"])
        return f"<div class=\"table-wrap\"><table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></div>"
    if kind == "flow":
        steps = "".join(f"<li><strong>{esc(step['label'])}</strong><span>{esc(step['text'])}</span></li>" for step in block["steps"])
        return f"<ol class=\"flow\">{steps}</ol>"
    before = block["before"]
    after = block["after"]
    return (
        '<div class="comparison">'
        f"<article><h3>{esc(before['label'])}</h3><p>{esc(before['text'])}</p></article>"
        f"<article><h3>{esc(after['label'])}</h3><p>{esc(after['text'])}</p></article>"
        "</div>"
    )


def ordered_options(title: str, index: int, options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    correct = next(option for option in options if option["correct"] is True)
    distractors = [option for option in options if option is not correct]
    seed = hashlib.sha256(f"{title}:{index}".encode("utf-8")).digest()
    random.Random(seed).shuffle(distractors)
    target_positions = (0, 2, 1, 3, 1)
    # A title-derived rotation varies otherwise identical pages while preserving
    # a balanced, reproducible position pattern. This is not security randomness.
    rotation = hashlib.sha256(f"{title}:position".encode("utf-8")).digest()[0] % len(options)
    target = (target_positions[index] + rotation) % len(options)
    result: list[dict[str, Any]] = []
    distractor_index = 0
    for position in range(len(options)):
        if position == target:
            result.append(correct)
        else:
            result.append(distractors[distractor_index])
            distractor_index += 1
    return result


def render(spec: dict[str, Any]) -> str:
    toc = "".join(f"<li><a href=\"#{esc(section['id'])}\">{esc(section['title'])}</a></li>" for section in spec["sections"])
    sections = "".join(
        f"<section id=\"{esc(section['id'])}\"><h2>{esc(section['title'])}</h2>"
        + "".join(render_block(block) for block in section["blocks"])
        + "</section>"
        for section in spec["sections"]
    )
    if spec.get("assumption"):
        assumption = f"<aside class=\"callout assumption\"><strong>Assumption</strong><p>{esc(spec['assumption'])}</p></aside>"
    else:
        assumption = ""
    cards = []
    answers = []
    for index, question in enumerate(spec["quiz"], start=1):
        options = []
        feedback = []
        for option_index, option in enumerate(ordered_options(spec["title"], index - 1, question["options"])):
            options.append(
                f"<button type=\"button\" data-option-index=\"{option_index}\">{esc(option['text'])}</button>"
            )
            feedback.append(f"<template data-option-index=\"{option_index}\">{esc(option['feedback'])}</template>")
            if option["correct"]:
                answers.append(option_index)
        cards.append(f"<article class=\"quiz-card\"><h3>{index}. {esc(question['question'])}</h3><div class=\"quiz-options\">{''.join(options)}</div>{''.join(feedback)}<p class=\"quiz-feedback\" hidden></p></article>")
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{esc(spec['title'])}</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; line-height: 1.6; color: #1f2937; background: #f5f7fb; }}
body {{ max-width: 980px; margin: 0 auto; padding: 2rem 1rem 4rem; }}
header, section, .quiz-card {{ background: #fff; border: 1px solid #dbe2ea; border-radius: 14px; padding: 1.4rem; margin: 1rem 0; box-shadow: 0 3px 16px #1620330d; }}
h1, h2, h3 {{ line-height: 1.25; color: #102a43; }}
h1 {{ margin-top: 0; }}
a {{ color: #0b63ce; }}
.toc ul {{ display: flex; flex-wrap: wrap; gap: .7rem 1.4rem; padding-left: 1.2rem; }}
.callout {{ border-left: 4px solid #0b63ce; background: #eef6ff; padding: .8rem 1rem; margin: 1rem 0; }}
.callout p {{ margin: .3rem 0 0; }}
.assumption {{ border-left-color: #9a6700; background: #fff8dc; }}
pre {{ overflow-x: auto; padding: 1rem; border-radius: 10px; background: #172033; color: #edf2f7; white-space: pre-wrap; }}
code {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; vertical-align: top; border-bottom: 1px solid #dbe2ea; padding: .6rem; }}
.flow {{ display: grid; gap: .8rem; padding-left: 1.5rem; }}
.flow li {{ padding: .7rem 1rem; background: #f0f5fa; border-radius: 10px; }}
.flow span {{ display: block; }}
.comparison {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }}
.comparison article {{ padding: 1rem; border: 1px solid #dbe2ea; border-radius: 10px; }}
.quiz-options {{ display: grid; gap: .6rem; }}
.quiz-options button {{ text-align: left; border: 1px solid #9fb3c8; border-radius: 9px; background: #fff; padding: .7rem .9rem; cursor: pointer; font: inherit; }}
.quiz-options button:hover, .quiz-options button:focus-visible {{ border-color: #0b63ce; outline: 3px solid #bfdbfe; }}
.quiz-options button[disabled] {{ cursor: default; opacity: .8; }}
.quiz-options button.selected-correct {{ border-color: #18794e; background: #e8f7ef; }}
.quiz-options button.selected-wrong {{ border-color: #b42318; background: #fff0ee; }}
.quiz-feedback {{ padding: .7rem 1rem; border-radius: 9px; background: #f0f5fa; }}
@media (max-width: 640px) {{ body {{ padding: 1rem .6rem 3rem; }} .comparison {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header><h1>{esc(spec['title'])}</h1><p>{esc(spec['summary'])}</p>{assumption}</header>
<nav class="toc" aria-label="Table of contents"><h2>Contents</h2><ul>{toc}<li><a href="#quiz">Quiz</a></li></ul></nav>
{sections}
<section id="quiz"><h2>Quiz</h2>{''.join(cards)}</section>
<script>
(() => {{
  const answers = {json.dumps(answers)};
  document.querySelectorAll('.quiz-card').forEach((card, cardIndex) => {{
    const feedback = card.querySelector('.quiz-feedback');
    card.querySelectorAll('button').forEach((button) => button.addEventListener('click', () => {{
      if (card.dataset.answered) return;
      card.dataset.answered = 'true';
      card.querySelectorAll('button').forEach((option) => {{ option.disabled = true; }});
      const optionIndex = Number(button.dataset.optionIndex);
      const correct = optionIndex === answers[cardIndex];
      button.classList.add(correct ? 'selected-correct' : 'selected-wrong');
      const feedbackTemplate = card.querySelector(`template[data-option-index="${{optionIndex}}"]`);
      feedback.textContent = feedbackTemplate.content.textContent;
      feedback.hidden = false;
    }}));
  }});
}})();
</script>
</body>
</html>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        if not DATE_PREFIX.match(args.output.name):
            fail("output filename must start with YYYY-MM-DD-")
        if args.output.suffix.lower() != ".html":
            fail("output filename must use the .html extension")
        if args.output.name[:10] != date.today().isoformat():
            fail(f"output filename must start with today's date {date.today().isoformat()}-")
        output = args.output.resolve()
        repo_root = args.repo_root.resolve()
        input_path = args.input.resolve()
        try:
            input_path.relative_to(repo_root)
        except ValueError:
            pass
        else:
            fail("input must be outside --repo-root")
        try:
            output.relative_to(repo_root)
        except ValueError:
            pass
        else:
            fail("output must be outside --repo-root")
        spec = validate_spec(json.loads(input_path.read_text(encoding="utf-8")))
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output.open("x", encoding="utf-8") as artifact:
                artifact.write(render(spec))
        except FileExistsError:
            fail("output already exists; choose a new path instead of overwriting it")
        print(output)
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
