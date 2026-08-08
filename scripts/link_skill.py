#!/usr/bin/env python3
"""Thin per-skill linker for agent hosts.

Creates a directory junction (Windows) or symlink (Unix/macOS) from
workbench skills/<name> into ~/.{host}/skills/<name>.

Never overwrites a conflicting destination. If the host skills root is a
whole-tree reparse/symlink to this workbench's skills/, remove that link
and create a real directory before linking.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = WORKBENCH_ROOT / "skills"

HOST_NAMES = ("claude", "codex", "grok")

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_CONFLICT = 2

IS_WINDOWS = os.name == "nt"


def abspath_nofollow(path: Path) -> Path:
    """Absolute path without following a final-component junction/symlink."""
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    # os.path.abspath does not follow the last component's reparse on Windows
    # the same way Path.resolve() does for an existing junction.
    return Path(os.path.abspath(os.path.normpath(str(expanded))))


def normalize_path_key(path: Path) -> str:
    """Stable path comparison across \\?\\ prefixes, case (Win), and separators."""
    text = str(path)
    if text.startswith("\\\\?\\"):
        text = text[4:]
    elif text.startswith("//?/"):
        text = text[4:]
    # realpath follows links — avoid for link identity. Use abspath + normcase.
    return os.path.normcase(os.path.abspath(os.path.normpath(text)))


def same_path(a: Path, b: Path) -> bool:
    return normalize_path_key(a) == normalize_path_key(b)


def host_skills_dir(host: str, *, home: Optional[Path] = None) -> Path:
    host = host.lower()
    if host not in HOST_NAMES:
        raise ValueError(f"unknown host: {host}")
    base = home if home is not None else Path.home()
    if host == "grok":
        grok_home = os.environ.get("GROK_HOME")
        if grok_home:
            return abspath_nofollow(Path(grok_home)) / "skills"
    return abspath_nofollow(base / f".{host}" / "skills")


def is_link(path: Path) -> bool:
    """True for symlink (Unix/macOS/Win) or directory junction (Windows)."""
    try:
        if path.is_symlink():
            return True
    except OSError:
        pass
    if not IS_WINDOWS:
        return False
    # Windows junctions are reparse points but often not pathlib symlinks.
    try:
        st = path.lstat()
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & reparse)


def link_target(path: Path) -> Optional[Path]:
    """Best-effort absolute target of a junction/symlink."""
    if not is_link(path):
        return None
    try:
        target = path.readlink()
        if not target.is_absolute():
            target = path.parent / target
        return abspath_nofollow(target)
    except OSError:
        pass
    if IS_WINDOWS:
        try:
            # Last resort: resolve follows the reparse point.
            return abspath_nofollow(path.resolve())
        except OSError:
            return None
    return None


def remove_link(path: Path) -> None:
    """Remove a junction/symlink without deleting the target tree."""
    if IS_WINDOWS:
        # rmdir removes a directory junction; does not delete target contents.
        result = subprocess.run(
            ["cmd", "/c", "rmdir", str(path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Directory symlink may need unlink semantics.
            try:
                path.unlink()
                return
            except OSError as exc:
                detail = (result.stderr or result.stdout or str(exc)).strip()
                raise OSError(f"failed to remove link {path}: {detail}") from exc
        return
    # Unix/macOS: unlink the symlink node only.
    path.unlink()


def create_dir_link(source: Path, destination: Path) -> None:
    """Create host link: junction on Windows, directory symlink on Unix/macOS."""
    source = Path(os.path.abspath(str(source.resolve())))
    destination = abspath_nofollow(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or is_link(destination):
        raise FileExistsError(str(destination))

    if IS_WINDOWS:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(destination), str(source)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise OSError(
                f"mklink /J failed: "
                f"{(result.stderr or result.stdout or str(result.returncode)).strip()}"
            )
        return

    # Relative targets break if the host cwd differs; always absolute on Unix.
    os.symlink(str(source), str(destination), target_is_directory=True)


def resolve_skill_source(skill: str) -> Path:
    raw = skill.strip().replace("\\", "/").lstrip("/")
    if not raw or ".." in Path(raw).parts:
        raise ValueError(f"invalid skill path: {skill}")
    root = SKILLS_ROOT.resolve()
    source = (root / raw).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"skill escapes skills root: {skill}") from exc
    if not source.is_dir():
        raise FileNotFoundError(f"skill directory not found: {source}")
    return source


def list_all_skill_sources() -> List[Path]:
    if not SKILLS_ROOT.is_dir():
        return []
    entries: List[Path] = []
    for p in SKILLS_ROOT.iterdir():
        if p.name.startswith("."):
            continue
        # Follow into real dirs; skip if entry itself is a stray file.
        try:
            if p.is_dir():
                entries.append(p.resolve() if not is_link(p) else abspath_nofollow(p))
        except OSError:
            continue
    return sorted(entries, key=lambda p: p.name.lower())


def ensure_skills_root(
    skills_dir: Path,
    *,
    workbench_skills: Path,
) -> Dict[str, Any]:
    """Ensure skills_dir is a real directory; migrate whole-tree workbench link if needed."""
    workbench_skills = abspath_nofollow(Path(os.path.abspath(str(workbench_skills.resolve()))))
    skills_dir = abspath_nofollow(skills_dir)
    result: Dict[str, Any] = {
        "path": str(skills_dir),
        "action": "ok",
        "message": None,
        "platform": "windows" if IS_WINDOWS else "unix",
    }

    if not skills_dir.exists() and not is_link(skills_dir):
        skills_dir.mkdir(parents=True, exist_ok=True)
        result["action"] = "created"
        return result

    if is_link(skills_dir):
        target = link_target(skills_dir)
        if target is not None and same_path(target, workbench_skills):
            remove_link(skills_dir)
            if not skills_dir.exists() and not is_link(skills_dir):
                skills_dir.mkdir(parents=True, exist_ok=True)
            result["action"] = "migrated_whole_tree"
            result["message"] = f"removed whole-tree link to {workbench_skills}"
            return result
        result["action"] = "error"
        result["message"] = (
            f"{skills_dir} is a link to {target or 'unknown'}, "
            f"not this workbench skills root ({workbench_skills}); refusing to modify"
        )
        return result

    if not skills_dir.is_dir():
        result["action"] = "error"
        result["message"] = f"{skills_dir} exists and is not a directory"
        return result

    return result


def link_one(source: Path, destination: Path) -> Dict[str, Any]:
    source = Path(os.path.abspath(str(source.resolve())))
    destination = abspath_nofollow(destination)
    item: Dict[str, Any] = {
        "src": str(source),
        "dst": str(destination),
        "action": "linked",
        "message": None,
        "link_kind": "junction" if IS_WINDOWS else "symlink",
    }
    if is_link(destination):
        target = link_target(destination)
        if target is not None and same_path(target, source):
            item["action"] = "skipped"
            item["message"] = "already linked"
            return item
        item["action"] = "conflict"
        item["message"] = f"destination is a link to {target or 'unknown'}"
        return item

    if destination.exists():
        item["action"] = "conflict"
        item["message"] = "destination already exists"
        return item

    try:
        create_dir_link(source, destination)
    except FileExistsError:
        item["action"] = "conflict"
        item["message"] = "destination already exists"
    except OSError as exc:
        item["action"] = "error"
        item["message"] = str(exc)
    return item


def link_skills_to_root(
    sources: Sequence[Path],
    skills_dir: Path,
    *,
    workbench_skills: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    root_info = ensure_skills_root(skills_dir, workbench_skills=workbench_skills)
    if root_info["action"] == "error":
        return root_info, []

    # Use migrated/normalized path for destinations.
    root_path = Path(root_info["path"])
    results: List[Dict[str, Any]] = []
    for source in sources:
        dest = root_path / source.name
        results.append(link_one(source, dest))
    return root_info, results


def unlink_one(source: Path, destination: Path) -> Dict[str, Any]:
    """Remove a host skill link only; never deletes the workbench source tree."""
    source = Path(os.path.abspath(str(source.resolve())))
    destination = abspath_nofollow(destination)
    item: Dict[str, Any] = {
        "src": str(source),
        "dst": str(destination),
        "action": "unlinked",
        "message": None,
        "link_kind": "junction" if IS_WINDOWS else "symlink",
    }

    if not destination.exists() and not is_link(destination):
        item["action"] = "skipped"
        item["message"] = "not installed"
        return item

    if not is_link(destination):
        item["action"] = "conflict"
        item["message"] = (
            "destination is a real directory/file, not a link; "
            "refusing to delete (workbench source is never removed)"
        )
        return item

    target = link_target(destination)
    if target is not None and not same_path(target, source):
        item["action"] = "conflict"
        item["message"] = (
            f"destination is a link to {target}, not workbench source {source}; "
            "refusing to remove"
        )
        return item

    try:
        remove_link(destination)
    except OSError as exc:
        item["action"] = "error"
        item["message"] = str(exc)
        return item

    # Source must still exist; this path never deletes workbench content.
    item["message"] = "host link removed; workbench source kept"
    return item


def unlink_skills_from_root(
    sources: Sequence[Path],
    skills_dir: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    skills_dir = abspath_nofollow(skills_dir)
    root_info: Dict[str, Any] = {
        "path": str(skills_dir),
        "action": "ok",
        "message": None,
        "platform": "windows" if IS_WINDOWS else "unix",
    }
    if is_link(skills_dir):
        root_info["action"] = "error"
        root_info["message"] = (
            f"{skills_dir} is still a whole-tree link; "
            "migrate to a real skills directory before unlinking individual skills"
        )
        return root_info, []
    if not skills_dir.exists():
        root_info["action"] = "ok"
        root_info["message"] = "skills dir missing; nothing to unlink"
        return root_info, [
            {
                "src": str(s),
                "dst": str(skills_dir / s.name),
                "action": "skipped",
                "message": "not installed",
                "link_kind": "junction" if IS_WINDOWS else "symlink",
            }
            for s in sources
        ]
    if not skills_dir.is_dir():
        root_info["action"] = "error"
        root_info["message"] = f"{skills_dir} is not a directory"
        return root_info, []

    results = [unlink_one(source, skills_dir / source.name) for source in sources]
    return root_info, results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Link or unlink workbench skill directories in agent host skills/ "
            "(Windows junction, Unix/macOS symlink). Unlink never deletes workbench sources."
        ),
    )
    p.add_argument(
        "skill",
        nargs="?",
        help="Skill path under workbench skills/ (e.g. call-grok). Omit with --all or --migrate-only.",
    )
    p.add_argument(
        "--host",
        nargs="+",
        metavar="HOST",
        help=f"Host name(s): {', '.join(HOST_NAMES)}",
    )
    p.add_argument(
        "--to",
        metavar="DIR",
        help="Explicit host skills directory (instead of --host)",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Link/unlink every top-level directory under workbench skills/",
    )
    p.add_argument(
        "--unlink",
        "--uninstall",
        action="store_true",
        dest="unlink",
        help=(
            "Remove host skill link(s) only (junction/symlink). "
            "Never deletes workbench skills/ content."
        ),
    )
    p.add_argument(
        "--migrate-only",
        action="store_true",
        help="Only migrate whole-tree skills root to a real directory; do not link skills",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON summary only (still the same final object; suppresses human lines)",
    )
    p.add_argument(
        "--home",
        help=argparse.SUPPRESS,  # test override for Path.home()
    )
    return p


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    home = abspath_nofollow(Path(args.home)) if args.home else None

    if not args.host and not args.to:
        eprint("error: provide --host HOST [...] and/or --to DIR")
        return EXIT_USAGE
    if args.skill and args.all:
        eprint("error: pass either SKILL or --all, not both")
        return EXIT_USAGE
    if not args.skill and not args.all and not args.migrate_only:
        eprint("error: provide SKILL, --all, or --migrate-only")
        return EXIT_USAGE
    if args.migrate_only and (args.skill or args.all or args.unlink):
        eprint("error: --migrate-only cannot be combined with SKILL, --all, or --unlink")
        return EXIT_USAGE
    if args.unlink and not args.skill and not args.all:
        eprint("error: --unlink requires SKILL or --all")
        return EXIT_USAGE

    targets: List[Tuple[str, Path]] = []
    if args.to:
        targets.append(("custom", abspath_nofollow(Path(args.to))))
    if args.host:
        for host in args.host:
            try:
                targets.append((host.lower(), host_skills_dir(host, home=home)))
            except ValueError as exc:
                eprint(f"error: {exc}")
                return EXIT_USAGE

    sources: List[Path] = []
    if not args.migrate_only:
        if args.all:
            sources = list_all_skill_sources()
            if not sources:
                eprint(f"error: no skill directories under {SKILLS_ROOT}")
                return EXIT_USAGE
        else:
            try:
                sources = [resolve_skill_source(args.skill)]
            except (ValueError, FileNotFoundError) as exc:
                eprint(f"error: {exc}")
                return EXIT_USAGE

    summary: Dict[str, Any] = {
        "ok": True,
        "op": "unlink" if args.unlink else ("migrate" if args.migrate_only else "link"),
        "platform": "windows" if IS_WINDOWS else "unix",
        "link_kind": "junction" if IS_WINDOWS else "symlink",
        "workbench": str(WORKBENCH_ROOT),
        "skills_root": str(SKILLS_ROOT),
        "hosts": [],
    }
    had_conflict = False
    had_error = False

    for label, skills_dir in targets:
        host_entry: Dict[str, Any] = {
            "host": label,
            "skills_dir": str(skills_dir),
            "root": None,
            "items": [],
        }
        if args.migrate_only:
            root_info = ensure_skills_root(skills_dir, workbench_skills=SKILLS_ROOT)
            host_entry["root"] = root_info
            if root_info["action"] == "error":
                had_error = True
                summary["ok"] = False
                if not args.json:
                    eprint(f"[{label}] ERROR {root_info['message']}")
            elif not args.json:
                print(f"[{label}] root {root_info['action']}: {root_info['path']}")
        elif args.unlink:
            root_info, items = unlink_skills_from_root(sources, skills_dir)
            host_entry["root"] = root_info
            host_entry["items"] = items
            if root_info["action"] == "error":
                had_error = True
                summary["ok"] = False
                if not args.json:
                    eprint(f"[{label}] ERROR {root_info['message']}")
            else:
                for item in items:
                    tag = item["action"].upper()
                    if item["action"] == "conflict":
                        had_conflict = True
                        summary["ok"] = False
                    elif item["action"] == "error":
                        had_error = True
                        summary["ok"] = False
                    if not args.json:
                        msg = f"  [{tag}] {Path(item['dst']).name}"
                        if item.get("message"):
                            msg += f" ({item['message']})"
                        print(msg)
        else:
            root_info, items = link_skills_to_root(
                sources, skills_dir, workbench_skills=SKILLS_ROOT
            )
            host_entry["root"] = root_info
            host_entry["items"] = items
            if root_info["action"] == "error":
                had_error = True
                summary["ok"] = False
                if not args.json:
                    eprint(f"[{label}] ERROR {root_info['message']}")
            else:
                if not args.json and root_info["action"] in {"created", "migrated_whole_tree"}:
                    print(f"[{label}] root {root_info['action']}: {root_info['path']}")
                for item in items:
                    tag = item["action"].upper()
                    if item["action"] == "conflict":
                        had_conflict = True
                        summary["ok"] = False
                    elif item["action"] == "error":
                        had_error = True
                        summary["ok"] = False
                    if not args.json:
                        msg = f"  [{tag}] {Path(item['dst']).name} -> {item['src']}"
                        if item.get("message"):
                            msg += f" ({item['message']})"
                        print(msg)
        summary["hosts"].append(host_entry)

    print(json.dumps(summary, ensure_ascii=False))

    if had_error:
        return EXIT_USAGE
    if had_conflict:
        return EXIT_CONFLICT
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
