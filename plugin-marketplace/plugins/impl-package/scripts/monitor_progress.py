from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen


PROTOCOL_VERSION = 2
CONTEXT_VERSION = 2
RUNTIME_VERSION = 7
POLICY_VERSION = "STATIC_MONITOR_POLICY_V18"
DEFAULT_PORT = 43187
THREAD_ID_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
AUTOMATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
CREATED_THREAD_RE = re.compile(r'::created-thread\{threadId="([0-9a-f-]{36})"\}', re.I)
LEVELS = {"normal", "attention", "abnormal"}
SCOPES = {"session", "task"}
OBSERVATION_STATES = {"candidate", "confirmed"}
OBSERVATION_KINDS = {"one-time", "pattern"}
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
    "kind",
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
LEGACY_OBSERVATION_FIELDS = OBSERVATION_FIELDS - {"kind"}
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
SOURCE_SCAN_FIELDS = {
    "lastSeenTurnId",
    "lastSeenUserMessageId",
    "backfillComplete",
    "threadUpdatedAt",
    "rolloutOffset",
    "rolloutPathHash",
}
LEGACY_SOURCE_SCAN_FIELDS = SOURCE_SCAN_FIELDS - {"rolloutOffset", "rolloutPathHash"}
RUNTIME_FIELDS = {
    "sourceScanState",
    "observationFingerprint",
    "reportedObservationDigests",
    "reportedObservationSnapshots",
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
    "lastSimulationCorrection",
    "rendererState",
    "monitorHealthState",
    "packageState",
}
V6_RUNTIME_FIELDS = RUNTIME_FIELDS - {"reportedObservationSnapshots", "packageState"}
V5_RUNTIME_FIELDS = V6_RUNTIME_FIELDS - {"monitorHealthState"}
V4_RUNTIME_FIELDS = V5_RUNTIME_FIELDS - {"rendererState"}
V3_RUNTIME_FIELDS = V4_RUNTIME_FIELDS - {"lastSimulationCorrection"}
V2_RUNTIME_FIELDS = V3_RUNTIME_FIELDS - {"reportedObservationDigests"}
SIMULATION_CORRECTION_FIELDS = {"reason", "message"}
RENDERER_STATE_FIELDS = {"status", "pid", "port", "instanceId", "startedAt", "health"}
RENDERER_STATUSES = {"alive", "dead", "missing", "mismatch"}
MONITOR_HEALTH_FIELDS = {"status", "targetThreadId", "successorThreadId", "rendererStatus"}
MONITOR_HEALTH_STATUSES = {"healthy", "target-unavailable", "retarget-required", "renderer-abnormal"}
RENDERER_STATE_VERSION = 1
RENDERER_FILE_FIELDS = {"version", "pid", "port", "instanceId", "startedAt"}
WRITE_CYCLE_FIELDS = WRITE_EVALUATION_FIELDS | {"runtimeState"}
TARGET_STATUSES = {"active", "idle", "blocked", "terminal", "unknown"}
BASELINE_STATUSES = {"current", "stale"}
DEFAULT_CODEX_DB = Path.home() / ".codex" / "state_5.sqlite"
MAX_OWNER_INPUT_CHARS = 4000
MAX_OWNER_INPUTS = 100
MAX_TARGET_UPDATES = 100

POLICY_SNAPSHOT = {
    "evaluation": [
        "正式 Ticket 与 Gate 状态只以 read-cycle.packageStatus 为准；targetUpdates 只解释正在执行什么，不得覆盖正式状态。",
        "面向 Owner 的 Ticket 状态使用 read-cycle.ticketPresentation：DEVELOPING=开发中，INVESTIGATING=调研中；同时保留 packageStatus 的正式 PENDING/SATISFIED 口径。",
        "targetBaseline 是冻结的任务合同；confirmed observations 是当前 Owner 指令。两者冲突时报告，不静默覆盖。",
        "按最新 task 状态评价进展、baby step、worker lifecycle、review、evidence、manual acceptance、方向与 Owner 分叉。",
        "缺失信息不推断为完成；worker return、focused tests 或局部提交不自动等于 Ticket、Gate 或 package closure。",
        "evaluation.progress 写 target 当前事实、执行进展及必须处理的 blocker、finding、失败测试和验收缺口。",
        "evaluation.improvements 只写不采纳也不影响当前 Ticket/Gate 收口的可选建议，没有则为空数组；必须处理的问题不得写入 improvements。",
        "evaluation.next 只写处理当前事实与问题的下一动作，不重复问题清单；evaluation.owner 只写确需 Owner 裁决的事项，否则为 null。通知沿用这四个字段，不创造当前问题等未定义栏目。",
        "monitor、renderer、sidecar、automation 或 canonical target 的维护动作只进入独立监控健康告警。",
    ],
    "observations": [
        "只有直接改变目标任务授权、执行方式、验收要求或 Owner 决策边界的纠偏才是本任务 observation。",
        "一个 observation topic 只承载一个可被未来消息独立修改的决策轴；同一消息改变多个轴时分别新增或更新，不把正式 Ticket 状态写入 observation。",
        "先服从 Owner 明示范围：绑定具体 Ticket、session、本次动作或一次性决策时 kind=one-time，不得靠改写正文将其泛化。仅在没有明示实例边界时做实例替换测试：移除或替换实例后仍应约束后续同类场景才是 kind=pattern；混合消息拆开记录。",
        "pattern 写成稳定的适用条件、行为和边界，不保留仅用于举例的实例；高置信时 confirmed，不确定时 candidate。one-time 保留具体对象、动作和完成条件，不主动泛化。",
        "按 source、turn 和时间顺序处理新 Owner 输入；结合同批前序消息、当前完整 observations 与 task 状态，先消解 antecedent、主体、动作和范围，再决定 observation topic 或原地更新。",
        "不得把上下文中的局部对象扩大为整个类别；指代无法确认时不覆盖 confirmed observation，也不据此授权 target 消息。",
        "针对监控模板、CLI、dashboard、prompt 或 observation 机制本身的反馈属于工具调试，不写入目标任务 sidecar。",
        "Owner 明确的纠偏直接记为 confirmed；监控推断先记 candidate，pending candidate 同时最多一条。",
        "同一语义 topic 原地更新并保留短 ID；询问、讨论、附件或引用本身不形成 observation。",
        "confirmed observation 与 baseline 冲突时报告 baselineConflict，不覆盖 baseline；合同变化只标 baselineStatus=stale。",
        "ownerInputs 只证明消息已读取；observationDiff 才证明消息被收纳为 observation 的新增、更新或删除。",
    ],
    "visibility": "read_thread 返回 items: [] 表示内容不可见；read-cycle 通过 Codex 数据库登记的 canonical rollout 增量补偿新 Owner 消息和 target 的用户可见进展。",
    "intervention": [
        "默认不向 target 发送消息。只有 confirmed observation 明确授权某类消息且当前事实符合其条件时才可发送。",
        "任何 steer 前必须结合按时间排序的 ownerInputs、targetUpdates、完整 observations 与 packageStatus 识别对话上下文；idle、turn completed、blocked 或 notLoaded 状态本身不证明 blocker，讨论、澄清、问答或等待 Owner 回复时不得发送。",
        "candidate observation 不授权动作。发送时记录采用的 observation ID，并用 runtime 的 target turn ID 去重。",
        "confirmed observation 要求 dry-run 时禁止向 target 发送；仅在触发条件成立且拟纠偏不同于 lastSimulationCorrection 时报告原因和拟发送全文，并标记未发送。",
    ],
    "levels": {
        "normal": "明确 terminal/closed 且无 finding、review、evidence 或 manual acceptance 缺口。",
        "attention": "仍有 active step、pending Gate、调度或证据缺口、confirmed 纠偏未吸收或 baselineConflict。",
        "abnormal": "同一 Topic 连续两轮显式 INCOMPLETE/BLOCKED、重复违背纠偏、closure 与 evidence 矛盾、baseline stale 或 CLI 失败。",
    },
    "communication": [
        "Owner 通知默认只写当前做到哪里、是否正常、接下来做什么、是否需要 Owner。",
        "observationDiff 非空时下一次 heartbeat 必须逐条报告变化类型、ID、topic、具体变化和完整当前内容；删除至少报告 ID。成功 write-cycle 后才视为已报告。",
        "每次 NOTIFY 都显示模拟纠偏；触发时报告原因、拟发送全文和未发送标记，无触发时显示‘模拟纠偏：无’并将 lastSimulationCorrection 写为 null。空模拟纠偏本身不触发 NOTIFY。",
        "monitorHealthDiff 与其它 diff 并列；target unavailable、retarget required 或 renderer abnormal 时单独报告。renderer 异常从 rendererStatus 读取 PID、43187 和影响并明确未自动重启，同一状态只报告一次。",
        "内部执行术语只有在它本身构成故障时才出现，并同时解释真实对象、动作和影响。",
        "监控器自身配置变化只在导致监控中断或需要 Owner 操作时作为独立监控健康告警通知，不写入 target evaluation。",
    ],
    "boundaries": "只读两个 task；renderer 仅绑定 127.0.0.1:43187，使用当前开机周期的 detached 进程，死亡只报告不重启；仅通过本 CLI 写监控 sidecar。除 confirmed observation 明确授权的窄范围消息外，不干预 target。",
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


def _renderer_path(root: Path) -> Path:
    return root / ".progress-record" / "codex-progress-dashboard" / "renderer.json"


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


def _missing_renderer_state() -> dict[str, Any]:
    return {
        "status": "missing",
        "pid": None,
        "port": DEFAULT_PORT,
        "instanceId": None,
        "startedAt": None,
        "health": False,
    }


def validate_renderer_state(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, RENDERER_STATE_FIELDS, "renderer state")
    status = record["status"]
    if status not in RENDERER_STATUSES:
        raise MonitorProgressError(f"renderer state.status must be one of {sorted(RENDERER_STATUSES)}")
    pid = record["pid"]
    if pid is not None and (not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0):
        raise MonitorProgressError("renderer state.pid must be a positive integer or null")
    if record["port"] != DEFAULT_PORT:
        raise MonitorProgressError(f"renderer state.port must be {DEFAULT_PORT}")
    if not isinstance(record["health"], bool):
        raise MonitorProgressError("renderer state.health must be boolean")
    return {
        "status": status,
        "pid": pid,
        "port": DEFAULT_PORT,
        "instanceId": _optional_token(record["instanceId"], "renderer state.instanceId"),
        "startedAt": _iso(record["startedAt"], "renderer state.startedAt", nullable=True),
        "health": record["health"],
    }


def validate_renderer_file(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, RENDERER_FILE_FIELDS, "renderer file")
    if record["version"] != RENDERER_STATE_VERSION:
        raise MonitorProgressError(f"renderer file version must be {RENDERER_STATE_VERSION}")
    state = validate_renderer_state(
        {
            **{key: record[key] for key in RENDERER_FILE_FIELDS - {"version"}},
            "status": "alive",
            "health": True,
        }
    )
    return {"version": RENDERER_STATE_VERSION, **{key: state[key] for key in RENDERER_FILE_FIELDS - {"version"}}}


def validate_monitor_health(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    record = _expect_fields(value, MONITOR_HEALTH_FIELDS, "monitor health state")
    status = record["status"]
    if status not in MONITOR_HEALTH_STATUSES:
        raise MonitorProgressError(
            f"monitor health state.status must be one of {sorted(MONITOR_HEALTH_STATUSES)}"
        )
    renderer_status = record["rendererStatus"]
    if renderer_status not in RENDERER_STATUSES:
        raise MonitorProgressError(
            f"monitor health state.rendererStatus must be one of {sorted(RENDERER_STATUSES)}"
        )
    return {
        "status": status,
        "targetThreadId": normalise_thread_id(record["targetThreadId"]),
        "successorThreadId": (
            normalise_thread_id(record["successorThreadId"])
            if record["successorThreadId"] is not None
            else None
        ),
        "rendererStatus": renderer_status,
    }


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


def _observation_digests(observations: list[dict[str, Any]]) -> dict[str, str]:
    return {
        item["id"]: hashlib.sha256(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for item in observations
    }


def _observation_snapshots(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: copy.deepcopy(item) for item in observations}


def _reported_observation_snapshots(
    observations: list[dict[str, Any]], reported: dict[str, str]
) -> dict[str, dict[str, Any]]:
    current = _observation_digests(observations)
    return {
        item["id"]: copy.deepcopy(item)
        for item in observations
        if reported.get(item["id"]) == current[item["id"]]
    }


def _observation_diff(
    observations: list[dict[str, Any]],
    reported: dict[str, str],
    snapshots: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    current = _observation_digests(observations)
    changes = [
        {
            "change": "created" if item["id"] not in reported else "updated",
            "before": snapshots.get(item["id"]),
            "after": item,
            "observation": item,
        }
        for item in observations
        if reported.get(item["id"]) != current[item["id"]]
    ]
    changes.extend(
        {
            "change": "removed",
            "id": item_id,
            "before": snapshots.get(item_id),
            "after": None,
        }
        for item_id in reported
        if item_id not in current
    )
    return changes


def _package_status(package: Path) -> dict[str, Any]:
    state_path = package / ".impl-package" / "state.json"
    status = "current"
    attempt = None
    gate: Any = None
    tickets: dict[str, dict[str, Any]] = {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        if not isinstance(state, dict):
            raise ValueError("package state must be an object")
        attempt_value = state.get("attempt")
        if isinstance(attempt_value, dict) and isinstance(attempt_value.get("id"), str):
            attempt = attempt_value["id"]
        history = state.get("attemptHistory")
        if isinstance(history, list) and history and isinstance(history[-1], dict):
            gate = json.loads(json.dumps(history[-1].get("gate"), ensure_ascii=False))
        ticket_values = state.get("tickets")
        if not isinstance(ticket_values, dict):
            raise ValueError("package tickets must be an object")
        for ticket_id, value in ticket_values.items():
            if not isinstance(ticket_id, str) or not isinstance(value, dict) or not isinstance(value.get("state"), str):
                raise ValueError("invalid package ticket state")
            acceptance = value.get("acceptance")
            revision = acceptance.get("revision") if isinstance(acceptance, dict) else None
            tickets[ticket_id] = {
                "state": value["state"],
                "acceptanceRevision": revision if isinstance(revision, str) else None,
            }
    except FileNotFoundError:
        status = "missing"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        status = "invalid"
        attempt = None
        gate = None
        tickets = {}
    payload = {"status": status, "attempt": attempt, "gate": gate, "tickets": tickets}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**payload, "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def _ticket_presentation(package: Path) -> dict[str, Any]:
    state_path = package / ".impl-package" / "state.json"
    if not state_path.is_file():
        return {"status": "missing", "readyTicketIds": [], "runningTicketIds": [], "tickets": {}}
    try:
        scripts = str(Path(__file__).resolve().parent)
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from codex_progress_dashboard.server import package_snapshot

        snapshot = package_snapshot(package, [])
        tickets = {
            ticket["id"]: {
                "formalState": ticket["state"],
                "runtimeState": ticket["runtimeState"],
                "label": (
                    "已验收"
                    if ticket["state"] in {"SATISFIED", "RETIRED"}
                    else "开发中"
                    if ticket["runtimeState"] == "DEVELOPING"
                    else "调研中"
                    if ticket["runtimeState"] == "INVESTIGATING"
                    else "可启动"
                    if ticket["runtimeState"] == "READY"
                    else "未开始"
                ),
            }
            for ticket in snapshot["tickets"]
        }
        return {
            "status": "current",
            "readyTicketIds": snapshot["readyTicketIds"],
            "runningTicketIds": snapshot["runningTicketIds"],
            "tickets": tickets,
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, KeyError):
        return {"status": "invalid", "readyTicketIds": [], "runningTicketIds": [], "tickets": {}}


def _package_diff(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any] | None:
    if previous["fingerprint"] == current["fingerprint"]:
        return None
    ticket_changes = []
    for ticket_id in sorted(set(previous["tickets"]) | set(current["tickets"])):
        before = previous["tickets"].get(ticket_id)
        after = current["tickets"].get(ticket_id)
        if before != after:
            ticket_changes.append({"id": ticket_id, "before": before, "after": after})
    return {
        "previousStatus": previous["status"],
        "currentStatus": current["status"],
        "previousAttempt": previous["attempt"],
        "currentAttempt": current["attempt"],
        "previousGate": previous["gate"],
        "currentGate": current["gate"],
        "ticketChanges": ticket_changes,
    }


def validate_package_status(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, {"status", "attempt", "gate", "tickets", "fingerprint"}, "package state")
    if record["status"] not in {"current", "missing", "invalid"}:
        raise MonitorProgressError("package state.status must be current, missing, or invalid")
    attempt = _text(record["attempt"], "package state.attempt", nullable=True)
    try:
        gate = json.loads(json.dumps(record["gate"], ensure_ascii=False))
    except (TypeError, ValueError) as error:
        raise MonitorProgressError("package state.gate must be JSON serializable") from error
    if not isinstance(record["tickets"], dict):
        raise MonitorProgressError("package state.tickets must be an object")
    tickets = {}
    for ticket_id, value in record["tickets"].items():
        if not isinstance(ticket_id, str):
            raise MonitorProgressError("package state ticket ids must be strings")
        ticket = _expect_fields(value, {"state", "acceptanceRevision"}, f"package state ticket {ticket_id}")
        tickets[ticket_id] = {
            "state": _text(ticket["state"], f"package state ticket {ticket_id}.state"),
            "acceptanceRevision": _text(
                ticket["acceptanceRevision"],
                f"package state ticket {ticket_id}.acceptanceRevision",
                nullable=True,
            ),
        }
    fingerprint = _text(record["fingerprint"], "package state.fingerprint", limit=64)
    payload = {"status": record["status"], "attempt": attempt, "gate": gate, "tickets": tickets}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if fingerprint != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
        raise MonitorProgressError("package state fingerprint mismatch")
    return {**payload, "fingerprint": fingerprint}


def default_runtime_state(
    observations: list[dict[str, Any]] | None = None, package: Path | None = None
) -> dict[str, Any]:
    empty_scan = {
        "lastSeenTurnId": None,
        "lastSeenUserMessageId": None,
        "backfillComplete": False,
        "threadUpdatedAt": None,
        "rolloutOffset": 0,
        "rolloutPathHash": None,
    }
    return {
        "sourceScanState": {"monitor": dict(empty_scan), "target": dict(empty_scan)},
        **_observation_runtime(observations or []),
        "reportedObservationDigests": _observation_digests(observations or []),
        "reportedObservationSnapshots": _observation_snapshots(observations or []),
        "lastMainMessageId": None,
        "lastEvaluationFingerprint": None,
        "incompleteStreak": 0,
        "baselineStatus": "current",
        "activeConcernFingerprints": [],
        "lastTargetStatus": "unknown",
        "lastTargetTurnId": None,
        "lastFallbackTurnId": None,
        "lastFallbackAt": None,
        "lastSimulationCorrection": None,
        "rendererState": _missing_renderer_state(),
        "monitorHealthState": None,
        "packageState": _package_status(package or Path("__monitor_package_unset__")),
    }


def validate_runtime_state(value: Any) -> dict[str, Any]:
    record = _expect_fields(value, RUNTIME_FIELDS, "runtime state")
    scans = _expect_fields(record["sourceScanState"], {"monitor", "target"}, "runtime source scan state")
    validated_scans: dict[str, dict[str, Any]] = {}
    for source in ("monitor", "target"):
        scan = _expect_fields(scans[source], SOURCE_SCAN_FIELDS, f"runtime source scan state.{source}")
        if not isinstance(scan["backfillComplete"], bool):
            raise MonitorProgressError(f"runtime source scan state.{source}.backfillComplete must be boolean")
        rollout_offset = scan["rolloutOffset"]
        if not isinstance(rollout_offset, int) or isinstance(rollout_offset, bool) or rollout_offset < 0:
            raise MonitorProgressError(f"runtime source scan state.{source}.rolloutOffset must be non-negative")
        rollout_path_hash = scan["rolloutPathHash"]
        if rollout_path_hash is not None and (
            not isinstance(rollout_path_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", rollout_path_hash)
        ):
            raise MonitorProgressError(f"runtime source scan state.{source}.rolloutPathHash must be SHA-256 or null")
        validated_scans[source] = {
            "lastSeenTurnId": _optional_token(scan["lastSeenTurnId"], f"runtime.{source}.lastSeenTurnId"),
            "lastSeenUserMessageId": _optional_token(
                scan["lastSeenUserMessageId"], f"runtime.{source}.lastSeenUserMessageId"
            ),
            "backfillComplete": scan["backfillComplete"],
            "threadUpdatedAt": _iso(
                scan["threadUpdatedAt"], f"runtime.{source}.threadUpdatedAt", nullable=True
            ),
            "rolloutOffset": rollout_offset,
            "rolloutPathHash": rollout_path_hash,
        }
    pending_ids = record["pendingCandidateIds"]
    if not isinstance(pending_ids, list) or any(
        not isinstance(item, str) or not OBSERVATION_ID_RE.fullmatch(item) for item in pending_ids
    ):
        raise MonitorProgressError("runtime.pendingCandidateIds must contain observation ids")
    reported = record["reportedObservationDigests"]
    if not isinstance(reported, dict) or any(
        not isinstance(item_id, str)
        or not OBSERVATION_ID_RE.fullmatch(item_id)
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        for item_id, digest in reported.items()
    ):
        raise MonitorProgressError("runtime.reportedObservationDigests must map observation ids to SHA-256")
    snapshots = record["reportedObservationSnapshots"]
    if not isinstance(snapshots, dict):
        raise MonitorProgressError("runtime.reportedObservationSnapshots must be an object")
    validated_snapshots = {}
    for item_id, snapshot in snapshots.items():
        if not isinstance(item_id, str) or not OBSERVATION_ID_RE.fullmatch(item_id):
            raise MonitorProgressError("runtime.reportedObservationSnapshots contains an invalid id")
        validated = validate_observation(snapshot, allow_legacy=True)
        if validated["id"] != item_id:
            raise MonitorProgressError("runtime.reportedObservationSnapshots id mismatch")
        validated_snapshots[item_id] = validated
    incomplete_streak = record["incompleteStreak"]
    if not isinstance(incomplete_streak, int) or isinstance(incomplete_streak, bool) or incomplete_streak < 0:
        raise MonitorProgressError("runtime.incompleteStreak must be a non-negative integer")
    baseline_status = record["baselineStatus"]
    if baseline_status not in BASELINE_STATUSES:
        raise MonitorProgressError(f"runtime.baselineStatus must be one of {sorted(BASELINE_STATUSES)}")
    target_status = record["lastTargetStatus"]
    if target_status not in TARGET_STATUSES:
        raise MonitorProgressError(f"runtime.lastTargetStatus must be one of {sorted(TARGET_STATUSES)}")
    simulation = record["lastSimulationCorrection"]
    if simulation is not None:
        simulation = _expect_fields(
            simulation, SIMULATION_CORRECTION_FIELDS, "runtime.lastSimulationCorrection"
        )
        simulation = {
            "reason": _text(simulation["reason"], "runtime.lastSimulationCorrection.reason"),
            "message": _text(simulation["message"], "runtime.lastSimulationCorrection.message"),
        }
    renderer_state = validate_renderer_state(record["rendererState"])
    monitor_health_state = validate_monitor_health(record["monitorHealthState"])
    package_state = validate_package_status(record["packageState"])
    return {
        "sourceScanState": validated_scans,
        "observationFingerprint": _text(record["observationFingerprint"], "runtime.observationFingerprint"),
        "reportedObservationDigests": reported,
        "reportedObservationSnapshots": validated_snapshots,
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
        "lastSimulationCorrection": simulation,
        "rendererState": renderer_state,
        "monitorHealthState": monitor_health_state,
        "packageState": package_state,
    }


def validate_v2_runtime_state(
    value: Any, observations: list[dict[str, Any]], package_state: dict[str, Any]
) -> dict[str, Any]:
    record = _expect_fields(value, V2_RUNTIME_FIELDS, "v2 runtime state")
    return validate_runtime_state(
        {
            **record,
            "reportedObservationDigests": _observation_digests(observations),
            "reportedObservationSnapshots": _observation_snapshots(observations),
            "lastSimulationCorrection": None,
            "rendererState": _missing_renderer_state(),
            "monitorHealthState": None,
            "packageState": package_state,
        }
    )


def validate_v3_runtime_state(
    value: Any, observations: list[dict[str, Any]], package_state: dict[str, Any]
) -> dict[str, Any]:
    record = _expect_fields(value, V3_RUNTIME_FIELDS, "v3 runtime state")
    return validate_runtime_state(
        {
            **record,
            "reportedObservationSnapshots": _reported_observation_snapshots(
                observations, record["reportedObservationDigests"]
            ),
            "lastSimulationCorrection": None,
            "rendererState": _missing_renderer_state(),
            "monitorHealthState": None,
            "packageState": package_state,
        }
    )


def validate_v4_runtime_state(
    value: Any, observations: list[dict[str, Any]], package_state: dict[str, Any]
) -> dict[str, Any]:
    record = _expect_fields(value, V4_RUNTIME_FIELDS, "v4 runtime state")
    return validate_runtime_state(
        {
            **record,
            "reportedObservationSnapshots": _reported_observation_snapshots(
                observations, record["reportedObservationDigests"]
            ),
            "rendererState": _missing_renderer_state(),
            "monitorHealthState": None,
            "packageState": package_state,
        }
    )


def validate_v5_runtime_state(
    value: Any, observations: list[dict[str, Any]], package_state: dict[str, Any]
) -> dict[str, Any]:
    record = _expect_fields(value, V5_RUNTIME_FIELDS, "v5 runtime state")
    return validate_runtime_state(
        {
            **record,
            "reportedObservationSnapshots": _reported_observation_snapshots(
                observations, record["reportedObservationDigests"]
            ),
            "monitorHealthState": None,
            "packageState": package_state,
        }
    )


def validate_v6_runtime_state(
    value: Any, observations: list[dict[str, Any]], package_state: dict[str, Any]
) -> dict[str, Any]:
    record = _expect_fields(value, V6_RUNTIME_FIELDS, "v6 runtime state")
    return validate_runtime_state(
        {
            **record,
            "reportedObservationSnapshots": _reported_observation_snapshots(
                observations, record["reportedObservationDigests"]
            ),
            "packageState": package_state,
        }
    )


def validate_v1_runtime_state(
    value: Any, observations: list[dict[str, Any]], package_state: dict[str, Any]
) -> dict[str, Any]:
    record = _expect_fields(value, V2_RUNTIME_FIELDS, "v1 runtime state")
    scans = _expect_fields(record["sourceScanState"], {"monitor", "target"}, "legacy source scan state")
    migrated_scans: dict[str, dict[str, Any]] = {}
    for source in ("monitor", "target"):
        scan = _expect_fields(scans[source], LEGACY_SOURCE_SCAN_FIELDS, f"legacy source scan state.{source}")
        migrated_scans[source] = {**scan, "rolloutOffset": 0, "rolloutPathHash": None}
    return validate_v2_runtime_state(
        {**record, "sourceScanState": migrated_scans}, observations, package_state
    )


def _runtime_state_for_migration(
    value: Any,
    automation_id: str,
    observations: list[dict[str, Any]],
    package: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MonitorProgressError("monitor runtime store must be a JSON object")
    if value.get("version") == RUNTIME_VERSION:
        store = validate_runtime_store(value)
    elif value.get("version") in {1, 2, 3, 4, 5, 6}:
        record = _expect_fields(value, RUNTIME_STORE_FIELDS, "legacy monitor runtime store")
        package_state = _package_status(package)
        if value.get("version") == 1:
            runtime_state = validate_v1_runtime_state(record["runtimeState"], observations, package_state)
        elif value.get("version") == 2:
            runtime_state = validate_v2_runtime_state(record["runtimeState"], observations, package_state)
        elif value.get("version") == 3:
            runtime_state = validate_v3_runtime_state(record["runtimeState"], observations, package_state)
        elif value.get("version") == 4:
            runtime_state = validate_v4_runtime_state(record["runtimeState"], observations, package_state)
        elif value.get("version") == 5:
            runtime_state = validate_v5_runtime_state(record["runtimeState"], observations, package_state)
        else:
            runtime_state = validate_v6_runtime_state(record["runtimeState"], observations, package_state)
        store = {
            "version": RUNTIME_VERSION,
            "automationId": _automation_id(record["automationId"]),
            "runtimeState": runtime_state,
        }
    else:
        raise MonitorProgressError("unsupported monitor runtime version")
    if store["automationId"] != automation_id:
        raise MonitorProgressError("monitor runtime automation id mismatch")
    return store["runtimeState"]


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


def validate_observation(
    value: Any, *, allow_new: bool = False, allow_legacy: bool = False
) -> dict[str, Any]:
    if allow_legacy and isinstance(value, dict) and set(value) == LEGACY_OBSERVATION_FIELDS:
        value = {**value, "kind": "one-time"}
    elif allow_legacy and isinstance(value, dict) and value.get("kind") == "specific":
        value = {**value, "kind": "one-time"}
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
    kind = record["kind"]
    response = record["response"]
    if scope not in SCOPES:
        raise MonitorProgressError(f"observation.scope must be one of {sorted(SCOPES)}")
    if state not in OBSERVATION_STATES:
        raise MonitorProgressError(f"observation.state must be one of {sorted(OBSERVATION_STATES)}")
    if kind not in OBSERVATION_KINDS:
        raise MonitorProgressError(f"observation.kind must be one of {sorted(OBSERVATION_KINDS)}")
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
        "kind": kind,
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
    validated = [validate_observation(item, allow_legacy=True) for item in observations]
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
            "runtimeState": default_runtime_state(
                instance["observations"], Path(instance["monitor"]["packagePath"])
            ),
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


def _normalise_codex_path(value: Any) -> Path:
    text = _text(value, "Codex rollout path")
    if text.startswith("\\\\?\\"):
        text = text[4:]
    return Path(text).resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _canonical_task(thread_id: str, db_path: Path = DEFAULT_CODEX_DB) -> tuple[Path, str]:
    database = db_path.resolve()
    uri = f"file:{database.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            row = connection.execute(
                "SELECT rollout_path, COALESCE(NULLIF(name, ''), title) FROM threads WHERE id = ?",
                (normalise_thread_id(thread_id),),
            ).fetchone()
    except sqlite3.Error as exc:
        raise MonitorProgressError(f"cannot read Codex task database: {database}") from exc
    if row is None:
        raise MonitorProgressError(f"Codex task is unavailable: {thread_id}")
    rollout = _normalise_codex_path(row[0])
    sessions_root = (database.parent / "sessions").resolve()
    if not rollout.is_file() or not _is_within(rollout, sessions_root):
        raise MonitorProgressError("canonical rollout is unavailable or outside the Codex sessions directory")
    return rollout, _text(row[1], "Codex task title", limit=500)


def _canonical_rollout(thread_id: str, db_path: Path = DEFAULT_CODEX_DB) -> Path:
    return _canonical_task(thread_id, db_path)[0]


def _rollout_hash(path: Path) -> str:
    return hashlib.sha256(str(path).casefold().encode("utf-8")).hexdigest()


def _complete_line_end(path: Path) -> int:
    size = path.stat().st_size
    if size == 0:
        return 0
    with path.open("rb") as stream:
        stream.seek(size - 1)
        if stream.read(1) == b"\n":
            return size
        position = size - 1
        while position > 0:
            position -= 1
            stream.seek(position)
            if stream.read(1) == b"\n":
                return position + 1
    return 0


def _message_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part["text"] for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()


def _owner_inputs(thread_id: str, scan: dict[str, Any], db_path: Path) -> dict[str, Any]:
    if scan["rolloutPathHash"] is None:
        return {
            "status": "unseeded",
            "inputs": [],
            "updates": [],
            "nextOffset": 0,
            "pathHash": None,
            "reset": False,
            "successorThreadId": None,
        }
    try:
        rollout = _canonical_rollout(thread_id, db_path)
    except MonitorProgressError:
        return {
            "status": "unavailable",
            "inputs": [],
            "updates": [],
            "nextOffset": scan["rolloutOffset"],
            "pathHash": scan["rolloutPathHash"],
            "reset": False,
            "successorThreadId": None,
        }
    path_hash = _rollout_hash(rollout)
    offset = scan["rolloutOffset"]
    reset = scan["rolloutPathHash"] != path_hash or rollout.stat().st_size < offset
    if reset:
        offset = 0
    inputs: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    successor_thread_id = None
    next_offset = offset
    with rollout.open("rb") as stream:
        stream.seek(offset)
        while len(inputs) < MAX_OWNER_INPUTS and len(updates) < MAX_TARGET_UPDATES:
            raw = stream.readline()
            if not raw or not raw.endswith(b"\n"):
                break
            next_offset = stream.tell()
            try:
                record = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            payload = record.get("payload") if isinstance(record, dict) else None
            if (
                not isinstance(payload, dict)
                or record.get("type") != "response_item"
                or payload.get("type") != "message"
            ):
                continue
            text = _message_text(payload)
            if payload.get("role") == "assistant":
                matches = CREATED_THREAD_RE.findall(text)
                if matches:
                    successor_thread_id = normalise_thread_id(matches[-1])
                if text:
                    metadata = payload.get("internal_chat_message_metadata_passthrough")
                    turn_id = metadata.get("turn_id") if isinstance(metadata, dict) else None
                    updates.append(
                        {
                            "messageId": _text(payload.get("id"), "rollout assistant message id", limit=200),
                            "turnId": _optional_token(turn_id, "rollout assistant turn id"),
                            "createdAt": _iso(record.get("timestamp"), "rollout assistant timestamp"),
                            "phase": payload.get("phase") if payload.get("phase") in {"commentary", "final_answer"} else None,
                            "text": text[:MAX_OWNER_INPUT_CHARS],
                        }
                    )
                continue
            if payload.get("role") != "user":
                continue
            if not text or text.lstrip().startswith("<heartbeat>"):
                continue
            metadata = payload.get("internal_chat_message_metadata_passthrough")
            turn_id = metadata.get("turn_id") if isinstance(metadata, dict) else None
            inputs.append(
                {
                    "messageId": _text(payload.get("id"), "rollout user message id", limit=200),
                    "turnId": _optional_token(turn_id, "rollout user turn id"),
                    "createdAt": _iso(record.get("timestamp"), "rollout user timestamp"),
                    "text": text[:MAX_OWNER_INPUT_CHARS],
                }
            )
    return {
        "status": "current",
        "inputs": inputs,
        "updates": updates,
        "nextOffset": next_offset,
        "pathHash": path_hash,
        "reset": reset,
        "successorThreadId": successor_thread_id,
    }


def _monitor_health(
    target_thread_id: str,
    target_scan: dict[str, Any],
    renderer_status: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    successor_thread_id = target_scan["successorThreadId"]
    if (
        successor_thread_id is None
        and previous is not None
        and previous["status"] == "retarget-required"
        and previous["targetThreadId"] == target_thread_id
    ):
        successor_thread_id = previous["successorThreadId"]
    if successor_thread_id and successor_thread_id != target_thread_id:
        status = "retarget-required"
    elif target_scan["status"] == "unavailable":
        status = "target-unavailable"
    elif renderer_status["status"] != "alive":
        status = "renderer-abnormal"
    else:
        status = "healthy"
    return validate_monitor_health(
        {
            "status": status,
            "targetThreadId": target_thread_id,
            "successorThreadId": successor_thread_id,
            "rendererStatus": renderer_status["status"],
        }
    )


def seed_rollout_cursors(
    root: Path, automation_id: str, db_path: Path = DEFAULT_CODEX_DB
) -> dict[str, Any]:
    instance = read_instance(root, automation_id)
    monitor = instance["monitor"]
    runtime_state = _runtime_state_for_migration(
        _read_json(_runtime_path(root, automation_id)),
        automation_id,
        instance["observations"],
        Path(monitor["packagePath"]),
    )
    for source, thread_id in (("monitor", monitor["monitorThreadId"]), ("target", monitor["targetThreadId"])):
        rollout = _canonical_rollout(thread_id, db_path)
        runtime_state["sourceScanState"][source].update(
            {"rolloutOffset": _complete_line_end(rollout), "rolloutPathHash": _rollout_hash(rollout)}
        )
    runtime_state["rendererState"] = _renderer_status(root)
    runtime_state["packageState"] = _package_status(Path(monitor["packagePath"]))
    runtime_state["monitorHealthState"] = _monitor_health(
        monitor["targetThreadId"],
        {
            "status": "current",
            "successorThreadId": None,
        },
        runtime_state["rendererState"],
        None,
    )
    store = validate_runtime_store(
        {"version": RUNTIME_VERSION, "automationId": automation_id, "runtimeState": runtime_state}
    )
    _atomic_write(_runtime_path(root, automation_id), store)
    return read_cycle(root, automation_id, db_path)


def read_cycle(
    root: Path, automation_id: str, db_path: Path = DEFAULT_CODEX_DB
) -> dict[str, Any]:
    context = validate_context(
        _read_json(_context_path(root, automation_id)), require_current_policy=False
    )
    runtime_store = validate_runtime_store(_read_json(_runtime_path(root, automation_id)))
    instance = read_instance(root, automation_id)
    if context["automationId"] != automation_id or runtime_store["automationId"] != automation_id:
        raise MonitorProgressError("monitor context automation id mismatch")
    current = context["policyVersion"] == POLICY_VERSION and context["policySnapshot"] == POLICY_SNAPSHOT
    monitor = instance["monitor"]
    source_inputs = {
        "monitor": _owner_inputs(
            monitor["monitorThreadId"],
            runtime_store["runtimeState"]["sourceScanState"]["monitor"],
            db_path,
        ),
        "target": _owner_inputs(
            monitor["targetThreadId"],
            runtime_store["runtimeState"]["sourceScanState"]["target"],
            db_path,
        ),
    }
    renderer_status = _renderer_status(root)
    previous_renderer = runtime_store["runtimeState"]["rendererState"]
    package_status = _package_status(Path(monitor["packagePath"]))
    ticket_presentation = _ticket_presentation(Path(monitor["packagePath"]))
    previous_package_status = runtime_store["runtimeState"]["packageState"]
    monitor_health = _monitor_health(
        monitor["targetThreadId"],
        source_inputs["target"],
        renderer_status,
        runtime_store["runtimeState"]["monitorHealthState"],
    )
    previous_monitor_health = runtime_store["runtimeState"]["monitorHealthState"]
    return {
        "staticRef": {
            "contextVersion": context["version"],
            "policyVersion": context["policyVersion"],
            "snapshotHash": context["snapshotHash"],
            "status": "current" if current else "reload-required",
        },
        "runtimeState": runtime_store["runtimeState"],
        "observationDiff": _observation_diff(
            instance["observations"],
            runtime_store["runtimeState"]["reportedObservationDigests"],
            runtime_store["runtimeState"]["reportedObservationSnapshots"],
        ),
        "packageStatus": package_status,
        "ticketPresentation": ticket_presentation,
        "packageDiff": _package_diff(previous_package_status, package_status),
        "rendererStatus": renderer_status,
        "rendererDiff": (
            None
            if renderer_status == previous_renderer
            else {"previous": previous_renderer, "current": renderer_status}
        ),
        "monitorHealthStatus": monitor_health,
        "monitorHealthDiff": (
            None
            if monitor_health == previous_monitor_health
            else {"previous": previous_monitor_health, "current": monitor_health}
        ),
        "ownerInputs": {source: value["inputs"] for source, value in source_inputs.items()},
        "targetUpdates": source_inputs["target"]["updates"],
        "nextRolloutCursors": {
            source: {
                "status": value["status"],
                "rolloutOffset": value["nextOffset"],
                "rolloutPathHash": value["pathHash"],
                "reset": value["reset"],
            }
            for source, value in source_inputs.items()
        },
        **instance,
    }


def retarget(
    root: Path,
    automation_id: str,
    target_thread_id: str,
    db_path: Path = DEFAULT_CODEX_DB,
) -> dict[str, Any]:
    target_thread_id = normalise_thread_id(target_thread_id)
    current = read_context(root, automation_id)
    monitor = current["monitor"]
    rollout, target_title = _canonical_task(target_thread_id, db_path)
    if monitor["targetThreadId"] == target_thread_id:
        if current["context"]["targetTitle"] != target_title:
            static_context = validate_context(
                {
                    **{key: current["context"][key] for key in CONTEXT_FIELDS},
                    "targetTitle": target_title,
                }
            )
            _atomic_write(_context_path(root, automation_id), static_context)
            current = read_context(root, automation_id)
        return {"retargeted": False, **current}
    original_monitor = monitor
    original_context = validate_context(_read_json(_context_path(root, automation_id)))
    original_runtime_store = validate_runtime_store(_read_json(_runtime_path(root, automation_id)))
    runtime_state = copy.deepcopy(original_runtime_store["runtimeState"])
    runtime_state["sourceScanState"]["target"] = {
        "lastSeenTurnId": None,
        "lastSeenUserMessageId": None,
        "backfillComplete": True,
        "threadUpdatedAt": None,
        "rolloutOffset": _complete_line_end(rollout),
        "rolloutPathHash": _rollout_hash(rollout),
    }
    renderer_status = _renderer_status(root)
    runtime_state["rendererState"] = renderer_status
    runtime_state["monitorHealthState"] = _monitor_health(
        target_thread_id,
        {"status": "current", "successorThreadId": None},
        renderer_status,
        None,
    )
    updated_monitor = validate_monitor({**monitor, "targetThreadId": target_thread_id})
    updated_runtime_store = validate_runtime_store(
        {"version": RUNTIME_VERSION, "automationId": automation_id, "runtimeState": runtime_state}
    )
    updated_context = validate_context({**original_context, "targetTitle": target_title})
    monitor_path = _instance_paths(root, automation_id)[0]
    runtime_path = _runtime_path(root, automation_id)
    context_path = _context_path(root, automation_id)
    try:
        _atomic_write(monitor_path, updated_monitor)
        _atomic_write(runtime_path, updated_runtime_store)
        _atomic_write(context_path, updated_context)
    except Exception:
        try:
            _atomic_write(monitor_path, original_monitor)
            _atomic_write(runtime_path, original_runtime_store)
            _atomic_write(context_path, original_context)
        except Exception as rollback_error:
            raise MonitorProgressError("retarget failed and rollback could not restore monitor state") from rollback_error
        raise
    return {"retargeted": True, **read_context(root, automation_id)}


def rebind_monitor(
    root: Path,
    automation_id: str,
    monitor_thread_id: str,
    db_path: Path = DEFAULT_CODEX_DB,
) -> dict[str, Any]:
    monitor_thread_id = normalise_thread_id(monitor_thread_id)
    current = read_context(root, automation_id)
    monitor = current["monitor"]
    if monitor["monitorThreadId"] == monitor_thread_id:
        return {"rebound": False, **current}
    rollout = _canonical_rollout(monitor_thread_id, db_path)
    original_monitor = monitor
    original_runtime_store = validate_runtime_store(_read_json(_runtime_path(root, automation_id)))
    runtime_state = copy.deepcopy(original_runtime_store["runtimeState"])
    runtime_state["sourceScanState"]["monitor"] = {
        "lastSeenTurnId": None,
        "lastSeenUserMessageId": None,
        "backfillComplete": True,
        "threadUpdatedAt": None,
        "rolloutOffset": _complete_line_end(rollout),
        "rolloutPathHash": _rollout_hash(rollout),
    }
    updated_monitor = validate_monitor({**monitor, "monitorThreadId": monitor_thread_id})
    updated_runtime_store = validate_runtime_store(
        {"version": RUNTIME_VERSION, "automationId": automation_id, "runtimeState": runtime_state}
    )
    monitor_path = _instance_paths(root, automation_id)[0]
    runtime_path = _runtime_path(root, automation_id)
    try:
        _atomic_write(monitor_path, updated_monitor)
        _atomic_write(runtime_path, updated_runtime_store)
    except Exception:
        try:
            _atomic_write(monitor_path, original_monitor)
            _atomic_write(runtime_path, original_runtime_store)
        except Exception as rollback_error:
            raise MonitorProgressError("monitor rebind failed and rollback could not restore state") from rollback_error
        raise
    return {"rebound": True, **read_context(root, automation_id)}


def refresh_context_policy(root: Path, automation_id: str) -> dict[str, Any]:
    path = _context_path(root, automation_id)
    raw_context = _read_json(path)
    instance = read_instance(root, automation_id)
    if isinstance(raw_context, dict) and raw_context.get("version") == 1:
        context, runtime_state = validate_legacy_context(raw_context)
    else:
        context = validate_context(raw_context, require_current_policy=False)
        runtime_state = _runtime_state_for_migration(
            _read_json(_runtime_path(root, automation_id)),
            automation_id,
            instance["observations"],
            Path(instance["monitor"]["packagePath"]),
        )
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
    if record["targetThreadId"] != current["targetThreadId"]:
        raise MonitorProgressError("target task change requires the retarget command")
    return validate_monitor(
        {
            **current,
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
        "reportedObservationDigests": _observation_digests(current["observations"]),
        "reportedObservationSnapshots": _observation_snapshots(current["observations"]),
        "packageState": _package_status(Path(current["monitor"]["packagePath"])),
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
        )
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
            "kinds": sorted(OBSERVATION_KINDS),
            "scopes": sorted(SCOPES),
            "states": sorted(OBSERVATION_STATES),
            "responses": sorted(RESPONSES),
        },
        "writeEvaluationInput": {"required": sorted(WRITE_EVALUATION_FIELDS)},
        "context": {"required": sorted(CONTEXT_FIELDS)},
        "runtimeStore": {"required": sorted(RUNTIME_STORE_FIELDS), "runtimeRequired": sorted(RUNTIME_FIELDS)},
        "ownerInput": {"required": ["messageId", "turnId", "createdAt", "text"]},
        "targetUpdate": {"required": ["messageId", "turnId", "createdAt", "phase", "text"]},
        "packageStatus": {
            "required": ["status", "attempt", "gate", "tickets", "fingerprint"],
            "states": ["current", "invalid", "missing"],
        },
        "ticketPresentation": {
            "required": ["status", "readyTicketIds", "runningTicketIds", "tickets"],
            "runtimeStates": ["DEVELOPING", "INVESTIGATING", "READY", None],
        },
        "packageDiff": {"acknowledgedBy": "write-cycle"},
        "observationDiff": {
            "changes": ["created", "updated", "removed"],
            "fields": ["before", "after"],
            "acknowledgedBy": "write-cycle",
        },
        "rendererStatus": {"required": sorted(RENDERER_STATE_FIELDS), "states": sorted(RENDERER_STATUSES)},
        "rendererDiff": {"acknowledgedBy": "write-cycle runtimeState.rendererState"},
        "monitorHealthStatus": {
            "required": sorted(MONITOR_HEALTH_FIELDS),
            "states": sorted(MONITOR_HEALTH_STATUSES),
        },
        "monitorHealthDiff": {"acknowledgedBy": "write-cycle runtimeState.monitorHealthState"},
        "initContextInput": {"required": sorted(INIT_CONTEXT_FIELDS)},
        "writeCycleInput": {"required": sorted(WRITE_CYCLE_FIELDS)},
        "refreshContextPolicy": {"preserves": ["targetBaseline", "runtimeState", "monitor", "observations"]},
        "retarget": {
            "preserves": ["targetBaseline", "observations", "evaluation", "monitor runtime"],
            "seedsTargetCursorAt": "current complete-line end",
        },
        "rebindMonitor": {
            "preserves": ["target task", "targetBaseline", "observations", "evaluation", "monitor runtime"],
            "seedsMonitorCursorAt": "current complete-line end",
        },
    }


def _find_root(package_path: Path) -> Path:
    for candidate in (package_path, *package_path.parents):
        if (candidate / ".git").exists():
            return candidate.resolve()
    raise MonitorProgressError("package is not inside a Git workspace")


def _health_payload(port: int) -> dict[str, Any] | None:
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, OSError, URLError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _health(port: int, instance_id: str | None = None) -> bool:
    payload = _health_payload(port)
    return bool(
        payload
        and payload.get("monitorProgressProtocol") == PROTOCOL_VERSION
        and (instance_id is None or payload.get("instanceId") == instance_id)
    )


def _process_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            return bool(
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                and exit_code.value == 259
            )
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _renderer_status(root: Path) -> dict[str, Any]:
    path = _renderer_path(root)
    if not path.is_file():
        return _missing_renderer_state()
    try:
        renderer = validate_renderer_file(_read_json(path))
    except MonitorProgressError:
        return {**_missing_renderer_state(), "status": "mismatch"}
    base = {
        "pid": renderer["pid"],
        "port": DEFAULT_PORT,
        "instanceId": renderer["instanceId"],
        "startedAt": renderer["startedAt"],
    }
    if not _process_alive(renderer["pid"]):
        return validate_renderer_state({**base, "status": "dead", "health": False})
    payload = _health_payload(DEFAULT_PORT)
    matches = bool(
        payload
        and payload.get("monitorProgressProtocol") == PROTOCOL_VERSION
        and payload.get("pid") == renderer["pid"]
        and payload.get("instanceId") == renderer["instanceId"]
        and payload.get("startedAt") == renderer["startedAt"]
    )
    return validate_renderer_state(
        {**base, "status": "alive" if matches else "mismatch", "health": matches}
    )


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        return connection.connect_ex(("127.0.0.1", port)) != 0


def _start_server(port: int, db_path: Path | None) -> dict[str, Any]:
    server = Path(__file__).resolve().parent / "codex_progress_dashboard" / "server.py"
    instance_id = uuid.uuid4().hex
    started_at = _now()
    command = [
        sys.executable,
        str(server),
        "--port",
        str(port),
        "--instance-id",
        instance_id,
        "--started-at",
        started_at,
    ]
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
    process = subprocess.Popen(command, **kwargs)
    try:
        _wait_for_server(port, instance_id)
    except Exception:
        process.terminate()
        raise
    return validate_renderer_file(
        {
            "version": RENDERER_STATE_VERSION,
            "pid": process.pid,
            "port": port,
            "instanceId": instance_id,
            "startedAt": started_at,
        }
    )


def _wait_for_server(port: int, instance_id: str) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _health(port, instance_id):
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
    port = DEFAULT_PORT
    payload = _health_payload(port)
    reusable = bool(
        payload
        and payload.get("monitorProgressProtocol") == PROTOCOL_VERSION
        and isinstance(payload.get("pid"), int)
        and _process_alive(payload["pid"])
        and isinstance(payload.get("instanceId"), str)
        and isinstance(payload.get("startedAt"), str)
    )
    if reusable:
        renderer = validate_renderer_file(
            {
                "version": RENDERER_STATE_VERSION,
                "pid": payload["pid"],
                "port": port,
                "instanceId": payload["instanceId"],
                "startedAt": payload["startedAt"],
            }
        )
    else:
        if not _port_available(port):
            raise MonitorProgressError(f"dashboard port {port} is occupied by another process")
        renderer = _start_server(port, db_path)
    _atomic_write(_renderer_path(root), renderer)
    reused = reusable
    packages = _target_packages(port, target_thread_id)
    if not any(item.get("path") == relative_package for item in packages if isinstance(item, dict)):
        raise MonitorProgressError("package does not belong to the target task workspace")
    query = urlencode({"task": target_thread_id, "package": relative_package})
    url = f"http://127.0.0.1:{port}/?{query}"
    if not no_browser and not webbrowser.open(url):
        raise MonitorProgressError("browser did not accept the dashboard URL")
    return {
        "url": url,
        "port": port,
        "pid": renderer["pid"],
        "reused": reused,
        "targetThreadId": target_thread_id,
        "packagePath": str(package_path),
    }


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
    read_cycle_parser.add_argument("--db", type=Path, default=DEFAULT_CODEX_DB)

    seed_rollout_parser = subparsers.add_parser(
        "seed-rollout-cursors", help="set canonical rollout cursors to the current complete-line ends"
    )
    _common_instance_arguments(seed_rollout_parser)
    seed_rollout_parser.add_argument("--db", type=Path, default=DEFAULT_CODEX_DB)

    retarget_parser = subparsers.add_parser(
        "retarget", help="bind the monitor to an explicit successor task without replaying its history"
    )
    _common_instance_arguments(retarget_parser)
    retarget_parser.add_argument("--target-thread", required=True)
    retarget_parser.add_argument("--db", type=Path, default=DEFAULT_CODEX_DB)

    rebind_monitor_parser = subparsers.add_parser(
        "rebind-monitor", help="move heartbeat ownership to an explicit monitor task"
    )
    _common_instance_arguments(rebind_monitor_parser)
    rebind_monitor_parser.add_argument("--monitor-thread", required=True)
    rebind_monitor_parser.add_argument("--db", type=Path, default=DEFAULT_CODEX_DB)

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
                result = read_cycle(root, automation_id, args.db)
            elif args.command == "seed-rollout-cursors":
                result = seed_rollout_cursors(root, automation_id, args.db)
            elif args.command == "retarget":
                result = retarget(root, automation_id, args.target_thread, args.db)
            elif args.command == "rebind-monitor":
                result = rebind_monitor(root, automation_id, args.monitor_thread, args.db)
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
