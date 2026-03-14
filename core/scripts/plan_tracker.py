"""Track todo tasks and workplans for multi-agent planning-with-files workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TODO_PATH = Path("plans/todo_current.md")
WORKPLAN_DIR = Path("plans/workplans")
STATUS_VALUES = ("UNPLANNED", "PLANNED", "DONE")
TABLE_COLUMNS = ("task_id", "task", "status", "plan_id", "updated_at", "note")


@dataclass
class TodoTask:
    """Structured row representation for a task in plans/todo_current.md."""

    task_id: str
    task: str
    status: str
    plan_id: str
    updated_at: str
    note: str

    def to_cells(self) -> list[str]:
        """Return row cells in canonical table column order."""
        return [
            self.task_id,
            self.task,
            self.status,
            self.plan_id,
            self.updated_at,
            self.note,
        ]


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


def parse_todo_file(path: Path) -> tuple[list[str], list[TodoTask]]:
    """Parse markdown task table from todo_current.md."""
    if not path.exists():
        raise FileNotFoundError(f"Missing todo file: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        cells = split_row(line)
        if [c.lower() for c in cells] == list(TABLE_COLUMNS):
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("todo_current.md is not in table format. Please migrate it first.")

    preamble = lines[:header_idx]
    tasks: list[TodoTask] = []
    for line in lines[header_idx + 1 :]:
        if not line.strip():
            continue
        cells = split_row(line)
        if not cells:
            continue
        if is_separator_row(cells):
            continue
        if len(cells) < len(TABLE_COLUMNS):
            cells += [""] * (len(TABLE_COLUMNS) - len(cells))
        row = dict(zip(TABLE_COLUMNS, cells[: len(TABLE_COLUMNS)]))
        tasks.append(
            TodoTask(
                task_id=row["task_id"],
                task=row["task"],
                status=normalize_status(row["status"]),
                plan_id=row["plan_id"],
                updated_at=row["updated_at"],
                note=row["note"],
            )
        )

    return preamble, tasks


def render_table(tasks: list[TodoTask]) -> list[str]:
    """Render task rows into canonical markdown table lines."""
    header = "| " + " | ".join(TABLE_COLUMNS) + " |"
    separator = "| " + " | ".join("---" for _ in TABLE_COLUMNS) + " |"
    lines = [header, separator]
    for task in tasks:
        cells = task.to_cells()
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def save_todo(path: Path, preamble: list[str], tasks: list[TodoTask]) -> None:
    """Persist todo markdown with preamble + canonical table."""
    output = []
    output.extend(preamble)
    if output and output[-1].strip() != "":
        output.append("")
    output.extend(render_table(tasks))
    output.append("")
    path.write_text("\n".join(output), encoding="utf-8")


def find_task(tasks: Iterable[TodoTask], task_id: str) -> TodoTask:
    """Find task by id or raise clear error."""
    for task in tasks:
        if task.task_id == task_id:
            return task
    raise ValueError(f"Task '{task_id}' was not found.")


def parse_task_ids(value: str | None) -> list[str]:
    """Parse comma-separated task id input."""
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def validate_plan_id(plan_id: str) -> None:
    """Validate project plan_id format: YYYYMMDD-<task_id>[-NN]."""
    value = plan_id.strip()
    if not value:
        raise ValueError("Invalid plan_id format: empty value.")

    parts = value.split("-")
    if len(parts) < 3:
        raise ValueError(
            "Invalid plan_id format. Expected YYYYMMDD-<task_id>[-NN], e.g. 20260218-TC-008."
        )

    date_part = parts[0]
    if not re.fullmatch(r"\d{8}", date_part):
        raise ValueError(
            "Invalid plan_id format. Expected YYYYMMDD-<task_id>[-NN], e.g. 20260218-TC-008."
        )
    try:
        dt.datetime.strptime(date_part, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(
            f"Invalid plan_id format: date '{date_part}' is not a valid calendar date."
        ) from exc

    suffix = ""
    task_segments = parts[1:]
    if len(task_segments) >= 3 and re.fullmatch(r"\d{2}", task_segments[-1]):
        suffix = task_segments[-1]
        task_segments = task_segments[:-1]

    task_id_part = "-".join(task_segments)
    if not re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+", task_id_part):
        raise ValueError(
            "Invalid plan_id format. Expected YYYYMMDD-<task_id>[-NN], e.g. 20260218-TC-008."
        )

    if suffix and suffix == "00":
        raise ValueError("Invalid plan_id format: optional suffix must be 01-99.")


def build_plan_id(existing: set[str], task_id: str, today: dt.date | None = None) -> str:
    """Generate a unique plan_id in YYYYMMDD-task_id[-NN] format."""
    normalized_task_id = task_id.strip()
    if not normalized_task_id:
        raise ValueError("Cannot build plan_id: task_id is empty.")
    if not re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+", normalized_task_id):
        raise ValueError(
            f"Cannot build plan_id: task_id '{task_id}' must contain alphanumeric segments joined by hyphens."
        )

    day = today or dt.date.today()
    base = f"{day.strftime('%Y%m%d')}-{normalized_task_id}"
    candidate = base
    suffix = 0
    while candidate in existing:
        suffix += 1
        candidate = f"{base}-{suffix:02d}"
    return candidate


def create_plan_files(plan_id: str, tasks: list[TodoTask], rationale: list[str]) -> None:
    """Create task_plan/findings/progress markdown files for a new plan."""
    WORKPLAN_DIR.mkdir(parents=True, exist_ok=True)
    task_list = "\n".join(f"- {task.task_id}: {task.task}" for task in tasks)
    now = now_iso()
    task_plan_path = WORKPLAN_DIR / f"task_plan.{plan_id}.md"
    findings_path = WORKPLAN_DIR / f"findings.{plan_id}.md"
    progress_path = WORKPLAN_DIR / f"progress.{plan_id}.md"

    task_plan_path.write_text(
        "\n".join(
            [
                f"# Task Plan: {plan_id}",
                "",
                "## Goal",
                "Implement selected todo_current tasks and keep progress persistent on disk.",
                "",
                "## Scope",
                task_list,
                "",
                "## Current Phase",
                "Phase 1",
                "",
                "## Phases",
                "### Phase 1: Requirements & Discovery",
                "- [x] Confirm selected tasks and constraints",
                "- [ ] Write findings and rationale",
                "- **Status:** in_progress",
                "",
                "### Phase 2: Planning & Structure",
                "- [ ] Define implementation sequence",
                "- [ ] Confirm dependencies and risks",
                "- **Status:** pending",
                "",
                "### Phase 3: Implementation",
                "- [ ] Execute selected tasks",
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
        f"# Findings & Decisions ({plan_id})",
        "",
        "## Requirements",
        task_list,
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
            f"- plans/workplans/task_plan.{plan_id}.md",
            "",
        ]
    )
    findings_path.write_text("\n".join(findings_lines), encoding="utf-8")

    progress_path.write_text(
        "\n".join(
            [
                f"# Progress Log ({plan_id})",
                "",
                f"## Session: {dt.date.today().isoformat()}",
                "",
                "### Phase 1: Requirements & Discovery",
                "- **Status:** in_progress",
                f"- **Started:** {now}",
                "- Actions taken:",
                f"  - Created plan {plan_id}",
                "  - Bound selected tasks from todo_current",
                "- Files created/modified:",
                f"  - plans/workplans/task_plan.{plan_id}.md (created)",
                f"  - plans/workplans/findings.{plan_id}.md (created)",
                f"  - plans/workplans/progress.{plan_id}.md (created)",
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


def choose_auto_tasks(tasks: list[TodoTask], max_tasks: int) -> tuple[list[TodoTask], list[str]]:
    """Select next tasks automatically with deterministic and explainable heuristics."""
    unfinished = [task for task in tasks if task.status in ("UNPLANNED", "PLANNED")]
    unplanned = [task for task in unfinished if task.status == "UNPLANNED"]
    planned = [task for task in unfinished if task.status == "PLANNED"]
    selected = unplanned[:max_tasks]
    rationale = [
        f"Candidate pool evaluated from unfinished tasks: {len(unfinished)} (UNPLANNED={len(unplanned)}, PLANNED={len(planned)}).",
        "Selected UNPLANNED tasks first to avoid plan ownership conflicts and maximize parallel throughput.",
        f"Chosen by todo order for predictability; selection count={len(selected)}.",
    ]
    return selected, rationale


def cmd_list(args: argparse.Namespace) -> int:
    """Print tasks with optional status filtering."""
    _, tasks = parse_todo_file(TODO_PATH)
    selected = tasks
    if args.status:
        status = normalize_status(args.status)
        selected = [task for task in tasks if task.status == status]
    print("| " + " | ".join(TABLE_COLUMNS) + " |")
    print("| " + " | ".join("---" for _ in TABLE_COLUMNS) + " |")
    for task in selected:
        print("| " + " | ".join(task.to_cells()) + " |")
    return 0


def cmd_quick_plan(args: argparse.Namespace) -> int:
    """Create one plan for selected tasks and mark them as PLANNED."""
    preamble, tasks = parse_todo_file(TODO_PATH)
    provided_ids = parse_task_ids(args.task_ids)

    if provided_ids:
        selected = [find_task(tasks, task_id) for task_id in provided_ids]
        rationale = [
            "Task scope explicitly provided by user.",
            f"Selected tasks: {', '.join(task.task_id for task in selected)}.",
        ]
    else:
        selected, rationale = choose_auto_tasks(tasks, max_tasks=args.max_tasks)

    if not selected:
        raise ValueError("No selectable tasks found. Use quick-resume for existing PLANNED tasks.")

    for task in selected:
        if task.status == "DONE":
            raise ValueError(f"Task {task.task_id} is DONE and cannot be planned again.")
        if task.status == "PLANNED" and task.plan_id:
            raise ValueError(
                f"Task {task.task_id} is already PLANNED by plan '{task.plan_id}'. Use quick-resume."
            )

    existing_plan_ids = {task.plan_id for task in tasks if task.plan_id}
    if args.plan_id:
        validate_plan_id(args.plan_id)
        plan_id = args.plan_id
    else:
        plan_id = build_plan_id(existing_plan_ids, task_id=selected[0].task_id)

    create_plan_files(plan_id=plan_id, tasks=selected, rationale=rationale)

    timestamp = now_iso()
    for task in selected:
        task.status = "PLANNED"
        task.plan_id = plan_id
        task.updated_at = timestamp
        if args.note:
            task.note = args.note
        elif not provided_ids:
            task.note = "auto-selected by agent heuristic"

    save_todo(TODO_PATH, preamble, tasks)
    print(f"Created plan: {plan_id}")
    print("Tasks:")
    for task in selected:
        print(f"- {task.task_id}: {task.task}")
    print(f"Files: {WORKPLAN_DIR}/task_plan.{plan_id}.md, findings.{plan_id}.md, progress.{plan_id}.md")
    return 0


def cmd_quick_resume(args: argparse.Namespace) -> int:
    """Resolve one PLANNED task/plan to continue and print related files."""
    _, tasks = parse_todo_file(TODO_PATH)
    planned = [task for task in tasks if task.status == "PLANNED"]
    if not planned:
        raise ValueError("No PLANNED tasks found.")

    selected: TodoTask | None = None
    if args.plan_id:
        for task in planned:
            if task.plan_id == args.plan_id:
                selected = task
                break
        if selected is None:
            raise ValueError(f"No PLANNED tasks found for plan '{args.plan_id}'.")
    elif args.task_id:
        selected = find_task(planned, args.task_id)
    else:
        selected = planned[0]

    assert selected is not None
    if not selected.plan_id:
        raise ValueError(f"Task {selected.task_id} is PLANNED but missing plan_id.")

    plan_id = selected.plan_id
    print(f"Resume task: {selected.task_id} ({selected.task})")
    print(f"Plan: {plan_id}")
    print(f"- {WORKPLAN_DIR / f'task_plan.{plan_id}.md'}")
    print(f"- {WORKPLAN_DIR / f'findings.{plan_id}.md'}")
    print(f"- {WORKPLAN_DIR / f'progress.{plan_id}.md'}")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    """Set task status with lifecycle guards and metadata updates."""
    preamble, tasks = parse_todo_file(TODO_PATH)
    task = find_task(tasks, args.task_id)
    new_status = normalize_status(args.status)

    if new_status in ("PLANNED", "DONE"):
        plan_id = args.plan_id or task.plan_id
        if not plan_id:
            raise ValueError(f"Task {task.task_id}: status {new_status} requires a plan_id.")
        if args.plan_id:
            validate_plan_id(plan_id)
        task.plan_id = plan_id
    elif new_status == "UNPLANNED":
        task.plan_id = ""

    task.status = new_status
    if args.note is not None:
        task.note = args.note
    task.updated_at = now_iso()

    save_todo(TODO_PATH, preamble, tasks)
    print(f"Updated {task.task_id} -> {task.status} (plan_id={task.plan_id or 'N/A'})")
    return 0


def cmd_bind_task(args: argparse.Namespace) -> int:
    """Bind a task to an active plan and mark it PLANNED."""
    preamble, tasks = parse_todo_file(TODO_PATH)
    task = find_task(tasks, args.task_id)
    validate_plan_id(args.plan_id)

    if task.status == "DONE":
        raise ValueError(f"Task {task.task_id} is DONE and cannot be rebound.")
    if task.status == "PLANNED" and task.plan_id and task.plan_id != args.plan_id:
        raise ValueError(
            f"Task {task.task_id} is already PLANNED by plan '{task.plan_id}', cannot bind to '{args.plan_id}'."
        )

    task.status = "PLANNED"
    task.plan_id = args.plan_id
    task.updated_at = now_iso()
    if args.note is not None:
        task.note = args.note

    save_todo(TODO_PATH, preamble, tasks)
    print(f"Bound {task.task_id} to plan {args.plan_id}")
    return 0


def cmd_view_active(_: argparse.Namespace) -> int:
    """Print the first active PLANNED task in one line for quick context hooks."""
    _, tasks = parse_todo_file(TODO_PATH)
    planned = [task for task in tasks if task.status == "PLANNED"]
    if not planned:
        print("[plan-tracker] no active PLANNED task")
        return 0
    task = planned[0]
    print(f"[plan-tracker] active={task.task_id} plan={task.plan_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser for plan/task tracking operations."""
    parser = argparse.ArgumentParser(
        description="Track todo task lifecycle and multi-plan files under plans/workplans."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List tasks from plans/todo_current.md")
    list_parser.add_argument("--status", help="Filter by status (UNPLANNED|PLANNED|DONE)")
    list_parser.set_defaults(func=cmd_list)

    plan_parser = subparsers.add_parser("quick-plan", help="Create one plan and bind task(s)")
    plan_parser.add_argument("--task-ids", help="Comma-separated task ids. Omit for auto-select.")
    plan_parser.add_argument("--max-tasks", type=int, default=1, help="Auto-select count when task ids omitted.")
    plan_parser.add_argument("--plan-id", help="Optional explicit plan id (YYYYMMDD-<task_id>[-NN]).")
    plan_parser.add_argument("--note", help="Optional note written to selected tasks.")
    plan_parser.set_defaults(func=cmd_quick_plan)

    resume_parser = subparsers.add_parser("quick-resume", help="Pick one PLANNED task for continuation")
    resume_parser.add_argument("--task-id", help="Specific PLANNED task id")
    resume_parser.add_argument("--plan-id", help="Specific plan id")
    resume_parser.set_defaults(func=cmd_quick_resume)

    status_parser = subparsers.add_parser("set-status", help="Set one task status")
    status_parser.add_argument("--task-id", required=True)
    status_parser.add_argument("--status", required=True, help="UNPLANNED|PLANNED|DONE")
    status_parser.add_argument("--plan-id", help="Required for PLANNED or DONE if task has no plan_id; format YYYYMMDD-<task_id>[-NN]")
    status_parser.add_argument("--note", help="Optional note overwrite")
    status_parser.set_defaults(func=cmd_set_status)

    bind_parser = subparsers.add_parser("bind-task", help="Bind one task to an active plan")
    bind_parser.add_argument("--task-id", required=True)
    bind_parser.add_argument("--plan-id", required=True, help="Plan id in YYYYMMDD-<task_id>[-NN] format")
    bind_parser.add_argument("--note", help="Optional note overwrite")
    bind_parser.set_defaults(func=cmd_bind_task)

    view_parser = subparsers.add_parser("view-active", help="Show first PLANNED task for hooks")
    view_parser.set_defaults(func=cmd_view_active)
    return parser


def main() -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"[plan-tracker] error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
