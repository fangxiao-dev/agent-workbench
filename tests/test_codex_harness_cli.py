from __future__ import annotations

import queue
import unittest

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


if __name__ == "__main__":
    unittest.main()
