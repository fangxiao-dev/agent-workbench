"""Read-only adapters for Situation, package state, and do-review rounds."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

TICKET_STATES = ("PENDING", "BLOCKED", "NEEDS-REVALIDATION", "SATISFIED", "RETIRED")
BAD_VERDICTS = {"UNCERTAIN", "INCOMPLETE", "FAIL"}


def read_package_state(package: str | Path) -> tuple[dict | None, str | None, str]:
    root = Path(package).expanduser().absolute()
    canonical = root / ".impl-package" / "state.json"
    path = canonical if canonical.exists() or canonical.is_symlink() else root / "state.json"
    if path.is_symlink() or (path.parent != root and path.parent.is_symlink()):
        return None, f"拒绝读取 symlink state：{path}", "undetermined"
    if not path.is_file():
        return None, f"state.json 不存在：{path}", "unconfirmed"
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, f"state.json 无法读取：{error}", "undetermined"
    if not isinstance(value, dict):
        return None, "state.json 顶层不是 object", "undetermined"
    attempt, tickets = value.get("attempt"), value.get("tickets")
    if not isinstance(attempt, dict) or not attempt.get("id") or not isinstance(tickets, dict):
        return None, "state.json 缺少有效 attempt.id/tickets", "undetermined"
    if any(not isinstance(row, dict) or row.get("state") not in TICKET_STATES for row in tickets.values()):
        return value, "state.json 含无法判定的 Ticket 状态", "undetermined"
    return value, None, "confirmed"


def _rounds_failure(path: Path, status: str, reason: str) -> dict:
    return {"path": str(path), "status": status, "group": None, "round": None,
            "phase": None, "open_seq": 0, "closed": False, "tracks": [],
            "open_findings": [], "open_findings_count": 0, "converged": False,
            "reasons": [reason]}


def _review_rounds_module(ledger: Path):
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / "do-review" / "scripts" / "review_rounds.py"
        if candidate.is_file():
            name = "_dev_loop_review_rounds_" + hashlib.sha256(str(candidate).encode("utf-8")).hexdigest()[:12]
            spec = importlib.util.spec_from_file_location(name, candidate)
            if spec is None or spec.loader is None:
                raise ImportError(f"无法加载 {candidate}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"同仓库未找到 review_rounds.py（{ledger}）")


def read_rounds_summary(path: str | Path) -> dict:
    """Summarize the latest ledger round without treating silence as PASS."""
    ledger = Path(path)
    if ledger.is_symlink():
        return _rounds_failure(ledger, "undetermined", "拒绝读取 symlink rounds 文件")
    if not ledger.is_file():
        return _rounds_failure(ledger, "unconfirmed", "rounds 文件不存在")
    try:
        state = json.loads(ledger.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return _rounds_failure(ledger, "undetermined", f"rounds JSON 无法读取：{error}")
    if not isinstance(state, dict) or not isinstance(state.get("rounds"), list) or not isinstance(state.get("findings"), list):
        return _rounds_failure(ledger, "undetermined", "rounds JSON 缺少 rounds/findings list")
    if not state["rounds"]:
        return _rounds_failure(ledger, "unconfirmed", "没有已登记的审阅轮次")
    latest = state["rounds"][-1]
    if not isinstance(latest, dict) or not isinstance(latest.get("tracks"), dict):
        return _rounds_failure(ledger, "undetermined", "最新轮次结构无效")
    group, phase, number = latest.get("group"), latest.get("phase"), latest.get("round")
    if not isinstance(group, str) or not group or not isinstance(phase, str) or not isinstance(number, int):
        return _rounds_failure(ledger, "undetermined", "最新轮次缺少 group/round/phase")
    tracks = [{"track": name, "verdict": result.get("verdict") if isinstance(result, dict) else None}
              for name, result in latest["tracks"].items()]
    if any(not isinstance(item, dict) for item in state["findings"]):
        return _rounds_failure(ledger, "undetermined", "findings 中存在无效记录")
    reasons = []
    if latest.get("closed") is not True:
        reasons.append("当前轮次尚未关闭")
    if not tracks:
        reasons.append("没有登记审阅轨")
    for track in tracks:
        verdict = track["verdict"]
        if verdict is None:
            reasons.append(f"{track['track']} 尚未返回")
        elif verdict != "PASS":
            reasons.append(f"{track['track']} verdict 为 {verdict}")

    try:
        review_rounds = _review_rounds_module(ledger)
        group_summary = review_rounds.group_status(ledger, group)
        findings = [{"id": finding.get("id"), "status": finding.get("status"), "ledger": str(source)}
                    for source, _, finding in review_rounds.group_findings(ledger, group)
                    if review_rounds.blocking(finding)]
    except Exception as error:
        return {"path": str(ledger), "status": "undetermined", "group": group, "round": number,
                "phase": phase, "open_seq": latest.get("openSeq", 0), "closed": latest.get("closed") is True,
                "tracks": tracks, "open_findings": [], "open_findings_count": 0, "converged": False,
                "reasons": [*reasons, f"无法确认 do-review group 收敛：{error}"]}
    if findings:
        reasons.append(f"仍有 {len(findings)} 个 open/fixed finding")
    group_reasons = group_summary.get("reasons", [])
    reasons.extend(f"group: {reason}" for reason in group_reasons)
    if not group_summary.get("converged") and not group_reasons:
        reasons.append(f"group state 为 {group_summary.get('state')}，尚未收敛")
    round_passed = (latest.get("closed") is True and bool(tracks)
                    and all(track["verdict"] == "PASS" for track in tracks) and not findings)
    converged = round_passed and bool(group_summary.get("converged"))
    return {"path": str(ledger), "status": "confirmed" if converged else "unconfirmed",
            "group": group, "round": number, "phase": phase, "open_seq": latest.get("openSeq", 0),
            "closed": latest.get("closed") is True, "tracks": tracks, "open_findings": findings,
            "open_findings_count": len(findings), "group_state": group_summary.get("state"),
            "group_complete": bool(group_summary.get("complete")), "converged": converged, "reasons": reasons}


def _situation_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "situation.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("同仓库未找到 impl-package/scripts/situation.py")


def _load_situation_module(source: Path):
    name = "_dev_loop_situation_" + hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_situation(package: str | Path) -> tuple[dict | None, str | None]:
    source = _situation_path()
    scripts = str(source.parent)
    inserted = scripts not in sys.path
    if inserted:
        sys.path.insert(0, scripts)
    try:
        module = _load_situation_module(source)
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = module.main(["render", "--package", str(Path(package).expanduser().absolute()), "--json"])
        if code:
            raise RuntimeError(errors.getvalue().strip() or f"situation 返回 {code}")
        value = json.loads(output.getvalue())
        if not isinstance(value, dict):
            raise ValueError("situation 投影不是 object")
        return value, None
    except Exception as error:
        return None, f"Situation projection undetermined：{error}"
    finally:
        if inserted:
            sys.path.remove(scripts)


def _round_files(package: Path) -> list[Path]:
    if not package.is_dir():
        return []
    return sorted(path for path in package.rglob("*.rounds.json")
                  if ".git" not in path.parts and not path.is_symlink())


def read_facts(package: str | Path) -> dict:
    """Read current package facts; a failed projection degrades to state.json."""
    root = Path(package).expanduser().absolute()
    projection, projection_error = None, None
    try:
        projection, projection_error = read_situation(root)
    except Exception as error:
        projection_error = f"Situation projection undetermined：{error}"
    state, state_error, state_status = read_package_state(root)
    source_state = ((projection or {}).get("sources") or {}).get("state") or {}
    source_state_warning = None
    if source_state.get("valid") is False:
        source_state_warning = source_state.get("reason") or "Situation 判定 state 无效"
        if not (state_status == "confirmed" and not (root / ".impl-package" / "state.json").exists()):
            state_status = "undetermined"
            state_error = source_state_warning
    warnings = [message for message in (projection_error, state_error) if message]
    warnings.extend(str(item) for item in (projection or {}).get("warnings", []))
    if source_state_warning and source_state_warning not in warnings:
        warnings.append(source_state_warning)
    try:
        rounds = [read_rounds_summary(path) for path in _round_files(root)]
    except OSError as error:
        rounds = []
        warnings.append(f"无法发现 rounds 文件：{error}")
    return {"projection": projection,
            "projection_status": "confirmed" if projection is not None else "undetermined",
            "state": state, "state_status": state_status, "rounds": rounds,
            "pending_returns": [item for item in (projection or {}).get("runnable", [])
                                if isinstance(item, dict) and item.get("source") == "pending-review"],
            "warnings": warnings}
