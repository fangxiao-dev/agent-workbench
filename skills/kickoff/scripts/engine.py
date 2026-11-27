"""Pipeline loading, state transitions, and kickoff command logic."""

import json
import os

from .store import (
    DEFAULT_STAGING_DIR,
    STATE_FILENAME,
    add_history,
    load_state,
    now,
    resolve_state_path,
    rounds_for,
    save_state,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
PIPELINE_PATH = os.path.join(SKILL_DIR, "pipeline.json")
CLI_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "kickoff.py")


class KickoffError(Exception):
    def __init__(self, message, code=2, raw=False):
        super().__init__(message)
        self.code = code
        self.raw = raw


class GateBlocked(KickoffError):
    def __init__(self, target, errors):
        self.target = target
        self.errors = errors
        super().__init__(f"无法进入 {target}", code=1)


def load_pipeline(path=PIPELINE_PATH):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取 pipeline.json：{error}") from error


PIPELINE = load_pipeline()
STAGES = {stage["id"]: stage for stage in PIPELINE["stages"]}
PRINCIPLES = {stage["id"]: stage["principles"] for stage in PIPELINE["stages"]}
OPTIONAL_TOOLS = {
    stage["id"]: stage.get("optional_tools", []) for stage in PIPELINE["stages"]
}
TRIAGE_STAGES = [stage["id"] for stage in PIPELINE["stages"] if stage["triage"]]
ADVANCE_TARGETS = [
    stage["id"] for stage in PIPELINE["stages"] if stage["id"] != PIPELINE["initial"]
]
GATE_LABELS = PIPELINE.get("gate_labels", {})
FLOW = PIPELINE.get("flow_help", "")


def _matches_when(when, switches):
    return all(switches.get(key) == value for key, value in when.items())


def _check_gate(gate, state, src_stage):
    if gate == "owner_confirmed":
        if not state.get("owner_confirmed"):
            return "尚未 Owner 确认：先运行 confirm（owner_confirmed=false）"
    elif gate == "pkg_bound":
        if not state.get("pkg_dir"):
            return "包目录未绑定：先运行 bind-pkg 或在 init 时用 --pkg"
    elif gate == "role:pe?":
        if state["switches"].get("pe") and not state.get("agents", {}).get("pe"):
            return "PE 未登记：先运行 register --role pe"
    elif gate == "role:reviewer":
        if not state.get("agents", {}).get("reviewer"):
            return "未登记 reviewer：先运行 register --role reviewer"
    elif gate == "role:plan-reviewer":
        if not state.get("agents", {}).get("plan_reviewers"):
            return "未登记 plan-reviewer：先运行 register --role plan-reviewer --agent-id <id>"
    elif gate == "rounds>=1":
        if len(rounds_for(state, src_stage)) < 1:
            return f"{src_stage} 阶段尚无分诊轮次：先运行 round --stage {src_stage}"
    elif gate == "last_round_clean":
        rounds = rounds_for(state, src_stage)
        if rounds and rounds[-1].get("verdict") != "clean":
            verdict = rounds[-1].get("verdict") or "open"
            return (
                f"{src_stage} 阶段最后一轮（#{rounds[-1]['round']}）结论为 {verdict}，"
                f"尚未清零：复验通过后再记录 round --stage {src_stage} --verdict clean"
            )
    else:
        raise ValueError(f"未知门禁标识: {gate}")
    return None


def _active_outgoing(stage, switches):
    return [
        transition
        for transition in PIPELINE["transitions"]
        if transition["src"] == stage and _matches_when(transition["when"], switches)
    ]


def next_command(state, state_path, script_path=CLI_SCRIPT_PATH):
    stage = state["stage"]
    switches = state["switches"]
    command = f"python {os.path.abspath(script_path)}"
    package = state.get("pkg_dir")
    location = f"--pkg {package}" if package else f"--state {os.path.abspath(state_path)}"

    outgoing = _active_outgoing(stage, switches)
    if not outgoing:
        return "已完成 kickoff，可进入下游执行阶段。"

    edge = outgoing[0]
    for gate in edge["gates"]:
        if gate == "owner_confirmed" and not state.get("owner_confirmed"):
            return f"{command} confirm {location}"
        if gate == "pkg_bound" and not package:
            return f"{command} bind-pkg --state {os.path.abspath(state_path)} --pkg <包目录>"
        if gate == "role:pe?" and switches.get("pe") and not state.get("agents", {}).get("pe"):
            return f"{command} register {location} --role pe --agent-id <pe-agent-id>"
        if gate == "role:reviewer" and not state.get("agents", {}).get("reviewer"):
            return f"{command} register {location} --role reviewer --agent-id <reviewer-agent-id>"
        if gate == "role:plan-reviewer" and not state.get("agents", {}).get("plan_reviewers"):
            return f"{command} register {location} --role plan-reviewer --agent-id <plan-reviewer-agent-id>"
        if gate == "rounds>=1" and len(rounds_for(state, stage)) < 1:
            return (
                f"{command} round {location} --stage {stage} "
                '--verdict open|clean --summary "<本轮分诊摘要>"'
            )
        if gate == "last_round_clean":
            rounds = rounds_for(state, stage)
            if rounds and rounds[-1].get("verdict") != "clean":
                return (
                    f"{command} round {location} --stage {stage} "
                    '--verdict clean --summary "<复验清零摘要>"'
                )

    return f"{command} advance {edge['dst']} {location}"


def gate_advance(state, target, artifacts):
    errors = []
    switches = state["switches"]
    stage = state["stage"]

    confirm_error = _check_gate("owner_confirmed", state, stage)
    if confirm_error:
        errors.append(confirm_error)

    for artifact in artifacts:
        if not os.path.exists(artifact):
            errors.append(f"声明的阶段产出不存在: {artifact}")

    candidates = [transition for transition in PIPELINE["transitions"] if transition["dst"] == target]
    active = [transition for transition in candidates if _matches_when(transition["when"], switches)]

    if not active:
        optional_switch = STAGES[target].get("optional_switch")
        if optional_switch:
            errors.append(f"{optional_switch} 环节已关闭（switches.{optional_switch}=false）")
        else:
            errors.append(f"当前开关配置下无法进入 {target}")
        return errors

    matched = next((transition for transition in active if transition["src"] == stage), None)
    if matched is None:
        expected = " / ".join(transition["src"] for transition in active)
        errors.append(f"当前阶段为 {stage}，进入 {target} 需处于 {expected}")
        chosen = active[0]
    else:
        chosen = matched

    for gate in chosen["gates"]:
        if gate == "owner_confirmed":
            continue
        error = _check_gate(gate, state, chosen["src"])
        if error:
            errors.append(error)

    return errors


def init(args):
    research = args.research
    for value in research:
        if value != "none" and not value.strip():
            raise KickoffError("--research 不能为空白（无材料请显式传 none）")
    prototype = args.prototype
    if prototype != "none" and not prototype.strip():
        raise KickoffError("--prototype 不能为空白（无原型请显式传 none）")

    switches = {
        "discover": args.discover == "on",
        "pe": args.pe == "on",
        "plan": args.plan == "on",
    }
    if args.pkg:
        base_dir = os.path.abspath(args.pkg)
        state_path = os.path.join(base_dir, STATE_FILENAME)
        pkg_dir = base_dir
        staging_path = None
        slug = None
    else:
        slug = args.slug
        state_path = os.path.join(args.staging_dir, f"{slug}.json")
        pkg_dir = None
        staging_path = os.path.abspath(state_path)

    if os.path.exists(state_path) and not args.force:
        raise KickoffError(f"状态文件已存在: {state_path}（用 --force 覆盖）")

    state = {
        "slug": slug,
        "goal": args.goal or "",
        "docs": args.docs or [],
        "inputs": {"research": research, "prototype": prototype},
        "switches": switches,
        "stage": PIPELINE["initial"],
        "owner_confirmed": False,
        "confirmed_at": None,
        "pkg_dir": pkg_dir,
        "staging_path": staging_path,
        "agents": {"pe": None, "reviewer": None, "plan_reviewers": []},
        "rounds": [],
        "history": [],
    }
    add_history(state, "init", pkg_dir=pkg_dir, staging_path=staging_path)
    save_state(state_path, state)
    return {
        "path": os.path.abspath(state_path),
        "state": state,
        "principles": PRINCIPLES[PIPELINE["initial"]],
        "research": research,
        "prototype": prototype,
        "next_command": next_command(state, state_path),
    }


def confirm(args):
    path = resolve_state_path(args)
    state = load_state(path)
    already_confirmed = bool(state.get("owner_confirmed"))
    if not already_confirmed:
        state["owner_confirmed"] = True
        state["confirmed_at"] = now()
        add_history(state, "confirm", note=args.note or "")
        save_state(path, state)
    return {
        "already_confirmed": already_confirmed,
        "next_command": next_command(state, path),
    }


def register(args):
    path = resolve_state_path(args)
    state = load_state(path)
    role = args.role
    agent_id = (args.agent_id or "").strip()
    if not agent_id:
        raise KickoffError("--agent-id 不能为空")

    if role == "plan-reviewer":
        label = (args.label or "").strip()
        pool = state.setdefault("agents", {}).setdefault("plan_reviewers", [])
        existing = next((item for item in pool if item.get("agent_id") == agent_id), None)
        if existing is not None:
            if label:
                existing["label"] = label
            add_history(state, "register", role=role, agent_id=agent_id, label=label or None)
            save_state(path, state)
            return {
                "kind": "plan-reviewer-existing",
                "agent_id": agent_id,
                "label": existing.get("label"),
                "count": len(pool),
            }
        entry = {"agent_id": agent_id}
        if label:
            entry["label"] = label
        pool.append(entry)
        add_history(state, "register", role=role, agent_id=agent_id, label=label or None)
        save_state(path, state)
        return {
            "kind": "plan-reviewer-added",
            "agent_id": agent_id,
            "label": label,
            "count": len(pool),
        }

    agents = state.setdefault("agents", {})
    previous = agents.get(role)
    agents[role] = agent_id
    add_history(state, "register", role=role, agent_id=agent_id, previous=previous or None)
    save_state(path, state)
    return {"kind": "role", "role": role, "agent_id": agent_id, "previous": previous}


def bind_pkg(args):
    source = args.state
    state = load_state(source)
    package = os.path.abspath(args.pkg)
    os.makedirs(package, exist_ok=True)
    destination = os.path.join(package, STATE_FILENAME)
    if os.path.exists(destination) and not args.force:
        raise KickoffError(f"目标状态已存在: {destination}（用 --force 覆盖）")
    state["pkg_dir"] = package
    state["staging_path"] = None
    add_history(state, "bind", source=os.path.abspath(source), target=destination)
    save_state(destination, state)
    if os.path.abspath(source) != os.path.abspath(destination) and os.path.exists(source):
        os.remove(source)
    return {
        "package": package,
        "path": destination,
        "next_command": next_command(state, destination),
    }


def record_round(args):
    path = resolve_state_path(args)
    state = load_state(path)
    stage = args.stage
    if stage != state["stage"] and not args.backfill:
        raise KickoffError(
            f"当前阶段为 {state['stage']}，不能记录 {stage} 阶段分诊"
            "（如确需补录历史阶段，请显式传 --backfill）"
        )
    if stage == "plan":
        if not state.get("agents", {}).get("plan_reviewers"):
            raise KickoffError("未登记 plan-reviewer：先运行 register --role plan-reviewer --agent-id <id>")
    elif not state.get("agents", {}).get("reviewer"):
        raise KickoffError("未登记 reviewer：先运行 register --role reviewer --agent-id <id>")

    summary = (args.summary or "").strip()
    if not summary:
        raise KickoffError("--summary 不能为空，请记录本轮分诊摘要")
    for name in ("added", "cut", "pe", "rejected"):
        if getattr(args, name) < 0:
            raise KickoffError(f"--{name} 必须是非负整数")

    same = rounds_for(state, stage)
    number = len(same) + 1
    entry = {
        "stage": stage,
        "round": number,
        "verdict": args.verdict,
        "counts": {
            "added": args.added,
            "cut": args.cut,
            "pe": args.pe,
            "rejected": args.rejected,
        },
        "summary": summary,
        "ts": now(),
    }
    if args.backfill:
        entry["backfill"] = True
    if args.touched_upstream:
        entry["touched_upstream"] = True
    state.setdefault("rounds", []).append(entry)
    add_history(
        state,
        "round",
        stage=stage,
        round=number,
        verdict=args.verdict,
        backfill=args.backfill or None,
        touched_upstream=args.touched_upstream or None,
    )
    save_state(path, state)

    limit = PIPELINE["convergence_limit"]
    recent = same[-(limit - 1):] + [entry] if limit > 1 else [entry]
    return {
        "stage": stage,
        "entry": entry,
        "touched_upstream": args.touched_upstream,
        "convergence_warning": (
            len(recent) == limit and all(round_["counts"]["added"] > 0 for round_ in recent)
        ),
        "convergence_limit": limit,
        "high_round_reminder": number >= PIPELINE.get("high_round_limit", 4),
        "next_command": next_command(state, path),
    }


def advance(args):
    path = resolve_state_path(args)
    state = load_state(path)
    target = args.target
    artifacts = args.artifact or []
    errors = gate_advance(state, target, artifacts)
    if errors:
        raise GateBlocked(target, errors)

    previous = state["stage"]
    state["stage"] = target
    if artifacts:
        state.setdefault("artifacts", {})[previous] = [os.path.abspath(item) for item in artifacts]
    add_history(state, "advance", source=previous, target=target, artifacts=artifacts or None)
    save_state(path, state)
    return {
        "previous": previous,
        "target": target,
        "skills": STAGES[target].get("skills") or [],
        "principles": PRINCIPLES[target],
        "optional_tools": OPTIONAL_TOOLS.get(target, []),
        "next_command": next_command(state, path),
    }


def status(args):
    path = resolve_state_path(args)
    state = load_state(path)
    stage = state["stage"]
    return {
        "path": os.path.abspath(path),
        "state": state,
        "skills": STAGES.get(stage, {}).get("skills") or [],
        "principles": PRINCIPLES.get(stage, []),
        "optional_tools": OPTIONAL_TOOLS.get(stage, []),
        "triage_rounds": [
            {"stage": triage_stage, "rounds": rounds_for(state, triage_stage)}
            for triage_stage in TRIAGE_STAGES
            if rounds_for(state, triage_stage)
        ],
        "next_command": next_command(state, path),
    }
