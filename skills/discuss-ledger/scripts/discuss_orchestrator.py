#!/usr/bin/env python3
"""Local round-robin orchestrator for Codex and Claude discuss-ledger turns."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
SRC = SKILL_DIR / "src"
SCHEMA_PATH = SKILL_DIR / "schemas" / "agent-result.schema.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from discuss_ledger_core import ledger


SUPPORTED_AGENTS = {"codex", "claude"}


class AdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def parse_agents(value: str) -> list[str]:
    agents = [part.strip().lower() for part in value.split(",") if part.strip()]
    unsupported = [agent for agent in agents if agent not in SUPPORTED_AGENTS]
    if unsupported:
        raise ValueError(f"unsupported agents: {', '.join(unsupported)}; supported: codex, claude")
    if not agents:
        raise ValueError("at least one agent is required")
    return agents


def parse_json_object(output: str) -> dict[str, Any]:
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        start = output.find("{")
        end = output.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(output[start : end + 1])


def looks_like_agent_result(data: Any) -> bool:
    return isinstance(data, dict) and all(key in data for key in ("convergences", "contests", "new_points"))


def iter_agent_result_candidates(value: Any):
    if looks_like_agent_result(value):
        yield value
    if isinstance(value, str):
        try:
            parsed = parse_json_object(value)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None:
            yield from iter_agent_result_candidates(parsed)
    elif isinstance(value, dict):
        for nested in value.values():
            yield from iter_agent_result_candidates(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_agent_result_candidates(nested)


def parse_codex_jsonl(output: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates.extend(iter_agent_result_candidates(event))
    if candidates:
        return candidates[-1]
    return parse_json_object(output)


def extract_agent_result(data: Any) -> dict[str, Any] | None:
    for candidate in iter_agent_result_candidates(data):
        return candidate
    return None


def normalize_result(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {}
    allowed_top = {"convergences", "contests", "new_points"}
    missing_top = allowed_top - set(data)
    if missing_top:
        raise AdapterError("INVALID_JSON", f"missing top-level keys: {', '.join(sorted(missing_top))}")
    extra_top = set(data) - allowed_top
    if extra_top:
        raise AdapterError("INVALID_JSON", f"unexpected top-level keys: {', '.join(sorted(extra_top))}")
    for key in ("convergences", "contests", "new_points"):
        value = data.get(key, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            raise AdapterError("INVALID_JSON", f"{key} must be an array")
        normalized[key] = value
    for item in normalized["convergences"]:
        validate_object(item, "convergences[]", {"point", "marker", "line"}, {"point", "marker", "line"})
    for item in normalized["contests"]:
        validate_object(item, "contests[]", {"point", "body", "movement"}, {"point", "body", "movement"}, {"point", "body"})
        if not isinstance(item["movement"], bool):
            raise AdapterError("INVALID_JSON", "contests[].movement must be boolean")
    for item in normalized["new_points"]:
        validate_object(item, "new_points[]", {"summary", "body"}, {"summary", "body"})
    return normalized


def validate_object(
    item: Any,
    label: str,
    allowed: set[str],
    required: set[str],
    string_required: set[str] | None = None,
) -> None:
    if not isinstance(item, dict):
        raise AdapterError("INVALID_JSON", f"{label} must be an object")
    missing = required - set(item)
    if missing:
        raise AdapterError("INVALID_JSON", f"{label} missing required keys: {', '.join(sorted(missing))}")
    extra = set(item) - allowed
    if extra:
        raise AdapterError("INVALID_JSON", f"{label} has unexpected keys: {', '.join(sorted(extra))}")
    for key in string_required or required:
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise AdapterError("INVALID_JSON", f"{label}.{key} must be a non-empty string")


def classify_process_error(command: str, returncode: int, stdout: str, stderr: str) -> AdapterError:
    combined = f"{stdout}\n{stderr}".lower()
    if "permission denied" in combined or "not allowed" in combined:
        return AdapterError("PERMISSION", f"{command} could not access the requested project or files")
    if "auth" in combined or "login" in combined or "not authenticated" in combined:
        return AdapterError("AUTH", f"{command} requires CLI login/authentication")
    return AdapterError("AGENT_FAILED", f"{command} exited with code {returncode}: {stderr.strip() or stdout.strip()}")


def read_target_document(root: Path, topic: str) -> str:
    topic_path = Path(topic)
    candidate = topic_path if topic_path.is_absolute() else root / topic
    if not candidate.exists() or not candidate.is_file():
        return "(no target document file found; topic is free text)"
    text = candidate.read_text(encoding="utf-8", errors="replace")
    max_chars = 80000
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[truncated]"
    return text


def build_prompt(agent: str, topic: str, target_document: str, status: ledger.LedgerStatus) -> str:
    open_points = "\n".join(
        f"- {point['id']} [{point['status']}] {point['summary']} (已历{point['rounds']}轮)"
        for point in status.open_points
    )
    if not open_points:
        open_points = "- (none)"
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    return f"""You are {agent} participating in a discuss-ledger review.

Topic: {topic}

Target document:
{target_document}

Return only JSON matching this schema:
{schema}

Interpret the fields as:
- convergences: points you now agree are settled
- contests: existing points you still dispute
- new_points: materially new disagreements

Open points:
{open_points}

Current ledger markdown:
{status.markdown}
"""


def run_process(
    command: list[str],
    *,
    stdin: str | None = None,
    timeout_s: int = 900,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = command[0]
    resolved = shutil.which(executable)
    if resolved is None:
        raise AdapterError("BINARY_NOT_FOUND", f"{executable} was not found on PATH")
    actual_command = command
    if resolved.lower().endswith(".ps1"):
        actual_command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            resolved,
            *command[1:],
        ]
    elif resolved.lower().endswith((".cmd", ".bat")):
        actual_command = ["cmd", "/c", resolved, *command[1:]]
    try:
        process = subprocess.Popen(
            actual_command,
            stdin=subprocess.PIPE if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        try:
            stdout, stderr = process.communicate(input=stdin, timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            terminate_process_tree(process.pid)
            stdout, stderr = process.communicate()
            raise AdapterError("TIMEOUT", f"{executable} timed out after {timeout_s}s") from exc
        return subprocess.CompletedProcess(actual_command, process.returncode, stdout, stderr)
    except PermissionError as exc:
        raise AdapterError("PERMISSION", str(exc)) from exc
    except FileNotFoundError as exc:
        raise AdapterError("BINARY_NOT_FOUND", f"{executable} was not found on PATH") from exc


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def run_codex(prompt: str, root: Path, timeout_s: int) -> dict[str, Any]:
    command = [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--output-schema",
        str(SCHEMA_PATH),
        "--sandbox",
        "read-only",
        "--cd",
        str(root),
        "-",
    ]
    completed = run_process(command, stdin=prompt, timeout_s=timeout_s, cwd=root)
    if completed.returncode != 0:
        raise classify_process_error("codex", completed.returncode, completed.stdout, completed.stderr)
    return parse_codex_jsonl(completed.stdout)


def run_claude(prompt: str, root: Path, timeout_s: int) -> dict[str, Any]:
    command = [
        "claude",
        "-p",
        "--no-session-persistence",
        "--effort",
        "low",
        "--disable-slash-commands",
        "--tools",
        "",
        "--system-prompt",
        "You are a non-interactive discuss-ledger participant. Return only the requested structured result.",
        "--output-format",
        "json",
    ]
    completed = run_process(command, stdin=prompt, timeout_s=timeout_s, cwd=root)
    if completed.returncode != 0:
        raise classify_process_error("claude", completed.returncode, completed.stdout, completed.stderr)
    try:
        parsed = parse_json_object(completed.stdout)
        result = extract_agent_result(parsed)
        if result is not None:
            return result
        raise json.JSONDecodeError("no agent result in Claude output", completed.stdout, 0)
    except json.JSONDecodeError:
        repair_prompt = (
            "Repair this output into JSON matching the discuss-ledger schema. "
            "Return only JSON.\n\n"
            f"Schema:\n{SCHEMA_PATH.read_text(encoding='utf-8')}\n\n"
            f"Invalid output:\n{completed.stdout}"
        )
        retry = run_process(command, stdin=repair_prompt, timeout_s=timeout_s, cwd=root)
        if retry.returncode != 0:
            raise classify_process_error("claude", retry.returncode, retry.stdout, retry.stderr)
        parsed = parse_json_object(retry.stdout)
        result = extract_agent_result(parsed)
        if result is not None:
            return result
        raise AdapterError("INVALID_JSON", "Claude did not return a valid agent result after repair")


def run_fake(agent: str, status: ledger.LedgerStatus) -> dict[str, Any]:
    if agent == "codex" and not status.open_points:
        return {
            "convergences": [],
            "contests": [],
            "new_points": [
                {
                    "summary": "Fake codex opening concern",
                    "body": "Fake codex opening concern: verify orchestration can add a point.",
                }
            ],
        }
    if agent == "claude" and status.open_points:
        point = status.open_points[0]["id"]
        return {
            "convergences": [
                {
                    "point": point,
                    "marker": "一致",
                    "line": f"Fake claude convergence for {point}.",
                }
            ],
            "contests": [],
            "new_points": [],
        }
    return {"convergences": [], "contests": [], "new_points": []}


def call_agent(agent: str, prompt: str, root: Path, status: ledger.LedgerStatus, fake: bool, timeout_s: int) -> dict[str, Any]:
    if fake:
        return run_fake(agent, status)
    if agent == "codex":
        return run_codex(prompt, root, timeout_s)
    if agent == "claude":
        return run_claude(prompt, root, timeout_s)
    raise AdapterError("UNSUPPORTED_AGENT", agent)


def ensure_ledger(root: Path, topic: str, slug: str, agents: list[str]) -> None:
    path = root / ledger.DEFAULT_DIR / f"discuss-{slug}.md"
    if path.exists():
        return
    ledger.init_ledger(root=root, topic=topic, slug=slug, initiator=agents[0], participants=agents)


def orchestrate(
    *,
    root: Path,
    topic: str,
    slug: str,
    agents: list[str],
    max_rounds: int,
    fake: bool,
    timeout_s: int,
) -> int:
    ensure_ledger(root, topic, slug, agents)
    turn_count = 0
    agent_index = 0
    while turn_count < max_rounds:
        status = ledger.get_status(root=root, slug=slug)
        if status.frontmatter.get("status") in (ledger.STATUS_AGREED, ledger.STATUS_DEADLOCK):
            print(f"EXIT: {status.frontmatter.get('status')}")
            return 0
        agent = agents[agent_index % len(agents)]
        ledger.set_next(root=root, slug=slug, next_agent=agent)
        status = ledger.get_status(root=root, slug=slug)
        target_document = read_target_document(root, topic)
        prompt = build_prompt(agent, topic, target_document, status)
        payload = normalize_result(call_agent(agent, prompt, root, status, fake, timeout_s))
        result = ledger.record_agent_turn(
            root=root,
            slug=slug,
            author=agent,
            convergences=payload["convergences"],
            contests=payload["contests"],
            new_points=payload["new_points"],
            end_turn_after=True,
        )
        print(result.message, end="")
        turn_count += 1
        agent_index += 1
        status = ledger.get_status(root=root, slug=slug)
        if status.frontmatter.get("status") in (ledger.STATUS_AGREED, ledger.STATUS_DEADLOCK):
            print(f"EXIT: {status.frontmatter.get('status')}")
            return 0
    print(f"STOP: max rounds reached ({max_rounds})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local discuss-ledger orchestration round-robin")
    parser.add_argument("--root", default=os.getcwd(), help="target project root")
    parser.add_argument("--topic", required=True, help="discussion topic or source document")
    parser.add_argument("--slug", help="ledger slug; defaults to topic-derived slug")
    parser.add_argument("--agents", default="codex,claude", help="comma list limited to codex,claude")
    parser.add_argument("--max-rounds", type=int, default=6)
    parser.add_argument("--adapter-mode", choices=["real", "fake"], default="real")
    parser.add_argument("--fake", action="store_true", help="use deterministic fake adapters")
    parser.add_argument("--timeout-s", type=int, default=900, help="per-agent timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve()
        agents = parse_agents(args.agents)
        slug = args.slug or ledger.derive_slug(args.topic)
        fake = args.fake or args.adapter_mode == "fake"
        return orchestrate(
            root=root,
            topic=args.topic,
            slug=slug,
            agents=agents,
            max_rounds=args.max_rounds,
            fake=fake,
            timeout_s=args.timeout_s,
        )
    except (AdapterError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
