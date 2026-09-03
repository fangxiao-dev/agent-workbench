from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen


PROTOCOL_VERSION = 2
CONTEXT_VERSION = 2
RUNTIME_VERSION = 1
POLICY_VERSION = "STATIC_MONITOR_POLICY_V5"
DEFAULT_PORT = 43187
LAST_PORT = 43197
THREAD_ID_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
AUTOMATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
LEVELS = {"normal", "attention", "abnormal"}
SCOPES = {"session", "task"}
OBSERVATION_STATES = {"candidate", "confirmed"}
RESPONSES = {"pending", "accepted", "contested", "not-applicable"}
OBSERVATION_ID_RE = re.compile(r"^O([0-9]{3,})$")
MONITOR_FIELDS = {
    "version",
    "automationId",
    "monitorThreadId",
    "targetThreadId",
    "packagePath",
    "observedAt",
    "latestAssistantAt",
    "level",
    "summary",
    "evaluation",
}
EVALUATION_FIELDS = {"progress", "improvements", "next", "owner"}
OBSERVATION_STORE_FIELDS = {"version", "automationId", "nextObservationNumber", "observations"}
OBSERVATION_FIELDS = {
    "id",
    "topic",
    "content",
    "scope",
    "state",
    "sourceThreadId",
    "sourceMessageId",
    "confirmedAt",
    "response",
    "baselineConflict",
}
WRITE_EVALUATION_FIELDS = {
    "targetThreadId",
    "observedAt",
    "latestAssistantAt",
    "level",
    "summary",
    "evaluation",
}
BASELINE_FIELDS = {
    "goal",
    "chosenDirection",
    "coreInvariants",
    "nonGoals",
    "requiredEvidence",
    "requiredReviews",
    "manualAcceptance",
    "ownerDecisionBoundary",
}
CONTEXT_FIELDS = {
    "version",
    "automationId",
    "targetTitle",
    "policyVersion",
    "policySnapshot",
    "targetBaseline",
    "snapshotHash",
}
LEGACY_CONTEXT_FIELDS = CONTEXT_FIELDS | {"runtimeState"}
RUNTIME_STORE_FIELDS = {"version", "automationId", "runtimeState"}
INIT_CONTEXT_FIELDS = {"targetTitle", "targetBaseline"}
SOURCE_SCAN_FIELDS = {"lastSeenTurnId", "lastSeenUserMessageId", "backfillComplete", "threadUpdatedAt"}
RUNTIME_FIELDS = {
    "sourceScanState",
    "observationFingerprint",
    "pendingCandidateIds",
    "lastMainMessageId",
    "lastEvaluationFingerprint",
    "incompleteStreak",
    "baselineStatus",
    "activeConcernFingerprints",
    "lastTargetStatus",
    "lastTargetTurnId",
    "lastFallbackTurnId",
    "lastFallbackAt",
}
WRITE_CYCLE_FIELDS = WRITE_EVALUATION_FIELDS | {"runtimeState"}
TARGET_STATUSES = {"active", "idle", "blocked", "terminal", "unknown"}
BASELINE_STATUSES = {"current", "stale"}

POLICY_SNAPSHOT = {
    "evaluation": [
        "targetBaseline 是冻结的任务合同；confirmed observations 是当前 Owner 指令。两者冲突时报告，不静默覆盖。",
        "按最新 task 状态评价进展、coherent step、worker lifecycle、review、evidence、manual acceptance、方向与 Owner 分叉。",
        "缺失信息不推断为完成；worker return、focused tests 或局部提交不自动等于 Ticket、Gate 或 package closure。",
    ],
    "observations": [
        "只有直接改变目标任务授权、执行方式、验收要求或 Owner 决策边界的纠偏才是本任务 observation。",
        "针对监控模板、CLI、dashboard、prompt 或 observation 机制本身的反馈属于工具调试，不写入目标任务 sidecar。",
        "Owner 明确的纠偏直接记为 confirmed；监控推断先记 candidate，pending candidate 同时最多一条。",
        "同一语义 topic 原地更新并保留短 ID；询问、讨论、附件或引用本身不形成 observation。",
        "confirmed observation 与 baseline 冲突时报告 baselineConflict，不覆盖 baseline；合同变化只标 baselineStatus=stale。",
    ],
    "visibility": "read_thread 返回 items: [] 表示内容不可见，不能推断没有 userMessage、没有续行请求或不存在 blocker。",
    "intervention": [
        "默认不向 target 发送消息。只有 confirmed observation 明确授权某类消息且当前事实符合其条件时才可发送。",
        "candidate observation 不授权动作。发送时记录采用的 observation ID，并用 runtime 的 target turn ID 去重。",
    ],
    "levels": {
        "normal": "明确 terminal/closed 且无 finding、review、evidence 或 manual acceptance 缺口。",
        "attention": "仍有 active step、pending Gate、调度或证据缺口、confirmed 纠偏未吸收或 baselineConflict。",
        "abnormal": "同一 Topic 连续两轮显式 INCOMPLETE/BLOCKED、重复违背纠偏、closure 与 evidence 矛盾、baseline stale 或 CLI 失败。",
    },
    "communication": [
        "Owner 通知默认只写当前做到哪里、是否正常、接下来做什么、是否需要 Owner。",
        "内部执行术语只有在它本身构成故障时才出现，并同时解释真实对象、动作和影响。",
        "监控器自身配置变化只在导致监控中断或需要 Owner 操作时通知。",
    ],
    "boundaries": "只读两个 task；仅通过本 CLI 写监控 sidecar。除 confirmed observation 明确授权的窄范围消息外，不干预 target；不得修改任务包、代码、数据库、运行环境或控制 worker。",
}


class MonitorProgressError(ValueError):
    pass


def _expect_fields(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MonitorProgressError(f"{label} must be a JSON object")
    actual = set(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        raise MonitorProgressError(f"{label} fields mismatch: missing={missing}, unknown={unknown}")
    return value


def _text(value: Any, label: str, *, limit: int = 4000, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise MonitorProgressError(f"{label} must be a non-empty string")
    if len(value) > limit:
        raise MonitorProgressError(f"{label} exceeds {limit} characters")
    return value.strip()


def _iso(value: Any, label: str, *, nullable: bool = False) -> str | None:
    text = _text(value, label, nullable=nullable)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MonitorProgressError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise MonitorProgressError(f"{label} must include a timezone")
    return text


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalise_thread_id(value: str) -> str:
    prefix = "codex://threads/"
    thread_id = value[len(prefix) :] if value.startswith(prefix) else value
    if not THREAD_ID_RE.fullmatch(thread_id):
        raise MonitorProgressError("invalid Codex thread id")
    return thread_id.lower()


def _automation_id(value: Any) -> str:
    if not isinstance(value, str) or not AUTOMATION_ID_RE.fullmatch(value):
        raise MonitorProgressError("invalid automation id")
    return value


def _root(value: str | Path) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise MonitorProgressError(f"workspace root is unavailable: {root}")
    return root


def _package(root: Path, value: str | Path) -> Path:
    package = Path(value).resolve()
    if not package.is_dir():
        raise MonitorProgressError(f"package is unavailable: {package}")
    try:
        package.relative_to(root)
    except ValueError as exc:
        raise MonitorProgressError("package must be inside workspace root") from exc
    return package


def _instance_paths(root: Path, automation_id: str) -> tuple[Path, Path]:
    base = root / ".progress-record" / "codex-progress-dashboard"
    return base / "monitors" / f"{automation_id}.json", base / "observations" / f"{automation_id}.json"


def _context_path(root: Path, automation_id: str) -> Path:
    return root / ".progress-record" / "codex-progress-dashboard" / "contexts" / f"{automation_id}.json"


def _runtime_path(root: Path, automation_id: str) -> Path:
    return root / ".progress-record" / "codex-progress-dashboard" / "runtime" / f"{automation_id}.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MonitorProgressError(f"monitor state is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorProgressError(f"cannot read monitor state: {path}") from exc


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _string_list(value: Any, label: str, *, limit: int = 2000) -> list[str]:
    if not isinstance(value, list):
        raise MonitorProgressError(f"{label} must be an array")
    return [_text(item, f"{label}[]", limit=limit) for item in value]


def _optional_token(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not MESSAGE_ID_RE.fullmatch(value):
        raise MonitorProgressError(f"{label} must be a valid token or null")
    return value


def validate_baseline(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, BASELINE_FIELDS, "target baseline")
    return {
        "goal": _text(record["goal"], "target baseline.goal"),
        "chosenDirection": _string_list(record["chosenDirection"], "target baseline.chosenDirection"),
        "coreInvariants": _string_list(record["coreInvariants"], "target baseline.coreInvariants"),
        "nonGoals": _string_list(record["nonGoals"], "target baseline.nonGoals"),
        "requiredEvidence": _string_list(record["requiredEvidence"], "target baseline.requiredEvidence"),
        "requiredReviews": _string_list(record["requiredReviews"], "target baseline.requiredReviews"),
        "manualAcceptance": _string_list(record["manualAcceptance"], "target baseline.manualAcceptance"),
        "ownerDecisionBoundary": _text(
            record["ownerDecisionBoundary"], "target baseline.ownerDecisionBoundary"
        ),
    }


def _observation_runtime(observations: list[dict[str, Any]]) -> dict[str, Any]:
    confirmed = sum(item["state"] == "confirmed" for item in observations)
    candidates = sum(item["state"] == "candidate" for item in observations)
    return {
        "observationFingerprint": f"confirmed:{confirmed}|candidate:{candidates}",
        "pendingCandidateIds": [
            item["id"] for item in observations if item["state"] == "candidate" and item["response"] == "pending"
        ],
    }


def default_runtime_state(observations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    empty_scan = {
        "lastSeenTurnId": None,
        "lastSeenUserMessageId": None,
        "backfillComplete": False,
        "threadUpdatedAt": None,
    }
    return {
        "sourceScanState": {"monitor": dict(empty_scan), "target": dict(empty_scan)},
        **_observation_runtime(observations or []),
        "lastMainMessageId": None,
        "lastEvaluationFingerprint": None,
        "incompleteStreak": 0,
        "baselineStatus": "current",
        "activeConcernFingerprints": [],
        "lastTargetStatus": "unknown",
        "lastTargetTurnId": None,
        "lastFallbackTurnId": None,
        "lastFallbackAt": None,
    }


def validate_runtime_state(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, RUNTIME_FIELDS, "runtime state")
    scans = _expect_fields(record["sourceScanState"], {"monitor", "target"}, "runtime source scan state")
    validated_scans: dict[str, dict[str, Any]] = {}
    for source in ("monitor", "target"):
        scan = _expect_fields(scans[source], SOURCE_SCAN_FIELDS, f"runtime source scan state.{source}")
        if not isinstance(scan["backfillComplete"], bool):
            raise MonitorProgressError(f"runtime source scan state.{source}.backfillComplete must be boolean")
        validated_scans[source] = {
            "lastSeenTurnId": _optional_token(scan["lastSeenTurnId"], f"runtime.{source}.lastSeenTurnId"),
            "lastSeenUserMessageId": _optional_token(
                scan["lastSeenUserMessageId"], f"runtime.{source}.lastSeenUserMessageId"
            ),
            "backfillComplete": scan["backfillComplete"],
            "threadUpdatedAt": _iso(
                scan["threadUpdatedAt"], f"runtime.{source}.threadUpdatedAt", nullable=True
            ),
        }
    pending_ids = record["pendingCandidateIds"]
    if not isinstance(pending_ids, list) or any(
        not isinstance(item, str) or not OBSERVATION_ID_RE.fullmatch(item) for item in pending_ids
    ):
        raise MonitorProgressError("runtime.pendingCandidateIds must contain observation ids")
    incomplete_streak = record["incompleteStreak"]
    if not isinstance(incomplete_streak, int) or isinstance(incomplete_streak, bool) or incomplete_streak < 0:
        raise MonitorProgressError("runtime.incompleteStreak must be a non-negative integer")
    baseline_status = record["baselineStatus"]
    if baseline_status not in BASELINE_STATUSES:
        raise MonitorProgressError(f"runtime.baselineStatus must be one of {sorted(BASELINE_STATUSES)}")
    target_status = record["lastTargetStatus"]
    if target_status not in TARGET_STATUSES:
        raise MonitorProgressError(f"runtime.lastTargetStatus must be one of {sorted(TARGET_STATUSES)}")
    return {
        "sourceScanState": validated_scans,
        "observationFingerprint": _text(record["observationFingerprint"], "runtime.observationFingerprint"),
        "pendingCandidateIds": pending_ids,
        "lastMainMessageId": _optional_token(record["lastMainMessageId"], "runtime.lastMainMessageId"),
        "lastEvaluationFingerprint": _text(
            record["lastEvaluationFingerprint"], "runtime.lastEvaluationFingerprint", nullable=True
        ),
        "incompleteStreak": incomplete_streak,
        "baselineStatus": baseline_status,
        "activeConcernFingerprints": _string_list(
            record["activeConcernFingerprints"], "runtime.activeConcernFingerprints", limit=500
        ),
        "lastTargetStatus": target_status,
        "lastTargetTurnId": _optional_token(record["lastTargetTurnId"], "runtime.lastTargetTurnId"),
        "lastFallbackTurnId": _optional_token(record["lastFallbackTurnId"], "runtime.lastFallbackTurnId"),
        "lastFallbackAt": _iso(record["lastFallbackAt"], "runtime.lastFallbackAt", nullable=True),
    }


def _snapshot_hash(
    target_baseline: dict[str, Any],
    policy_version: str = POLICY_VERSION,
    policy_snapshot: dict[str, Any] = POLICY_SNAPSHOT,
) -> str:
    payload = {
        "policyVersion": policy_version,
        "policySnapshot": policy_snapshot,
        "targetBaseline": target_baseline,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_context(value: Any, *, require_current_policy: bool = True) -> dict[str, Any]:
    record = _expect_fields(value, CONTEXT_FIELDS, "monitor context")
    if record["version"] != CONTEXT_VERSION:
        raise MonitorProgressError(f"monitor context version must be {CONTEXT_VERSION}")
    policy_version = _text(record["policyVersion"], "monitor context.policyVersion", limit=200)
    policy_snapshot = record["policySnapshot"]
    if not isinstance(policy_snapshot, dict):
        raise MonitorProgressError("monitor context.policySnapshot must be a JSON object")
    if require_current_policy and (policy_version != POLICY_VERSION or policy_snapshot != POLICY_SNAPSHOT):
        raise MonitorProgressError("monitor context policy snapshot does not match this CLI")
    baseline = validate_baseline(record["targetBaseline"])
    snapshot_hash = _text(record["snapshotHash"], "monitor context.snapshotHash", limit=64)
    if snapshot_hash != _snapshot_hash(baseline, policy_version, policy_snapshot):
        raise MonitorProgressError("monitor context snapshot hash mismatch")
    return {
        "version": CONTEXT_VERSION,
        "automationId": _automation_id(record["automationId"]),
        "targetTitle": _text(record["targetTitle"], "monitor context.targetTitle", limit=500),
        "policyVersion": policy_version,
        "policySnapshot": policy_snapshot,
        "targetBaseline": baseline,
        "snapshotHash": snapshot_hash,
    }


def validate_runtime_store(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, RUNTIME_STORE_FIELDS, "monitor runtime store")
    if record["version"] != RUNTIME_VERSION:
        raise MonitorProgressError(f"monitor runtime version must be {RUNTIME_VERSION}")
    return {
        "version": RUNTIME_VERSION,
        "automationId": _automation_id(record["automationId"]),
        "runtimeState": validate_runtime_state(record["runtimeState"]),
    }


def validate_legacy_context(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    record = _expect_fields(value, LEGACY_CONTEXT_FIELDS, "legacy monitor context")
    if record["version"] != 1:
        raise MonitorProgressError("legacy monitor context version must be 1")
    policy_version = _text(record["policyVersion"], "legacy monitor context.policyVersion", limit=200)
    policy_snapshot = record["policySnapshot"]
    if not isinstance(policy_snapshot, dict):
        raise MonitorProgressError("legacy monitor context.policySnapshot must be a JSON object")
    baseline = validate_baseline(record["targetBaseline"])
    snapshot_hash = _text(record["snapshotHash"], "legacy monitor context.snapshotHash", limit=64)
    if snapshot_hash != _snapshot_hash(baseline, policy_version, policy_snapshot):
        raise MonitorProgressError("legacy monitor context snapshot hash mismatch")
    static_context = {
        "version": CONTEXT_VERSION,
        "automationId": _automation_id(record["automationId"]),
        "targetTitle": _text(record["targetTitle"], "legacy monitor context.targetTitle", limit=500),
        "policyVersion": policy_version,
        "policySnapshot": policy_snapshot,
        "targetBaseline": baseline,
        "snapshotHash": snapshot_hash,
    }
    return static_context, validate_runtime_state(record["runtimeState"])


def validate_evaluation(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    record = _expect_fields(value, EVALUATION_FIELDS, "evaluation")
    improvements = record["improvements"]
    if not isinstance(improvements, list) or len(improvements) > 3:
        raise MonitorProgressError("evaluation.improvements must be an array of at most three strings")
    return {
        "progress": _text(record["progress"], "evaluation.progress"),
        "improvements": [_text(item, "evaluation.improvements[]", limit=2000) for item in improvements],
        "next": _text(record["next"], "evaluation.next"),
        "owner": _text(record["owner"], "evaluation.owner", nullable=True),
    }


def validate_monitor(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, MONITOR_FIELDS, "monitor")
    if record["version"] != PROTOCOL_VERSION:
        raise MonitorProgressError(f"monitor version must be {PROTOCOL_VERSION}")
    automation_id = _automation_id(record["automationId"])
    level = record["level"]
    if level not in LEVELS:
        raise MonitorProgressError(f"monitor.level must be one of {sorted(LEVELS)}")
    package = Path(_text(record["packagePath"], "monitor.packagePath")).resolve()
    return {
        "version": PROTOCOL_VERSION,
        "automationId": automation_id,
        "monitorThreadId": normalise_thread_id(record["monitorThreadId"]),
        "targetThreadId": normalise_thread_id(record["targetThreadId"]),
        "packagePath": str(package),
        "observedAt": _iso(record["observedAt"], "monitor.observedAt"),
        "latestAssistantAt": _iso(record["latestAssistantAt"], "monitor.latestAssistantAt", nullable=True),
        "level": level,
        "summary": _text(record["summary"], "monitor.summary", limit=2000),
        "evaluation": validate_evaluation(record["evaluation"]),
    }


def _topic_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def validate_observation(value: Any, *, allow_new: bool = False) -> dict[str, Any]:
    record = _expect_fields(value, OBSERVATION_FIELDS, "observation")
    observation_id = record["id"]
    message_id = record["sourceMessageId"]
    if observation_id is None and allow_new:
        pass
    elif not isinstance(observation_id, str) or not OBSERVATION_ID_RE.fullmatch(observation_id):
        raise MonitorProgressError("invalid observation id")
    if not isinstance(message_id, str) or not MESSAGE_ID_RE.fullmatch(message_id):
        raise MonitorProgressError("invalid source message id")
    scope = record["scope"]
    state = record["state"]
    response = record["response"]
    if scope not in SCOPES:
        raise MonitorProgressError(f"observation.scope must be one of {sorted(SCOPES)}")
    if state not in OBSERVATION_STATES:
        raise MonitorProgressError(f"observation.state must be one of {sorted(OBSERVATION_STATES)}")
    if response not in RESPONSES:
        raise MonitorProgressError(f"observation.response must be one of {sorted(RESPONSES)}")
    confirmed_at = record["confirmedAt"]
    if state == "confirmed":
        confirmed_at = _iso(confirmed_at, "observation.confirmedAt")
    elif confirmed_at is not None:
        raise MonitorProgressError("candidate observations must have confirmedAt=null")
    if not isinstance(record["baselineConflict"], bool):
        raise MonitorProgressError("observation.baselineConflict must be boolean")
    return {
        "id": observation_id,
        "topic": _text(record["topic"], "observation.topic", limit=200),
        "content": _text(record["content"], "observation.content", limit=2000),
        "scope": scope,
        "state": state,
        "sourceThreadId": normalise_thread_id(record["sourceThreadId"]),
        "sourceMessageId": message_id,
        "confirmedAt": confirmed_at,
        "response": response,
        "baselineConflict": record["baselineConflict"],
    }


def validate_observation_store(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, OBSERVATION_STORE_FIELDS, "observation store")
    if record["version"] != PROTOCOL_VERSION:
        raise MonitorProgressError(f"observation store version must be {PROTOCOL_VERSION}")
    observations = record["observations"]
    if not isinstance(observations, list):
        raise MonitorProgressError("observation store observations must be an array")
    next_number = record["nextObservationNumber"]
    if not isinstance(next_number, int) or isinstance(next_number, bool) or next_number < 1:
        raise MonitorProgressError("observation store nextObservationNumber must be a positive integer")
    validated = [validate_observation(item) for item in observations]
    ids = [item["id"] for item in validated]
    if len(ids) != len(set(ids)):
        raise MonitorProgressError("observation ids must be unique")
    highest_number = max(
        (int(OBSERVATION_ID_RE.fullmatch(item_id).group(1)) for item_id in ids),
        default=0,
    )
    if next_number <= highest_number:
        raise MonitorProgressError("observation store nextObservationNumber must exceed all existing ids")
    topics = [_topic_key(item["topic"]) for item in validated]
    if len(topics) != len(set(topics)):
        raise MonitorProgressError("observation topics must be unique")
    return {
        "version": PROTOCOL_VERSION,
        "automationId": _automation_id(record["automationId"]),
        "nextObservationNumber": next_number,
        "observations": validated,
    }


def init_instance(
    root: Path,
    automation_id: str,
    monitor_thread_id: str,
    target_thread_id: str,
    package_path: Path,
) -> dict[str, Any]:
    monitor_path, observation_path = _instance_paths(root, automation_id)
    if monitor_path.exists() or observation_path.exists():
        if not monitor_path.is_file() or not observation_path.is_file():
            raise MonitorProgressError("existing monitor instance is incomplete")
        current = read_instance(root, automation_id)
        monitor = current["monitor"]
        expected = {
            "monitorThreadId": monitor_thread_id,
            "targetThreadId": target_thread_id,
            "packagePath": str(package_path),
        }
        if any(monitor[key] != value for key, value in expected.items()):
            raise MonitorProgressError("existing monitor instance identity does not match")
        return current
    monitor = validate_monitor(
        {
            "version": PROTOCOL_VERSION,
            "automationId": automation_id,
            "monitorThreadId": monitor_thread_id,
            "targetThreadId": target_thread_id,
            "packagePath": str(package_path),
            "observedAt": _now(),
            "latestAssistantAt": None,
            "level": "attention",
            "summary": "监控已创建，等待首次评价；Owner 暂无待决事项。",
            "evaluation": None,
        }
    )
    observation_store = validate_observation_store(
        {
            "version": PROTOCOL_VERSION,
            "automationId": automation_id,
            "nextObservationNumber": 1,
            "observations": [],
        }
    )
    _atomic_write(monitor_path, monitor)
    _atomic_write(observation_path, observation_store)
    return {"monitor": monitor, "observations": []}


def _read_observation_store(root: Path, automation_id: str) -> dict[str, Any]:
    observation_path = _instance_paths(root, automation_id)[1]
    return validate_observation_store(_read_json(observation_path))


def read_instance(root: Path, automation_id: str) -> dict[str, Any]:
    monitor_path = _instance_paths(root, automation_id)[0]
    monitor = validate_monitor(_read_json(monitor_path))
    observation_store = _read_observation_store(root, automation_id)
    if monitor["automationId"] != automation_id or observation_store["automationId"] != automation_id:
        raise MonitorProgressError("monitor instance automation id mismatch")
    return {"monitor": monitor, "observations": observation_store["observations"]}


def init_context(root: Path, automation_id: str, payload: Any) -> dict[str, Any]:
    record = _expect_fields(payload, INIT_CONTEXT_FIELDS, "context init payload")
    instance = read_instance(root, automation_id)
    baseline = validate_baseline(record["targetBaseline"])
    expected = validate_context(
        {
            "version": CONTEXT_VERSION,
            "automationId": automation_id,
            "targetTitle": record["targetTitle"],
            "policyVersion": POLICY_VERSION,
            "policySnapshot": POLICY_SNAPSHOT,
            "targetBaseline": baseline,
            "snapshotHash": _snapshot_hash(baseline),
        }
    )
    runtime_store = validate_runtime_store(
        {
            "version": RUNTIME_VERSION,
            "automationId": automation_id,
            "runtimeState": default_runtime_state(instance["observations"]),
        }
    )
    path = _context_path(root, automation_id)
    if path.exists():
        current = read_context(root, automation_id)["context"]
        immutable_fields = ("automationId", "targetTitle", "policyVersion", "policySnapshot", "targetBaseline", "snapshotHash")
        if any(current[field] != expected[field] for field in immutable_fields):
            raise MonitorProgressError("existing monitor context identity or snapshot does not match")
        return {"context": current, **instance}
    if _runtime_path(root, automation_id).exists():
        raise MonitorProgressError("monitor runtime exists without a static context")
    _atomic_write(_runtime_path(root, automation_id), runtime_store)
    _atomic_write(path, expected)
    return {"context": {**expected, "runtimeState": runtime_store["runtimeState"]}, **instance}


def read_context(root: Path, automation_id: str) -> dict[str, Any]:
    context = validate_context(_read_json(_context_path(root, automation_id)))
    runtime_store = validate_runtime_store(_read_json(_runtime_path(root, automation_id)))
    instance = read_instance(root, automation_id)
    if context["automationId"] != automation_id or runtime_store["automationId"] != automation_id:
        raise MonitorProgressError("monitor context automation id mismatch")
    return {"context": {**context, "runtimeState": runtime_store["runtimeState"]}, **instance}


def read_static(root: Path, automation_id: str) -> dict[str, Any]:
    context = validate_context(_read_json(_context_path(root, automation_id)))
    monitor = read_instance(root, automation_id)["monitor"]
    if context["automationId"] != automation_id:
        raise MonitorProgressError("monitor context automation id mismatch")
    return {
        "staticContext": {
            **context,
            "monitorThreadId": monitor["monitorThreadId"],
            "targetThreadId": monitor["targetThreadId"],
            "packagePath": monitor["packagePath"],
        }
    }


def read_cycle(root: Path, automation_id: str) -> dict[str, Any]:
    context = validate_context(
        _read_json(_context_path(root, automation_id)), require_current_policy=False
    )
    runtime_store = validate_runtime_store(_read_json(_runtime_path(root, automation_id)))
    instance = read_instance(root, automation_id)
    if context["automationId"] != automation_id or runtime_store["automationId"] != automation_id:
        raise MonitorProgressError("monitor context automation id mismatch")
    current = context["policyVersion"] == POLICY_VERSION and context["policySnapshot"] == POLICY_SNAPSHOT
    return {
        "staticRef": {
            "contextVersion": context["version"],
            "policyVersion": context["policyVersion"],
            "snapshotHash": context["snapshotHash"],
            "status": "current" if current else "reload-required",
        },
        "runtimeState": runtime_store["runtimeState"],
        **instance,
    }


def refresh_context_policy(root: Path, automation_id: str) -> dict[str, Any]:
    path = _context_path(root, automation_id)
    raw_context = _read_json(path)
    if isinstance(raw_context, dict) and raw_context.get("version") == 1:
        context, runtime_state = validate_legacy_context(raw_context)
    else:
        context = validate_context(raw_context, require_current_policy=False)
        runtime_state = validate_runtime_store(_read_json(_runtime_path(root, automation_id)))["runtimeState"]
    instance = read_instance(root, automation_id)
    if context["automationId"] != automation_id:
        raise MonitorProgressError("monitor context automation id mismatch")
    updated = validate_context(
        {
            **context,
            "policyVersion": POLICY_VERSION,
            "policySnapshot": POLICY_SNAPSHOT,
            "snapshotHash": _snapshot_hash(context["targetBaseline"]),
        }
    )
    runtime_store = validate_runtime_store(
        {"version": RUNTIME_VERSION, "automationId": automation_id, "runtimeState": runtime_state}
    )
    _atomic_write(_runtime_path(root, automation_id), runtime_store)
    _atomic_write(path, updated)
    return {"context": {**updated, "runtimeState": runtime_state}, **instance}


def _updated_monitor(current: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    return validate_monitor(
        {
            **current,
            "targetThreadId": record["targetThreadId"],
            "observedAt": record["observedAt"],
            "latestAssistantAt": record["latestAssistantAt"],
            "level": record["level"],
            "summary": record["summary"],
            "evaluation": record["evaluation"],
        }
    )


def write_evaluation(root: Path, automation_id: str, payload: Any) -> dict[str, Any]:
    record = _expect_fields(payload, WRITE_EVALUATION_FIELDS, "evaluation write payload")
    current = read_instance(root, automation_id)["monitor"]
    updated = _updated_monitor(current, record)
    _atomic_write(_instance_paths(root, automation_id)[0], updated)
    return updated


def write_cycle(root: Path, automation_id: str, payload: Any) -> dict[str, Any]:
    record = _expect_fields(payload, WRITE_CYCLE_FIELDS, "cycle write payload")
    current = read_context(root, automation_id)
    runtime_state = {
        **validate_runtime_state(record["runtimeState"]),
        **_observation_runtime(current["observations"]),
    }
    runtime_store = validate_runtime_store(
        {"version": RUNTIME_VERSION, "automationId": automation_id, "runtimeState": runtime_state}
    )
    updated_monitor = _updated_monitor(current["monitor"], record)
    _atomic_write(_runtime_path(root, automation_id), runtime_store)
    _atomic_write(_instance_paths(root, automation_id)[0], updated_monitor)
    static_context = validate_context(_read_json(_context_path(root, automation_id)))
    return {
        "context": {**static_context, "runtimeState": runtime_state},
        "monitor": updated_monitor,
        "observations": current["observations"],
    }


def _next_observation_id(next_number: int) -> str:
    return f"O{next_number:03d}"


def put_observation(root: Path, automation_id: str, payload: Any) -> dict[str, Any]:
    incoming = validate_observation(payload, allow_new=True)
    observation_store = _read_observation_store(root, automation_id)
    observations = list(observation_store["observations"])
    by_id = {item["id"]: item for item in observations}
    if incoming["id"] is None:
        topic_key = _topic_key(incoming["topic"])
        duplicate = next((item for item in observations if _topic_key(item["topic"]) == topic_key), None)
        if duplicate:
            raise MonitorProgressError(f"observation topic already exists: {duplicate['id']}")
        incoming["id"] = _next_observation_id(observation_store["nextObservationNumber"])
        observation_store["nextObservationNumber"] += 1
        observations.append(incoming)
    else:
        existing = by_id.get(incoming["id"])
        if existing is None:
            raise MonitorProgressError(f"unknown observation id: {incoming['id']}")
        transition = (existing["state"], incoming["state"])
        allowed = {
            ("candidate", "candidate"),
            ("candidate", "confirmed"),
            ("confirmed", "confirmed"),
        }
        if transition not in allowed:
            raise MonitorProgressError(f"invalid observation transition: {transition[0]} -> {transition[1]}")
        duplicate = next(
            (
                item
                for item in observations
                if item["id"] != incoming["id"] and _topic_key(item["topic"]) == _topic_key(incoming["topic"])
            ),
            None,
        )
        if duplicate:
            raise MonitorProgressError(f"observation topic already exists: {duplicate['id']}")
        index = observations.index(existing)
        observations[index] = incoming
    updated = validate_observation_store(
        {**observation_store, "observations": observations}
    )
    _atomic_write(_instance_paths(root, automation_id)[1], updated)
    return {"observation": incoming, "observations": updated["observations"]}


def remove_observation(root: Path, automation_id: str, observation_id: str) -> dict[str, Any]:
    if not OBSERVATION_ID_RE.fullmatch(observation_id):
        raise MonitorProgressError("invalid observation id")
    observation_store = _read_observation_store(root, automation_id)
    observations = list(observation_store["observations"])
    if not any(item["id"] == observation_id for item in observations):
        raise MonitorProgressError(f"unknown observation id: {observation_id}")
    remaining = [item for item in observations if item["id"] != observation_id]
    updated = validate_observation_store(
        {**observation_store, "observations": remaining}
    )
    _atomic_write(_instance_paths(root, automation_id)[1], updated)
    return {"removed": observation_id, "observations": updated["observations"]}


def latest_for_package(root: Path, package_path: Path) -> dict[str, Any] | None:
    monitor_dir = root / ".progress-record" / "codex-progress-dashboard" / "monitors"
    if not monitor_dir.is_dir():
        return None
    candidates: list[dict[str, Any]] = []
    for path in monitor_dir.glob("*.json"):
        try:
            monitor = validate_monitor(_read_json(path))
        except MonitorProgressError:
            continue
        if Path(monitor["packagePath"]).resolve() == package_path.resolve():
            candidates.append(monitor)
    if not candidates:
        return None
    monitor = max(candidates, key=lambda item: _timestamp(item["observedAt"]))
    try:
        observations = read_instance(root, monitor["automationId"])["observations"]
    except MonitorProgressError:
        confirmed: list[dict[str, Any]] = []
    else:
        confirmed = sorted(
            (item for item in observations if item["state"] == "confirmed"),
            key=lambda item: _timestamp(item["confirmedAt"]),
            reverse=True,
        )[:5]
    return {"monitor": monitor, "observations": confirmed}


def schema_contract() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "contextVersion": CONTEXT_VERSION,
        "runtimeVersion": RUNTIME_VERSION,
        "policyVersion": POLICY_VERSION,
        "monitor": {"required": sorted(MONITOR_FIELDS), "levels": sorted(LEVELS)},
        "evaluation": {"required": sorted(EVALUATION_FIELDS), "maxImprovements": 3},
        "observationStore": {"required": sorted(OBSERVATION_STORE_FIELDS)},
        "observation": {
            "required": sorted(OBSERVATION_FIELDS),
            "scopes": sorted(SCOPES),
            "states": sorted(OBSERVATION_STATES),
            "responses": sorted(RESPONSES),
        },
        "writeEvaluationInput": {"required": sorted(WRITE_EVALUATION_FIELDS)},
        "context": {"required": sorted(CONTEXT_FIELDS)},
        "runtimeStore": {"required": sorted(RUNTIME_STORE_FIELDS), "runtimeRequired": sorted(RUNTIME_FIELDS)},
        "initContextInput": {"required": sorted(INIT_CONTEXT_FIELDS)},
        "writeCycleInput": {"required": sorted(WRITE_CYCLE_FIELDS)},
        "refreshContextPolicy": {"preserves": ["targetBaseline", "runtimeState", "monitor", "observations"]},
    }


def _find_root(package_path: Path) -> Path:
    for candidate in (package_path, *package_path.parents):
        if (candidate / ".git").exists():
            return candidate.resolve()
    raise MonitorProgressError("package is not inside a Git workspace")


def _health(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, OSError, URLError, json.JSONDecodeError):
        return False
    return payload.get("monitorProgressProtocol") == PROTOCOL_VERSION


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        return connection.connect_ex(("127.0.0.1", port)) != 0


def _start_server(port: int, db_path: Path | None) -> None:
    server = Path(__file__).resolve().parent / "codex_progress_dashboard" / "server.py"
    command = [sys.executable, str(server), "--port", str(port)]
    if db_path is not None:
        command.extend(["--db", str(db_path)])
    kwargs: dict[str, Any] = {
        "cwd": str(server.parent),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def _wait_for_server(port: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _health(port):
            return
        time.sleep(0.1)
    raise MonitorProgressError("progress dashboard did not become ready within 5 seconds")


def _target_packages(port: int, target_thread_id: str) -> list[dict[str, Any]]:
    url = f"http://127.0.0.1:{port}/api/tasks/{quote(target_thread_id)}/packages"
    try:
        with urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, OSError, URLError, json.JSONDecodeError) as exc:
        raise MonitorProgressError("target task is unavailable to the progress dashboard") from exc
    packages = payload.get("packages")
    if not isinstance(packages, list):
        raise MonitorProgressError("progress dashboard returned malformed package data")
    return packages


def open_dashboard(target: str, package: Path, *, no_browser: bool = False, db_path: Path | None = None) -> dict[str, Any]:
    target_thread_id = normalise_thread_id(target)
    package_path = package.resolve()
    if not package_path.is_dir():
        raise MonitorProgressError(f"package is unavailable: {package_path}")
    root = _find_root(package_path)
    relative_package = package_path.relative_to(root).as_posix()
    port = next((candidate for candidate in range(DEFAULT_PORT, LAST_PORT + 1) if _health(candidate)), None)
    reused = port is not None
    if port is None:
        port = next((candidate for candidate in range(DEFAULT_PORT, LAST_PORT + 1) if _port_available(candidate)), None)
        if port is None:
            raise MonitorProgressError(f"no dashboard port available in {DEFAULT_PORT}-{LAST_PORT}")
        _start_server(port, db_path)
        _wait_for_server(port)
    packages = _target_packages(port, target_thread_id)
    if not any(item.get("path") == relative_package for item in packages if isinstance(item, dict)):
        raise MonitorProgressError("package does not belong to the target task workspace")
    query = urlencode({"task": target_thread_id, "package": relative_package})
    url = f"http://127.0.0.1:{port}/?{query}"
    if not no_browser and not webbrowser.open(url):
        raise MonitorProgressError("browser did not accept the dashboard URL")
    return {"url": url, "port": port, "reused": reused, "targetThreadId": target_thread_id, "packagePath": str(package_path)}


def _stdin_json() -> Any:
    try:
        return json.loads(sys.stdin.readline())
    except json.JSONDecodeError as exc:
        raise MonitorProgressError("stdin must contain one compact JSON value followed by a newline") from exc


def _common_instance_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--automation-id", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validated Monitor Progress v2 storage and dashboard CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    open_parser = subparsers.add_parser("open", help="start or reuse the dashboard and open a task package")
    open_parser.add_argument("--target", required=True)
    open_parser.add_argument("--package", required=True, type=Path)
    open_parser.add_argument("--db", type=Path)
    open_parser.add_argument("--no-browser", action="store_true")

    init_parser = subparsers.add_parser("init", help="create a v2 monitor instance")
    _common_instance_arguments(init_parser)
    init_parser.add_argument("--monitor-thread", required=True)
    init_parser.add_argument("--target-thread", required=True)
    init_parser.add_argument("--package", required=True, type=Path)

    read_parser = subparsers.add_parser("read", help="validate and print a v2 monitor instance")
    _common_instance_arguments(read_parser)

    init_context_parser = subparsers.add_parser(
        "init-context", help="create the validated policy, baseline, and runtime context from stdin"
    )
    _common_instance_arguments(init_context_parser)

    read_context_parser = subparsers.add_parser(
        "read-context", help="validate and print the complete effective monitor context"
    )
    _common_instance_arguments(read_context_parser)

    read_static_parser = subparsers.add_parser(
        "read-static", help="validate and print only the immutable monitor document"
    )
    _common_instance_arguments(read_static_parser)

    read_cycle_parser = subparsers.add_parser(
        "read-cycle", help="print dynamic heartbeat state plus a compact static reference"
    )
    _common_instance_arguments(read_cycle_parser)

    refresh_context_parser = subparsers.add_parser(
        "refresh-context-policy", help="replace only the validated static policy snapshot and hash"
    )
    _common_instance_arguments(refresh_context_parser)

    write_parser = subparsers.add_parser("write-evaluation", help="atomically update the monitor evaluation from stdin")
    _common_instance_arguments(write_parser)

    write_cycle_parser = subparsers.add_parser(
        "write-cycle", help="atomically update runtime state and the monitor evaluation from stdin"
    )
    _common_instance_arguments(write_cycle_parser)

    observation_parser = subparsers.add_parser("put-observation", help="atomically upsert one observation from stdin")
    _common_instance_arguments(observation_parser)

    remove_parser = subparsers.add_parser("remove-observation", help="remove one current observation by id")
    _common_instance_arguments(remove_parser)
    remove_parser.add_argument("--id", required=True)

    subparsers.add_parser("schema", help="print the stable v2 contract")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "open":
            result = open_dashboard(args.target, args.package, no_browser=args.no_browser, db_path=args.db)
        elif args.command == "schema":
            result = schema_contract()
        else:
            root = _root(args.root)
            automation_id = _automation_id(args.automation_id)
            if args.command == "init":
                result = init_instance(
                    root,
                    automation_id,
                    normalise_thread_id(args.monitor_thread),
                    normalise_thread_id(args.target_thread),
                    _package(root, args.package),
                )
            elif args.command == "read":
                result = read_instance(root, automation_id)
            elif args.command == "init-context":
                result = init_context(root, automation_id, _stdin_json())
            elif args.command == "read-context":
                result = read_context(root, automation_id)
            elif args.command == "read-static":
                result = read_static(root, automation_id)
            elif args.command == "read-cycle":
                result = read_cycle(root, automation_id)
            elif args.command == "refresh-context-policy":
                result = refresh_context_policy(root, automation_id)
            elif args.command == "write-evaluation":
                result = write_evaluation(root, automation_id, _stdin_json())
            elif args.command == "write-cycle":
                result = write_cycle(root, automation_id, _stdin_json())
            elif args.command == "remove-observation":
                result = remove_observation(root, automation_id, args.id)
            else:
                result = put_observation(root, automation_id, _stdin_json())
    except (MonitorProgressError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
