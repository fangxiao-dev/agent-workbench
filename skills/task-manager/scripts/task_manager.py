#!/usr/bin/env python3
"""Dry-run, validate, and optionally apply TaskManager vault updates."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


STATUSES = {"计划中", "实施中", "验证中", "阻塞", "搁置", "已完成"}
PRIORITIES = {"当前", "下一批", "未来规划"}
TASK_TYPES = {"新增功能", "bug", "功能优化"}
VERIFICATION_PATHS = {"本地链路", "真实链路", "部分真实链路", "不涉及"}
WORKSPACES = {"主工作区", "worktree"}
SOURCE_TYPES = {"impl-plan", "source-note", "discussion", "handoff"}

LIST_FIELDS = {
    "状态": STATUSES,
    "优先级": PRIORITIES,
    "任务类型": TASK_TYPES,
    "验证链路": VERIFICATION_PATHS,
    "工作区": WORKSPACES,
    "来源类型": SOURCE_TYPES,
}

FIELD_MAP = {
    "status": "状态",
    "priority": "优先级",
    "taskType": "任务类型",
    "verificationPath": "验证链路",
    "workspace": "工作区",
    "source": "来源",
    "slug": "slug",
    "projectId": "项目ID",
    "sourceType": "来源类型",
    "sourceRelativePath": "来源相对路径",
}

SECTION_MAP = {
    "source": "来源链接/路径",
    "progress": "当前进度",
    "nextStep": "下一步建议",
    "verificationStatus": "验证状态",
    "residualRisk": "残余风险",
}

REQUIRED_SECTIONS = ["来源链接/路径", "当前进度", "下一步建议", "验证状态", "残余风险"]

TRACK_HINTS = [
    "00_Config/",
    "10_Tasks/",
    "20_Sources/",
    "30_Bases/",
    "40_Dashboards/",
    "40_Reports/",
    "90_Archive/",
    "Templates/",
    "README.md",
    "Task Dashboard.md",
    ".obsidian/community-plugins.json",
    ".obsidian/core-plugins.json",
    ".obsidian/templates.json",
    ".obsidian/types.json",
    ".obsidian/app.json",
    ".obsidian/appearance.json",
    ".obsidian/snippets/",
    ".obsidian/plugins/good-bases/",
    ".obsidian/plugins/tray/",
]

IGNORE_HINTS = [
    ".obsidian/workspace-mobile.json",
    ".obsidian/cache/",
    ".obsidian/logs/",
    ".trash/",
    ".obsidian/plugins/*/data.json",
    ".obsidian/workspace.json",
    ".obsidian/hotkeys.json",
    "00_Config/projects.local.yml",
]

TYPES_ADDITIONS = {
    "项目ID": "text",
    "项目名称": "text",
    "slug": "text",
    "slugAliases": "multitext",
    "来源相对路径": "text",
    "项目": "multitext",
    "来源类型": "multitext",
}

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "templates"


class TaskError(Exception):
    pass


def today() -> str:
    return dt.date.today().isoformat()


def slug_to_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', " ", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        raise TaskError("taskName cannot produce a valid filename")
    return f"{cleaned}.md"


def task_slug_to_filename(slug: Any) -> str:
    if not isinstance(slug, str):
        raise TaskError("slug must be a string")
    cleaned = slug.strip()
    if cleaned.lower().endswith(".md"):
        cleaned = cleaned[:-3].strip()
    if not cleaned:
        raise TaskError("slug is required when provided")
    if cleaned in {".", ".."} or all(ch == "." for ch in cleaned):
        raise TaskError("slug must not be dot-only or relative-directory syntax")
    if "/" in cleaned.replace("\\", "/"):
        raise TaskError("slug must not contain directories")
    if re.search(r'[<>:"/\\|?*\x00-\x1F]', cleaned):
        raise TaskError('slug must not contain invalid filename characters: <>:"/\\|?*')
    return f"{cleaned}.md"


def payload_slug(payload: dict[str, Any]) -> str | None:
    if "slug" not in payload or payload["slug"] is None:
        return None
    return task_slug_to_filename(payload["slug"])[:-3]


def normalize_slug_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, list):
        raw_values = value
    else:
        raise TaskError("slugAliases must be a string or list of strings")
    aliases: list[str] = []
    for item in raw_values:
        alias = task_slug_to_filename(item)[:-3]
        if alias not in aliases:
            aliases.append(alias)
    return aliases


def payload_slug_aliases(payload: dict[str, Any]) -> list[str]:
    if "slugAliases" not in payload:
        return []
    return normalize_slug_aliases(payload["slugAliases"])


def payload_slug_candidates(payload: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    primary = payload_slug(payload)
    if primary:
        candidates.append(primary)
    for alias in payload_slug_aliases(payload):
        if alias not in candidates:
            candidates.append(alias)
    return candidates


def tasks_dir(vault: Path) -> Path:
    return vault / "10_Tasks"


def project_tasks_dir(vault: Path, project_id: str) -> Path:
    return safe_child(tasks_dir(vault), project_id)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip("\n")
    body = text[end + len("\n---") :].lstrip("\n")
    return parse_frontmatter(raw), body


def parse_frontmatter(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            current = data.setdefault(current_key, [])
            if not isinstance(current, list):
                raise TaskError(f"Invalid mixed scalar/list field: {current_key}")
            current.append(unquote_scalar(line[4:].strip()))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if value == "":
            data[key] = []
        else:
            data[key] = unquote_scalar(value)
    return data


def unquote_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        if value[0] == '"':
            try:
                parsed = json.loads(value)
                return str(parsed)
            except json.JSONDecodeError:
                return value[1:-1]
        return value[1:-1]
    return value


def yaml_scalar(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text == "":
        return '""'
    if any(ch in text for ch in [":", "#", "\n", '"', "{", "}", "[", "]"]) or text.strip() != text:
        return json.dumps(text, ensure_ascii=False)
    return text


def render_frontmatter(data: dict[str, Any]) -> str:
    order = [
        "任务名",
        "状态",
        "优先级",
        "任务类型",
        "验证链路",
        "工作区",
        "项目ID",
        "项目",
        "项目名称",
        "来源类型",
        "来源相对路径",
        "来源",
        "创建日期",
        "更新日期",
    ]
    lines = ["---"]
    for key in order:
        if key not in data:
            continue
        append_yaml_field(lines, key, data[key])
    for key, value in data.items():
        if key in order:
            continue
        append_yaml_field(lines, key, value)
    lines.append("---")
    return "\n".join(lines) + "\n"


def append_yaml_field(lines: list[str], key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, list):
        if not value:
            return
        lines.append(f"{key}:")
        for item in value:
            lines.append(f"  - {yaml_scalar(item)}")
    else:
        lines.append(f"{key}: {yaml_scalar(value)}")


def normalize_list(value: Any, field: str) -> list[str]:
    allowed = LIST_FIELDS[field]
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    out: list[str] = []
    for raw in values:
        item = str(raw)
        if item not in allowed:
            raise TaskError(f"{field} has invalid value {item!r}; allowed: {', '.join(sorted(allowed))}")
        out.append(item)
    return out


def require_string_or_none(payload: dict[str, Any], json_key: str) -> None:
    value = payload.get(json_key)
    if value is not None and not isinstance(value, str):
        raise TaskError(f"{json_key} must be a string or null")


def validate_payload(payload: dict[str, Any]) -> None:
    operation = payload.get("operation")
    if operation not in {"create", "update"}:
        raise TaskError("operation must be create or update")
    if not payload.get("taskName"):
        raise TaskError("taskName is required")
    for json_key, yaml_key in FIELD_MAP.items():
        if json_key not in payload:
            continue
        value = payload[json_key]
        if yaml_key in LIST_FIELDS:
            if value is not None:
                normalize_list(value, yaml_key)
        else:
            require_string_or_none(payload, json_key)
    if payload.get("sourceRelativePath"):
        validate_relative_path(str(payload["sourceRelativePath"]), "sourceRelativePath")
    if payload.get("projectId"):
        validate_project_id(str(payload["projectId"]))
    payload_slug(payload)
    payload_slug_aliases(payload)


def validate_project_id(project_id: str) -> None:
    if project_id in {".", ".."} or all(ch == "." for ch in project_id):
        raise TaskError("project id must not be dot-only or relative-directory syntax")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", project_id):
        raise TaskError("project id may only contain letters, numbers, dot, underscore, and hyphen")


def validate_relative_path(value: str, field_name: str) -> None:
    raw = value.replace("\\", "/")
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw) or raw == ".":
        raise TaskError(f"{field_name} must be a relative path")
    parts = [part for part in raw.split("/") if part]
    if any(part == ".." for part in parts):
        raise TaskError(f"{field_name} must not contain .. segments")


def resolve_project_from_args(args: argparse.Namespace, payload: dict[str, Any]) -> str | None:
    cli_project = getattr(args, "project", None)
    payload_project = payload.get("projectId")
    if cli_project:
        validate_project_id(cli_project)
    if payload_project:
        validate_project_id(str(payload_project))
    if cli_project and payload_project and cli_project != payload_project:
        raise TaskError(f"--project {cli_project!r} conflicts with input projectId {payload_project!r}")
    return cli_project or payload_project


def validate_source_type_value(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 1 and value[0] in SOURCE_TYPES


def validate_source_relative_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        validate_relative_path(value, "来源相对路径")
    except TaskError:
        return False
    return True


def ensure_project_upsert_source_metadata(target: Path, payload: dict[str, Any]) -> None:
    source_type_present = "sourceType" in payload and payload["sourceType"] is not None
    source_rel_present = "sourceRelativePath" in payload and payload["sourceRelativePath"] is not None
    if payload.get("operation") == "create":
        if not source_type_present or not source_rel_present:
            raise TaskError("project task create requires sourceType and sourceRelativePath")
        return

    existing_fm, _ = load_task(target)
    effective_source_type = (
        normalize_list(payload["sourceType"], "来源类型")
        if source_type_present
        else existing_fm.get("来源类型")
    )
    effective_source_rel = (
        str(payload["sourceRelativePath"])
        if source_rel_present
        else existing_fm.get("来源相对路径")
    )
    if not validate_source_type_value(effective_source_type):
        raise TaskError("project task update requires sourceType, unless existing task has one valid 来源类型 value")
    if not validate_source_relative_value(effective_source_rel):
        raise TaskError("project task update requires sourceRelativePath, unless existing task has a valid 来源相对路径")


def find_task(
    vault: Path,
    task_name: str,
    project_id: str | None = None,
    slug_candidates: list[str] | None = None,
) -> Path:
    slug_candidates = slug_candidates or []
    filename = task_slug_to_filename(slug_candidates[0]) if slug_candidates else slug_to_filename(task_name)
    expected_stems = {task_slug_to_filename(item)[:-3].lower() for item in slug_candidates}
    expected_stems.add(filename[:-3].lower())
    if project_id:
        directory = project_tasks_dir(vault, project_id)
        search_pattern = "*.md"
    else:
        directory = tasks_dir(vault)
        search_pattern = "*.md"
    direct = directory / filename
    if direct.exists():
        return direct
    matches: list[Path] = []
    if directory.exists():
        for path in directory.glob(search_pattern):
            try:
                fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                continue
            aliases = fm.get("slugAliases", [])
            if not isinstance(aliases, list):
                aliases = []
            if (
                fm.get("任务名") == task_name
                or (isinstance(fm.get("slug"), str) and fm["slug"].lower() in expected_stems)
                or any(isinstance(alias, str) and alias.lower() in expected_stems for alias in aliases)
                or path.stem.lower() == task_name.lower()
                or path.stem.lower() in expected_stems
            ):
                matches.append(path)
    if len(matches) > 1:
        names = ", ".join(str(p) for p in matches)
        raise TaskError(f"Multiple matching task files found: {names}")
    if matches:
        return matches[0]
    if project_id is None:
        project_matches = find_project_task_matches(vault, task_name, slug_candidates)
        if project_matches:
            names = ", ".join(str(p) for p in project_matches)
            raise TaskError(f"Matching project task files require --project: {names}")
    return direct


def find_project_task_matches(vault: Path, task_name: str, slug_candidates: list[str] | None = None) -> list[Path]:
    matches: list[Path] = []
    slug_candidates = slug_candidates or []
    expected_stems = {task_slug_to_filename(item)[:-3].lower() for item in slug_candidates}
    directory = tasks_dir(vault)
    if not directory.exists():
        return matches
    for path in directory.glob("*/*.md"):
        try:
            fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
        aliases = fm.get("slugAliases", [])
        if not isinstance(aliases, list):
            aliases = []
        if (
            fm.get("任务名") == task_name
            or (isinstance(fm.get("slug"), str) and fm["slug"].lower() in expected_stems)
            or any(isinstance(alias, str) and alias.lower() in expected_stems for alias in aliases)
            or path.stem.lower() == task_name.lower()
            or path.stem.lower() in expected_stems
        ):
            matches.append(path)
    return matches


def section_block(title: str, content: str) -> str:
    body = content.strip()
    return f"### {title}\n\n{body}\n\n"


def default_body(task_name: str) -> str:
    blocks = [f"# {task_name}\n"]
    for title in REQUIRED_SECTIONS:
        blocks.append(section_block(title, ""))
    return "\n".join(blocks).rstrip() + "\n"


def markdown_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return path.stem


def replace_document_title(body: str, task_name: str) -> str:
    if re.match(r"^# .*$", body, re.MULTILINE):
        return re.sub(r"^# .*$", f"# {task_name}", body, count=1, flags=re.MULTILINE)
    return f"# {task_name}\n\n{body.lstrip()}"


def replace_section(body: str, title: str, content: str) -> str:
    pattern = re.compile(rf"(^### {re.escape(title)}\s*\n)(.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL)
    replacement = section_block(title, content)
    if pattern.search(body):
        return pattern.sub(replacement, body, count=1)
    if not body.endswith("\n"):
        body += "\n"
    return body + "\n" + replacement


def ensure_sections(body: str) -> str:
    out = body
    for title in REQUIRED_SECTIONS:
        if not re.search(rf"^### {re.escape(title)}\s*$", out, re.MULTILINE):
            if not out.endswith("\n"):
                out += "\n"
            out += "\n" + section_block(title, "")
    return out.rstrip() + "\n"


def source_body(source: str) -> str:
    source = source.strip()
    if not source:
        return ""
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return f"`{source}`"


def apply_payload(
    existing_fm: dict[str, Any],
    existing_body: str,
    payload: dict[str, Any],
    project_name: str | None = None,
) -> tuple[dict[str, Any], str]:
    fm = copy.deepcopy(existing_fm)
    body = existing_body or default_body(payload["taskName"])

    fm["任务名"] = payload["taskName"]
    if "创建日期" not in fm:
        fm["创建日期"] = today()
    fm["更新日期"] = today()
    body = replace_document_title(body, payload["taskName"])

    defaults: dict[str, Any] = {}
    if payload["operation"] == "create":
        defaults = {
            "status": "计划中",
            "verificationPath": "不涉及",
            "workspace": "主工作区",
        }

    merged = {**defaults, **payload}
    project_id = merged.get("projectId")
    if project_id:
        fm["项目ID"] = str(project_id)
        fm["项目"] = [str(project_id)]
        if project_name:
            fm["项目名称"] = project_name

    skip_slug_write = False
    if merged.get("operation") != "create" and "slug" in merged and "slugAliases" not in merged:
        existing_slug = fm.get("slug")
        existing_aliases = fm.get("slugAliases", [])
        if isinstance(existing_slug, str) and isinstance(existing_aliases, list):
            incoming_slug = payload_slug(merged)
            normalized_aliases = normalize_slug_aliases(existing_aliases)
            skip_slug_write = incoming_slug in normalized_aliases and incoming_slug != existing_slug

    for json_key, yaml_key in FIELD_MAP.items():
        if json_key == "projectId" or json_key not in merged:
            continue
        if json_key == "slug" and skip_slug_write:
            continue
        value = merged[json_key]
        if yaml_key in LIST_FIELDS:
            if value is None:
                fm.pop(yaml_key, None)
            else:
                values = normalize_list(value, yaml_key)
                if values:
                    fm[yaml_key] = values
                else:
                    fm.pop(yaml_key, None)
        else:
            if value is None:
                fm.pop(yaml_key, None)
            else:
                fm[yaml_key] = str(value)
    if "slugAliases" in merged:
        if merged["slugAliases"] is None:
            fm.pop("slugAliases", None)
        else:
            aliases = normalize_slug_aliases(merged["slugAliases"])
            primary_slug = payload_slug(merged)
            aliases = [alias for alias in aliases if alias != primary_slug]
            if aliases:
                fm["slugAliases"] = aliases
            else:
                fm.pop("slugAliases", None)

    status_values = fm.get("状态", [])
    if isinstance(status_values, list) and "已完成" in status_values:
        fm["工作区"] = ["主工作区"]
        fm.pop("优先级", None)
    if (
        isinstance(status_values, list)
        and "搁置" in status_values
        and payload.get("priority", None) is None
    ):
        fm.pop("优先级", None)

    if "source" in payload:
        body = replace_section(body, SECTION_MAP["source"], source_body(str(payload.get("source") or "")))
    for json_key in ["progress", "nextStep", "verificationStatus", "residualRisk"]:
        if json_key in payload and payload[json_key] is not None:
            body = replace_section(body, SECTION_MAP[json_key], str(payload[json_key]))

    body = ensure_sections(body)
    return fm, body


def load_task(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, ""
    return split_frontmatter(path.read_text(encoding="utf-8"))


def render_task(fm: dict[str, Any], body: str) -> str:
    return render_frontmatter(fm) + "\n" + body.rstrip() + "\n"


def diff_summary(before: str, after: str) -> dict[str, Any]:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    return {
        "before_lines": len(before_lines),
        "after_lines": len(after_lines),
        "changed": before != after,
    }


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_child(parent: Path, *parts: str) -> Path:
    candidate = parent.joinpath(*parts)
    if not is_within(candidate, parent):
        raise TaskError(f"Resolved path escapes intended parent: {candidate}")
    return candidate


def write_target_for_payload(target: Path, payload: dict[str, Any]) -> Path:
    if payload_slug(payload) is None:
        return target
    desired = target.with_name(slug_to_filename(payload["taskName"]))
    if desired == target:
        return target
    if desired.exists():
        raise TaskError(f"Cannot rename task because target already exists: {desired}")
    return desired


def command_upsert(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    project_id = resolve_project_from_args(args, payload)
    if project_id and not payload.get("projectId"):
        payload["projectId"] = project_id
    validate_payload(payload)

    target = find_task(vault, payload["taskName"], project_id, payload_slug_candidates(payload))
    expected_parent = project_tasks_dir(vault, project_id) if project_id else tasks_dir(vault)
    if not is_within(target, expected_parent):
        raise TaskError(f"Refusing to write outside expected task directory: {target}")
    write_target = write_target_for_payload(target, payload)
    if not is_within(write_target, expected_parent):
        raise TaskError(f"Refusing to write outside expected task directory: {write_target}")
    if project_id:
        ensure_project_upsert_source_metadata(target, payload)

    result = build_task_write(vault, target, payload, args.apply, write_target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_task_write(
    vault: Path,
    target: Path,
    payload: dict[str, Any],
    apply: bool,
    write_target: Path | None = None,
) -> dict[str, Any]:
    write_target = write_target or target
    existing_text = target.read_text(encoding="utf-8") if target.exists() else ""
    fm, body = load_task(target)
    project_name = project_name_for_task(vault, payload.get("projectId"))
    new_fm, new_body = apply_payload(fm, body, payload, project_name)
    next_text = render_task(new_fm, new_body)
    result = {
        "mode": "apply" if apply else "dry-run",
        "target": str(write_target),
        "exists": target.exists(),
        "sourceTarget": str(target) if target.exists() and write_target != target else None,
        "renamed": target.exists() and write_target != target,
        "summary": diff_summary(existing_text, next_text),
        "frontmatter": new_fm,
        "markdown": next_text,
    }
    if apply:
        write_target.parent.mkdir(parents=True, exist_ok=True)
        write_target.write_text(next_text, encoding="utf-8", newline="\n")
        if target.exists() and write_target != target:
            target.unlink()
    return result


def project_name_for_task(vault: Path, project_id: Any) -> str | None:
    if not project_id:
        return None
    projects_path = vault / "00_Config" / "projects.yml"
    if not projects_path.exists():
        return None
    projects = parse_simple_projects(projects_path)
    project = projects.get(str(project_id))
    if not project:
        return None
    return project.get("name")


def validate_task_content(
    path: Path,
    vault: Path,
    fm: dict[str, Any],
    body: str,
    projects: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    for field, allowed in LIST_FIELDS.items():
        if field not in fm:
            continue
        value = fm[field]
        if not isinstance(value, list):
            errors.append(f"{path}: {field} must be a YAML list")
            continue
        for item in value:
            if item not in allowed:
                errors.append(f"{path}: {field} has invalid value {item!r}")
    if "项目" in fm and not isinstance(fm["项目"], list):
        errors.append(f"{path}: 项目 must be a YAML list")
    if "项目ID" in fm and not isinstance(fm["项目ID"], str):
        errors.append(f"{path}: 项目ID must be a scalar string")
    if "项目名称" in fm and not isinstance(fm["项目名称"], str):
        errors.append(f"{path}: 项目名称 must be a scalar string")
    if "来源相对路径" in fm:
        rel = fm["来源相对路径"]
        if not isinstance(rel, str):
            errors.append(f"{path}: 来源相对路径 must be a scalar string")
        else:
            try:
                validate_relative_path(rel, "来源相对路径")
            except TaskError as exc:
                errors.append(f"{path}: {exc}")
    if "slug" in fm:
        try:
            task_slug_to_filename(fm["slug"])
        except TaskError as exc:
            errors.append(f"{path}: {exc}")
    if "slugAliases" in fm:
        try:
            normalize_slug_aliases(fm["slugAliases"])
        except TaskError as exc:
            errors.append(f"{path}: {exc}")

    status = fm.get("状态", [])
    workspace = fm.get("工作区", [])
    if isinstance(status, list) and "已完成" in status:
        if "优先级" in fm:
            errors.append(f"{path}: 已完成 task must not keep 优先级")
        if workspace != ["主工作区"]:
            errors.append(f"{path}: 已完成 task must use 工作区=主工作区")
    if isinstance(status, list) and "搁置" in status and "优先级" in fm:
        errors.append(f"{path}: 搁置 task should not keep 优先级")
    for title in REQUIRED_SECTIONS:
        if not re.search(rf"^### {re.escape(title)}\s*$", body, re.MULTILINE):
            errors.append(f"{path}: missing section ### {title}")

    rel_parts = path.resolve().relative_to(tasks_dir(vault).resolve()).parts
    if len(rel_parts) >= 2:
        project_id = rel_parts[0]
        project_values = fm.get("项目")
        if fm.get("项目ID") != project_id:
            errors.append(f"{path}: 项目ID must match folder name {project_id!r}")
        if project_values != [project_id]:
            errors.append(f"{path}: 项目 must be a single-item list matching folder name {project_id!r}")
        expected_project_name = (projects or {}).get(project_id, {}).get("name")
        if expected_project_name and fm.get("项目名称") != expected_project_name:
            errors.append(f"{path}: 项目名称 must match configured project name {expected_project_name!r}")
        source_type = fm.get("来源类型")
        if "来源类型" not in fm:
            errors.append(f"{path}: project task must include 来源类型")
        elif not validate_source_type_value(source_type):
            errors.append(f"{path}: 来源类型 must be a single-item YAML list with one valid value")
        source_relative_path = fm.get("来源相对路径")
        if "来源相对路径" not in fm:
            errors.append(f"{path}: project task must include 来源相对路径")
        elif not validate_source_relative_value(source_relative_path):
            errors.append(f"{path}: 来源相对路径 must be a valid scalar relative path")
    return errors


def validate_task(path: Path, vault: Path, projects: dict[str, dict[str, str]] | None = None) -> list[str]:
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    return validate_task_content(path, vault, fm, body, projects)


def command_validate(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    directory = tasks_dir(vault)
    if not directory.exists():
        raise TaskError(f"Missing task directory: {directory}")
    errors: list[str] = []
    projects = parse_simple_projects(vault / "00_Config" / "projects.yml")
    project_id = getattr(args, "project", None)
    if project_id:
        validate_project_id(project_id)
        scan_root = project_tasks_dir(vault, project_id)
        paths = sorted(scan_root.glob("**/*.md")) if scan_root.exists() else []
    else:
        paths = sorted(directory.glob("**/*.md"))
    for path in paths:
        errors.extend(validate_task(path, vault, projects))
    result = {
        "vault": str(vault),
        "project": project_id,
        "task_count": len(paths),
        "ok": not errors,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def template_text(name: str, fallback: str) -> str:
    path = TEMPLATE_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def render_template(name: str, fallback: str, values: dict[str, str]) -> str:
    text = template_text(name, fallback)
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def plan_write_file(path: Path, content: str, changes: list[dict[str, Any]], apply: bool, overwrite: bool = True) -> None:
    exists = path.exists()
    before = path.read_text(encoding="utf-8") if exists else ""
    if exists and not overwrite:
        action = "exists"
        changed = False
    else:
        action = "update" if exists else "create"
        changed = before != content
    changes.append(
        {
            "path": str(path),
            "action": action,
            "changed": changed,
            "summary": diff_summary(before, content) if action != "exists" else None,
        }
    )
    if apply and changed and action != "exists":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def plan_directory(path: Path, changes: list[dict[str, Any]], apply: bool) -> None:
    exists = path.exists()
    changes.append({"path": str(path), "action": "mkdir", "changed": not exists})
    if apply:
        path.mkdir(parents=True, exist_ok=True)


def detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def rendered_project_identity_block(project_id: str, project_name: str | None, newline: str) -> str:
    fields: dict[str, Any] = {
        "项目ID": project_id,
        "项目": [project_id],
    }
    if project_name:
        fields["项目名称"] = project_name
    lines: list[str] = []
    for key in ["项目ID", "项目", "项目名称"]:
        if key in fields:
            append_yaml_field(lines, key, fields[key])
    return newline.join(lines) + newline


def frontmatter_key_block_spans(lines: list[str], keys: set[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        matched = any(re.match(rf"^{re.escape(key)}\s*:", line) for key in keys)
        if not matched:
            index += 1
            continue
        end = index + 1
        while end < len(lines):
            next_line = lines[end].rstrip("\r\n")
            if next_line.startswith((" ", "\t")):
                end += 1
                continue
            break
        spans.append((index, end))
        index = end
    return spans


def frontmatter_insert_index(lines: list[str], spans: list[tuple[int, int]]) -> int:
    if spans:
        return min(start for start, _end in spans)
    for anchor in ["来源类型", "来源相对路径", "来源", "创建日期", "更新日期"]:
        for index, line in enumerate(lines):
            if re.match(rf"^{re.escape(anchor)}\s*:", line.rstrip("\r\n")):
                return index
    return len(lines)


def splice_project_identity_frontmatter(original_text: str, project_id: str, project_name: str | None) -> str:
    keys = {"项目ID", "项目"}
    if project_name:
        keys.add("项目名称")
    newline = detect_newline(original_text)

    if original_text.startswith("---\r\n"):
        marker = "---\r\n"
        newline = "\r\n"
    elif original_text.startswith("---\n"):
        marker = "---\n"
        newline = "\n"
    else:
        identity_block = rendered_project_identity_block(project_id, project_name, newline)
        return "---" + newline + identity_block + "---" + newline + newline + original_text

    closing_marker = newline + "---"
    end = original_text.find(closing_marker, len(marker))
    if end == -1:
        identity_block = rendered_project_identity_block(project_id, project_name, newline)
        return "---" + newline + identity_block + "---" + newline + newline + original_text

    identity_block = rendered_project_identity_block(project_id, project_name, newline)

    raw_frontmatter = original_text[len(marker) : end]
    tail = original_text[end:]
    lines = raw_frontmatter.splitlines(keepends=True)
    spans = frontmatter_key_block_spans(lines, keys)
    insert_index = frontmatter_insert_index(lines, spans)
    skip_indexes = {line_index for start, stop in spans for line_index in range(start, stop)}

    new_lines: list[str] = []
    inserted = False
    for index, line in enumerate(lines):
        if index == insert_index and not inserted:
            new_lines.append(identity_block)
            inserted = True
        if index in skip_indexes:
            continue
        new_lines.append(line)
    if not inserted:
        new_lines.append(identity_block)

    return marker + "".join(new_lines) + tail


def refresh_task_project_metadata(
    path: Path,
    vault: Path,
    project_id: str,
    project_name: str | None,
    apply: bool,
) -> dict[str, Any]:
    original_text = path.read_text(encoding="utf-8")
    fm, _body = split_frontmatter(original_text)
    next_text = splice_project_identity_frontmatter(original_text, project_id, project_name)
    new_fm, _new_body = split_frontmatter(next_text)
    tracked_keys = ["项目ID", "项目", "项目名称"]
    frontmatter_changes = {
        key: {"before": fm.get(key), "after": new_fm.get(key)}
        for key in tracked_keys
        if fm.get(key) != new_fm.get(key)
    }
    result = {
        "path": str(path),
        "project": project_id,
        "summary": diff_summary(original_text, next_text),
        "frontmatterChanges": frontmatter_changes,
        "bodyChanged": split_frontmatter(original_text)[1] != split_frontmatter(next_text)[1],
    }
    if apply and original_text != next_text:
        path.write_text(next_text, encoding="utf-8", newline="\n")
    return result


def selected_project_ids(projects: dict[str, dict[str, str]], project_id: str | None) -> list[str]:
    if project_id:
        validate_project_id(project_id)
        if project_id not in projects:
            raise TaskError(f"Missing project in 00_Config/projects.yml: {project_id}")
        return [project_id]
    return sorted(projects)


def command_refresh_project_metadata(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    projects = parse_simple_projects(vault / "00_Config" / "projects.yml")
    project_ids = selected_project_ids(projects, args.project)
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    for project_id in project_ids:
        project = projects.get(project_id)
        project_name = project.get("name") if project else None
        if not project_name:
            warnings.append(f"{project_id}: no configured project name; 项目名称 was not updated")
        scan_root = project_tasks_dir(vault, project_id)
        paths = sorted(scan_root.glob("**/*.md")) if scan_root.exists() else []
        for path in paths:
            results.append(refresh_task_project_metadata(path, vault, project_id, project_name, args.apply))
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "project": args.project,
        "projects": project_ids,
        "task_count": len(results),
        "warnings": warnings,
        "results": results,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def render_gitignore() -> str:
    return template_text(
        "taskmanager.gitignore",
        "\n".join(
            [
                "# Local Obsidian state",
                ".obsidian/workspace-mobile.json",
                ".obsidian/cache/",
                ".obsidian/logs/",
                ".trash/",
                ".obsidian/plugins/*/data.json",
                ".obsidian/workspace.json",
                ".obsidian/hotkeys.json",
                "",
                "# Machine-local project roots",
                "00_Config/projects.local.yml",
                "",
            ]
        ),
    )


def gitignore_required_entries() -> list[str]:
    return [
        line.strip()
        for line in render_gitignore().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def merge_gitignore(existing: str) -> str:
    current = set(existing.splitlines())
    missing = [entry for entry in gitignore_required_entries() if entry not in current]
    if not existing.strip():
        return render_gitignore()
    if not missing:
        return existing if existing.endswith("\n") else existing + "\n"
    return existing.rstrip() + "\n\n# TaskManager generated ignores\n" + "\n".join(missing) + "\n"


def render_readme() -> str:
    return template_text(
        "vault-readme.md",
        "# TaskManager\n\n"
        "This vault stores cross-project task notes, source references, Bases, and dashboards.\n\n"
        "Tracked project metadata lives in `00_Config/projects.yml`. Machine-local repository roots live in "
        "`00_Config/projects.local.yml`, which is intentionally ignored.\n",
    )


def render_compat_dashboard() -> str:
    return template_text(
        "task-dashboard.md",
        "# Task Dashboard\n\n"
        "This compatibility entry points to the global dashboard.\n\n"
        "![[40_Dashboards/Global Dashboard.md]]\n",
    )


def render_global_dashboard() -> str:
    return template_text(
        "global-dashboard.md",
        "# Global Dashboard\n\n"
        "![[30_Bases/global-tasks.base]]\n",
    )


def convert_task_folder_filter(content: str, task_folder: str) -> str:
    converted = content.replace('file.folder == "10_Tasks"', f'file.inFolder("{task_folder}")')
    converted = converted.replace("file.folder == '10_Tasks'", f'file.inFolder("{task_folder}")')
    return converted


def global_base_content(vault: Path) -> tuple[str, dict[str, Any]]:
    legacy_path = vault / "30_Bases" / "任务面板.base"
    global_path = vault / "30_Bases" / "global-tasks.base"
    status = {
        "path": str(legacy_path),
        "exists": legacy_path.exists(),
        "used_as_source": False,
    }
    if global_path.exists():
        return convert_task_folder_filter(global_path.read_text(encoding="utf-8"), "10_Tasks"), status
    if legacy_path.exists():
        status["used_as_source"] = True
        return convert_task_folder_filter(legacy_path.read_text(encoding="utf-8"), "10_Tasks"), status
    return render_base(), status


def render_base(project_id: str | None = None) -> str:
    folder = f"10_Tasks/{project_id}" if project_id else "10_Tasks"
    project_values = (
        {
            "projectPropertyBlock": "  note.项目名称:\n    displayName: 项目\n",
            "projectOrderBlock": "      - 项目\n",
            "projectPillBlock": "      - 项目\n",
        }
        if project_id is None
        else {
            "projectPropertyBlock": "",
            "projectOrderBlock": "",
            "projectPillBlock": "",
        }
    )
    values = {"taskFolder": folder, **project_values}
    return render_template(
        "project-base.base",
        """filters:
  and:
    - file.ext == "md"
    - file.inFolder("{{taskFolder}}")
properties:
  file.name:
    displayName: 任务文件
  note.任务名:
    displayName: 任务名
{{projectPropertyBlock}}  note.状态:
    displayName: 状态
  note.优先级:
    displayName: 优先级
  note.任务类型:
    displayName: 任务类型
  note.验证链路:
    displayName: 验证链路
  note.工作区:
    displayName: 工作区
  note.来源类型:
    displayName: 来源类型
  note.来源:
    displayName: 来源
  note.更新日期:
    displayName: 更新日期
views:
  - type: notion-table
    name: 进行中
    filters:
      and:
        - '!note["状态"].contains("已完成")'
    order:
      - 状态
{{projectOrderBlock}}      - 优先级
      - 任务类型
      - 验证链路
      - 工作区
      - 来源类型
      - 更新日期
    sort:
      - property: 优先级
        direction: ASC
      - property: 更新日期
        direction: DESC
    pillProperties:
      - 状态
{{projectPillBlock}}      - 优先级
      - 任务类型
      - 验证链路
      - 工作区
      - 来源类型
  - type: notion-table
    name: 已完成
    filters:
      and:
        - note["状态"].contains("已完成")
    order:
      - 状态
{{projectOrderBlock}}      - 验证链路
      - 工作区
      - 来源类型
      - 更新日期
    pillProperties:
      - 状态
{{projectPillBlock}}      - 验证链路
      - 工作区
      - 来源类型
""",
        values,
    )


def render_project_dashboard(project_id: str, name: str) -> str:
    return render_template(
        "project-dashboard.md",
        "# {{projectName}} Dashboard\n\n"
        "## 进行中\n\n"
        "![[30_Bases/{{projectId}}.base#进行中]]\n\n"
        "## 已完成\n\n"
        "![[30_Bases/{{projectId}}.base#已完成]]\n",
        {"projectId": project_id, "projectName": name},
    )


def merge_types_json(existing_text: str) -> str:
    if existing_text.strip():
        try:
            data = json.loads(existing_text)
        except json.JSONDecodeError as exc:
            raise TaskError(f"Invalid .obsidian/types.json: {exc}") from exc
    else:
        data = {"types": {}}
    if not isinstance(data, dict):
        raise TaskError(".obsidian/types.json must contain a JSON object")
    types = data.setdefault("types", {})
    if not isinstance(types, dict):
        raise TaskError(".obsidian/types.json types field must be an object")
    types.update(TYPES_ADDITIONS)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def command_init_vault_repo(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    changes: list[dict[str, Any]] = []
    for rel in [
        "00_Config",
        "10_Tasks",
        "20_Sources/_design",
        "30_Bases",
        "40_Dashboards",
        "40_Reports",
        "90_Archive",
        "Templates",
        ".obsidian",
    ]:
        plan_directory(vault / rel, changes, args.apply)
    gitignore_path = vault / ".gitignore"
    existing_gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    plan_write_file(gitignore_path, merge_gitignore(existing_gitignore), changes, args.apply)
    plan_write_file(vault / "README.md", render_readme(), changes, args.apply)
    plan_write_file(vault / "Task Dashboard.md", render_compat_dashboard(), changes, args.apply)
    global_base, legacy_base_status = global_base_content(vault)
    changes.append({"action": "legacy-base-status", "changed": False, **legacy_base_status})
    plan_write_file(vault / "30_Bases" / "global-tasks.base", global_base, changes, args.apply)
    plan_write_file(vault / "40_Dashboards" / "Global Dashboard.md", render_global_dashboard(), changes, args.apply, overwrite=False)
    plan_write_file(vault / "40_Reports" / ".gitkeep", "", changes, args.apply, overwrite=False)
    existing_types = (vault / ".obsidian" / "types.json").read_text(encoding="utf-8") if (vault / ".obsidian" / "types.json").exists() else ""
    plan_write_file(vault / ".obsidian" / "types.json", merge_types_json(existing_types), changes, args.apply)

    git_init = {"needed": not is_git_repo(vault), "ran": False}
    if args.apply and git_init["needed"]:
        run_git(vault, ["init"])
        git_init["ran"] = True

    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "changes": changes,
        "git_init": git_init,
        "track": TRACK_HINTS,
        "ignore": IGNORE_HINTS,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def is_git_repo(path: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def run_git(path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise TaskError(f"git {' '.join(args)} failed: {detail}")
    return completed


def git_status(path: Path) -> list[str]:
    completed = run_git(path, ["status", "--porcelain"])
    return [line for line in completed.stdout.splitlines() if line.strip()]


def command_baseline_commit(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    if not is_git_repo(vault):
        raise TaskError(f"Vault is not a git repository: {vault}")
    status = git_status(vault)
    if not status:
        raise TaskError("No changes to commit")
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "message": args.message,
        "status": status,
        "commands": [
            "git add -A",
            f"git commit -m {args.message!r}",
        ],
    }
    if args.apply:
        run_git(vault, ["add", "-A"])
        commit = run_git(vault, ["commit", "-m", args.message])
        result["commit_output"] = commit.stdout.strip()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_write_design(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise TaskError("input title is required")
    summary = payload.get("summary", "")
    decisions = payload.get("decisions", [])
    if isinstance(decisions, str):
        decisions_list = [decisions]
    elif isinstance(decisions, list):
        decisions_list = [str(item) for item in decisions]
    else:
        raise TaskError("decisions must be a string or list")
    filename = payload.get("filename") or slug_to_filename(title)
    if not isinstance(filename, str):
        raise TaskError("filename must be a string")
    if not filename.lower().endswith(".md"):
        filename += ".md"
    validate_relative_path(filename, "filename")
    if "/" in filename.replace("\\", "/"):
        raise TaskError("filename must not contain directories")
    target = vault / "20_Sources" / "_design" / filename
    content = render_design_note(title, str(summary), decisions_list)
    changes: list[dict[str, Any]] = []
    plan_write_file(target, content, changes, args.apply)
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "target": str(target),
        "changes": changes,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def render_design_note(title: str, summary: str, decisions: list[str]) -> str:
    lines = [
        f"# {title.strip()}",
        "",
        "## Summary",
        "",
        summary.strip(),
        "",
        "## Decisions",
        "",
    ]
    if decisions:
        lines.extend(f"- {item}" for item in decisions)
    else:
        lines.append("- None recorded.")
    lines.append("")
    return "\n".join(lines)


def parse_simple_projects(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    data: dict[str, dict[str, str]] = {}
    current: str | None = None
    in_projects = False
    seen_projects = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "projects:" and not line.startswith(" "):
            if seen_projects:
                raise TaskError(f"Unsupported project config {path}: duplicate projects key at line {line_number}")
            seen_projects = True
            in_projects = True
            current = None
            continue
        if not in_projects:
            raise TaskError(f"Unsupported project config {path}: unexpected line before projects at line {line_number}")
        match_project = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
        if match_project:
            current = match_project.group(1)
            validate_project_id(current)
            data.setdefault(current, {})
            continue
        match_field = re.match(r"^    ([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match_field and current:
            value = match_field.group(2).strip()
            if value == "":
                raise TaskError(f"Unsupported project config {path}: nested or empty value at line {line_number}")
            data[current][match_field.group(1)] = unquote_scalar(value)
            continue
        raise TaskError(f"Unsupported project config {path}: cannot parse line {line_number}")
    if path.exists() and not seen_projects and path.read_text(encoding="utf-8").strip():
        raise TaskError(f"Unsupported project config {path}: missing projects key")
    return data


def render_simple_projects(projects: dict[str, dict[str, str]]) -> str:
    lines = ["projects:"]
    for project_id in sorted(projects):
        lines.append(f"  {project_id}:")
        for key in sorted(projects[project_id]):
            lines.append(f"    {key}: {yaml_scalar(projects[project_id][key])}")
    return "\n".join(lines) + "\n"


def command_init_project(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    project_id = args.project
    validate_project_id(project_id)
    repo = Path(args.repo).resolve()
    source_root = args.source_root.replace("\\", "/").strip("/")
    validate_relative_path(source_root, "source-root")
    task_path = safe_child(vault / "10_Tasks", project_id)
    source_path = safe_child(vault / "20_Sources", project_id)
    base_path = safe_child(vault / "30_Bases", f"{project_id}.base")
    dashboard_path = safe_child(vault / "40_Dashboards", f"{project_id} Dashboard.md")

    projects_path = vault / "00_Config" / "projects.yml"
    local_path = vault / "00_Config" / "projects.local.yml"
    projects = parse_simple_projects(projects_path)
    projects[project_id] = {
        "basePath": base_path.relative_to(vault).as_posix(),
        "dashboardPath": dashboard_path.relative_to(vault).as_posix(),
        "name": args.name,
        "sourcePath": source_path.relative_to(vault).as_posix(),
        "sourceRoot": source_root,
        "taskPath": task_path.relative_to(vault).as_posix(),
    }
    local_projects = parse_simple_projects(local_path)
    local_projects[project_id] = {"root": str(repo).replace("\\", "/")}

    changes: list[dict[str, Any]] = []
    for path in [
        task_path,
        safe_child(source_path, "discussions"),
        safe_child(source_path, "specs"),
        safe_child(source_path, "references"),
        safe_child(source_path, "handoffs"),
        vault / "30_Bases",
        vault / "40_Dashboards",
        vault / "00_Config",
    ]:
        plan_directory(path, changes, args.apply)
    gitignore_path = vault / ".gitignore"
    existing_gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    plan_write_file(gitignore_path, merge_gitignore(existing_gitignore), changes, args.apply)
    plan_write_file(projects_path, render_simple_projects(projects), changes, args.apply)
    plan_write_file(local_path, render_simple_projects(local_projects), changes, args.apply)
    plan_write_file(base_path, render_base(project_id), changes, args.apply)
    plan_write_file(
        dashboard_path,
        render_project_dashboard(project_id, args.name),
        changes,
        args.apply,
    )

    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "project": project_id,
        "repo": str(repo),
        "changes": changes,
        "tracked_config": str(projects_path),
        "local_config": str(local_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_refresh_bases(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    projects = parse_simple_projects(vault / "00_Config" / "projects.yml")
    project_ids = selected_project_ids(projects, args.project)
    changes: list[dict[str, Any]] = []
    plan_directory(vault / "30_Bases", changes, args.apply)
    plan_write_file(vault / "30_Bases" / "global-tasks.base", render_base(), changes, args.apply)
    for project_id in project_ids:
        plan_write_file(vault / "30_Bases" / f"{project_id}.base", render_base(project_id), changes, args.apply)
    plan_directory(vault / ".obsidian", changes, args.apply)
    types_path = vault / ".obsidian" / "types.json"
    existing_types = types_path.read_text(encoding="utf-8") if types_path.exists() else ""
    plan_write_file(types_path, merge_types_json(existing_types), changes, args.apply)
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "project": args.project,
        "projects": project_ids,
        "changes": changes,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_refresh_dashboards(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    projects = parse_simple_projects(vault / "00_Config" / "projects.yml")
    project_ids = selected_project_ids(projects, args.project)
    changes: list[dict[str, Any]] = []
    plan_directory(vault / "40_Dashboards", changes, args.apply)
    plan_write_file(vault / "40_Dashboards" / "Global Dashboard.md", render_global_dashboard(), changes, args.apply)
    for project_id in project_ids:
        project_name = projects[project_id].get("name") or project_id
        plan_write_file(
            vault / "40_Dashboards" / f"{project_id} Dashboard.md",
            render_project_dashboard(project_id, project_name),
            changes,
            args.apply,
        )
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "project": args.project,
        "projects": project_ids,
        "changes": changes,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def clean_legacy_source(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] == "`":
        text = text[1:-1].strip()
    return text


def legacy_source_path(value: str) -> Path:
    return Path(value.replace("/", "\\"))


def classify_legacy_source(
    source: Any,
    vault: Path,
    repo_root: Path,
    moved_source_notes: dict[str, str],
) -> tuple[str, str]:
    text = clean_legacy_source(source)
    if not text:
        raise TaskError("legacy 来源 is empty")

    source_path = legacy_source_path(text)
    if source_path.is_absolute():
        resolved = source_path.resolve()
        if is_within(resolved, repo_root):
            return "impl-plan", resolved.relative_to(repo_root).as_posix()

        legacy_source_root = (vault / "20_Sources").resolve()
        if is_within(resolved, legacy_source_root) and resolved.parent == legacy_source_root:
            target_rel = moved_source_notes.get(resolved.name)
            if target_rel:
                return "source-note", target_rel
        raise TaskError(f"legacy 来源 cannot be classified: {text}")

    normalized = text.replace("\\", "/").lstrip("./")
    for filename, target_rel in moved_source_notes.items():
        if normalized in {filename, f"20_Sources/{filename}"}:
            return "source-note", target_rel
    raise TaskError(f"legacy 来源 cannot be classified: {text}")


def build_migrated_task_content(
    source_path: Path,
    target_path: Path,
    vault: Path,
    project_id: str,
    project_name: str | None,
    source_type: str,
    source_relative_path: str,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    original_text = source_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(original_text)
    new_fm = copy.deepcopy(fm)
    new_fm["项目ID"] = project_id
    new_fm["项目"] = [project_id]
    if project_name:
        new_fm["项目名称"] = project_name
    new_fm["来源类型"] = [source_type]
    new_fm["来源相对路径"] = source_relative_path
    new_fm["更新日期"] = today()
    new_body = ensure_sections(body)
    migrated_text = render_task(new_fm, new_body)
    errors = validate_task_content(target_path, vault, new_fm, new_body)
    if errors:
        raise TaskError("migrated task would fail validate: " + "; ".join(errors))

    tracked_keys = ["项目ID", "项目", "项目名称", "来源类型", "来源相对路径", "来源", "更新日期"]
    frontmatter_changes = {
        key: {"before": fm.get(key), "after": new_fm.get(key)}
        for key in tracked_keys
        if fm.get(key) != new_fm.get(key)
    }
    return migrated_text, fm, new_fm, frontmatter_changes


def command_migrate_legacy_project(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    project_id = args.project
    validate_project_id(project_id)
    project_name = project_name_for_task(vault, project_id)
    repo_root = Path(args.repo).resolve()
    if not vault.exists() or not vault.is_dir():
        raise TaskError(f"Vault does not exist or is not a directory: {vault}")
    if not repo_root.exists() or not repo_root.is_dir():
        raise TaskError(f"Repo root does not exist or is not a directory: {repo_root}")

    legacy_tasks_dir = vault / "10_Tasks"
    legacy_sources_dir = vault / "20_Sources"
    if not legacy_tasks_dir.exists():
        raise TaskError(f"Missing legacy task directory: {legacy_tasks_dir}")
    if not legacy_sources_dir.exists():
        raise TaskError(f"Missing legacy source directory: {legacy_sources_dir}")

    target_tasks_dir = project_tasks_dir(vault, project_id)
    target_discussions_dir = safe_child(vault / "20_Sources", project_id, "discussions")
    task_files = sorted(path for path in legacy_tasks_dir.glob("*.md") if path.is_file())
    source_files = sorted(path for path in legacy_sources_dir.glob("*.md") if path.is_file())

    moved_source_notes = {
        path.name: (target_discussions_dir / path.name).relative_to(vault).as_posix()
        for path in source_files
    }
    changes: list[dict[str, Any]] = []
    for path in [target_tasks_dir, target_discussions_dir]:
        plan_directory(path, changes, False)

    collisions: list[str] = []
    for path in task_files:
        target = target_tasks_dir / path.name
        if target.exists():
            collisions.append(f"target task already exists: {target}")
    for path in source_files:
        target = target_discussions_dir / path.name
        if target.exists():
            collisions.append(f"target source note already exists: {target}")
    if collisions:
        raise TaskError("; ".join(collisions))

    source_moves = [
        {
            "source": str(path),
            "target": str(target_discussions_dir / path.name),
            "relativeTarget": (target_discussions_dir / path.name).relative_to(vault).as_posix(),
        }
        for path in source_files
    ]

    task_moves: list[dict[str, Any]] = []
    migrated_tasks: list[tuple[Path, Path, str]] = []
    for path in task_files:
        target = target_tasks_dir / path.name
        fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        try:
            source_type, source_relative_path = classify_legacy_source(
                fm.get("来源"),
                vault,
                repo_root,
                moved_source_notes,
            )
        except TaskError as exc:
            raise TaskError(f"{path}: {exc}") from exc
        migrated_text, _old_fm, new_fm, frontmatter_changes = build_migrated_task_content(
            path,
            target,
            vault,
            project_id,
            project_name,
            source_type,
            source_relative_path,
        )
        migrated_tasks.append((path, target, migrated_text))
        task_moves.append(
            {
                "source": str(path),
                "target": str(target),
                "sourceType": source_type,
                "sourceRelativePath": source_relative_path,
                "frontmatterChanges": frontmatter_changes,
                "summary": diff_summary(path.read_text(encoding="utf-8"), migrated_text),
            }
        )

    if args.apply:
        for path in [target_tasks_dir, target_discussions_dir]:
            path.mkdir(parents=True, exist_ok=True)
        for source_path in source_files:
            source_path.replace(target_discussions_dir / source_path.name)
        for source_path, target_path, migrated_text in migrated_tasks:
            target_path.write_text(migrated_text, encoding="utf-8", newline="\n")
            source_path.unlink()

    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "project": project_id,
        "repo": str(repo_root),
        "directories": changes,
        "sourceMoves": source_moves,
        "taskMoves": task_moves,
        "validateCommand": [
            sys.executable,
            str(Path(__file__).resolve()),
            "validate",
            "--vault",
            str(vault),
            "--project",
            project_id,
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_import_impl_plans(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    project_id = args.project
    validate_project_id(project_id)
    if args.limit < 1:
        raise TaskError("--limit must be at least 1")
    normalize_list(args.default_status, "状态")
    projects = parse_simple_projects(vault / "00_Config" / "projects.yml")
    local_projects = parse_simple_projects(vault / "00_Config" / "projects.local.yml")
    if project_id not in projects:
        raise TaskError(f"Missing project in 00_Config/projects.yml: {project_id}")
    if project_id not in local_projects or not local_projects[project_id].get("root"):
        raise TaskError(f"Missing project root in ignored 00_Config/projects.local.yml: {project_id}")
    source_root = projects[project_id].get("sourceRoot")
    if not source_root:
        raise TaskError(f"Project {project_id} is missing sourceRoot")
    source_root = source_root.replace("\\", "/").strip("/")
    validate_relative_path(source_root, "sourceRoot")
    repo_root = Path(local_projects[project_id]["root"]).resolve()
    source_dir = (repo_root / source_root).resolve()
    if not is_within(source_dir, repo_root):
        raise TaskError(f"Resolved source root escapes project repo: {source_dir}")
    if not source_dir.exists():
        raise TaskError(f"Missing source root: {source_dir}")

    candidates = [
        path
        for path in source_dir.glob("*.md")
        if path.name.lower() != "readme.md" and path.parent == source_dir
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    selected = candidates[: args.limit]
    results: list[dict[str, Any]] = []
    for path in selected:
        rel = path.relative_to(repo_root).as_posix()
        task_name = markdown_title(path)
        payload = {
            "operation": "create",
            "taskName": task_name,
            "slug": task_name,
            "slugAliases": [path.stem],
            "status": args.default_status,
            "verificationPath": "不涉及",
            "workspace": "主工作区",
            "source": rel,
            "projectId": project_id,
            "sourceType": "impl-plan",
            "sourceRelativePath": rel,
            "progress": f"Imported from implementation plan `{rel}`.",
            "nextStep": "Review the implementation plan and decide the next execution step.",
            "verificationStatus": "",
            "residualRisk": "",
        }
        validate_payload(payload)
        target = find_task(vault, payload["taskName"], project_id, payload_slug_candidates(payload))
        if target.exists() and not args.overwrite_existing:
            results.append(
                {
                    "mode": "apply" if args.apply else "dry-run",
                    "target": str(target),
                    "exists": True,
                    "skipped_existing": True,
                    "source": str(path),
                }
            )
            continue
        results.append(build_task_write(vault, target, payload, args.apply))

    result = {
        "mode": "apply" if args.apply else "dry-run",
        "vault": str(vault),
        "project": project_id,
        "source_dir": str(source_dir),
        "selected": [str(path) for path in selected],
        "results": results,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage TaskManager vault files")
    sub = parser.add_subparsers(dest="command", required=True)

    init_vault = sub.add_parser("init-vault-repo", help="Create dashboard-required vault files and optional git repo")
    init_vault.add_argument("--vault", required=True)
    init_vault.add_argument("--apply", action="store_true")
    init_vault.set_defaults(func=command_init_vault_repo)

    baseline = sub.add_parser("baseline-commit", help="Stage and commit the current vault baseline")
    baseline.add_argument("--vault", required=True)
    baseline.add_argument("--message", default="chore: baseline taskmanager vault")
    baseline.add_argument("--apply", action="store_true")
    baseline.set_defaults(func=command_baseline_commit)

    write_design = sub.add_parser("write-design", help="Write a design reference note under 20_Sources/_design")
    write_design.add_argument("--vault", required=True)
    write_design.add_argument("--input", required=True)
    write_design.add_argument("--apply", action="store_true")
    write_design.set_defaults(func=command_write_design)

    init_project = sub.add_parser("init-project", help="Create project metadata, local root, directories, Base, and dashboard")
    init_project.add_argument("--vault", required=True)
    init_project.add_argument("--project", required=True)
    init_project.add_argument("--repo", required=True)
    init_project.add_argument("--name", required=True)
    init_project.add_argument("--source-root", default="docs/impl-plans")
    init_project.add_argument("--apply", action="store_true")
    init_project.set_defaults(func=command_init_project)

    refresh_metadata = sub.add_parser(
        "refresh-project-metadata",
        help="Refresh generated project task frontmatter such as 项目名称 without changing task bodies",
    )
    refresh_metadata.add_argument("--vault", required=True)
    refresh_metadata.add_argument("--project")
    refresh_metadata.add_argument("--apply", action="store_true")
    refresh_metadata.set_defaults(func=command_refresh_project_metadata)

    refresh_bases = sub.add_parser("refresh-bases", help="Regenerate project and global Base files from templates")
    refresh_bases.add_argument("--vault", required=True)
    refresh_bases.add_argument("--project")
    refresh_bases.add_argument("--apply", action="store_true")
    refresh_bases.set_defaults(func=command_refresh_bases)

    refresh_dashboards = sub.add_parser("refresh-dashboards", help="Regenerate project and global dashboard Markdown from templates")
    refresh_dashboards.add_argument("--vault", required=True)
    refresh_dashboards.add_argument("--project")
    refresh_dashboards.add_argument("--apply", action="store_true")
    refresh_dashboards.set_defaults(func=command_refresh_dashboards)

    migrate_legacy = sub.add_parser("migrate-legacy-project", help="Move legacy single-project vault files into one project namespace")
    migrate_legacy.add_argument("--vault", required=True)
    migrate_legacy.add_argument("--project", required=True)
    migrate_legacy.add_argument("--repo", required=True)
    migrate_legacy.add_argument("--apply", action="store_true")
    migrate_legacy.set_defaults(func=command_migrate_legacy_project)

    import_impl = sub.add_parser("import-impl-plans", help="Import recent direct implementation plans as project tasks")
    import_impl.add_argument("--vault", required=True)
    import_impl.add_argument("--project", required=True)
    import_impl.add_argument("--limit", type=int, default=5)
    import_impl.add_argument("--default-status", default="计划中")
    import_impl.add_argument("--overwrite-existing", action="store_true")
    import_impl.add_argument("--apply", action="store_true")
    import_impl.set_defaults(func=command_import_impl_plans)

    validate = sub.add_parser("validate", help="Validate task files")
    validate.add_argument("--vault", required=True)
    validate.add_argument("--project")
    validate.set_defaults(func=command_validate)

    upsert = sub.add_parser("upsert", help="Create/update a task from JSON")
    upsert.add_argument("--vault", required=True)
    upsert.add_argument("--input", required=True)
    upsert.add_argument("--project")
    upsert.add_argument("--apply", action="store_true")
    upsert.set_defaults(func=command_upsert)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TaskError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
