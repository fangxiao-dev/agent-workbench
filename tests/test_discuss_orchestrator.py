from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "discuss-ledger" / "scripts" / "discuss_orchestrator.py"
SRC = ROOT / "skills" / "discuss-ledger" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_orchestrator():
    spec = importlib.util.spec_from_file_location("discuss_orchestrator_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fake_orchestrator_runs_round_robin_without_real_agent_clis(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()

    exit_code = orchestrator.main(
        [
            "--root",
            str(tmp_path),
            "--topic",
            "MCP orchestration smoke",
            "--slug",
            "mcp-smoke",
            "--agents",
            "codex,claude",
            "--max-rounds",
            "2",
            "--fake",
        ]
    )

    assert exit_code == 0

    ledger_path = tmp_path / "docs" / "exchange" / "discuss" / "discuss-mcp-smoke.md"
    text = ledger_path.read_text(encoding="utf-8")
    assert "participants: [codex, claude]" in text
    assert "next: claude" in text or "next: codex" in text or "next: —" in text
    assert "Fake codex opening concern" in text
    assert "Fake claude convergence" in text


def test_agent_result_schema_accepts_orchestrator_payload_shape() -> None:
    schema_path = ROOT / "skills" / "discuss-ledger" / "schemas" / "agent-result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert {"convergences", "contests", "new_points"}.issubset(schema["properties"])


def test_orchestrator_parser_defaults_match_interactive_use() -> None:
    orchestrator = load_orchestrator()

    args = orchestrator.build_parser().parse_args(["--topic", "docs/plan.md"])

    assert args.agents == "codex,claude"
    assert args.max_rounds == 5
    assert args.timeout_s == 300


def test_resolve_root_and_topic_detects_any_git_worktree_shape(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    project = tmp_path / "some-container" / "feature-checkout"
    target = project / "docs" / "impl-plans" / "plan.md"
    (project / ".git").mkdir(parents=True)
    target.parent.mkdir(parents=True)
    target.write_text("# Plan\n", encoding="utf-8")

    root, topic = orchestrator.resolve_root_and_topic(str(tmp_path), str(target))

    assert root == project.resolve()
    assert topic == "docs/impl-plans/plan.md"


def test_resolve_root_and_topic_detects_dot_worktrees_relative_paths(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    project = tmp_path / ".worktrees" / "raw-material-production-design"
    target = project / "docs" / "impl-plans" / "patch.md"
    (project / ".git").mkdir(parents=True)
    target.parent.mkdir(parents=True)
    target.write_text("# Patch\n", encoding="utf-8")

    root, topic = orchestrator.resolve_root_and_topic(str(tmp_path), ".worktrees/raw-material-production-design/docs/impl-plans/patch.md")

    assert root == project.resolve()
    assert topic == "docs/impl-plans/patch.md"


def test_parse_codex_jsonl_extracts_nested_final_result() -> None:
    orchestrator = load_orchestrator()
    final = {
        "convergences": [],
        "contests": [],
        "new_points": [{"summary": "S", "body": "B"}],
    }
    stream = "\n".join(
        [
            json.dumps({"type": "turn_started"}),
            json.dumps({"type": "message", "payload": {"content": json.dumps(final)}}),
        ]
    )

    assert orchestrator.parse_codex_jsonl(stream) == final


def test_extract_agent_result_accepts_claude_wrapper_with_fenced_result() -> None:
    orchestrator = load_orchestrator()
    final = {
        "convergences": [],
        "contests": [],
        "new_points": [{"summary": "S", "body": "B"}],
    }
    claude_output = {
        "type": "result",
        "subtype": "success",
        "result": "```json\n" + json.dumps(final) + "\n```",
    }

    assert orchestrator.extract_agent_result(claude_output) == final


def test_extract_agent_result_skips_non_result_json_before_fenced_result() -> None:
    orchestrator = load_orchestrator()
    final = {
        "convergences": [{"point": "D1", "marker": "一致", "line": "已收敛"}],
        "contests": [],
        "new_points": [],
    }
    mixed_text = (
        "Schema example:\n"
        "```json\n{\"type\":\"object\",\"properties\":{}}\n```\n\n"
        "Actual result:\n"
        "```json\n"
        + json.dumps(final, ensure_ascii=False)
        + "\n```"
    )

    assert orchestrator.extract_agent_result({"result": mixed_text}) == final


def test_normalize_result_rejects_missing_required_shape() -> None:
    orchestrator = load_orchestrator()

    try:
        orchestrator.normalize_result({"convergences": [], "contests": []})
    except orchestrator.AdapterError as exc:
        assert exc.code == "INVALID_JSON"
        assert "missing top-level keys" in exc.message
    else:
        raise AssertionError("expected AdapterError")


def test_run_claude_uses_target_root_for_process(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del timeout_s
        calls.append((command, stdin, cwd))

        class Completed:
            returncode = 0
            stdout = json.dumps({"convergences": [], "contests": [], "new_points": []})
            stderr = ""

        return Completed()

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    assert orchestrator.run_claude("prompt", tmp_path, 10) == {
        "convergences": [],
        "contests": [],
        "new_points": [],
    }
    command, stdin, cwd = calls[0]
    assert command[:9] == [
        "claude",
        "-p",
        "--no-session-persistence",
        "--effort",
        "low",
        "--disable-slash-commands",
        "--tools",
        "",
        "--system-prompt",
    ]
    assert command[10] == "--output-format"
    assert command[11] == "json"
    assert "prompt" not in command
    assert stdin == "prompt"
    assert cwd == tmp_path


def test_run_claude_repairs_invalid_inner_result_without_wrapper_noise(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []
    invalid_inner_result = (
        '```json\n'
        '{"convergences":[],"contests":[{"point":"D1","body":"Task says "quoted" text","movement":true}],"new_points":[]}'
        '\n```'
    )
    repaired = {
        "convergences": [],
        "contests": [{"point": "D1", "body": 'Task says "quoted" text', "movement": True}],
        "new_points": [],
    }

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del command, timeout_s, cwd
        calls.append(stdin)

        class Completed:
            returncode = 0
            stderr = ""

        completed = Completed()
        if len(calls) == 1:
            completed.stdout = json.dumps(
                {
                    "type": "result",
                    "result": invalid_inner_result,
                    "usage": {"input_tokens": 1},
                }
            )
        else:
            completed.stdout = json.dumps({"type": "result", "result": json.dumps(repaired)})
        return completed

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    assert orchestrator.run_claude("prompt", tmp_path, 10) == repaired
    assert len(calls) == 2
    assert "Invalid Claude result text:" in calls[1]
    assert invalid_inner_result in calls[1]
    assert '"usage"' not in calls[1]


def test_run_codex_sets_fast_service_tier_on_success(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del stdin, timeout_s, cwd
        calls.append(command)

        class Completed:
            returncode = 0
            stdout = json.dumps({"convergences": [], "contests": [], "new_points": []})
            stderr = ""

        return Completed()

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    assert orchestrator.run_codex("prompt", tmp_path, 10) == {
        "convergences": [],
        "contests": [],
        "new_points": [],
    }

    assert len(calls) == 1
    assert "--ignore-user-config" not in calls[0]
    config_index = calls[0].index("-c")
    assert calls[0][config_index + 1] == 'service_tier="fast"'


def test_run_codex_retries_with_ignore_user_config_for_service_tier_config_error(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del stdin, timeout_s, cwd
        calls.append(command)

        class Completed:
            stdout = ""
            stderr = ""

        completed = Completed()
        if len(calls) == 1:
            completed.returncode = 1
            completed.stderr = "Error loading config.toml: unknown variant `priority`, expected `fast` or `flex` in `service_tier`"
        else:
            completed.returncode = 0
            completed.stdout = json.dumps({"convergences": [], "contests": [], "new_points": []})
        return completed

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    assert orchestrator.run_codex("prompt", tmp_path, 10) == {
        "convergences": [],
        "contests": [],
        "new_points": [],
    }

    assert len(calls) == 2
    assert "--ignore-user-config" not in calls[0]
    assert "--ignore-user-config" in calls[1]
    for command in calls:
        config_index = command.index("-c")
        assert command[config_index + 1] == 'service_tier="fast"'


def test_run_codex_does_not_retry_non_config_failures(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del stdin, timeout_s, cwd
        calls.append(command)

        class Completed:
            returncode = 1
            stdout = ""
            stderr = "model overloaded"

        return Completed()

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    try:
        orchestrator.run_codex("prompt", tmp_path, 10)
    except orchestrator.AdapterError as exc:
        assert exc.code == "AGENT_FAILED"
    else:
        raise AssertionError("expected AdapterError")

    assert len(calls) == 1


def test_eval_happy_path_codex_opens_claude_converges_without_retry(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []

    class Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del timeout_s
        calls.append((command, stdin, cwd))
        assert cwd == tmp_path
        assert "Your previous response was invalid" not in stdin
        if command[0] == "codex":
            config_index = command.index("-c")
            assert command[config_index + 1] == 'service_tier="fast"'
            assert "--ignore-user-config" not in command
            return Completed(
                0,
                json.dumps(
                    {
                        "convergences": [],
                        "contests": [],
                        "new_points": [
                            {
                                "summary": "Codex opened the review topic",
                                "body": "The happy path starts with Codex creating one tracked point.",
                            }
                        ],
                    }
                ),
            )
        if command[0] == "claude":
            assert "Current legal open point IDs for convergences/contests: D1" in stdin
            return Completed(
                0,
                json.dumps(
                    {
                        "convergences": [
                            {
                                "point": "D1",
                                "marker": "一致",
                                "line": "Claude agrees with the opening point.",
                            }
                        ],
                        "contests": [],
                        "new_points": [],
                    }
                ),
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    exit_code = orchestrator.orchestrate(
        root=tmp_path,
        topic="Happy path eval",
        slug="happy-path-eval",
        agents=["codex", "claude"],
        max_rounds=2,
        fake=False,
        timeout_s=300,
    )

    assert exit_code == 0
    assert [command[0] for command, _, _ in calls] == ["codex", "claude"]
    assert all("--ignore-user-config" not in command for command, _, _ in calls)

    status = orchestrator.ledger.get_status(root=tmp_path, slug="happy-path-eval")
    assert status.frontmatter["status"] == orchestrator.ledger.STATUS_AGREED
    assert status.frontmatter["next"] == "—"
    text = (tmp_path / "docs" / "exchange" / "discuss" / "discuss-happy-path-eval.md").read_text(encoding="utf-8")
    assert "participants: [codex, claude]" in text
    assert "Codex opened the review topic" in text
    assert "[一致] Claude agrees with the opening point." in text


def test_eval_codex_config_fallback_empty_ledger_correction_reaches_agreement(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []
    codex_retry_payloads = [
        {
            "convergences": [{"point": "D01", "marker": "一致", "line": "invalid empty-ledger reference"}],
            "contests": [],
            "new_points": [],
        },
        {
            "convergences": [],
            "contests": [],
            "new_points": [
                {
                    "summary": "Codex correction opened the real issue",
                    "body": "Codex recovered from the empty-ledger correction prompt with a tracked point.",
                }
            ],
        },
    ]

    class Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del timeout_s
        calls.append((command, stdin, cwd))
        if command[0] == "codex":
            assert cwd == tmp_path
            config_index = command.index("-c")
            assert command[config_index + 1] == 'service_tier="fast"'
            if "--ignore-user-config" not in command:
                return Completed(
                    1,
                    stderr="Error loading config.toml: unknown variant `priority`, expected `fast` or `flex` in `service_tier`",
                )
            return Completed(0, json.dumps(codex_retry_payloads.pop(0)))
        if command[0] == "claude":
            assert cwd == tmp_path
            assert "Current legal open point IDs for convergences/contests: D1" in stdin
            return Completed(
                0,
                json.dumps(
                    {
                        "convergences": [
                            {
                                "point": "D1",
                                "marker": "一致",
                                "line": "Claude agrees after stateful handoff.",
                            }
                        ],
                        "contests": [],
                        "new_points": [],
                    }
                ),
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    exit_code = orchestrator.orchestrate(
        root=tmp_path,
        topic="Smooth flow eval",
        slug="smooth-flow-eval",
        agents=["codex", "claude"],
        max_rounds=2,
        fake=False,
        timeout_s=300,
    )

    assert exit_code == 0
    assert not codex_retry_payloads
    codex_calls = [command for command, _, _ in calls if command[0] == "codex"]
    assert len(codex_calls) == 4
    assert "--ignore-user-config" not in codex_calls[0]
    assert "--ignore-user-config" in codex_calls[1]
    assert "--ignore-user-config" not in codex_calls[2]
    assert "--ignore-user-config" in codex_calls[3]
    assert any("Your previous response was invalid" in (stdin or "") for command, stdin, _ in calls if command[0] == "codex")

    status = orchestrator.ledger.get_status(root=tmp_path, slug="smooth-flow-eval")
    assert status.frontmatter["status"] == orchestrator.ledger.STATUS_AGREED
    assert status.frontmatter["next"] == "—"
    text = (tmp_path / "docs" / "exchange" / "discuss" / "discuss-smooth-flow-eval.md").read_text(encoding="utf-8")
    assert "participants: [codex, claude]" in text
    assert "Codex correction opened the real issue" in text
    assert "[一致] Claude agrees after stateful handoff." in text
    assert "D01" not in text


def test_empty_ledger_invalid_point_references_retry_as_new_points(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    payloads = [
        {
            "convergences": [{"point": "D01", "marker": "一致", "line": "不存在的点"}],
            "contests": [],
            "new_points": [],
        },
        {
            "convergences": [],
            "contests": [],
            "new_points": [{"summary": "新议题", "body": "空 ledger 应通过 new_points 发起讨论。"}],
        },
    ]
    prompts = []

    def fake_call_agent(agent, prompt, root, status, fake, timeout_s):
        del agent, root, status, fake, timeout_s
        prompts.append(prompt)
        return payloads.pop(0)

    monkeypatch.setattr(orchestrator, "call_agent", fake_call_agent)

    exit_code = orchestrator.orchestrate(
        root=tmp_path,
        topic="Empty ledger review",
        slug="empty-ledger-review",
        agents=["claude"],
        max_rounds=1,
        fake=False,
        timeout_s=10,
    )

    assert exit_code == 0
    assert len(prompts) == 2
    assert "Current legal open point IDs: (none)" in prompts[1]
    text = (tmp_path / "docs" / "exchange" / "discuss" / "discuss-empty-ledger-review.md").read_text(encoding="utf-8")
    assert "| D1 | 新议题 | 分歧 | 1 |" in text
    assert "D01" not in text


def test_invalid_point_reference_after_retry_leaves_ledger_without_points(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()

    def fake_call_agent(agent, prompt, root, status, fake, timeout_s):
        del agent, prompt, root, status, fake, timeout_s
        return {
            "convergences": [],
            "contests": [{"point": "D01", "body": "不存在的点", "movement": True}],
            "new_points": [],
        }

    monkeypatch.setattr(orchestrator, "call_agent", fake_call_agent)

    try:
        orchestrator.orchestrate(
            root=tmp_path,
            topic="Invalid retry",
            slug="invalid-retry",
            agents=["claude"],
            max_rounds=1,
            fake=False,
            timeout_s=10,
        )
    except orchestrator.AdapterError as exc:
        assert exc.code == "INVALID_TURN"
    else:
        raise AssertionError("expected AdapterError")

    text = (tmp_path / "docs" / "exchange" / "discuss" / "discuss-invalid-retry.md").read_text(encoding="utf-8")
    assert "| D1 |" not in text
    assert "不存在的点" not in text


def test_validate_turn_allows_only_current_open_point_ids(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    orchestrator.ledger.init_ledger(root=tmp_path, topic="State machine", slug="state-machine", initiator="codex")
    orchestrator.ledger.add_point(root=tmp_path, slug="state-machine", author="codex", summary="Open point", body="Open body")
    status = orchestrator.ledger.get_status(root=tmp_path, slug="state-machine")

    orchestrator.validate_turn_against_ledger(
        status,
        {
            "convergences": [],
            "contests": [{"point": "D1", "body": "valid", "movement": True}],
            "new_points": [],
        },
    )

    try:
        orchestrator.validate_turn_against_ledger(
            status,
            {
                "convergences": [],
                "contests": [{"point": "D2", "body": "invalid", "movement": True}],
                "new_points": [],
            },
        )
    except orchestrator.AdapterError as exc:
        assert exc.code == "INVALID_TURN"
        assert "D2" in exc.message
    else:
        raise AssertionError("expected AdapterError")

    orchestrator.ledger.converge_point(root=tmp_path, slug="state-machine", point="D1", marker="一致", line="closed")
    status = orchestrator.ledger.get_status(root=tmp_path, slug="state-machine")
    try:
        orchestrator.validate_turn_against_ledger(
            status,
            {
                "convergences": [],
                "contests": [{"point": "D1", "body": "closed", "movement": True}],
                "new_points": [],
            },
        )
    except orchestrator.AdapterError as exc:
        assert exc.code == "INVALID_TURN"
    else:
        raise AssertionError("expected AdapterError")


def test_run_process_wraps_windows_powershell_shims(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    calls = []

    monkeypatch.setattr(orchestrator.shutil, "which", lambda exe: f"C:/tools/{exe}.ps1")

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))
            self.pid = 123
            self.returncode = 0

        def communicate(self, input=None, timeout=None):
            del input, timeout
            return "", ""

    monkeypatch.setattr(orchestrator.subprocess, "Popen", FakePopen)

    orchestrator.run_process(["codex", "--version"])

    assert calls[0][0][:5] == [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
    ]
    assert calls[0][0][5:] == ["C:/tools/codex.ps1", "--version"]


def test_run_process_wraps_windows_cmd_shims(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    calls = []

    monkeypatch.setattr(orchestrator.shutil, "which", lambda exe: f"C:/tools/{exe}.CMD")

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))
            self.pid = 123
            self.returncode = 0

        def communicate(self, input=None, timeout=None):
            del input, timeout
            return "", ""

    monkeypatch.setattr(orchestrator.subprocess, "Popen", FakePopen)

    orchestrator.run_process(["claude", "--version"])

    assert calls[0][0] == ["cmd", "/c", "C:/tools/claude.CMD", "--version"]


def test_run_process_starts_new_session_on_posix(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    calls = []

    monkeypatch.setattr(orchestrator.os, "name", "posix")
    monkeypatch.setattr(orchestrator.shutil, "which", lambda exe: f"/usr/local/bin/{exe}")

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))
            self.pid = 123
            self.returncode = 0

        def communicate(self, input=None, timeout=None):
            del input, timeout
            return "", ""

    monkeypatch.setattr(orchestrator.subprocess, "Popen", FakePopen)

    orchestrator.run_process(["codex", "--version"])

    assert calls[0][0] == ["codex", "--version"]
    assert calls[0][1]["start_new_session"] is True


def test_timeout_kills_posix_process_group(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    killed = []

    monkeypatch.setattr(orchestrator.os, "name", "posix")
    monkeypatch.setattr(orchestrator.os, "killpg", lambda pid, sig: killed.append((pid, sig)), raising=False)

    orchestrator.terminate_process_tree(123)

    assert killed == [(123, orchestrator.signal.SIGTERM)]
