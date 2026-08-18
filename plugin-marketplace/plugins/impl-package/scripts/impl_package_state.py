"""Thin Ticket-first state CLI router for the 3.5 grouped runtime."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from impl_package_runtime.config import CONFIG  # noqa: E402


GROUPS = {
    "package",
    "ticket",
    "evidence",
    "recovery",
    "trail",
    "gate",
}

LEGACY = {
    "init": ("package", "init"),
    "status": ("package", "status"),
    "validate": ("package", "validate"),
    "refresh-progress": ("package", "refresh-progress"),
    "set-state": ("ticket", "transition"),
    "evidence-add": ("evidence", "add"),
    "evidence-invalidate": ("evidence", "invalidate"),
    "checkpoint": ("recovery", "checkpoint"),
    "er-add": ("recovery", "judgment"),
}


def _root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ticket-first Impl-Package state router (format 3.5)",
        epilog="Flat 3.5 command spellings remain accepted as compatibility aliases.",
    )
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("group", choices=sorted(GROUPS))
    return parser


def _command_groups():
    return importlib.import_module("impl_package_runtime.command_groups")


def _route(argv: list[str]) -> tuple[Path, str, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("route")
    args, rest = parser.parse_known_args(argv)
    route = args.route
    if route in LEGACY:
        group, command = LEGACY[route]
        return args.package.resolve(), group, [command, *rest]
    if route in GROUPS:
        return args.package.resolve(), route, rest
    _root_parser().error(f"unknown command group: {route}")
    raise AssertionError("argparse.error should exit")


def _command_token(argv: list[str]) -> str | None:
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--package":
            index += 2
            continue
        if value.startswith("-"):
            index += 1
            continue
        return value
    return None


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values or _command_token(values) is None:
        _root_parser().print_help()
        return 0
    package, group, remainder = _route(values)
    return _command_groups().main(package, group, remainder)


if __name__ == "__main__":
    raise SystemExit(main())
