from __future__ import annotations

import atexit
import os
import shutil
import tempfile


os.environ["IMPL_PACKAGE_NO_SITUATION"] = "1"

# CLI runs append to <tempdir>/impl-package/usage.jsonl; keep test runs out of the real temp directory.
_TEST_TEMP = tempfile.mkdtemp(prefix="impl-package-tests-")
for _name in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_name] = _TEST_TEMP
tempfile.tempdir = _TEST_TEMP
atexit.register(shutil.rmtree, _TEST_TEMP, ignore_errors=True)
