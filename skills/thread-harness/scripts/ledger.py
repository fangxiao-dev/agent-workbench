#!/usr/bin/env python3
"""Compatibility entry point for the thread-harness broker CLI."""

from ledger_cli import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
