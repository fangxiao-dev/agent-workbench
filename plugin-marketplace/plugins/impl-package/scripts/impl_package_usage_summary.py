"""Summarise the impl_package_state.py usage log (stdlib only).

Reads <tempdir>/impl-package/usage.jsonl (or the path given as the only argument)
and prints, per command: calls, failures, failure rate, and the top 3
`error_type: reason` pairs among the failures.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import Counter, defaultdict


def default_path() -> str:
    return os.path.join(tempfile.gettempdir(), "impl-package", "usage.jsonl")


def summarize(path: str) -> str:
    calls: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    causes: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    try:
        with open(path, encoding="utf-8") as stream:
            lines = stream.read().splitlines()
    except OSError as exc:
        return f"cannot read {path}: {exc}"
    for line in lines:
        try:
            row = json.loads(line)
            command = str(row["command"])
        except (ValueError, KeyError, TypeError):
            continue  # skip a damaged or foreign line
        calls[command] += 1
        if not row.get("ok"):
            failures[command] += 1
            causes[command][(str(row.get("error_type")), str(row.get("reason")))] += 1
    if not calls:
        return "no usage records"
    out = [f"{'command':<32} {'calls':>6} {'failed':>7} {'fail rate':>9}"]
    for command, total in sorted(calls.items(), key=lambda item: (-item[1], item[0])):
        failed = failures[command]
        out.append(f"{command:<32} {total:>6} {failed:>7} {failed / total:>8.0%}")
        for (error_type, reason), count in causes[command].most_common(3):
            out.append(f"    {count}x {error_type}: {reason}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print(summarize(args[0] if args else default_path()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
