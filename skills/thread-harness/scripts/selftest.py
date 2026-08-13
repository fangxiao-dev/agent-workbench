#!/usr/bin/env python3
"""Scenario registry for the thread-harness selftest suite."""

from __future__ import annotations

import argparse
from importlib import import_module

from selftest_support import ScenarioResult


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


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        return list_scenarios()
    return run_scenario(args.scenario).returncode


if __name__ == "__main__":
    raise SystemExit(main())
