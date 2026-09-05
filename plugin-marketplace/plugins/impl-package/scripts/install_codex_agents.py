"""Install Impl-Package review profiles into Codex's agent-role directory."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import tempfile


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PLUGIN_ROOT / "agents"
AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
FRONTMATTER_FIELD_RE = re.compile(r"^(name|description):(?:\s+(.*))?$")
MANAGED_MARKER = "# managed-by = agent-workbench:impl-package"
CODEX_EXECUTION_PROFILES = {
    "review-track-code": ("gpt-6-astra", "high"),
    "review-track-safety": ("gpt-6-astra", "medium"),
    "review-track-spec": ("gpt-6-astra", "medium"),
    "review-track-standards": ("gpt-6-astra", "medium"),
}


@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    developer_instructions: str
    source: Path


class InstallConflictError(RuntimeError):
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths
        joined = ", ".join(str(path) for path in paths)
        super().__init__(f"refusing to overwrite existing Codex agent files: {joined}")


class UnsafePathError(RuntimeError):
    pass


def _parse_frontmatter(lines: list[str], path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    folded_description: list[str] | None = None
    for line in lines:
        match = FRONTMATTER_FIELD_RE.match(line.rstrip("\r\n"))
        if match:
            key, raw_value = match.groups()
            value = (raw_value or "").strip()
            if key == "description" and value in {">", "|"}:
                folded_description = []
                continue
            folded_description = None
            if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
                try:
                    value = str(ast.literal_eval(value))
                except (SyntaxError, ValueError):
                    pass
            values[key] = value
            continue
        if folded_description is not None and line[:1].isspace():
            folded_description.append(line.strip())
            values["description"] = " ".join(folded_description).strip()
            continue
        folded_description = None

    if "name" not in values or "description" not in values:
        raise ValueError(f"agent profile frontmatter must define name and description: {path}")
    return values


def _read_agent_markdown(path: Path) -> AgentProfile:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"agent profile is missing YAML frontmatter: {path}")

    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"agent profile has an unclosed YAML frontmatter block: {path}") from exc

    frontmatter = _parse_frontmatter(lines[1:end], path)
    name = frontmatter["name"].strip()
    description = frontmatter["description"].strip()
    instructions = "".join(lines[end + 1 :]).strip()
    if not name or not AGENT_NAME_RE.fullmatch(name):
        raise ValueError(f"agent profile has an invalid name: {path}")
    if not description:
        raise ValueError(f"agent profile has no description: {path}")
    if not instructions:
        raise ValueError(f"agent profile has no developer instructions: {path}")
    if "'''" in instructions:
        raise ValueError(f"agent profile contains unsupported triple apostrophes: {path}")

    return AgentProfile(
        name=name,
        description=description,
        developer_instructions=instructions,
        source=path,
    )


def load_profiles(source_dir: Path = SOURCE_DIR) -> list[AgentProfile]:
    paths = sorted(path for path in source_dir.glob("*.md") if path.is_file())
    if not paths:
        raise ValueError(f"no Markdown agent profiles found in {source_dir}")

    profiles = [_read_agent_markdown(path) for path in paths]
    names = [profile.name for profile in profiles]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate agent profile names in {source_dir}")
    if set(names) != set(CODEX_EXECUTION_PROFILES):
        raise ValueError("Codex execution profiles must match the Impl-Package review agents")
    return profiles


def render_codex_role(profile: AgentProfile) -> str:
    model, reasoning_effort = CODEX_EXECUTION_PROFILES[profile.name]
    return (
        f"{MANAGED_MARKER}\n"
        f"name = {json.dumps(profile.name, ensure_ascii=False)}\n"
        f"description = {json.dumps(profile.description, ensure_ascii=False)}\n"
        f"model = {json.dumps(model)}\n"
        f"model_reasoning_effort = {json.dumps(reasoning_effort)}\n"
        "developer_instructions = '''\n"
        f"{profile.developer_instructions}\n"
        "'''\n"
    )


def _render_legacy_codex_role(profile: AgentProfile) -> str:
    return (
        f"name = {json.dumps(profile.name, ensure_ascii=False)}\n"
        f"description = {json.dumps(profile.description, ensure_ascii=False)}\n"
        "developer_instructions = '''\n"
        f"{profile.developer_instructions}\n"
        "'''\n"
    )


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt" or not path.exists():
        return False
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _find_reparse_ancestor(path: Path) -> Path | None:
    current = path
    while True:
        if _is_reparse_point(current):
            return current
        if current.parent == current:
            return None
        current = current.parent


def _write_role_atomically(destination: Path, content: str) -> None:
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            dir=destination.parent,
            text=True,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        if _is_reparse_point(destination):
            raise UnsafePathError(f"refusing to write through symlink or reparse point: {destination}")
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def default_codex_agents_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    home = Path(codex_home).expanduser().absolute() if codex_home else Path.home() / ".codex"
    return home / "agents"


def install_profiles(
    target_dir: Path,
    *,
    source_dir: Path = SOURCE_DIR,
    force: bool = False,
) -> dict[str, list[str] | str]:
    profiles = load_profiles(source_dir)
    rendered = {f"{profile.name}.toml": render_codex_role(profile) for profile in profiles}
    legacy_rendered = {f"{profile.name}.toml": _render_legacy_codex_role(profile) for profile in profiles}
    destinations = {name: target_dir / name for name in rendered}

    unsafe_target = _find_reparse_ancestor(target_dir)
    if unsafe_target is not None:
        raise UnsafePathError(f"refusing to write below symlink or reparse point: {unsafe_target}")

    conflicts: list[Path] = []
    unowned: list[Path] = []
    for name, destination in destinations.items():
        if _is_reparse_point(destination):
            raise UnsafePathError(f"refusing to write through symlink or reparse point: {destination}")
        if not destination.exists():
            continue
        if not destination.is_file():
            conflicts.append(destination)
            continue
        existing = destination.read_text(encoding="utf-8")
        if existing != rendered[name]:
            conflicts.append(destination)
            if existing != legacy_rendered[name] and not existing.startswith(f"{MANAGED_MARKER}\n"):
                unowned.append(destination)
    if conflicts and not force:
        raise InstallConflictError(conflicts)
    if any(not path.is_file() for path in conflicts):
        raise InstallConflictError(conflicts)
    if unowned:
        raise InstallConflictError(unowned)

    target_dir.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    for name, content in rendered.items():
        destination = destinations[name]
        if destination.is_file() and destination.read_text(encoding="utf-8") == content:
            skipped.append(name)
            continue
        was_present = destination.exists()
        _write_role_atomically(destination, content)
        (updated if was_present else installed).append(name)

    return {
        "target": str(target_dir),
        "installed": installed,
        "updated": updated,
        "skipped": skipped,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--global", dest="global_install", action="store_true")
    scope.add_argument("--target", type=Path, help="explicit Codex agents directory")
    parser.add_argument("--source", type=Path, default=SOURCE_DIR)
    parser.add_argument("--force", action="store_true", help="replace changed files owned by this package")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target_dir = default_codex_agents_dir() if args.global_install else args.target.expanduser().absolute()
    try:
        report = install_profiles(
            target_dir,
            source_dir=args.source.expanduser().resolve(),
            force=args.force,
        )
    except (InstallConflictError, OSError, UnsafePathError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({"status": "ok", **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
