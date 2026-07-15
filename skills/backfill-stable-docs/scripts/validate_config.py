#!/usr/bin/env python3
"""Validate Stable Docs Backfill repository configuration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stable_docs_config import ConfigError, load_repository_config, resolve_project_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--require-existing",
        action="store_true",
        help="also require configured canonical/state/source paths to exist",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        project = args.project_root.resolve()
        config, metadata = load_repository_config(project, args.config)
        missing: list[str] = []
        if args.require_existing:
            paths = [
                *(home["path"] for home in config["canonicalDocs"]),
                config["pendingPath"],
                config["compactionPath"],
                config["statePath"],
                config["implementationsPath"],
            ]
            missing = [path for path in paths if not resolve_project_path(project, path).exists()]
            if missing:
                raise ConfigError("configured paths do not exist: " + ", ".join(missing))
        sys.stdout.write(
            json.dumps(
                {
                    "valid": True,
                    "schemaVersion": config["schemaVersion"],
                    "configSource": metadata["source"],
                    "configSha256": metadata["sha256"],
                    "canonicalDocCount": len(config["canonicalDocs"]),
                    "dangerRuleCount": len(config["dangerRules"]),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
