"""State-file storage and small state helpers for kickoff."""

import json
import os
import tempfile
from datetime import datetime, timezone

STATE_FILENAME = "kickoff-state.json"
DEFAULT_STAGING_DIR = os.path.join(".", "output", "kickoff")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state(path):
    if not path or not os.path.isfile(path):
        raise ValueError(f"状态文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def save_state(path, state):
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}-", suffix=".tmp", dir=parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def add_history(state, action, **extra):
    entry = {"action": action, "ts": now()}
    entry.update(extra)
    state.setdefault("history", []).append(entry)


def resolve_state_path(args):
    pkg = getattr(args, "pkg", None)
    state = getattr(args, "state", None)
    if pkg and state:
        raise ValueError("--pkg 与 --state 只能选其一")
    if not pkg and not state:
        raise ValueError("必须提供 --pkg <dir> 或 --state <path>")
    if pkg:
        return os.path.join(pkg, STATE_FILENAME)
    return state


def rounds_for(state, stage):
    return [round_ for round_ in state.get("rounds", []) if round_.get("stage") == stage]
