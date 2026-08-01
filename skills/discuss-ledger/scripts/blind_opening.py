"""Independent multi-agent idea discovery for discuss-ledger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Callable

import discuss_orchestrator as orchestrator


SKILL_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SKILL_DIR / "schemas" / "blind-opening-result.schema.json"
SKILLS_DIR = SKILL_DIR.parent


class BlindOpeningError(RuntimeError):
    pass


def normalize_summary(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_result(value: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(value, dict) or set(value) != {"ideas", "new_points"}:
        raise BlindOpeningError("INVALID_OUTPUT: expected only ideas and new_points")
    normalized: dict[str, list[dict[str, str]]] = {}
    for key in ("ideas", "new_points"):
        entries = value[key]
        if not isinstance(entries, list):
            raise BlindOpeningError(f"INVALID_OUTPUT: {key} must be an array")
        normalized[key] = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"summary", "body"}:
                raise BlindOpeningError(f"INVALID_OUTPUT: {key} entries require summary and body")
            summary = entry["summary"]
            body = entry["body"]
            if not isinstance(summary, str) or not summary.strip() or not isinstance(body, str) or not body.strip():
                raise BlindOpeningError(f"INVALID_OUTPUT: {key} summary and body must be non-empty strings")
            normalized[key].append({"summary": summary.strip(), "body": body.strip()})
    return normalized


def parse_result_text(text: str) -> dict[str, list[dict[str, str]]]:
    for candidate in orchestrator.iter_json_objects_from_text(text):
        try:
            return validate_result(candidate)
        except BlindOpeningError:
            continue
    raise BlindOpeningError("INVALID_OUTPUT: participant did not return Blind Opening JSON")


def build_prompt(agent: str, topic: str, target_document: str) -> str:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    return f"""You are {agent} participating in a Blind Opening.

Topic: {topic}

Target document:
{target_document}

Independently form your own view before any discussion. You have not received,
and must not assume, another participant's opinions. Identify candidate approaches
or insights in ideas, and only material questions or disagreements worth later
discussion in new_points.

Return only JSON matching this schema:
{schema}
"""


def executor_path(agent: str) -> Path:
    names = {
        "codex": SKILLS_DIR / "call-codex" / "scripts" / "call_codex.py",
        "claude": SKILLS_DIR / "call-claude" / "scripts" / "call_claude.py",
        "grok": SKILLS_DIR / "call-grok" / "scripts" / "grok_task.py",
    }
    try:
        return names[agent]
    except KeyError as exc:
        raise BlindOpeningError(f"unsupported agent: {agent}") from exc


def claude_schema_json() -> str:
    """Render the canonical schema for Claude's draft-agnostic validator."""

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema.pop("$schema", None)
    schema.pop("$id", None)
    return json.dumps(schema, ensure_ascii=False, separators=(",", ":"))


def call_executor(
    agent: str,
    prompt: str,
    root: Path,
    timeout_s: int,
    claude_effort: str = "low",
) -> dict[str, list[dict[str, str]]]:
    path = executor_path(agent)
    if not path.is_file():
        raise BlindOpeningError(f"EXECUTOR_NOT_FOUND: {path}")
    command = [sys.executable, str(path), "--cwd", str(root), "--prompt", prompt]
    if agent == "codex":
        command.extend(
            [
                "--timeout-s",
                str(timeout_s),
                "--config",
                'service_tier="fast"',
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--output-schema",
                str(SCHEMA_PATH),
            ]
        )
    elif agent == "claude":
        command.extend(
            [
                "--timeout-s",
                str(timeout_s),
                "--effort",
                claude_effort,
                "--tools",
                "Read,Glob,Grep",
                "--system-prompt",
                "You are a non-interactive Blind Opening participant. Return only the requested structured result.",
                "--json-schema",
                claude_schema_json(),
                "--no-session-persistence",
            ]
        )
    else:
        command.extend(
            [
                "--effort",
                "low",
                "--tools",
                "",
                "--no-subagents",
                "--rules",
                "Return only one JSON object matching the caller-provided schema. Do not use Markdown fences or prose.",
                "--overall-timeout-sec",
                str(timeout_s),
            ]
        )
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout_s + 15, check=False)
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BlindOpeningError(f"EXECUTOR_INVALID_ENVELOPE: {agent}") from exc
    if completed.returncode != 0 or not envelope.get("ok"):
        error = envelope.get("error") or {"code": "AGENT_FAILED", "message": completed.stderr.strip()}
        raise BlindOpeningError(f"{error.get('code', 'AGENT_FAILED')}: {error.get('message', agent)}")
    text = envelope.get("text")
    if not isinstance(text, str):
        raise BlindOpeningError(f"INVALID_OUTPUT: {agent} did not return Blind Opening text")
    try:
        return parse_result_text(text)
    except BlindOpeningError as exc:
        raise BlindOpeningError(f"INVALID_OUTPUT: {agent} did not return Blind Opening JSON") from exc


def fake_result(agent: str) -> dict[str, list[dict[str, str]]]:
    return {
        "ideas": [{"summary": f"Fake {agent} idea", "body": f"Independent {agent} idea."}],
        "new_points": [{"summary": f"Fake {agent} concern", "body": f"Independent {agent} concern."}],
    }


def aggregate(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    points: dict[str, dict[str, str]] = {}
    for result in results:
        agent = result["agent"]
        for point in result["new_points"]:
            key = normalize_summary(point["summary"])
            source_body = f"[{agent}] {point['body']}"
            existing = points.get(key)
            if existing is None:
                points[key] = {"summary": point["summary"], "body": source_body}
            else:
                existing["body"] += f"\n\n{source_body}"
    return list(points.values())


def render_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Blind Opening: {result['slug']}", "", f"Topic: {result['topic']}", "", "## Independent findings", ""]
    for participant in result["participants"]:
        lines.extend([f"### {participant['agent']}", ""])
        lines.append("#### Ideas")
        for idea in participant["ideas"]:
            lines.append(f"- **{idea['summary']}** — {idea['body']}")
        lines.append("")
        lines.append("#### Candidate discussion points")
        for point in participant["new_points"]:
            lines.append(f"- **{point['summary']}** — {point['body']}")
        lines.append("")
    lines.extend(["## Consolidated initial points", ""])
    for point in result["initial_points"]:
        lines.append(f"- **{point['summary']}** — {point['body']}")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(result: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"blind-{result['slug']}-{uuid.uuid4().hex[:8]}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def run_blind_opening(
    *,
    root: Path,
    topic: str,
    slug: str,
    agents: list[str],
    timeout_s: int,
    output_dir: Path,
    fake: bool = False,
    claude_effort: str = "low",
    agent_runner: Callable[[str, str, Path, int], dict[str, list[dict[str, str]]]] | None = None,
) -> dict[str, Any]:
    target_document = orchestrator.read_target_document(root, topic)
    runner = agent_runner or (
        lambda agent, prompt, runner_root, runner_timeout: call_executor(
            agent,
            prompt,
            runner_root,
            runner_timeout,
            claude_effort,
        )
    )
    participants: list[dict[str, Any]] = []
    for agent in agents:
        prompt = build_prompt(agent, topic, target_document)
        raw = fake_result(agent) if fake else runner(agent, prompt, root, timeout_s)
        normalized = validate_result(raw)
        participants.append({"agent": agent, **normalized})
    result: dict[str, Any] = {
        "topic": topic,
        "slug": slug,
        "participants": participants,
        "initial_points": aggregate(participants),
    }
    result["artifacts"] = write_artifacts(result, output_dir)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run independent multi-agent Blind Opening")
    parser.add_argument("--root", default=".", help="target project root")
    parser.add_argument("--topic", required=True, help="topic or target document")
    parser.add_argument("--slug", help="result slug; defaults to topic-derived slug")
    parser.add_argument("--agents", default="codex,claude", help="comma list: codex, claude, grok")
    parser.add_argument("--timeout-s", type=int, default=300, help="per participant timeout in seconds")
    parser.add_argument("--claude-effort", choices=["low", "medium"], default="low", help="Claude effort selected by the calling agent from target scale")
    parser.add_argument("--output-dir", default=str(Path(tempfile.gettempdir()) / "discuss-ledger"))
    parser.add_argument("--fake", action="store_true", help="use deterministic fake participants")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root, topic = orchestrator.resolve_root_and_topic(args.root, args.topic)
        agents = orchestrator.parse_agents(args.agents)
        slug = args.slug or orchestrator.ledger.derive_slug(topic)
        result = run_blind_opening(
            root=root,
            topic=topic,
            slug=slug,
            agents=agents,
            timeout_s=args.timeout_s,
            output_dir=Path(args.output_dir),
            fake=args.fake,
            claude_effort=args.claude_effort,
        )
        print(json.dumps({"ok": True, "artifacts": result["artifacts"], "initial_points": result["initial_points"]}, ensure_ascii=False))
        return 0
    except (BlindOpeningError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
