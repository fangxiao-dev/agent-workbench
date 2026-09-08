"""Read-only audit of dispatch, return, and review trail events."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from situation import FACT_KEYS, LEGACY_FACT_KEYS, _dispatch_is_running

SITUATION = Path(__file__).with_name("situation.py")
STALE_DIGEST_THRESHOLD = 3
DIGEST_RE = re.compile(r"^[0-9a-f]{12}$", re.I)
TRAIL_ARCHIVE_RE = re.compile(r"^trail\.(\d{3})\.jsonl$")


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _kind(row):
    return str(row.get("kind", "")).lower()


def _digest(row):
    value = row.get("situation_digest")
    if "situation_digest" not in row or value is None or (isinstance(value, str) and not value.strip()):
        return "missing", None
    return ("valid", value) if isinstance(value, str) and DIGEST_RE.fullmatch(value) else ("invalid", None)


def _trail_paths(attempt_dir):
    attempt_dir = Path(attempt_dir)
    if not attempt_dir.is_dir():
        return []
    archives = []
    for path in attempt_dir.iterdir():
        match = TRAIL_ARCHIVE_RE.fullmatch(path.name)
        if match and path.is_file():
            archives.append((int(match.group(1)), path))
    archives.sort(key=lambda item: item[0])
    current = attempt_dir / "trail.jsonl"
    paths = [path for _, path in archives]
    if current.is_file():
        paths.append(current)
    return paths


def _trail_for(package):
    package = Path(package).expanduser().resolve()
    if not package.is_dir():
        raise ValueError(f"package directory does not exist: {package}")
    attempt = None
    try:
        state = json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8-sig"))
        attempt = _text(state.get("attempt", {}).get("id")) if isinstance(state, dict) and isinstance(state.get("attempt"), dict) else None
    except (OSError, json.JSONDecodeError):
        pass
    if attempt and (trails := _trail_paths(package / "execution" / attempt)):
        return package, attempt, trails
    candidates = []
    if (package / "execution").is_dir():
        for child in package.joinpath("execution").iterdir():
            trails = _trail_paths(child)
            if trails:
                candidates.append((child.name, trails))
    if len(candidates) == 1:
        return package, candidates[0][0], candidates[0][1]
    raise ValueError("no unique execution/<attempt>/trail.jsonl or trail.NNN.jsonl found")


def _read_rows(paths):
    rows, violations = [], []
    number = 0
    for path in paths:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            number += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                violations.append({"line": number, "issues": [f"invalid-json:{exc.msg}"]})
                continue
            if not isinstance(row, dict):
                violations.append({"line": number, "issues": ["row-is-not-object"]})
                continue
            issues = []
            if _kind(row) == "fact":
                key, subject = _text(row.get("key")), row.get("subject")
                if key not in LEGACY_FACT_KEYS:
                    if key is None:
                        issues.append("missing-key")
                    elif key not in FACT_KEYS:
                        issues.append(f"unknown-fact-key:{key}")
                    if isinstance(subject, str) and subject in FACT_KEYS:
                        issues.append("subject-is-fact-key")
                    if "value" not in row:
                        issues.append("missing-value")
                    if _text(row.get("ts")) is None:
                        issues.append("missing-ts")
            if _kind(row) == "dispatch" and not _text(row.get("dispatch_id")) and "situation_digest" in row:
                value = row.get("situation_digest")
                if value is not None and (not isinstance(value, str) or not DIGEST_RE.fullmatch(value)):
                    issues.append("invalid-situation-digest")
            rows.append((number, row))
            if issues:
                violations.append({"line": number, "issues": issues})
    return rows, violations


def _stale(dispatches):
    groups, run = [], []
    for number, row in dispatches:
        state, digest = _digest(row)
        if state == "valid" and (not run or run[0][1] == digest):
            run.append((number, digest))
            continue
        if len(run) >= STALE_DIGEST_THRESHOLD:
            groups.append({"digest": run[0][1], "count": len(run), "lines": [item[0] for item in run]})
        run = [] if state != "valid" else [(number, digest)]
    if len(run) >= STALE_DIGEST_THRESHOLD:
        groups.append({"digest": run[0][1], "count": len(run), "lines": [item[0] for item in run]})
    return groups


def _has_reason(row):
    chosen = _text(row.get("chosen"))
    return bool(_text(row.get("reason")) or (chosen and chosen.lower().startswith("escape:") and _text(chosen.split(":", 1)[1])))


def _related_reason(dispatch, rows):
    ident = next((str(dispatch[name]) for name in ("id", "seq", "dispatch_id", "dispatchId") if dispatch.get(name) is not None), None)
    if ident is None:
        return False
    for _, row in rows:
        if _kind(row) not in {"decision", "escape"} or row.get("subject") != dispatch.get("subject"):
            continue
        ids = {str(row[name]) for name in ("of", "decision", "dispatch_id", "dispatchId", "decision_id", "decisionId", "id", "seq") if row.get(name) is not None}
        if ident in ids and _has_reason(row):
            return True
    return False


def replay_situation(package, head):
    resolved = subprocess.run(["git", "-C", str(package), "rev-parse", "--verify", f"{head}^{{commit}}"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    commit = resolved.stdout.strip() if resolved.returncode == 0 else None
    if not commit:
        return None, f"head cannot be resolved: {head}"
    completed = subprocess.run([sys.executable, str(SITUATION), "render", "--package", str(package), "--at", head, "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "unknown render error"
        return None, f"situation render failed: {detail}"
    try:
        rendered = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"situation render returned invalid JSON: {exc.msg}"
    if not isinstance(rendered, dict) or rendered.get("unchanged") is True:
        return None, "situation render did not return a full JSON snapshot"
    if rendered.get("at") != commit or rendered.get("head") != commit:
        return None, "situation render did not return the requested commit snapshot"
    return (rendered, None) if isinstance(rendered.get("digest"), str) else (None, "situation render did not return a digest")


def _action_ids(rendered, subject, *, legacy=False):
    ids = set()
    names = ("selected", "parallel_matches", "other_matches", "suppressed_matches")
    if not legacy and "runnable" in rendered:
        names = ("blocking",) if rendered.get("blocking") else ("runnable",)
    for name in names:
        value = rendered.get(name)
        items = [value] if isinstance(value, dict) else value if isinstance(value, list) else []
        for item in items:
            if isinstance(item, dict) and item.get("subject") == subject:
                ids.update(value for value in item.get("action_ids", []) if isinstance(value, str))
                if _text(item.get("action_id")):
                    ids.add(item["action_id"])
    return ids


def _receipt(row):
    value = row.get("receipt")
    return bool(_text(value) or (isinstance(value, dict) and value))


def _execution_audit(rows):
    """Audit received dispatches, attributable returns, and fixed delta reviews."""
    issues, unknown, pending, overlaps = [], [], [], []
    dispatches, returns, waiting, reviews, active = {}, {}, {}, {}, {}
    fix_counts, returned_dispatches, completed_candidates = {}, set(), set()
    for number, row in rows:
        kind = _kind(row)
        if kind == "fact" and row.get("key") == "review.dispatch_pending":
            value = row.get("value")
            if isinstance(value, dict) and _text(value.get("return_id")):
                waiting.setdefault(value["return_id"], []).append((number, row, value))
        if kind == "dispatch" and _dispatch_is_running(row):
            ident = _text(row.get("dispatch_id"))
            if not ident:
                unknown.append({"line": number, "reason": "legacy dispatch has no dispatch_id/receipt contract"})
                continue
            if not _text(row.get("subject")):
                unknown.append({"line": number, "reason": "dispatch has no valid subject"})
                continue
            if ident in dispatches:
                issues.append({"line": number, "reason": "duplicate dispatch_id", "dispatch_id": ident})
                continue
            if not _receipt(row):
                issues.append({"line": number, "reason": "dispatch has no successful host receipt", "dispatch_id": ident})
                continue
            candidate_id = _text(row.get("candidate_id"))
            if not candidate_id:
                unknown.append({"line": number, "reason": "dispatch has no candidate_id"})
            elif candidate_id in completed_candidates or any(_text(other.get("candidate_id")) == candidate_id for _, other in active.values()):
                issues.append({"line": number, "reason": "candidate already running or DONE", "candidate_id": candidate_id})
            resources = row.get("resource_keys")
            if not isinstance(resources, list) or any(not _text(key) for key in resources):
                unknown.append({"line": number, "reason": "missing or invalid declared resource_keys"})
            for other_id, (other_number, other) in active.items():
                overlaps.append({
                    "dispatch_ids": [other_id, ident],
                    "lines": [other_number, number],
                    "resources": [other.get("resource_keys"), row.get("resource_keys")],
                })
            dispatches[ident] = active[ident] = (number, row)
            if _text(row.get("reviews")):
                reviews.setdefault(row["reviews"], []).append((number, row))
            if row.get("mode") == "fix":
                subject = row.get("subject")
                fix_counts[subject] = fix_counts.get(subject, 0) + 1
        if kind == "worker-return":
            ident, return_id, outcome = _text(row.get("of")), _text(row.get("return_id")), _text(row.get("outcome"))
            if not ident or not return_id or not outcome:
                unknown.append({"line": number, "reason": "worker return lacks dispatch/return identity or outcome"})
                continue
            if return_id in returns:
                issues.append({"line": number, "reason": "duplicate return_id", "return_id": return_id})
                continue
            if ident in returned_dispatches:
                issues.append({"line": number, "reason": "dispatch already returned; late return is not consumed", "return_id": return_id})
                continue
            if ident not in dispatches or dispatches[ident][1].get("subject") != row.get("subject"):
                issues.append({"line": number, "reason": "return has no matching received dispatch", "return_id": return_id})
                continue
            returns[return_id] = (number, row)
            returned_dispatches.add(ident)
            active.pop(ident, None)
            candidate_id = _text(dispatches[ident][1].get("candidate_id"))
            if outcome.upper() == "DONE" and candidate_id:
                completed_candidates.add(candidate_id)

    for return_id, (number, row) in returns.items():
        if not row.get("code_delta"):
            continue
        delta, consumption = row["code_delta"], _text(row.get("consumption_id"))
        if not isinstance(delta, dict) or not all(re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", str(delta.get(key, ""))) for key in ("base", "head")) or not consumption:
            unknown.append({"line": number, "reason": "code return lacks immutable delta/consumption identity"})
            continue
        matching_reviews = []
        for review_number, review in reviews.get(return_id, []):
            if review_number <= number or review.get("code_delta") != delta or review.get("subject") != row.get("subject") or review.get("consumption_id") != consumption:
                issues.append({"line": review_number, "reason": "review does not match fixed return delta"})
            elif review.get("worker") == dispatches[row["of"]][1].get("worker"):
                issues.append({"line": review_number, "reason": "reviewer implemented the reviewed delta"})
            else:
                matching_reviews.append((review_number, review))
        matching_pending = [(n, value) for n, fact, value in waiting.get(return_id, [])
                            if n > number and fact.get("subject") == row.get("subject")
                            and value.get("code_delta") == delta and value.get("consumption_id") == consumption
                            and _text(value.get("reason"))]
        first_record = min([n for n, _ in matching_pending] + [n for n, _ in matching_reviews], default=float("inf"))
        if any(number < n < first_record and dispatch.get("mode") in {"implement", "fix"} for n, dispatch in dispatches.values()):
            issues.append({"line": number, "reason": "new implementation dispatched before recording delta review", "return_id": return_id})
        if not matching_reviews and not matching_pending:
            issues.append({"line": number, "reason": "code return has neither same-consumption review nor pending reason", "return_id": return_id})
        if not matching_reviews:
            pending.append({"line": number, "return_id": return_id, "code_delta": delta, "recorded": bool(matching_pending)})
    for return_id, entries in reviews.items():
        if return_id not in returns:
            issues.extend({"line": n, "reason": "review references unknown return", "return_id": return_id} for n, _ in entries)
    return {"execution_issues": issues, "execution_uncheckable": unknown, "pending_reviews": pending,
            "concurrent_dispatches": overlaps,
            "repeat_fixes": {subject: count - 1 for subject, count in fix_counts.items() if count > 1}}


def audit_package(package):
    package, attempt, trails = _trail_for(package)
    rows, violations = _read_rows(trails)
    dispatches = [(n, r) for n, r in rows if _kind(r) == "dispatch"]
    legacy_dispatches = [(n, r) for n, r in dispatches if not _text(r.get("dispatch_id"))]
    no_digest = [n for n, r in legacy_dispatches if _digest(r)[0] == "missing"]
    deviations, uncheckable, cache, replayed = [], [], {}, 0
    for number, row in legacy_dispatches:
        state, digest = _digest(row)
        if state == "missing":
            continue
        if state == "invalid":
            uncheckable.append({"line": number, "reason": "invalid-situation-digest"})
            continue
        chosen, subject = _text(row.get("chosen")), _text(row.get("subject"))
        if chosen is None:
            uncheckable.append({"line": number, "reason": "dispatch has no chosen action id"})
            continue
        if subject is None:
            uncheckable.append({"line": number, "reason": "dispatch has no subject"})
            continue
        if chosen.lower() == "escape" or chosen.lower().startswith("escape:"):
            if _has_reason(row) or _related_reason(row, rows):
                continue
            deviations.append({"line": number, "chosen": chosen, "reason": "escape has no reason"})
            continue
        head = _text(row.get("head"))
        if head is None:
            uncheckable.append({"line": number, "reason": "dispatch has no head"})
            continue
        if head not in cache:
            cache[head] = replay_situation(package, head)
        rendered, error = cache[head]
        if error or rendered is None:
            uncheckable.append({"line": number, "reason": error or "replay failed"})
            continue
        legacy = rendered.get("legacy_digest") == digest and rendered.get("digest") != digest
        if rendered.get("digest") != digest and not legacy:
            uncheckable.append({"line": number, "reason": "digest differs from --at replay"})
            continue
        replayed += 1
        if chosen not in _action_ids(rendered, subject, legacy=legacy) and not _related_reason(row, rows):
            deviations.append({"line": number, "chosen": chosen, "reason": "chosen action is absent from replayed situation actions"})
    return {"package": str(package), "attempt": attempt, "trail": str(trails[-1]), "trails": [str(path) for path in trails], "dispatches": len(dispatches), "legacy_dispatches": len(legacy_dispatches), "no_digest": no_digest, "stale": _stale(legacy_dispatches), "deviations": deviations, "uncheckable": uncheckable, "replayed": replayed, "schema_violations": violations, **_execution_audit(rows)}


def _format_report(report):
    total, legacy, missing = report["dispatches"], report.get("legacy_dispatches", report["dispatches"]), len(report["no_digest"])
    percent = "n/a" if not legacy else f"{missing / legacy * 100:.1f}%"
    lines = ["dispatch-audit", f"package: {report['package']}", f"attempt: {report['attempt']}", f"trail: {report['trail']}", f"dispatches: {total}", f"no-digest: {missing}/{legacy} ({percent})", f"stale-digest: {len(report['stale'])} (threshold: {STALE_DIGEST_THRESHOLD} consecutive dispatches)", f"deviation: {len(report['deviations'])} (replayed: {report['replayed']}, uncheckable: {len(report['uncheckable'])})", f"schema-violations: {len(report['schema_violations'])}"]
    trail_files = report.get("trails", [report["trail"]])
    if len(trail_files) > 1:
        lines.insert(4, f"trail-files: {len(trail_files)}")
    lines += [f"  stale digest {x['digest']} on lines {','.join(map(str, x['lines']))}" for x in report["stale"]]
    lines += [f"  deviation line {x['line']}: {x['reason']}" for x in report["deviations"]]
    lines += [f"  schema line {x['line']}: {', '.join(x['issues'])}" for x in report["schema_violations"]]
    lines += [f"  uncheckable line {x['line']}: {x['reason']}" for x in report["uncheckable"]]
    lines += [f"{key}: {len(report.get(key, []))}" for key in ("execution_issues", "execution_uncheckable", "pending_reviews", "concurrent_dispatches")]
    for key in ("execution_issues", "execution_uncheckable"):
        lines += [f"  {key} line {x['line']}: {x['reason']}" for x in report.get(key, [])]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only dispatch/situation digest audit.")
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Emit the complete audit evidence as JSON.")
    try:
        args = parser.parse_args(argv)
        report = audit_package(args.package)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else _format_report(report))
    except (OSError, ValueError) as exc:
        print(f"dispatch-audit: ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
