#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import uuid
from pathlib import Path


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "generated-skill"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def read_json(path: Path, default):
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_config(config_path: Path) -> dict:
    default = {
        "min_session_length": 10,
        "candidate_name_prefix": "learned",
        "pending_dir": "skills/continuous-learning/pending",
        "state_file": "skills/continuous-learning/pending/state.json",
        "index_file": "skills/continuous-learning/pending/index.json",
    }
    if not config_path.exists():
        return default
    current = read_json(config_path, {})
    merged = default.copy()
    merged.update(current)
    return merged


def resolve_path(value: str, root: Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return root / p


def proposal_files(pending_dir: Path) -> list[Path]:
    return sorted(
        [p for p in pending_dir.glob("proposal-*.json") if p.name not in {"index.json", "state.json"}],
        key=lambda x: x.name,
        reverse=True,
    )


def build_state_and_index(pending_dir: Path, state_file: Path, index_file: Path) -> tuple[dict, dict]:
    proposals = []
    for file in proposal_files(pending_dir):
        data = read_json(file, None)
        if not isinstance(data, dict):
            continue
        proposals.append(
            {
                "id": data.get("id"),
                "file": str(file),
                "candidateSkillName": data.get("candidateSkillName"),
                "title": data.get("title"),
                "createdAt": data.get("createdAt"),
                "messageCount": data.get("messageCount"),
                "status": data.get("status", "pending"),
            }
        )
    latest = proposals[0] if proposals else None
    state = {
        "hasPending": len(proposals) > 0,
        "pendingCount": len(proposals),
        "latestProposal": latest,
        "updatedAt": utc_now(),
        "nextAction": "run approve-pending-skill / reject-pending-skill / list-pending-skills",
    }
    index = {"updatedAt": state["updatedAt"], "pending": proposals}
    write_json(state_file, state)
    write_json(index_file, index)
    return state, index


def build_default_skill_content(proposal: dict) -> str:
    name = proposal["candidateSkillName"]
    title = proposal["title"]
    description = proposal["description"]
    source = proposal.get("transcriptPath", "")
    created_at = proposal.get("createdAt", "")
    return "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {description}",
            "origin: continuous-learning-local",
            "---",
            "",
            f"# {title}",
            "",
            "## Purpose",
            "",
            description,
            "",
            "## Trigger",
            "",
            "- Use when encountering the same workflow pattern repeatedly.",
            "",
            "## Workflow",
            "",
            "- Identify whether the current task matches this repeated pattern.",
            "- Apply the pattern steps consistently.",
            "- Verify outcome and adjust with project context.",
            "",
            "## Notes",
            "",
            f"- Generated from proposal at {created_at}",
            f"- Source transcript: {source}",
            "",
        ]
    )


def cmd_create(args) -> int:
    root = repo_root()
    config = load_config(Path(args.config))
    pending_dir = resolve_path(config["pending_dir"], root)
    state_file = resolve_path(config["state_file"], root)
    index_file = resolve_path(config["index_file"], root)
    pending_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    transcript_name = Path(args.transcript).stem if args.transcript else "session"
    base_slug = slugify(transcript_name)
    candidate = slugify(f'{config.get("candidate_name_prefix", "learned")}-{base_slug}')
    proposal_id = f"{ts}-{suffix}"
    proposal_file = pending_dir / f"proposal-{proposal_id}__{candidate}.json"

    title = f"Learned Pattern {proposal_id}"
    description = f"Draft proposal extracted from a session with {args.message_count} user messages."
    proposal = {
        "id": proposal_id,
        "status": "pending",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "transcriptPath": args.transcript,
        "messageCount": args.message_count,
        "candidateSkillName": candidate,
        "title": title,
        "description": description,
        "nextAction": "approve or reject this proposal",
    }
    write_json(proposal_file, proposal)
    state, index = build_state_and_index(pending_dir, state_file, index_file)
    out = {
        "event": "pending_proposal_created",
        "proposalFile": str(proposal_file),
        "proposalId": proposal_id,
        "stateFile": str(state_file),
        "indexFile": str(index_file),
        "hasPending": state["hasPending"],
        "pendingCount": state["pendingCount"],
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def resolve_proposal_input(pending_dir: Path, proposal_input: str | None) -> Path:
    files = proposal_files(pending_dir)
    if not files:
        raise RuntimeError("No pending proposals found.")
    if not proposal_input:
        return files[0]
    p = Path(proposal_input)
    if p.exists():
        return p
    for f in files:
        if proposal_input in f.name:
            return f
    raise RuntimeError(f"Proposal not found: {proposal_input}")


def cmd_list(args) -> int:
    root = repo_root()
    config = load_config(Path(args.config))
    pending_dir = resolve_path(config["pending_dir"], root)
    state_file = resolve_path(config["state_file"], root)
    index_file = resolve_path(config["index_file"], root)
    pending_dir.mkdir(parents=True, exist_ok=True)
    state, index = build_state_and_index(pending_dir, state_file, index_file)
    print(json.dumps({"state": state, "index": index}, ensure_ascii=False))
    return 0


def cmd_state(args) -> int:
    root = repo_root()
    config = load_config(Path(args.config))
    pending_dir = resolve_path(config["pending_dir"], root)
    state_file = resolve_path(config["state_file"], root)
    index_file = resolve_path(config["index_file"], root)
    pending_dir.mkdir(parents=True, exist_ok=True)
    state, _ = build_state_and_index(pending_dir, state_file, index_file)
    print(json.dumps(state, ensure_ascii=False))
    return 0


def cmd_reject(args) -> int:
    root = repo_root()
    config = load_config(Path(args.config))
    pending_dir = resolve_path(config["pending_dir"], root)
    state_file = resolve_path(config["state_file"], root)
    index_file = resolve_path(config["index_file"], root)
    pending_dir.mkdir(parents=True, exist_ok=True)
    proposal_file = resolve_proposal_input(pending_dir, args.proposal)
    proposal_file.unlink(missing_ok=True)
    state, _ = build_state_and_index(pending_dir, state_file, index_file)
    print(json.dumps({"event": "proposal_rejected", "proposalFile": str(proposal_file), "state": state}, ensure_ascii=False))
    return 0


def cmd_approve(args) -> int:
    root = repo_root()
    config = load_config(Path(args.config))
    pending_dir = resolve_path(config["pending_dir"], root)
    state_file = resolve_path(config["state_file"], root)
    index_file = resolve_path(config["index_file"], root)
    pending_dir.mkdir(parents=True, exist_ok=True)
    proposal_file = resolve_proposal_input(pending_dir, args.proposal)
    proposal = read_json(proposal_file, {})
    skill_name = slugify(args.skill_name) if args.skill_name else slugify(proposal.get("candidateSkillName", "generated-skill"))
    skill_dir = root / "skills" / skill_name
    if skill_dir.exists():
        raise RuntimeError(f"Skill directory already exists: {skill_dir}")
    skill_dir.mkdir(parents=True, exist_ok=False)
    content = build_default_skill_content({**proposal, "candidateSkillName": skill_name})
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    proposal_file.unlink(missing_ok=True)
    state, _ = build_state_and_index(pending_dir, state_file, index_file)
    print(
        json.dumps(
            {
                "event": "proposal_approved",
                "skillName": skill_name,
                "skillFile": str(skill_file),
                "state": state,
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config.json"))
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--transcript", required=True)
    create.add_argument("--message-count", required=True, type=int)
    create.set_defaults(func=cmd_create)

    ls = sub.add_parser("list")
    ls.set_defaults(func=cmd_list)

    state = sub.add_parser("state")
    state.set_defaults(func=cmd_state)

    reject = sub.add_parser("reject")
    reject.add_argument("--proposal")
    reject.set_defaults(func=cmd_reject)

    approve = sub.add_parser("approve")
    approve.add_argument("--proposal")
    approve.add_argument("--skill-name")
    approve.set_defaults(func=cmd_approve)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
