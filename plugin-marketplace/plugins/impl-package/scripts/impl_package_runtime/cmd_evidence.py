"""evidence and set-state commands."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from situation import (
    evidence_record_valid,
)

from .attempt_store import (
    _best_effort_trail,
    _ensure_execution_record,
    _parse_execution_record,
)
from .state_core import (
    DISPOSITIONS,
    Lifecycle,
    STATE_PATH,
    StateError,
    TICKET_STATES,
    _is_ancestor,
    _load_json,
    _read,
    _repo_relative,
    _repo_root,
    _run_git,
    _validate_commit,
    _write_json,
    _write_text,
)
from .validate_state import (
    _refresh_projections,
    _ticket_released,
    _validate_state,
)


def _assert_mutable(summary: dict[str, Any]) -> None:
    if summary["_lifecycle"].frozen:
        raise StateError(f"Attempt {summary['attempt']} is frozen by terminal Gate {summary['_lifecycle'].gate_verdict}")


def _v36_record_valid(
    package: Path,
    record: dict[str, Any],
    comparison_commit: str,
    *,
    expected_environment: str | None = None,
    attempt_active: bool = True,
) -> bool:
    return evidence_record_valid(
        record,
        comparison_commit,
        repo=_repo_root(package),
        package=package,
        expected_environment=expected_environment,
        attempt_active=attempt_active,
    )


def _ticket_owned_evidence_keys(summary: dict[str, Any], identifier: str) -> list[str]:
    document = next(row for row in summary["_documents"] if row["id"] == identifier)
    suites = summary["_journeySpec"]["suites"]
    return [f"review:{identifier}"] + [
        f"suite:{suite_id}" for suite_id in document["coverage"]["suites"] if suites[suite_id]["scope"] == "ticket"
    ]


def _v36_ticket_satisfy_gaps(package: Path, state: dict[str, Any], summary: dict[str, Any], identifier: str, revision: str) -> list[str]:
    repo = _repo_root(package)
    head = _run_git(repo, "rev-parse", "HEAD")
    if not _is_ancestor(repo, revision, head):
        return ["--revision must be an ancestor of current HEAD"]
    document = next(row for row in summary["_documents"] if row["id"] == identifier)
    gaps = []
    spec = summary["_journeySpec"]
    lifecycle: Lifecycle = summary["_lifecycle"]
    for suite_id in document["coverage"]["suites"]:
        suite = spec["suites"][suite_id]
        records = state["evidenceIndex"].get(f"suite:{suite_id}", [])
        if not any(
            _v36_record_valid(
                package,
                record,
                revision,
                expected_environment=suite["environment"],
                attempt_active=not lifecycle.frozen,
            )
            for record in records
        ):
            template = json.dumps({"kind": "suite", "suiteId": suite_id, "environment": suite["environment"], "revision": revision, "artifact": "<package-relative file>", "conclusion": "supporting"}, ensure_ascii=False)
            gaps.append(f"Suite {suite_id} 缺少对当前 revision 有效的 supporting 记录；补登：echo '{template}' | impl_package_state.py --package <package> evidence add")
    if document["coverage"]["requiredReview"] != "none":
        records = state["evidenceIndex"].get(f"review:{identifier}", [])
        if not any(
            _v36_record_valid(package, record, revision, attempt_active=not lifecycle.frozen)
            for record in records
        ):
            template = json.dumps({"kind": "review", "ticket": identifier, "environment": "<env>", "revision": revision, "artifact": "execution/<attempt>/reviews/<file>", "conclusion": "supporting"}, ensure_ascii=False)
            gaps.append(f"Ticket {identifier} 缺少有效的 supporting review（需无未关闭 blocker）；补登：echo '{template}' | impl_package_state.py --package <package> evidence add")
    return gaps


def _validate_first_step_object_is_new(state: dict[str, Any], spec: dict[str, Any], record: dict[str, Any]) -> None:
    if record.get("kind") != "journey-step" or not record.get("outputRef"):
        return
    journey = next(item for item in spec["journeys"] if item["id"] == record["journeyId"])
    if record["stepId"] != journey["steps"][0]["id"]:
        return
    output_ref = record["outputRef"]
    for records in state["evidenceIndex"].values():
        for existing in records:
            if (
                existing.get("kind") == "journey-step"
                and existing.get("runId") != record["runId"]
                and output_ref in {existing.get("inputRef"), existing.get("outputRef")}
            ):
                suggested_ref = f"{record['runId']}-{output_ref}"
                raise StateError(
                    f"第 1 步产出的对象 {output_ref!r} 已在 run {existing['runId']} 中出现，"
                    f"每次 run 需新建业务对象；给 outputRef/inputRef 加 runId 前缀（例如 {suggested_ref!r}）"
                )


def _validate_journey_step_order(state: dict[str, Any], spec: dict[str, Any], record: dict[str, Any]) -> None:
    journey = next(item for item in spec["journeys"] if item["id"] == record["journeyId"])
    positions = {step["id"]: index for index, step in enumerate(journey["steps"])}
    current_position = positions[record["stepId"]]
    steps_by_position: dict[int, list[dict[str, Any]]] = {}
    for records in state["evidenceIndex"].values():
        for existing in records:
            # 一次 run 可连续走多条 Journey，顺序只在同一 Journey 内核对。
            if (
                existing.get("kind") == "journey-step"
                and existing.get("runId") == record["runId"]
                and existing.get("journeyId") == record["journeyId"]
            ):
                steps_by_position.setdefault(positions[existing["stepId"]], []).append(existing)
    if not steps_by_position:
        if current_position != 0:
            # 按影响范围复测：新 run 可从受影响步骤起步，但承接须对上其他 run 上一步的有效 outputRef。
            previous_step = journey["steps"][current_position - 1]
            inherited = record.get("inputRef")
            ok = isinstance(inherited, str) and any(
                existing.get("kind") == "journey-step"
                and existing.get("journeyId") == record["journeyId"]
                and existing.get("stepId") == previous_step["id"]
                and existing.get("conclusion") == "supporting"
                and not existing.get("invalidatedBy")
                and existing.get("outputRef") == inherited
                for records in state["evidenceIndex"].values()
                for existing in records
            )
            if not ok:
                raise StateError(
                    f"Journey run {record['runId']} must start at {journey['steps'][0]['id']}；"
                    "若第 1 步刚因对象复用被拒，先修正第 1 步的 outputRef/inputRef 再按 Spec 顺序重试。"
                    "按影响范围复测时可从受影响步骤起步，但其 inputRef 须等于其他 run 上一步的 outputRef"
                )
        return
    last_position = max(steps_by_position)
    if set(steps_by_position) != set(range(min(steps_by_position), last_position + 1)):
        raise StateError(f"Journey run {record['runId']} has a missing earlier step; start a new run")
    if current_position < last_position or current_position > last_position + 1:
        raise StateError(f"Journey run {record['runId']} must record steps in Spec order")
    if current_position == last_position + 1:
        last_record = steps_by_position[last_position][-1]
        if last_record.get("conclusion") != "supporting" or last_record.get("invalidatedBy"):
            raise StateError(f"Journey run {record['runId']} cannot continue after a failed or invalidated step")
    current_step = journey["steps"][current_position]
    handoff = current_step["handoff"]
    if current_position > 0 and handoff != "—":
        previous_step = journey["steps"][current_position - 1]
        previous_records = steps_by_position[current_position - 1]
        previous_record = previous_records[-1]
        previous_output = previous_record.get("outputRef")
        context = (
            f"Journey {journey['id']} 第 {current_position + 1} 步 {current_step['id']} "
            f"承接‘{handoff}’"
        )
        if not isinstance(previous_output, str) or not previous_output.strip():
            raise StateError(
                f"{context}无法核对：第 {current_position} 步 {previous_step['id']} 缺少 outputRef，"
                "期望值为上一条记录的 outputRef。请用 evidence invalidate --key "
                f"journey:{record['runId']}:{previous_step['id']} --invalidated-by <原因> 失效该步后补带 outputRef 重新登记，或另起 run。"
            )
        actual_input = record.get("inputRef")
        if not isinstance(actual_input, str) or not actual_input.strip():
            raise StateError(
                f"{context}缺少 inputRef；期望值为 {previous_output!r}，需与 "
                f"{previous_step['id']} 的 outputRef 完全相等。"
            )
        if actual_input != previous_output:
            raise StateError(
                f"{context}的 inputRef 与 {previous_step['id']} outputRef 不一致；"
                f"期望值为 {previous_output!r}，实际为 {actual_input!r}。"
            )


def command_evidence_add(package: Path, payload_text: str, dry_run: bool = False) -> dict[str, Any]:
    from impl_package_runtime import evidence_batch

    return evidence_batch.evidence_add(package, payload_text, dry_run)


def command_evidence_invalidate(package: Path, key: str, invalidated_by: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if not isinstance(invalidated_by, str) or not invalidated_by.strip():
        raise StateError("invalidated-by must be non-empty")
    if not isinstance(key, str) or not key.strip():
        raise StateError("evidence invalidate requires --key")
    records = state["evidenceIndex"].get(key)
    if not isinstance(records, list) or not records:
        raise StateError("evidence key not found")
    changed = False
    for record in records:
        previous = record.get("invalidatedBy")
        if previous is None:
            record["invalidatedBy"] = invalidated_by.strip()
            changed = True
        elif previous != invalidated_by.strip():
            raise StateError(f"evidence key {key} is already invalidated by {previous}")
    if changed:
        _validate_state(package, state, projections=False)
        _write_json(package / STATE_PATH, state)
        _refresh_projections(package, state)
    return {"evidenceKey": key, "invalidated": True, "idempotent": not changed}


def command_evidence_carry_forward(
    package: Path, key: str | None, to: str, reason: str | list[str] | None, judged_by: str,
    selects: list[str] | None = None, dry_run: bool = False,
) -> dict[str, Any]:
    """Record the agent's judgment that supporting evidence still covers runtime changes up to `to` (batched in evidence_batch)."""
    from impl_package_runtime import evidence_batch

    return evidence_batch.evidence_carry_forward(package, key, to, reason, judged_by, selects, dry_run)


def command_set_state(
    package: Path,
    identifier: str,
    target: str,
    expect: str,
    revision: str | None,
    environment: str | None,
    disposition: str | None,
    successor: str | None,
    evidence: str | None,
    revalidation_plan: str | None,
    invalidated_by: str | None = None,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if identifier not in state["tickets"] or target not in TICKET_STATES:
        raise StateError(f"unknown Ticket or invalid state: {identifier}/{target}")
    current = state["tickets"][identifier]["state"]
    if current != expect:
        raise StateError(f"stale ticket transition for {identifier}: expected {expect}, found {current}")
    repo = _repo_root(package)
    if target != "NEEDS-REVALIDATION" and invalidated_by is not None:
        raise StateError("--invalidated-by is only valid for NEEDS-REVALIDATION")

    if current == "RETIRED":
        if target != "RETIRED":
            raise StateError(f"RETIRED Ticket {identifier} is terminal; create a patch Attempt to continue")
        if disposition not in DISPOSITIONS or not evidence:
            raise StateError("repeating RETIRED requires the original --disposition and --evidence")
        normalized_retired = _repo_relative(repo, evidence, "retired evidence")
        existing = state["tickets"][identifier]
        if (
            disposition != existing.get("disposition")
            or normalized_retired != existing.get("evidence")
            or successor != existing.get("successor")
        ):
            raise StateError(f"RETIRED Ticket {identifier} is terminal; only an identical retry is idempotent")
        return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True}

    if current == target and target != "NEEDS-REVALIDATION":
        return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True}

    invalidated_count = 0
    if target == "NEEDS-REVALIDATION":
        if not isinstance(invalidated_by, str) or not invalidated_by.strip():
            raise StateError("NEEDS-REVALIDATION requires a non-empty --invalidated-by")
        for key in _ticket_owned_evidence_keys(summary, identifier):
            for record in state["evidenceIndex"].get(key, []):
                if record.get("invalidatedBy") is None:
                    record["invalidatedBy"] = invalidated_by.strip()
                    invalidated_count += 1
        if current == target and invalidated_count == 0:
            return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True, "invalidatedEvidence": 0}

    if target == "PENDING" and current in {"BLOCKED", "NEEDS-REVALIDATION"} and not revalidation_plan:
        raise StateError("returning to PENDING requires --revalidation-plan")
    if target == "PENDING" and current in {"BLOCKED", "NEEDS-REVALIDATION"}:
        _repo_relative(repo, revalidation_plan, "revalidation plan")
    if target == "SATISFIED":
        if not revision:
            revision = _run_git(repo, "rev-parse", "HEAD")
        if environment is not None and not environment.strip():
            raise StateError("SATISFIED --environment must be non-empty when provided")
        revision = _validate_commit(repo, revision)
        gaps = _v36_ticket_satisfy_gaps(package, state, summary, identifier, revision)
        unreleased = [
            dep for kind, dep in summary["_ticketDependencies"][identifier]
            if kind in {"implementation", "acceptance"} and not _ticket_released(state["tickets"], dep)
        ]
        if unreleased:
            gaps.append(f"Ticket implementation or acceptance dependencies are not released: {', '.join(unreleased)}")
        if gaps:
            raise StateError("SATISFIED rejected (all gaps):\n- " + "\n- ".join(gaps))
    if target == "BLOCKED" and not evidence:
        raise StateError("BLOCKED requires --evidence")
    normalized_evidence = _repo_relative(repo, evidence, "Ticket evidence") if evidence else None
    if target == "RETIRED":
        if disposition not in DISPOSITIONS or not evidence:
            raise StateError("RETIRED requires --disposition and --evidence")
        if disposition == "superseded" and not successor:
            raise StateError("superseded RETIRED requires --successor")
        state["tickets"][identifier] = {"state": "RETIRED", "disposition": disposition, "evidence": _repo_relative(repo, evidence, "retired evidence")}
        if successor:
            state["tickets"][identifier]["successor"] = successor
    if target != "RETIRED":
        state["tickets"][identifier] = {"state": target}
        if normalized_evidence and target in {"BLOCKED", "NEEDS-REVALIDATION"}:
            state["tickets"][identifier]["evidence"] = normalized_evidence
        if target == "SATISFIED":
            acceptance = {"revision": revision}
            if environment is not None:
                acceptance["environment"] = environment
            state["tickets"][identifier] = {"state": target, "acceptance": acceptance}
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    result = {"kind": "ticket", "id": identifier, "state": target, "idempotent": False}
    if target == "NEEDS-REVALIDATION":
        result["invalidatedEvidence"] = invalidated_count
    if target in {"SATISFIED", "RETIRED"}:
        _best_effort_trail(
            package,
            summary["attempt"],
            {
                "subject": f"ticket:{identifier}",
                "kind": "result",
                "transition": "ticket-state",
                "from": current,
                "to": target,
                "outcome": target,
            },
        )
    return result


def _add_judgment(package: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if payload.get("purpose") != "judgment":
        raise StateError("er-add accepts judgment only; use checkpoint command")
    subject = payload.get("subject", "attempt")
    if subject != "attempt" and (not isinstance(subject, str) or not re.fullmatch(r"ticket:[^\s]+", subject) or subject.split(":", 1)[1] not in state["tickets"]):
        raise StateError(f"invalid judgment subject: {subject}")
    title, content = payload.get("title"), payload.get("content")
    if not isinstance(title, str) or not title.strip() or "\n" in title or not isinstance(content, str) or not content.strip():
        raise StateError("judgment requires one-line title and non-empty content")
    evidence = payload.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        raise StateError("judgment evidence must be a path or list")
    repo = _repo_root(package)
    normalized = [_repo_relative(repo, item, "judgment evidence") for item in evidence]
    path = _ensure_execution_record(package, summary["attempt"])
    _, entries = _parse_execution_record(path, summary["attempt"])
    same = next((row for row in entries if row["purpose"] == "judgment" and row["subject"] == subject and row["title"] == title.strip() and row["content"] == content.strip() and row["evidence"] == normalized), None)
    if same:
        return {"recordId": same["id"], "attempt": summary["attempt"], "idempotent": True}
    number = max((row["number"] for row in entries), default=0) + 1
    record_id = f"{summary['attempt']}-ER-{number:03d}"
    evidence_text = "\n".join(f"- {item}" for item in normalized) or "- none"
    block = f"\n## {record_id} · judgment\n\n- Subject: {subject}\n- Title: {title.strip()}\n- Next action: none\n\n### Evidence\n\n{evidence_text}\n\n### Content\n\n{content.strip()}\n"
    _write_text(path, _read(path).rstrip() + block)
    _refresh_projections(package, state)
    return {"recordId": record_id, "attempt": summary["attempt"], "idempotent": False}


def command_er_add(package: Path, input_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(input_text)
    except json.JSONDecodeError as exc:
        raise StateError(f"er-add input is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StateError("er-add input must be an object")
    return _add_judgment(package, payload)
