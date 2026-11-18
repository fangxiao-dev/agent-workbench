"""Markdown helpers and Journey spec parsing/coverage."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .state_core import (
    FIXED_COMMIT_RE,
    StateError,
    _is_ancestor,
    _read,
    _run_git_result,
)


def _markdown_section(text: str, title: str, level: int, spec_label: str = "spec.md") -> list[str]:
    lines = text.splitlines()
    pattern = re.compile(rf"^{'#' * level} {re.escape(title)}[ \t]*$")
    matches = [index for index, line in enumerate(lines) if pattern.fullmatch(line)]
    if len(matches) != 1:
        raise StateError(f"{spec_label} must contain exactly one {'#' * level} {title} section")
    start = matches[0] + 1
    end = len(lines)
    for index in range(start, len(lines)):
        heading = re.match(r"^(#+)\s", lines[index])
        if heading and len(heading.group(1)) <= level:
            end = index
            break
    return lines[start:end]


def _table_cells(line: str, label: str) -> list[str]:
    value = line.strip()
    if not value.startswith("|") or not value.endswith("|"):
        raise StateError(f"{label} must use a pipe-delimited Markdown table")
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", value[1:-1])]


def _markdown_table(lines: list[str], columns: tuple[str, ...], label: str) -> list[dict[str, str]]:
    rows = [line.strip() for line in lines if line.strip().startswith("|")]
    if len(rows) < 2:
        raise StateError(f"{label} is missing its Markdown table header or separator")
    header = _table_cells(rows[0], label)
    if tuple(header) != columns:
        raise StateError(f"{label} columns must be: {' | '.join(columns)}")
    separator = _table_cells(rows[1], label)
    if len(separator) != len(columns) or any(re.fullmatch(r":?-{3,}:?", cell) is None for cell in separator):
        raise StateError(f"{label} has an invalid Markdown table separator")
    result: list[dict[str, str]] = []
    for number, line in enumerate(rows[2:], start=1):
        cells = _table_cells(line, label)
        if len(cells) != len(columns):
            raise StateError(f"{label} row {number} has {len(cells)} cells; expected {len(columns)}")
        if any(not cell for cell in cells):
            raise StateError(f"{label} row {number} contains an empty cell")
        result.append(dict(zip(columns, cells, strict=True)))
    return result


def _chapter_headings(text: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    parent: int | None = None
    section_seven = False
    numbered_title = re.compile(r"^(\d+(?:\.\d+)*)(?:[.)])?\s+(.+)$")
    for line in text.splitlines():
        match = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if match is None:
            continue
        level = len(match.group(1))
        title = match.group(2)
        number_match = numbered_title.fullmatch(title)
        number = number_match.group(1) if number_match else None
        plain_title = number_match.group(2) if number_match else title
        if level == 2:
            section_seven = number == "7"
            parent = len(headings)
        headings.append({
            "index": len(headings),
            "level": level,
            "title": title,
            "plainTitle": plain_title,
            "number": number,
            "parent": parent if level == 3 else None,
            "sectionSeven": section_seven,
        })
    return headings


def _chapter_references(value: str, label: str, *, allow_none: bool) -> list[str]:
    if allow_none and value.casefold() == "none":
        return []
    if not value.strip():
        raise StateError(f"{label} must be a chapter reference list separated by ', ', or none")
    references = [item.strip() for item in value.split(", ")]
    if any(not item or item.casefold() == "none" or "," in item for item in references):
        raise StateError(f"{label} must be a chapter reference list separated by ', ', or none")
    return references


def _resolve_chapter_reference(reference: str, headings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if reference.startswith("§"):
        number = reference[1:]
        if re.fullmatch(r"\d+(?:\.\d+)?", number) is None:
            return None
        matches = [heading for heading in headings if heading["number"] == number]
    else:
        matches = [
            heading for heading in headings
            if heading["title"] == reference or heading["plainTitle"] == reference
        ]
    return matches[0] if len(matches) == 1 else None


def _chapter_label(heading: dict[str, Any]) -> str:
    if heading["number"]:
        return f"§{heading['number']} ({heading['title']})"
    return f"“{heading['title']}”"


def _spec_coverage_findings(
    text: str,
    rule_rows: list[dict[str, str]],
    no_acceptance_value: str,
    spec_label: str,
) -> list[str]:
    headings = _chapter_headings(text)
    findings: list[str] = []
    covered: set[int] = set()
    not_required: set[int] = set()

    def resolve_references(value: str, label: str, *, allow_none: bool) -> list[dict[str, Any]]:
        try:
            references = _chapter_references(value, label, allow_none=allow_none)
        except StateError as exc:
            findings.append(f"{label}：{exc}")
            return []
        resolved: list[dict[str, Any]] = []
        for reference in references:
            heading = _resolve_chapter_reference(reference, headings)
            if heading is None:
                findings.append(
                    f"{label} 引用 {reference!r} 未能唯一解析到 spec 标题；请改为实际章节编号（§N/§N.M）或标题原文。"
                )
                continue
            resolved.append(heading)
        return resolved

    for row in rule_rows:
        label = f"{spec_label} §7 Rule Matrix 的 Rule {row['Rule']} Source"
        for source in resolve_references(row["Source"], label, allow_none=False):
            covered.add(source["index"])
    no_acceptance_label = f"{spec_label} §7 Rule Matrix 的‘无需验收的章节’行"
    not_required.update(
        heading["index"]
        for heading in resolve_references(no_acceptance_value, no_acceptance_label, allow_none=True)
    )

    excluded_titles = {"Journeys", "Rule Matrix", "Required Suites"}
    for heading in headings:
        if heading["sectionSeven"] or heading["title"] in excluded_titles or heading["plainTitle"] in excluded_titles:
            continue
        is_covered = heading["index"] in covered or heading["index"] in not_required
        if not is_covered and heading["level"] == 3 and heading["parent"] is not None:
            is_covered = heading["parent"] in covered or heading["parent"] in not_required
        if not is_covered and heading["level"] == 2:
            # 只有子节的父标题：所有子节都已分类即视为已分类
            children = [item for item in headings if item["parent"] == heading["index"]]
            is_covered = bool(children) and all(item["index"] in covered or item["index"] in not_required for item in children)
        if not is_covered:
            findings.append(
                f"{spec_label} {_chapter_label(heading)} 未分类；请在 §7 Rule Matrix 增加引用该章节的规则行，或加入‘无需验收的章节’行。"
            )
    return findings


def _journey_spec_text(text: str, spec_label: str = "spec.md") -> dict[str, Any]:
    journey_section = _markdown_section(text, "Journeys", 3, spec_label)
    headings: list[tuple[int, str, str]] = []
    for index, line in enumerate(journey_section):
        if not line.startswith("#### "):
            continue
        match = re.fullmatch(r"####\s+(J\d+)\s+(.+?)\s*", line)
        if match is None:
            raise StateError(f"invalid Journey heading in spec.md: {line.strip()}")
        headings.append((index, match.group(1), match.group(2)))
    if not headings:
        raise StateError("spec.md Journeys section must contain at least one #### J<n> <terminal> heading")

    journeys: list[dict[str, Any]] = []
    steps: dict[str, dict[str, str]] = {}
    journey_ids: set[str] = set()
    for position, (start, identifier, terminal) in enumerate(headings):
        if identifier in journey_ids:
            raise StateError(f"duplicate Journey ID: {identifier}")
        journey_ids.add(identifier)
        end = headings[position + 1][0] if position + 1 < len(headings) else len(journey_section)
        block = journey_section[start + 1:end]
        preparation_lines = [line.strip() for line in block if line.strip().startswith("准备：")]
        if len(preparation_lines) > 1:
            raise StateError(f"Journey {identifier} may contain only one 准备： line")
        preparation = None
        if preparation_lines:
            match = re.fullmatch(r"准备：\s*(.+?)\s*", preparation_lines[0])
            if match is None:
                raise StateError(f"Journey {identifier} 准备： must contain text")
            preparation = match.group(1).strip()

        columns = ("Step", "角色", "入口类型", "控件", "操作入口", "观察表面", "预期", "承接")
        try:
            table = _markdown_table(block, columns, f"{spec_label} Journey {identifier} steps")
        except StateError as exc:
            if "columns must be:" in str(exc):
                raise StateError(
                    f"{spec_label} Journey {identifier} steps must use the 3.6 header: "
                    + " | ".join(columns)
                ) from exc
            raise
        if not table:
            raise StateError(f"Journey {identifier} must contain at least one step")
        if all(row["入口类型"] == "记录" for row in table):
            raise StateError(f"Journey {identifier} cannot consist only of 记录 steps")
        journey_steps: list[dict[str, str]] = []
        for number, row in enumerate(table, start=1):
            step_id = row["Step"]
            if step_id != f"{identifier}-S{number}":
                raise StateError(f"Journey {identifier} steps must be ordered and named {identifier}-S1, {identifier}-S2, ...")
            if number == 1 and row["承接"] != "—":
                raise StateError(f"{spec_label} Journey {identifier} 第 1 步 {step_id} 的承接必须为 —")
            if row["入口类型"] not in {"页面", "文件", "记录"}:
                raise StateError(f"{spec_label} Journey {step_id} 入口类型必须是 页面、文件 或 记录")
            if row["入口类型"] == "记录" and number == 1:
                raise StateError(f"{spec_label} Journey 第 1 步 {step_id} 不能是记录")
            if row["入口类型"] == "页面" and row["控件"] == "—":
                raise StateError(f"{spec_label} Journey {step_id} 页面步必须填写控件可见名称")
            if row["入口类型"] in {"文件", "记录"} and row["控件"] != "—":
                raise StateError(f"{spec_label} Journey {step_id} 文件或记录步的控件必须为 —")
            if step_id in steps:
                raise StateError(f"duplicate Journey step ID: {step_id}")
            step = {
                "id": step_id,
                "role": row["角色"],
                "entryType": row["入口类型"],
                "control": row["控件"],
                "operationEntry": row["操作入口"],
                "observationSurface": row["观察表面"],
                "expected": row["预期"],
                "handoff": row["承接"],
            }
            journey_steps.append(step)
            steps[step_id] = {**step, "journeyId": identifier}
        journeys.append({"id": identifier, "terminalResult": terminal, "preparation": preparation, "steps": journey_steps})

    matrix_section = _markdown_section(text, "Rule Matrix", 3, spec_label)
    rule_rows = _markdown_table(matrix_section, ("Rule", "Source", "Suite", "Oracle"), f"{spec_label} §7 Rule Matrix")
    table_lines = [index for index, line in enumerate(matrix_section) if line.strip().startswith("|")]
    no_acceptance_lines = [
        (index, line.strip())
        for index, line in enumerate(matrix_section)
        if line.strip().startswith("- 无需验收的章节：")
    ]
    if len(no_acceptance_lines) != 1 or not table_lines or no_acceptance_lines[0][0] <= table_lines[-1]:
        raise StateError(f"{spec_label} §7 Rule Matrix 表格后必须有一行‘- 无需验收的章节：’并填写章节引用或 none")
    no_acceptance_match = re.fullmatch(r"- 无需验收的章节：\s*(.*?)\s*", no_acceptance_lines[0][1])
    if no_acceptance_match is None or not no_acceptance_match.group(1):
        raise StateError(f"{spec_label} §7 Rule Matrix 的‘无需验收的章节’行必须填写章节引用或 none")
    coverage_findings = _spec_coverage_findings(text, rule_rows, no_acceptance_match.group(1), spec_label)
    if coverage_findings:
        raise StateError("Spec 章节覆盖检查失败：\n- " + "\n- ".join(coverage_findings))
    suite_rows = _markdown_table(_markdown_section(text, "Required Suites", 3, spec_label), ("Suite", "Kind", "Scope", "Entry", "Environment"), f"{spec_label} Required Suites")
    suites: dict[str, dict[str, str]] = {}
    for row in suite_rows:
        suite_id = row["Suite"]
        if suite_id in suites:
            raise StateError(f"duplicate required suite: {suite_id}")
        if row["Kind"] not in {"rule", "safety"}:
            raise StateError(f"suite {suite_id} Kind must be rule or safety")
        if row["Scope"] not in {"ticket", "package"}:
            raise StateError(f"suite {suite_id} Scope must be ticket or package")
        suites[suite_id] = {"id": suite_id, "kind": row["Kind"], "scope": row["Scope"], "entry": row["Entry"], "environment": row["Environment"]}
    rule_ids: set[str] = set()
    for row in rule_rows:
        if row["Rule"] in rule_ids:
            raise StateError(f"duplicate Rule ID: {row['Rule']}")
        rule_ids.add(row["Rule"])
        if row["Suite"] not in suites:
            raise StateError(f"Rule Matrix references unknown required suite: {row['Suite']}")
    return {"journeys": journeys, "steps": steps, "suites": suites, "rules": rule_rows}


def _journey_spec(package: Path) -> dict[str, Any]:
    return _journey_spec_text(_read(package / "spec.md"))


def _frozen_journey_spec(
    package: Path,
    repo: Path,
    revision: str,
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    baseline = acceptance["contractBaseline"]
    if not _is_ancestor(repo, baseline["head"], revision):
        raise StateError(
            "frozen contract baseline is not an ancestor of the Gate comparison commit"
        )
    package_rel = package.resolve().relative_to(repo.resolve()).as_posix()
    spec_path = f"{package_rel}/spec.md"
    code, text, error = _run_git_result(repo, "show", f"{revision}:{spec_path}")
    if code != 0:
        detail = error.strip() or "file not found"
        raise StateError(
            f"frozen contract spec.md is unavailable at {revision}: {detail}"
        )
    code, blob, error = _run_git_result(repo, "rev-parse", "--verify", f"{revision}:{spec_path}")
    if code != 0 or FIXED_COMMIT_RE.fullmatch(blob.strip()) is None:
        detail = error.strip() or blob.strip() or "invalid blob ID"
        raise StateError(f"frozen contract spec.md has no readable Git blob at {revision}: {detail}")
    accepted_blobs = {baseline["files"]["spec.md"]}
    accepted_blobs.update(
        amendment.get("affectedBlobs", {}).get("spec.md")
        for amendment in acceptance["amendments"]
        if amendment.get("affectedBlobs", {}).get("spec.md") is not None
    )
    if blob.strip() not in accepted_blobs:
        raise StateError(
            f"frozen contract spec.md blob {blob.strip()} at {revision} "
            "does not match contractBaseline or a recorded Amendment"
        )
    return _journey_spec_text(text, f"spec.md@{revision[:7]}")


def _journey_expected_surface(step: dict[str, Any]) -> str:
    return {"页面": "page", "文件": "file", "记录": "log"}[step["entryType"]]


def validate_spec_document(path: Path, spec_label: str = "spec.md") -> dict[str, Any]:
    return _journey_spec_text(_read(path), spec_label)


def _coverage_list(value: str, label: str, ticket: str) -> list[str]:
    if value.casefold() == "none":
        return []
    values = [item.strip() for item in value.split(",")]
    if any(not item or item.casefold() == "none" for item in values):
        raise StateError(f"Ticket {ticket} Coverage {label} must be none or a comma-separated list")
    if len(values) != len(set(values)):
        raise StateError(f"Ticket {ticket} Coverage {label} contains duplicates")
    return values


def _ticket_coverage(text: str, ticket: str) -> dict[str, Any]:
    section = _markdown_section(text, "Coverage", 2)
    fields: dict[str, str] = {}
    expected = {"Journey steps", "Suites", "Required review"}
    for line in section:
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        match = re.fullmatch(r"-\s*(Journey steps|Suites|Required review):\s*(.*?)\s*", stripped)
        if match is None:
            raise StateError(f"Ticket {ticket} Coverage contains an invalid row: {stripped}")
        name, value = match.groups()
        if name in fields:
            raise StateError(f"Ticket {ticket} Coverage repeats {name}")
        if not value:
            raise StateError(f"Ticket {ticket} Coverage {name} must not be empty")
        fields[name] = value
    missing = expected - set(fields)
    if missing:
        raise StateError(
            f"Ticket {ticket} Coverage is missing: {', '.join(sorted(missing))}；"
            "## Coverage 须含三行：`- Journey steps: <J1-S1, J1-S2 | none>`、"
            "`- Suites: <S-id | none>`、`- Required review: <none | 说明>`"
        )
    journey_steps = _coverage_list(fields["Journey steps"], "Journey steps", ticket)
    suites = _coverage_list(fields["Suites"], "Suites", ticket)
    if not journey_steps and not suites:
        raise StateError(f"Ticket {ticket} Coverage Journey steps and Suites cannot both be none（至少认领一个 Journey step 或 Suite）")
    return {"journeySteps": journey_steps, "suites": suites, "requiredReview": fields["Required review"]}


def _journey_coverage_errors(spec: dict[str, Any], documents: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    claimed_steps: set[str] = set()
    claimed_suites: set[str] = set()
    for document in documents:
        coverage = document["coverage"]
        for step_id in coverage["journeySteps"]:
            if step_id not in spec["steps"]:
                errors.append(f"Ticket {document['id']} Coverage references unknown Journey step: {step_id}")
            claimed_steps.add(step_id)
        for suite_id in coverage["suites"]:
            if suite_id not in spec["suites"]:
                errors.append(f"Ticket {document['id']} Coverage references unknown suite: {suite_id}")
            claimed_suites.add(suite_id)
    unclaimed_steps = sorted(set(spec["steps"]) - claimed_steps)
    if unclaimed_steps:
        errors.append(
            f"Journey steps have no Ticket Coverage: {', '.join(unclaimed_steps)}"
            "（每个 Attempt 含 patch 都要由其 Ticket 认领 Spec 的全部 Journey step，Gate 只认当前 Attempt 的走查证据）"
        )
    unclaimed_suites = sorted(
        suite_id for suite_id, suite in spec["suites"].items()
        if suite["scope"] == "ticket" and suite_id not in claimed_suites
    )
    if unclaimed_suites:
        errors.append(f"ticket-scope suites have no Ticket Coverage: {', '.join(unclaimed_suites)}")
    return errors


def _validate_journey_coverage(spec: dict[str, Any], documents: list[dict[str, Any]]) -> None:
    errors = _journey_coverage_errors(spec, documents)
    if errors:
        raise StateError("\n".join(errors))
