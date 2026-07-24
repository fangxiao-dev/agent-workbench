"""Load optional repository-local executor overrides without dependencies."""

from __future__ import annotations

import os
from pathlib import Path


def load_executor_env(repository_root: Path) -> None:
    """Load ``.env`` values only when the process environment did not set them."""

    path = repository_root / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
