"""Mechanical CLI usage log: one JSONL line per impl_package_state.py invocation.

Never raises and never changes a command's exit code or output.  Arguments and
paths are not recorded; `reason` is the first line of the error message only.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone

REASON_LIMIT = 200

_noted: tuple[str, str] | None = None


def log_path() -> str:
    return os.path.join(tempfile.gettempdir(), "impl-package", "usage.jsonl")


def begin() -> None:
    global _noted
    _noted = None


def note_error(error_type: str, message: str) -> None:
    global _noted
    if _noted is None:
        _noted = (error_type, message)


class UsageArgumentParser(argparse.ArgumentParser):
    def error(self, message: str):
        note_error("ArgparseError", message)
        super().error(message)


def command_label(argv: list[str]) -> str:
    """`<group> <subcommand>`; `<group> --help` for help; never includes option values."""
    tokens: list[str] = []
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--package":
            index += 2
            continue
        if not value.startswith("-"):
            tokens.append(value)
            break
        index += 1
    if not tokens:
        return "--help"
    group = tokens[0]
    rest = argv[index + 1:]
    if "-h" in argv or "--help" in argv:
        return f"{group} --help"
    for value in rest:
        if value.startswith("-"):
            break
        return f"{group} {value}"
    return group


def record(command: str, code: int) -> None:
    try:
        ok = code == 0
        error_type = reason = None
        if not ok:
            if _noted is not None:
                error_type = _noted[0]
                reason = (_noted[1].strip().splitlines() or [""])[0][:REASON_LIMIT]
            else:
                error_type = f"exit:{code}"
        row = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "command": command,
            "ok": ok,
            "error_type": error_type,
            "reason": reason,
        }
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(descriptor, data)  # single append write keeps concurrent lines whole
        finally:
            os.close(descriptor)
    except Exception:
        pass
