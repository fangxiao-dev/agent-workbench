"""Read-only audit of dispatches against situation-table snapshots."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from situation import FACT_KEYS
except ImportError:  # pragma: no cover
    FACT_KEYS = frozenset()

SITUATION = Path(__file__).with_name("situation.py")
STALE_DIGEST_THRESHOLD = 3
DIGEST_RE = re.compile(r"^[0-9a-f]{12}$", re.I)


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _kind(row):
    return str(row.get("kind", "")).lower()


def _digest(row):
    value = row.get("situation_digest")
    if "situation_digest" not in row or value is None or (isinstance(value, str) and not value.strip()):
        return "missing", None
    return ("valid", value) if isinstance(value, str) and DIGEST_RE.fullmatch(value) else ("invalid", None)


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
    if attempt and (trail := package / "execution" / attempt / "trail.jsonl").is_file():
        return package, attempt, trail
    candidates = sorted((package / "execution").glob("*/trail.jsonl")) if (package / "execution").is_dir() else []
    if len(candidates) == 1:
        return package, candidates[0].parent.name, candidates[0]
    raise ValueError("no unique execution/<attempt>/trail.jsonl found")


def _read_rows(path):
    rows, violations = [], []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
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
        if _kind(row) == "dispatch" and "situation_digest" in row:
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


def _action_ids(rendered, subject):
    ids = set()
    for name in ("selected", "parallel_matches", "other_matches", "suppressed_matches"):
        value = rendered.get(name)
        items = [value] if isinstance(value, dict) else value if isinstance(value, list) else []
        for item in items:
            if isinstance(item, dict) and item.get("subject") == subject:
                ids.update(value for value in item.get("action_ids", []) if isinstance(value, str))
    return ids


def audit_package(package):
    package, attempt, trail = _trail_for(package)
    rows, violations = _read_rows(trail)
    dispatches = [(n, r) for n, r in rows if _kind(r) == "dispatch"]
    no_digest = [n for n, r in dispatches if _digest(r)[0] == "missing"]
    deviations, uncheckable, cache, replayed = [], [], {}, 0
    for number, row in dispatches:
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
        cache.setdefault(head, replay_situation(package, head))
        rendered, error = cache[head]
        if error or rendered is None:
            uncheckable.append({"line": number, "reason": error or "replay failed"})
            continue
        if rendered.get("digest") != digest:
            uncheckable.append({"line": number, "reason": "digest differs from --at replay"})
            continue
        replayed += 1
        if chosen not in _action_ids(rendered, subject) and not _related_reason(row, rows):
            deviations.append({"line": number, "chosen": chosen, "reason": "chosen action is absent from replayed situation actions"})
    return {"package": str(package), "attempt": attempt, "trail": str(trail), "dispatches": len(dispatches), "no_digest": no_digest, "stale": _stale(dispatches), "deviations": deviations, "uncheckable": uncheckable, "replayed": replayed, "schema_violations": violations}


def _format_report(report):
    total, missing = report["dispatches"], len(report["no_digest"])
    percent = "n/a" if not total else f"{missing / total * 100:.1f}%"
    lines = ["dispatch-audit", f"package: {report['package']}", f"attempt: {report['attempt']}", f"trail: {report['trail']}", f"dispatches: {total}", f"no-digest: {missing}/{total} ({percent})", f"stale-digest: {len(report['stale'])} (threshold: {STALE_DIGEST_THRESHOLD} consecutive dispatches)", f"deviation: {len(report['deviations'])} (replayed: {report['replayed']}, uncheckable: {len(report['uncheckable'])})", f"schema-violations: {len(report['schema_violations'])}"]
    lines += [f"  stale digest {x['digest']} on lines {','.join(map(str, x['lines']))}" for x in report["stale"]]
    lines += [f"  deviation line {x['line']}: {x['reason']}" for x in report["deviations"]]
    lines += [f"  schema line {x['line']}: {', '.join(x['issues'])}" for x in report["schema_violations"]]
    lines += [f"  uncheckable line {x['line']}: {x['reason']}" for x in report["uncheckable"]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only dispatch/situation digest audit.")
    parser.add_argument("--package", type=Path, required=True)
    try:
        print(_format_report(audit_package(parser.parse_args(argv).package)))
    except (OSError, ValueError) as exc:
        print(f"dispatch-audit: ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
