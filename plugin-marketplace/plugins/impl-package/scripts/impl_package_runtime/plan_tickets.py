"""Plan info, Ticket documents/dependencies and spec/contract checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .spec_journey import (
    _ticket_coverage,
    validate_spec_document,
)
from .state_core import (
    ACCEPTANCE_JOURNEY_RE,
    ARRIVAL_PATH_RE,
    ARRIVAL_SEGMENT_RE,
    ATTEMPT_ID_RE,
    ATTEMPT_RE,
    BATCH_ESTIMATE_RE,
    COMPOSITION_RE,
    DECISION_RE,
    DEPENDENCY_HEADING_RE,
    PLAN_RE,
    PREDECESSORS_RE,
    PUBLICATION_RE,
    RELEASE_ORDER_RE,
    SPEC_RE,
    StateError,
    TICKET_ID_RE,
    _read,
    _repo_relative,
    _repo_root,
    _run_git,
    _run_git_result,
)


def _field(pattern: re.Pattern[str], text: str, label: str, *, optional: bool = False) -> str | None:
    match = pattern.search(text)
    if match:
        return match.group(1)
    if optional:
        return None
    raise StateError(f"missing {label}")


def _predecessors_from_plan(package: Path, repo: Path, text: str) -> list[str] | None:
    matches = list(PREDECESSORS_RE.finditer(text))
    if len(matches) != 1:
        raise StateError("plan must declare 前置包（Predecessors） exactly once")
    raw = matches[0].group(1).strip()
    if raw.casefold() == "none":
        return None
    if not raw:
        raise StateError("前置包（Predecessors） must be None or a repository-relative directory list")
    values = [item.strip() for item in raw.split(",")]
    if any(not item or item.casefold() == "none" for item in values):
        raise StateError("前置包（Predecessors） cannot mix None with paths or contain an empty path")
    result: list[str] = []
    for value in values:
        normalized = _repo_relative(repo, value, "predecessor")
        if "#" in normalized:
            raise StateError("predecessor must not contain a text anchor")
        path = repo / Path(*normalized.split("/"))
        if not path.is_dir():
            raise StateError(f"predecessor must be a directory: {normalized}")
        if path.resolve() == package.resolve():
            raise StateError("a package cannot declare itself as a predecessor")
        if normalized in result:
            raise StateError(f"duplicate predecessor: {normalized}")
        result.append(normalized)
    return result


def _normalize_state_predecessors(package: Path, repo: Path, value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise StateError("state predecessors must be null or a non-empty list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise StateError("state predecessors must contain repository-relative paths")
        normalized = _repo_relative(repo, item, "state predecessor")
        if "#" in normalized or not (repo / Path(*normalized.split("/"))).is_dir():
            raise StateError(f"state predecessor must be an existing directory: {normalized}")
        if normalized in result:
            raise StateError(f"duplicate state predecessor: {normalized}")
        if (repo / Path(*normalized.split("/"))).resolve() == package.resolve():
            raise StateError("state cannot declare the current package as a predecessor")
        result.append(normalized)
    return result


def _package_relative(package: Path, path: Path) -> str:
    return path.resolve().relative_to(package.resolve()).as_posix()


HARNESS_PLAN_FORMATS = {
    "Harness setup": "Harness setup: <命令>",
    "Harness precheck": "Harness precheck: <命令>",
    "Harness cleanup": "Harness cleanup: <命令>",
    "Harness isolation": "Harness isolation: per-run",
    "First visible step": "First visible step: <StepId> @ <TicketId>",
}


def _harness_from_plan(text: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    errors: list[str] = []
    for field in HARNESS_PLAN_FORMATS:
        rows = [line for line in text.splitlines() if line.startswith(f"{field}:")]
        if len(rows) != 1:
            errors.append(f"{field}：{'缺失' if not rows else '只能出现一次'}")
            continue
        value = rows[0].partition(":")[2].strip()
        if not value:
            errors.append(f"{field}：值不能为空")
            continue
        values[field] = value

    isolation = values.get("Harness isolation")
    if isolation is not None and isolation != "per-run":
        errors.append(f"Harness isolation: {isolation}（只接受 per-run）")
    first_visible = values.get("First visible step")
    match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s+@\s+([A-Za-z0-9][A-Za-z0-9._-]*)", first_visible or "")
    if first_visible is not None and match is None:
        errors.append(f"First visible step: {first_visible}（StepId 与 TicketId 格式无效）")
    if errors:
        expected = "\n".join(f"- {line}" for line in HARNESS_PLAN_FORMATS.values())
        raise StateError("plan Harness 字段缺失或非法：\n- " + "\n- ".join(errors) + "\n正确格式：\n" + expected)

    assert match is not None
    return {
        "setup": values["Harness setup"],
        "precheck": values["Harness precheck"],
        "cleanup": values["Harness cleanup"],
        "isolation": isolation,
        "firstVisibleStep": {"step": match.group(1), "ticket": match.group(2)},
    }


def _validate_first_visible_step(harness: dict[str, Any], spec: dict[str, Any], documents: list[dict[str, Any]]) -> None:
    first = harness["firstVisibleStep"]
    step = spec["steps"].get(first["step"])
    if step is None or step["entryType"] not in {"页面", "文件"}:
        raise StateError(
            f"First visible step {first['step']} 必须存在于 Spec 且入口类型为 页面 或 文件；"
            f"正确格式：{HARNESS_PLAN_FORMATS['First visible step']}"
        )
    if first["ticket"] not in {document["id"] for document in documents}:
        raise StateError(
            f"First visible step Ticket {first['ticket']} 不存在；"
            f"正确格式：{HARNESS_PLAN_FORMATS['First visible step']}"
        )


def _plan_info(package: Path, repo: Path, plan_value: str) -> dict[str, Any]:
    plan_rel = _repo_relative(repo, plan_value, "plan", must_exist=False)
    plan_path = repo / plan_rel.split("#", 1)[0]
    if not plan_path.exists():
        raise StateError(
            f"plan does not exist: {plan_rel}；--plan 必须是相对仓库根的路径，"
            f"例如 {_package_relative(repo, package)}/<attempt>.patch-plan.md"
        )
    try:
        plan_path.resolve().relative_to(package.resolve())
    except ValueError as exc:
        raise StateError("current plan must be inside the package") from exc
    if not (package / "spec.md").is_file():
        raise StateError("spec.md is required for an active Attempt")
    text = _read(plan_path)
    # Composition is optional; a plan that still declares a Task/DAG composition is unsupported.
    composition = COMPOSITION_RE.search(text)
    if composition is not None and (composition.group(2).lower() == "true" or composition.group(1).lower() != "true"):
        raise StateError("only tickets=true, dag=false is supported")
    if len(ACCEPTANCE_JOURNEY_RE.findall(text)) != 1:
        raise StateError("plan must declare Acceptance: journey exactly once; plans without it are no longer supported")
    release_order = "none"
    release_markers = RELEASE_ORDER_RE.findall(text)
    if len(release_markers) > 1:
        raise StateError("plan must declare Release order at most once")
    if re.search(r"(?m)^Release order:", text) and not release_markers:
        raise StateError("Release order must be required or none")
    if release_markers:
        release_order = release_markers[0]
    harness = _harness_from_plan(text)
    attempt = _field(ATTEMPT_RE, text, "Attempt ID")
    if not isinstance(attempt, str) or ATTEMPT_ID_RE.fullmatch(attempt) is None:
        raise StateError(f"invalid Attempt ID: {attempt!r}")
    return {"path": plan_rel, "attempt": attempt, "decision": _field(DECISION_RE, text, "Decision Revision", optional=True), "spec": _field(SPEC_RE, text, "Spec Revision", optional=True), "plan": _field(PLAN_RE, text, "Plan Revision", optional=True), "predecessors": _predecessors_from_plan(package, repo, text), "releaseOrder": release_order, "harness": harness}


def _arrival_paths(text: str, ticket_id: str, path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for match in ARRIVAL_PATH_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        segments = re.split(r"\s*(?:→|->)\s*", match.group(1).strip())
        if len(segments) < 2 or segments[0].casefold() != "entry" or segments[-1].casefold() != "arrival":
            raise StateError(f"Ticket {ticket_id} arrival path in {path.name}:{line} must use entry → ... → arrival")
        nodes: list[dict[str, str]] = []
        for segment in segments[1:-1]:
            marked = ARRIVAL_SEGMENT_RE.fullmatch(segment.strip())
            if marked is None:
                raise StateError(
                    f"Ticket {ticket_id} arrival path in {path.name}:{line} has an unmarked segment: {segment!r}; use EXISTS: or NEW:"
                )
            symbol = marked.group(2).strip()
            if symbol.startswith("`") and symbol.endswith("`"):
                symbol = symbol[1:-1].strip()
            if not symbol:
                raise StateError(f"Ticket {ticket_id} arrival path in {path.name}:{line} has an empty symbol")
            nodes.append({"kind": marked.group(1), "symbol": symbol})
        result.append({"line": line, "nodes": nodes})
    return result


def _ticket_documents(package: Path, attempt: str, errors: list[str] | None = None) -> list[dict[str, Any]]:
    """Parse the Attempt's Ticket files; with `errors`, record each bad file and keep going."""
    directory = package / "tickets"
    if not directory.is_dir():
        raise StateError("Composition earns tickets but tickets/ is missing")
    result: list[dict[str, Any]] = []
    for child in sorted(directory.iterdir(), key=lambda item: item.name):
        if not child.is_file() or child.suffix.lower() != ".md":
            continue
        if errors is None:
            _append_ticket_document(package, attempt, child, result)
            continue
        try:
            _append_ticket_document(package, attempt, child, result)
        except StateError as exc:
            errors.append(f"tickets/{child.name}: {exc}")
    if not result and directory.exists() and not errors:
        raise StateError(f"Composition earns tickets but no Ticket belongs to Attempt {attempt}")
    return result


def _batch_estimate_absent_findings(package: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"code": "ticket-batch-estimate-absent", "ticket": document["id"], "path": _package_relative(package, document["path"])}
        for document in summary["_documents"]
        if not BATCH_ESTIMATE_RE.search(document["text"])
    ]


def _append_ticket_document(package: Path, attempt: str, child: Path, result: list[dict[str, Any]]) -> None:
    text = _read(child)
    identifier = _field(TICKET_ID_RE, text, f"Ticket ID in {child.name}")
    ticket_attempt = _field(ATTEMPT_RE, text, f"Attempt ID in {child.name}")
    if ticket_attempt != attempt:
        return
    if any(row["id"] == identifier for row in result):
        raise StateError(f"duplicate Ticket ID for Attempt {attempt}: {identifier}")
    publication = PUBLICATION_RE.search(text)
    if publication is None:
        raise StateError(f"missing Publication Status in {child.name}")
    if "impl-package:projection runtime-acceptance" in text:
        raise StateError(f"Ticket {identifier} contains retired Runtime Acceptance projection")
    arrival_paths = _arrival_paths(text, str(identifier), child)
    coverage = _ticket_coverage(text, str(identifier))
    document = {"id": str(identifier), "path": child, "text": text, "publication": "Approved" if publication.group(2) == "Approved" else "Draft", "coverage": coverage, "arrivalPaths": arrival_paths}
    result.append(document)


def _ticket_dependencies(documents: list[dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    identifiers = {row["id"] for row in documents}
    result: dict[str, list[tuple[str, str]]] = {}
    for row in documents:
        section = DEPENDENCY_HEADING_RE.search(row["text"])
        dependencies: list[tuple[str, str]] = []
        if section:
            for line in section.group(1).splitlines():
                stripped = line.strip()
                if not stripped.startswith("-") or stripped.lower() in {"- none", "- 无"}:
                    continue
                match = re.fullmatch(r"-\s*(implementation|acceptance|release)\s*:\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\s*[（(:：—–-].*)?", stripped)
                if match is None:
                    raise StateError(
                        f"Ticket {row['id']} has invalid typed dependency: {stripped}；"
                        "正确格式：`- implementation: T01`（或 acceptance/release）；"
                        "同行注释须紧跟在 id 后、以（ ( : ： — – - 之一开头，否则放到列表下方的独立段落"
                    )
                if match.group(2) not in identifiers:
                    raise StateError(f"Ticket {row['id']} has unknown dependency: {match.group(2)}")
                dependencies.append((match.group(1), match.group(2)))
        result[row["id"]] = dependencies
    _reject_cycles({key: [item for _, item in value] for key, value in result.items()}, "Ticket dependency graph")
    return result


def _reject_cycles(graph: dict[str, list[str]], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise StateError(f"{label} contains a cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _git_grep_symbol(repo: Path, commit: str, symbol: str, paths: list[str], excluded: list[str]) -> list[str]:
    args = ["grep", "-I", "-F", "-l", "-e", symbol, commit, "--"]
    args.extend(paths or ["."])
    args.extend(f":!(exclude){path}" for path in excluded)
    code, stdout, stderr = _run_git_result(repo, *args)
    if code == 1:
        return []
    if code != 0:
        raise StateError(stderr.strip() or f"cannot search comparison commit {commit}")
    return [line for line in stdout.splitlines() if line.strip()]


PLAN_GATE_RE = re.compile(r"(?:不派发|不进入|必须先[^。；;\n]*?PASS|失败时不[^。；;\n]*)", re.I)
CONTRACT_DOC_NAMES = ("decision.md", "spec.md", "contract-design.md")


def _contains_ticket_id(text: str, ticket: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_-]){re.escape(ticket)}(?![A-Za-z0-9_-])", text) is not None


def _contract_doc_name_findings(package: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    ticket_ids = sorted(
        document["id"] for document in summary["_documents"] if document["publication"] == "Approved"
    )
    findings: list[dict[str, Any]] = []
    for name in CONTRACT_DOC_NAMES:
        path = package / name
        if not path.is_file():
            continue
        try:
            text = _read(path)
        except StateError:
            continue
        hits = {
            ticket: len(re.findall(rf"(?<![A-Za-z0-9_-]){re.escape(ticket)}(?![A-Za-z0-9_-])", text))
            for ticket in ticket_ids
        }
        matched = {ticket: count for ticket, count in hits.items() if count}
        if matched:
            findings.append(
                {
                    "code": "contract-doc-names-ticket",
                    "path": _package_relative(package, path),
                    "hitCount": sum(matched.values()),
                    "ticketIds": sorted(matched),
                }
            )
    return findings


def _plan_prose_gate_findings(repo: Path, package: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    plan_path = repo / Path(*summary["_info"]["path"].split("#", 1)[0].split("/"))
    try:
        plan_text = _read(plan_path)
    except StateError:
        return []
    inbound: dict[str, list[tuple[str, str]]] = {ticket: [] for ticket in summary["_ticketDependencies"]}
    for source, edges in summary["_ticketDependencies"].items():
        for kind, target in edges:
            inbound.setdefault(target, []).append((kind, source))
    plan_relative = _package_relative(package, plan_path)
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(plan_text.splitlines(), start=1):
        for match in PLAN_GATE_RE.finditer(line):
            phrase = match.group(0)
            tickets = [ticket for ticket in inbound if _contains_ticket_id(phrase, ticket)]
            if not tickets:
                tickets = [ticket for ticket in inbound if _contains_ticket_id(line, ticket)]
            for ticket in tickets:
                inbound_types = sorted({kind for kind, _source in inbound[ticket]})
                if inbound_types != ["acceptance"]:
                    continue
                findings.append(
                    {
                        "code": "plan-prose-gates-acceptance-edge",
                        "ticket": ticket,
                        "path": plan_relative,
                        "line": line_number,
                        "detail": phrase,
                        "inboundTypes": inbound_types,
                    }
                )
    return findings


def _arrival_path_absent_findings(package: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "code": "ticket-arrival-path-absent",
            "ticket": document["id"],
            "path": _package_relative(package, document["path"]),
        }
        for document in summary["_documents"]
        if not document["arrivalPaths"]
    ]


def _arrival_findings(repo: Path, package: Path, summary: dict[str, Any], comparison_commit: str) -> list[dict[str, Any]]:
    package_rel = package.resolve().relative_to(repo.resolve()).as_posix()
    excluded = [package_rel, f"{package_rel}/**", "**/*.md"]
    predecessors = summary.get("predecessors") or []
    findings: list[dict[str, Any]] = []
    for document in summary["_documents"]:
        document_rel = _package_relative(package, document["path"])
        for route in document.get("arrivalPaths", []):
            for node in route["nodes"]:
                if node["kind"] != "EXISTS":
                    continue
                symbol = node["symbol"]
                if predecessors and _git_grep_symbol(repo, comparison_commit, symbol, predecessors, excluded):
                    continue
                if _git_grep_symbol(repo, comparison_commit, symbol, [], excluded):
                    continue
                findings.append(
                    {
                        "code": "arrival-exists-symbol-not-found",
                        "ticket": document["id"],
                        "path": document_rel,
                        "line": route["line"],
                        "symbol": symbol,
                        "comparisonCommit": comparison_commit,
                    }
                )
    return findings


def _working_tree_blobs(repo: Path, package: Path, relatives: list[str] | tuple[str, ...]) -> dict[str, str]:
    existing = [relative for relative in relatives if (package / relative).is_file()]
    if not existing:
        return {}
    package_rel = package.resolve().relative_to(repo.resolve()).as_posix()
    paths = [f"{package_rel}/{relative}" for relative in existing]
    hashes = _run_git(repo, "hash-object", "--", *paths).splitlines()
    if len(hashes) != len(paths):
        raise StateError("Git returned an unexpected number of working-tree blob IDs")
    return dict(zip(existing, hashes, strict=True))


def _contract_baseline(package: Path, repo: Path) -> dict[str, Any]:
    head = _run_git(repo, "rev-parse", "HEAD")
    files = _working_tree_blobs(repo, package, CONTRACT_DOC_NAMES)
    if "spec.md" not in files:
        raise StateError("contractBaseline requires spec.md")
    return {"head": head, "files": files}


def _pending_amendments(amendments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PENDING amendments that no later amendment supersedes; superseded ones no longer block the Gate."""
    superseded = {item for row in amendments for item in row.get("supersedes", [])}
    return [row for row in amendments if row["status"] == "PENDING" and row["id"] not in superseded]


def _contract_amendment_findings(package: Path, repo: Path, acceptance: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = acceptance["contractBaseline"]["files"]
    amendments = acceptance["amendments"]
    findings = []
    current_blobs = _working_tree_blobs(repo, package, CONTRACT_DOC_NAMES)
    for name in CONTRACT_DOC_NAMES:
        current = current_blobs.get(name)
        if current == baseline.get(name):
            continue
        if any(row.get("affectedBlobs", {}).get(name) == current for row in amendments):
            continue
        findings.append({"code": "contract-amendment-unregistered", "path": name, "baseline": baseline.get(name), "current": current})
    return findings


def _post_gate_pending_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    if not summary["_lifecycle"].frozen or summary["_lifecycle"].gate_verdict != "pass":
        return []
    return [{"code": "post-gate-amendment-pending", "id": row["id"]} for row in _pending_amendments(summary["_acceptance"]["amendments"])]


def command_check_spec(package: Path, spec_value: str | None = None) -> dict[str, Any]:
    repo = _repo_root(package)
    spec_value = spec_value or _package_relative(repo, package / "spec.md")
    spec_relative = _repo_relative(repo, spec_value, "spec")
    if "#" in spec_relative:
        raise StateError("spec must not contain a text anchor")
    spec = validate_spec_document(repo / spec_relative, spec_relative)
    return {
        "spec": spec_relative,
        "valid": True,
        "journeys": len(spec["journeys"]),
        "steps": len(spec["steps"]),
        "rules": len(spec["rules"]),
        "suites": len(spec["suites"]),
    }
