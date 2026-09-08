from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
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
QUESTION_STATUSES = (Q_STATUS_OPEN, Q_STATUS_ANSWERED, Q_STATUS_NEEDS_USER, Q_STATUS_CONVERGED)


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
    return Path(root) / directory / f"grill-{slug}.ledger.md"


def state_path(root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> Path:
    return Path(root) / directory / f"grill-{slug}.ledger.json"


def review_path(root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> Path:
    return Path(root) / directory / f"grill-{slug}.review.md"


def _legacy_ledger_path(root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> Path:
    return Path(root) / directory / f"grill-{slug}.md"


def legacy_backup_path(root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> Path:
    return Path(root) / directory / f"grill-{slug}.legacy.md"


def _slug_is_safe(slug: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", slug))


def _initial_state(topic: str, slug: str, initiator: str) -> dict:
    return {
        "schema_version": 2,
        "frontmatter": {"status": STATUS_OPEN, "round": 1, "next": "questioner",
                        "topic": topic, "slug": slug, "participants": [initiator]},
        "questions": [],
        "stop_proof": "尚未停止：仍需沿设计树继续提出问题。",
    }


def _load_state(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".json":
        state = json.loads(text)
        if state.get("schema_version") != 2:
            raise ValueError("unsupported ledger schema_version")
        return state
    start = text.index(STATE_START) + len(STATE_START)
    state, _ = json.JSONDecoder().raw_decode(text[start:].lstrip())
    # Keep the original Markdown as the historical archive when a write migrates it.
    pending = {item["question"]: item["line"] for item in state.get("needs_user", [])}
    for question in state["questions"]:
        if question["id"] in pending:
            question["owner_question"] = pending[question["id"]]
    for key in ("events", "convergences", "needs_user"):
        state.pop(key, None)
    state["schema_version"] = 2
    return state


def _load(root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> tuple[Path, dict]:
    if not _slug_is_safe(slug):
        raise ValueError("unsafe slug")
    for path in (state_path(root, slug, directory), ledger_path(root, slug, directory),
                 _legacy_ledger_path(root, slug, directory)):
        if path.exists():
            return path, _load_state(path)
    raise FileNotFoundError(f"ledger not found: {state_path(root, slug, directory)}")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_state(root: Path | str, slug: str, state: dict, directory: str = DEFAULT_DIR,
                 path: Path | None = None) -> Path:
    target = state_path(root, slug, directory)
    if path is not None and path.suffix == ".md" and not target.exists():
        backup = legacy_backup_path(root, slug, directory)
        original = path.read_bytes()
        if backup.exists():
            if backup.read_bytes() != original:
                raise FileExistsError(f"legacy backup differs: {backup}")
        else:
            _atomic_write(backup, original)
        state["legacy_archive"] = str(backup.resolve())
    _atomic_write(target, json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8"))
    try:
        _write_index(root, slug, state, directory)
    except OSError as exc:
        print(f"warning: JSON saved at {target}; index failed: {exc}; run rebuild-index --slug {slug}", file=sys.stderr)
    return target


def _question_map(state: dict) -> dict[str, dict]:
    return {question["id"]: question for question in state["questions"]}


def _require_question(state: dict, question_id: str) -> dict:
    try:
        return _question_map(state)[question_id]
    except KeyError:
        raise ValueError(f"unknown question: {question_id}") from None


def _add_participant(state: dict, author: str) -> None:
    participants = state["frontmatter"]["participants"]
    if author not in participants:
        participants.append(author)


def _resolve_question(state: dict, item: dict, cache: dict | None = None) -> dict:
    source = state.get("imports", {}).get(item.get("batch_id"), {})
    resolved = {}
    if "path" in source:
        cache = {} if cache is None else cache
        key = source["path"]
        if key not in cache:
            data = Path(key).read_bytes()
            if hashlib.sha256(data).hexdigest() != source["sha256"]:
                raise ValueError(f"batch source changed: {key}")
            cache[key] = {entry["id"]: entry for entry in json.loads(data.decode("utf-8-sig"))["items"]}
        resolved.update(cache[key][item["source_id"]])
        resolved.pop("id", None)
    resolved.update(copy.deepcopy(item))
    resolved.pop("preview", None)
    return resolved


def _revise(item: dict, values: dict, kind: str, previous: dict) -> None:
    old = {key: previous.get(key) for key in values}
    if old == values:
        return
    if any(old.get(key) for key in ("answer", "decision", "owner_question")):
        # Imported originals already hold the first answer; preserve its reference, not a duplicate.
        if kind == "answer" and "batch_id" in item and "answer" not in item:
            old = {"batch_id": item["batch_id"], "source_id": item["source_id"]}
        item.setdefault("history", []).append({"kind": kind, "previous": old})
    item.update(values)


def _recompute_status(state: dict) -> str:
    status = STATUS_NEEDS_USER if any(q["status"] == Q_STATUS_NEEDS_USER for q in state["questions"]) else STATUS_OPEN
    state["frontmatter"].update(status=status, next="user" if status == STATUS_NEEDS_USER else "questioner")
    state["stop_proof"] = ("自动判断暂停：剩余问题依赖真实用户的产品意图、偏好或风险取舍。"
                           if status == STATUS_NEEDS_USER else "尚未停止：仍有开放问题或未探索分支。")
    return status


def _mark_stopped(state: dict, proof: str) -> str:
    unresolved = [q["id"] for q in state["questions"] if q["status"] in {Q_STATUS_OPEN, Q_STATUS_ANSWERED}]
    if unresolved:
        raise ValueError(f"cannot stop with unresolved questions: {', '.join(unresolved)}")
    status = STATUS_NEEDS_USER if any(q["status"] == Q_STATUS_NEEDS_USER for q in state["questions"]) else STATUS_CONVERGED
    state["frontmatter"].update(status=status, next="user" if status == STATUS_NEEDS_USER else "done")
    state["stop_proof"] = proof
    return status


def init_ledger(*, root: Path | str, topic: str, slug: str, initiator: str,
                directory: str = DEFAULT_DIR, force: bool = False) -> CommandResult:
    if not _slug_is_safe(slug):
        raise ValueError("unsafe slug")
    existing = next((p for p in (state_path(root, slug, directory), ledger_path(root, slug, directory),
                                _legacy_ledger_path(root, slug, directory)) if p.exists()), None)
    if existing and not force:
        raise FileExistsError(f"ledger already exists: {existing}; use status or pass force=True")
    path = _write_state(root, slug, _initial_state(topic, slug, initiator), directory, path=existing)
    return CommandResult(f"initialized Q ledger at {path}")


def add_question(*, root: Path | str, slug: str, author: str, branch: str, question: str,
                 why_now: str, recommended_default: str, directory: str = DEFAULT_DIR) -> QuestionResult:
    path, state = _load(root, slug, directory)
    _add_participant(state, author)
    question_id = f"Q{len(state['questions']) + 1}"
    state["questions"].append({
        "id": question_id, "branch": branch, "question": question, "why_now": why_now,
        "recommended_default": recommended_default, "asked_by": author, "answer_author": "",
        "answer": "", "evidence": "", "uncertainty": "", "needs_user": False,
        "status": Q_STATUS_OPEN, "decision": "", "rationale": "", "impact": "",
    })
    _recompute_status(state)
    if state["frontmatter"]["status"] == STATUS_OPEN:
        state["frontmatter"]["next"] = "answerer"
    target = _write_state(root, slug, state, directory, path)
    return QuestionResult(f"added {question_id} at {target}", question_id)


def record_answer(*, root: Path | str, slug: str, question: str, author: str, answer: str,
                  evidence: str, uncertainty: str, needs_user: bool, directory: str = DEFAULT_DIR) -> CommandResult:
    path, state = _load(root, slug, directory)
    item = _require_question(state, question)
    previous = _resolve_question(state, item)
    _revise(item, {"answer_author": author, "answer": answer, "evidence": evidence,
                   "uncertainty": uncertainty, "needs_user": bool(needs_user)}, "answer", previous)
    _add_participant(state, author)
    item["status"] = Q_STATUS_ANSWERED
    _recompute_status(state)
    _write_state(root, slug, state, directory, path)
    return CommandResult(f"recorded answer for {question}")


def converge_question(*, root: Path | str, slug: str, question: str, line: str, rationale: str,
                      impact: str, directory: str = DEFAULT_DIR) -> CommandResult:
    path, state = _load(root, slug, directory)
    item = _require_question(state, question)
    _revise(item, {"decision": line, "rationale": rationale, "impact": impact}, "decision", item)
    item["status"] = Q_STATUS_CONVERGED
    item["needs_user"] = False
    _recompute_status(state)
    _write_state(root, slug, state, directory, path)
    return CommandResult(f"converged {question}")


def need_user(*, root: Path | str, slug: str, question: str, line: str,
              directory: str = DEFAULT_DIR) -> CommandResult:
    path, state = _load(root, slug, directory)
    item = _require_question(state, question)
    _revise(item, {"owner_question": line}, "owner_question", item)
    item.update(status=Q_STATUS_NEEDS_USER, needs_user=True)
    _recompute_status(state)
    _write_state(root, slug, state, directory, path)
    return CommandResult(f"marked {question} as needing user")


def end_turn(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> CommandResult:
    path, state = _load(root, slug, directory)
    status = _recompute_status(state)
    if status == STATUS_OPEN:
        state["frontmatter"]["round"] += 1
    _write_state(root, slug, state, directory, path)
    return CommandResult(f"ended turn; status = {status}")


def import_round(*, root: Path | str, slug: str, file: Path | str, accept: list[str] | None = None,
                 directory: str = DEFAULT_DIR) -> CommandResult:
    if not _slug_is_safe(slug):
        raise ValueError("unsafe slug")
    source = Path(file).resolve()
    source_bytes = source.read_bytes()
    batch = json.loads(source_bytes.decode("utf-8-sig"))
    if not isinstance(batch, dict) or set(batch) != {"batch_id", "items"}:
        raise ValueError("round must contain batch_id and items")
    batch_id = batch["batch_id"]
    if not isinstance(batch_id, str) or not batch_id.strip():
        raise ValueError("batch_id must be a nonempty string")
    if not isinstance(batch["items"], list) or not batch["items"]:
        raise ValueError("items must be a nonempty list")
    text_fields = {
        "id", "branch", "question", "why_now", "recommended_default", "answer",
        "evidence", "uncertainty", "discussion", "questioner_review",
    }
    ids = set()
    for item in batch["items"]:
        if not isinstance(item, dict) or not text_fields.union({"needs_user"}) <= item.keys():
            raise ValueError("item is missing required fields")
        if item.keys() - text_fields - {"needs_user", "proposal"}:
            raise ValueError("item contains unknown fields")
        for key in text_fields:
            if not isinstance(item[key], str) or (key not in {"uncertainty", "discussion"} and not item[key].strip()):
                raise ValueError(f"invalid text field: {key}")
        if type(item["needs_user"]) is not bool:
            raise ValueError("needs_user must be a boolean")
        if item["id"] in ids:
            raise ValueError(f"duplicate item id: {item['id']}")
        ids.add(item["id"])
        if "proposal" in item:
            proposal = item["proposal"]
            if not isinstance(proposal, dict) or set(proposal) != {"line", "rationale", "impact"}:
                raise ValueError("proposal must contain line, rationale and impact")
            if any(not isinstance(value, str) or not value.strip() for value in proposal.values()):
                raise ValueError("proposal fields must be nonempty strings")
    accepted = set(accept or [])
    if accepted - ids:
        raise ValueError(f"unknown accepted item ids: {sorted(accepted - ids)}")
    for item in batch["items"]:
        if item["id"] in accepted and (item["needs_user"] or "proposal" not in item):
            raise ValueError(f"cannot accept {item['id']}: needs Owner or has no proposal")

    path, state = _load(root, slug, directory)
    fingerprint = hashlib.sha256(
        json.dumps([batch, sorted(accepted)], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    previous = state.get("imports", {}).get(batch_id)
    if previous:
        if previous["fingerprint"] != fingerprint:
            raise ValueError(f"batch {batch_id} already imported with different content or acceptance")
        return CommandResult(json.dumps({"batch_id": batch_id, "ids": previous["ids"], "replayed": True}))

    existing_ids = {q["source_id"] for q in state["questions"] if "source_id" in q}
    if existing_ids & ids:
        raise ValueError(f"item ids already imported: {sorted(existing_ids & ids)}; use existing ledger Q IDs")


    mapping = {}
    for entry in batch["items"]:
        question_id = f"Q{len(state['questions']) + 1}"
        mapping[entry["id"]] = question_id
        item = {
            "id": question_id, "batch_id": batch_id, "source_id": entry["id"], "branch": entry["branch"],
            "preview": _preview(entry["question"]), "asked_by": "Questioner", "answer_author": "Answerer",
            "needs_user": entry["needs_user"], "status": Q_STATUS_ANSWERED,
        }
        if entry["needs_user"]:
            item["status"] = Q_STATUS_NEEDS_USER
        elif entry["id"] in accepted:
            item.update(status=Q_STATUS_CONVERGED, decision=entry["proposal"]["line"],
                        rationale=entry["proposal"]["rationale"], impact=entry["proposal"]["impact"])
        state["questions"].append(item)
    state.setdefault("imports", {})[batch_id] = {
        "fingerprint": fingerprint, "ids": mapping, "path": str(source),
        "sha256": hashlib.sha256(source_bytes).hexdigest(),
    }
    _add_participant(state, "Questioner")
    _add_participant(state, "Answerer")
    _recompute_status(state)
    _write_state(root, slug, state, directory, path)
    return CommandResult(json.dumps({"batch_id": batch_id, "ids": mapping, "replayed": False}))


def stop_review(*, root: Path | str, slug: str, proof: str, directory: str = DEFAULT_DIR) -> CommandResult:
    path, state = _load(root, slug, directory)
    status = _mark_stopped(state, proof)
    target = _write_state(root, slug, state, directory, path)
    return CommandResult(f"stopped review; status = {status}; ledger = {target}; Review synthesis required")


def get_status(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> LedgerStatus:
    path, state = _load(root, slug, directory)
    return LedgerStatus(path, state["frontmatter"], _question_map(state), state)


def _counts(state: dict) -> dict:
    return {"total": len(state["questions"]), **{
        status: sum(q["status"] == status for q in state["questions"]) for status in QUESTION_STATUSES
    }}


def status_summary(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR, proof: bool = False) -> dict:
    path, state = _load(root, slug, directory)
    summary = {
        **{key: state["frontmatter"][key] for key in ("status", "round", "next")},
        "counts": _counts(state),
        "files": {"source": str(path), "index": str(ledger_path(root, slug, directory)),
                  "review": str(review_path(root, slug, directory))},
        "format": "json" if path.suffix == ".json" else "legacy",
    }
    if proof:
        summary["stop_proof"] = state["stop_proof"]
    return summary


def _preview(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 120 else text[:119] + "…"


def list_questions(*, root: Path | str, slug: str, offset: int = 0, limit: int = 20,
                   status: str | None = None, branch: str | None = None, directory: str = DEFAULT_DIR) -> dict:
    if offset < 0 or limit <= 0:
        raise ValueError("offset must be nonnegative and limit must be positive")
    if status is not None and status not in QUESTION_STATUSES:
        raise ValueError(f"unknown question status: {status}")
    _, state = _load(root, slug, directory)
    selected = [q for q in state["questions"] if (status is None or q["status"] == status)
                and (branch is None or branch in q["branch"])]
    return {
        "total": len(selected), "offset": offset,
        "next_offset": offset + limit if offset + limit < len(selected) else None,
        "items": [{"id": q["id"], "branch": _preview(q["branch"]), "status": q["status"],
                   "preview": q.get("preview", _preview(q.get("question", "")))}
                  for q in selected[offset:offset + limit]],
    }


def get_questions(*, root: Path | str, slug: str, questions: list[str], history: bool = False,
                  directory: str = DEFAULT_DIR) -> list[dict]:
    if not questions:
        raise ValueError("at least one question ID is required")
    path, state = _load(root, slug, directory)
    cache = {}
    results = []
    for question_id in dict.fromkeys(questions):
        item = _resolve_question(state, _require_question(state, question_id), cache)
        if item["status"] == Q_STATUS_NEEDS_USER and "owner_question" not in item:
            item["owner_question"] = item["question"]
        if history:
            for revision in item.get("history", []):
                previous = revision["previous"]
                if revision["kind"] == "answer" and set(previous) == {"batch_id", "source_id"}:
                    original = _resolve_question(state, previous, cache)
                    revision["previous"] = {k: original[k] for k in ("answer", "evidence", "uncertainty", "needs_user")}
                    revision["previous"]["answer_author"] = "Answerer"
            archive = state.get("legacy_archive") or (str(path) if path.suffix == ".md" else None)
            if archive:
                item["legacy_archive"] = archive
        else:
            item.pop("history", None)
        results.append(item)
    return results


def _render_index(state: dict, slug: str) -> str:
    counts = _counts(state)
    pending = [q for q in state["questions"] if q["status"] != Q_STATUS_CONVERGED]
    lines = [
        f"# Grill Ledger：{state['frontmatter']['topic']}", "",
        f"- 状态：{state['frontmatter']['status']}",
        f"- 轮次：{state['frontmatter']['round']}；下一角色：{state['frontmatter']['next']}",
        "- 数量：" + "；".join(f"{k}={v}" for k, v in counts.items()),
        f"- 权威记录：grill-{slug}.ledger.json", "",
        "## 待处理索引（前 20 项）", "",
    ]
    for item in pending[:20]:
        preview = item.get("preview", _preview(item.get("question", "")))
        lines.append(f"- {item['id']} · {item['status']} · {_preview(item['branch'])}：{preview}")
    if not pending:
        lines.append("- 无。")
    lines.extend([
        "", "## 按需读取", "",
        f"python <skill>/scripts/grill_ledger.py status --slug {slug}",
        f"python <skill>/scripts/grill_ledger.py list-questions --slug {slug} --offset 0 --limit 20",
        f"python <skill>/scripts/grill_ledger.py get-question --slug {slug} --question Q1 Q2",
        "追加 --history 可查看指定问题的历史版本；list-questions 支持 --status 和 --branch 筛选。",
        "按命令返回的 next_offset 继续分页，直到为 null；权威 JSON 不作为默认上下文读取。",
        "",
    ])
    return "\n".join(lines)


def _write_index(root: Path | str, slug: str, state: dict, directory: str = DEFAULT_DIR) -> None:
    _atomic_write(ledger_path(root, slug, directory), _render_index(state, slug).encode("utf-8"))


def rebuild_index(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> CommandResult:
    path, state = _load(root, slug, directory)
    if path.suffix != ".json":
        raise ValueError("legacy ledger is unchanged; use status/list-questions/get-question or resume a mutation")
    _write_index(root, slug, state, directory)
    return CommandResult(f"rebuilt index at {ledger_path(root, slug, directory)}")


def read_markdown(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> str:
    path, state = _load(root, slug, directory)
    rendered = _render_index(state, slug)
    if path.suffix == ".md":
        rendered = rendered.replace(f"权威记录：grill-{slug}.ledger.json", f"旧版权威记录：{path}")
    return rendered


def read_review(*, root: Path | str, slug: str, directory: str = DEFAULT_DIR) -> str:
    return review_path(root, slug, directory).read_text(encoding="utf-8")


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
    status.add_argument("--proof", action="store_true")

    listing = sub.add_parser("list-questions")
    listing.add_argument("--slug", required=True)
    listing.add_argument("--offset", type=int, default=0)
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--status", choices=QUESTION_STATUSES)
    listing.add_argument("--branch")
    detail = sub.add_parser("get-question")
    detail.add_argument("--slug", required=True)
    detail.add_argument("--question", nargs="+", required=True)
    detail.add_argument("--history", action="store_true")
    rebuild = sub.add_parser("rebuild-index")
    rebuild.add_argument("--slug", required=True)

    batch_parser = sub.add_parser("import-round")
    batch_parser.add_argument("--slug", required=True)
    batch_parser.add_argument("--file", required=True)
    batch_parser.add_argument("--accept", nargs="*", default=[])

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
                json.dumps(status_summary(root=root, slug=args.slug, directory=args.dir, proof=args.proof), ensure_ascii=False, indent=2)
            )
        elif args.cmd == "list-questions":
            result = CommandResult(json.dumps(list_questions(root=root, slug=args.slug, offset=args.offset,
                limit=args.limit, status=args.status, branch=args.branch, directory=args.dir), ensure_ascii=False))
        elif args.cmd == "get-question":
            result = CommandResult(json.dumps(get_questions(root=root, slug=args.slug, questions=args.question,
                history=args.history, directory=args.dir), ensure_ascii=False, indent=2))
        elif args.cmd == "rebuild-index":
            result = rebuild_index(root=root, slug=args.slug, directory=args.dir)
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
        elif args.cmd == "import-round":
            result = import_round(root=root, slug=args.slug, file=args.file, accept=args.accept, directory=args.dir)
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
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
