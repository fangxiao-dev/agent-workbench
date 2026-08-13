#!/usr/bin/env python3
"""Scenario registry for the thread-harness selftest suite."""

from __future__ import annotations

import argparse
import shutil
import time
from importlib import import_module

from selftest_support import BASE, ScenarioResult


SCENARIOS = {
    "full": "selftest_scenarios.full_regression",
    "broker": "selftest_scenarios.broker",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="thread-harness selftest scenarios")
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available scenarios without running one",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIOS),
        default="full",
        help="run one scenario (default: full)",
    )
    return parser


def list_scenarios() -> int:
    for name in SCENARIOS:
        print(name)
    return 0


def run_scenario(name: str) -> ScenarioResult:
    module = import_module(SCENARIOS[name])
    result = module.run()
    if isinstance(result, ScenarioResult):
        return result
    return ScenarioResult(name, int(result))


def _cleanup_base(attempts: int = 10, delay_s: float = 0.5) -> None:
    # BASE is PID-scoped (see selftest_support.py); safe to remove
    # unconditionally, even under concurrent selftest runs. Windows can keep
    # a short-lived handle open on files under .git after a git subprocess
    # returns, so retry briefly instead of leaving litter on the first
    # PermissionError.
    for attempt in range(attempts):
        try:
            shutil.rmtree(BASE)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == attempts - 1:
                return
            time.sleep(delay_s)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        return list_scenarios()
    try:
        return run_scenario(args.scenario).returncode
    finally:
        _cleanup_base()


if __name__ == "__main__":
    raise SystemExit(main())
