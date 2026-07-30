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
ROLE_VALUES = ("removed", "retained", "added", "transition", "neutral")
DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")
LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
ROLE_LABELS = {
    "en": {
        "removed": "Removed",
        "retained": "Retained",
        "added": "Added",
        "transition": "Transition",
        "neutral": "Context",
    },
    "zh": {
        "removed": "移除",
        "retained": "保留",
        "added": "新增",
        "transition": "迁移期",
        "neutral": "背景",
    },
}
UI_LABELS = {
    "en": {"assumption": "Assumption", "contents": "Contents", "quiz": "Quiz", "legend": "Visual legend"},
    "zh": {"assumption": "前提", "contents": "目录", "quiz": "理解检查", "legend": "视觉图例"},
}


def fail(message: str) -> None:
    raise ValueError(message)


def text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{field} must be a non-empty string")
    return value


def validate_role(value: Any, field: str) -> None:
    if value is not None and value not in ROLE_VALUES:
        fail(f"{field} must be one of {list(ROLE_VALUES)}")


def validate_annotated_text(value: Any, field: str) -> None:
    if isinstance(value, str):
        text(value, field)
        return
    if not isinstance(value, dict):
        fail(f"{field} must be a string or annotated text object")
    text(value.get("text"), f"{field}.text")
    validate_role(value.get("role"), f"{field}.role")


def validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        fail("root must be an object")
    title = text(spec.get("title"), "title")
    text(spec.get("summary"), "summary")
    assumption = spec.get("assumption", "")
    if not isinstance(assumption, str):
        fail("assumption must be a string when provided")
    lang = spec.get("lang", "en")
    if not isinstance(lang, str) or not LANGUAGE_TAG.fullmatch(lang):
        fail("lang must be a simple BCP 47 language tag such as en or zh-CN")
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
            validate_role(block.get("role"), f"{field}.role")
    elif kind == "code":
        text(block.get("code"), f"{field}.code")
        validate_role(block.get("role"), f"{field}.role")
    elif kind == "list":
        if not isinstance(block.get("items"), list) or not block["items"]:
            fail(f"{field}.items must be a non-empty array")
        for index, item in enumerate(block["items"]):
            validate_annotated_text(item, f"{field}.items[{index}]")
    elif kind == "table":
        headers = block.get("headers")
        rows = block.get("rows")
        if not isinstance(headers, list) or not headers or not all(isinstance(v, str) for v in headers):
            fail(f"{field}.headers must be a non-empty string array")
        if not isinstance(rows, list):
            fail(f"{field}.rows must be an array")
        for row_index, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(headers):
                fail(f"{field}.rows must match headers")
            for cell_index, cell in enumerate(row):
                validate_annotated_text(cell, f"{field}.rows[{row_index}][{cell_index}]")
    elif kind == "flow":
        steps = block.get("steps")
        if not isinstance(steps, list) or not steps:
            fail(f"{field}.steps must be a non-empty array")
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                fail(f"{field}.steps[{index}] must be an object")
            text(step.get("label"), f"{field}.steps[{index}].label")
            text(step.get("text"), f"{field}.steps[{index}].text")
            validate_role(step.get("role"), f"{field}.steps[{index}].role")
    elif kind == "comparison":
        for side in ("before", "after"):
            value = block.get(side)
            if not isinstance(value, dict):
                fail(f"{field}.{side} must be an object")
            text(value.get("label"), f"{field}.{side}.label")
            text(value.get("text"), f"{field}.{side}.text")
            validate_role(value.get("role"), f"{field}.{side}.role")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def role_class(role: Any) -> str:
    return f" role-{esc(role)}" if role else ""


def role_panel_class(role: Any) -> str:
    return f" role-panel{role_class(role)}" if role else ""


def role_label(role: str, lang: str) -> str:
    labels = ROLE_LABELS["zh"] if lang.lower().startswith("zh") else ROLE_LABELS["en"]
    return labels[role]


def ui_labels(lang: str) -> dict[str, str]:
    return UI_LABELS["zh"] if lang.lower().startswith("zh") else UI_LABELS["en"]


def role_chip(role: Any, lang: str) -> str:
    if not role:
        return ""
    return f'<span class="role-chip">{esc(role_label(role, lang))}</span>'


def render_annotated(value: Any, lang: str) -> str:
    if isinstance(value, str):
        return esc(value)
    role = value.get("role")
    return f'<span class="annotated{role_class(role)}">{role_chip(role, lang)}<span>{esc(value["text"])}</span></span>'


def render_block(block: dict[str, Any], lang: str) -> str:
    kind = block["type"]
    if kind == "paragraph":
        return f"<p>{esc(block['text'])}</p>"
    if kind == "callout":
        role = block.get("role")
        return f'<aside class="callout{role_panel_class(role)}">{role_chip(role, lang)}<strong>{esc(block["label"])}</strong><p>{esc(block["text"])}</p></aside>'
    if kind == "code":
        language = esc(block.get("language", "text"))
        role = block.get("role")
        classes = f' class="role-panel{role_class(role)}"' if role else ""
        return f'<pre{classes}><code class="language-{language}">{esc(block["code"])}</code></pre>'
    if kind == "list":
        items = "".join(
            f'<li class="{role_class(item.get("role")).strip() if isinstance(item, dict) else ""}">{render_annotated(item, lang)}</li>'
            for item in block["items"]
        )
        return f'<ul class="content-list">{items}</ul>'
    if kind == "table":
        headers = "".join(f"<th>{esc(value)}</th>" for value in block["headers"])
        rows = "".join("<tr>" + "".join(f"<td>{render_annotated(value, lang)}</td>" for value in row) + "</tr>" for row in block["rows"])
        return f"<div class=\"table-wrap\"><table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></div>"
    if kind == "flow":
        steps = "".join(
            f'<li class="{role_panel_class(step.get("role")).strip()}">{role_chip(step.get("role"), lang)}<strong>{esc(step["label"])}</strong><span>{esc(step["text"])}</span></li>'
            for step in block["steps"]
        )
        return f"<ol class=\"flow\">{steps}</ol>"
    before = block["before"]
    after = block["after"]
    return (
        '<div class="comparison">'
        f'<article class="{role_panel_class(before.get("role")).strip()}">{role_chip(before.get("role"), lang)}<h3>{esc(before["label"])}</h3><p>{esc(before["text"])}</p></article>'
        f'<article class="{role_panel_class(after.get("role")).strip()}">{role_chip(after.get("role"), lang)}<h3>{esc(after["label"])}</h3><p>{esc(after["text"])}</p></article>'
        "</div>"
    )


def roles_used(spec: dict[str, Any]) -> list[str]:
    found: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            role = value.get("role")
            if role in ROLE_VALUES:
                found.add(role)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(spec["sections"])
    return [role for role in ROLE_VALUES if role in found]


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
    lang = spec.get("lang", "en")
    labels = ui_labels(lang)
    toc = "".join(f"<li><a href=\"#{esc(section['id'])}\">{esc(section['title'])}</a></li>" for section in spec["sections"])
    sections = "".join(
        f"<section id=\"{esc(section['id'])}\"><h2>{esc(section['title'])}</h2>"
        + "".join(render_block(block, lang) for block in section["blocks"])
        + "</section>"
        for section in spec["sections"]
    )
    if spec.get("assumption"):
        assumption = f'<aside class="callout assumption"><strong>{esc(labels["assumption"])}</strong><p>{esc(spec["assumption"])}</p></aside>'
    else:
        assumption = ""
    used_roles = roles_used(spec)
    legend_title = labels["legend"]
    legend = ""
    if used_roles:
        legend_items = "".join(
            f'<li class="role-panel role-{esc(role)}">{role_chip(role, lang)}</li>'
            for role in used_roles
        )
        legend = f'<aside class="role-legend" aria-label="{esc(legend_title)}"><strong>{esc(legend_title)}</strong><ul>{legend_items}</ul></aside>'
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
<html lang="{esc(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{esc(spec['title'])}</title>
<style>
:root {{
  color-scheme: light;
  font-family: ui-sans-serif, "Segoe UI Variable Text", "Segoe UI", sans-serif;
  line-height: 1.62;
  color: #263442;
  background: #edf1f3;
  --ink: #142b3b;
  --line: #cfd9df;
  --paper: #fffefb;
  --removed: #c93b5d;
  --removed-soft: #fff1f4;
  --retained: #316bc7;
  --retained-soft: #edf5ff;
  --added: #258b68;
  --added-soft: #edf9f4;
  --transition: #c77b17;
  --transition-soft: #fff7e8;
  --neutral: #687985;
  --neutral-soft: #f2f5f6;
}}
body {{ max-width: 1040px; margin: 0 auto; padding: 2.5rem 1rem 5rem; }}
header, section, .quiz-card {{ background: var(--paper); border: 1px solid var(--line); border-radius: 6px; padding: 1.6rem; margin: 1rem 0; box-shadow: 0 10px 30px #1b34420a; }}
header {{ border-top: 7px solid var(--ink); }}
h1, h2, h3 {{ font-family: ui-serif, "Iowan Old Style", "Palatino Linotype", Georgia, serif; line-height: 1.18; color: var(--ink); letter-spacing: -.015em; }}
h1 {{ margin-top: 0; font-size: clamp(2rem, 5vw, 3.35rem); max-width: none; }}
h2 {{ border-bottom: 1px solid var(--line); padding-bottom: .55rem; }}
a {{ color: #155aa8; text-underline-offset: .18em; }}
.toc ul {{ display: flex; flex-wrap: wrap; gap: .7rem 1.4rem; padding-left: 1.2rem; }}
.callout {{ border-left: 4px solid #0b63ce; background: #eef6ff; padding: .8rem 1rem; margin: 1rem 0; }}
.callout p {{ margin: .3rem 0 0; }}
.assumption {{ border-left-color: #9a6700; background: #fff8dc; }}
pre {{ overflow-x: auto; padding: 1rem; border-radius: 4px; background: #152a38; color: #f3f7f8; white-space: pre-wrap; }}
code {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; vertical-align: top; border-bottom: 1px solid #dbe2ea; padding: .6rem; }}
.content-list {{ padding-left: 1.25rem; }}
.content-list > li {{ margin: .45rem 0; }}
.flow {{ display: grid; gap: .8rem; padding-left: 1.5rem; }}
.flow li {{ padding: .8rem 1rem; background: #f0f5fa; border-radius: 4px; }}
.flow span {{ display: block; }}
.comparison {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }}
.comparison article {{ padding: 1rem; border: 1px solid #dbe2ea; border-radius: 4px; }}
.role-panel {{ --role: var(--neutral); --role-soft: var(--neutral-soft); border-left: 4px solid var(--role) !important; background: var(--role-soft) !important; }}
.role-removed {{ --role: var(--removed); --role-soft: var(--removed-soft); }}
.role-retained {{ --role: var(--retained); --role-soft: var(--retained-soft); }}
.role-added {{ --role: var(--added); --role-soft: var(--added-soft); }}
.role-transition {{ --role: var(--transition); --role-soft: var(--transition-soft); }}
.role-neutral {{ --role: var(--neutral); --role-soft: var(--neutral-soft); }}
pre.role-panel {{ background: #152a38 !important; color: #f3f7f8; }}
.role-chip {{ display: inline-flex; align-items: center; width: max-content; margin: 0 .5rem .45rem 0; border: 1px solid var(--role); border-radius: 999px; padding: .1rem .48rem; color: var(--role); background: var(--paper); font-size: .72rem; font-weight: 750; line-height: 1.35; letter-spacing: .04em; text-transform: uppercase; }}
.annotated {{ display: inline-flex; align-items: baseline; flex-wrap: wrap; gap: .15rem; }}
.annotated .role-chip {{ margin-bottom: 0; }}
.role-legend {{ display: grid; grid-template-columns: minmax(8rem, auto) 1fr; align-items: center; gap: 1rem; margin: 1rem 0; padding: .8rem 1rem; border: 1px solid var(--line); border-radius: 6px; background: #f9fbfb; }}
.role-legend ul {{ display: flex; flex-wrap: wrap; gap: .55rem; margin: 0; padding: 0; list-style: none; }}
.role-legend li {{ border: 0 !important; background: transparent !important; }}
.role-legend .role-chip {{ margin: 0; }}
.quiz-options {{ display: grid; gap: .6rem; }}
.quiz-options button {{ text-align: left; border: 1px solid #9fb3c8; border-radius: 4px; background: #fff; padding: .7rem .9rem; cursor: pointer; font: inherit; }}
.quiz-options button:hover, .quiz-options button:focus-visible {{ border-color: #0b63ce; outline: 3px solid #bfdbfe; }}
.quiz-options button[disabled] {{ cursor: default; opacity: .8; }}
.quiz-options button.selected-correct {{ border-color: #18794e; background: #e8f7ef; }}
.quiz-options button.selected-wrong {{ border-color: #b42318; background: #fff0ee; }}
.quiz-feedback {{ padding: .7rem 1rem; border-radius: 9px; background: #f0f5fa; }}
@media (max-width: 640px) {{ body {{ padding: 1rem .6rem 3rem; }} .comparison {{ grid-template-columns: 1fr; }} .role-legend {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header><h1>{esc(spec['title'])}</h1><p>{esc(spec['summary'])}</p>{assumption}</header>
{legend}
<nav class="toc" aria-label="{esc(labels['contents'])}"><h2>{esc(labels['contents'])}</h2><ul>{toc}<li><a href="#quiz">{esc(labels['quiz'])}</a></li></ul></nav>
{sections}
<section id="quiz"><h2>{esc(labels['quiz'])}</h2>{''.join(cards)}</section>
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
