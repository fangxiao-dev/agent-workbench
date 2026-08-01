#!/usr/bin/env python3
"""Local round-robin orchestrator for Codex and Claude discuss-ledger turns."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
SRC = SKILL_DIR / "src"
SCHEMA_PATH = SKILL_DIR / "schemas" / "agent-result.schema.json"
LEDGER_PARTICIPANT_PROMPT_PATH = SKILL_DIR / "references" / "ledger-participant-prompt.md"
CALL_CODEX = SKILL_DIR.parent / "call-codex" / "scripts" / "call_codex.py"
CALL_CLAUDE = SKILL_DIR.parent / "call-claude" / "scripts" / "call_claude.py"
CALL_GROK = SKILL_DIR.parent / "call-grok" / "scripts" / "grok_task.py"
CLAUDE_AGENT_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "convergences": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "point": {"type": "string"},
                    "marker": {"type": "string"},
                    "line": {"type": "string"},
                },
                "required": ["point", "marker", "line"],
            },
        },
        "contests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "point": {"type": "string"},
                    "body": {"type": "string"},
                    "movement": {"type": "boolean"},
                },
                "required": ["point", "body", "movement"],
            },
        },
        "new_points": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["summary", "body"],
            },
        },
    },
    "required": ["convergences", "contests", "new_points"],
}
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from discuss_ledger_core import ledger


SUPPORTED_AGENTS = {"codex", "claude", "grok"}


class AdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def parse_agents(value: str) -> list[str]:
    agents = [part.strip().lower() for part in value.split(",") if part.strip()]
    unsupported = [agent for agent in agents if agent not in SUPPORTED_AGENTS]
    if unsupported:
        raise ValueError(f"unsupported agents: {', '.join(unsupported)}; supported: codex, claude, grok")
    if not agents:
        raise ValueError("at least one agent is required")
    return agents


def parse_json_object(output: str) -> dict[str, Any]:
    for parsed in iter_json_objects_from_text(output):
        return parsed
    raise json.JSONDecodeError("no JSON object found", output, 0)


def iter_json_objects_from_text(output: str):
    seen: set[str] = set()
    for candidate in iter_json_object_candidates(output):
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            yield parsed


def iter_json_object_candidates(output: str):
    stripped = output.strip()
    if stripped:
        yield stripped

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", output, flags=re.IGNORECASE | re.DOTALL):
        yield match.group(1)

    yield from iter_balanced_json_objects(output)


def iter_balanced_json_objects(output: str):
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(output):
        if start is None:
            if char == "{":
                start = index
                depth = 1
                in_string = False
                escaped = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield output[start : index + 1]
                start = None


def looks_like_agent_result(data: Any) -> bool:
    return isinstance(data, dict) and all(key in data for key in ("convergences", "contests", "new_points"))


def iter_agent_result_candidates(value: Any):
    if looks_like_agent_result(value):
        yield value
    if isinstance(value, str):
        for parsed in iter_json_objects_from_text(value):
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


def extract_agent_result_from_text(output: str) -> dict[str, Any] | None:
    for parsed in iter_json_objects_from_text(output):
        result = extract_agent_result(parsed)
        if result is not None:
            return result
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


def validate_turn_against_ledger(status: ledger.LedgerStatus, payload: dict[str, list[dict[str, Any]]]) -> None:
    open_ids = {point["id"] for point in status.open_points}
    invalid_refs: list[str] = []
    for section in ("convergences", "contests"):
        for item in payload.get(section, []):
            point_id = item.get("point")
            if point_id not in open_ids:
                invalid_refs.append(f"{section}[].point={point_id}")
    if invalid_refs:
        legal = ", ".join(sorted(open_ids)) if open_ids else "(none)"
        raise AdapterError(
            "INVALID_TURN",
            "invalid point references for current ledger state: "
            f"{', '.join(invalid_refs)}; legal open point IDs: {legal}. "
            "Use new_points for new issues or evidence that undermines prior convergence.",
        )


def build_turn_correction_prompt(original_prompt: str, status: ledger.LedgerStatus, error: AdapterError) -> str:
    open_ids = [point["id"] for point in status.open_points]
    legal = ", ".join(open_ids) if open_ids else "(none)"
    return f"""{original_prompt}

Your previous response was invalid for the current discuss-ledger state:
{error.message}

Correction rules:
- Current legal open point IDs: {legal}
- convergences[].point and contests[].point may reference only current legal open point IDs.
- If there are no legal open point IDs, return convergences=[] and contests=[].
- Do not contest or converge missing, closed, or already-converged point IDs.
- New issues, first-turn opinions, or evidence that undermines prior convergence must go in new_points.

Return corrected JSON only.
"""


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


def find_git_root(path: Path) -> Path | None:
    start = path if path.is_dir() else path.parent
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_root_and_topic(root_arg: str, topic_arg: str) -> tuple[Path, str]:
    root = Path(root_arg).resolve()
    topic_path = Path(topic_arg)
    candidate = topic_path if topic_path.is_absolute() else root / topic_path
    if not candidate.exists():
        return root, topic_arg
    git_root = find_git_root(candidate)
    if git_root is None:
        return root, topic_arg
    try:
        topic = candidate.resolve().relative_to(git_root).as_posix()
    except ValueError:
        return root, topic_arg
    return git_root.resolve(), topic


def build_prompt(agent: str, topic: str, target_document: str, status: ledger.LedgerStatus) -> str:
    open_point_ids = [point["id"] for point in status.open_points]
    open_points = "\n".join(
        f"- {point['id']} [{point['status']}] {point['summary']} (已历{point['rounds']}轮)"
        for point in status.open_points
    )
    if not open_points:
        open_points = "- (none)"
    legal_ids = ", ".join(open_point_ids) if open_point_ids else "(none)"
    convergence = "\n".join(f"- {item}" for item in status.convergence) if status.convergence else "- (none)"
    replacements = {
        "{{AGENT}}": agent,
        "{{TOPIC}}": topic,
        "{{TARGET_DOCUMENT}}": target_document,
        "{{SCHEMA}}": SCHEMA_PATH.read_text(encoding="utf-8"),
        "{{LEGAL_IDS}}": legal_ids,
        "{{OPEN_POINTS}}": open_points,
        "{{CONVERGENCE}}": convergence,
        "{{LEDGER_MARKDOWN}}": status.markdown,
    }
    prompt = LEDGER_PARTICIPANT_PROMPT_PATH.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt


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
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE if stdin is not None else None,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "cwd": str(cwd) if cwd else None,
    }
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(actual_command, **popen_kwargs)
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
            os.killpg(pid, signal.SIGTERM)
        except (AttributeError, OSError):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


def run_executor(script: Path, arguments: list[str], prompt: str, root: Path, timeout_s: int) -> str:
    if not script.is_file():
        raise AdapterError("EXECUTOR_NOT_FOUND", f"executor not found: {script}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".prompt", delete=False) as handle:
        handle.write(prompt)
        prompt_path = Path(handle.name)
    try:
        command = [sys.executable, str(script), "--cwd", str(root), "--prompt-file", str(prompt_path), *arguments]
        completed = run_process(command, timeout_s=timeout_s + 30, cwd=root)
    finally:
        prompt_path.unlink(missing_ok=True)
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterError("INVALID_EXECUTOR_OUTPUT", f"{script.name} did not return a JSON envelope") from exc
    if not isinstance(envelope, dict):
        raise AdapterError("INVALID_EXECUTOR_OUTPUT", f"{script.name} returned a non-object envelope")
    if completed.returncode != 0 or not envelope.get("ok"):
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = error.get("code") if isinstance(error.get("code"), str) else "AGENT_FAILED"
        message = error.get("message") if isinstance(error.get("message"), str) else completed.stderr.strip()
        raise AdapterError(code, message or f"{script.name} failed")
    text = envelope.get("text")
    if not isinstance(text, str) or not text.strip():
        raise AdapterError("INVALID_EXECUTOR_OUTPUT", f"{script.name} returned no final text")
    return text


def run_codex(prompt: str, root: Path, timeout_s: int) -> dict[str, Any]:
    text = run_executor(
        CALL_CODEX,
        [
            "--config",
            'service_tier="fast"',
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--output-schema",
            str(SCHEMA_PATH),
        ],
        prompt,
        root,
        timeout_s,
    )
    return parse_json_object(text)


def run_claude(prompt: str, root: Path, timeout_s: int, effort: str = "low") -> dict[str, Any]:
    schema_json = json.dumps(CLAUDE_AGENT_RESULT_SCHEMA, ensure_ascii=False, separators=(",", ":"))
    text = run_executor(
        CALL_CLAUDE,
        [
            "--no-session-persistence",
            "--disable-slash-commands",
            "--effort",
            effort,
            "--tools",
            "Read,Glob,Grep",
            "--system-prompt",
            "You are a non-interactive discuss-ledger participant. Prefer Chinese unless the task explicitly requires another language. Return only the requested structured result.",
            "--json-schema",
            schema_json,
        ],
        prompt,
        root,
        timeout_s,
    )
    result = extract_agent_result_from_text(text)
    if result is not None:
        return result

    invalid_output = text
    repair_prompt = (
        "Repair the following Claude result text into one JSON object matching the discuss-ledger schema. "
        "Return only the repaired agent result object, not the Claude CLI wrapper, not markdown. "
        "Preserve or convert prose to Chinese unless another language is explicitly required. "
        "Escape quotation marks inside JSON string values.\n\n"
        f"Schema:\n{schema_json}\n\n"
        f"Invalid Claude result text:\n{invalid_output}"
    )
    retry_text = run_executor(
        CALL_CLAUDE,
        [
            "--no-session-persistence",
            "--disable-slash-commands",
            "--effort",
            effort,
            "--tools",
            "",
            "--system-prompt",
            "You are a non-interactive discuss-ledger participant. Prefer Chinese unless the task explicitly requires another language. Return only the requested structured result.",
        ],
        repair_prompt,
        root,
        timeout_s,
    )
    result = extract_agent_result_from_text(retry_text)
    if result is not None:
        return result
    raise AdapterError("INVALID_JSON", "Claude did not return a valid agent result after repair")


def run_grok(prompt: str, root: Path, timeout_s: int) -> dict[str, Any]:
    text = run_executor(
        CALL_GROK,
        [
            "--effort",
            "low",
            "--tools",
            "",
            "--no-subagents",
            "--overall-timeout-sec",
            str(timeout_s),
        ],
        prompt,
        root,
        timeout_s,
    )
    result = extract_agent_result_from_text(text)
    if result is None:
        raise AdapterError("INVALID_JSON", "Grok did not return a valid agent result")
    return result


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


def call_agent(
    agent: str,
    prompt: str,
    root: Path,
    status: ledger.LedgerStatus,
    fake: bool,
    timeout_s: int,
    claude_effort: str = "low",
) -> dict[str, Any]:
    if fake:
        return run_fake(agent, status)
    if agent == "codex":
        return run_codex(prompt, root, timeout_s)
    if agent == "claude":
        return run_claude(prompt, root, timeout_s, claude_effort)
    if agent == "grok":
        return run_grok(prompt, root, timeout_s)
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
    claude_effort: str = "low",
) -> int:
    ensure_ledger(root, topic, slug, agents)
    for _round_index in range(max_rounds):
        for agent_index, agent in enumerate(agents):
            status = ledger.get_status(root=root, slug=slug)
            if status.frontmatter.get("status") in (ledger.STATUS_AGREED, ledger.STATUS_DEADLOCK):
                print(f"EXIT: {status.frontmatter.get('status')}")
                return 0
            ledger.set_next(root=root, slug=slug, next_agent=agent)
            status = ledger.get_status(root=root, slug=slug)
            target_document = read_target_document(root, topic)
            prompt = build_prompt(agent, topic, target_document, status)
            payload = normalize_result(call_agent(agent, prompt, root, status, fake, timeout_s, claude_effort))
            try:
                validate_turn_against_ledger(status, payload)
            except AdapterError as exc:
                if exc.code != "INVALID_TURN":
                    raise
                correction_prompt = build_turn_correction_prompt(prompt, status, exc)
                payload = normalize_result(call_agent(agent, correction_prompt, root, status, fake, timeout_s, claude_effort))
                validate_turn_against_ledger(status, payload)
            try:
                result = ledger.record_agent_turn(
                    root=root,
                    slug=slug,
                    author=agent,
                    convergences=payload["convergences"],
                    contests=payload["contests"],
                    new_points=payload["new_points"],
                    end_turn_after=False,
                )
            except (SystemExit, ValueError) as exc:
                raise AdapterError("INVALID_TURN", str(exc)) from exc
            print(result.message, end="")

            status = ledger.get_status(root=root, slug=slug)
            end_round = agent_index == len(agents) - 1 or not status.open_points
            if not end_round:
                continue
            result = ledger.end_turn(root=root, slug=slug)
            print(result.message, end="")
            status = ledger.get_status(root=root, slug=slug)
            if status.frontmatter.get("status") in (ledger.STATUS_AGREED, ledger.STATUS_DEADLOCK):
                print(f"EXIT: {status.frontmatter.get('status')}")
                return 0
            if agent_index != len(agents) - 1:
                break
    print(f"STOP: max rounds reached ({max_rounds} full participant cycles)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local discuss-ledger orchestration round-robin")
    parser.add_argument("--root", default=os.getcwd(), help="target project root")
    parser.add_argument("--topic", required=True, help="discussion topic or source document")
    parser.add_argument("--slug", help="ledger slug; defaults to topic-derived slug")
    parser.add_argument("--agents", default="codex,claude", help="comma list: codex, claude, grok")
    parser.add_argument("--max-rounds", type=int, default=5, help="full participant cycles (default 5)")
    parser.add_argument("--adapter-mode", choices=["real", "fake"], default="real")
    parser.add_argument("--fake", action="store_true", help="use deterministic fake adapters")
    parser.add_argument("--timeout-s", type=int, default=300, help="per-agent timeout in seconds")
    parser.add_argument("--claude-effort", choices=["low", "medium"], default="low", help="Claude effort selected by the calling agent from target scale")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root, topic = resolve_root_and_topic(args.root, args.topic)
        agents = parse_agents(args.agents)
        slug = args.slug or ledger.derive_slug(topic)
        fake = args.fake or args.adapter_mode == "fake"
        return orchestrate(
            root=root,
            topic=topic,
            slug=slug,
            agents=agents,
            max_rounds=args.max_rounds,
            fake=fake,
            timeout_s=args.timeout_s,
            claude_effort=args.claude_effort,
        )
    except (AdapterError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
