from __future__ import annotations

import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_harness_agent import RoleTurnError, run_role_turn
from scripts.codex_harness_cli import TurnControlRequested
from scripts.codex_harness_control import cancel_request_path, write_cancel_request


class _AliveProcess:
    returncode = None

    @staticmethod
    def poll() -> None:
        return None


class _FakeSession:
    def __init__(self, command: list[str], stderr_path: Path) -> None:
        self.command = command
        self.stderr_path = stderr_path
        self.process = _AliveProcess()
        self.messages: queue.Queue[dict] = queue.Queue()
        self.calls: list[tuple[str, dict, float]] = []
        self.collect_calls: list[dict] = []
        self.cancel_request: dict | None = None
        self.confirm_interrupt = True
        self.thread_read_hook = None

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def request(self, request_id: int, method: str, params: dict, timeout: float) -> tuple[dict, list[dict]]:
        self.calls.append((method, params, timeout))
        if method == "initialize":
            return {}, []
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}}, []
        if method == "thread/resume":
            return {}, []
        if method == "turn/start":
            return {"turn": {"id": "turn-1"}}, []
        if method == "turn/interrupt":
            return {"acknowledged": True}, []
        if method == "thread/read":
            if self.thread_read_hook is not None:
                self.thread_read_hook()
            return {"thread": {"id": "thread-1"}}, []
        raise AssertionError(f"unexpected method {method}")

    def collect_until_turn_complete(self, thread_id: str, timeout: float | None = None, **kwargs: object) -> list[dict]:
        self.collect_calls.append({"thread_id": thread_id, "timeout": timeout, **kwargs})
        if self.cancel_request is not None and len(self.collect_calls) == 1:
            raise TurnControlRequested(self.cancel_request)
        if timeout == 30 and not self.confirm_interrupt:
            raise TimeoutError("no terminal")
        status = "interrupted" if timeout == 30 else "completed"
        return [{"method": "turn/completed", "params": {"threadId": thread_id, "turn": {"id": "turn-1", "status": status}}}]


class _Factory:
    def __init__(self) -> None:
        self.session: _FakeSession | None = None

    def __call__(self, command: list[str], stderr_path: Path) -> _FakeSession:
        self.session = _FakeSession(command, stderr_path)
        return self.session


class CodexHarnessAgentTest(unittest.TestCase):
    def _run(self, state_path: Path, factory: _Factory, **overrides: object) -> dict:
        arguments = {
            "state_path": state_path,
            "run_id": "run-1",
            "role": "worker",
            "cwd": state_path.parent,
            "prompt": "complete the bounded assignment",
            "execution": {"model": "gpt-5.6-terra", "reasoning_effort": "high"},
            "stderr_path": state_path.parent / "role.stderr.log",
            "sandbox": "workspace-write",
            "session_factory": factory,
        }
        arguments.update(overrides)
        with patch("scripts.codex_harness_agent.app_server_command", return_value=["codex", "app-server"]):
            return run_role_turn(**arguments)

    def test_normal_turn_has_no_duration_timeout_and_persists_ids_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            factory = _Factory()
            persisted: list[tuple[str, ...]] = []
            result = self._run(
                Path(temporary) / "state.json",
                factory,
                on_thread_started=lambda thread_id: persisted.append(("thread", thread_id)),
                on_turn_started=lambda thread_id, turn_id: persisted.append(("turn", thread_id, turn_id)),
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(persisted, [("thread", "thread-1"), ("turn", "thread-1", "turn-1")])
            assert factory.session is not None
            self.assertIsNone(factory.session.collect_calls[0]["timeout"])
            self.assertEqual(factory.session.collect_calls[0]["expected_turn_id"], "turn-1")
            self.assertEqual(factory.session.collect_calls[0]["control_poll_interval_seconds"], 1.0)
            self.assertTrue(callable(factory.session.collect_calls[0]["on_control_poll"]))
            self.assertNotIn("turn/interrupt", [method for method, _, _ in factory.session.calls])

    def test_workspace_write_turn_forwards_only_explicit_writable_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            factory = _Factory()
            metadata_root = Path(temporary) / "git-metadata"
            metadata_root.mkdir()
            self._run(Path(temporary) / "state.json", factory, writable_roots=[metadata_root])
            assert factory.session is not None
            turn_start = next(params for method, params, _ in factory.session.calls if method == "turn/start")
            self.assertEqual(turn_start["sandboxPolicy"], {"type": "workspaceWrite", "writableRoots": [str(metadata_root.resolve())], "networkAccess": False})

    def test_read_only_turn_rejects_writable_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(RoleTurnError):
                self._run(Path(temporary) / "state.json", _Factory(), role="verifier", sandbox="read-only", enable_multi_agent=False, writable_roots=[Path(temporary)])

    def test_cancel_after_terminal_discards_role_result_without_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            factory = _Factory()
            cancelling: list[dict] = []

            def create_session(command: list[str], stderr_path: Path) -> _FakeSession:
                session = factory(command, stderr_path)
                session.thread_read_hook = lambda: write_cancel_request(state_path, "run-1", "stop before result application")
                return session

            with patch("scripts.codex_harness_agent.app_server_command", return_value=["codex"]):
                result = run_role_turn(
                    state_path=state_path,
                    run_id="run-1",
                    role="worker",
                    cwd=Path(temporary),
                    prompt="work",
                    execution={"model": "gpt-5.6-terra", "reasoning_effort": "high"},
                    stderr_path=Path(temporary) / "stderr.log",
                    sandbox="workspace-write",
                    on_cancelling=cancelling.append,
                    session_factory=create_session,
                )

            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(result["terminal"]["status"], "completed")
            self.assertFalse(result["interrupt"]["attempted"])
            self.assertEqual(cancelling, [result["cancel_request"]])
            assert factory.session is not None
            self.assertNotIn("turn/interrupt", [method for method, _, _ in factory.session.calls])

    def test_fresh_read_only_verifier_disables_multi_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            factory = _Factory()
            with patch("scripts.codex_harness_agent.app_server_command", return_value=["verifier-command"]) as command:
                result = run_role_turn(
                    state_path=Path(temporary) / "state.json",
                    run_id="run-1",
                    role="verifier",
                    cwd=Path(temporary),
                    prompt="verify base to head",
                    execution={"model": "gpt-5.6-sol", "reasoning_effort": "high"},
                    stderr_path=Path(temporary) / "verifier.stderr.log",
                    sandbox="read-only",
                    enable_multi_agent=False,
                    session_factory=factory,
                )
            command.assert_called_once_with(enable_multi_agent=False, approval_policy="never")
            self.assertEqual(result["thread_id"], "thread-1")
            assert factory.session is not None
            thread_start = next(params for method, params, _ in factory.session.calls if method == "thread/start")
            turn_start = next(params for method, params, _ in factory.session.calls if method == "turn/start")
            thread_read = next(params for method, params, _ in factory.session.calls if method == "thread/read")
            self.assertEqual(thread_start["sandbox"], "read-only")
            self.assertEqual(turn_start["sandboxPolicy"], {"type": "readOnly", "networkAccess": False})
            self.assertEqual(thread_read, {"threadId": "thread-1"})

    def test_verifier_rejects_resume_write_or_multi_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            for overrides in ({"thread_id": "existing"}, {"sandbox": "workspace-write"}, {"enable_multi_agent": True}):
                with self.subTest(overrides=overrides), self.assertRaises(RoleTurnError):
                    verifier = {"role": "verifier", "sandbox": "read-only", "enable_multi_agent": False, **overrides}
                    self._run(state_path, _Factory(), **verifier)

    def test_cancel_before_turn_start_returns_confirmed_without_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            request = write_cancel_request(state_path, "run-1", "stop before starting")
            factory = _Factory()
            cancelling: list[dict] = []
            result = self._run(state_path, factory, on_cancelling=cancelling.append)
            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(result["cancel_request"], request)
            self.assertEqual(cancelling, [request])
            assert factory.session is not None
            self.assertNotIn("turn/start", [method for method, _, _ in factory.session.calls])
            self.assertNotIn("turn/interrupt", [method for method, _, _ in factory.session.calls])

    def test_collect_cancel_interrupts_same_turn_and_requires_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            request = write_cancel_request(state_path, "run-1", "stop active turn")
            cancel_request_path(state_path).unlink()
            factory = _Factory()

            def create_session(command: list[str], stderr_path: Path) -> _FakeSession:
                session = factory(command, stderr_path)
                session.cancel_request = request
                return session

            with patch("scripts.codex_harness_agent.app_server_command", return_value=["codex"]):
                result = run_role_turn(
                    state_path=state_path,
                    run_id="run-1",
                    role="worker",
                    cwd=Path(temporary),
                    prompt="work",
                    execution={"model": "gpt-5.6-terra", "reasoning_effort": "high"},
                    stderr_path=Path(temporary) / "stderr.log",
                    sandbox="workspace-write",
                    session_factory=create_session,
                )
            self.assertEqual(result["status"], "cancelled")
            self.assertTrue(result["interrupt"]["acknowledged"])
            self.assertEqual(result["terminal"]["status"], "interrupted")
            assert factory.session is not None
            interrupt = next(params for method, params, _ in factory.session.calls if method == "turn/interrupt")
            self.assertEqual(interrupt, {"threadId": "thread-1", "turnId": "turn-1"})
            self.assertEqual(factory.session.collect_calls[-1]["timeout"], 30)

    def test_interrupt_ack_without_terminal_returns_quarantine_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            request = write_cancel_request(state_path, "run-1", "stop active turn")
            cancel_request_path(state_path).unlink()
            factory = _Factory()

            def create_session(command: list[str], stderr_path: Path) -> _FakeSession:
                session = factory(command, stderr_path)
                session.cancel_request = request
                session.confirm_interrupt = False
                return session

            with patch("scripts.codex_harness_agent.app_server_command", return_value=["codex"]):
                result = run_role_turn(
                    state_path=state_path,
                    run_id="run-1",
                    role="worker",
                    cwd=Path(temporary),
                    prompt="work",
                    execution={"model": "gpt-5.6-terra", "reasoning_effort": "high"},
                    stderr_path=Path(temporary) / "stderr.log",
                    sandbox="workspace-write",
                    session_factory=create_session,
                )
            self.assertEqual(result["status"], "quarantined")
            self.assertTrue(result["interrupt"]["acknowledged"])
            self.assertFalse(result["terminal"]["observed"])
            self.assertEqual(result["quarantine"]["reason"], "turn_stop_unconfirmed")


if __name__ == "__main__":
    unittest.main()
