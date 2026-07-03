from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path(tempfile.gettempdir())
DEFAULT_DIR = "codex-grill"
STATE_START = "<!-- grill-ledger-state"
STATE_END = "-->"

STATUS_OPEN = "进行中"
STATUS_NEEDS_USER = "待用户裁决"
STATUS_CONVERGED = "已收敛"

Q_STATUS_OPEN = "待回答"
Q_STATUS_ANSWERED = "已回答"
Q_STATUS_CONVERGED = "已收敛"
Q_STATUS_NEEDS_USER = "待用户裁决"


@dataclass(frozen=True)
class CommandResult:
    message: str


@dataclass(frozen=True)
class QuestionResult(CommandResult):
    question_id: str


@dataclass(frozen=True)
class LedgerStatus:
    path: Path
    frontmatter: dict
    questions: dict[str, dict]
    state: dict


def ledger_path(root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> Path:
    return Path(root) / directory / f"grill-{slug}.md"


def _slug_is_safe(slug: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", slug))


def _next_question_id(state: dict) -> str:
    return f"Q{len(state['questions']) + 1}"


def _initial_state(topic: str, slug: str, initiator: str) -> dict:
    return {
        "frontmatter": {
            "status": STATUS_OPEN,
            "round": 1,
            "next": "questioner",
            "topic": topic,
            "slug": slug,
            "participants": [initiator],
        },
        "convergences": [],
        "needs_user": [],
        "questions": [],
        "stop_proof": "尚未停止：仍需沿设计树继续提出问题。",
        "events": [],
    }


def _load_state(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    start = text.index(STATE_START) + len(STATE_START)
    end = text.index(STATE_END, start)
    return json.loads(text[start:end].strip())


def _write_state(root: Path | str, slug: str, state: dict, directory: str = DEFAULT_DIR) -> Path:
    path = ledger_path(root, slug, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(state), encoding="utf-8")
    return path


def _load(root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> tuple[Path, dict]:
    path = ledger_path(root, slug, directory)
    if not path.exists():
        raise FileNotFoundError(f"ledger not found: {path}")
    return path, _load_state(path)


def _add_participant(state: dict, author: str) -> None:
    participants = state["frontmatter"].setdefault("participants", [])
    if author not in participants:
        participants.append(author)


def _question_map(state: dict) -> dict[str, dict]:
    return {question["id"]: question for question in state["questions"]}


def _require_question(state: dict, question_id: str) -> dict:
    questions = _question_map(state)
    if question_id not in questions:
        raise ValueError(f"unknown question: {question_id}")
    return questions[question_id]


def _recompute_status(state: dict) -> str:
    questions = state["questions"]
    if not questions:
        status = STATUS_OPEN
    elif any(q["status"] == Q_STATUS_NEEDS_USER for q in questions):
        status = STATUS_NEEDS_USER
    else:
        status = STATUS_OPEN
    state["frontmatter"]["status"] = status
    state["frontmatter"]["next"] = "user" if status == STATUS_NEEDS_USER else "questioner"
    if status == STATUS_NEEDS_USER:
        state["stop_proof"] = "自动判断暂停：剩余问题依赖真实用户的产品意图、偏好或风险取舍。"
    else:
        state["stop_proof"] = "尚未停止：仍有开放问题或未探索分支。"
    return status


def _mark_stopped(state: dict, proof: str) -> str:
    if any(q["status"] == Q_STATUS_NEEDS_USER for q in state["questions"]):
        status = STATUS_NEEDS_USER
        state["frontmatter"]["status"] = status
        state["frontmatter"]["next"] = "user"
        state["stop_proof"] = proof
        return status
    status = STATUS_CONVERGED
    state["frontmatter"]["status"] = status
    state["frontmatter"]["next"] = "done"
    state["stop_proof"] = proof
    return status


def init_ledger(
    *,
    root: Path | str,
    topic: str,
    slug: str,
    initiator: str,
    directory: str = DEFAULT_DIR,
    force: bool = False,
) -> CommandResult:
    if not _slug_is_safe(slug):
        raise ValueError("slug may contain only letters, numbers, dot, underscore, and dash")
    path = ledger_path(root, slug, directory)
    if path.exists() and not force:
        raise FileExistsError(f"ledger already exists: {path}; use status or pass force=True")
    state = _initial_state(topic, slug, initiator)
    path = _write_state(root, slug, state, directory)
    return CommandResult(f"initialized Q ledger at {path}")


def add_question(
    *,
    root: Path | str,
    slug: str,
    author: str,
    branch: str,
    question: str,
    why_now: str,
    recommended_default: str,
    directory: str = DEFAULT_DIR,
) -> QuestionResult:
    _, state = _load(root, slug, directory)
    _add_participant(state, author)
    question_id = _next_question_id(state)
    state["questions"].append(
        {
            "id": question_id,
            "branch": branch,
            "question": question,
            "why_now": why_now,
            "recommended_default": recommended_default,
            "asked_by": author,
            "answer_author": "",
            "answer": "",
            "evidence": "",
            "uncertainty": "",
            "needs_user": False,
            "status": Q_STATUS_OPEN,
            "decision": "",
            "rationale": "",
            "impact": "",
        }
    )
    state["events"].append(f"{author} 提出 {question_id}: {question}")
    state["frontmatter"]["status"] = STATUS_OPEN
    state["frontmatter"]["next"] = "answerer"
    path = _write_state(root, slug, state, directory)
    return QuestionResult(f"added {question_id} at {path}", question_id=question_id)


def record_answer(
    *,
    root: Path | str,
    slug: str,
    question: str,
    author: str,
    answer: str,
    evidence: str,
    uncertainty: str,
    needs_user: bool,
    directory: str = DEFAULT_DIR,
) -> CommandResult:
    _, state = _load(root, slug, directory)
    _add_participant(state, author)
    item = _require_question(state, question)
    item["answer_author"] = author
    item["answer"] = answer
    item["evidence"] = evidence
    item["uncertainty"] = uncertainty
    item["needs_user"] = bool(needs_user)
    item["status"] = Q_STATUS_ANSWERED
    state["events"].append(f"{author} 回答 {question}: {answer}")
    _recompute_status(state)
    _write_state(root, slug, state, directory)
    return CommandResult(f"recorded answer for {question}")


def converge_question(
    *,
    root: Path | str,
    slug: str,
    question: str,
    line: str,
    rationale: str,
    impact: str,
    directory: str = DEFAULT_DIR,
) -> CommandResult:
    _, state = _load(root, slug, directory)
    item = _require_question(state, question)
    item["status"] = Q_STATUS_CONVERGED
    item["decision"] = line
    item["rationale"] = rationale
    item["impact"] = impact
    state["convergences"] = [c for c in state["convergences"] if c["question"] != question]
    state["convergences"].append(
        {
            "question": question,
            "line": line,
            "rationale": rationale,
            "impact": impact,
            "evidence": item.get("evidence", ""),
        }
    )
    state["needs_user"] = [n for n in state["needs_user"] if n["question"] != question]
    state["events"].append(f"{question} 收敛: {line}")
    _recompute_status(state)
    _write_state(root, slug, state, directory)
    return CommandResult(f"converged {question}")


def need_user(
    *,
    root: Path | str,
    slug: str,
    question: str,
    line: str,
    directory: str = DEFAULT_DIR,
) -> CommandResult:
    _, state = _load(root, slug, directory)
    item = _require_question(state, question)
    item["status"] = Q_STATUS_NEEDS_USER
    state["needs_user"] = [n for n in state["needs_user"] if n["question"] != question]
    state["needs_user"].append({"question": question, "line": line, "branch": item["branch"]})
    state["events"].append(f"{question} 需要用户裁决: {line}")
    _recompute_status(state)
    _write_state(root, slug, state, directory)
    return CommandResult(f"marked {question} as needing user")


def end_turn(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> CommandResult:
    _, state = _load(root, slug, directory)
    status = _recompute_status(state)
    if status == STATUS_OPEN:
        state["frontmatter"]["round"] += 1
    _write_state(root, slug, state, directory)
    return CommandResult(f"ended turn; status = {status}")


def stop_review(
    *,
    root: Path | str,
    slug: str,
    proof: str,
    directory: str = DEFAULT_DIR,
) -> CommandResult:
    _, state = _load(root, slug, directory)
    status = _mark_stopped(state, proof)
    _write_state(root, slug, state, directory)
    return CommandResult(f"stopped review; status = {status}")


def get_status(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> LedgerStatus:
    path, state = _load(root, slug, directory)
    return LedgerStatus(
        path=path,
        frontmatter=state["frontmatter"],
        questions=_question_map(state),
        state=state,
    )


def read_markdown(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> str:
    return ledger_path(root, slug, directory).read_text(encoding="utf-8")


def _render_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for key in ["status", "round", "next", "topic", "slug"]:
        value = fm.get(key, "")
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, str) else value}")
    lines.append("participants:")
    for participant in fm.get("participants", []):
        lines.append(f"  - {json.dumps(participant, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def _table_row(cells: list[str]) -> str:
    escaped = [str(cell).replace("\n", "<br>").replace("|", "\\|") for cell in cells]
    return "| " + " | ".join(escaped) + " |"


def _render_summary(state: dict) -> list[str]:
    lines = ["## 已收敛决策摘要", ""]
    if not state["convergences"]:
        lines.append("- 尚无已收敛决策。")
    else:
        for item in state["convergences"]:
            lines.append(
                f"- **{item['question']}**：{item['line']}；理由：{item['rationale']}；影响：{item['impact']}；证据：{item['evidence'] or '未记录'}。"
            )
    lines.extend(["", "## 待用户裁决", ""])
    if not state["needs_user"]:
        lines.append("- 暂无。")
    else:
        for item in state["needs_user"]:
            lines.append(f"- **{item['question']} / {item['branch']}**：{item['line']}")
    return lines


def _render_question_table(state: dict) -> list[str]:
    lines = [
        "## 问题与回答总览",
        "",
        _table_row(["ID", "分支", "问题", "状态", "回答来源"]),
        _table_row(["---", "---", "---", "---", "---"]),
    ]
    if not state["questions"]:
        lines.append(_table_row(["-", "-", "尚无问题", "-", "-"]))
    else:
        for item in state["questions"]:
            lines.append(
                _table_row(
                    [
                        item["id"],
                        item["branch"],
                        item["question"],
                        item["status"],
                        item.get("answer_author") or "-",
                    ]
                )
            )
    return lines


def _render_open_branches(state: dict) -> list[str]:
    lines = [
        "## 当前未探索分支",
        "",
        _table_row(["ID", "分支", "为什么现在问", "推荐默认"]),
        _table_row(["---", "---", "---", "---"]),
    ]
    open_questions = [q for q in state["questions"] if q["status"] in {Q_STATUS_OPEN, Q_STATUS_ANSWERED}]
    if not open_questions:
        lines.append(_table_row(["-", "-", "暂无开放问题。", "-"]))
    else:
        for item in open_questions:
            lines.append(
                _table_row(
                    [
                        item["id"],
                        item["branch"],
                        item["why_now"],
                        item["recommended_default"],
                    ]
                )
            )
    return lines


def _render_full_log(state: dict) -> list[str]:
    lines = ["## 完整记录", ""]
    if not state["questions"]:
        lines.append("- 尚无。")
        return lines
    for item in state["questions"]:
        lines.extend(
            [
                f"### {item['id']} {item['branch']}",
                "",
                f"- 问题：{item['question']}",
                f"- 为什么现在问：{item['why_now']}",
                f"- 推荐默认：{item['recommended_default']}",
                f"- 回答：{item['answer'] or '尚未回答'}",
                f"- 证据：{item['evidence'] or '尚未记录'}",
                f"- 不确定性：{item['uncertainty'] or '尚未记录'}",
                f"- 状态：{item['status']}",
                "",
            ]
        )
    return lines


def _render(state: dict) -> str:
    topic = state["frontmatter"]["topic"]
    chunks = [
        _render_frontmatter(state["frontmatter"]),
        "",
        STATE_START,
        json.dumps(state, ensure_ascii=False, indent=2),
        STATE_END,
        "",
        f"# Grill Ledger：{topic}",
        "",
        f"- 状态：{state['frontmatter']['status']}",
        f"- 当前轮次：{state['frontmatter']['round']}",
        f"- 下一角色：{state['frontmatter']['next']}",
        "",
        *_render_summary(state),
        "",
        *_render_question_table(state),
        "",
        *_render_open_branches(state),
        "",
        *_render_full_log(state),
        "",
        "## 停止证明",
        "",
        state["stop_proof"],
        "",
    ]
    return "\n".join(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic writer for Grill Me Smartly ledgers.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--dir", default=DEFAULT_DIR)
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("--topic", required=True)
    init.add_argument("--slug", required=True)
    init.add_argument("--initiator", required=True)
    init.add_argument("--force", action="store_true")

    status = sub.add_parser("status")
    status.add_argument("--slug", required=True)

    add = sub.add_parser("add-question")
    add.add_argument("--slug", required=True)
    add.add_argument("--author", required=True)
    add.add_argument("--branch", required=True)
    add.add_argument("--question", required=True)
    add.add_argument("--why-now", required=True)
    add.add_argument("--recommended-default", required=True)

    answer = sub.add_parser("record-answer")
    answer.add_argument("--slug", required=True)
    answer.add_argument("--question", required=True)
    answer.add_argument("--author", required=True)
    answer.add_argument("--answer", required=True)
    answer.add_argument("--evidence", required=True)
    answer.add_argument("--uncertainty", required=True)
    answer.add_argument("--needs-user", choices=["true", "false"], required=True)

    converge = sub.add_parser("converge")
    converge.add_argument("--slug", required=True)
    converge.add_argument("--question", required=True)
    converge.add_argument("--line", required=True)
    converge.add_argument("--rationale", required=True)
    converge.add_argument("--impact", required=True)

    needs_user = sub.add_parser("need-user")
    needs_user.add_argument("--slug", required=True)
    needs_user.add_argument("--question", required=True)
    needs_user.add_argument("--line", required=True)

    end_turn_parser = sub.add_parser("end-turn")
    end_turn_parser.add_argument("--slug", required=True)

    stop_parser = sub.add_parser("stop")
    stop_parser.add_argument("--slug", required=True)
    stop_parser.add_argument("--proof", required=True)

    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if args.cmd == "init":
            result = init_ledger(
                root=root,
                topic=args.topic,
                slug=args.slug,
                initiator=args.initiator,
                directory=args.dir,
                force=args.force,
            )
        elif args.cmd == "status":
            result = CommandResult(
                json.dumps(get_status(root=root, slug=args.slug, directory=args.dir).state, ensure_ascii=False, indent=2)
            )
        elif args.cmd == "add-question":
            result = add_question(
                root=root,
                slug=args.slug,
                author=args.author,
                branch=args.branch,
                question=args.question,
                why_now=args.why_now,
                recommended_default=args.recommended_default,
                directory=args.dir,
            )
        elif args.cmd == "record-answer":
            result = record_answer(
                root=root,
                slug=args.slug,
                question=args.question,
                author=args.author,
                answer=args.answer,
                evidence=args.evidence,
                uncertainty=args.uncertainty,
                needs_user=args.needs_user == "true",
                directory=args.dir,
            )
        elif args.cmd == "converge":
            result = converge_question(
                root=root,
                slug=args.slug,
                question=args.question,
                line=args.line,
                rationale=args.rationale,
                impact=args.impact,
                directory=args.dir,
            )
        elif args.cmd == "need-user":
            result = need_user(root=root, slug=args.slug, question=args.question, line=args.line, directory=args.dir)
        elif args.cmd == "end-turn":
            result = end_turn(root=root, slug=args.slug, directory=args.dir)
        elif args.cmd == "stop":
            result = stop_review(root=root, slug=args.slug, proof=args.proof, directory=args.dir)
        else:
            raise AssertionError(args.cmd)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
