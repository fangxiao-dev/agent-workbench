"""Thin Ticket-first state CLI router for the 3.6 grouped runtime."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from impl_package_runtime import usage_log  # noqa: E402
from impl_package_runtime.config import CONFIG  # noqa: E402


GROUPS = {
    "package",
    "ticket",
    "evidence",
    "recovery",
    "trail",
    "gate",
}


def _root_parser() -> argparse.ArgumentParser:
    parser = usage_log.UsageArgumentParser(
        description="Ticket-first Impl-Package state router (format 3.6)",
    )
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--no-situation", action="store_true", help="do not append the current situation")
    parser.add_argument("group", choices=sorted(GROUPS))
    return parser


def _command_groups():
    return importlib.import_module("impl_package_runtime.command_groups")


def _route(argv: list[str]) -> tuple[Path, str, list[str]]:
    parser = usage_log.UsageArgumentParser(add_help=False)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("route")
    args, rest = parser.parse_known_args(argv)
    route = args.route
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
    label = usage_log.command_label(values)
    usage_log.begin()
    code = 1
    try:
        code = _main(values)
        return code
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0 if exc.code is None else 1
        raise
    except BaseException as exc:
        usage_log.note_error(type(exc).__name__, str(exc))
        raise
    finally:
        usage_log.record(label, code)


def _main(values: list[str]) -> int:
    no_situation = "--no-situation" in values
    values = [value for value in values if value != "--no-situation"]
    if not values or _command_token(values) is None:
        _root_parser().print_help()
        return 0
    package, group, remainder = _route(values)
    return _command_groups().main(package, group, remainder, no_situation=no_situation)


if __name__ == "__main__":
    raise SystemExit(main())
