#!/usr/bin/env python3
"""CLI for the package development pipeline status and routing profile."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.machinery
import json
import sys
from pathlib import Path
from types import ModuleType

SCRIPT_DIR = Path(__file__).resolve().parent
_PACKAGE_NAME = "_dev_loop_" + hashlib.sha256(str(SCRIPT_DIR).encode("utf-8")).hexdigest()[:12]


def _register_local_package() -> None:
    """Pin sibling imports to this script directory, including direct path execution."""
    existing = sys.modules.get(_PACKAGE_NAME)
    if existing is not None:
        if Path(existing.__path__[0]).resolve() != SCRIPT_DIR:
            raise ImportError("dev-loop sibling module namespace points outside scripts directory")
        return
    package = ModuleType(_PACKAGE_NAME)
    package.__package__ = _PACKAGE_NAME
    package.__path__ = [str(SCRIPT_DIR)]
    package.__spec__ = importlib.machinery.ModuleSpec(_PACKAGE_NAME, loader=None, is_package=True)
    package.__spec__.submodule_search_locations = [str(SCRIPT_DIR)]
    sys.modules[_PACKAGE_NAME] = package


_register_local_package()
engine = importlib.import_module(f"{_PACKAGE_NAME}.engine")
render = importlib.import_module(f"{_PACKAGE_NAME}.render")
diagram = importlib.import_module(f"{_PACKAGE_NAME}.diagram")


def _add_agent_fields(parser: argparse.ArgumentParser, required: bool = False) -> None:
    parser.add_argument("--role", required=required)
    parser.add_argument("--scope", action="append", required=required,
                        help="Ticket/batch id，可重复或用逗号分隔")
    parser.add_argument("--host", required=required)
    parser.add_argument("--agent-id")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--review-group")
    parser.add_argument("--note")


def _add_batch_fields(parser: argparse.ArgumentParser, updating: bool = False) -> None:
    parser.add_argument("--ticket", dest="tickets", action="append", default=None if updating else [],
                        help="Ticket id，可重复")
    parser.add_argument("--return-id", dest="returns", action="append", default=None if updating else [],
                        help="worker-return id，可重复")
    parser.add_argument("--reviewed-head")
    parser.add_argument("--snapshot-kind", choices=("integrated", "isolated"),
                        default=None if updating else "integrated")
    parser.add_argument("--review-run-id")
    parser.add_argument("--rounds-file")
    parser.add_argument("--ticket-note", action="append", default=[], metavar="TICKET=NOTE")
    parser.add_argument("--note")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="显示包级 Pipeline 状态")
    status.add_argument("--package", required=True)
    status.add_argument("--json", action="store_true")
    config = commands.add_parser("config", help="查看或设置本包模型路由")
    actions = config.add_subparsers(dest="config_command", required=True)
    show = actions.add_parser("show", help="显示本包 Pipeline 配置")
    show.add_argument("--package", required=True)
    show.add_argument("--json", action="store_true")
    route = actions.add_parser("set-route", help="设置后续派发的模型路由建议")
    route.add_argument("--package", required=True)
    route.add_argument("--role", required=True)
    route.add_argument("--model", required=True)
    route.add_argument("--effort")
    route.add_argument("--json", action="store_true")

    agent = commands.add_parser("agent", help="管理本包 Agent 池")
    agent_actions = agent.add_subparsers(dest="agent_action", required=True)
    register = agent_actions.add_parser("register", help="登记 agent")
    register.add_argument("--package", required=True)
    register.add_argument("--id")
    _add_agent_fields(register, required=True)
    register.add_argument("--json", action="store_true")
    update = agent_actions.add_parser("update", help="补录或更新 agent")
    update.add_argument("--package", required=True)
    update.add_argument("--id", required=True)
    _add_agent_fields(update)
    update.add_argument("--status", choices=("active", "replaced", "retired"))
    update.add_argument("--replaced-by")
    update.add_argument("--handoff-note")
    update.add_argument("--json", action="store_true")
    replace = agent_actions.add_parser("replace", help="替代 agent 并记录交接")
    replace.add_argument("--package", required=True)
    replace.add_argument("--id", required=True, help="旧 agent id")
    replace.add_argument("--new-id", help="已有 successor id，省略时自动创建")
    replace.add_argument("--handoff-note", required=True)
    _add_agent_fields(replace)
    replace.add_argument("--json", action="store_true")
    agent_list = agent_actions.add_parser("list", help="列出 agent 及续用提示")
    agent_list.add_argument("--package", required=True)
    agent_list.add_argument("--json", action="store_true")

    batch = commands.add_parser("batch", help="管理跨 Ticket 审阅批次")
    batch_actions = batch.add_subparsers(dest="batch_action", required=True)
    register = batch_actions.add_parser("register", help="登记审阅批次")
    register.add_argument("--package", required=True)
    register.add_argument("--batch-id")
    _add_batch_fields(register)
    register.add_argument("--status", choices=("open", "triaged", "closed", "superseded"), default="open")
    register.add_argument("--json", action="store_true")
    update = batch_actions.add_parser("update", help="补充批次信息或逐票备注")
    update.add_argument("--package", required=True)
    update.add_argument("--batch-id", required=True)
    _add_batch_fields(update, updating=True)
    update.add_argument("--status", choices=("open", "triaged", "closed", "superseded"))
    update.add_argument("--json", action="store_true")
    close = batch_actions.add_parser("close", help="关闭审阅批次")
    close.add_argument("--package", required=True)
    close.add_argument("--batch-id", required=True)
    close.add_argument("--json", action="store_true")
    batch_list = batch_actions.add_parser("list", help="列出审阅批次")
    batch_list.add_argument("--package", required=True)
    batch_list.add_argument("--json", action="store_true")
    graph = commands.add_parser("diagram", help="从 pipeline.json 生成 Mermaid 主链图")
    graph.add_argument("--sync-md", help="写回该 Markdown 的图表标记区")
    graph.add_argument("--check", action="store_true", help="配合 --sync-md，只检查是否过时")
    return parser


def _scope_value(values: list[str] | None) -> str | list[str] | None:
    if values is None:
        return None
    scopes = [part.strip() for value in values for part in value.split(",") if part.strip()]
    return scopes[0] if len(scopes) == 1 else scopes


def _agent_values(args: argparse.Namespace, include_id: bool = False) -> dict:
    names = ("role", "host", "agent_id", "model", "effort", "review_group", "note")
    values = {name: getattr(args, name) for name in names if getattr(args, name) is not None}
    scope = _scope_value(args.scope)
    if scope is not None:
        values["scope"] = scope
    if include_id and args.id is not None:
        values["id"] = args.id
    return values


def _ticket_notes(rows: list[str]) -> dict[str, str]:
    result = {}
    for row in rows:
        ticket, separator, note = row.partition("=")
        if not separator or not ticket.strip():
            raise ValueError("--ticket-note 格式必须为 TICKET=NOTE")
        result[ticket.strip()] = note
    return result


def _batch_values(args: argparse.Namespace, include_defaults: bool = False) -> dict:
    values = {}
    for name in ("tickets", "returns", "reviewed_head", "snapshot_kind", "review_run_id", "rounds_file", "note"):
        value = getattr(args, name)
        if value is not None:
            values[name] = value
    notes = _ticket_notes(args.ticket_note)
    if notes or include_defaults:
        values["ticket_notes"] = notes
    return values


def _output(value: dict, as_json: bool, formatter) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2) if as_json else formatter(value))
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "diagram":
            mermaid = diagram.render_mermaid(engine.PIPELINE)
            if not args.sync_md:
                sys.stdout.write(mermaid)
            elif not diagram.sync_markdown(args.sync_md, mermaid, args.check):
                print(f"dev-loop: {args.sync_md} 中的流程图已过时", file=sys.stderr)
                return 1
            return 0
        if args.command == "status":
            return _output(engine.status_view(args.package), args.json, render.status_text)
        if args.command == "config":
            if args.config_command == "show":
                return _output(engine.config_show(args.package), args.json, render.config_text)
            engine.config_set_route(args.package, args.role, args.model, args.effort)
            return _output(engine.status_view(args.package), args.json, render.status_text)
        if args.command == "agent":
            if args.agent_action == "list":
                return _output(engine.agent_list(args.package), args.json, render.agent_text)
            if args.agent_action == "register":
                engine.agent_register(args.package, _agent_values(args, include_id=True))
            elif args.agent_action == "update":
                changes = _agent_values(args)
                for name in ("status", "replaced_by", "handoff_note"):
                    value = getattr(args, name)
                    if value is not None:
                        changes[name] = value
                engine.agent_update(args.package, args.id, changes)
            else:
                engine.agent_replace(args.package, args.id, _agent_values(args),
                                     args.new_id, args.handoff_note)
            return _output(engine.status_view(args.package), args.json, render.status_text)
        if args.batch_action == "list":
            return _output(engine.batch_list(args.package), args.json, render.batch_text)
        if args.batch_action == "register":
            values = _batch_values(args, include_defaults=True)
            values["status"] = args.status
            if args.batch_id is not None:
                values["batch_id"] = args.batch_id
            engine.batch_register(args.package, values)
        elif args.batch_action == "update":
            values = _batch_values(args)
            if args.status is not None:
                values["status"] = args.status
            engine.batch_update(args.package, args.batch_id, values)
        else:
            engine.batch_close(args.package, args.batch_id)
        return _output(engine.status_view(args.package), args.json, render.status_text)
    except (OSError, ValueError, ImportError) as error:
        print(f"dev-loop: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
