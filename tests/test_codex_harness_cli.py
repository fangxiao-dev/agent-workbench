from __future__ import annotations

import io
import queue
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.codex_harness_cli import JsonRpcSession, TurnControlRequested


class _AliveProcess:
    returncode = None

    @staticmethod
    def poll() -> None:
        return None


class CodexHarnessCliTest(unittest.TestCase):
    def test_explicit_control_request_yields_without_interrupting_transport(self) -> None:
        session = object.__new__(JsonRpcSession)
        session.process = _AliveProcess()
        session.messages = queue.Queue()
        request = {"request_id": "cancel-1", "run_id": "run-1"}

        with self.assertRaises(TurnControlRequested) as raised:
            session.collect_until_turn_complete(
                "thread-1",
                None,
                control_poll_interval_seconds=0.001,
                on_control_poll=lambda: request,
            )

        self.assertEqual(raised.exception.request, request)

    def test_session_closes_parent_stderr_handle(self) -> None:
        class Process:
            returncode = 0
            stdin = io.StringIO()
            stdout = io.StringIO()

            @staticmethod
            def poll() -> int:
                return 0

        with TemporaryDirectory() as directory, patch("scripts.codex_harness_cli.subprocess.Popen", return_value=Process()):
            session = JsonRpcSession(["codex"], Path(directory) / "stderr.log")
            session.close()
            self.assertTrue(session._stderr_file.closed)


if __name__ == "__main__":
    unittest.main()
