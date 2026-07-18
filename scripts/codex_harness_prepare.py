"""Generate a draft parent-stage adapter from an approved Impl-Package DAG."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from codex_harness_impl_package_compat import attempt_id as canonical_attempt_id
    from codex_harness_impl_package_compat import composition_flags, matches_artifact_pattern, task_blocks as canonical_task_blocks, ticket_id as canonical_ticket_id
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_impl_package_compat import attempt_id as canonical_attempt_id
    from scripts.codex_harness_impl_package_compat import composition_flags, matches_artifact_pattern, task_blocks as canonical_task_blocks, ticket_id as canonical_ticket_id


class PrepareError(RuntimeError):
    """A source package cannot safely be adapted automatically."""


IMPL_PACKAGE_CONTRACT_VERSION = "3.2"


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


def _canonical_source_validation(repository_root: Path, source_commit: str, package_path: str) -> dict[str, Any]:
    state_cli = Path(__file__).resolve().parents[1] / "skills" / "impl-package" / "scripts" / "impl_package_state.py"
    worktree_root = Path(tempfile.mkdtemp(prefix="codex-harness-prepare-source-"))
    try:
        add = subprocess.run(["git", "-C", str(repository_root), "worktree", "add", "--detach", str(worktree_root), source_commit], capture_output=True, text=True)
        if add.returncode:
            raise PrepareError(add.stderr.strip() or "cannot create source validation worktree")
        package = worktree_root / package_path
        validate = subprocess.run([sys.executable, str(state_cli), "--package", str(package), "validate", "--committed"], capture_output=True, text=True)
        if validate.returncode:
            raise PrepareError("canonical Impl-Package validation failed: " + (validate.stderr.strip() or validate.stdout.strip()))
        resolve = subprocess.run([sys.executable, str(state_cli), "--package", str(package), "resolve-gate"], capture_output=True, text=True)
        if resolve.returncode:
            raise PrepareError("canonical gate resolution failed: " + (resolve.stderr.strip() or resolve.stdout.strip()))
        gate = json.loads(resolve.stdout)
        if gate.get("kind") == "mismatch" or gate.get("needsManualGateReview"):
            raise PrepareError("source package gate requires manual review")
        if gate.get("appliesToCurrentRevision") and gate.get("gateResolution") in {"pass", "fail", "defer"}:
            raise PrepareError("current package attempt is frozen by a terminal gate; create a post-gate patch attempt")
        return {"validation": json.loads(validate.stdout), "gate": gate}
    except json.JSONDecodeError as exc:
        raise PrepareError("canonical source validation returned invalid JSON") from exc
    finally:
        subprocess.run(["git", "-C", str(repository_root), "worktree", "remove", "--force", str(worktree_root)], capture_output=True, text=True)


def _relative(value: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise PrepareError(f"unsafe repository-relative path: {value!r}")
    return path.as_posix().rstrip("/")


def _binding_snapshot(repository_root: Path, source_ref: str, package_path: str) -> dict[str, Any]:
    sidecar = json.loads(_source(repository_root, source_ref, package_path, ".impl-package/revision-bindings.json"))
    if sidecar.get("contractVersion") != IMPL_PACKAGE_CONTRACT_VERSION:
        raise PrepareError(f"source package contractVersion must be {IMPL_PACKAGE_CONTRACT_VERSION}")
    current = sidecar.get("current", {})
    expected: list[tuple[str, str, str]] = []
    for key in ("decision", "spec"):
        selection = current.get(key)
        if selection:
            artifact = selection.get("artifact")
            revision = selection.get("revision")
            if not isinstance(artifact, str) or not isinstance(revision, str) or not artifact or not revision:
                raise PrepareError(f"revision binding has invalid current {key} selection")
            expected.append((key, artifact, revision))
    attempt_selection = current.get("attempt")
    if not isinstance(attempt_selection, dict):
        raise PrepareError("revision binding has no current attempt selection")
    plan_artifact = attempt_selection.get("plan")
    plan_revision = attempt_selection.get("revision")
    attempt_id = attempt_selection.get("id")
    if not all(isinstance(value, str) and value for value in (plan_artifact, plan_revision, attempt_id)):
        raise PrepareError("revision binding has invalid current attempt selection")
    expected.append(("plan", plan_artifact, plan_revision))
    checks: dict[str, bool] = {}
    for kind, artifact, revision in expected:
        entry = next(
            (
                item
                for item in sidecar.get("bindings", [])
                if item.get("artifact") == artifact
                and item.get("revision") == revision
                and (kind != "plan" or item.get("attempt") == attempt_id)
            ),
            None,
        )
        checks[f"{kind}:{artifact}"] = bool(entry and entry.get("blob") == _source_blob(repository_root, source_ref, package_path, artifact))
    if not all(checks.values()):
        raise PrepareError("source package D/S/P blobs do not match its current revision binding")
    return {"attempt_id": attempt_id, "plan_artifact": plan_artifact, "revisions": {"decision": current.get("decision", {}).get("revision", "N/A") if current.get("decision") else "N/A", "spec": current.get("spec", {}).get("revision", "N/A"), "plan": plan_revision}, "checks": checks}


def _task_blocks(dag: str) -> list[tuple[str, str, str]]:
    try:
        return canonical_task_blocks(dag)
    except (RuntimeError, ValueError) as error:
        raise PrepareError(str(error)) from error


def _line_value(block: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}[:：]([^\n]+)$", block, re.MULTILINE)
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
        identifier = canonical_ticket_id(text)
        if identifier:
            paths[identifier] = relative
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
    for match in re.finditer(r"^- Cohort (\d+)[:：]([^\n]+)$", section.group("body"), re.MULTILINE):
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
    canonical = _canonical_source_validation(repository_root, source_commit, package_path)
    plan_text = _source(repository_root, source_commit, package_path, binding["plan_artifact"])
    try:
        tickets_earned, dag_earned = composition_flags(plan_text)
    except (RuntimeError, ValueError) as error:
        raise PrepareError(str(error)) from error
    if not dag_earned:
        raise PrepareError("current package has a legal no-DAG Composition; automatic parent-stage preparation is not applicable")
    dag_candidates = [
        name[len(package_path) + 1 :]
        for name in _git(repository_root, "ls-tree", "-r", "--name-only", source_commit, package_path).splitlines()
        if name.startswith(package_path + "/") and matches_artifact_pattern(name[len(package_path) + 1 :], "dagArtifactPatterns")
    ]
    matching_dags = [
        name
        for name in dag_candidates
        if canonical_attempt_id(_source(repository_root, source_commit, package_path, name)) == binding["attempt_id"]
    ]
    if len(matching_dags) != 1:
        raise PrepareError("current plan earns DAG but no unique attempt DAG artifact is present")
    dag = _source(repository_root, source_commit, package_path, matching_dags[0])
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
        "canonical_validation": canonical,
        "composition": {"tickets": tickets_earned, "dag": dag_earned},
        "dag_artifact": matching_dags[0],
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
