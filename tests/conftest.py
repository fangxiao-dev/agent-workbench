from __future__ import annotations

import atexit
import os
import shutil
import tempfile


os.environ["IMPL_PACKAGE_NO_SITUATION"] = "1"

# CLI runs append to <tempdir>/impl-package/usage.jsonl; keep test runs out of the real temp directory.
# pytest's own basetemp stays where it was (short paths matter on Windows).
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", tempfile.gettempdir())
_TEST_TEMP = tempfile.mkdtemp(prefix="ipt")
for _name in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_name] = _TEST_TEMP
tempfile.tempdir = _TEST_TEMP
atexit.register(shutil.rmtree, _TEST_TEMP, ignore_errors=True)
