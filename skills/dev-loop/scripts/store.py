"""Read and atomically update the small per-package dev-loop profile."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

PROFILE_NAME = "development-pipeline.json"


def profile_path(package: str | Path) -> tuple[Path, Path]:
    root = Path(package).expanduser().absolute()
    directory = root / ".impl-package"
    return directory, directory / PROFILE_NAME


def default_profile() -> dict:
    return {"version": 1, "routing": {}, "agents": [], "batches": []}


def _symlinked(root: Path, directory: Path, path: Path) -> bool:
    return any(item.is_symlink() for item in (root, directory, path))


def load_profile(package: str | Path) -> tuple[dict, str | None]:
    """Return defaults for a missing file; report damaged or unsafe files locally."""
    root = Path(package).expanduser().absolute()
    directory, path = profile_path(root)
    if _symlinked(root, directory, path):
        return default_profile(), "拒绝 symlink profile 路径"
    if not path.exists():
        return default_profile(), None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return default_profile(), f"development-pipeline.json undetermined：{error}"
    if not isinstance(value, dict) or value.get("version") != 1:
        return default_profile(), "development-pipeline.json undetermined：version/schema 无效"
    routing = value.get("routing", {})
    agents, batches = value.get("agents", []), value.get("batches", [])
    if (not isinstance(routing, dict) or not isinstance(agents, list) or not isinstance(batches, list)
            or any(not isinstance(role, str) or not isinstance(route, dict) for role, route in routing.items())):
        return default_profile(), "development-pipeline.json undetermined：routing/agents/batches 类型无效"
    return {**default_profile(), **value}, None


def save_profile(package: str | Path, profile: dict) -> None:
    """Write through a same-directory temporary file so replace stays atomic."""
    root = Path(package).expanduser().absolute()
    directory, path = profile_path(root)
    if _symlinked(root, directory, path):
        raise ValueError("拒绝 symlink profile 路径")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("写入期间 profile 路径变成 symlink")

    descriptor, temporary = tempfile.mkstemp(prefix="development-pipeline-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(profile, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if directory.is_symlink() or path.is_symlink():
            raise ValueError("写入期间 profile 路径变成 symlink")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
