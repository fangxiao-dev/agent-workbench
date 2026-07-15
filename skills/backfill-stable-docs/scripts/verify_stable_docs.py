#!/usr/bin/env python3
"""Run deterministic Stable Docs Backfill verification checks."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from make_item_id import make_item_id
from stable_docs_config import (
    ConfigError,
    load_method_activation,
    load_repository_config,
    resolve_project_path,
)


METHOD_ROOT = Path(__file__).resolve().parents[3]
ITEM_ID_RE = re.compile(r"^SDB-[0-9a-f]{12}$")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")


class VerificationError(RuntimeError):
    """Raised for a failed deterministic assertion."""


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise VerificationError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=root
    )
    if completed.returncode not in (0, 1):
        raise VerificationError("unable to compare project watermark with Source HEAD")
    return completed.returncode == 0


def _slug(value: str) -> str:
    value = re.sub(r"[^\w\- ]", "", value.strip().lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "-", value)


def _markdown_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".md" else []
    if path.is_dir():
        return sorted(item for item in path.rglob("*.md") if item.is_file())
    return []


def _check_paths(project: Path, config: dict[str, Any]) -> str:
    configured = [
        *(home["path"] for home in config["canonicalDocs"]),
        config["pendingPath"],
        config["compactionPath"],
        config["statePath"],
        config["implementationsPath"],
    ]
    missing = [path for path in configured if not resolve_project_path(project, path).exists()]
    if missing:
        raise VerificationError("configured paths do not exist: " + ", ".join(missing))
    return f"{len(configured)} configured paths exist"


def _check_links(project: Path, config: dict[str, Any]) -> str:
    failures: list[str] = []
    checked = 0
    for home in config["canonicalDocs"]:
        for markdown in _markdown_files(resolve_project_path(project, home["path"])):
            text = markdown.read_text(encoding="utf-8")
            for match in LINK_RE.finditer(text):
                raw = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
                if not raw or raw.startswith(("http://", "https://", "mailto:")):
                    continue
                path_part, _, anchor = unquote(raw).partition("#")
                target = markdown if not path_part else (markdown.parent / path_part).resolve()
                try:
                    target.relative_to(project)
                except ValueError:
                    failures.append(f"{markdown.relative_to(project)} -> {raw} escapes project")
                    continue
                checked += 1
                if not target.exists():
                    failures.append(f"{markdown.relative_to(project)} -> {raw} missing target")
                    continue
                if anchor and target.is_file() and target.suffix.lower() == ".md":
                    headings = {
                        _slug(line_match.group(1))
                        for line in target.read_text(encoding="utf-8").splitlines()
                        if (line_match := HEADING_RE.match(line))
                    }
                    if anchor.lower() not in headings:
                        failures.append(f"{markdown.relative_to(project)} -> {raw} missing anchor")
    if failures:
        raise VerificationError("; ".join(failures[:20]))
    return f"{checked} local Markdown links/anchors resolved"


def _check_danger_rules(project: Path, config: dict[str, Any]) -> str:
    matches: list[str] = []
    files_checked: set[Path] = set()
    for rule in config["dangerRules"]:
        for relative in rule["paths"]:
            path = resolve_project_path(project, relative)
            for file in _markdown_files(path):
                files_checked.add(file)
                text = file.read_text(encoding="utf-8").casefold()
                for literal in rule["literals"]:
                    if literal.casefold() in text:
                        matches.append(f"{rule['id']}:{file.relative_to(project)}:{literal}")
    if matches:
        raise VerificationError("danger-rule residue: " + "; ".join(matches[:20]))
    return f"{len(config['dangerRules'])} danger rules checked across {len(files_checked)} files"


def _destination_owner(destination: str, homes: list[dict[str, Any]]) -> list[str]:
    path = Path(destination.replace("\\", "/"))
    owners: list[str] = []
    for home in homes:
        home_path = Path(home["path"])
        if path == home_path or home_path in path.parents:
            owners.append(home["path"])
    return owners


def _module_inventory(project: Path, config: dict[str, Any]) -> set[str] | None:
    home = next((item for item in config["canonicalDocs"] if item["moduleInventory"]), None)
    if home is None:
        return None
    root = resolve_project_path(project, home["path"])
    return {path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith("_")}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label} must be readable JSON: {path}") from error
    if not isinstance(payload, dict):
        raise VerificationError(f"{label} must contain a JSON object")
    return payload


def _check_audit(
    project: Path,
    config: dict[str, Any],
    method_activation: dict[str, str],
    config_sha256: str,
    audit: dict[str, Any] | None,
) -> str:
    if audit is None:
        return "audit JSON not requested"
    if audit.get("schemaVersion") != 1 or audit.get("mode") != "audit":
        raise VerificationError("audit JSON must use schemaVersion 1 and mode audit")
    if audit.get("methodActivation") != method_activation:
        raise VerificationError("audit methodActivation does not match current agent-workbench repository/commit")
    if audit.get("configSha256") != config_sha256:
        raise VerificationError("audit configSha256 does not match selected configuration")
    required_arrays = (
        "moduleCoverage",
        "items",
        "pending",
        "carryForward",
        "removedPackages",
        "blockers",
    )
    for field in required_arrays:
        if not isinstance(audit.get(field), list):
            raise VerificationError(f"audit {field} must be an array")
    items = audit["items"]
    coverage = audit["moduleCoverage"]
    seen: set[str] = set()
    dispositions = {"candidate", "already-covered", "conflict", "no-delta"}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise VerificationError(f"audit items[{index}] must be an object")
        item_id = item.get("id")
        source = item.get("source")
        destination = item.get("destination")
        statement = item.get("statement")
        if not isinstance(item_id, str) or ITEM_ID_RE.fullmatch(item_id) is None:
            raise VerificationError(f"audit items[{index}] has invalid stable ID")
        if item_id in seen:
            raise VerificationError(f"duplicate audit item ID: {item_id}")
        seen.add(item_id)
        if not isinstance(source, str) or not isinstance(statement, str):
            raise VerificationError(f"audit item {item_id} lacks source or statement")
        if item_id != make_item_id(source, destination if isinstance(destination, str) else None, statement):
            raise VerificationError(f"audit item {item_id} is not stable for its identity fields")
        if item.get("disposition") not in dispositions:
            raise VerificationError(f"audit item {item_id} has invalid disposition")
        if item.get("disposition") == "candidate":
            if not isinstance(destination, str) or len(_destination_owner(destination, config["canonicalDocs"])) != 1:
                raise VerificationError(f"candidate {item_id} does not have exactly one canonical owner")
    referenced: dict[str, int] = {}
    for index, row in enumerate(coverage):
        if not isinstance(row, dict):
            raise VerificationError(f"audit moduleCoverage[{index}] must be an object")
        module = row.get("module")
        result = row.get("result")
        item_ids = row.get("itemIds")
        if not isinstance(module, str) or not module.strip():
            raise VerificationError(f"audit moduleCoverage[{index}].module must be non-empty")
        if result not in dispositions:
            raise VerificationError(f"audit moduleCoverage[{index}] has invalid result")
        if not isinstance(item_ids, list) or not all(
            isinstance(item_id, str) for item_id in item_ids
        ):
            raise VerificationError(
                f"audit moduleCoverage[{index}].itemIds must be an array of IDs"
            )
        for item_id in item_ids:
            if item_id not in seen:
                raise VerificationError(
                    f"moduleCoverage references unknown item ID: {item_id}"
                )
            referenced[item_id] = referenced.get(item_id, 0) + 1
    unreferenced = sorted(seen - set(referenced))
    if unreferenced:
        raise VerificationError(
            "audit items missing from moduleCoverage: " + ", ".join(unreferenced)
        )
    repeated = sorted(item_id for item_id, count in referenced.items() if count != 1)
    if repeated:
        raise VerificationError(
            "audit items must be referenced by exactly one moduleCoverage row: "
            + ", ".join(repeated)
        )
    inventory = _module_inventory(project, config)
    if inventory is not None:
        covered = {
            row.get("module") for row in coverage if isinstance(row, dict) and isinstance(row.get("module"), str)
        }
        missing = sorted(inventory - covered)
        if missing:
            raise VerificationError("module coverage missing: " + ", ".join(missing))
    return f"{len(items)} stable audit items and {len(coverage)} coverage rows verified"


def _select_source_head(
    project: Path,
    audit: dict[str, Any] | None,
    explicit_source_head: str | None,
) -> str | None:
    if audit is None:
        return explicit_source_head
    audit_project = audit.get("project")
    if not isinstance(audit_project, dict):
        raise VerificationError("audit project must be an object")
    audited_source_head = audit_project.get("sourceHead")
    if not isinstance(audited_source_head, str) or not audited_source_head.strip():
        raise VerificationError("audit project.sourceHead must be a commit")
    resolved_audited_head = _git(
        project, "rev-parse", "--verify", f"{audited_source_head}^{{commit}}"
    )
    if explicit_source_head is not None:
        resolved_explicit_head = _git(
            project, "rev-parse", "--verify", f"{explicit_source_head}^{{commit}}"
        )
        if resolved_explicit_head != resolved_audited_head:
            raise VerificationError(
                "explicit --source-head conflicts with audit project.sourceHead"
            )
    return resolved_audited_head


def _check_state(
    project: Path,
    config: dict[str, Any],
    method_activation: dict[str, str],
    source_head: str | None,
    audit: dict[str, Any] | None,
) -> str:
    state = _load_json(resolve_project_path(project, config["statePath"]), "compaction state")
    activation = state.get("method_activation")
    if activation != method_activation:
        raise VerificationError("state method_activation must equal current agent-workbench repository/commit; Plugin-era state requires a fresh audit before apply")
    project_state = state.get("project")
    if not isinstance(project_state, dict):
        raise VerificationError("state project must be an object")
    watermark = project_state.get("source_watermark")
    if not isinstance(watermark, str):
        raise VerificationError("state project.source_watermark must be a commit")
    resolved_watermark = _git(project, "rev-parse", "--verify", f"{watermark}^{{commit}}")
    resolved_head = _git(project, "rev-parse", "--verify", f"{source_head or 'HEAD'}^{{commit}}")
    if not _is_ancestor(project, resolved_watermark, resolved_head):
        raise VerificationError("Project Source Watermark is not an ancestor of Source HEAD")
    carry = state.get("carry_forward")
    if not isinstance(carry, list) or not all(isinstance(value, str) for value in carry):
        raise VerificationError("state carry_forward must be an array of package IDs")
    if len(carry) != len(set(carry)):
        raise VerificationError("state carry_forward contains duplicate package IDs")
    pending_count = 0
    if audit is not None:
        audit_carry_values = audit.get("carryForward")
        audit_pending_values = audit.get("pending")
        if not isinstance(audit_carry_values, list):
            raise VerificationError("audit carryForward must be an array")
        if not isinstance(audit_pending_values, list):
            raise VerificationError("audit pending must be an array")
        audit_carry = _audit_identifiers(
            audit_carry_values, "carryForward", ("packageId", "id")
        )
        if set(carry) != set(audit_carry):
            raise VerificationError(
                "audit/state carry-forward mismatch: "
                f"audit={sorted(audit_carry)}, state={sorted(carry)}"
            )
        pending_ids = _audit_identifiers(
            audit_pending_values, "pending", ("id", "pendingId")
        )
        pending_text = resolve_project_path(project, config["pendingPath"]).read_text(
            encoding="utf-8"
        )
        missing_pending = sorted(
            pending_id for pending_id in pending_ids if pending_id not in pending_text
        )
        if missing_pending:
            raise VerificationError(
                "audit pending IDs missing from configured pending register: "
                + ", ".join(missing_pending)
            )
        pending_count = len(pending_ids)
    return (
        f"watermark {resolved_watermark} is safe; {len(carry)} carry-forward packages; "
        f"{pending_count} audit pending IDs reconciled"
    )


def _audit_identifiers(
    values: list[Any], field: str, object_keys: tuple[str, ...]
) -> list[str]:
    identifiers: list[str] = []
    for index, value in enumerate(values):
        identifier: Any = value
        if isinstance(value, dict):
            identifier = next((value.get(key) for key in object_keys if key in value), None)
        if not isinstance(identifier, str) or not identifier.strip():
            raise VerificationError(
                f"audit {field}[{index}] must be an ID string or object with "
                + "/".join(object_keys)
            )
        identifier = identifier.strip()
        if identifier in identifiers:
            raise VerificationError(f"audit {field} contains duplicate ID: {identifier}")
        identifiers.append(identifier)
    return identifiers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--source-head")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    results: list[dict[str, str]] = []
    try:
        project = args.project_root.resolve()
        config, metadata = load_repository_config(project, args.config)
        method_activation = load_method_activation(METHOD_ROOT)
        audit = (
            _load_json(args.audit_json.resolve(), "audit JSON")
            if args.audit_json is not None
            else None
        )
        source_head = _select_source_head(project, audit, args.source_head)
    except (ConfigError, VerificationError) as error:
        sys.stdout.write(
            json.dumps({"passed": False, "error": str(error)}, indent=2) + "\n"
        )
        return 2

    checks: list[tuple[str, Callable[[], str]]] = [
        ("configured-paths", lambda: _check_paths(project, config)),
        ("canonical-links", lambda: _check_links(project, config)),
        ("danger-rules", lambda: _check_danger_rules(project, config)),
        (
            "audit-contract",
            lambda: _check_audit(project, config, method_activation, metadata["sha256"], audit),
        ),
        (
            "state-watermark",
            lambda: _check_state(project, config, method_activation, source_head, audit),
        ),
    ]
    for name, check in checks:
        try:
            results.append({"check": name, "result": "passed", "detail": check()})
        except (ConfigError, VerificationError, OSError, UnicodeError) as error:
            results.append({"check": name, "result": "failed", "detail": str(error)})
    failed = sum(1 for result in results if result["result"] == "failed")
    payload = {
        "schemaVersion": 1,
        "methodActivation": method_activation,
        "configSha256": metadata["sha256"],
        "passed": failed == 0,
        "checks": results,
        "summary": {"total": len(results), "passed": len(results) - failed, "failed": failed},
    }
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
