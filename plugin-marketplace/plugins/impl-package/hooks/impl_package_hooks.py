"""Codex lifecycle hooks for Impl-Package.

This module only protects machine-owned state and supplies a read-only resume
capsule. Business state, acceptance, and Gate decisions remain owned by the
Impl-Package skills and semantic CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SITUATION_CLI = PLUGIN_ROOT / "scripts" / "situation.py"
STATE_REL = PurePosixPath(".impl-package/state.json")
BINDING_VERSION = 1
CAPSULE_VERSION = 1
SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PATCH_HEADER_RE = re.compile(
    r"^\*\*\* (?:Add File|Update File|Delete File|Move to):\s*(.+?)\s*$",
    re.MULTILINE,
)


class HookError(RuntimeError):
    """A bounded hook input, binding, or subprocess failure."""


def _json_dump(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _warning(message: str) -> dict[str, str]:
    return {"systemMessage": f"Impl-Package Hook warning: {message}"}


def _session_id(explicit: str | None = None) -> str:
    value = explicit or os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")
    if not value or not SESSION_RE.fullmatch(value):
        raise HookError("a valid Codex session id is required")
    return value


def _git(repo_or_child: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo_or_child,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise HookError(detail)
    return completed.stdout.strip()


def _repo_root(cwd: Path) -> Path:
    return Path(_git(cwd, "rev-parse", "--show-toplevel")).resolve()


def _binding_path(repo_root: Path, session_id: str) -> Path:
    relative = _git(
        repo_root,
        "rev-parse",
        "--git-path",
        f"codex/impl-package-hooks/{session_id}.json",
    )
    candidate = Path(relative)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    candidate = candidate.resolve()
    git_dir = Path(_git(repo_root, "rev-parse", "--absolute-git-dir")).resolve()
    if not candidate.is_relative_to(git_dir):
        raise HookError("binding path escaped the current Git worktree metadata")
    return candidate


def _is_fixture_path(path: PurePosixPath) -> bool:
    parts = tuple(part.casefold() for part in path.parts)
    return any(parts[index : index + 2] == ("tests", "fixtures") for index in range(len(parts) - 1))


def _normalized_patch_path(raw: str) -> PurePosixPath:
    normalized = raw.strip().strip('"').replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return PurePosixPath(normalized)


def _protected_patch_paths(command: str) -> list[str]:
    blocked: list[str] = []
    for match in PATCH_HEADER_RE.finditer(command):
        path = _normalized_patch_path(match.group(1))
        folded = tuple(part.casefold() for part in path.parts)
        if len(folded) >= 2 and folded[-2:] == (".impl-package", "state.json") and not _is_fixture_path(path):
            blocked.append(path.as_posix())
    return sorted(set(blocked))


def _read_event() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HookError(f"invalid hook event JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise HookError("hook event must be a JSON object")
    return payload


def _activate(package_arg: str, explicit_session: str | None) -> int:
    session_id = _session_id(explicit_session)
    repo_root = _repo_root(Path.cwd())
    requested = Path(package_arg)
    package = (requested if requested.is_absolute() else repo_root / requested).resolve()
    if not package.is_relative_to(repo_root):
        raise HookError("package must stay inside the current Git worktree")
    relative = PurePosixPath(package.relative_to(repo_root).as_posix())
    if _is_fixture_path(relative):
        raise HookError("test fixtures cannot be activated as a live Impl-Package")
    state_path = package / STATE_REL.as_posix()
    if not state_path.is_file() or not state_path.resolve().is_relative_to(repo_root):
        raise HookError("package is missing .impl-package/state.json")

    binding_path = _binding_path(repo_root, session_id)
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": BINDING_VERSION,
        "session_id": session_id,
        "repo_root": str(repo_root),
        "package": relative.as_posix(),
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=binding_path.parent,
            prefix=f".{binding_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        os.replace(temporary_path, binding_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    _json_dump({"status": "activated", "session_id": session_id, "package": relative.as_posix()})
    return 0


def _deactivate(explicit_session: str | None) -> int:
    session_id = _session_id(explicit_session)
    repo_root = _repo_root(Path.cwd())
    binding_path = _binding_path(repo_root, session_id)
    existed = binding_path.is_file()
    if existed:
        binding_path.unlink()
    _json_dump({"status": "deactivated" if existed else "not-bound", "session_id": session_id})
    return 0


def _pre_tool_use() -> int:
    try:
        event = _read_event()
        if event.get("hook_event_name") != "PreToolUse" or event.get("tool_name") != "apply_patch":
            return 0
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
            raise HookError("PreToolUse apply_patch event is missing tool_input.command")
        blocked = _protected_patch_paths(tool_input["command"])
        if not blocked:
            return 0
        _json_dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Impl-Package machine state must be changed through "
                        "scripts/impl_package_state.py, not apply_patch. Blocked: "
                        + ", ".join(blocked)
                    ),
                }
            }
        )
        return 0
    except HookError as exc:
        _json_dump(_warning(str(exc)))
        return 0


def _load_binding(repo_root: Path, session_id: str) -> tuple[dict[str, Any] | None, str | None]:
    binding_path = _binding_path(repo_root, session_id)
    if not binding_path.is_file():
        return None, None
    try:
        payload = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"could not read the active package binding: {exc}"
    expected = {"version", "session_id", "repo_root", "package"}
    if not isinstance(payload, dict) or set(payload) != expected:
        return None, "the active package binding has an invalid shape"
    if payload.get("version") != BINDING_VERSION or payload.get("session_id") != session_id:
        return None, None
    if not isinstance(payload.get("repo_root"), str) or Path(payload["repo_root"]).resolve() != repo_root:
        return None, None
    package_value = payload.get("package")
    if not isinstance(package_value, str):
        return None, "the active package binding has an invalid package path"
    package_rel = PurePosixPath(package_value)
    if package_rel.is_absolute() or ".." in package_rel.parts or _is_fixture_path(package_rel):
        return None, "the active package binding points outside the supported package scope"
    package = (repo_root / Path(*package_rel.parts)).resolve()
    state_path = package / STATE_REL.as_posix()
    if (
        not package.is_relative_to(repo_root)
        or not state_path.is_file()
        or not state_path.resolve().is_relative_to(repo_root)
    ):
        return None, "the activated package no longer exists in this worktree"
    return {**payload, "package_path": package}, None


def _render_situation(package: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(SITUATION_CLI),
                "render",
                "--package",
                str(package),
                "--no-write-credential",
                "--json",
            ],
            cwd=package,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HookError(f"situation render could not run: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "situation render failed"
        raise HookError(detail[:500])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HookError("situation render returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HookError("situation render returned a non-object result")
    return payload


def _action_ids(candidate: Any) -> list[str]:
    if not isinstance(candidate, dict):
        return []
    values = candidate.get("action_ids")
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if isinstance(value, str) and value]


def _resume_capsule(binding: dict[str, Any], rendered: dict[str, Any]) -> str:
    selected = rendered.get("selected") if isinstance(rendered.get("selected"), dict) else None
    parallel = rendered.get("parallel_matches") if isinstance(rendered.get("parallel_matches"), list) else []
    sources = rendered.get("sources") if isinstance(rendered.get("sources"), dict) else {}
    state = sources.get("state") if isinstance(sources.get("state"), dict) else {}
    gate = sources.get("gate") if isinstance(sources.get("gate"), dict) else {}
    selected_slug = selected.get("slug") if selected else None
    selected_actions = _action_ids(selected)
    parallel_items = []
    for item in parallel:
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
            continue
        actions = _action_ids(item)
        suffix = f"[{','.join(actions)}]" if actions else ""
        parallel_items.append(f"{item['slug']}{suffix}")

    lines = [
        f"Impl-Package Resume Capsule v{CAPSULE_VERSION}",
        f"package: {binding['package']}",
        f"attempt: {rendered.get('attempt') or '?'}",
        f"head: {rendered.get('head') or '?'}",
        f"state-valid: {str(bool(state.get('valid'))).lower()}",
        f"gate-verdict: {gate.get('verdict') or 'none'}",
        f"preview-digest: {rendered.get('digest') or '?'}",
        f"selected: {selected_slug or 'none'}",
        f"actions: {','.join(selected_actions) if selected_actions else 'none'}",
        f"parallel: {';'.join(parallel_items) if parallel_items else 'none'}",
        f"warnings: {len(rendered.get('warnings', [])) if isinstance(rendered.get('warnings'), list) else 0}",
        f"undetermined: {len(rendered.get('undetermined', [])) if isinstance(rendered.get('undetermined'), list) else 0}",
        "This capsule is navigation context only; it is not Evidence, Acceptance, Gate, or closure.",
        "Before dispatch, rerun situation.py render without --no-write-credential; consume successful CLI updates without full restore.",
    ]
    return "\n".join(lines)


def _session_start() -> int:
    try:
        event = _read_event()
        if event.get("hook_event_name") != "SessionStart":
            return 0
        if event.get("source") not in {"startup", "resume", "compact"}:
            return 0
        event_session = event.get("session_id")
        if not isinstance(event_session, str) or not SESSION_RE.fullmatch(event_session):
            raise HookError("SessionStart event is missing a valid session_id")
        session_id = event_session
        cwd_value = event.get("cwd")
        if not isinstance(cwd_value, str) or not cwd_value:
            raise HookError("SessionStart event is missing cwd")
        repo_root = _repo_root(Path(cwd_value))
        binding, warning = _load_binding(repo_root, session_id)
        if warning:
            _json_dump(_warning(warning))
            return 0
        if binding is None:
            return 0
        rendered = _render_situation(binding["package_path"])
        _json_dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": _resume_capsule(binding, rendered),
                }
            }
        )
        return 0
    except HookError as exc:
        _json_dump(_warning(str(exc)))
        return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex lifecycle hooks for Impl-Package")
    subparsers = parser.add_subparsers(dest="command", required=True)
    activate = subparsers.add_parser("activate", help="bind one package to the current Codex session")
    activate.add_argument("--package", required=True)
    activate.add_argument("--session-id")
    deactivate = subparsers.add_parser("deactivate", help="remove the current session binding")
    deactivate.add_argument("--session-id")
    subparsers.add_parser("pre-tool-use", help="run the PreToolUse state guard")
    subparsers.add_parser("session-start", help="run the SessionStart resume hook")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "activate":
            return _activate(args.package, args.session_id)
        if args.command == "deactivate":
            return _deactivate(args.session_id)
        if args.command == "pre-tool-use":
            return _pre_tool_use()
        if args.command == "session-start":
            return _session_start()
    except HookError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
