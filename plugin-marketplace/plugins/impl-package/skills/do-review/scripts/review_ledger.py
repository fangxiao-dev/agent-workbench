#!/usr/bin/env python3
"""Create and update the canonical do-review ledger in the user temp folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


LEDGER_NAME = re.compile(r"^\d{10}-[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{7}\.md$")


class ReviewRunError(ValueError):
    """The requested immutable review run cannot be created safely."""


def ledger_directory() -> Path:
    return Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()).resolve() / "do-review"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("slug must contain at least one ASCII letter or digit")
    return slug


def validate_ledger_path(value: str) -> Path:
    path = Path(value).resolve()
    directory = ledger_directory()
    if path.parent != directory or not LEDGER_NAME.fullmatch(path.name):
        raise ValueError(f"ledger path must be a do-review temp ledger: {directory}\\<YYMMDDHHMM>-<slug>-<shortsha>.md")
    return path


def run_git(repo: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        check=False,
    )


def git_output(repo: Path, *args: str) -> str:
    result = run_git(repo, *args)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise ReviewRunError(detail)
    return result.stdout.strip()


def resolve_repo_root(value: Path) -> Path:
    candidate = value.resolve()
    if not candidate.is_dir():
        raise ReviewRunError(f"repository path is not a directory: {candidate}")
    return Path(git_output(candidate, "rev-parse", "--show-toplevel")).resolve()


def resolve_commit(repo: Path, ref: str) -> str:
    return git_output(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def require_non_empty_diff(repo: Path, diff_range: str) -> None:
    result = run_git(repo, "diff", "--quiet", diff_range, "--")
    if result.returncode == 0:
        raise ReviewRunError(f"empty diff: {diff_range}")
    if result.returncode != 1:
        detail = result.stderr.strip() or result.stdout.strip() or "git diff failed"
        raise ReviewRunError(detail)


def normalize_source_path(repo: Path, value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        absolute = candidate.resolve()
    else:
        absolute = Path(os.path.abspath(repo / candidate))
    try:
        relative = absolute.relative_to(repo)
    except ValueError as error:
        raise ReviewRunError(f"contract source escapes repository: {value}") from error
    git_path = relative.as_posix()
    if not git_path or git_path == ".":
        raise ReviewRunError(f"contract source does not map to a Git path: {value}")
    return git_path


def source_record(repo: Path, resolved_head: str, value: str) -> dict[str, str]:
    git_path = normalize_source_path(repo, value)
    tree = run_git(
        repo,
        "ls-tree",
        "-z",
        "--full-tree",
        resolved_head,
        "--",
        f":(literal){git_path}",
        text=False,
    )
    if tree.returncode != 0:
        detail = tree.stderr.decode("utf-8", errors="replace").strip() or "git ls-tree failed"
        raise ReviewRunError(detail)
    records = [record for record in tree.stdout.split(b"\0") if record]
    if len(records) != 1:
        raise ReviewRunError(f"contract source is not a Git blob in resolved head: {value}")
    metadata, separator, returned_path = records[0].partition(b"\t")
    if not separator:
        raise ReviewRunError(f"cannot resolve contract source in resolved head: {value}")
    fields = metadata.decode("ascii", errors="strict").split()
    if len(fields) != 3 or fields[1] != "blob" or returned_path.decode("utf-8", errors="strict") != git_path:
        raise ReviewRunError(f"contract source is not a Git blob in resolved head: {value}")
    object_id = fields[2]
    blob = run_git(repo, "cat-file", "blob", object_id, text=False)
    if blob.returncode != 0:
        detail = blob.stderr.decode("utf-8", errors="replace").strip() or "git cat-file failed"
        raise ReviewRunError(detail)
    try:
        blob.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewRunError(f"contract source is not valid UTF-8 in resolved head: {value}") from error
    return {
        "path": git_path,
        "git_object_id": object_id,
        "sha256": hashlib.sha256(blob.stdout).hexdigest(),
    }


def prepare_review_run(args: argparse.Namespace) -> dict[str, object]:
    repo = resolve_repo_root(args.repo_root)
    resolved_base = resolve_commit(repo, args.base)
    resolved_head = resolve_commit(repo, args.head)
    diff_range = f"{resolved_base}...{resolved_head}"
    require_non_empty_diff(repo, diff_range)
    sources = [source_record(repo, resolved_head, value) for value in args.source]
    return {
        "resolved_base_sha": resolved_base,
        "resolved_head_sha": resolved_head,
        "diff_range": diff_range,
        "contract_sources": sources,
    }


def create(args: argparse.Namespace) -> int:
    review_run = prepare_review_run(args)
    slug = slugify(args.slug)
    resolved_head = str(review_run["resolved_head_sha"])
    short_sha = resolved_head[:7]
    timestamp = args.timestamp or datetime.now().strftime("%y%m%d%H%M")
    if not re.fullmatch(r"\d{10}", timestamp):
        raise ValueError("timestamp must use YYMMDDHHMM")
    directory = ledger_directory()
    path = directory / f"{timestamp}-{slug}-{short_sha}.md"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing ledger: {path}")
    contract_sources = json.dumps(review_run["contract_sources"], ensure_ascii=False, indent=2)
    content = f"""# do-review canonical ledger

- Ledger path: `{path}`
- Review slug: `{slug}`
- Created at (local): `{datetime.now().astimezone().isoformat(timespec='seconds')}`
- Resolved base SHA: `{review_run['resolved_base_sha']}`
- Resolved head SHA: `{resolved_head}`
- Diff range: `{review_run['diff_range']}`
- Mode: `{args.mode}`
- Round cap: `{args.round_cap}`
- Review phase: `pending`
- Safety applicability / evidence / coverage: `pending`
- Owner: `main-session`
- Status: `in-progress`

## Immutable contract sources

```json
{contract_sources}
```

## Track lifecycle

| Track | State | Consecutive clean rounds | Last completed round | Reactivation reason |
| --- | --- | --- | --- | --- |

- The main session initializes this table before Round 1. It is required only for `Loop` mode; `N rounds` and `Closure verification` keep every selected track active.

## Review rounds

| Round | Track verdicts | New accepted | Convergence note |
| --- | --- | --- | --- |

## Known findings ledger

| ID | Title | Severity | Classification | Source | Status | Evidence | Main-session decision |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Verification and decisions

- Stop reason: `pending`
"""
    directory.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with path.open("x", encoding="utf-8", newline="\n") as ledger:
            created = True
            ledger.write(content)
    except OSError:
        if created:
            path.unlink(missing_ok=True)
        raise
    output = {"ledger_path": str(path), **review_run}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def write(args: argparse.Namespace) -> int:
    path = validate_ledger_path(args.ledger)
    content = sys.stdin.read()
    if not content.strip():
        raise ValueError("refusing to write an empty ledger")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    print(path)
    return 0


def show(args: argparse.Namespace) -> int:
    path = validate_ledger_path(args.ledger)
    sys.stdout.write(path.read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create a new canonical ledger")
    create_parser.add_argument("--repo-root", type=Path, required=True)
    create_parser.add_argument("--base", required=True)
    create_parser.add_argument("--head", required=True)
    create_parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Contract source at resolved head, absolute or repository-relative; repeat as needed.",
    )
    create_parser.add_argument("--slug", required=True)
    create_parser.add_argument("--mode", required=True)
    create_parser.add_argument("--round-cap", required=True)
    create_parser.add_argument("--timestamp", help="YYMMDDHHMM; intended for deterministic tests")
    create_parser.set_defaults(handler=create)

    write_parser = subparsers.add_parser("write", help="atomically replace an existing ledger from stdin")
    write_parser.add_argument("--ledger", required=True)
    write_parser.set_defaults(handler=write)

    show_parser = subparsers.add_parser("show", help="read an existing ledger")
    show_parser.add_argument("--ledger", required=True)
    show_parser.set_defaults(handler=show)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"review_ledger: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
