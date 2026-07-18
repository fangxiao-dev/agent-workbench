"""Canonical Impl-Package 3.2 grammar access for Harness adapters.

Adapters must consume the skill-owned configuration rather than carrying a
second, narrower copy of document regexes or artifact discovery rules.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import re
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any


@lru_cache(maxsize=1)
def _canonical_state_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "skills" / "impl-package" / "scripts" / "impl_package_state.py"
    spec = importlib.util.spec_from_file_location("codex_harness_canonical_impl_package_state", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical Impl-Package state engine: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_config() -> dict[str, Any]:
    config = getattr(_canonical_state_module(), "CONFIG", None)
    if not isinstance(config, dict):
        raise RuntimeError("canonical Impl-Package state engine did not expose CONFIG")
    return config


def composition_flags(text: str) -> tuple[bool, bool]:
    pattern = canonical_config()["documents"]["compositionPattern"]
    match = re.search(pattern, text, re.I)
    if match is None:
        raise ValueError("current plan has no parseable Composition declaration")
    return match.group(1).lower() == "true", match.group(2).lower() == "true"


def attempt_id(text: str) -> str | None:
    pattern = canonical_config()["documents"]["attemptPattern"]
    match = re.search(pattern, text)
    return match.group(1) if match else None


def ticket_id(text: str) -> str | None:
    pattern = canonical_config()["documents"]["ticketIdPattern"]
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def matches_artifact_pattern(relative_path: str, kind: str) -> bool:
    patterns = canonical_config()["documents"][kind]
    return any(fnmatch.fnmatchcase(relative_path, pattern) for pattern in patterns)


def task_blocks(text: str) -> list[tuple[str, str, str]]:
    documents = canonical_config()["documents"]
    heading = re.compile(documents["taskHeadingPattern"])
    matches = list(heading.finditer(text))
    if not matches:
        raise ValueError("DAG has no canonical task headings")
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title_end = text.find("\n", match.end())
        title = text[match.end() : title_end if title_end >= 0 else end].strip()
        blocks.append((match.group(1), title, text[match.end() : end]))
    return blocks


def task_block(text: str, task_id: str) -> str:
    pattern = canonical_config()["documents"]["taskBlockPattern"].format(task_id=re.escape(task_id))
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"DAG task block is missing: {task_id}")
    return match.group(0)
