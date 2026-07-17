"""Generate a draft parent-stage adapter from an approved Impl-Package DAG."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PrepareError(RuntimeError):
    """A source package cannot safely be adapted automatically."""


@dataclass(frozen=True)
class PreparedStage:
    id: str
    cohort: str
    ticket: str
    ticket_path: str
    parent_role: str
    objective: str
    depends_on: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    skills: tuple[str, ...]
    sandbox: str
    sensitive_originals: str
    path_ownership_inferred: bool


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repository_root), *args], capture_output=True, text=True)
    if completed.returncode:
        raise PrepareError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _source(repository_root: Path, source_ref: str, package_path: str, path: str) -> str:
    return _git(repository_root, "show", f"{source_ref}:{package_path}/{path}")


def _source_blob(repository_root: Path, source_ref: str, package_path: str, path: str) -> str:
    return _git(repository_root, "rev-parse", f"{source_ref}:{package_path}/{path}")


def _relative(value: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise PrepareError(f"unsafe repository-relative path: {value!r}")
    return path.as_posix().rstrip("/")


def _binding_snapshot(repository_root: Path, source_ref: str, package_path: str) -> dict[str, Any]:
    sidecar = json.loads(_source(repository_root, source_ref, package_path, ".impl-package/revision-bindings.json"))
    current = sidecar.get("current", {})
    expected = {
        "design.md": current.get("design", {}).get("revision"),
        "spec.md": current.get("spec", {}).get("revision"),
        "plan.md": current.get("attempt", {}).get("revision"),
    }
    if not all(isinstance(value, str) and value for value in expected.values()):
        raise PrepareError("revision binding has no current D/S/P selection")
    checks: dict[str, bool] = {}
    for artifact, revision in expected.items():
        entry = next((item for item in sidecar.get("bindings", []) if item.get("artifact") == artifact and item.get("revision") == revision), None)
        checks[artifact] = bool(entry and entry.get("blob") == _source_blob(repository_root, source_ref, package_path, artifact))
    if not all(checks.values()):
        raise PrepareError("source package D/S/P blobs do not match its current revision binding")
    attempt_id = current.get("attempt", {}).get("id")
    if not isinstance(attempt_id, str) or not attempt_id:
        raise PrepareError("revision binding has no current attempt id")
    return {"attempt_id": attempt_id, "revisions": {"design": expected["design.md"], "spec": expected["spec.md"], "plan": expected["plan.md"]}, "checks": checks}


def _task_blocks(dag: str) -> list[tuple[str, str, str]]:
    matches = list(re.finditer(r"^### (T\d+)：([^\n]+)\n", dag, re.MULTILINE))
    if not matches:
        raise PrepareError("DAG has no '### Tn：title' task contracts")
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(dag)
        blocks.append((match.group(1), match.group(2).strip(), dag[match.end() : end]))
    return blocks


def _line_value(block: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}：([^\n]+)$", block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _ticket_paths(repository_root: Path, source_ref: str, package_path: str) -> dict[str, str]:
    listing = _git(repository_root, "ls-tree", "-r", "--name-only", source_ref, f"{package_path}/tickets")
    paths: dict[str, str] = {}
    for absolute_path in listing.splitlines():
        prefix = package_path + "/"
        if not absolute_path.startswith(prefix):
            continue
        relative = absolute_path[len(prefix) :]
        text = _git(repository_root, "show", f"{source_ref}:{absolute_path}")
        match = re.search(r"\*\*Ticket ID：\*\*\s*([^\n]+)", text)
        if match:
            paths[match.group(1).strip()] = relative
    return paths


def _ticket_id(title: str, block: str, ticket_ids: tuple[str, ...]) -> str:
    """Bind a task to a package ticket without encoding a domain-specific ID format."""
    if "主线集成" in title or re.search(r"\breview\b", title, re.IGNORECASE):
        return "integration-gate"
    return next((ticket_id for ticket_id in ticket_ids if ticket_id in block), "integration-gate")


def _cohorts(dag: str) -> dict[str, str]:
    section = re.search(r"^## Parallel Cohorts\n(?P<body>.*?)(?=^## |\Z)", dag, re.MULTILINE | re.DOTALL)
    if not section:
        return {}
    result: dict[str, str] = {}
    for match in re.finditer(r"^- Cohort (\d+)：([^\n]+)$", section.group("body"), re.MULTILINE):
        for task_id in re.findall(r"T\d+", match.group(2)):
            # Later cohort prose can mention a task as a concurrent neighbour;
            # the first declaration is its owning cohort.
            result.setdefault(task_id, f"C{match.group(1)}")
    return result


def _owned_paths(block: str) -> tuple[tuple[str, ...], bool]:
    primary = _line_value(block, "Primary owned files/modules")
    candidates = re.findall(r"`([^`]+)`", primary)
    paths: list[str] = []
    for candidate in candidates:
        candidate = candidate.strip().rstrip("/")
        if "/" not in candidate or candidate.startswith("http"):
            continue
        try:
            normalized = _relative(candidate)
        except PrepareError:
            continue
        if normalized not in paths:
            paths.append(normalized)
    return tuple(paths), bool(paths)


def _objective(title: str, block: str) -> str:
    done_when = _line_value(block, "Done when")
    if done_when:
        return f"{title}。完成标准：{done_when}"
    return title


def _role(task_id: str, title: str) -> str:
    if "外部验收" in title or "Test Mandant" in title:
        return "manual_acceptance_handoff"
    if "集成" in title or re.search(r"\breview\b", title, re.IGNORECASE):
        return "impl_package_integration_reviewer"
    return f"impl_package_{task_id.lower()}_parent"


def _skills(title: str) -> tuple[str, ...]:
    base = ["impl-package", "impl-package/dev-with-track"]
    if "集成" in title or re.search(r"\breview\b", title, re.IGNORECASE):
        base.extend(["impl-package/reviews/code-review", "impl-package/reviews/module-review", "impl-package/reviews/safety-review"])
    return tuple(base)


def _sensitive_mode(title: str, block: str) -> str:
    text = title + "\n" + block
    return "on_demand" if "OCR" in text and ("原件" in text or "真实" in text) else "forbidden"


def prepare_adapter(repository_root: Path, source_ref: str, package_path: str, parent_profile: str, timeout_seconds: int = 1800, max_parallel_parents: int = 2) -> tuple[str, dict[str, Any]]:
    repository_root = repository_root.resolve()
    package_path = _relative(package_path)
    source_commit = _git(repository_root, "rev-parse", f"{source_ref}^{{commit}}")
    binding = _binding_snapshot(repository_root, source_commit, package_path)
    dag = _source(repository_root, source_commit, package_path, "dag.md")
    tickets = _ticket_paths(repository_root, source_commit, package_path)
    ticket_ids = tuple(tickets)
    cohorts = _cohorts(dag)
    stages: list[PreparedStage] = []
    for task_id, title, block in _task_blocks(dag):
        ticket = _ticket_id(title, block, ticket_ids)
        paths, inferred = _owned_paths(block)
        if not paths:
            # Drafts must stay fail-closed: this path permits only package-local
            # evidence until an owner supplies code ownership explicitly.
            paths = (package_path,)
        sandbox = "read_only" if _role(task_id, title) == "manual_acceptance_handoff" else "workspace_write"
        stages.append(
            PreparedStage(
                id=task_id,
                cohort="external" if sandbox == "read_only" else cohorts.get(task_id, "unassigned"),
                ticket=ticket,
                ticket_path=tickets.get(ticket, ""),
                parent_role=_role(task_id, title),
                objective=_objective(title, block),
                depends_on=tuple(re.findall(r"T\d+", _line_value(block, "Depends on"))),
                allowed_paths=paths,
                skills=_skills(title),
                sandbox=sandbox,
                sensitive_originals=_sensitive_mode(title, block),
                path_ownership_inferred=inferred,
            )
        )
    manifest = render_manifest(repository_root, source_commit, package_path, binding["attempt_id"], parent_profile, timeout_seconds, max_parallel_parents, stages)
    readiness = {
        "status": "draft_requires_review",
        "source_commit": source_commit,
        "package_path": package_path,
        "attempt_id": binding["attempt_id"],
        "revisions": binding["revisions"],
        "binding_checks": binding["checks"],
        "stage_count": len(stages),
        "initial_ready_stages": [stage.id for stage in stages if not stage.depends_on],
        "path_ownership_review": [stage.id for stage in stages if not stage.path_ownership_inferred],
        "verifier_review": [stage.id for stage in stages],
        "sensitive_on_demand": [stage.id for stage in stages if stage.sensitive_originals == "on_demand"],
        "manual_acceptance": [stage.id for stage in stages if stage.parent_role == "manual_acceptance_handoff"],
    }
    return manifest, readiness


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_list(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def render_manifest(repository_root: Path, source_commit: str, package_path: str, attempt_id: str, parent_profile: str, timeout_seconds: int, max_parallel_parents: int, stages: list[PreparedStage]) -> str:
    lines = [
        "# Generated by prepare-codex-harness-package.py. Review all TODO comments before execution.",
        "schema_version = 1",
        "",
        "[package]",
        f"repository_root = {_toml_string(repository_root.as_posix())}",
        f"source_ref = {_toml_string(source_commit)}",
        f"path = {_toml_string(package_path)}",
        f"attempt_id = {_toml_string(attempt_id)}",
        "",
        "[runtime]",
        f"parent_profile = {_toml_string(parent_profile)}",
        f"timeout_seconds = {timeout_seconds}",
        f"max_parallel_parents = {max_parallel_parents}",
        "network_access = false",
    ]
    for stage in stages:
        lines.extend(
            [
                "",
                "[[stage]]",
                f"id = {_toml_string(stage.id)}",
                f"cohort = {_toml_string(stage.cohort)}",
                f"ticket = {_toml_string(stage.ticket)}",
                f"ticket_path = {_toml_string(stage.ticket_path)}",
                f"parent_role = {_toml_string(stage.parent_role)}",
                f"objective = {_toml_string(stage.objective)}",
                f"depends_on = {_toml_list(stage.depends_on)}",
                f"allowed_paths = {_toml_list(stage.allowed_paths)}",
                f"skills = {_toml_list(stage.skills)}",
                "# TODO(owner): replace with independent, safe-to-rerun verifier commands before execution.",
                "verification_commands = []",
                f"sandbox = {_toml_string(stage.sandbox)}",
                f"sensitive_originals = {_toml_string(stage.sensitive_originals)}",
            ]
        )
    return "\n".join(lines) + "\n"
