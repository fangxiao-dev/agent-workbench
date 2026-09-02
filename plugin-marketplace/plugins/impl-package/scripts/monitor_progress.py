from __future__ import annotations

import argparse
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


def write_evaluation(root: Path, automation_id: str, payload: Any) -> dict[str, Any]:
    record = _expect_fields(payload, WRITE_EVALUATION_FIELDS, "evaluation write payload")
    current = read_instance(root, automation_id)["monitor"]
    updated = validate_monitor(
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
    _atomic_write(_instance_paths(root, automation_id)[0], updated)
    return updated


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

    write_parser = subparsers.add_parser("write-evaluation", help="atomically update the monitor evaluation from stdin")
    _common_instance_arguments(write_parser)

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
            elif args.command == "write-evaluation":
                result = write_evaluation(root, automation_id, _stdin_json())
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
