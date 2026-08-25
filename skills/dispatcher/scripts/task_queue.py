#!/usr/bin/env python3
"""Validated single-writer task queue for the Dispatcher skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


FIELDS = {"id", "summary", "status", "depOn"}
STATUSES = {"planned", "in-progress"}


class QueueError(Exception):
    """A queue input or persistence error that is safe to show to the caller."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise QueueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def validate_queue(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise QueueError("top-level JSON value must be an array")

    seen_ids: set[str] = set()
    for index, task in enumerate(value):
        if not isinstance(task, dict):
            raise QueueError(f"task at index {index} must be an object")
        if set(task) != FIELDS:
            raise QueueError(f"task at index {index} must contain exactly: id, summary, status, depOn")

        task_id = task["id"]
        if not isinstance(task_id, str) or not task_id.strip():
            raise QueueError(f"task at index {index} id must be a non-empty string")
        if task_id in seen_ids:
            raise QueueError(f"duplicate task id: {task_id}")
        seen_ids.add(task_id)

        summary = task["summary"]
        if not isinstance(summary, str) or not summary.strip():
            raise QueueError(f"task {task_id} summary must be a non-empty string")

        status = task["status"]
        if not isinstance(status, str) or status not in STATUSES:
            raise QueueError(f"task {task_id} status must be planned or in-progress")

        dependencies = task["depOn"]
        if not isinstance(dependencies, list):
            raise QueueError(f"task {task_id} depOn must be an array")
        seen_dependencies: set[str] = set()
        for dependency in dependencies:
            if not isinstance(dependency, str) or not dependency.strip():
                raise QueueError(f"task {task_id} dependency ids must be non-empty strings")
            if dependency in seen_dependencies:
                raise QueueError(f"task {task_id} has duplicate dependency: {dependency}")
            seen_dependencies.add(dependency)

    for task in value:
        task_id = task["id"]
        for dependency in task["depOn"]:
            if dependency == task_id:
                raise QueueError(f"task {task_id} cannot depend on itself")
            if dependency not in seen_ids:
                raise QueueError(f"task {task_id} has unknown dependency: {dependency}")

    graph = {task["id"]: task["depOn"] for task in value}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise QueueError(f"dependency graph contains a cycle involving: {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in graph[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id)

    return value


def load_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise QueueError(f"queue file does not exist: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise QueueError(f"cannot read queue file {path}: {error}") from error
    try:
        value = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise QueueError(f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}") from error
    return validate_queue(value)


def render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write_queue(path: Path, queue: list[dict[str, Any]], *, expect_absent: bool = False) -> None:
    validate_queue(queue)
    parent = path.parent
    if not parent.is_dir():
        raise QueueError(f"parent directory does not exist: {parent}")
    if expect_absent and path.exists():
        raise QueueError(f"queue file already exists: {path}")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(render_json(queue))
            handle.flush()
            os.fsync(handle.fileno())

        if expect_absent and path.exists():
            raise QueueError(f"queue file already exists: {path}")
        os.replace(temp_path, path)
        temp_path = None
    except QueueError:
        raise
    except OSError as error:
        raise QueueError(f"cannot write queue file {path}: {error}") from error
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def print_json(value: Any) -> None:
    sys.stdout.write(render_json(value))


def find_task(queue: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    for task in queue:
        if task["id"] == task_id:
            return task
    raise QueueError(f"task not found: {task_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain a validated Dispatcher task queue.")
    parser.add_argument("--path", required=True, type=Path, help="Path to task-queue.json")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="Create an empty queue without overwriting an existing path")

    add = commands.add_parser("add", help="Append a planned task")
    add.add_argument("--id", required=True)
    add.add_argument("--summary", required=True)
    add.add_argument("--dep-on", action="append", default=[])

    delete = commands.add_parser("delete", help="Delete a task and release it from all dependencies")
    delete.add_argument("--id", required=True)

    update_summary = commands.add_parser("update-summary", help="Replace a task summary")
    update_summary.add_argument("--id", required=True)
    update_summary.add_argument("--summary", required=True)

    update_status = commands.add_parser("update-status", help="Replace a task status")
    update_status.add_argument("--id", required=True)
    update_status.add_argument("--status", required=True, choices=sorted(STATUSES))

    update_deps = commands.add_parser("update-deps", help="Add or remove one dependency")
    update_deps.add_argument("--id", required=True)
    dependency_change = update_deps.add_mutually_exclusive_group(required=True)
    dependency_change.add_argument("--add")
    dependency_change.add_argument("--remove")

    list_command = commands.add_parser("list", help="Return the queue or one task")
    list_command.add_argument("--id")

    commands.add_parser("get-next-tasks", help="Return all planned tasks with no dependencies")
    return parser


def run_command(args: argparse.Namespace) -> Any:
    path: Path = args.path
    if args.command == "init":
        queue: list[dict[str, Any]] = []
        write_queue(path, queue, expect_absent=True)
        return queue

    queue = load_queue(path)
    if args.command == "list":
        return find_task(queue, args.id) if args.id else queue
    if args.command == "get-next-tasks":
        return [task for task in queue if task["status"] == "planned" and task["depOn"] == []]

    if args.command == "add":
        if any(task["id"] == args.id for task in queue):
            raise QueueError(f"task already exists: {args.id}")
        queue.append({"id": args.id, "summary": args.summary, "status": "planned", "depOn": args.dep_on})
    elif args.command == "delete":
        find_task(queue, args.id)
        queue = [task for task in queue if task["id"] != args.id]
        for task in queue:
            task["depOn"] = [dependency for dependency in task["depOn"] if dependency != args.id]
    elif args.command == "update-summary":
        find_task(queue, args.id)["summary"] = args.summary
    elif args.command == "update-status":
        find_task(queue, args.id)["status"] = args.status
    elif args.command == "update-deps":
        task = find_task(queue, args.id)
        dependencies = task["depOn"]
        if args.add is not None:
            if args.add in dependencies:
                raise QueueError(f"task {args.id} already depends on: {args.add}")
            dependencies.append(args.add)
        else:
            if args.remove not in dependencies:
                raise QueueError(f"task {args.id} does not depend on: {args.remove}")
            dependencies.remove(args.remove)
    else:
        raise QueueError(f"unsupported command: {args.command}")

    write_queue(path, queue)
    return queue


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_command(args)
    except QueueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
