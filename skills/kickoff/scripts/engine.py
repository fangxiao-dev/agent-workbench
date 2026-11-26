"""Pipeline loader, state I/O, and gate evaluation engine for kickoff."""

import json
import os
import sys
from datetime import datetime, timezone

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
PIPELINE_PATH = os.path.join(SKILL_DIR, "pipeline.json")
CLI_SCRIPT_PATH = os.path.join(SCRIPTS_DIR, "kickoff.py")

STATE_FILENAME = "kickoff-state.json"
DEFAULT_STAGING_DIR = os.path.join(".", "output", "kickoff")


def load_pipeline(path=PIPELINE_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


PIPELINE = load_pipeline()
STAGES = {s["id"]: s for s in PIPELINE["stages"]}
PRINCIPLES = {s["id"]: s["principles"] for s in PIPELINE["stages"]}
TRIAGE_STAGES = [s["id"] for s in PIPELINE["stages"] if s["triage"]]
ADVANCE_TARGETS = [s["id"] for s in PIPELINE["stages"] if s["id"] != PIPELINE["initial"]]
GATE_LABELS = PIPELINE.get("gate_labels", {})
FLOW = PIPELINE.get("flow_help", "")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fail(msg, code=2):
    print(f"错误: {msg}", file=sys.stderr)
    sys.exit(code)


def load_state(path):
    if not path or not os.path.isfile(path):
        fail(f"状态文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path, state):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def add_history(state, action, **extra):
    entry = {"action": action, "ts": now()}
    entry.update(extra)
    state.setdefault("history", []).append(entry)


def resolve_state_path(args):
    pkg = getattr(args, "pkg", None)
    state = getattr(args, "state", None)
    if pkg and state:
        fail("--pkg 与 --state 只能选其一")
    if not pkg and not state:
        fail("必须提供 --pkg <dir> 或 --state <path>")
    if pkg:
        return os.path.join(pkg, STATE_FILENAME)
    return state


def rounds_for(state, stage):
    return [r for r in state.get("rounds", []) if r.get("stage") == stage]


def _matches_when(when, switches):
    return all(switches.get(k) == v for k, v in when.items())


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
        rs = rounds_for(state, src_stage)
        if rs and rs[-1].get("verdict") != "clean":
            verdict = rs[-1].get("verdict") or "open"
            return (
                f"{src_stage} 阶段最后一轮（#{rs[-1]['round']}）结论为 {verdict}，"
                f"尚未清零：复验通过后再记录 round --stage {src_stage} --verdict clean"
            )
    else:
        raise ValueError(f"未知门禁标识: {gate}")
    return None


def _active_outgoing(stage, switches):
    return [
        t for t in PIPELINE["transitions"]
        if t["src"] == stage and _matches_when(t["when"], switches)
    ]


def next_command(state, state_path, script_path=CLI_SCRIPT_PATH):
    stage = state["stage"]
    sw = state["switches"]
    p = f"python {os.path.abspath(script_path)}"
    pkg_dir = state.get("pkg_dir")
    loc = f"--pkg {pkg_dir}" if pkg_dir else f"--state {os.path.abspath(state_path)}"

    outgoing = _active_outgoing(stage, sw)
    if not outgoing:
        return "已完成 kickoff，可进入下游执行阶段。"

    edge = outgoing[0]
    for gate in edge["gates"]:
        if gate == "owner_confirmed" and not state.get("owner_confirmed"):
            return f"{p} confirm {loc}"
        if gate == "pkg_bound" and not pkg_dir:
            return f"{p} bind-pkg --state {os.path.abspath(state_path)} --pkg <包目录>"
        if gate == "role:pe?" and sw.get("pe") and not state.get("agents", {}).get("pe"):
            return f"{p} register {loc} --role pe --agent-id <pe-agent-id>"
        if gate == "role:reviewer" and not state.get("agents", {}).get("reviewer"):
            return f"{p} register {loc} --role reviewer --agent-id <reviewer-agent-id>"
        if gate == "role:plan-reviewer" and not state.get("agents", {}).get("plan_reviewers"):
            return f"{p} register {loc} --role plan-reviewer --agent-id <plan-reviewer-agent-id>"
        if gate == "rounds>=1" and len(rounds_for(state, stage)) < 1:
            return (
                f"{p} round {loc} --stage {stage} "
                '--verdict open|clean --summary "<本轮分诊摘要>"'
            )
        if gate == "last_round_clean":
            rs = rounds_for(state, stage)
            if rs and rs[-1].get("verdict") != "clean":
                return (
                    f"{p} round {loc} --stage {stage} "
                    '--verdict clean --summary "<复验清零摘要>"'
                )

    return f"{p} advance {edge['dst']} {loc}"


def gate_advance(state, target, artifacts):
    errs = []
    sw = state["switches"]
    stage = state["stage"]

    confirm_err = _check_gate("owner_confirmed", state, stage)
    if confirm_err:
        errs.append(confirm_err)

    for art in artifacts:
        if not os.path.exists(art):
            errs.append(f"声明的阶段产出不存在: {art}")

    candidates = [t for t in PIPELINE["transitions"] if t["dst"] == target]
    active = [t for t in candidates if _matches_when(t["when"], sw)]

    if not active:
        sw_name = STAGES[target].get("optional_switch")
        if sw_name:
            errs.append(f"{sw_name} 环节已关闭（switches.{sw_name}=false）")
        else:
            errs.append(f"当前开关配置下无法进入 {target}")
        return errs

    matched = next((t for t in active if t["src"] == stage), None)
    if matched is None:
        expected = " / ".join(t["src"] for t in active)
        errs.append(f"当前阶段为 {stage}，进入 {target} 需处于 {expected}")
        chosen = active[0]
    else:
        chosen = matched

    for gate in chosen["gates"]:
        if gate == "owner_confirmed":
            continue
        err = _check_gate(gate, state, chosen["src"])
        if err:
            errs.append(err)

    return errs
