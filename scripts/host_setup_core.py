"""Host-neutral machinery shared by the per-host setup audit scripts.

This module holds the inventory primitives (snapshot, diff, audit items),
link audits, and report rendering used by ``codex_setup.py`` and
``claude_setup.py``. It must stay free of host-specific CLI calls and
repository-root coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
from typing import Any

import link_skill


IGNORED_DIRS = {".git", ".pytest_cache", "__pycache__"}
IGNORED_FILES = {".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
STATUS_ORDER = ("BLOCKED", "DRIFT", "MISSING", "INSTALL-MISMATCH")


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    sha256: str
    entries: dict[str, str]


@dataclass
class AuditItem:
    kind: str
    name: str
    status: str
    expected_sha: str = "—"
    actual_sha: str = "—"
    expected_path: str = "—"
    actual_path: str = "—"
    note: str = ""
    differences: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    items: list[AuditItem]
    operational_error: bool = False

    @property
    def clean(self) -> bool:
        return not self.operational_error and all(item.status == "MATCH" for item in self.items)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_content(content: bytes) -> str:
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        canonical = content
    else:
        canonical = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256_bytes(canonical)


def is_ignored(path: Path) -> bool:
    return (
        path.name in IGNORED_DIRS
        or path.name in IGNORED_FILES
        or path.suffix.lower() in IGNORED_SUFFIXES
    )


def snapshot_tree(root: Path) -> Snapshot:
    root = Path(root)
    if not root.is_dir():
        raise SetupError(f"directory is unavailable: {root}")

    entries: dict[str, str] = {}

    def visit(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise SetupError(f"cannot read directory {directory}: {exc}") from exc
        for child in children:
            if is_ignored(child):
                continue
            relative = child.relative_to(root).as_posix()
            if link_skill.is_link(child):
                target = link_skill.link_target(child)
                target_text = str(target) if target is not None else "<unresolved>"
                entries[relative] = f"link:{sha256_bytes(target_text.encode('utf-8'))}"
                continue
            try:
                if child.is_dir():
                    visit(child)
                elif child.is_file():
                    entries[relative] = f"file:{sha256_content(child.read_bytes())}"
            except OSError as exc:
                raise SetupError(f"cannot hash {child}: {exc}") from exc

    visit(root)
    digest = hashlib.sha256()
    for relative, identity in sorted(entries.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(identity.encode("ascii"))
        digest.update(b"\n")
    return Snapshot(digest.hexdigest(), entries)


def snapshot_content(name: str, content: bytes) -> Snapshot:
    digest = sha256_content(content)
    return Snapshot(digest, {name: f"file:{digest}"})


def diff_snapshots(expected: Snapshot, actual: Snapshot) -> list[str]:
    differences: list[str] = []
    for path in sorted(set(expected.entries) | set(actual.entries)):
        wanted = expected.entries.get(path)
        found = actual.entries.get(path)
        if wanted == found:
            continue
        if wanted is None:
            differences.append(f"A {path} | actual {found}")
        elif found is None:
            differences.append(f"D {path} | expected {wanted}")
        else:
            differences.append(f"M {path} | expected {wanted} | actual {found}")
    return differences


def blocked(kind: str, name: str, note: str) -> AuditItem:
    return AuditItem(kind=kind, name=name, status="BLOCKED", note=note)


def path_is_within(path: Path, root: Path) -> bool:
    path_key = link_skill.normalize_path_key(path)
    root_key = link_skill.normalize_path_key(root)
    try:
        return os.path.commonpath([path_key, root_key]) == root_key
    except ValueError:
        return False


def stale_workbench_links(
    kind: str,
    installed_root: Path,
    source_root: Path,
    expected_names: set[str],
) -> list[AuditItem]:
    if not installed_root.is_dir():
        return []
    results: list[AuditItem] = []
    try:
        children = list(installed_root.iterdir())
    except OSError as exc:
        return [blocked(kind, installed_root.name, f"cannot enumerate {installed_root}: {exc}")]
    for child in sorted(children, key=lambda value: value.name.lower()):
        if child.name in expected_names or not link_skill.is_link(child):
            continue
        target = link_skill.link_target(child)
        if target is None or not path_is_within(target, source_root):
            continue
        results.append(
            AuditItem(
                kind=kind,
                name=child.name,
                status="INSTALL-MISMATCH",
                expected_path="removed from current workbench inventory",
                actual_path=str(child),
                note=f"stale workbench link points to {target}",
            )
        )
    return results


def audit_linked_directory(kind: str, name: str, source: Path, destination: Path) -> AuditItem:
    try:
        wanted = snapshot_tree(source)
    except SetupError as exc:
        return blocked(kind, name, str(exc))
    if not destination.exists() and not link_skill.is_link(destination):
        return AuditItem(
            kind=kind,
            name=name,
            status="MISSING",
            expected_sha=wanted.sha256,
            expected_path=str(source),
            actual_path=str(destination),
        )
    if link_skill.is_link(destination):
        target = link_skill.link_target(destination)
        if target is not None and link_skill.same_path(target, source):
            return AuditItem(
                kind=kind,
                name=name,
                status="MATCH",
                expected_sha=wanted.sha256,
                actual_sha=wanted.sha256,
                expected_path=str(source),
                actual_path=str(destination),
                note=f"linked to {target}",
            )
        return AuditItem(
            kind=kind,
            name=name,
            status="INSTALL-MISMATCH",
            expected_sha=wanted.sha256,
            expected_path=str(source),
            actual_path=str(destination),
            note=f"link points to {target or '<unresolved>'}",
        )
    if not destination.is_dir():
        return AuditItem(
            kind=kind,
            name=name,
            status="INSTALL-MISMATCH",
            expected_sha=wanted.sha256,
            expected_path=str(source),
            actual_path=str(destination),
            note="destination is not a directory link",
        )
    try:
        found = snapshot_tree(destination)
    except SetupError as exc:
        return blocked(kind, name, str(exc))
    return AuditItem(
        kind=kind,
        name=name,
        status="INSTALL-MISMATCH",
        expected_sha=wanted.sha256,
        actual_sha=found.sha256,
        expected_path=str(source),
        actual_path=str(destination),
        note="destination is a real directory; it will not follow workbench updates",
        differences=diff_snapshots(wanted, found),
    )


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_pull(data: dict[str, Any] | None) -> str:
    if data is None:
        return "未运行。"
    lines = [
        f"- Pull 前：`{data['before']}`",
        f"- Pull 后：`{data['after']}`",
        f"- 统计：{data['stat']}",
        "",
        "### Commits",
        "",
    ]
    lines.extend(
        f"- `{commit}` {subject}" for commit, subject in data["commits"]
    )
    if not data["commits"]:
        lines.append("- 无新增 commit")
    for group, changes in data["groups"].items():
        if not changes:
            continue
        lines.extend(["", f"### {group}", ""])
        lines.extend(f"- `{escape(change)}`" for change in changes)
    return "\n".join(lines)


def render_audit(result: AuditResult | None) -> str:
    if result is None:
        return "未运行。"
    sections: list[str] = []
    for status in STATUS_ORDER:
        items = [item for item in result.items if item.status == status]
        if not items:
            continue
        sections.extend(
            [
                f"### {status} ({len(items)})",
                "",
                "| 类型 | 名称 | 安装位置 |",
                "|---|---|---|",
            ]
        )
        for item in items:
            sections.append(
                f"| {escape(item.kind)} | `{escape(item.name)}` | `{escape(item.actual_path)}` |"
            )
        sections.append("")
    return "\n".join(sections).rstrip() or "未发现差异。"


def render_workspace(dirty: list[str]) -> str:
    if not dirty:
        return "工作树 clean。"
    return "工作树存在以下未提交路径；它们未混入 pull commit 增量：\n\n" + "\n".join(
        f"- `{escape(line)}`" for line in dirty
    )


def render_actions(actions: list[str]) -> str:
    if not actions:
        return "未执行 apply。"
    return "\n".join(f"- {line}" for line in actions)


def render_template(template_path: Path, values: dict[str, str]) -> str:
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"cannot read report template {template_path}: {exc}") from exc
    report = template
    for key, value in values.items():
        report = report.replace(f"{{{{{key}}}}}", value)
    if "{{" in report or "}}" in report:
        raise SetupError("report template contains an unresolved placeholder")
    return report.rstrip() + "\n"
