"""Journey evidence normalisation and validation."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from situation import (
    carried_forward_error,
    evidence_artifact_base,
    evidence_record_valid,
)

from .spec_journey import (
    _journey_expected_surface,
)
from .state_core import (
    CONCLUSIONS,
    StateError,
    TIMINGS,
    _validate_commit,
    _validate_iso_timestamp,
)


# 复验路由：R1 文案/格式，R2 状态显隐，R3 因果链（见 run-acceptance）。
REVERIFY_ROUTES = ("R1", "R2", "R3")


def _package_relative_artifact(package: Path, value: Any, field: str, *, must_exist: bool, local_ok: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{field} must be a non-empty package-relative path")
    raw = value.strip().replace("\\", "/")
    path_value, separator, anchor_value = raw.partition("#")
    path = PurePosixPath(path_value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", raw) or raw.startswith("//") or ".." in path.parts or str(path) in {"", "."}:
        raise StateError(f"{field} must be package-relative: {value!r}")
    base = evidence_artifact_base(package, path) if local_ok else package
    resolved = (base / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError as exc:
        raise StateError(f"{field} escapes the package: {value!r}") from exc
    if must_exist and not resolved.exists():
        raise StateError(f"{field} does not exist: {path.as_posix()}")
    anchor = f"#{anchor_value}" if separator else ""
    return path.as_posix() + anchor


def _trace_action_method(event: dict[str, Any]) -> str | None:
    actions = {"click", "tap", "check", "press", "fill"}
    pending: list[Any] = [event]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if key.casefold() in {"method", "apiname", "type", "name"} and isinstance(child, str):
                    method = child.rsplit(".", 1)[-1].casefold()
                    if method in actions:
                        return method
                if isinstance(child, (dict, list)):
                    pending.append(child)
        elif isinstance(value, list):
            pending.extend(value)
    return None


def _trace_action_description(event: dict[str, Any]) -> str:
    descriptors: list[str] = []
    pending: list[Any] = [event]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if key.casefold() in {"selector", "params", "locator", "description", "locatordescription", "locator_description"}:
                    descriptors.append(child if isinstance(child, str) else json.dumps(child, ensure_ascii=False, sort_keys=True))
                elif isinstance(child, (dict, list)):
                    pending.append(child)
        elif isinstance(value, list):
            pending.extend(value)
    return " ".join(descriptors)


def _playwright_trace_actions(path: Path, control: str) -> tuple[bool, list[str]]:
    actions: list[str] = []
    found = False
    trace_files = 0
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir() or PurePosixPath(info.filename).suffix.casefold() != ".trace":
                    continue
                trace_files += 1
                with archive.open(info) as stream:
                    for line_number, line in enumerate(stream, start=1):
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                            raise StateError(f"Playwright trace JSONL 无法解析：{info.filename}:{line_number}: {exc}") from exc
                        if not isinstance(event, dict):
                            raise StateError(f"Playwright trace JSONL 事件必须是 object：{info.filename}:{line_number}")
                        method = _trace_action_method(event)
                        if method is None:
                            continue
                        description = _trace_action_description(event)
                        actions.append((method + (f" {description}" if description else ""))[:240])
                        if control.casefold() in description.casefold():
                            found = True
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        raise StateError(f"Playwright trace 无法解析：{exc}") from exc
    if not trace_files:
        raise StateError("Playwright trace ZIP 未包含 *.trace JSONL 文件")
    return found, actions


def _validate_journey_surface_evidence(
    package: Path, step: dict[str, Any], record: dict[str, Any], *, live: bool = True,
) -> str | None:
    surface = record.get("surface")
    if surface not in {"page", "file", "api", "log"}:
        raise StateError("Journey evidence surface must be page, file, api, or log")
    artifact = record.get("artifact")
    relative = PurePosixPath(str(artifact).replace("\\", "/").partition("#")[0])
    base = evidence_artifact_base(package, relative)
    path = (base / Path(*relative.parts)).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise StateError("Journey evidence artifact must be package-relative") from exc

    if surface == "api":
        if "manualBy" in record or "artifactSha256" in record:
            raise StateError("API Journey evidence cannot include manualBy or artifactSha256")
        return None

    expected_surface = _journey_expected_surface(step)
    if surface != expected_surface:
        raise StateError(f"Journey step {step['id']} entry type {step['entryType']} requires surface={expected_surface}")
    if live and not path.is_file():
        raise StateError(f"Journey {surface} artifact must be an existing package file: {record['artifact']}")

    if surface == "log":
        if "manualBy" in record or "artifactSha256" in record:
            raise StateError("log Journey evidence cannot include manualBy or artifactSha256")
        return None

    suffix = path.suffix.casefold()
    if surface == "page":
        if "artifactSha256" in record:
            raise StateError("page Journey evidence cannot include artifactSha256")
        if "testFile" in record or "testCase" in record:
            # R1 复验不截图：artifact 是组件测试的原始输出，记录写明测试文件与用例名。
            if record.get("route") != "R1":
                raise StateError("testFile/testCase (component test output as page evidence) is only valid with route R1")
            for field in ("testFile", "testCase"):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    raise StateError(f"R1 test-output evidence requires a non-empty {field}")
            if "manualBy" in record:
                raise StateError("R1 test-output evidence cannot include manualBy")
            return None
        if "manualBy" in record:
            manual_by = record["manualBy"]
            if not isinstance(manual_by, str) or not manual_by.strip():
                raise StateError("manualBy must be a non-empty string")
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise StateError(
                    "manualBy requires a package image artifact (.png, .jpg, .jpeg, .webp)；"
                    "截图不提交：放被 git 忽略的 output/qa/<runId>/，artifact 直接写该本地路径"
                )
            record["manualBy"] = manual_by.strip()
            return None
        if suffix != ".zip":
            raise StateError(
                "page Journey evidence requires a Playwright trace .zip or manualBy plus a package image "
                "(.png/.jpg/.jpeg/.webp；截图可放被 git 忽略的 output/qa/<runId>/)"
            )
        if not live:
            return None
        found, actions = _playwright_trace_actions(path, step["control"])
        if not found:
            actual = "; ".join(actions[:5]) or "none"
            raise StateError(
                f"Playwright trace must contain a click/tap/check/press/fill action for control "
                f"{step['control']!r}; actual actions: {actual}"
            )
        return None

    if "manualBy" in record:
        raise StateError("file Journey evidence cannot include manualBy")
    if suffix in {".md", ".txt", ".log"}:
        raise StateError(
            "file Journey artifact must not use .md, .txt, or .log；"
            "放该步产出的文件或接口返回本体（如 .json/.csv/.xlsx/.pdf）"
        )
    if not live:
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    recorded_digest = record.get("artifactSha256")
    if recorded_digest is not None and recorded_digest != digest:
        raise StateError("file Journey artifact sha256 does not match artifactSha256")
    return digest


def _validate_journey_evidence_index(
    package: Path,
    repo: Path,
    index: Any,
    spec: dict[str, Any],
    ticket_ids: set[str],
    *,
    live: bool,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(index, dict):
        raise StateError("3.6 evidenceIndex must be an object keyed by evidenceKey")
    normalized: dict[str, list[dict[str, Any]]] = {}
    run_environments: dict[str, tuple[str, str]] = {}
    run_setup_environments: dict[str, str] = {}
    journey_run_environments: dict[str, str] = {}
    setup_run_ids: set[str] = set()
    journey_run_ids: set[str] = set()
    base_fields = {"kind", "artifact", "revision", "environment", "conclusion"}
    fields_by_kind = {
        "journey-step": {"runId", "journeyId", "stepId", "actor", "entry", "surface"},
        "run-setup": {"runId"},
        "suite": {"suiteId"},
        "review": {"ticket"},
        "release": set(),
    }
    optional_fields_by_kind = {"journey-step": {"inputRef", "outputRef", "manualBy", "artifactSha256", "route", "testFile", "testCase"}}
    for evidence_key, records in index.items():
        if not isinstance(evidence_key, str) or not evidence_key or not isinstance(records, list):
            raise StateError(f"evidenceIndex[{evidence_key}] must map an evidenceKey to a list")
        normalized[evidence_key] = []
        for record in records:
            if not isinstance(record, dict):
                raise StateError(f"evidenceIndex[{evidence_key}] record must be an object")
            kind = record.get("kind")
            if not isinstance(kind, str) or kind not in fields_by_kind:
                raise StateError(f"evidenceIndex[{evidence_key}] has invalid kind")
            required = base_fields | fields_by_kind[kind]
            allowed = required | optional_fields_by_kind.get(kind, set()) | {"invalidatedBy", "timing", "recordedAt", "carriedForward"}
            if not required <= set(record) or set(record) - allowed:
                raise StateError(f"evidenceIndex[{evidence_key}] " + _evidence_field_error(kind, required, allowed, record))
            if "carriedForward" in record and (message := carried_forward_error(record["carriedForward"])):
                raise StateError(f"evidenceIndex[{evidence_key}] {message}")
            if not isinstance(record["conclusion"], str) or record["conclusion"] not in CONCLUSIONS:
                raise StateError(f"evidenceIndex[{evidence_key}] has invalid conclusion")
            if "timing" in record and (not isinstance(record["timing"], str) or record["timing"] not in TIMINGS):
                raise StateError(f"evidenceIndex[{evidence_key}] has invalid timing")
            if "recordedAt" in record:
                _validate_iso_timestamp(record["recordedAt"], f"evidenceIndex[{evidence_key}] recordedAt")
            invalidated_by = record.get("invalidatedBy")
            if "invalidatedBy" in record and invalidated_by is not None and (not isinstance(invalidated_by, str) or not invalidated_by.strip()):
                raise StateError(f"evidenceIndex[{evidence_key}] invalidatedBy must be text or null")
            normalized_artifact = _package_relative_artifact(package, record["artifact"], f"evidence {evidence_key}", must_exist=live, local_ok=True)
            for field in ("revision", "environment"):
                if not isinstance(record[field], str) or not record[field].strip():
                    raise StateError(f"evidence {evidence_key} {field} must be non-empty")
            copy = dict(record)
            copy["artifact"] = normalized_artifact
            copy["revision"] = _validate_commit(repo, record["revision"])
            if "carriedForward" in record:
                copy["carriedForward"] = {**record["carriedForward"], "to": _validate_commit(repo, record["carriedForward"]["to"])}
            if kind == "journey-step":
                run_id, journey_id, step_id, entry = (record[field] for field in ("runId", "journeyId", "stepId", "entry"))
                if not all(isinstance(value, str) and value.strip() for value in (run_id, journey_id, step_id, entry)):
                    raise StateError(f"evidenceIndex[{evidence_key}] Journey fields must be non-empty strings")
                for field in ("inputRef", "outputRef"):
                    if field in record and (not isinstance(record[field], str) or not record[field].strip()):
                        raise StateError(f"evidenceIndex[{evidence_key}] {field} must be a non-empty business object identifier")
                if "route" in record and record["route"] not in REVERIFY_ROUTES:
                    raise StateError(f"evidenceIndex[{evidence_key}] route must be one of {', '.join(REVERIFY_ROUTES)}")
                if evidence_key != f"journey:{run_id}:{step_id}":
                    raise StateError(f"evidenceIndex[{evidence_key}] must use journey:<runId>:<stepId>")
                step = spec["steps"].get(step_id)
                drift = (
                    "step" if step is None or step["journeyId"] != journey_id
                    else "entry" if entry != step["operationEntry"]
                    else "actor" if record["actor"] != step["role"]
                    else None
                )
                if drift:
                    # Spec 改写 Journey 后，对不上当前步骤的旧走查记录视为失效，只保留为审计痕迹，不再计入 reach。
                    if not copy.get("invalidatedBy"):
                        copy["invalidatedBy"] = f"spec-drift:{drift}"
                    if record["surface"] not in {"page", "file", "api", "log"}:
                        raise StateError(f"evidenceIndex[{evidence_key}] surface must be page, file, api, or log")
                    journey_run_ids.add(run_id)
                    journey_run_environments[run_id] = record["environment"]
                    normalized[evidence_key].append(copy)
                    continue
                if record["surface"] not in {"page", "file", "api", "log"}:
                    raise StateError(f"evidenceIndex[{evidence_key}] surface must be page, file, api, or log")
                digest = _validate_journey_surface_evidence(package, step, copy, live=live)
                if record["surface"] == "file":
                    if not isinstance(record.get("artifactSha256"), str) or re.fullmatch(r"[0-9a-f]{64}", record["artifactSha256"]) is None:
                        raise StateError(f"evidenceIndex[{evidence_key}] file surface requires artifactSha256")
                    if live and digest != record["artifactSha256"]:
                        raise StateError(f"evidenceIndex[{evidence_key}] file artifact sha256 does not match artifactSha256")
                elif "artifactSha256" in record:
                    raise StateError(f"evidenceIndex[{evidence_key}] artifactSha256 is only valid for file surface")
                environment_tuple = (journey_id, record["environment"])
                previous = run_environments.setdefault(run_id, environment_tuple)
                if previous != environment_tuple:
                    raise StateError(f"Journey run {run_id} must use one Journey and environment")
                journey_run_ids.add(run_id)
                journey_run_environments[run_id] = record["environment"]
            elif kind == "run-setup":
                run_id = record["runId"]
                if not isinstance(run_id, str) or not run_id.strip():
                    raise StateError(f"evidenceIndex[{evidence_key}] run-setup runId must be non-empty")
                if evidence_key != f"run-setup:{run_id}":
                    raise StateError(f"evidenceIndex[{evidence_key}] must use run-setup:<runId>")
                setup_run_ids.add(run_id)
                previous_environment = run_setup_environments.setdefault(run_id, record["environment"])
                if previous_environment != record["environment"]:
                    raise StateError(f"run-setup {run_id} must use one environment")
            elif kind == "suite":
                suite_id = record["suiteId"]
                if not isinstance(suite_id, str) or suite_id not in spec["suites"]:
                    raise StateError(f"evidenceIndex[{evidence_key}] references unknown suite")
                if evidence_key != f"suite:{suite_id}":
                    raise StateError(f"evidenceIndex[{evidence_key}] must use suite:<suiteId>")
                expected_environment = spec["suites"][suite_id]["environment"]
                if record["environment"] != expected_environment:
                    raise StateError(
                        f"evidenceIndex[{evidence_key}] environment 与 Spec 不一致："
                        f"Spec Suite {suite_id} 要求 {expected_environment!r}，实际为 {record['environment']!r}；"
                        "environment 须与 Spec 逐字一致"
                    )
            elif kind == "review":
                ticket = record["ticket"]
                if not isinstance(ticket, str) or (ticket != "package" and ticket not in ticket_ids):
                    raise StateError(f"evidenceIndex[{evidence_key}] review ticket must be a known Ticket or package")
                if evidence_key != f"review:{ticket}":
                    raise StateError(f"evidenceIndex[{evidence_key}] must use review:<ticket>")
            elif evidence_key != "release":
                raise StateError("release evidence key must be release")
            normalized[evidence_key].append(copy)
    missing_setups = sorted(journey_run_ids - setup_run_ids)
    if missing_setups:
        raise StateError("Journey runs missing run-setup: " + ", ".join(missing_setups))
    mismatched_setups = sorted(
        run_id for run_id in journey_run_ids
        if run_setup_environments.get(run_id) != journey_run_environments.get(run_id)
    )
    if mismatched_setups:
        raise StateError("Journey run-setup environment must match its Journey run: " + ", ".join(mismatched_setups))
    return normalized


def _evidence_field_error(kind: str, required: set[str], allowed: set[str], record: dict[str, Any]) -> str:
    missing = sorted(required - set(record))
    unknown = sorted(set(record) - allowed)
    return (
        f"3.6 {kind} evidence record has missing or unknown fields: "
        f"missing: {', '.join(missing) or '-'}; unknown: {', '.join(unknown) or '-'}"
    )


def _normalize_journey_evidence(
    package: Path,
    repo: Path,
    summary: dict[str, Any],
    state: dict[str, Any],
    comparison_commit: str,
    payload: Any,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise StateError("evidence record must be an object")
    kind = payload.get("kind")
    fields_by_kind = {
        "journey-step": {"runId", "journeyId", "stepId", "actor", "entry", "surface"},
        "run-setup": {"runId"},
        "suite": {"suiteId"},
        "review": {"ticket"},
        "release": set(),
    }
    optional_fields_by_kind = {"journey-step": {"inputRef", "outputRef", "manualBy", "route", "testFile", "testCase"}}
    if not isinstance(kind, str) or kind not in fields_by_kind:
        raise StateError("3.6 evidence kind must be journey-step, run-setup, suite, review, or release")
    required = {"kind", "artifact", "revision", "environment", "conclusion"} | fields_by_kind[kind]
    allowed = required | optional_fields_by_kind.get(kind, set()) | {"evidenceKey", "invalidatedBy", "timing", "recordedAt"}
    if not required <= set(payload) or set(payload) - allowed:
        raise StateError(_evidence_field_error(kind, required, allowed, payload))
    record = {field: value for field, value in payload.items() if field != "evidenceKey"}
    if not isinstance(record["conclusion"], str) or record["conclusion"] not in CONCLUSIONS:
        raise StateError("invalid evidence conclusion")
    if kind == "journey-step":
        for field in ("inputRef", "outputRef"):
            if field in record and (not isinstance(record[field], str) or not record[field].strip()):
                raise StateError(f"Journey evidence {field} must be a non-empty business object identifier")
        if "route" in record and record["route"] not in REVERIFY_ROUTES:
            raise StateError(f"Journey evidence route must be one of {', '.join(REVERIFY_ROUTES)}")
    if "timing" in record and record["timing"] not in TIMINGS:
        raise StateError("invalid evidence timing")
    if "recordedAt" in record:
        _validate_iso_timestamp(record["recordedAt"], "evidence recordedAt")
    if "invalidatedBy" in record and record["invalidatedBy"] is not None and (not isinstance(record["invalidatedBy"], str) or not record["invalidatedBy"].strip()):
        raise StateError("evidence invalidatedBy must be text or null")
    for field in ("revision", "environment"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise StateError(f"evidence {field} must be non-empty")
    record["artifact"] = _package_relative_artifact(package, record["artifact"], "evidence artifact", must_exist=False, local_ok=True)
    record["revision"] = _validate_commit(repo, record["revision"])

    spec = summary["_journeySpec"]
    if kind == "journey-step":
        run_id, journey_id, step_id, actor, entry = (record[field] for field in ("runId", "journeyId", "stepId", "actor", "entry"))
        if not all(isinstance(value, str) and value.strip() for value in (run_id, journey_id, step_id, actor, entry)):
            raise StateError("Journey evidence runId, journeyId, stepId, actor, and entry must be non-empty")
        step = spec["steps"].get(step_id)
        if step is None or step["journeyId"] != journey_id:
            raise StateError(f"unknown Journey step: {journey_id}/{step_id}")
        if actor != step["role"]:
            raise StateError(
                f"Journey evidence actor 与 Spec 不一致：实际为 {actor!r}，"
                f"Spec Journey 表 {journey_id}/{step_id} 允许的角色为 {step['role']!r}；"
                "走查人写在 manualBy"
            )
        if entry != step["operationEntry"]:
            raise StateError("Journey evidence entry does not match the Spec operation entry")
        if record["surface"] not in {"page", "file", "api", "log"}:
            raise StateError("Journey evidence surface must be page, file, api, or log")
        if "artifactSha256" in payload:
            raise StateError("artifactSha256 is generated automatically for file Journey evidence")
        attempt_active = not summary["_lifecycle"].frozen
        run_setup = state["evidenceIndex"].get(f"run-setup:{run_id}", [])
        if not any(
            setup.get("kind") == "run-setup"
            and evidence_record_valid(
                setup,
                comparison_commit,
                repo=repo,
                package=package,
                expected_environment=record["environment"],
                attempt_active=attempt_active,
            )
            for setup in run_setup
        ):
            raise StateError(
                f"Journey run {run_id} 缺少有效 run-setup；请先运行 Plan 中的 Harness setup 与 Harness precheck 并登记 run-setup"
            )
        digest = _validate_journey_surface_evidence(package, step, record)
        if record["surface"] == "file":
            record["artifactSha256"] = digest
        evidence_key = f"journey:{run_id}:{step_id}"
    elif kind == "run-setup":
        run_id = record["runId"]
        if not isinstance(run_id, str) or not run_id.strip():
            raise StateError("run-setup runId must be non-empty")
        if any(
            existing.get("environment") != record["environment"]
            for existing in state["evidenceIndex"].get(f"run-setup:{run_id}", [])
            if existing.get("kind") == "run-setup"
        ):
            raise StateError(f"run-setup {run_id} must use one environment")
        evidence_key = f"run-setup:{run_id}"
    elif kind == "suite":
        suite_id = record["suiteId"]
        if not isinstance(suite_id, str) or suite_id not in spec["suites"]:
            raise StateError(f"unknown required suite: {suite_id}")
        expected_environment = spec["suites"][suite_id]["environment"]
        if record["environment"] != expected_environment:
            raise StateError(
                f"suite {suite_id} evidence environment 与 Spec 不一致："
                f"Spec 要求 {expected_environment!r}，实际为 {record['environment']!r}；"
                "environment 须与 Spec 逐字一致"
            )
        evidence_key = f"suite:{suite_id}"
    elif kind == "review":
        ticket = record["ticket"]
        if not isinstance(ticket, str) or (ticket != "package" and ticket not in {item["id"] for item in summary["_documents"]}):
            raise StateError("review evidence ticket must be a known Ticket or package")
        evidence_key = f"review:{ticket}"
    else:
        evidence_key = "release"
    supplied_key = payload.get("evidenceKey")
    if supplied_key is not None and supplied_key != evidence_key:
        raise StateError(f"evidenceKey must be {evidence_key}")
    return evidence_key, record
