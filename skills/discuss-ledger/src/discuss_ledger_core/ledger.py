#!/usr/bin/env python3
"""discuss_ledger.py — deterministic writer for discuss-ledger documents.

The script owns the *structure and state machine* of a discussion ledger so that
agents never hand-edit YAML frontmatter, renumber point IDs, move sections, or
forget to bump the round. Agents supply *decisions and prose*; the script does
the mechanical, error-prone bookkeeping.

Subcommands:
  init      create a ledger from the canonical skeleton (+ ensure dir & gitignore)
  status    print current state (status/round/next + open-point table) — read only
  add-point register a NEW disagreement (auto-allocates Dn, adds table row + log entry)
  contest   add a counter-argument to an existing point in the current round
  converge  promote a point into the convergence section with a source marker
  end-turn  bump the round, wait for external next-speaker assignment
  set-next  set the next speaker explicitly (user/orchestrator decision)

Edits are targeted splices, never a full re-render, so free-form prose written by
another party (e.g. Codex editing the file directly) is preserved.

No third-party dependencies. Mutating commands accept --dry-run to preview.
"""
from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass
import io
import os
import re
import sys
import tempfile
import time
from typing import Any

CONV_HEADER = "## 收敛区(已定论,勿重开)"
POINTS_HEADER = "## 未决分歧"
LOG_HEADER = "## 讨论记录"
CONV_PLACEHOLDER = "_(初始化时为空"
DEFAULT_DIR = "docs/exchange/discuss"

STATUS_OPEN = "进行中"
STATUS_AGREED = "已达成一致"
STATUS_DEADLOCK = "僵局"
STATUS_WAITING_NEXT = "待指定"

POINT_OPEN = "分歧"
POINT_CONVERGED = "收敛"
POINT_DEADLOCK = "僵局"

FM_ORDER = ["topic", "slug", "status", "round", "next", "participants"]
_HELD_LOCKS: set[str] = set()


@dataclass
class CommandResult:
    message: str
    path: str | None = None


@dataclass
class LedgerStatus:
    frontmatter: dict[str, Any]
    open_points: list[dict[str, str]]
    convergence: list[str]
    markdown: str


# --------------------------------------------------------------------------- IO
def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@contextlib.contextmanager
def file_lock(path: str, timeout_s: float = 10.0):
    lock_path = f"{path}.lock"
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lock_key = os.path.abspath(lock_path)
    if lock_key in _HELD_LOCKS:
        yield
        return
    deadline = time.monotonic() + timeout_s
    fd = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for lock: {lock_path}")
            time.sleep(0.05)
    try:
        _HELD_LOCKS.add(lock_key)
        os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
        yield
    finally:
        _HELD_LOCKS.discard(lock_key)
        os.close(fd)
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


def write_text(path: str, text: str) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    with file_lock(path):
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".md", dir=parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def sanitize_cell(s: str) -> str:
    """Pipes break markdown tables; summaries live in a table cell."""
    return s.replace("|", "/").replace("\n", " ").strip()


def read_body_arg(value: str | None) -> str:
    if value is None:
        return ""
    if value == "-":
        return sys.stdin.read().rstrip("\n")
    return value


# --------------------------------------------------------------- frontmatter
def split_frontmatter(text: str):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("ledger has no YAML frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    fm = {}
    for ln in lines[1:end]:
        if ":" not in ln:
            continue
        key, _, raw = ln.partition(":")
        key = key.strip()
        val = raw.split("  #")[0].strip()  # drop trailing "  # comment"
        if key == "participants":
            val = [p.strip() for p in val.strip("[]").split(",") if p.strip()]
        elif key == "round":
            try:
                val = int(val)
            except ValueError:
                val = 1
        fm[key] = val
    body = "\n".join(lines[end + 1 :])
    return fm, body


def render_frontmatter(fm: dict) -> str:
    out = ["---"]
    for k in FM_ORDER:
        if k not in fm:
            continue
        v = fm[k]
        if k == "participants":
            v = "[" + ", ".join(v) + "]"
        out.append(f"{k}: {v}")
    out.append("---")
    return "\n".join(out)


def replace_frontmatter(text: str, fm: dict) -> str:
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
    body = "\n".join(lines[end + 1 :])
    return render_frontmatter(fm) + "\n" + body


def parse_participants(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


def ensure_participant(fm: dict, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    participants = fm.setdefault("participants", [])
    if name in participants:
        return False
    participants.append(name)
    return True


# ------------------------------------------------------------------ sections
def section_bounds(lines, header):
    """Return (start, end) line indices; body is lines[start+1:end]."""
    start = next((i for i, l in enumerate(lines) if l.strip() == header), -1)
    if start == -1:
        raise ValueError(f"missing section: {header}")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return start, end


# --------------------------------------------------------------- point table
ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def parse_row(line):
    m = ROW_RE.match(line)
    if not m:
        return None
    cells = [c.strip() for c in m.group(1).split("|")]
    if len(cells) < 4:
        return None
    return cells


def table_rows(lines, start, end):
    """Yield (index, cells) for data rows (skip header + separator)."""
    seen_header = False
    for i in range(start + 1, end):
        cells = parse_row(lines[i])
        if cells is None:
            continue
        if not seen_header:
            seen_header = True  # the "点ID | 摘要 ..." header
            continue
        if set("".join(cells)) <= set("-: "):
            continue  # the |---|---| separator
        yield i, cells


def render_row(cells):
    return "| " + " | ".join(cells) + " |"


def find_point(lines, point_id):
    start, end = section_bounds(lines, POINTS_HEADER)
    for i, cells in table_rows(lines, start, end):
        if cells[0] == point_id:
            return i, cells
    return -1, None


def next_point_id(lines):
    start, end = section_bounds(lines, POINTS_HEADER)
    mx = 0
    for _, cells in table_rows(lines, start, end):
        m = re.match(r"D(\d+)", cells[0])
        if m:
            mx = max(mx, int(m.group(1)))
    return f"D{mx + 1}"


def last_table_index(lines, start, end):
    last = -1
    for i, _ in table_rows(lines, start, end):
        last = i
    if last != -1:
        return last
    # no data rows yet: insert right after the separator (or header)
    for i in range(start + 1, end):
        if set("".join(parse_row(lines[i]) or [""])) <= set("-: ") and parse_row(lines[i]):
            return i
    for i in range(start + 1, end):
        if parse_row(lines[i]):
            return i
    return start


# --------------------------------------------------------------- round blocks
ROUND_RE = re.compile(r"^### 轮次 (\d+)(?: · (.+))?$")


def round_header_index(lines, rnd, author=None):
    s, _ = section_bounds(lines, LOG_HEADER)
    for i in range(s + 1, len(lines)):
        m = ROUND_RE.match(lines[i])
        if not m or int(m.group(1)) != rnd:
            continue
        if author is None or (m.group(2) or "").strip() == author:
            return i
    return -1


def round_block_end(lines, header_idx):
    for i in range(header_idx + 1, len(lines)):
        if lines[i].startswith("### ") or lines[i].startswith("## "):
            return i
    return len(lines)


def append_log_entry(lines, rnd, author, bullet):
    """Append a bullet under '### 轮次 <rnd> · <author>', creating it if absent."""
    hidx = round_header_index(lines, rnd, author)
    if hidx == -1:
        # create a new round block at end of file
        while lines and lines[-1].strip() == "":
            lines.pop()
        lines.extend(["", f"### 轮次 {rnd} · {author}", "", bullet])
        return
    end = round_block_end(lines, hidx)
    insert_at = end
    while insert_at - 1 > hidx and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, bullet)


def render_bullet(point_id, body, suffix=""):
    body_lines = body.split("\n")
    head = f"- **{point_id}**{suffix}: {body_lines[0]}"
    rest = [("  " + l) if l.strip() else "" for l in body_lines[1:]]
    return "\n".join([head, *rest]) if rest else head


# ------------------------------------------------------------------- gitignore
def ensure_gitignore(root, dir_rel):
    gi = os.path.join(root, ".gitignore")
    entry = dir_rel.rstrip("/") + "/"
    existing = read_text(gi).splitlines() if os.path.exists(gi) else []
    if entry in (l.strip() for l in existing):
        return False
    text = ("\n".join(existing) + "\n" if existing else "") + entry + "\n"
    write_text(gi, text)
    return True


# ----------------------------------------------------------------- skeleton
def build_skeleton(fm, title, source_path):
    src_line = f"> 评审对象:`{source_path}`\n" if source_path else ""
    return f"""{render_frontmatter(fm)}

# 讨论:{title}

{src_line}> 参与方:{' / '.join(fm['participants'])}

{CONV_HEADER}

> 每条:`[来源标记]` 结论 —— 简短依据。来源标记:`[一致]` / `[用户裁决]`(覆盖时写 `[用户裁决·覆盖<方>]`)。

- {CONV_PLACEHOLDER}时为空,或只放确实无争议的点)_

{POINTS_HEADER}

> 状态取值:`分歧` / `收敛` / `僵局`。

| 点ID | 摘要 | 状态 | 已历轮次 |
|------|------|------|---------|

{LOG_HEADER}

> 只记分歧的完整论证;同意的点一句带过。论证要带依据(文件路径、行号、可核实事实)。
"""


# ------------------------------------------------------------------ commands
def ledger_path(args):
    return os.path.join(args.root, args.dir, f"discuss-{args.slug}.md")


def out(text, args, path):
    if getattr(args, "dry_run", False):
        sys.stdout.write("# --- dry-run preview (not written) ---\n")
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    else:
        write_text(path, text)


def cmd_init(args):
    slug = args.slug or derive_slug(args.topic)
    args.slug = slug
    path = ledger_path(args)
    if os.path.exists(path) and not args.force:
        sys.exit(f"ledger already exists: {path} (use --force to overwrite)")
    parts = parse_participants(args.participants)
    fm = {
        "topic": args.topic,
        "slug": slug,
        "status": STATUS_OPEN,
        "round": 1,
        "next": args.initiator,
        "participants": parts,
    }
    ensure_participant(fm, args.initiator)
    title = args.title or slug
    source = args.topic if ("/" in args.topic or args.topic.endswith(".md")) else ""
    text = build_skeleton(fm, title, source)
    if not args.dry_run:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        changed = ensure_gitignore(args.root, args.dir)
        if changed:
            print(f"gitignore: added '{args.dir.rstrip('/')}/'")
    out(text, args, path)
    print(f"initialized round 1; next = {args.initiator}")
    print(f"path: {path}")


def derive_slug(topic):
    base = os.path.basename(topic)
    if base.endswith(".md"):
        base = base[:-3]
    return re.sub(r"[^0-9A-Za-z\-_.一-鿿]+", "-", base).strip("-")


def cmd_status(args):
    text = read_text(ledger_path(args))
    fm, _ = split_frontmatter(text)
    lines = text.split("\n")
    print(f"slug:   {fm.get('slug')}")
    print(f"status: {fm.get('status')}")
    print(f"round:  {fm.get('round')}")
    print(f"next:   {fm.get('next')}")
    print(f"参与方: {', '.join(fm.get('participants', []))}")
    print("\n未决分歧:")
    s, e = section_bounds(lines, POINTS_HEADER)
    any_row = False
    for _, cells in table_rows(lines, s, e):
        any_row = True
        print(f"  {cells[0]}  [{cells[2]}]  已历{cells[3]}轮  — {cells[1]}")
    if not any_row:
        print("  (无)")
    cs, ce = section_bounds(lines, CONV_HEADER)
    conv = [
        l[2:]
        for l in lines[cs + 1 : ce]
        if l.startswith("- ") and CONV_PLACEHOLDER not in l
    ]
    print("\n收敛区:")
    for c in conv:
        print(f"  - {c}")
    if not conv:
        print("  (空)")


def cmd_add_point(args):
    path = ledger_path(args)
    text = read_text(path)
    fm, _ = split_frontmatter(text)
    lines = text.split("\n")
    ensure_participant(fm, args.author)
    pid = args.id if args.id and args.id != "auto" else next_point_id(lines)
    summary = sanitize_cell(args.summary)
    rnd = fm["round"]
    # 1) add table row
    s, e = section_bounds(lines, POINTS_HEADER)
    idx = last_table_index(lines, s, e)
    lines.insert(idx + 1, render_row([pid, summary, POINT_OPEN, str(rnd)]))
    # 2) add log entry under current round
    body = read_body_arg(args.body) or summary
    append_log_entry(lines, rnd, args.author, render_bullet(pid, body))
    out(replace_frontmatter("\n".join(lines), fm), args, path)
    print(f"added {pid} (round {rnd}, {args.author})")


def cmd_contest(args):
    path = ledger_path(args)
    text = read_text(path)
    fm, _ = split_frontmatter(text)
    lines = text.split("\n")
    ensure_participant(fm, args.author)
    ridx, cells = find_point(lines, args.point)
    if ridx == -1:
        sys.exit(f"point not found: {args.point}")
    if cells[2] == POINT_CONVERGED:
        sys.exit(f"{args.point} already converged; re-open explicitly instead")
    rounds = max(int(cells[3]) if cells[3].isdigit() else 1, int(fm["round"]))
    movement = args.movement.lower() in ("true", "1", "yes", "y")
    status = cells[2]
    lines[ridx] = render_row([cells[0], cells[1], status, str(rounds)])
    suffix = "" if movement else "(无新进展)"
    body = read_body_arg(args.body)
    append_log_entry(lines, fm["round"], args.author, render_bullet(args.point, body, suffix))
    out(replace_frontmatter("\n".join(lines), fm), args, path)
    note = " → 标记僵局" if status == POINT_DEADLOCK else ""
    print(f"contested {args.point} (已历{rounds}轮, movement={movement}){note}")


def cmd_converge(args):
    path = ledger_path(args)
    text = read_text(path)
    lines = text.split("\n")
    ridx, cells = find_point(lines, args.point)
    if ridx == -1:
        sys.exit(f"point not found: {args.point}")
    # 1) flip table row status
    lines[ridx] = render_row([cells[0], cells[1], POINT_CONVERGED, cells[3]])
    # 2) insert convergence bullet (replace placeholder if present)
    cs, ce = section_bounds(lines, CONV_HEADER)
    bullet = f"- [{args.marker}] {args.line.strip()}  (来自 {args.point})"
    placeholder = next(
        (i for i in range(cs + 1, ce) if CONV_PLACEHOLDER in lines[i]), -1
    )
    if placeholder != -1:
        lines[placeholder] = bullet
    else:
        last = max(
            (i for i in range(cs + 1, ce) if lines[i].startswith("- ")), default=cs
        )
        lines.insert(last + 1, bullet)
    out("\n".join(lines), args, path)
    print(f"converged {args.point} [{args.marker}]")


def recompute_status(lines):
    s, e = section_bounds(lines, POINTS_HEADER)
    statuses = [cells[2] for _, cells in table_rows(lines, s, e)]
    if not statuses:
        return STATUS_AGREED
    if any(st == POINT_OPEN for st in statuses):
        return STATUS_OPEN
    if any(st == POINT_DEADLOCK for st in statuses):
        return STATUS_DEADLOCK
    return STATUS_AGREED


def cmd_end_turn(args):
    path = ledger_path(args)
    text = read_text(path)
    fm, _ = split_frontmatter(text)
    lines = text.split("\n")
    new_status = recompute_status(lines)
    fm["status"] = new_status
    if new_status == STATUS_OPEN:
        fm["next"] = STATUS_WAITING_NEXT
        fm["round"] = int(fm["round"]) + 1
    else:
        fm["next"] = "用户" if new_status == STATUS_DEADLOCK else "—"
    new_text = replace_frontmatter("\n".join(lines), fm)
    out(new_text, args, path)
    if new_status == STATUS_OPEN:
        print(f"round → {fm['round']}; next = {fm['next']} (await user/orchestrator set-next)")
    elif new_status == STATUS_AGREED:
        print("EXIT: 已达成一致 — 全部分歧收敛。告知用户并停止更新。")
    else:
        print("EXIT: 僵局 — 存在未解的僵局分歧,交用户裁决。停止更新。")


def cmd_set_next(args):
    path = ledger_path(args)
    text = read_text(path)
    fm, _ = split_frontmatter(text)
    if fm.get("status") != STATUS_OPEN:
        sys.exit("cannot set next unless status is 进行中")
    ensure_participant(fm, args.next)
    fm["next"] = args.next.strip()
    out(replace_frontmatter(text, fm), args, path)
    print(f"next = {fm['next']}")


# -------------------------------------------------------------- core helpers
def _ns(root: str | os.PathLike[str], dir: str = DEFAULT_DIR, **kwargs):
    values = {
        "root": os.fspath(root),
        "dir": dir,
        "dry_run": False,
    }
    values.update(kwargs)
    return argparse.Namespace(**values)


def _run_command(func, args) -> CommandResult:
    buffer = io.StringIO()
    path = ledger_path(args) if hasattr(args, "slug") and getattr(args, "slug", None) else None
    if path is None and hasattr(args, "topic"):
        args.slug = args.slug or derive_slug(args.topic)
        path = ledger_path(args)
    lock_context = file_lock(path) if path and not getattr(args, "dry_run", False) else contextlib.nullcontext()
    with lock_context, contextlib.redirect_stdout(buffer):
        func(args)
    return CommandResult(message=buffer.getvalue(), path=path)


def init_ledger(
    *,
    root: str | os.PathLike[str],
    topic: str,
    initiator: str,
    slug: str | None = None,
    title: str | None = None,
    participants: list[str] | str | None = None,
    dir: str = DEFAULT_DIR,
    force: bool = False,
    dry_run: bool = False,
) -> CommandResult:
    if isinstance(participants, list):
        participant_arg = ",".join(participants)
    else:
        participant_arg = participants
    args = _ns(
        root,
        dir,
        topic=topic,
        slug=slug,
        title=title,
        participants=participant_arg,
        initiator=initiator,
        force=force,
        dry_run=dry_run,
    )
    return _run_command(cmd_init, args)


def add_point(
    *,
    root: str | os.PathLike[str],
    slug: str,
    author: str,
    summary: str,
    body: str | None = None,
    id: str = "auto",
    dir: str = DEFAULT_DIR,
    dry_run: bool = False,
) -> CommandResult:
    args = _ns(root, dir, slug=slug, author=author, summary=summary, body=body, id=id, dry_run=dry_run)
    return _run_command(cmd_add_point, args)


def contest_point(
    *,
    root: str | os.PathLike[str],
    slug: str,
    point: str,
    author: str,
    body: str | None = None,
    movement: bool | str = True,
    dir: str = DEFAULT_DIR,
    dry_run: bool = False,
) -> CommandResult:
    movement_arg = str(movement).lower() if isinstance(movement, bool) else movement
    args = _ns(root, dir, slug=slug, point=point, author=author, body=body, movement=movement_arg, dry_run=dry_run)
    return _run_command(cmd_contest, args)


def converge_point(
    *,
    root: str | os.PathLike[str],
    slug: str,
    point: str,
    marker: str,
    line: str,
    dir: str = DEFAULT_DIR,
    dry_run: bool = False,
) -> CommandResult:
    args = _ns(root, dir, slug=slug, point=point, marker=marker, line=line, dry_run=dry_run)
    return _run_command(cmd_converge, args)


def end_turn(
    *,
    root: str | os.PathLike[str],
    slug: str,
    dir: str = DEFAULT_DIR,
    dry_run: bool = False,
) -> CommandResult:
    args = _ns(root, dir, slug=slug, dry_run=dry_run)
    return _run_command(cmd_end_turn, args)


def set_next(
    *,
    root: str | os.PathLike[str],
    slug: str,
    next_agent: str,
    dir: str = DEFAULT_DIR,
    dry_run: bool = False,
) -> CommandResult:
    args = _ns(root, dir, slug=slug, next=next_agent, dry_run=dry_run)
    return _run_command(cmd_set_next, args)


def read_markdown(
    *,
    root: str | os.PathLike[str],
    slug: str,
    dir: str = DEFAULT_DIR,
) -> str:
    args = _ns(root, dir, slug=slug)
    return read_text(ledger_path(args))


def get_status(
    *,
    root: str | os.PathLike[str],
    slug: str,
    dir: str = DEFAULT_DIR,
) -> LedgerStatus:
    markdown = read_markdown(root=root, slug=slug, dir=dir)
    fm, _ = split_frontmatter(markdown)
    lines = markdown.split("\n")
    ps, pe = section_bounds(lines, POINTS_HEADER)
    open_points = [
        {"id": cells[0], "summary": cells[1], "status": cells[2], "rounds": cells[3]}
        for _, cells in table_rows(lines, ps, pe)
        if cells[2] == POINT_OPEN
    ]
    cs, ce = section_bounds(lines, CONV_HEADER)
    convergence = [
        line[2:]
        for line in lines[cs + 1 : ce]
        if line.startswith("- ") and CONV_PLACEHOLDER not in line
    ]
    return LedgerStatus(
        frontmatter=fm,
        open_points=open_points,
        convergence=convergence,
        markdown=markdown,
    )


def record_agent_turn(
    *,
    root: str | os.PathLike[str],
    slug: str,
    author: str,
    convergences: list[dict[str, Any]] | None = None,
    contests: list[dict[str, Any]] | None = None,
    new_points: list[dict[str, Any]] | None = None,
    end_turn_after: bool = False,
    dir: str = DEFAULT_DIR,
) -> CommandResult:
    messages: list[str] = []
    path: str | None = None
    lock_path = ledger_path(_ns(root, dir, slug=slug))
    with file_lock(lock_path):
        for item in convergences or []:
            result = converge_point(
                root=root,
                dir=dir,
                slug=slug,
                point=item["point"],
                marker=item.get("marker", "一致"),
                line=item["line"],
            )
            path = result.path
            messages.append(result.message)
        for item in contests or []:
            result = contest_point(
                root=root,
                dir=dir,
                slug=slug,
                point=item["point"],
                author=author,
                body=item.get("body"),
                movement=item.get("movement", True),
            )
            path = result.path
            messages.append(result.message)
        for item in new_points or []:
            result = add_point(
                root=root,
                dir=dir,
                slug=slug,
                author=author,
                summary=item["summary"],
                body=item.get("body"),
                id=item.get("id", "auto"),
            )
            path = result.path
            messages.append(result.message)
        if end_turn_after:
            result = end_turn(root=root, dir=dir, slug=slug)
            path = result.path
            messages.append(result.message)
    return CommandResult(message="".join(messages), path=path)


# --------------------------------------------------------------------- parser
def build_parser():
    p = argparse.ArgumentParser(description="discuss-ledger deterministic writer")
    p.add_argument("--root", default=os.getcwd(), help="repo root (default: cwd)")
    p.add_argument("--dir", default=DEFAULT_DIR, help="ledger dir relative to root")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init")
    i.add_argument("--topic", required=True, help="source doc path or topic text")
    i.add_argument("--slug", help="default: derived from topic basename")
    i.add_argument("--title")
    i.add_argument("--participants", help="optional comma list, e.g. CC,Codex")
    i.add_argument("--initiator", required=True, help="who speaks round 1")
    i.add_argument("--force", action="store_true")
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(func=cmd_init)

    s = sub.add_parser("status")
    s.add_argument("--slug", required=True)
    s.set_defaults(func=cmd_status)

    a = sub.add_parser("add-point")
    a.add_argument("--slug", required=True)
    a.add_argument("--author", required=True)
    a.add_argument("--summary", required=True)
    a.add_argument("--body", help="full argument; '-' reads stdin")
    a.add_argument("--id", default="auto")
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(func=cmd_add_point)

    c = sub.add_parser("contest")
    c.add_argument("--slug", required=True)
    c.add_argument("--point", required=True)
    c.add_argument("--author", required=True)
    c.add_argument("--body", help="counter-argument; '-' reads stdin")
    c.add_argument("--movement", default="true", help="true if genuinely new ground")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_contest)

    v = sub.add_parser("converge")
    v.add_argument("--slug", required=True)
    v.add_argument("--point", required=True)
    v.add_argument("--marker", required=True, help="一致 | 用户裁决 | 用户裁决·覆盖CC")
    v.add_argument("--line", required=True, help="one-line settled conclusion")
    v.add_argument("--dry-run", action="store_true")
    v.set_defaults(func=cmd_converge)

    e = sub.add_parser("end-turn")
    e.add_argument("--slug", required=True)
    e.add_argument("--dry-run", action="store_true")
    e.set_defaults(func=cmd_end_turn)

    n = sub.add_parser("set-next")
    n.add_argument("--slug", required=True)
    n.add_argument("--next", required=True, help="next party chosen by caller/user/orchestrator")
    n.add_argument("--dry-run", action="store_true")
    n.set_defaults(func=cmd_set_next)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
