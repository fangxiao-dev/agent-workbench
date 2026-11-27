"""Human-readable views for the dev-loop CLI; JSON stays in the CLI layer."""

from __future__ import annotations

import json


def _scope_text(scope: object) -> str:
    if isinstance(scope, list):
        return ",".join(str(item) for item in scope)
    return str(scope) if scope else "未关联"


def _queue_item_label(item: object) -> str:
    if not isinstance(item, dict):
        return str(item)
    return str(item.get("slug") or item.get("candidate_id") or item.get("dispatch_id")
               or item.get("return_id") or item.get("subject") or "项目")


def status_text(snapshot: dict) -> str:
    lines = [f"Package: {snapshot['package']}", "Pipeline:"]
    lines.extend(
        f"- {stage['label']} ({stage['id']}): {stage['status']} — {stage['reason']}"
        for stage in snapshot["pipeline"]
    )
    counts = ", ".join(f"{name}={count}" for name, count in snapshot["tickets"]["counts"].items())
    lines.append(f"Tickets: {counts}")
    queues = snapshot.get("situation", {})
    queue_labels = (("blocking", "blocking"), ("runnable", "runnable"), ("in_flight", "in_flight"),
                    ("withheld", "withheld"), ("manual", "manual"), ("undetermined", "undetermined"))
    populated = [(key, label, queues.get(key, [])) for key, label in queue_labels if queues.get(key)]
    if populated:
        lines.append("Situation 队列: " + " ".join(f"{label}={len(items)}" for _, label, items in populated))
        details = []
        for _, label, items in populated:
            names = [_queue_item_label(item) for item in items[:2]]
            if len(items) > 2:
                names.append(f"…+{len(items) - 2}")
            details.append(f"{label}: {', '.join(names)}")
        lines.append("Situation 摘要: " + "; ".join(details))
    returns = snapshot.get("uncovered_returns", snapshot.get("pending_returns", []))
    lines.append(f"未覆盖待审 returns: {len(returns)}")
    for item in returns:
        lines.append(f"- {item.get('return_id') or item.get('candidate_id')}: {item.get('subject', 'scope 未知')}")
    lines.append(f"审阅轮次: {len(snapshot['review_rounds'])}")
    for round_ in snapshot["review_rounds"]:
        verdicts = ", ".join(f"{track['track']}={track['verdict']}" for track in round_["tracks"])
        convergence = "收敛" if round_["converged"] else "未收敛"
        lines.append(f"- {round_['group']} #{round_['round']} {round_['phase']}: {verdicts or '无轨道'}; {convergence}")
        lines.extend(f"  原因: {reason}" for reason in round_["reasons"])

    agent_view = snapshot.get("agents", {})
    active_agents = agent_view.get("active", [])
    lines.append(f"Agent 池: {len(active_agents)} 个活跃 / {len(agent_view.get('items', []))} 条记录")
    for row in agent_view.get("items", []):
        lines.append(f"- {row.get('id')}: {row.get('role')} scope={_scope_text(row.get('scope'))} "
                     f"host={row.get('host')} agent_id={row.get('agent_id') or 'unconfirmed'} "
                     f"model={row.get('model') or '未登记'} effort={row.get('effort') or '未登记'} "
                     f"status={row.get('status')}")
        if row.get("replaced_by"):
            lines.append(f"  replaced_by={row['replaced_by']}; handoff={row.get('handoff_note') or '未登记'}")
    lines.append("续用推荐:")
    recommendations = agent_view.get("reuse_recommendations", [])
    lines.extend(f"- {item['scope']} / {item['role']}: "
                 + ", ".join(row.get("id", "?") for row in item.get("agents", []))
                 for item in recommendations)
    if not recommendations:
        lines.append("- 暂无")
    previous = agent_view.get("previous_reviewers", [])
    lines.append("前驱审阅者（组织新审阅组时提醒保持独立性）:")
    lines.extend(f"- {row.get('id')}: scope={_scope_text(row.get('scope'))} "
                 f"host={row.get('host')} agent_id={row.get('agent_id') or 'unconfirmed'} "
                 f"status={row.get('status')} group={row.get('review_group') or '未登记'}"
                 for row in previous)
    if not previous:
        lines.append("- 暂无已知审阅者")

    batch_rows = snapshot.get("batches", [])
    lines.append(f"审阅批次: {len(batch_rows)}")
    for row in batch_rows:
        lines.append(f"- {row.get('batch_id')}: {row.get('status')} tickets={','.join(row.get('tickets', [])) or '无'} "
                     f"returns={','.join(row.get('returns', [])) or '无'} "
                     f"snapshot={row.get('snapshot_kind')} head={row.get('reviewed_head') or '未登记'}")
        if row.get("covered_returns"):
            lines.append("  已归入批次: " + ", ".join(row["covered_returns"]))
        summary = row.get("rounds_summary")
        if isinstance(summary, dict):
            verdicts = ", ".join(f"{item.get('track')}={item.get('verdict') or 'unconfirmed'}"
                                  for item in summary.get("tracks", []))
            convergence = "收敛" if summary.get("converged") else summary.get("status", "unconfirmed")
            lines.append(f"  rounds: #{summary.get('round') or 'unconfirmed'} {summary.get('phase') or 'unconfirmed'}; "
                         f"{verdicts or '无 verdict'}; open findings={summary.get('open_findings_count', 0)}; {convergence}")
            lines.extend(f"  rounds 提示: {reason}" for reason in summary.get("reasons", []))
        notes = row.get("ticket_notes", {})
        if isinstance(notes, dict):
            lines.extend(f"  {ticket} 主控备注: {note}" for ticket, note in notes.items())
        lines.extend(f"  提醒: {alert}" for alert in row.get("alerts", []))

    routing = snapshot["routing"]
    lines.append("模型路由: " + (json.dumps(routing, ensure_ascii=False) if routing else "未配置"))
    lines.append(snapshot["routing_hint"])
    lines.append(f"下一步: {snapshot['next_step']['command']} — {snapshot['next_step']['reason']}")
    if snapshot["warnings"]:
        lines.append("读取提示: " + "; ".join(snapshot["warnings"]))
    return "\n".join(lines)


def config_text(result: dict) -> str:
    lines = [f"Package: {result['package']} (profile {result['status']})"]
    routes = result["profile"]["routing"]
    lines.append("模型路由:")
    lines.extend(f"- {role}: {route}" for role, route in sorted(routes.items()))
    if not routes:
        lines.append("尚未配置模型路由。")
    if result.get("warning"):
        lines.append(f"读取提示: {result['warning']}")
    return "\n".join(lines)


def agent_text(result: dict) -> str:
    lines = [f"Package: {result['package']} (profile {result.get('status', 'unconfirmed')})", "Agents:"]
    for row in result.get("items", []):
        lines.append(f"- {row.get('id')}: {row.get('role')} scope={_scope_text(row.get('scope'))} "
                     f"host={row.get('host')} agent_id={row.get('agent_id') or 'unconfirmed'} "
                     f"status={row.get('status')} model={row.get('model') or '未登记'} "
                     f"effort={row.get('effort') or '未登记'}")
    if not result.get("items"):
        lines.append("- 暂无 agent 记录")
    if result.get("warning"):
        lines.append(f"读取提示: {result['warning']}")
    return "\n".join(lines)


def batch_text(result: dict) -> str:
    lines = [f"Package: {result['package']} (profile {result.get('status', 'unconfirmed')})", "Batches:"]
    for row in result.get("batches", []):
        lines.append(f"- {row.get('batch_id')}: {row.get('status')} tickets={','.join(row.get('tickets', [])) or '无'} "
                     f"returns={','.join(row.get('returns', [])) or '无'} snapshot={row.get('snapshot_kind')}")
        notes = row.get("ticket_notes", {})
        if isinstance(notes, dict):
            lines.extend(f"  {ticket} 主控备注: {note}" for ticket, note in notes.items())
    if not result.get("batches"):
        lines.append("- 暂无审阅批次")
    if result.get("warning"):
        lines.append(f"读取提示: {result['warning']}")
    return "\n".join(lines)
