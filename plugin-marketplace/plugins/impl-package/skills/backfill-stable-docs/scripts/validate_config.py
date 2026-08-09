#!/usr/bin/env python3
"""Validate Stable Docs Backfill configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stable_docs_config import ConfigError, load_repository_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        config, metadata = load_repository_config(args.project_root, args.config)
        payload = {"valid": True, "config": metadata}
    except ConfigError as error:
        payload = {"valid": False, "error": str(error)}
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
