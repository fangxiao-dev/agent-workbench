"""Track todo tasks and per-task workplan directories for the planning-with-files workflow."""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

TODO_PATH = Path("plans/todo_current.md")
WORKPLAN_DIR = Path("plans/workplans")

STATUS_VALUES = ("UNPLANNED", "PLANNED", "DONE")
SIMPLE_TABLE_COLUMNS = ("task_id", "task", "status", "updated_at", "note")
LEGACY_SIMPLE_TABLE_COLUMNS = ("task_id", "task", "status", "plan_id", "updated_at", "note")
RICH_TABLE_COLUMNS = ("task id", "slug", "title", "status", "dependencies", "parallel", "notes")
LEGACY_RICH_TABLE_COLUMNS = ("task id", "slug", "title", "status", "plan id", "dependencies", "parallel", "notes")


def set_root(root: Path) -> None:
    """Override TODO_PATH and WORKPLAN_DIR to resolve under the given project root."""
    global TODO_PATH, WORKPLAN_DIR
    TODO_PATH = root / "plans/todo_current.md"
    WORKPLAN_DIR = root / "plans/workplans"


@dataclass
class TodoTask:
    """Structured row representation for a task in plans/todo_current.md."""

    task_id: str
    task: str
    status: str
    updated_at: str
    note: str
    extras: dict[str, str] = field(default_factory=dict)

    def to_cells(self, table_kind: str) -> list[str]:
        """Return row cells in the canonical table schema."""
        if table_kind == "simple":
            return [
                self.task_id,
                self.task,
                self.status,
                self.updated_at,
                self.note,
            ]
        if table_kind == "rich":
            return [
                self.task_id,
                self.extras.get("slug", ""),
                self.task,
                self.status,
                self.extras.get("dependencies", ""),
                self.extras.get("parallel", ""),
                self.note,
            ]
        raise ValueError(f"Unsupported table kind '{table_kind}'.")


@dataclass
class ParsedTodo:
    """Parsed todo_current.md with schema metadata."""

    preamble: list[str]
    tasks: list[TodoTask]
    table_kind: str


def now_iso() -> str:
    """Return ISO-8601 timestamp with local timezone and second precision."""
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def split_row(line: str) -> list[str]:
    """Split a markdown table row into trimmed cells."""
    raw = line.strip()
    if not raw.startswith("|") or not raw.endswith("|"):
        return []
    return [part.strip() for part in raw.split("|")[1:-1]]


def is_separator_row(cells: list[str]) -> bool:
    """Identify markdown separator rows like | --- | --- |."""
    if not cells:
        return False
    compact = "".join(cells).replace("-", "").replace(":", "").strip()
    return compact == ""


def normalize_status(value: str) -> str:
    """Validate and normalize task status values."""
    status = value.strip().upper()
    if status not in STATUS_VALUES:
        raise ValueError(f"Unsupported status '{value}'. Expected one of {STATUS_VALUES}.")
    return status


def parse_todo_file(path: Path) -> ParsedTodo:
    """Parse markdown task table from todo_current.md."""
    if not path.exists():
        raise FileNotFoundError(f"Missing todo file: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    header_idx = None
    schema = None
    for idx, line in enumerate(lines):
        lowered = [cell.lower() for cell in split_row(line)]
        if lowered == list(SIMPLE_TABLE_COLUMNS):
            header_idx = idx
            schema = "simple"
            break
        if lowered == list(LEGACY_SIMPLE_TABLE_COLUMNS):
            header_idx = idx
            schema = "legacy_simple"
            break
        if lowered == list(RICH_TABLE_COLUMNS):
            header_idx = idx
            schema = "rich"
            break
        if lowered == list(LEGACY_RICH_TABLE_COLUMNS):
            header_idx = idx
            schema = "legacy_rich"
            break
    if header_idx is None or schema is None:
        raise ValueError("todo_current.md is not in a supported table format.")

    table_kind = "rich" if "rich" in schema else "simple"
    preamble = lines[:header_idx]
    tasks: list[TodoTask] = []
    for line in lines[header_idx + 1 :]:
        if not line.strip():
            continue
        cells = split_row(line)
        if not cells or is_separator_row(cells):
            continue
        if schema in ("simple", "legacy_simple"):
            columns = SIMPLE_TABLE_COLUMNS if schema == "simple" else LEGACY_SIMPLE_TABLE_COLUMNS
            if len(cells) < len(columns):
                cells += [""] * (len(columns) - len(cells))
            row = dict(zip(columns, cells[: len(columns)]))
            tasks.append(
                TodoTask(
                    task_id=row["task_id"],
                    task=row["task"],
                    status=normalize_status(row["status"]),
                    updated_at=row["updated_at"],
                    note=row["note"],
                )
            )
            continue

        columns = RICH_TABLE_COLUMNS if schema == "rich" else LEGACY_RICH_TABLE_COLUMNS
        if len(cells) < len(columns):
            cells += [""] * (len(columns) - len(cells))
        row = dict(zip(columns, cells[: len(columns)]))
        tasks.append(
            TodoTask(
                task_id=row["task id"],
                task=row["title"],
                status=normalize_status(row["status"]),
                updated_at="",
                note=row["notes"],
                extras={
                    "slug": row["slug"],
                    "dependencies": row["dependencies"],
                    "parallel": row["parallel"],
                },
            )
        )

    return ParsedTodo(preamble=preamble, tasks=tasks, table_kind=table_kind)


def render_table(tasks: list[TodoTask], table_kind: str) -> list[str]:
    """Render task rows into the canonical markdown table schema."""
    columns = SIMPLE_TABLE_COLUMNS if table_kind == "simple" else RICH_TABLE_COLUMNS
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, separator]
    for task in tasks:
        lines.append("| " + " | ".join(task.to_cells(table_kind)) + " |")
    return lines


def save_todo(path: Path, parsed: ParsedTodo) -> None:
    """Persist todo markdown with preamble + canonical table."""
    output = []
    output.extend(parsed.preamble)
    if output and output[-1].strip() != "":
        output.append("")
    output.extend(render_table(parsed.tasks, parsed.table_kind))
    output.append("")
    path.write_text("\n".join(output), encoding="utf-8")


def find_task(tasks: Iterable[TodoTask], task_id: str) -> TodoTask:
    """Find task by id or raise clear error."""
    for task in tasks:
        if task.task_id == task_id:
            return task
    raise ValueError(f"Task '{task_id}' was not found.")


def task_dir(task_id: str) -> Path:
    """Return the canonical workplan directory for a task."""
    return WORKPLAN_DIR / task_id


def task_file_paths(task_id: str) -> tuple[Path, Path, Path]:
    """Return canonical workplan file paths for a task."""
    base = task_dir(task_id)
    return base / "task_plan.md", base / "findings.md", base / "progress.md"


def create_plan_files(task: TodoTask, rationale: list[str]) -> None:
    """Create task_plan/findings/progress markdown files for one task."""
    workplan_path = task_dir(task.task_id)
    workplan_path.mkdir(parents=True, exist_ok=True)
    task_plan_path, findings_path, progress_path = task_file_paths(task.task_id)
    now = now_iso()

    task_plan_path.write_text(
        "\n".join(
            [
                f"# Task Plan: {task.task_id}",
                "",
                "## Goal",
                task.task,
                "",
                "## Scope",
                f"- {task.task_id}: {task.task}",
                "",
                "## Current Phase",
                "Phase 1",
                "",
                "## Phases",
                "### Phase 1: Requirements & Discovery",
                "- [x] Confirm selected task and constraints",
                "- [ ] Write findings and rationale",
                "- **Status:** in_progress",
                "",
                "### Phase 2: Planning & Structure",
                "- [ ] Define implementation sequence",
                "- [ ] Confirm dependencies and risks",
                "- **Status:** pending",
                "",
                "### Phase 3: Implementation",
                "- [ ] Execute the task",
                "- [ ] Keep progress and errors updated",
                "- **Status:** pending",
                "",
                "### Phase 4: Testing & Verification",
                "- [ ] Run relevant tests/checks",
                "- [ ] Record validation results",
                "- **Status:** pending",
                "",
                "### Phase 5: Delivery",
                "- [ ] Update task status in todo_current",
                "- [ ] Summarize output and residual risks",
                "- **Status:** pending",
                "",
            ]
        ),
        encoding="utf-8",
    )

    findings_lines = [
        f"# Findings & Decisions ({task.task_id})",
        "",
        "## Requirements",
        f"- {task.task_id}: {task.task}",
        "",
        "## Research Findings",
        "-",
        "",
        "## Technical Decisions",
        "| Decision | Rationale |",
        "|---|---|",
    ]
    for item in rationale:
        findings_lines.append(f"| Task selection | {item} |")
    findings_lines.extend(
        [
            "",
            "## Issues Encountered",
            "| Issue | Resolution |",
            "|---|---|",
            "| | |",
            "",
            "## Resources",
            "- plans/todo_current.md",
            f"- plans/workplans/{task.task_id}/task_plan.md",
            "",
        ]
    )
    findings_path.write_text("\n".join(findings_lines), encoding="utf-8")

    progress_path.write_text(
        "\n".join(
            [
                f"# Progress Log ({task.task_id})",
                "",
                f"## Session: {dt.date.today().isoformat()}",
                "",
                "### Phase 1: Requirements & Discovery",
                "- **Status:** in_progress",
                f"- **Started:** {now}",
                "- Actions taken:",
                f"  - Created workplan for task {task.task_id}",
                "  - Marked task as PLANNED in todo_current",
                "- Files created/modified:",
                f"  - plans/workplans/{task.task_id}/task_plan.md (created)",
                f"  - plans/workplans/{task.task_id}/findings.md (created)",
                f"  - plans/workplans/{task.task_id}/progress.md (created)",
                "",
                "## Test Results",
                "| Test | Input | Expected | Actual | Status |",
                "|---|---|---|---|---|",
                "| | | | | |",
                "",
                "## Error Log",
                "| Timestamp | Error | Attempt | Resolution |",
                "|---|---|---|---|",
                "| | | 1 | |",
                "",
            ]
        ),
        encoding="utf-8",
    )


def choose_auto_task(tasks: list[TodoTask]) -> tuple[TodoTask | None, list[str]]:
    """Select the next task automatically with deterministic heuristics."""
    unfinished = [task for task in tasks if task.status in ("UNPLANNED", "PLANNED")]
    unplanned = [task for task in unfinished if task.status == "UNPLANNED"]
    planned = [task for task in unfinished if task.status == "PLANNED"]
    selected = unplanned[0] if unplanned else None
    rationale = [
        f"Candidate pool evaluated from unfinished tasks: {len(unfinished)} (UNPLANNED={len(unplanned)}, PLANNED={len(planned)}).",
        "Selected the first UNPLANNED task by todo order for predictability and single-task ownership.",
    ]
    return selected, rationale


def cmd_list(args: argparse.Namespace) -> int:
    """Print tasks with optional status filtering."""
    parsed = parse_todo_file(TODO_PATH)
    selected = parsed.tasks
    if args.status:
        status = normalize_status(args.status)
        selected = [task for task in parsed.tasks if task.status == status]
    columns = SIMPLE_TABLE_COLUMNS if parsed.table_kind == "simple" else RICH_TABLE_COLUMNS
    print("| " + " | ".join(columns) + " |")
    print("| " + " | ".join("---" for _ in columns) + " |")
    for task in selected:
        print("| " + " | ".join(task.to_cells(parsed.table_kind)) + " |")
    return 0


def cmd_quick_plan(args: argparse.Namespace) -> int:
    """Create one workplan for one task and mark it PLANNED."""
    parsed = parse_todo_file(TODO_PATH)
    tasks = parsed.tasks

    selected: TodoTask | None
    if args.task_id:
        selected = find_task(tasks, args.task_id)
        rationale = [
            "Task scope explicitly provided by user.",
            f"Selected task: {selected.task_id}.",
        ]
    elif args.task_ids:
        provided = [part.strip() for part in args.task_ids.split(",") if part.strip()]
        if len(provided) != 1:
            raise ValueError("quick-plan supports exactly one task. Use --task-id with a single task.")
        selected = find_task(tasks, provided[0])
        rationale = [
            "Task scope explicitly provided by legacy --task-ids input.",
            f"Selected task: {selected.task_id}.",
        ]
    else:
        selected, rationale = choose_auto_task(tasks)

    if selected is None:
        raise ValueError("No selectable UNPLANNED tasks found. Use quick-resume for existing PLANNED tasks.")
    if selected.status == "DONE":
        raise ValueError(f"Task {selected.task_id} is DONE and cannot be planned again.")
    if selected.status == "PLANNED":
        raise ValueError(f"Task {selected.task_id} is already PLANNED. Use quick-resume.")

    create_plan_files(task=selected, rationale=rationale)

    selected.status = "PLANNED"
    selected.updated_at = now_iso()
    if args.note:
        selected.note = args.note
    elif not args.task_id and not args.task_ids:
        selected.note = "auto-selected by agent heuristic"

    save_todo(TODO_PATH, parsed)
    print(f"Created workplan for task: {selected.task_id}")
    print(f"Task: {selected.task}")
    print("Files:")
    for path in task_file_paths(selected.task_id):
        print(f"- {path}")
    return 0


def cmd_quick_resume(args: argparse.Namespace) -> int:
    """Resolve one PLANNED task to continue and print related files."""
    parsed = parse_todo_file(TODO_PATH)
    planned = [task for task in parsed.tasks if task.status == "PLANNED"]
    if not planned:
        raise ValueError("No PLANNED tasks found.")

    selected = find_task(planned, args.task_id) if args.task_id else planned[0]

    print(f"Resume task: {selected.task_id} ({selected.task})")
    for path in task_file_paths(selected.task_id):
        print(f"- {path}")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    """Set task status with lifecycle guards and metadata updates."""
    parsed = parse_todo_file(TODO_PATH)
    task = find_task(parsed.tasks, args.task_id)
    new_status = normalize_status(args.status)

    task.status = new_status
    if args.note is not None:
        task.note = args.note
    task.updated_at = now_iso()

    save_todo(TODO_PATH, parsed)
    print(f"Updated {task.task_id} -> {task.status}")
    return 0


def cmd_view_active(_: argparse.Namespace) -> int:
    """Print the first active PLANNED task in one line for quick context hooks."""
    parsed = parse_todo_file(TODO_PATH)
    planned = [task for task in parsed.tasks if task.status == "PLANNED"]
    if not planned:
        print("[plan-tracker] no active PLANNED task")
        return 0
    task = planned[0]
    print(f"[plan-tracker] active={task.task_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser for task tracking operations."""
    parser = argparse.ArgumentParser(
        description="Track todo task lifecycle and per-task workplan directories under plans/workplans/<task_id>/."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Project root directory (default: current working directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List tasks from plans/todo_current.md")
    list_parser.add_argument("--status", help="Filter by status (UNPLANNED|PLANNED|DONE)")
    list_parser.set_defaults(func=cmd_list)

    plan_parser = subparsers.add_parser("quick-plan", help="Create one workplan and bind one task")
    plan_parser.add_argument("--task-id", help="Single task id to plan.")
    plan_parser.add_argument("--task-ids", help="Legacy comma-separated task ids. Must resolve to one task.")
    plan_parser.add_argument("--note", help="Optional note written to the selected task.")
    plan_parser.set_defaults(func=cmd_quick_plan)

    resume_parser = subparsers.add_parser("quick-resume", help="Pick one PLANNED task for continuation")
    resume_parser.add_argument("--task-id", help="Specific PLANNED task id")
    resume_parser.set_defaults(func=cmd_quick_resume)

    status_parser = subparsers.add_parser("set-status", help="Set one task status")
    status_parser.add_argument("--task-id", required=True)
    status_parser.add_argument("--status", required=True, help="UNPLANNED|PLANNED|DONE")
    status_parser.add_argument("--note", help="Optional note overwrite")
    status_parser.set_defaults(func=cmd_set_status)

    view_parser = subparsers.add_parser("view-active", help="Show first PLANNED task for hooks")
    view_parser.set_defaults(func=cmd_view_active)
    return parser


def main() -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    if args.root is not None:
        set_root(Path(args.root).resolve())
    try:
        return args.func(args)
    except Exception as exc:
        print(f"[plan-tracker] error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
