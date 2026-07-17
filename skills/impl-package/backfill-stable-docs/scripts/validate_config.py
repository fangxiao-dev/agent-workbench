#!/usr/bin/env python3
"""Validate Stable Docs Backfill repository configuration (contract 3.2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stable_docs_config import (
    CONTRACT_VERSION,
    ConfigError,
    discover_pending_paths,
    load_repository_config,
    resolve_target_branch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        project = args.project_root.resolve()
        config, metadata = load_repository_config(project, args.config)
        pending_discovery = discover_pending_paths(project, config)
        gaps = [
            entry for entry in pending_discovery if entry["status"] in {"missing", "ambiguous"}
        ]
        cold_starts = [
            entry for entry in pending_discovery if entry["status"] == "cold-start"
        ]
        try:
            target_branch_commit = resolve_target_branch(project, config["targetBranch"])
            target_branch_gap = None
        except ConfigError as error:
            target_branch_commit = None
            target_branch_gap = str(error)
        sys.stdout.write(
            json.dumps(
                {
                    "valid": True,
                    "contractVersion": CONTRACT_VERSION,
                    "configSource": metadata["source"],
                    "configSha256": metadata["sha256"],
                    "targetBranch": config["targetBranch"],
                    "targetBranchCommit": target_branch_commit,
                    "targetBranchConfigGap": target_branch_gap,
                    "implementationRootCount": len(config["implementations"]),
                    "systemKnowledgeRootCount": len(config["stableDocs"]["systemKnowledge"]),
                    "contextKnowledgeRootCount": len(config["stableDocs"]["contextKnowledge"]),
                    "moduleKnowledgeRootCount": len(config["stableDocs"]["moduleKnowledge"]),
                    "ignoreGroupCount": len(config["ignore"]),
                    "pendingDiscovery": pending_discovery,
                    "pendingConfigGaps": gaps,
                    "pendingColdStarts": cold_starts,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0 if not gaps and target_branch_gap is None else 2
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
