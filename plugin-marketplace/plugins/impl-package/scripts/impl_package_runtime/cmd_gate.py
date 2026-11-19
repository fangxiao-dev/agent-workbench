"""checkpoint and gate commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from situation import (
    live_package_reference_fact,
    terminal_coverage_fact,
)

from .acceptance import (
    _v36_acceptance_status,
)
from .attempt_store import (
    _best_effort_result,
    _best_effort_trail,
    _best_effort_trail_rotation,
    _set_execution_record_status,
    _write_attempt_archive,
)
from .cmd_evidence import (
    _assert_mutable,
)
from .state_core import (
    GATE_PATH,
    Lifecycle,
    STATE_PATH,
    StateError,
    TERMINAL_VERDICTS,
    _load_json,
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


def command_checkpoint(
    package: Path,
    subject: str,
    next_action: str,
    blocker: str | None,
    evidence: list[str],
    handoff: bool = False,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if subject != "attempt" and (not re.fullmatch(r"ticket:[^\s]+", subject) or subject.split(":", 1)[1] not in state["tickets"]):
        raise StateError(f"invalid checkpoint subject: {subject}")
    repo = _repo_root(package)
    state["activeCheckpoints"][subject] = {"next": next_action.strip(), "blocker": blocker.strip() if blocker else None, "evidence": [_repo_relative(repo, item, "checkpoint evidence") for item in evidence]}
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    _best_effort_trail(
        package,
        summary["attempt"],
        {
            "subject": subject,
            "kind": "checkpoint",
            "checkpoint": True,
            **state["activeCheckpoints"][subject],
        },
    )
    if handoff:
        _best_effort_trail_rotation(package, summary["attempt"])
        _best_effort_trail(
            package,
            summary["attempt"],
            {
                "subject": subject,
                "kind": "handoff",
                "checkpoint": True,
                **state["activeCheckpoints"][subject],
            },
        )
    return {"subject": subject, "checkpoint": state["activeCheckpoints"][subject], "idempotent": False}


def _update_history(state: dict[str, Any], attempt: str, lifecycle: str, gate: dict[str, Any] | None) -> None:
    for row in state["attemptHistory"]:
        if row["id"] == attempt:
            row["lifecycle"] = lifecycle
            row["gate"] = gate
            return


def _v36_gate_items(
    package: Path,
    state: dict[str, Any],
    summary: dict[str, Any],
    comparison_commit: str,
    durable: list[str],
    no_durable_reason: str | None,
) -> tuple[list[dict[str, str]], dict[str, Any], Any, Any]:
    """Gate gaps as {category, message, fix}; `pass` joins the messages, `gate preflight` reports the rest."""
    lifecycle: Lifecycle = summary["_lifecycle"]
    status = _v36_acceptance_status(package, state, summary, comparison_commit, attempt_active=not lifecycle.frozen)
    items: list[dict[str, str]] = []
    state_cmd = "impl_package_state.py --package <package>"

    def gap(category: str, message: str, fix: str = "") -> None:
        items.append({"category": category, "message": message, "fix": fix})

    for row in status["unregisteredAmendments"]:
        gap("amendment", f"合同文件 {row['path']} 相对 contractBaseline 有变化但未登记 Amendment；合同已变更，需登记 Amendment 并经 Owner 确认",
            f"{state_cmd} package amendment add --id <AMD-id> --summary <变更摘要> --affected {row['path']}")
    for journey in status["journeys"]:
        if journey["reach"] != journey["total"]:
            hint = "；API 预演已走通，仍需页面/文件/记录证据" if journey["rehearsalReach"] == journey["total"] else ""
            gap("journey", f"Journey {journey['id']} 尚未在同一 run 走通全部页面/文件/记录步骤 "
                f"（有效步骤走通 {journey['reach']}/{journey['total']}，API 预演 {journey['rehearsalReach']}/{journey['total']}）{hint}",
                f"走查 Journey {journey['id']} 后 {state_cmd} evidence add（模板见 evidence add --help）")
    suites = summary["_journeySpec"]["suites"]
    for suite in status["suites"]:
        if not suite["valid"]:
            entry = suites[suite["id"]]["entry"]
            gap("suite", f"Required Suite {suite['id']} 缺少当前有效的 supporting 记录",
                f"运行 {entry} 后 {state_cmd} evidence add（kind=suite, suiteId={suite['id']}, revision=HEAD）")
    for key in status["staleEvidence"]:
        gap("stale", f"Evidence {key} 的 supporting 记录待复验；若变更不影响运行时，用 "
            f"evidence carry-forward --key {key} --to <HEAD> --reason <理由> --judged-by <人>",
            f"{state_cmd} evidence carry-forward --key {key} --to {comparison_commit} --reason <理由> --judged-by <人>")
    for ticket, row in state["tickets"].items():
        if row["state"] != "SATISFIED":
            gap("ticket", f"Required Ticket {ticket} 状态为 {row['state']}，需要 SATISFIED", f"{state_cmd} ticket satisfy {ticket} --expect {row['state']}")
    for ticket, edges in summary["_ticketDependencies"].items():
        for kind, dependency in edges:
            if not _ticket_released(state["tickets"], dependency):
                gap("ticket", f"Ticket {ticket} 的 {kind} 入边 {dependency} 未释放", f"先释放 Ticket {dependency}")
    for row in status["pendingAmendments"]:
        gap("amendment", f"合同修订 {row['id']} 待 Owner 确认：{row['summary']}",
            f"{state_cmd} package amendment confirm --id {row['id']} --confirmed-by <Owner>（须 Owner 同意）")
    if status["releaseRequired"] and not status["releaseValid"]:
        gap("release", "Plan 要求发布顺序，但缺少当前有效的 release 记录", f"{state_cmd} evidence add（kind=release）")
    coverage = terminal_coverage_fact(package)
    if not coverage.known or coverage.value is not True:
        label = "unknown" if not coverage.known else "incomplete"
        gap("review", f"terminal review coverage {label}：{coverage.reason or '未通过'}",
            f"{state_cmd} trail append --help（写 review.terminal_summary；报告头四行须为 verdict/reviewed-head/review-run/review-track）")
    live_references = live_package_reference_fact(package)
    if not live_references.known:
        gap("references", f"live package reference 无法判定：{live_references.reason or 'unknown'}")
    elif live_references.value is True:
        gap("references", (live_references.reason or "package 含活体 package 引用")
            + "；先将每条引用通过 /impl-package:backfill-stable-docs 吸收进 stable docs，再把当前 package 改为引用 stable docs")
    if not durable and not (no_durable_reason and no_durable_reason.strip()):
        gap("durable", "terminal Gate 需要 Durable Delta 或 --no-durable-delta-reason", "gate pass 加 --durable-delta <路径> 或 --no-durable-delta-reason <原因>")
    return items, status, coverage, live_references


def _v36_gate_gaps(
    package: Path,
    state: dict[str, Any],
    summary: dict[str, Any],
    comparison_commit: str,
    durable: list[str],
    no_durable_reason: str | None,
) -> tuple[list[str], dict[str, Any], Any, Any]:
    items, status, coverage, live_references = _v36_gate_items(
        package, state, summary, comparison_commit, durable, no_durable_reason,
    )
    return [item["message"] for item in items], status, coverage, live_references


CATEGORY_ORDER = ("amendment", "suite", "journey", "stale", "review", "ticket", "release", "references", "durable", "state")


def gate_preflight(
    package: Path, commit: str | None, durable: list[str], no_durable_reason: str | None,
) -> dict[str, Any]:
    """Read-only run of every `gate pass` check; groups gaps by category with a fix command each."""
    from .impact import evidence_impact

    state = _load_json(package / STATE_PATH)
    repo = _repo_root(package)
    head = _run_git(repo, "rev-parse", "HEAD")
    resolved = _validate_commit(repo, commit or head)
    items: list[dict[str, str]] = []
    try:
        summary = _validate_state(package, state, projections=False)
        lifecycle: Lifecycle = summary["_lifecycle"]
        if lifecycle.frozen:
            ok = lifecycle.gate and lifecycle.gate["verdict"] == "pass"
            if not ok:
                items.append({"category": "state", "message": f"Attempt {summary['attempt']} 已被 {lifecycle.gate_verdict} Gate 冻结", "fix": ""})
            return _preflight_result(resolved, items, already_passed=bool(ok))
        if resolved != head:
            items.append({"category": "state", "message": "terminal Gate comparison commit 必须等于当前 HEAD", "fix": f"--comparison-commit {head}"})
        gate_items, *_ = _v36_gate_items(package, state, summary, resolved, durable, no_durable_reason)
        items.extend(gate_items)
        stale = [i for i in items if i["category"] == "stale"]
        if stale:
            impact = evidence_impact(package, resolved)
            fixes = {u["key"]: impact["carryCommand"] for u in impact["carry"]}
            fixes.update({u["key"]: u["command"] for u in impact["rerun"]})
            for item in stale:
                key = item["message"].split(" ", 2)[1]
                unit = f"run:{key.split(':')[1]}" if key.startswith(("journey:", "run-setup:")) else key
                item["fix"] = fixes.get(unit, item["fix"])
    except StateError as exc:
        items.append({"category": "state", "message": str(exc), "fix": ""})
    return _preflight_result(resolved, items)


def _preflight_result(commit: str, items: list[dict[str, str]], already_passed: bool = False) -> dict[str, Any]:
    items = sorted(items, key=lambda i: CATEGORY_ORDER.index(i["category"]))
    counts: dict[str, int] = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {"commit": commit, "ok": not items, "alreadyPassed": already_passed, "counts": counts, "gaps": items}


def render_preflight(result: dict[str, Any], *, summary_only: bool = False) -> str:
    if result["ok"]:
        return "gate preflight: Gate 已 pass（Attempt 已冻结）" if result["alreadyPassed"] else "gate preflight: OK，可以 gate pass"
    head = "gate preflight: " + f"{len(result['gaps'])} 个缺口（" + "，".join(f"{k} {v}" for k, v in result["counts"].items()) + "）"
    if summary_only:
        return head
    lines = [head]
    for item in result["gaps"]:
        lines.append(f"[{item['category']}] {item['message']}")
        if item["fix"]:
            lines.append(f"    修复：{item['fix']}")
    return "\n".join(lines)


def _owner_summary(
    status: dict[str, Any],
    comparison_commit: str,
    verdict: str,
    reason: str,
) -> list[str]:
    lines = ["## Owner Summary\n"]
    for journey in status["journeys"]:
        lines.append(
            f"- {journey['id']} {journey['title']}：有效步骤走通 {journey['reach']}/{journey['total']} · "
            f"API 预演 {journey['rehearsalReach']}/{journey['total']}\n"
        )
    if status.get("walkingSkeletonOverdue"):
        first_visible = status["firstVisibleStep"]
        lines.append(
            f"- walking skeleton：{first_visible['step']} 应在 {first_visible['ticket']} 合入后走通，尚未走通\n"
        )
    valid_suites = sum(1 for row in status["suites"] if row["valid"])
    lines.append(f"- 套件：{valid_suites}/{len(status['suites'])} 通过\n")
    for row in status.get("carriedForwardEvidence", []):
        lines.append(
            f"- 沿用证据：{row['key']} {row['from'][:7]}→{row['to'][:7]}，{row['reason']}（{row['judgedBy']}判断）\n"
        )
    pending = status["pendingAmendments"]
    unregistered = status["unregisteredAmendments"]
    if pending:
        descriptions = "；".join(f"{row['id']} {row['summary']}" for row in pending)
        lines.append(f"- 合同修订：{len(pending)} 条待 Owner 确认（{descriptions}）\n")
    elif unregistered:
        files = "、".join(row["path"] for row in unregistered)
        lines.append(f"- 合同修订：存在漏登文件 {files}\n")
    else:
        lines.append("- 合同修订：无待确认或漏登\n")
    if not status["releaseRequired"]:
        release = "未要求"
    else:
        release = "已记录" if status["releaseValid"] else "缺失"
    lines.append(f"- 发布顺序：{release}\n")
    lines.append(f"- 最终版本：{comparison_commit[:7]}\n")
    conclusion = reason.strip() or ("所有验收项已满足" if verdict == "pass" else "仍有验收缺口")
    lines.append(f"- 结论：{verdict} — {conclusion}\n")
    manual = [
        f"{item['stepId']}（{item['manualBy']}）"
        for journey in status["journeys"]
        for item in journey["manualWalkthroughs"]
    ]
    if manual:
        lines.append(f"- 走查：{'、'.join(manual)}\n")
    return lines


def command_gate(package: Path, verdict: str, commit: str, reason: str, evidence: list[str], durable: list[str], no_durable_reason: str | None, environment: str | None, commit_changes: bool = False) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    repo = _repo_root(package)
    resolved = _validate_commit(repo, commit)
    lifecycle: Lifecycle = summary["_lifecycle"]
    if lifecycle.frozen:
        if lifecycle.gate and lifecycle.gate["verdict"] == verdict and lifecycle.gate["commit"] == resolved:
            _write_attempt_archive(package, summary["attempt"], state["tickets"])
            _best_effort_result(package, summary["attempt"], {
                "subject": f"attempt:{summary['attempt']}", "transition": "gate", "verdict": verdict,
                "commit": resolved, "outcome": verdict,
            })
            result = {"formatVersion": summary["formatVersion"], "verdict": verdict, "attempt": summary["attempt"], "commit": resolved, "idempotent": True}
            return result
        raise StateError(f"Attempt {summary['attempt']} is already frozen by terminal Gate {lifecycle.gate_verdict}")
    if verdict in TERMINAL_VERDICTS and resolved != _run_git(repo, "rev-parse", "HEAD"):
        raise StateError("terminal Gate comparison commit must equal current HEAD")
    if verdict in TERMINAL_VERDICTS and not durable and not (no_durable_reason and no_durable_reason.strip()) and verdict != "pass":
        raise StateError("terminal Gate requires --durable-delta or --no-durable-delta-reason")
    if verdict == "pass":
        gaps, v36_status, _coverage, _live_references = _v36_gate_gaps(
            package, state, summary, resolved, durable, no_durable_reason,
        )
        if gaps:
            raise StateError("pass Gate rejected: " + "; ".join(gaps))
    else:
        v36_status = _v36_acceptance_status(
            package, state, summary, resolved, attempt_active=not lifecycle.frozen,
        )
    normalized_evidence = [_repo_relative(repo, item, "gate evidence") for item in evidence]
    if verdict in TERMINAL_VERDICTS:
        state["activeCheckpoints"] = {}
    gate = {"verdict": verdict, "commit": resolved, "environment": environment}
    _update_history(state, summary["attempt"], "frozen" if verdict in TERMINAL_VERDICTS else "active", gate)
    if verdict in TERMINAL_VERDICTS:
        _validate_state(
            package,
            state,
            projections=False,
            frozen_contract_commit=resolved,
        )
    lines = ["# Gate\n", f"- Verdict: {verdict}\n", f"- Attempt: {summary['attempt']}\n", f"- Comparison commit: {resolved}\n", f"- Reason: {reason.strip()}\n"]
    lines.append("\n")
    lines.extend(_owner_summary(v36_status, resolved, verdict, reason))
    lines.append("\n## Evidence\n")
    lines.extend(f"- {item}\n" for item in normalized_evidence) or lines.append("- none\n")
    lines.append("\n## Durable Deltas\n")
    lines.extend(f"- {item}\n" for item in durable) or lines.append(f"- Reason: {no_durable_reason or 'none'}\n")
    _write_text(package / GATE_PATH, "".join(lines))
    _set_execution_record_status(package, summary["attempt"], "frozen" if verdict in TERMINAL_VERDICTS else "active", verdict)
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    if verdict in TERMINAL_VERDICTS:
        _write_attempt_archive(package, summary["attempt"], state["tickets"])
    _best_effort_result(package, summary["attempt"], {
        "subject": f"attempt:{summary['attempt']}", "transition": "gate", "verdict": verdict,
        "commit": resolved, "outcome": verdict,
    })
    result = {"formatVersion": summary["formatVersion"], "verdict": verdict, "attempt": summary["attempt"], "commit": resolved, "idempotent": False}
    if commit_changes:
        result["packageCommit"] = _commit_package(package, repo, summary["attempt"], verdict)
    return result


def _commit_package(package: Path, repo: Path, attempt: str, verdict: str) -> str | None:
    """Commit only the package directory; the message carries no attribution trailer. None when nothing changed."""
    rel = package.resolve().relative_to(repo).as_posix()
    _run_git(repo, "add", "--", rel)
    if _run_git(repo, "status", "--porcelain", "--", rel) == "":
        return None
    _run_git(repo, "commit", "-m", f"docs({package.name}): Gate {verdict} {attempt}", "--", rel)
    return _run_git(repo, "rev-parse", "HEAD")
