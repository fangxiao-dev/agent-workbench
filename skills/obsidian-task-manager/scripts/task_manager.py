#!/usr/bin/env python3
"""Dry-run, validate, and optionally apply Obsidian TaskManager updates."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


STATUSES = {"计划中", "实施中", "验证中", "阻塞", "搁置", "已完成"}
PRIORITIES = {"当前", "下一批", "未来规划"}
TASK_TYPES = {"新增功能", "bug", "功能优化"}
VERIFICATION_PATHS = {"本地链路", "真实链路", "部分真实链路", "不涉及"}
WORKSPACES = {"主工作区", "worktree"}

LIST_FIELDS = {
    "状态": STATUSES,
    "优先级": PRIORITIES,
    "任务类型": TASK_TYPES,
    "验证链路": VERIFICATION_PATHS,
    "工作区": WORKSPACES,
}

FIELD_MAP = {
    "status": "状态",
    "priority": "优先级",
    "taskType": "任务类型",
    "verificationPath": "验证链路",
    "workspace": "工作区",
    "source": "来源",
}

SECTION_MAP = {
    "source": "来源链接/路径",
    "progress": "当前进度",
    "nextStep": "下一步建议",
    "verificationStatus": "验证状态",
    "residualRisk": "残余风险",
}

REQUIRED_SECTIONS = ["来源链接/路径", "当前进度", "下一步建议", "验证状态", "残余风险"]


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


def tasks_dir(vault: Path) -> Path:
    return vault / "10_Tasks"


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
        return value[1:-1]
    return value


def yaml_scalar(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text == "":
        return '""'
    if any(ch in text for ch in [":", "#", "\n", '"']) or text.strip() != text:
        return json.dumps(text, ensure_ascii=False)
    return text


def render_frontmatter(data: dict[str, Any]) -> str:
    order = ["任务名", "状态", "优先级", "任务类型", "验证链路", "工作区", "来源", "创建日期", "更新日期"]
    lines = ["---"]
    for key in order:
        if key not in data:
            continue
        value = data[key]
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    for key, value in data.items():
        if key in order or value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


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
        elif value is not None and not isinstance(value, str):
            raise TaskError(f"{json_key} must be a string or null")


def find_task(vault: Path, task_name: str) -> Path:
    direct = tasks_dir(vault) / slug_to_filename(task_name)
    if direct.exists():
        return direct
    matches: list[Path] = []
    for path in tasks_dir(vault).glob("*.md"):
        try:
            fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
        if fm.get("任务名") == task_name or path.stem.lower() == task_name.lower():
            matches.append(path)
    if len(matches) > 1:
        names = ", ".join(str(p) for p in matches)
        raise TaskError(f"Multiple matching task files found: {names}")
    if matches:
        return matches[0]
    return direct


def section_block(title: str, content: str) -> str:
    body = content.strip()
    return f"### {title}\n\n{body}\n\n"


def default_body(task_name: str) -> str:
    blocks = [f"# {task_name}\n"]
    for title in REQUIRED_SECTIONS:
        blocks.append(section_block(title, ""))
    return "\n".join(blocks).rstrip() + "\n"


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


def apply_payload(existing_fm: dict[str, Any], existing_body: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    fm = copy.deepcopy(existing_fm)
    body = existing_body or default_body(payload["taskName"])

    if "任务名" not in fm:
        fm["任务名"] = payload["taskName"]
    if "创建日期" not in fm:
        fm["创建日期"] = today()
    fm["更新日期"] = today()

    defaults = {}
    if payload["operation"] == "create":
        defaults = {
            "status": "计划中",
            "verificationPath": "不涉及",
            "workspace": "主工作区",
        }

    merged = {**defaults, **payload}
    for json_key, yaml_key in FIELD_MAP.items():
        if json_key not in merged:
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


def command_upsert(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    validate_payload(payload)
    target = find_task(vault, payload["taskName"])
    if not str(target.resolve()).startswith(str(tasks_dir(vault).resolve())):
        raise TaskError(f"Refusing to write outside 10_Tasks: {target}")

    existing_text = target.read_text(encoding="utf-8") if target.exists() else ""
    fm, body = load_task(target)
    new_fm, new_body = apply_payload(fm, body, payload)
    next_text = render_task(new_fm, new_body)
    result = {
        "mode": "apply" if args.apply else "dry-run",
        "target": str(target),
        "exists": target.exists(),
        "summary": diff_summary(existing_text, next_text),
        "frontmatter": new_fm,
        "markdown": next_text,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(next_text, encoding="utf-8", newline="\n")
    return 0


def validate_task(path: Path) -> list[str]:
    errors: list[str] = []
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
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
    return errors


def command_validate(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    directory = tasks_dir(vault)
    if not directory.exists():
        raise TaskError(f"Missing task directory: {directory}")
    errors: list[str] = []
    for path in sorted(directory.glob("*.md")):
        errors.extend(validate_task(path))
    result = {
        "vault": str(vault),
        "task_count": len(list(directory.glob("*.md"))),
        "ok": not errors,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Obsidian TaskManager tasks")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate task files")
    validate.add_argument("--vault", required=True)
    validate.set_defaults(func=command_validate)

    upsert = sub.add_parser("upsert", help="Create/update a task from JSON")
    upsert.add_argument("--vault", required=True)
    upsert.add_argument("--input", required=True)
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
