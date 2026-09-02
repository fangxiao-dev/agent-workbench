from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


PLUGIN_SERVER = (
    Path(__file__).resolve().parents[2]
    / "plugin-marketplace"
    / "plugins"
    / "impl-package"
    / "scripts"
    / "codex_progress_dashboard"
    / "server.py"
)
spec = importlib.util.spec_from_file_location("impl_package_progress_dashboard", PLUGIN_SERVER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load progress dashboard: {PLUGIN_SERVER}")
implementation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = implementation
spec.loader.exec_module(implementation)

for name in dir(implementation):
    if not name.startswith("__"):
        globals()[name] = getattr(implementation, name)


if __name__ == "__main__":
    implementation.main()
