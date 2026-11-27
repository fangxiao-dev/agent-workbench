#!/usr/bin/env python3
"""Thin CLI for the deterministic kickoff state machine."""

import argparse
import hashlib
import importlib
import importlib.machinery
import os
import sys
from types import ModuleType

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_NAME = "_kickoff_" + hashlib.sha256(SCRIPT_DIR.encode("utf-8")).hexdigest()[:12]


def _register_local_package():
    """Pin sibling imports to this script directory for CLI and dynamic loading."""
    existing = sys.modules.get(_PACKAGE_NAME)
    if existing is not None:
        if os.path.abspath(existing.__path__[0]) != SCRIPT_DIR:
            raise ImportError("kickoff sibling module namespace points outside scripts directory")
        return
    package = ModuleType(_PACKAGE_NAME)
    package.__package__ = _PACKAGE_NAME
    package.__path__ = [SCRIPT_DIR]
    package.__spec__ = importlib.machinery.ModuleSpec(_PACKAGE_NAME, loader=None, is_package=True)
    package.__spec__.submodule_search_locations = [SCRIPT_DIR]
    sys.modules[_PACKAGE_NAME] = package


_register_local_package()
engine = importlib.import_module(f"{_PACKAGE_NAME}.engine")
render = importlib.import_module(f"{_PACKAGE_NAME}.render")
diagram = importlib.import_module(f"{_PACKAGE_NAME}.diagram")


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def build_parser():
    parser = argparse.ArgumentParser(
        prog="kickoff",
        description="kickoff 状态机 CLI：编排新需求从 init 到 ready 的主链。\n\n" + engine.FLOW,
        epilog="状态文件：除 init/diagram 外，用 --pkg <dir> 或 --state <path> 指定。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("init", help="初始化 kickoff（先 --slug 暂存，或 --pkg 直接绑定）")
    group = command.add_mutually_exclusive_group(required=True)
    group.add_argument("--pkg", help="直接写入 <dir>/kickoff-state.json 并绑定 pkg_dir")
    group.add_argument("--slug", help="暂存到 <staging-dir>/<slug>.json")
    command.add_argument("--staging-dir", default=engine.DEFAULT_STAGING_DIR, help="暂存目录（默认 ./output/kickoff）")
    command.add_argument("--goal", default="", help="需求目标")
    command.add_argument("--docs", action="append", default=[], help="相关文档路径（可重复）")
    command.add_argument("--research", action="append", required=True, metavar="PATH|none",
                         help="调研材料路径；无材料显式传 none（可重复）")
    command.add_argument("--prototype", required=True, metavar="PATH|none",
                         help="原型路径；无原型显式传 none")
    command.add_argument("--discover", choices=["on", "off"], default="on", help="探索环节开关（默认 on）")
    command.add_argument("--pe", choices=["on", "off"], default="on", help="常驻 PE 开关（默认 on）")
    command.add_argument("--plan", choices=["on", "off"], default="on", help="计划环节开关（默认 on）")
    command.add_argument("--force", action="store_true", help="覆盖已存在的状态文件")

    command = sub.add_parser("confirm", help="Owner 确认（唯一必停点）")
    command.add_argument("--pkg")
    command.add_argument("--state")
    command.add_argument("--note", default="")

    command = sub.add_parser("register", help="登记角色 PE / reviewer / plan-reviewer")
    command.add_argument("--pkg")
    command.add_argument("--state")
    command.add_argument("--role", choices=["pe", "reviewer", "plan-reviewer"], required=True)
    command.add_argument("--agent-id", required=True)
    command.add_argument(
        "--label",
        default="",
        help="可选：plan-reviewer 分轨或职责标签（如 scope / risk / delivery），便于后续复用",
    )

    command = sub.add_parser("bind-pkg", help="把暂存状态迁到包目录并绑定 pkg_dir")
    command.add_argument("--state", required=True)
    command.add_argument("--pkg", required=True)
    command.add_argument("--force", action="store_true")

    command = sub.add_parser("round", help="记录一轮审阅分诊")
    command.add_argument("--pkg")
    command.add_argument("--state")
    command.add_argument("--stage", choices=engine.TRIAGE_STAGES, required=True)
    command.add_argument("--added", type=int, default=0)
    command.add_argument("--cut", type=int, default=0)
    command.add_argument("--pe", type=int, default=0)
    command.add_argument("--rejected", type=int, default=0)
    command.add_argument(
        "--verdict",
        choices=["open", "clean"],
        default="open",
        help="本轮审阅结论：open(仍有待修项，默认) / clean(复验清零，可过门)",
    )
    command.add_argument("--backfill", action="store_true", help="允许补录非当前阶段的历史分诊轮次")
    command.add_argument(
        "--touched-upstream",
        action="store_true",
        help="标记本轮修订回改了上游合同（Decision / Spec / contract-design），触发联动重验提醒",
    )
    command.add_argument("--summary", required=True, help="本轮分诊摘要（非空）")

    command = sub.add_parser("advance", help="过门进入下一阶段")
    command.add_argument("target", choices=engine.ADVANCE_TARGETS)
    command.add_argument("--pkg")
    command.add_argument("--state")
    command.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="可选：声明本阶段产出路径，仅校验路径存在并登记（不解析内容）",
    )

    command = sub.add_parser("status", help="查看当前状态与下一步有效命令")
    command.add_argument("--pkg")
    command.add_argument("--state")

    command = sub.add_parser("diagram", help="从声明式 PIPELINE 生成 Mermaid 流程图或同步文档")
    command.add_argument("--sync-md", metavar="PATH", help="将流程图同步写入指定 Markdown 文件的标记区块")
    command.add_argument("--check", action="store_true", help="配合 --sync-md 仅校验文档图块是否与 PIPELINE 一致（防漂移）")
    return parser


def _run_diagram(args):
    mermaid = diagram.render_mermaid(engine.PIPELINE)
    if args.sync_md:
        return diagram.sync_markdown_diagram(args.sync_md, mermaid, check_only=args.check)
    if args.check:
        raise engine.KickoffError("--check 必须配合 --sync-md <md路径> 使用")
    return mermaid.rstrip("\n")


def main(argv=None):
    _force_utf8()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "diagram":
            output = _run_diagram(args)
        else:
            handler = {
                "init": (engine.init, render.init_text),
                "confirm": (engine.confirm, render.confirm_text),
                "register": (engine.register, render.register_text),
                "bind-pkg": (engine.bind_pkg, render.bind_pkg_text),
                "round": (engine.record_round, render.round_text),
                "advance": (engine.advance, render.advance_text),
                "status": (engine.status, render.status_text),
            }[args.command]
            output = handler[1](handler[0](args))
        print(output)
        return 0
    except engine.GateBlocked as error:
        print(f"[门禁拦截] 无法进入 {error.target}：", file=sys.stderr)
        for message in error.errors:
            print(f"  - {message}", file=sys.stderr)
        return error.code
    except engine.KickoffError as error:
        message = str(error) if error.raw else f"错误: {error}"
        print(message, file=sys.stderr)
        return error.code
    except (OSError, ValueError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
