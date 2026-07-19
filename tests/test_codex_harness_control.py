from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.codex_harness_control import CancelRequestError, cancel_request_path, clear_cancel_request, read_cancel_request, write_cancel_request


class CodexHarnessControlTest(unittest.TestCase):
    def test_cancel_request_path_is_a_state_sidecar(self) -> None:
        state_path = Path("run") / "control-state.json"
        self.assertEqual(cancel_request_path(state_path), Path("run") / "control-state.json.cancel-request.json")

    def test_atomic_write_roundtrips_without_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "nested" / "state.json"
            request = write_cancel_request(state_path, "run-1", "owner requested cancellation")
            self.assertEqual(read_cancel_request(state_path, "run-1"), request)
            self.assertEqual(request["schema_version"], "codex-crew.cancel-request.v0.1")
            self.assertEqual(list(state_path.parent.glob("*.tmp")), [])

    def test_duplicate_request_for_same_run_is_idempotent_while_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            first = write_cancel_request(state_path, "run-1", "first reason")
            second = write_cancel_request(state_path, "run-1", "a later duplicate", provenance="broker")
            self.assertEqual(second, first)
            self.assertEqual(read_cancel_request(state_path, "run-1"), first)

    def test_concurrent_requests_preserve_one_request_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            results: list[dict] = []

            def request_cancel() -> None:
                results.append(write_cancel_request(state_path, "run-1", "stop"))

            threads = [threading.Thread(target=request_cancel) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len({item["request_id"] for item in results}), 1)
            self.assertEqual(read_cancel_request(state_path, "run-1"), results[0])

    def test_malformed_and_mismatched_requests_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            sidecar = cancel_request_path(state_path)
            sidecar.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(CancelRequestError):
                read_cancel_request(state_path, "run-1")
            with self.assertRaises(CancelRequestError):
                write_cancel_request(state_path, "run-1", "do not overwrite malformed evidence")
            sidecar.write_text(json.dumps({
                "schema_version": "codex-crew.cancel-request.v0.1",
                "request_id": "request-1",
                "run_id": "another-run",
                "reason": "stop",
                "provenance": "owner",
                "requested_at": 1.0,
            }), encoding="utf-8")
            with self.assertRaises(CancelRequestError):
                read_cancel_request(state_path, "run-1")

    def test_clear_only_removes_the_matching_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            request = write_cancel_request(state_path, "run-1", "stop")
            self.assertFalse(clear_cancel_request(state_path, "different-request"))
            self.assertTrue(cancel_request_path(state_path).exists())
            self.assertTrue(clear_cancel_request(state_path, request["request_id"]))
            self.assertFalse(cancel_request_path(state_path).exists())
            self.assertFalse(clear_cancel_request(state_path, request["request_id"]))

    def test_unlocked_persistent_lock_file_is_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            sidecar = cancel_request_path(state_path)
            lock_path = sidecar.with_name(f"{sidecar.name}.lock")
            lock_path.write_text(json.dumps({"pid": 2147483647, "process_token": "dead-owner", "created_at": 1.0}), encoding="utf-8")
            request = write_cancel_request(state_path, "run-1", "stop", lock_timeout_seconds=0.1)
            self.assertEqual(read_cancel_request(state_path, "run-1"), request)
            self.assertTrue(lock_path.exists())

    def test_live_cross_process_lock_contention_does_not_terminate_holder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            child_code = """
import sys, time
from pathlib import Path
from scripts.codex_harness_control import _cancel_request_lock, cancel_request_path
with _cancel_request_lock(cancel_request_path(Path(sys.argv[1])), timeout_seconds=1):
    print('ready', flush=True)
    time.sleep(1)
"""
            child = subprocess.Popen([sys.executable, "-c", child_code, str(state_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                assert child.stdout is not None
                self.assertEqual(child.stdout.readline().strip(), "ready")
                with self.assertRaisesRegex(CancelRequestError, "lock is busy"):
                    write_cancel_request(state_path, "run-1", "stop", lock_timeout_seconds=0.05)
                self.assertIsNone(child.poll(), "lock contention must not terminate the live holder")
            finally:
                child.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
