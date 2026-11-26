#!/usr/bin/env python3
"""Deterministic kickoff state machine.

Single source of truth: PIPELINE defines stages, transitions, switches, gates,
triage loops, and per-stage principles. Both the runtime gate engine and the
Mermaid diagram generator read directly from PIPELINE. Only Python 3 stdlib is
used.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

STATE_FILENAME = "kickoff-state.json"
DEFAULT_STAGING_DIR = os.path.join(".", "output", "kickoff")

DIAGRAM_BEGIN = "<!-- BEGIN:PIPELINE_DIAGRAM -->"
DIAGRAM_END = "<!-- END:PIPELINE_DIAGRAM -->"

# ------------------------------------------------------------------ PIPELINE
# Single source of truth for both runtime execution and diagram generation.

PIPELINE = {
    "name": "kickoff",
    "initial": "init",
    "terminal": "ready",
    "convergence_limit": 2,
    "high_round_limit": 4,
    "stages": [
        {
            "id": "init",
            "label": "init",
            "note": "唯一必停点: confirm",
            "optional_switch": None,
            "triage": False,
            "principles": [
                "向 Owner 复述目标、输入清单、环节开关与代理分工，等 Owner 明确确认后再推进（全程唯一必停点）。",
                "把已有文档/记忆里已回答的部分先列出来，不重复劳动。",
                "不把假设当结论：不确定的写成待确认项，而不是直接写成决定。",
            ],
        },
        {
            "id": "discover",
            "label": "discover",
            "note": "可选, 默认 on",
            "optional_switch": "discover",
            "triage": False,
            "principles": [
                "先读材料与原型梳理未知项；本阶段不建包、不写 Decision/Spec。",
                "有 PE 时未知项先交 PE 收敛，仅业务取舍升级 Owner。",
                "记录冲突与缺口，产出可供 decision 阶段直接使用的依据。",
            ],
        },
        {
            "id": "decision",
            "label": "decision",
            "note": None,
            "optional_switch": None,
            "triage": True,
            "principles": [
                "有原型时先按主题写“原型基线”，再逐条写差异与理由。",
                "角色=权限集合，不把“某角色能否操作”当独立业务分支。",
                "交 Owner 裁定的事项必须已有 PE 判定。",
                "审阅意见先四类分诊（往下钻 / 根部裁剪+人工兜底 / 交 PE / 驳回），不照单全收。",
                "外部/合规确认（如税务师书面确认）做成上线前门控开关，不阻塞 Decision/Spec。",
            ],
        },
        {
            "id": "spec",
            "label": "spec",
            "note": None,
            "optional_switch": None,
            "triage": True,
            "principles": [
                "严格对齐已过门的 Decision 与原型，不新增未过门的行为合同。",
                "改动现行规则、接口、表约束或测试入口前，先核现行代码与规则分册，不凭记忆写。",
                "每次修订同步核对 spec.md（正文 / Rule Matrix / Journeys）与 contract-design.md 口径一致，先过 check-spec 等确定性校验再交 reviewer 复验。",
                "续用同一 reviewer；审阅回来先分诊再改。",
                "连续两轮都在加分支，就停下来回看原型并过 PE，判断能否从根部裁剪。",
            ],
        },
        {
            "id": "plan",
            "label": "plan",
            "note": "可选, 默认 on",
            "optional_switch": "plan",
            "triage": True,
            "principles": [
                "续用同一 reviewer 审实施计划。",
                "计划切块遵循 Spec 合同边界，不自行发明行为合同。",
                "每块给出验证方式与依赖顺序。",
            ],
        },
        {
            "id": "ready",
            "label": "ready",
            "note": None,
            "optional_switch": None,
            "triage": False,
            "principles": [
                "用人话向 Owner 汇报：做什么 / 不做什么。",
                "标出关键决定，PE 拍板项单独标注。",
                "给出计划分块与顺序。",
                "列出仍待 Owner 定事项（在哪 / 现状 / 为什么 / 建议），一句话结论：可以开工 / 还差什么。",
            ],
        },
    ],
    "transitions": [
        {
            "src": "init",
            "dst": "discover",
            "when": {"discover": True},
            "gates": ["owner_confirmed"],
            "style": "solid",
        },
        {
            "src": "init",
            "dst": "decision",
            "when": {"discover": False},
            "gates": ["owner_confirmed", "pkg_bound", "role:pe?"],
            "style": "dashed",
        },
        {
            "src": "discover",
            "dst": "decision",
            "when": {"discover": True},
            "gates": ["owner_confirmed", "pkg_bound", "role:pe?"],
            "style": "solid",
        },
        {
            "src": "decision",
            "dst": "spec",
            "when": {},
            "gates": ["owner_confirmed", "role:reviewer", "rounds>=1", "last_round_clean"],
            "style": "solid",
        },
        {
            "src": "spec",
            "dst": "plan",
            "when": {"plan": True},
            "gates": ["owner_confirmed", "role:reviewer", "rounds>=1", "last_round_clean"],
            "style": "solid",
        },
        {
            "src": "spec",
            "dst": "ready",
            "when": {"plan": False},
            "gates": ["owner_confirmed", "rounds>=1", "last_round_clean"],
            "style": "dashed",
        },
        {
            "src": "plan",
            "dst": "ready",
            "when": {"plan": True},
            "gates": ["owner_confirmed", "rounds>=1", "last_round_clean"],
            "style": "solid",
        },
    ],
}

STAGES = {s["id"]: s for s in PIPELINE["stages"]}
PRINCIPLES = {s["id"]: s["principles"] for s in PIPELINE["stages"]}
TRIAGE_STAGES = [s["id"] for s in PIPELINE["stages"] if s["triage"]]
ADVANCE_TARGETS = [s["id"] for s in PIPELINE["stages"] if s["id"] != PIPELINE["initial"]]

GATE_LABELS = {
    "owner_confirmed": "owner_confirmed",
    "pkg_bound": "pkg_bound",
    "role:pe?": "pe(if on)",
    "role:reviewer": "reviewer",
    "rounds>=1": "rounds>=1",
    "last_round_clean": "last=clean",
}

FLOW = """\
流程：
  init -> confirm -> discover(可选,默认on) -> bind-pkg -> decision -> spec -> plan(可选,默认on) -> ready

职责分工：
  - kickoff       管编排与输入契约：状态机、角色登记、分诊轮次、阶段门禁、阶段原则。
  - impl-package  管单阶段方法：req-align(Decision/Spec)、impl-planning(Plan) 等怎么做。
  - 审阅者        负责挑全漏洞（只读、独立），不替 Owner 做业务取舍。
  - 主控 + PE     负责四类分诊与根部裁剪，把业务取舍升级给 Owner。

两段式落点：
  - init --slug 先写暂存 <staging-dir>/<slug>.json；
  - bind-pkg 再迁到 <pkg>/kickoff-state.json 并绑定 pkg_dir。
"""


# ---------------------------------------------------------------- utilities


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


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


# ----------------------------------------------------------- pipeline engine


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


def next_command(state, state_path):
    stage = state["stage"]
    sw = state["switches"]
    script = os.path.abspath(__file__)
    p = f"python {script}"
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


def _gate_advance(state, target, artifacts):
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


# ----------------------------------------------------------- diagram mapper


def render_mermaid(pipeline=PIPELINE):
    lines = ["flowchart TD"]
    terminal = pipeline["terminal"]
    initial = pipeline["initial"]
    limit = pipeline["convergence_limit"]

    for st in pipeline["stages"]:
        sid = st["id"]
        label = st["label"]
        if st.get("note"):
            label = f"{label}<br/>({st['note']})"
        if sid == terminal:
            lines.append(f'    {sid}(["{label}"])')
        else:
            lines.append(f'    {sid}["{label}"]')

    lines.append("")

    for t in pipeline["transitions"]:
        src, dst = t["src"], t["dst"]
        arrow = "-.->" if t.get("style") == "dashed" else "-->"
        conds = [f"{k}={'on' if v else 'off'}" for k, v in t.get("when", {}).items()]
        gates = [
            GATE_LABELS.get(g, g)
            for g in t.get("gates", [])
            if g != "owner_confirmed" or src == initial
        ]
        parts = []
        if conds:
            parts.append(" & ".join(conds))
        if gates:
            parts.append(" & ".join(gates))
        edge_label = "<br/>".join(parts)
        if edge_label:
            lines.append(f'    {src} {arrow}|"{edge_label}"| {dst}')
        else:
            lines.append(f"    {src} {arrow} {dst}")

    triage_nodes = [st["id"] for st in pipeline["stages"] if st.get("triage")]
    if triage_nodes:
        lines.append("")
        for sid in triage_nodes:
            lines.append(f'    {sid} -->|"round (连续{limit}轮 added>0 警告)"| {sid}')

    return "\n".join(lines) + "\n"


def sync_markdown_diagram(md_path, diagram_text, check_only=False):
    if not os.path.isfile(md_path):
        fail(f"Markdown 文件不存在: {md_path}")
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    start_idx = content.find(DIAGRAM_BEGIN)
    end_idx = content.find(DIAGRAM_END)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        fail(
            f"{md_path} 缺少图表标记 {DIAGRAM_BEGIN} ... {DIAGRAM_END}"
        )

    fenced = f"{DIAGRAM_BEGIN}\n```mermaid\n{diagram_text.rstrip()}\n```\n{DIAGRAM_END}"
    updated = content[:start_idx] + fenced + content[end_idx + len(DIAGRAM_END):]

    if check_only:
        if updated != content:
            print(
                f"[diagram] {md_path} 中的流程图已过时，请运行：\n"
                f"  python {os.path.abspath(__file__)} diagram --sync-md {md_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[diagram] {md_path} 流程图已是最新。")
        return

    if updated == content:
        print(f"[diagram] {md_path} 无变化，已是最新。")
        return

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"[diagram] 已刷新 {md_path} 中的流程图。")


# --------------------------------------------------------------- commands


def cmd_init(args):
    research = args.research
    for value in research:
        if value != "none" and not value.strip():
            fail("--research 不能为空白（无材料请显式传 none）")
    prototype = args.prototype
    if prototype != "none" and not prototype.strip():
        fail("--prototype 不能为空白（无原型请显式传 none）")

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
        staging_dir = args.staging_dir
        state_path = os.path.join(staging_dir, f"{slug}.json")
        pkg_dir = None
        staging_path = os.path.abspath(state_path)

    if os.path.exists(state_path) and not args.force:
        fail(f"状态文件已存在: {state_path}（用 --force 覆盖）")

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
        "agents": {"pe": None, "reviewer": None},
        "rounds": [],
        "history": [],
    }
    add_history(state, "init", pkg_dir=pkg_dir, staging_path=staging_path)
    save_state(state_path, state)

    print(f"[init] 状态文件: {os.path.abspath(state_path)}")
    print(f"  目标: {state['goal'] or '(未填写)'}")
    print(f"  调研材料: {', '.join(research) if research else '(空)'}")
    print(f"  原型: {prototype}" + ("  (none=无原型)" if prototype == "none" else ""))
    print(f"  Docs: {', '.join(state['docs']) if state['docs'] else '(无)'}")
    print(
        "  环节开关: "
        f"discover={args.discover}, pe={args.pe}, plan={args.plan}"
    )
    print("  落点: " + (f"已绑定 pkg_dir  {pkg_dir}" if pkg_dir else f"暂存(待 bind-pkg)  {staging_path}"))
    print("\n[Step 0 原则]")
    for line in PRINCIPLES[PIPELINE["initial"]]:
        print(f"  - {line}")
    print(f"\n下一步: {next_command(state, state_path)}")


def cmd_confirm(args):
    path = resolve_state_path(args)
    state = load_state(path)
    if state.get("owner_confirmed"):
        print("Owner 已确认过，继续。")
    else:
        state["owner_confirmed"] = True
        state["confirmed_at"] = now()
        add_history(state, "confirm", note=args.note or "")
        save_state(path, state)
        print("Owner 已确认，owner_confirmed=true。")
    print(f"下一步: {next_command(state, path)}")


def cmd_register(args):
    path = resolve_state_path(args)
    state = load_state(path)
    role = args.role
    agent_id = (args.agent_id or "").strip()
    if not agent_id:
        fail("--agent-id 不能为空")
    prev = state.setdefault("agents", {}).get(role)
    if prev and prev != agent_id:
        print(
            f"[警告] 正在替换已登记的 {role} ({prev} -> {agent_id})，"
            "确认不是误开新代理破坏续用原则。"
        )
    state["agents"][role] = agent_id
    add_history(state, "register", role=role, agent_id=agent_id, previous=prev or None)
    save_state(path, state)
    print(f"[register] {role} = {agent_id}")


def cmd_bind_pkg(args):
    src = args.state
    if not src:
        fail("bind-pkg 必须提供 --state <暂存路径>")
    state = load_state(src)
    pkg = os.path.abspath(args.pkg)
    os.makedirs(pkg, exist_ok=True)
    dest = os.path.join(pkg, STATE_FILENAME)
    if os.path.exists(dest) and not args.force:
        fail(f"目标状态已存在: {dest}（用 --force 覆盖）")
    state["pkg_dir"] = pkg
    state["staging_path"] = None
    add_history(state, "bind", source=os.path.abspath(src), target=dest)
    save_state(dest, state)
    if os.path.abspath(src) != os.path.abspath(dest) and os.path.exists(src):
        os.remove(src)
    print(f"[bind-pkg] 已绑定 pkg_dir: {pkg}")
    print(f"  状态文件: {dest}")
    print(f"下一步: {next_command(state, dest)}")


def cmd_round(args):
    path = resolve_state_path(args)
    state = load_state(path)
    if not state.get("agents", {}).get("reviewer"):
        fail("未登记 reviewer：先运行 register --role reviewer --agent-id <id>")
    summary = (args.summary or "").strip()
    if not summary:
        fail("--summary 不能为空，请记录本轮分诊摘要")
    for name in ("added", "cut", "pe", "rejected"):
        if getattr(args, name) < 0:
            fail(f"--{name} 必须是非负整数")
    stage = args.stage
    if stage != state["stage"] and not args.backfill:
        fail(
            f"当前阶段为 {state['stage']}，不能记录 {stage} 阶段分诊"
            "（如确需补录历史阶段，请显式传 --backfill）"
        )
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
    state.setdefault("rounds", []).append(entry)
    add_history(
        state,
        "round",
        stage=stage,
        round=number,
        verdict=args.verdict,
        backfill=args.backfill or None,
    )
    save_state(path, state)

    c = entry["counts"]
    print(
        f"[round] {stage} #{number} [{entry['verdict']}]: added={c['added']} cut={c['cut']} "
        f"pe={c['pe']} rejected={c['rejected']} — {summary}"
    )
    limit = PIPELINE["convergence_limit"]
    recent = same[-(limit - 1):] + [entry] if limit > 1 else [entry]
    if len(recent) == limit and all(r["counts"]["added"] > 0 for r in recent):
        print(
            f"\n[收敛警告] 同一阶段连续 {limit} 轮都在新增分支，停止继续加分支。\n"
            "  回看原型（若有），过 PE 判断能否从根部裁剪，而不是往下钻补条条框框。"
        )
    high_limit = PIPELINE.get("high_round_limit", 4)
    if number >= high_limit:
        print(
            f"\n[轮次提醒] {stage} 已进入第 {number} 轮，"
            "确认是在收尾零星不一致而非陷入细节拉锯。"
        )
    print(f"\n下一步: {next_command(state, path)}")


def cmd_advance(args):
    path = resolve_state_path(args)
    state = load_state(path)
    target = args.target
    artifacts = args.artifact or []

    errs = _gate_advance(state, target, artifacts)
    if errs:
        print(f"[门禁拦截] 无法进入 {target}：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    prev = state["stage"]
    state["stage"] = target
    if artifacts:
        state.setdefault("artifacts", {})[prev] = [os.path.abspath(a) for a in artifacts]
    add_history(state, "advance", source=prev, target=target, artifacts=artifacts or None)
    save_state(path, state)

    print(f"[advance] {prev} -> {target}  已完成状态迁移。")
    print(f"\n[{target} 硬原则]")
    for line in PRINCIPLES[target]:
        print(f"  - {line}")
    print(f"\n下一步: {next_command(state, path)}")


def cmd_status(args):
    path = resolve_state_path(args)
    state = load_state(path)
    sw = state["switches"]
    print("== kickoff 状态 ==")
    print(f"  状态文件: {os.path.abspath(path)}")
    print(f"  当前阶段: {state['stage']}")
    print(f"  包目录: {state.get('pkg_dir') or '(未绑定)'}")
    if state.get("staging_path"):
        print(f"  暂存路径: {state['staging_path']}")
    print(f"  Owner 确认: {'是' if state.get('owner_confirmed') else '否'}"
          + (f"  ({state.get('confirmed_at')})" if state.get("confirmed_at") else ""))
    print(f"  目标: {state.get('goal') or '(未填写)'}")
    print(f"  输入契约: research={state['inputs']['research']}  prototype={state['inputs']['prototype']}")
    if state.get("docs"):
        print(f"  Docs: {', '.join(state['docs'])}")
    print(
        f"  环节开关: discover={'on' if sw['discover'] else 'off'} "
        f"pe={'on' if sw['pe'] else 'off'} plan={'on' if sw['plan'] else 'off'}"
    )
    agents = state.get("agents", {})
    print(f"  角色: pe={agents.get('pe') or '(未登记)'}  reviewer={agents.get('reviewer') or '(未登记)'}")
    if state.get("artifacts"):
        print("  阶段产出:")
        for st, paths in state["artifacts"].items():
            print(f"    {st}: {', '.join(paths)}")

    print("  分诊轮次:")
    if not state.get("rounds"):
        print("    (无)")
    else:
        for stage in TRIAGE_STAGES:
            rs = rounds_for(state, stage)
            if not rs:
                continue
            print(f"    {stage}: {len(rs)} 轮")
            for r in rs:
                c = r["counts"]
                verdict = r.get("verdict") or "open"
                print(
                    f"      #{r['round']} [{verdict}] added={c['added']} cut={c['cut']} "
                    f"pe={c['pe']} rejected={c['rejected']} — {r['summary']}"
                )

    print("\n[当前阶段硬原则]")
    for line in PRINCIPLES.get(state["stage"], []):
        print(f"  - {line}")
    print(f"\n下一步有效命令: {next_command(state, path)}")


def cmd_diagram(args):
    mermaid = render_mermaid(PIPELINE)
    if args.sync_md:
        sync_markdown_diagram(args.sync_md, mermaid, check_only=args.check)
    elif args.check:
        fail("--check 必须配合 --sync-md <md路径> 使用")
    else:
        sys.stdout.write(mermaid)


# ------------------------------------------------------------------- main


def build_parser():
    parser = argparse.ArgumentParser(
        prog="kickoff",
        description="kickoff 状态机 CLI：编排新需求从 init 到 ready 的主链。\n\n" + FLOW,
        epilog="状态文件：除 init/diagram 外，用 --pkg <dir> 或 --state <path> 指定。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="初始化 kickoff（先 --slug 暂存，或 --pkg 直接绑定）")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--pkg", help="直接写入 <dir>/kickoff-state.json 并绑定 pkg_dir")
    g.add_argument("--slug", help="暂存到 <staging-dir>/<slug>.json")
    p.add_argument("--staging-dir", default=DEFAULT_STAGING_DIR, help="暂存目录（默认 ./output/kickoff）")
    p.add_argument("--goal", default="", help="需求目标")
    p.add_argument("--docs", action="append", default=[], help="相关文档路径（可重复）")
    p.add_argument("--research", action="append", required=True, metavar="PATH|none",
                   help="调研材料路径；无材料显式传 none（可重复）")
    p.add_argument("--prototype", required=True, metavar="PATH|none",
                   help="原型路径；无原型显式传 none")
    p.add_argument("--discover", choices=["on", "off"], default="on", help="探索环节开关（默认 on）")
    p.add_argument("--pe", choices=["on", "off"], default="on", help="常驻 PE 开关（默认 on）")
    p.add_argument("--plan", choices=["on", "off"], default="on", help="计划环节开关（默认 on）")
    p.add_argument("--force", action="store_true", help="覆盖已存在的状态文件")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("confirm", help="Owner 确认（唯一必停点）")
    p.add_argument("--pkg")
    p.add_argument("--state")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_confirm)

    p = sub.add_parser("register", help="登记常驻角色 PE / reviewer")
    p.add_argument("--pkg")
    p.add_argument("--state")
    p.add_argument("--role", choices=["pe", "reviewer"], required=True)
    p.add_argument("--agent-id", required=True)
    p.set_defaults(func=cmd_register)

    p = sub.add_parser("bind-pkg", help="把暂存状态迁到包目录并绑定 pkg_dir")
    p.add_argument("--state", required=True)
    p.add_argument("--pkg", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_bind_pkg)

    p = sub.add_parser("round", help="记录一轮审阅分诊")
    p.add_argument("--pkg")
    p.add_argument("--state")
    p.add_argument("--stage", choices=TRIAGE_STAGES, required=True)
    p.add_argument("--added", type=int, default=0)
    p.add_argument("--cut", type=int, default=0)
    p.add_argument("--pe", type=int, default=0)
    p.add_argument("--rejected", type=int, default=0)
    p.add_argument(
        "--verdict",
        choices=["open", "clean"],
        default="open",
        help="本轮审阅结论：open(仍有待修项，默认) / clean(复验清零，可过门)",
    )
    p.add_argument(
        "--backfill",
        action="store_true",
        help="允许补录非当前阶段的历史分诊轮次",
    )
    p.add_argument("--summary", required=True, help="本轮分诊摘要（非空）")
    p.set_defaults(func=cmd_round)

    p = sub.add_parser("advance", help="过门进入下一阶段")
    p.add_argument("target", choices=ADVANCE_TARGETS)
    p.add_argument("--pkg")
    p.add_argument("--state")
    p.add_argument("--artifact", action="append", default=[],
                   help="可选：声明本阶段产出路径，仅校验路径存在并登记（不解析内容）")
    p.set_defaults(func=cmd_advance)

    p = sub.add_parser("status", help="查看当前状态与下一步有效命令")
    p.add_argument("--pkg")
    p.add_argument("--state")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("diagram", help="从声明式 PIPELINE 生成 Mermaid 流程图或同步文档")
    p.add_argument("--sync-md", metavar="PATH",
                   help="将流程图同步写入指定 Markdown 文件的标记区块")
    p.add_argument("--check", action="store_true",
                   help="配合 --sync-md 仅校验文档图块是否与 PIPELINE 一致（防漂移）")
    p.set_defaults(func=cmd_diagram)

    return parser


def main(argv=None):
    _force_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
