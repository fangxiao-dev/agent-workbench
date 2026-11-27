"""Build package status snapshots and apply per-package route updates."""

from __future__ import annotations

import json
from pathlib import Path

from . import agents, batches
from .facts import BAD_VERDICTS, read_facts
from .store import load_profile, save_profile

STATUS_VALUES = {"done", "active", "pending", "blocked", "attention"}
PIPELINE_PATH = Path(__file__).resolve().parents[1] / "pipeline.json"


def load_pipeline() -> dict:
    try:
        pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取 pipeline.json：{error}") from error
    stages = pipeline.get("stages") if isinstance(pipeline, dict) else None
    identifiers = [item.get("id") for item in stages or [] if isinstance(item, dict)]
    if (not isinstance(stages, list) or not stages or len(identifiers) != len(stages)
            or len(set(identifiers)) != len(identifiers)
            or any(not isinstance(item.get("label"), str) or not isinstance(item.get("description"), str)
                   for item in stages if isinstance(item, dict))
            or not STATUS_VALUES.issubset(set(pipeline.get("statuses", [])))):
        raise ValueError("pipeline.json stages/statuses 结构无效")
    return pipeline


PIPELINE = load_pipeline()
PIPELINE_STAGES = tuple(stage["id"] for stage in PIPELINE["stages"])


def _projection_matches(facts: dict) -> tuple[dict | None, set[str]]:
    projection = facts.get("projection")
    rows = [row for key in ("matches", "blocking", "runnable", "withheld")
            for row in (projection or {}).get(key, []) if isinstance(row, dict)]
    return projection, {row.get("slug") for row in rows}


def _rounds_path_key(path: object, package: str | Path | None = None) -> Path | None:
    if not isinstance(path, str) or not path.strip():
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and package is not None:
        candidate = Path(package).expanduser() / candidate
    try:
        return candidate.resolve()
    except (OSError, RuntimeError):
        return None


def _batch_rounds_path(row: dict, package: str | Path | None = None) -> Path | None:
    summary = row.get("rounds_summary")
    path = summary.get("path") if isinstance(summary, dict) else None
    return _rounds_path_key(path or row.get("rounds_file"), package)


def _situation_queues(facts: dict, batch_view: dict) -> dict[str, list]:
    projection = facts.get("projection") or {}
    covered_returns = {row.get("return_id") for row in batch_view.get("return_assignments", [])
                       if isinstance(row, dict) and isinstance(row.get("return_id"), str)}
    queues = {}
    for name in ("blocking", "runnable", "withheld", "in_flight", "manual", "undetermined"):
        rows = projection.get(name, [])
        rows = rows if isinstance(rows, list) else []
        if name == "runnable":
            rows = [row for row in rows if not (
                isinstance(row, dict) and row.get("source") == "pending-review"
                and row.get("return_id") in covered_returns)]
        queues[name] = rows
    return queues


def derive_pipeline(facts: dict, batch_rows: list[dict] | None = None,
                    package: str | Path | None = None) -> list[dict]:
    state = facts.get("state")
    tickets = state.get("tickets", {}) if isinstance(state, dict) else {}
    ticket_states = [row.get("state") for row in tickets.values() if isinstance(row, dict)]
    all_terminal = bool(ticket_states) and all(value in {"SATISFIED", "RETIRED"} for value in ticket_states)
    has_active_ticket = any(value in {"PENDING", "NEEDS-REVALIDATION"} for value in ticket_states)
    has_blocked_ticket = "BLOCKED" in ticket_states
    projection, slugs = _projection_matches(facts)
    gate = ((projection or {}).get("sources") or {}).get("gate") or {}
    verdict = gate.get("verdict")
    projection_status = facts.get("projection_status")
    gate_authoritative_pass = (projection_status == "confirmed" and verdict == "pass"
                               and gate.get("error") is None)
    returns = facts.get("uncovered_returns", facts.get("pending_returns", []))
    batch_rows = batch_rows or []
    superseded_paths = {_batch_rounds_path(row, package) for row in batch_rows
                        if row.get("status") == "superseded"}
    superseded_paths.discard(None)
    rounds = [row for row in facts.get("rounds", [])
              if not isinstance(row, dict) or _rounds_path_key(row.get("path"), package) not in superseded_paths]
    rounds.extend(row["rounds_summary"] for row in batch_rows
                  if row.get("status") != "superseded" and isinstance(row.get("rounds_summary"), dict))
    final_rounds = [round_ for round_ in rounds if round_.get("phase") == "terminal-final"]
    final_paths = {_rounds_path_key(row.get("path"), package) for row in final_rounds}
    final_paths.discard(None)
    ambiguous_final_source = False
    if len(final_paths) > 1:
        owners_by_path = {
            path: {row.get("batch_id") for row in batch_rows
                   if row.get("status") != "superseded" and row.get("batch_id")
                   and _batch_rounds_path(row, package) == path}
            for path in final_paths
        }
        owners = set().union(*owners_by_path.values())
        ambiguous_final_source = (len(owners) != 1
                                  or any(len(path_owners) != 1 for path_owners in owners_by_path.values()))
    review = None if ambiguous_final_source else max(
        final_rounds, key=lambda item: item.get("open_seq", 0), default=None)
    review_converged = bool(review and review.get("converged"))
    review_failed = bool(review and any(track.get("verdict") in BAD_VERDICTS
                                        for track in review.get("tracks", [])
                                        if isinstance(track.get("verdict"), str)))
    acceptance_pending = any(isinstance(slug, str) and slug.startswith("attempt.accept.")
                             and slug != "attempt.accept.all-tickets-terminal" for slug in slugs)
    if facts.get("state_status") != "confirmed":
        intake = ("attention", "Package state 未确认")
        ticket_stage = ("attention", "Ticket 状态缺失或未确认")
    else:
        intake = (("active", "Situation 标出 intake backlog") if "package.record.intake-backlog" in slugs
                  else ("done", "state.json 与 Ticket 集合可读"))
        if not ticket_states:
            ticket_stage = ("attention", "没有可判定的 Ticket 状态")
        elif all_terminal:
            ticket_stage = ("done", "全部 Ticket 为 SATISFIED/RETIRED")
        elif has_active_ticket:
            ticket_stage = ("active", "仍有 PENDING/NEEDS-REVALIDATION Ticket")
        elif has_blocked_ticket:
            ticket_stage = ("blocked", "未完成 Ticket 均处于 BLOCKED")
        else:
            ticket_stage = ("attention", "Ticket 状态无法归类")
    open_batches = [row for row in batch_rows if row.get("status") == "open"]
    triaged_batches = [row for row in batch_rows if row.get("status") == "triaged"]
    if returns:
        review_stage = ("active", f"有 {len(returns)} 个未纳入有效审阅批次的 worker-return")
    elif open_batches:
        summary = open_batches[-1].get("rounds_summary")
        tracks = summary.get("tracks", []) if isinstance(summary, dict) else []
        tracks = tracks if isinstance(tracks, list) else []
        if isinstance(summary, dict) and summary.get("status") == "undetermined":
            review_stage = ("attention", "审阅批次 rounds 摘要损坏或无法确认")
        elif (isinstance(summary, dict) and summary.get("closed") is not True) or any(
                not isinstance(track, dict) or track.get("verdict") is None for track in tracks):
            review_stage = ("active", "等待审阅轨收齐并关闭轮次，不提前分诊")
        elif any(isinstance(track, dict) and track.get("verdict") in BAD_VERDICTS for track in tracks):
            review_stage = ("attention", "审阅轨存在异常 verdict，未收敛")
        elif isinstance(summary, dict) and summary.get("open_findings_count", 0) > 0:
            review_stage = ("attention", "审阅批次仍有 open findings，待主控分诊")
        elif isinstance(summary, dict) and summary.get("converged") is True:
            review_stage = ("active", "审阅轮次已收敛，待主控逐票核对并更新批次")
        else:
            review_stage = ("active", f"有 {len(open_batches)} 个 open 审阅批次处理中")
    elif triaged_batches:
        review_stage = ("attention", f"有 {len(triaged_batches)} 个已分诊批次待关闭")
    elif "attempt.review.terminal-coverage-incomplete" in slugs:
        review_stage = ("active", "Situation 要求补齐 terminal-final coverage")
    elif ambiguous_final_source:
        review_stage = ("attention", "多个 terminal-final 文件来源冲突或不明，请主控核对对应终审文件")
    elif review_converged:
        review_stage = ("done", "terminal-final 收齐 PASS 且无 open findings")
    elif review_failed:
        review_stage = ("attention", "审阅轨存在 FAIL/UNCERTAIN/INCOMPLETE")
    elif review and not review.get("closed"):
        review_stage = ("active", "terminal-final 轮次尚未关闭")
    elif review and review.get("open_findings_count"):
        review_stage = ("attention", "仍有未闭合 findings")
    elif review and review.get("reasons"):
        review_stage = ("attention", "审阅组未收敛：" + "; ".join(review["reasons"]))
    elif all_terminal:
        review_stage = ("attention", "缺少已确认的 terminal-final 收敛摘要")
    else:
        review_stage = ("pending", "Ticket 尚未全部收口")
    gate_signals = {"attempt.gate.verdict-undecided", "attempt.gate.durable-delta-missing"}
    gate_conflict_slugs = gate_signals | {"attempt.gate.missing", "attempt.review.terminal-coverage-incomplete"}
    gate_conflict = acceptance_pending or bool(slugs.intersection(gate_conflict_slugs))
    if projection_status != "confirmed" and not gate_authoritative_pass:
        verify_stage = ("attention", "Situation projection 未确认，不能确认最终验证")
    elif verdict == "pass" and gate_conflict:
        verify_stage = ("attention", "Gate pass 与当前 Situation 缺口冲突，需主控核对")
    elif gate_authoritative_pass:
        verify_stage = ("done", "Gate pass 证明最终验证已完成")
    elif review_converged and acceptance_pending:
        verify_stage = ("active", "Situation 标出未完成 acceptance/evidence")
    elif review_converged and (slugs.intersection(gate_signals) or bool(verdict)):
        verify_stage = ("done", "Situation 已推进至 Gate")
    elif review_converged and "attempt.gate.missing" in slugs:
        verify_stage = ("active", "终审已收敛，确认最终验证并准备 Gate")
    elif review_converged:
        verify_stage = ("active", "终审已收敛，等待最终验证事实")
    else:
        verify_stage = ("pending", "等待 terminal-final 审阅收敛")
    if projection_status != "confirmed" and not gate_authoritative_pass:
        gate_stage = ("attention", "Situation projection 未确认，不能确认 Gate 状态")
    elif verdict == "pass" and gate_conflict:
        gate_stage = ("attention", "Gate pass 与当前 Situation 缺口冲突，需主控核对")
    elif gate_authoritative_pass:
        gate_stage = ("done", "Gate verdict 为 pass")
    elif verdict in {"fail", "blocked", "defer"}:
        gate_stage = ("blocked", f"Gate verdict 为 {verdict}")
    elif verify_stage[0] == "done":
        gate_stage = ("active", "最终验证完成，等待 Gate")
    else:
        gate_stage = ("pending", "等待最终验证完成")
    closeout = (("attention", "Gate 已通过；没有可确认的 closeout 状态")
                if gate_authoritative_pass and not gate_conflict
                else ("pending", "等待 Gate 完成"))
    values = {"intake": intake, "tickets": ticket_stage, "final-review": review_stage,
              "final-verify": verify_stage, "gate": gate_stage, "closeout": closeout}
    return [{**stage, "status": values[stage["id"]][0], "reason": values[stage["id"]][1]}
            for stage in PIPELINE["stages"]]


def _next_step(facts: dict, stages: list[dict], batch_view: dict,
               situation: dict | None = None) -> dict:
    if facts.get("uncovered_returns", facts.get("pending_returns", [])):
        return {"command": "/impl-package:do-review", "reason": "派审未覆盖的 worker-return"}
    for row in batch_view.get("items", []):
        if row.get("alerts"):
            return {"command": "按票执行 evidence add", "reason": "；".join(row["alerts"])}
    for item in (situation or _situation_queues(facts, batch_view)).get("runnable", []):
        actions = item.get("actions", []) if isinstance(item, dict) else []
        if actions and isinstance(actions[0], dict) and actions[0].get("do"):
            return {"command": actions[0]["do"], "reason": item.get("reason", item.get("candidate_id", "Situation action"))}
    for row in reversed(batch_view.get("items", [])):
        if row.get("status") == "open":
            summary = row.get("rounds_summary") or {}
            if summary.get("status") == "undetermined":
                return {"command": "核对审阅批次 rounds 文件", "reason": f"{row.get('batch_id')} 摘要状态为 undetermined"}
            if summary.get("converged"):
                return {"command": "dev-loop batch update --status triaged",
                        "reason": f"{row.get('batch_id')} 已收敛；逐票核对并补充 ticket_notes 后更新状态"}
            return {"command": "/impl-package:do-review", "reason": f"继续处理 open 审阅批次 {row.get('batch_id')}"}
        if row.get("status") == "triaged":
            return {"command": "dev-loop batch close", "reason": f"{row.get('batch_id')} 已分诊，核对逐票备注后关闭批次"}
    commands = {"intake": "dev-with-track：核对 intake queue", "tickets": "/impl-package:dev-with-track",
                "final-review": "/impl-package:do-review phase=terminal-final",
                "final-verify": "/impl-package:dev-with-track Verify", "gate": "/impl-package:dev-with-track Gate",
                "closeout": "/impl-package:backfill-stable-docs"}
    current = next((stage for stage in stages if stage["status"] != "done"), stages[-1])
    return {"command": commands[current["id"]], "reason": current["reason"]}


def status_view(package: str | Path) -> dict:
    """Return the complete read-only package snapshot for either renderer."""
    profile, profile_error = load_profile(package)
    facts = read_facts(package)
    batch_view = batches.status_view(profile, facts.get("pending_returns", []), package)
    facts = {**facts, "pending_returns": batch_view["uncovered_returns"],
             "uncovered_returns": batch_view["uncovered_returns"]}
    stages = derive_pipeline(facts, batch_view["items"], package)
    situation = _situation_queues(facts, batch_view)
    state = facts.get("state")
    ticket_rows = state.get("tickets", {}) if isinstance(state, dict) else {}
    counts = {name: sum(1 for row in ticket_rows.values()
                        if isinstance(row, dict) and row.get("state") == name)
              for name in ("PENDING", "BLOCKED", "NEEDS-REVALIDATION", "SATISFIED", "RETIRED")}
    warnings = list(facts["warnings"])
    if profile_error:
        warnings.append(profile_error)
    agent_view = agents.status_view(profile)
    ticket_items = []
    for key, row in sorted(ticket_rows.items()):
        if isinstance(row, dict):
            item = {"id": key, "state": row.get("state")}
            item.update({name: row[name] for name in ("depends_on", "dependencies") if name in row})
            ticket_items.append(item)
    return {"package": str(Path(package).expanduser().absolute()), "pipeline": stages,
            "tickets": {"counts": counts, "items": ticket_items},
            "pending_returns": facts["uncovered_returns"], "uncovered_returns": facts["uncovered_returns"],
            "return_assignments": batch_view["return_assignments"], "review_rounds": facts["rounds"],
            "situation": situation, "agents": agent_view, "batches": batch_view["items"],
            "routing": profile["routing"], "routing_hint": "路由仅影响后续建议，不改写已有 agent 记录。",
            "projection_status": facts["projection_status"], "state_status": facts["state_status"],
            "warnings": warnings, "next_step": _next_step(facts, stages, batch_view, situation)}


def config_show(package: str | Path) -> dict:
    profile, warning = load_profile(package)
    return {"package": str(Path(package).expanduser().absolute()),
            "status": "undetermined" if warning else "confirmed", "profile": profile, "warning": warning}


def _writable_profile(package: str | Path) -> dict:
    profile, warning = load_profile(package)
    if warning:
        raise ValueError(f"profile 未确认，拒绝覆盖：{warning}")
    return profile


def config_set_route(package: str | Path, role: str, model: str, effort: str | None = None) -> dict:
    if not role.strip() or not model.strip() or (effort is not None and not effort.strip()):
        raise ValueError("role/model/effort 必须是非空字符串")
    profile = _writable_profile(package)
    route = dict(profile["routing"].get(role, {}))
    route["model"] = model.strip()
    if effort is not None:
        route["effort"] = effort.strip()
    profile["routing"][role] = route
    save_profile(package, profile)
    return config_show(package)


def agent_register(package: str | Path, values: dict) -> dict:
    profile = _writable_profile(package)
    record = agents.register(profile, values)
    save_profile(package, profile)
    return record


def agent_update(package: str | Path, agent_id: str, changes: dict) -> dict:
    profile = _writable_profile(package)
    record = agents.update(profile, agent_id, changes)
    save_profile(package, profile)
    return record


def agent_replace(package: str | Path, agent_id: str, values: dict,
                  new_id: str | None, handoff_note: str) -> dict:
    profile = _writable_profile(package)
    result = agents.replace(profile, agent_id, values, new_id, handoff_note)
    save_profile(package, profile)
    return result


def agent_list(package: str | Path) -> dict:
    profile, warning = load_profile(package)
    return {"package": str(Path(package).expanduser().absolute()),
            "status": "undetermined" if warning else "confirmed", "warning": warning,
            **agents.status_view(profile)}


def batch_register(package: str | Path, values: dict) -> dict:
    profile = _writable_profile(package)
    record = batches.register(profile, values)
    save_profile(package, profile)
    return record


def batch_update(package: str | Path, batch_id: str, changes: dict) -> dict:
    profile = _writable_profile(package)
    record = batches.update(profile, batch_id, changes)
    save_profile(package, profile)
    return record


def batch_close(package: str | Path, batch_id: str) -> dict:
    profile = _writable_profile(package)
    record = batches.close(profile, batch_id)
    save_profile(package, profile)
    return record


def batch_list(package: str | Path) -> dict:
    profile, warning = load_profile(package)
    return {"package": str(Path(package).expanduser().absolute()),
            "status": "undetermined" if warning else "confirmed", "warning": warning,
            "batches": batches.list_batches(profile)}
