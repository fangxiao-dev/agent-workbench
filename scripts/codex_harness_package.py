"""Manifest-driven parent-stage runner for Impl-Package execution.

This module deliberately schedules *parent* stages only. A parent may use
native Codex subagents and Skills as it sees fit; neither becomes a Harness
acceptance dependency.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from codex_harness_cli import JsonRpcSession, app_server_command
    from codex_harness_controller import artifacts_valid, load_parent_profile, parse_parent_result, walk_root_agent_messages
    from codex_harness_impl_package_compat import attempt_id as canonical_attempt_id
    from codex_harness_impl_package_compat import composition_flags, matches_artifact_pattern
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession, app_server_command
    from scripts.codex_harness_controller import artifacts_valid, load_parent_profile, parse_parent_result, walk_root_agent_messages
    from scripts.codex_harness_impl_package_compat import attempt_id as canonical_attempt_id
    from scripts.codex_harness_impl_package_compat import composition_flags, matches_artifact_pattern

try:
    from codex_harness_policy import PolicyError, load_runtime_policy
    from codex_harness_runtime import ResourceLedger
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_policy import PolicyError, load_runtime_policy
    from scripts.codex_harness_runtime import ResourceLedger


REQUIRED_PACKAGE_FILES = ("spec.md", ".impl-package/revision-bindings.json", ".impl-package/runtime-state.json")
IMPL_PACKAGE_CONTRACT_VERSION = "3.2"
TERMINAL_GATE_VERDICTS = {"pass", "fail", "defer"}
VALID_SENSITIVE_MODES = {"forbidden", "on_demand"}
VALID_SANDBOXES = {"read_only", "workspace_write"}


@dataclass(frozen=True)
class Stage:
    id: str
    cohort: str
    ticket: str
    ticket_path: str
    parent_role: str
    objective: str
    depends_on: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    skills: tuple[str, ...]
    verification_commands: tuple[str, ...]
    sandbox: str
    sensitive_originals: str


@dataclass(frozen=True)
class Manifest:
    path: Path
    repository_root: Path
    source_ref: str
    package_path: str
    attempt_id: str
    parent_profile: Path
    timeout_seconds: int
    max_parallel_parents: int
    network_access: bool
    stages: tuple[Stage, ...]


class ManifestError(RuntimeError):
    """The package manifest is invalid or unsafe to dispatch."""


def _canonical_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _relative_path(value: str, field: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ManifestError(f"{field} must be a non-empty repository-relative path: {value!r}")
    return path.as_posix().rstrip("/")


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ManifestError(f"{field} must be an array of non-empty strings")
    return tuple(value)


def load_manifest(path: Path, repository_root_override: Path | None = None) -> Manifest:
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    if data.get("schema_version") != 1:
        raise ManifestError("schema_version must be 1")
    package = data.get("package")
    runtime = data.get("runtime")
    if not isinstance(package, dict) or not isinstance(runtime, dict):
        raise ManifestError("[package] and [runtime] are required")
    repository_value = package.get("repository_root")
    if repository_root_override is None and (not isinstance(repository_value, str) or not repository_value.strip()):
        raise ManifestError("package.repository_root is required")
    repository_root = repository_root_override or Path(repository_value)
    source_ref = package.get("source_ref")
    package_path = package.get("path")
    attempt_id = package.get("attempt_id")
    if not all(isinstance(value, str) and value.strip() for value in (source_ref, package_path, attempt_id)):
        raise ManifestError("package.source_ref, package.path, and package.attempt_id are required")
    parent_profile_value = runtime.get("parent_profile")
    if not isinstance(parent_profile_value, str) or not parent_profile_value.strip():
        raise ManifestError("runtime.parent_profile is required")
    parent_profile = Path(parent_profile_value)
    if not parent_profile.is_absolute():
        parent_profile = (path.parent / parent_profile).resolve()
    timeout_seconds = runtime.get("timeout_seconds", 900)
    max_parallel_parents = runtime.get("max_parallel_parents", 1)
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ManifestError("runtime.timeout_seconds must be a positive integer")
    if not isinstance(max_parallel_parents, int) or max_parallel_parents <= 0:
        raise ManifestError("runtime.max_parallel_parents must be a positive integer")
    network_access = runtime.get("network_access", False)
    if not isinstance(network_access, bool):
        raise ManifestError("runtime.network_access must be a boolean")
    raw_stages = data.get("stage")
    if not isinstance(raw_stages, list) or not raw_stages:
        raise ManifestError("at least one [[stage]] is required")
    stages: list[Stage] = []
    for raw in raw_stages:
        if not isinstance(raw, dict):
            raise ManifestError("each [[stage]] must be a table")
        required = ("id", "cohort", "ticket", "parent_role", "objective")
        if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required):
            raise ManifestError(f"stage is missing one of {', '.join(required)}")
        sandbox = raw.get("sandbox", "workspace_write")
        sensitive_originals = raw.get("sensitive_originals", "forbidden")
        if sandbox not in VALID_SANDBOXES:
            raise ManifestError(f"stage {raw['id']} has unsupported sandbox {sandbox!r}")
        if sensitive_originals not in VALID_SENSITIVE_MODES:
            raise ManifestError(f"stage {raw['id']} has unsupported sensitive_originals mode {sensitive_originals!r}")
        allowed_paths = tuple(_relative_path(value, f"stage {raw['id']} allowed_paths") for value in _string_list(raw.get("allowed_paths"), f"stage {raw['id']} allowed_paths"))
        ticket_path_value = raw.get("ticket_path", "")
        if not isinstance(ticket_path_value, str):
            raise ManifestError(f"stage {raw['id']} ticket_path must be a string")
        stages.append(
            Stage(
                id=raw["id"],
                cohort=raw["cohort"],
                ticket=raw["ticket"],
                ticket_path=_relative_path(ticket_path_value, f"stage {raw['id']} ticket_path") if ticket_path_value else "",
                parent_role=raw["parent_role"],
                objective=raw["objective"],
                depends_on=_string_list(raw.get("depends_on", []), f"stage {raw['id']} depends_on"),
                allowed_paths=allowed_paths,
                skills=_string_list(raw.get("skills", []), f"stage {raw['id']} skills"),
                verification_commands=_string_list(raw.get("verification_commands", []), f"stage {raw['id']} verification_commands"),
                sandbox=sandbox,
                sensitive_originals=sensitive_originals,
            )
        )
    return Manifest(
        path=path.resolve(),
        repository_root=repository_root.resolve(),
        source_ref=source_ref,
        package_path=_relative_path(package_path, "package.path"),
        attempt_id=attempt_id,
        parent_profile=parent_profile,
        timeout_seconds=timeout_seconds,
        max_parallel_parents=max_parallel_parents,
        network_access=network_access,
        stages=tuple(stages),
    )


def _git(repository_root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(["git", "-C", str(repository_root), *args], capture_output=True, text=True)
    if check and completed.returncode:
        raise ManifestError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _git_succeeds(repository_root: Path, *args: str) -> bool:
    return subprocess.run(["git", "-C", str(repository_root), *args], capture_output=True, text=True).returncode == 0


def _source_text(manifest: Manifest, relative_path: str) -> str:
    return _git(manifest.repository_root, "show", f"{manifest.source_ref}:{manifest.package_path}/{relative_path}")


def _source_blob(manifest: Manifest, relative_path: str) -> str:
    return _git(manifest.repository_root, "rev-parse", f"{manifest.source_ref}:{manifest.package_path}/{relative_path}")


def _canonical_state_cli() -> Path:
    return Path(__file__).resolve().parents[1] / "skills" / "impl-package" / "scripts" / "impl_package_state.py"


def _canonical_source_validation(manifest: Manifest, source_commit: str) -> dict[str, Any]:
    """Validate a committed source snapshot in a detached temporary worktree."""
    worktree_root = Path(tempfile.mkdtemp(prefix="codex-harness-package-source-"))
    try:
        completed = subprocess.run(
            ["git", "-C", str(manifest.repository_root), "worktree", "add", "--detach", str(worktree_root), source_commit],
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise ManifestError(completed.stderr.strip() or "cannot create source validation worktree")
        package = worktree_root / manifest.package_path
        validate = subprocess.run(
            [sys.executable, str(_canonical_state_cli()), "--package", str(package), "validate", "--committed"],
            capture_output=True,
            text=True,
        )
        if validate.returncode:
            raise ManifestError("canonical Impl-Package validation failed: " + (validate.stderr.strip() or validate.stdout.strip()))
        resolve = subprocess.run(
            [sys.executable, str(_canonical_state_cli()), "--package", str(package), "resolve-gate"],
            capture_output=True,
            text=True,
        )
        if resolve.returncode:
            raise ManifestError("canonical gate resolution failed: " + (resolve.stderr.strip() or resolve.stdout.strip()))
        try:
            gate = json.loads(resolve.stdout)
        except json.JSONDecodeError as exc:
            raise ManifestError("canonical gate resolver returned invalid JSON") from exc
        if gate.get("kind") == "mismatch" or gate.get("needsManualGateReview"):
            raise ManifestError("source package gate requires manual review")
        if gate.get("appliesToCurrentRevision") and gate.get("gateResolution") in TERMINAL_GATE_VERDICTS:
            raise ManifestError("current package attempt is frozen by a terminal gate; create a post-gate patch attempt")
        try:
            validate_payload = json.loads(validate.stdout)
        except json.JSONDecodeError as exc:
            raise ManifestError("canonical validate returned non-JSON output") from exc
        return {"validate": validate_payload, "gate": gate}
    finally:
        subprocess.run(
            ["git", "-C", str(manifest.repository_root), "worktree", "remove", "--force", str(worktree_root)],
            capture_output=True,
            text=True,
        )


def _status_paths(repository_root: Path) -> list[str]:
    paths: list[str] = []
    completed = subprocess.run(["git", "-C", str(repository_root), "status", "--porcelain=v1"], check=True, capture_output=True, text=True)
    for line in completed.stdout.splitlines():
        if len(line) >= 4:
            paths.append(line[3:].replace("\\", "/"))
    return sorted(paths)


def validate_manifest(manifest: Manifest) -> dict[str, Any]:
    errors: list[str] = []
    if not (manifest.repository_root / ".git").exists() and not _git(manifest.repository_root, "rev-parse", "--is-inside-work-tree", check=False) == "true":
        errors.append("repository_root is not a Git worktree")
    source_commit = _git(manifest.repository_root, "rev-parse", f"{manifest.source_ref}^{{commit}}", check=False)
    if not source_commit:
        errors.append(f"source_ref cannot be resolved: {manifest.source_ref}")
    if not manifest.parent_profile.is_file():
        errors.append(f"parent profile is missing: {manifest.parent_profile}")
    stage_ids = [stage.id for stage in manifest.stages]
    if len(set(stage_ids)) != len(stage_ids):
        errors.append("stage ids must be unique")
    known = set(stage_ids)
    for stage in manifest.stages:
        unknown = set(stage.depends_on) - known
        if unknown:
            errors.append(f"stage {stage.id} has unknown dependencies: {', '.join(sorted(unknown))}")
        if stage.id in stage.depends_on:
            errors.append(f"stage {stage.id} cannot depend on itself")
    if not errors:
        unresolved = {stage.id: set(stage.depends_on) for stage in manifest.stages}
        resolved: set[str] = set()
        while True:
            ready = {stage_id for stage_id, deps in unresolved.items() if deps <= resolved}
            ready -= resolved
            if not ready:
                break
            resolved |= ready
        if resolved != known:
            errors.append("stage dependency graph contains a cycle")
    binding_checks: dict[str, bool] = {}
    revisions: dict[str, str] = {}
    canonical_state: dict[str, Any] = {}
    if not errors:
        try:
            for filename in REQUIRED_PACKAGE_FILES:
                _source_text(manifest, filename)
            for stage in manifest.stages:
                if stage.ticket_path:
                    _source_text(manifest, stage.ticket_path)
            bindings = json.loads(_source_text(manifest, ".impl-package/revision-bindings.json"))
            if bindings.get("contractVersion") != IMPL_PACKAGE_CONTRACT_VERSION:
                errors.append(f"package contractVersion must be {IMPL_PACKAGE_CONTRACT_VERSION}")
            current = bindings.get("current", {})
            attempt_selection = current.get("attempt", {})
            plan_artifact = attempt_selection.get("plan")
            if not isinstance(plan_artifact, str) or not plan_artifact:
                raise ManifestError("revision binding has no current attempt plan artifact")
            plan_text = _source_text(manifest, plan_artifact)
            try:
                tickets_earned, dag_earned = composition_flags(plan_text)
            except (RuntimeError, ValueError) as error:
                raise ManifestError(str(error)) from error
            if current.get("attempt", {}).get("id") != manifest.attempt_id:
                errors.append("manifest attempt_id does not match revision binding")
            revisions = {
                "decision": str(current.get("decision", {}).get("revision", "N/A")) if current.get("decision") else "N/A",
                "spec": str(current.get("spec", {}).get("revision", "")),
                "plan": str(current.get("attempt", {}).get("revision", "")),
            }
            expected: list[tuple[str, str, str]] = [
                ("spec", "spec.md", revisions["spec"]),
                ("plan", plan_artifact, revisions["plan"]),
            ]
            if current.get("decision"):
                decision_artifact = current["decision"].get("artifact", "decision.md")
                expected.insert(0, ("decision", decision_artifact, revisions["decision"]))
            for kind, filename, revision in expected:
                entry = next(
                    (
                        item
                        for item in bindings.get("bindings", [])
                        if item.get("artifact") == filename
                        and item.get("revision") == revision
                        and (kind != "plan" or item.get("attempt") == manifest.attempt_id)
                    ),
                    None,
                )
                actual_blob = _source_blob(manifest, filename)
                binding_checks[f"{kind}:{filename}"] = bool(entry and entry.get("blob") == actual_blob)
            if not all(binding_checks.values()):
                errors.append("D/S/P source blobs do not match the current revision binding")
            if dag_earned:
                candidates = [
                    name for name in _git(manifest.repository_root, "ls-tree", "-r", "--name-only", manifest.source_ref, manifest.package_path).splitlines()
                    if name.startswith(manifest.package_path + "/")
                    and matches_artifact_pattern(name[len(manifest.package_path) + 1 :], "dagArtifactPatterns")
                ]
                matching = [
                    name
                    for name in candidates
                    if canonical_attempt_id(_source_text(manifest, name[len(manifest.package_path) + 1 :])) == manifest.attempt_id
                ]
                if len(matching) != 1:
                    errors.append("current plan earns DAG but source package has no unique attempt DAG artifact")
        except (ManifestError, json.JSONDecodeError) as error:
            errors.append(f"package binding validation failed: {error}")
        if not errors:
            try:
                canonical_state = _canonical_source_validation(manifest, source_commit)
            except ManifestError as error:
                errors.append(str(error))
    return {
        "valid": not errors,
        "errors": errors,
        "repository_root": str(manifest.repository_root),
        "source_ref": manifest.source_ref,
        "source_commit": source_commit,
        "package_path": manifest.package_path,
        "attempt_id": manifest.attempt_id,
        "revisions": revisions,
        "binding_checks": binding_checks,
        "canonical_state": canonical_state,
        "repository_status": _status_paths(manifest.repository_root) if not errors else [],
    }


def ready_stages(manifest: Manifest, completed: set[str]) -> list[Stage]:
    known = {stage.id for stage in manifest.stages}
    unknown = completed - known
    if unknown:
        raise ManifestError(f"completed contains unknown stages: {', '.join(sorted(unknown))}")
    return [stage for stage in manifest.stages if stage.id not in completed and set(stage.depends_on) <= completed]


def build_work_package(manifest: Manifest, stage: Stage, sensitive_roots: tuple[str, ...] = ()) -> dict[str, Any]:
    if sensitive_roots and stage.sensitive_originals != "on_demand":
        raise ManifestError(f"stage {stage.id} does not allow sensitive originals")
    normalized_sensitive = tuple(_relative_path(path, "sensitive root") for path in sensitive_roots)
    package = {
        "schema_version": "codex-harness.work-package.v1",
        "package": {"path": manifest.package_path, "source_ref": manifest.source_ref, "attempt_id": manifest.attempt_id},
        "stage": {
            "id": stage.id,
            "cohort": stage.cohort,
            "ticket": stage.ticket,
            "ticket_path": stage.ticket_path,
            "parent_role": stage.parent_role,
            "objective": stage.objective,
            "depends_on": list(stage.depends_on),
            "allowed_paths": list(stage.allowed_paths),
            "skills": list(stage.skills),
            "verification_commands": list(stage.verification_commands),
        },
        "boundary": {
            "sandbox": stage.sandbox,
            "network_access": manifest.network_access,
            "sensitive_originals": {"mode": stage.sensitive_originals, "roots": list(normalized_sensitive)},
            "child_acceptance": "excluded",
            "external_side_effects": "forbidden unless the work package explicitly says otherwise",
        },
    }
    package["sha256"] = _canonical_hash(package)
    return package


def stage_prompt(run_id: str, work_package: dict[str, Any]) -> str:
    boundary = work_package["boundary"]
    stage = work_package["stage"]
    sensitive = boundary["sensitive_originals"]
    sensitive_instruction = "Sensitive originals are forbidden for this stage."
    if sensitive["roots"]:
        sensitive_instruction = (
            "You may read sensitive originals only from these declared repository-relative roots: "
            + ", ".join(sensitive["roots"])
            + ". Do not copy their full content, identifiers, or payloads into logs, artifacts, prompts, commits, or the Parent Result; report only permitted hashes, sample IDs, and bounded conclusions."
        )
    return (
        "You are the parent execution agent for one bounded Impl-Package stage. "
        "You own the execution method and may use installed Skills when relevant, including the declared Impl-Package Skills. "
        "You may decide whether and how to use native subagents; child roles, topology, activity, and results are internal and are not Harness acceptance evidence.\n\n"
        f"Run ID: {run_id}\nWork package SHA-256: {work_package['sha256']}\n"
        f"Package: {work_package['package']['path']} at {work_package['package']['source_ref']}\n"
        f"Stage: {stage['id']} ({stage['ticket']}), parent role: {stage['parent_role']}\n"
        f"Objective: {stage['objective']}\n"
        f"Ticket material: {work_package['package']['path']}/{stage['ticket_path'] or 'not separately published; use the current plan and any earned DAG artifact'}\n"
        f"Allowed paths: {', '.join(stage['allowed_paths'])}\n"
        f"Relevant Skills allowed on demand: {', '.join(stage['skills']) or 'none declared'}\n"
        f"Sandbox: {boundary['sandbox']}; network access: {boundary['network_access']}.\n"
        f"{sensitive_instruction}\n\n"
        "First read the pinned package spec.md, the current attempt plan, optional decision/DAG/ticket material, and the declared ticket material before acting. Do not assume an optional artifact exists. Do not modify files outside Allowed paths. Do not perform external side effects. Do not claim a verification command passed unless you ran it. "
        "Return only one JSON object, with no Markdown fence or surrounding prose, in this exact shape: "
        f'{{"schema_version":"codex-harness.parent-result.v0","run_id":"{run_id}","stage":"{stage["id"]}","status":"succeeded","summary":"bounded conclusion","artifacts":[{{"path":"repo-relative/path","purpose":"what it proves"}}],"verification":[{{"command":"exact command or inspection","exit_code":0,"claim":"bounded claim"}}],"findings":[],"owner_decisions":[],"retry_hint":"none","boundary_violations":[],"work_package_sha256":"{work_package["sha256"]}","comparison_point":"git commit or HEAD before this stage","changed_paths":[]}}. '
        "Allowed status values are exactly succeeded, failed, needs_owner, or interrupted; use succeeded, never completed. artifacts must be objects, never strings. verification must use integer exit_code, never result/evidence fields. status must be needs_owner when a required human approval, sensitive-root declaration, or external DATEV acceptance is missing."
    )


def _changed_paths(repository_root: Path) -> list[str]:
    paths = set(_git(repository_root, "diff", "--name-only").splitlines())
    paths.update(_status_paths(repository_root))
    return sorted(path.replace("\\", "/") for path in paths if path)


def _paths_allowed(paths: list[str], allowed_paths: tuple[str, ...]) -> bool:
    return all(any(path == allowed or path.startswith(allowed + "/") for allowed in allowed_paths) for path in paths)


def _artifacts_outside_sensitive_roots(parent_result: dict[str, Any] | None, sensitive_roots: tuple[str, ...]) -> bool:
    if parent_result is None:
        return False
    normalized = tuple(Path(root).as_posix().rstrip("/") for root in sensitive_roots)
    for artifact in parent_result.get("artifacts", []):
        path = artifact.get("path", "") if isinstance(artifact, dict) else ""
        if any(path == root or path.startswith(root + "/") for root in normalized):
            return False
    return True


def _run_verifiers(worktree: Path, commands: tuple[str, ...]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=worktree,
            capture_output=True,
            text=True,
        )
        results.append({"command": command, "exit_code": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]})
    return results


def execute_stage(manifest: Manifest, stage: Stage, worktree: Path, timeout_seconds: int, sensitive_roots: tuple[str, ...] = ()) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    if not validation["valid"]:
        raise ManifestError("manifest is not executable: " + "; ".join(validation["errors"]))
    if not worktree.is_dir() or _git(worktree, "rev-parse", "--is-inside-work-tree", check=False) != "true":
        raise ManifestError("worktree must be an existing Git worktree")
    if not _git_succeeds(worktree, "merge-base", "--is-ancestor", validation["source_commit"], "HEAD"):
        raise ManifestError("worktree does not descend from the manifest source commit")
    if sensitive_roots and stage.sensitive_originals != "on_demand":
        raise ManifestError("sensitive roots require a stage with sensitive_originals='on_demand'")
    policy_root = Path(__file__).resolve().parents[1]
    try:
        policy_bundle = load_runtime_policy(policy_root)
    except PolicyError as error:
        raise ManifestError(f"runtime policy validation failed: {error}") from error
    work_package = build_work_package(manifest, stage, sensitive_roots)
    profile = load_parent_profile(manifest.parent_profile)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + stage.id.lower() + "-" + uuid.uuid4().hex[:8]
    # Runner-owned evidence must not create an untracked mutation in the target
    # worktree; target artifacts are accepted only when the stage owns that path.
    artifact_dir = Path(__file__).resolve().parents[1] / ".codex" / "harness-runs" / "package"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stderr_path = artifact_dir / f"{run_id}.package.stderr.log"
    ledger_path = artifact_dir / f"{run_id}.resource-ledger.jsonl"
    resource_ledger = ResourceLedger(ledger_path, run_id)
    resource_ledger.append("run", run_id, "started", "package stage initialization", policy_identity=policy_bundle["identity"], package_path=manifest.package_path, attempt_id=manifest.attempt_id, stage=stage.id)
    before = _status_paths(worktree)
    if before:
        raise ManifestError("worktree must be clean before a parent stage starts")
    session = None
    session_closed = False
    disposition_recorded = False
    try:
        session = JsonRpcSession(app_server_command(), stderr_path)
        session.request(1, "initialize", {"clientInfo": {"name": "codex-harness-package-runner", "version": "0.1"}, "capabilities": {"experimentalApi": True}}, 30)
        sandbox = "read-only" if stage.sandbox == "read_only" else "workspace-write"
        start_result, _ = session.request(
            2,
            "thread/start",
            {"cwd": str(worktree), "sandbox": sandbox, "approvalPolicy": "never", "ephemeral": False, "developerInstructions": profile["developer_instructions"], "model": profile["model"], "config": {"model_reasoning_effort": profile["model_reasoning_effort"]}},
            30,
        )
        root_thread_id = start_result["thread"]["id"]
        resource_ledger.append("thread", root_thread_id, "started", "thread/start", process_id=session.process.pid, worktree=str(worktree.resolve()))
        turn_result, notifications = session.request(
            3,
            "turn/start",
            {"threadId": root_thread_id, "input": [{"type": "text", "text": stage_prompt(run_id, work_package)}], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly" if stage.sandbox == "read_only" else "workspaceWrite", "networkAccess": manifest.network_access}},
            30,
        )
        turn_id = turn_result.get("turn", {}).get("id")
        if turn_id:
            resource_ledger.append("turn", turn_id, "started", "turn/start", thread_id=root_thread_id)
        if not any(item.get("method") == "turn/completed" and item.get("params", {}).get("threadId") == root_thread_id for item in notifications):
            notifications.extend(session.collect_until_turn_complete(root_thread_id, timeout_seconds))
        try:
            history, history_notifications = session.request(4, "thread/read", {"threadId": root_thread_id, "includeTurns": True}, 30)
        except RuntimeError:
            history, history_notifications = {}, []
        messages = walk_root_agent_messages(notifications + history_notifications + [history], root_thread_id)
        raw_result = messages[-1] if messages else ""
        parent_result = parse_parent_result(raw_result, run_id)
        changed_paths = _changed_paths(worktree)
        after = _status_paths(worktree)
        extended_result_valid = bool(
            parent_result
            and isinstance(parent_result.get("work_package_sha256"), str)
            and isinstance(parent_result.get("comparison_point"), str)
            and parent_result.get("comparison_point")
            and isinstance(parent_result.get("changed_paths"), list)
            and all(isinstance(path, str) for path in parent_result["changed_paths"])
        )
        package_hash_matches = bool(extended_result_valid and parent_result.get("work_package_sha256") == work_package["sha256"])
        stage_matches = bool(parent_result and parent_result.get("stage") == stage.id)
        parent_paths_match = bool(extended_result_valid and sorted(parent_result["changed_paths"]) == changed_paths)
        allowed = _paths_allowed(changed_paths, stage.allowed_paths)
        artifacts_safe = bool(parent_result and artifacts_valid(worktree, parent_result))
        sensitive_artifacts_safe = _artifacts_outside_sensitive_roots(parent_result, tuple(_relative_path(path, "sensitive root") for path in sensitive_roots))
        verifier_results = _run_verifiers(worktree, stage.verification_commands)
        verifiers_passed = bool(verifier_results) and all(item["exit_code"] == 0 for item in verifier_results)
        if parent_result and parent_result["status"] == "needs_owner":
            verdict = "needs_owner"
        elif parent_result and parent_result["status"] == "succeeded" and package_hash_matches and stage_matches and parent_paths_match and allowed and artifacts_safe and sensitive_artifacts_safe and not parent_result["boundary_violations"] and verifiers_passed:
            verdict = "passed"
        else:
            verdict = "failed"
        summary = {
            "run_id": run_id,
            "status": verdict,
            "stage": stage.id,
            "ticket": stage.ticket,
            "worktree": str(worktree.resolve()),
            "source_commit": validation["source_commit"],
            "root_thread_id": root_thread_id,
            "turn_id": turn_result.get("turn", {}).get("id"),
            "work_package": work_package,
            "parent_result": parent_result,
            "parent_result_raw": raw_result,
            "checks": {"extended_parent_result": extended_result_valid, "work_package_hash": package_hash_matches, "stage_matches": stage_matches, "changed_paths_match": parent_paths_match, "changed_paths_allowed": allowed, "artifacts_safe": artifacts_safe, "sensitive_artifacts_safe": sensitive_artifacts_safe, "external_verifiers_configured": bool(verifier_results), "external_verifiers_passed": verifiers_passed},
            "changed_paths": changed_paths,
            "worktree_status_before": before,
            "worktree_status_after": after,
            "verifier_results": verifier_results,
            "stderr_log": str(stderr_path),
            "policy_identity": policy_bundle["identity"],
            "resource_ledger": str(ledger_path),
        }
        session.close()
        session_closed = True
        resource_ledger.append("process", str(session.process.pid), "closed", "session.close", thread_id=locals().get("root_thread_id"))
        disposition = "promote" if verdict == "passed" else ("needs_owner" if verdict == "needs_owner" else "discard")
        resource_ledger.terminal_disposition(disposition, f"package stage verdict: {verdict}")
        disposition_recorded = True
        (artifact_dir / f"{run_id}.package.summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        if session is not None and not session_closed:
            try:
                session.close()
            finally:
                resource_ledger.append("process", str(session.process.pid), "closed", "session.close", thread_id=locals().get("root_thread_id"))
        if not disposition_recorded:
            resource_ledger.terminal_disposition("needs_owner", "package runner exception before terminal verdict")


def plan_summary(manifest: Manifest, completed: set[str], sensitive_roots: tuple[str, ...] = ()) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    ready = ready_stages(manifest, completed) if validation["valid"] else []
    return {
        "manifest": str(manifest.path),
        "validation": validation,
        "completed": sorted(completed),
        "ready_stages": [{"id": stage.id, "cohort": stage.cohort, "ticket": stage.ticket, "work_package": build_work_package(manifest, stage, sensitive_roots if stage.sensitive_originals == "on_demand" else ())} for stage in ready],
        "max_parallel_parents": manifest.max_parallel_parents,
    }
