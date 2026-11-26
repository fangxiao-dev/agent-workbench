#!/usr/bin/env python3
"""Deterministic kickoff state machine CLI.

Single source of truth lives in ../pipeline.json. Runtime gate evaluation lives
in engine.py and Mermaid diagram generation lives in diagram.py. Only Python 3
stdlib is used.
"""

import argparse
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from diagram import render_mermaid, sync_markdown_diagram  # noqa: E402
from engine import (  # noqa: E402
    ADVANCE_TARGETS,
    DEFAULT_STAGING_DIR,
    FLOW,
    PIPELINE,
    PRINCIPLES,
    STAGES,
    STATE_FILENAME,
    TRIAGE_STAGES,
    add_history,
    fail,
    gate_advance,
    load_state,
    next_command,
    now,
    resolve_state_path,
    rounds_for,
    save_state,
)


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


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
        "agents": {"pe": None, "reviewer": None, "plan_reviewers": []},
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
    if role == "plan-reviewer":
        label = (args.label or "").strip()
        pool = state.setdefault("agents", {}).setdefault("plan_reviewers", [])
        existing = next((item for item in pool if item.get("agent_id") == agent_id), None)
        if existing is not None:
            if label:
                existing["label"] = label
            add_history(state, "register", role=role, agent_id=agent_id, label=label or None)
            save_state(path, state)
            tag = f" ({existing.get('label')})" if existing.get("label") else ""
            print(f"[register] plan-reviewer 已存在并保留: {agent_id}{tag}（共 {len(pool)} 位）")
            return
        entry = {"agent_id": agent_id}
        if label:
            entry["label"] = label
        pool.append(entry)
        add_history(state, "register", role=role, agent_id=agent_id, label=label or None)
        save_state(path, state)
        tag = f" ({label})" if label else ""
        print(f"[register] plan-reviewer += {agent_id}{tag}（共 {len(pool)} 位）")
        return
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
    stage = args.stage
    if stage != state["stage"] and not args.backfill:
        fail(
            f"当前阶段为 {state['stage']}，不能记录 {stage} 阶段分诊"
            "（如确需补录历史阶段，请显式传 --backfill）"
        )
    if stage == "plan":
        if not state.get("agents", {}).get("plan_reviewers"):
            fail("未登记 plan-reviewer：先运行 register --role plan-reviewer --agent-id <id>")
    else:
        if not state.get("agents", {}).get("reviewer"):
            fail("未登记 reviewer：先运行 register --role reviewer --agent-id <id>")
    summary = (args.summary or "").strip()
    if not summary:
        fail("--summary 不能为空，请记录本轮分诊摘要")
    for name in ("added", "cut", "pe", "rejected"):
        if getattr(args, name) < 0:
            fail(f"--{name} 必须是非负整数")
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

    c = entry["counts"]
    upstream_tag = " [touched-upstream]" if args.touched_upstream else ""
    print(
        f"[round] {stage} #{number} [{entry['verdict']}]{upstream_tag}: added={c['added']} cut={c['cut']} "
        f"pe={c['pe']} rejected={c['rejected']} — {summary}"
    )
    if args.touched_upstream:
        print(
            "\n[上游变更提醒] 本轮回改了上游合同（Decision / Spec / contract-design），\n"
            "  请重跑 check-spec 等确定性校验，并确认受影响合同条款已完成复验。"
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

    errs = gate_advance(state, target, artifacts)
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
    skills = STAGES[target].get("skills") or []
    if skills:
        print(f"\n[{target} 调用 Skill] {', '.join(skills)}")
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
    pr_list = agents.get("plan_reviewers") or []
    pr_str = (
        ", ".join(
            f"{item['agent_id']}({item['label']})" if item.get("label") else item["agent_id"]
            for item in pr_list
        )
        if pr_list
        else "(未登记)"
    )
    print(
        f"  角色: pe={agents.get('pe') or '(未登记)'}  "
        f"reviewer={agents.get('reviewer') or '(未登记)'}  "
        f"plan-reviewer={pr_str}"
    )
    skills = STAGES.get(state["stage"], {}).get("skills") or []
    if skills:
        print(f"  阶段 Skill: {', '.join(skills)}")
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
                up_tag = " [touched-upstream]" if r.get("touched_upstream") else ""
                print(
                    f"      #{r['round']} [{verdict}]{up_tag} added={c['added']} cut={c['cut']} "
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

    p = sub.add_parser("register", help="登记角色 PE / reviewer / plan-reviewer")
    p.add_argument("--pkg")
    p.add_argument("--state")
    p.add_argument("--role", choices=["pe", "reviewer", "plan-reviewer"], required=True)
    p.add_argument("--agent-id", required=True)
    p.add_argument(
        "--label",
        default="",
        help="可选：plan-reviewer 分轨或职责标签（如 scope / risk / delivery），便于后续复用",
    )
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
    p.add_argument(
        "--touched-upstream",
        action="store_true",
        help="标记本轮修订回改了上游合同（Decision / Spec / contract-design），触发联动重验提醒",
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
