#!/usr/bin/env python3
"""FastMCP server for discuss-ledger."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent
SRC = SKILL_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from discuss_ledger_core import ledger

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised only when dependency exists
    FastMCP = None


@dataclass
class ServerConfig:
    root: str
    dir: str = ledger.DEFAULT_DIR


CONFIG = ServerConfig(root=os.getcwd())


def configure(*, root: str | os.PathLike[str] | None = None, dir: str | None = None) -> None:
    if root is not None:
        CONFIG.root = os.fspath(root)
    if dir is not None:
        CONFIG.dir = dir


def _command_payload(result: ledger.CommandResult) -> dict[str, Any]:
    return {"message": result.message, "path": result.path}


def _status_payload(status: ledger.LedgerStatus) -> dict[str, Any]:
    return {
        "frontmatter": status.frontmatter,
        "open_points": status.open_points,
        "convergence": status.convergence,
    }


def init_ledger(
    topic: str,
    initiator: str,
    slug: str | None = None,
    title: str | None = None,
    participants: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    return _command_payload(
        ledger.init_ledger(
            root=CONFIG.root,
            dir=CONFIG.dir,
            topic=topic,
            slug=slug,
            title=title,
            initiator=initiator,
            participants=participants,
            force=force,
        )
    )


def get_status(slug: str) -> dict[str, Any]:
    return _status_payload(ledger.get_status(root=CONFIG.root, dir=CONFIG.dir, slug=slug))


def add_point(slug: str, author: str, summary: str, body: str | None = None) -> dict[str, Any]:
    return _command_payload(
        ledger.add_point(root=CONFIG.root, dir=CONFIG.dir, slug=slug, author=author, summary=summary, body=body)
    )


def contest_point(
    slug: str,
    point: str,
    author: str,
    body: str | None = None,
    movement: bool = True,
) -> dict[str, Any]:
    return _command_payload(
        ledger.contest_point(
            root=CONFIG.root,
            dir=CONFIG.dir,
            slug=slug,
            point=point,
            author=author,
            body=body,
            movement=movement,
        )
    )


def converge_point(slug: str, point: str, marker: str, line: str) -> dict[str, Any]:
    return _command_payload(
        ledger.converge_point(root=CONFIG.root, dir=CONFIG.dir, slug=slug, point=point, marker=marker, line=line)
    )


def end_turn(slug: str) -> dict[str, Any]:
    return _command_payload(ledger.end_turn(root=CONFIG.root, dir=CONFIG.dir, slug=slug))


def set_next(slug: str, next_agent: str) -> dict[str, Any]:
    return _command_payload(ledger.set_next(root=CONFIG.root, dir=CONFIG.dir, slug=slug, next_agent=next_agent))


def record_agent_turn(
    slug: str,
    author: str,
    convergences: list[dict[str, Any]] | None = None,
    contests: list[dict[str, Any]] | None = None,
    new_points: list[dict[str, Any]] | None = None,
    end_turn_after: bool = False,
) -> dict[str, Any]:
    return _command_payload(
        ledger.record_agent_turn(
            root=CONFIG.root,
            dir=CONFIG.dir,
            slug=slug,
            author=author,
            convergences=convergences,
            contests=contests,
            new_points=new_points,
            end_turn_after=end_turn_after,
        )
    )


def state_resource(slug: str) -> str:
    return json.dumps(get_status(slug), ensure_ascii=False, indent=2)


def markdown_resource(slug: str) -> str:
    return ledger.read_markdown(root=CONFIG.root, dir=CONFIG.dir, slug=slug)


def open_points_resource(slug: str) -> str:
    status = ledger.get_status(root=CONFIG.root, dir=CONFIG.dir, slug=slug)
    return json.dumps(status.open_points, ensure_ascii=False, indent=2)


def convergence_resource(slug: str) -> str:
    status = ledger.get_status(root=CONFIG.root, dir=CONFIG.dir, slug=slug)
    return json.dumps(status.convergence, ensure_ascii=False, indent=2)


def create_server(root: str, dir: str):
    if FastMCP is None:
        raise RuntimeError("mcp[cli] is required to run the discuss-ledger MCP server")
    configure(root=root, dir=dir)
    app = FastMCP("discuss-ledger")
    app.tool()(init_ledger)
    app.tool()(get_status)
    app.tool()(add_point)
    app.tool()(contest_point)
    app.tool()(converge_point)
    app.tool()(end_turn)
    app.tool()(record_agent_turn)
    app.resource("ledger://{slug}/state")(state_resource)
    app.resource("ledger://{slug}/markdown")(markdown_resource)
    app.resource("ledger://{slug}/open-points")(open_points_resource)
    app.resource("ledger://{slug}/convergence")(convergence_resource)
    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the discuss-ledger FastMCP server")
    parser.add_argument("--root", default=os.getcwd(), help="target project root")
    parser.add_argument("--dir", default=ledger.DEFAULT_DIR, help="ledger dir relative to root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = create_server(args.root, args.dir)
    app.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
