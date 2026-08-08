from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


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
    assert orchestrator.main(["--root", str(tmp_path), "--topic", "Smoke", "--slug", "smoke", "--fake", "--max-rounds", "2"]) == 0
    text = (tmp_path / "docs" / "exchange" / "discuss" / "discuss-smoke.md").read_text(encoding="utf-8")
    assert "Fake codex opening concern" in text
    assert "Fake claude convergence" in text


def test_parser_defaults_and_root_resolution(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    args = orchestrator.build_parser().parse_args(["--topic", "docs/plan.md"])
    assert (args.agents, args.max_rounds, args.timeout_s, args.claude_effort) == ("codex,claude", 5, 300, "low")
    assert orchestrator.parse_agents("codex, claude, grok") == ["codex", "claude", "grok"]
    target = tmp_path / "checkout" / "docs" / "plan.md"
    (tmp_path / "checkout" / ".git").mkdir(parents=True)
    target.parent.mkdir(parents=True)
    target.write_text("# Plan", encoding="utf-8")
    root, topic = orchestrator.resolve_root_and_topic(str(tmp_path), str(target))
    assert root == (tmp_path / "checkout").resolve()
    assert topic == "docs/plan.md"


def test_ledger_prompt_requires_independent_review_and_evidence_based_convergence() -> None:
    orchestrator = load_orchestrator()
    status = SimpleNamespace(open_points=[], convergence=[], markdown="")

    prompt = orchestrator.build_prompt("claude", "topic", "target", status)

    assert "form your own view before relying on the current ledger" in prompt
    assert "Add any materially new issue" in prompt
    assert "strongest plausible alternative or counterexample" in prompt
    assert "disconfirming pass" in prompt
    assert "{{AGENT}}" not in prompt
    assert "{{LEDGER_MARKDOWN}}" not in prompt


def test_result_helpers_keep_ledger_business_validation() -> None:
    orchestrator = load_orchestrator()
    payload = {"convergences": [], "contests": [], "new_points": [{"summary": "S", "body": "B"}]}
    stream = json.dumps({"type": "message", "payload": {"content": json.dumps(payload)}})
    assert orchestrator.parse_codex_jsonl(stream) == payload
    assert orchestrator.extract_agent_result({"result": "```json\n" + json.dumps(payload) + "\n```"}) == payload
    try:
        orchestrator.normalize_result({"convergences": [], "contests": []})
    except orchestrator.AdapterError as exc:
        assert exc.code == "INVALID_JSON"
    else:
        raise AssertionError("expected invalid Ledger payload")


def test_orchestrator_passes_legacy_codex_and_claude_configuration_to_executors(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []
    codex_payload = {"convergences": [], "contests": [], "new_points": []}
    claude_payload = {"convergences": [], "contests": [], "new_points": []}

    def fake_executor(script, arguments, prompt, root, timeout_s):
        calls.append((script, arguments, prompt, root, timeout_s))
        return json.dumps(codex_payload if script == orchestrator.CALL_CODEX else claude_payload)

    monkeypatch.setattr(orchestrator, "run_executor", fake_executor)
    assert orchestrator.run_codex("codex prompt", tmp_path, 10) == codex_payload
    assert orchestrator.run_claude("claude prompt", tmp_path, 10, "medium") == claude_payload
    codex_args = calls[0][1]
    claude_args = calls[1][1]
    assert ["--config", 'service_tier="fast"'] == codex_args[:2]
    assert "read-only" in codex_args and "--ephemeral" in codex_args
    assert "--output-schema" in codex_args
    assert "--no-session-persistence" in claude_args and "--disable-slash-commands" in claude_args
    assert "--tools" in claude_args and "Read,Glob,Grep" in claude_args
    assert "--json-schema" in claude_args
    assert claude_args[claude_args.index("--effort") + 1] == "medium"


def test_orchestrator_passes_explicit_grok_configuration_to_executor(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    payload = {"convergences": [], "contests": [], "new_points": []}
    calls = []

    def fake_executor(script, arguments, prompt, root, timeout_s):
        calls.append((script, arguments, prompt, root, timeout_s))
        return json.dumps(payload)

    monkeypatch.setattr(orchestrator, "run_executor", fake_executor)
    assert orchestrator.run_grok("grok prompt", tmp_path, 10) == payload
    assert calls == [
        (
            orchestrator.CALL_GROK,
            ["--effort", "low", "--tools", "", "--no-subagents", "--overall-timeout-sec", "10"],
            "grok prompt",
            tmp_path,
            10,
        )
    ]


def test_orchestrator_keeps_claude_business_json_repair_above_executor(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    repaired = {"convergences": [], "contests": [{"point": "D1", "body": 'quoted "text"', "movement": True}], "new_points": []}
    outputs = [
        '```json\n{"convergences":[],"contests":[{"point":"D1","body":"quoted "text"","movement":true}],"new_points":[]}\n```',
        json.dumps(repaired),
    ]
    efforts = []

    def fake_executor(script, arguments, prompt, root, timeout_s):
        del script, root, timeout_s
        efforts.append(arguments[arguments.index("--effort") + 1])
        if len(outputs) == 2:
            assert prompt == "prompt"
        else:
            assert "Invalid Claude result text:" in prompt
        return outputs.pop(0)

    monkeypatch.setattr(orchestrator, "run_executor", fake_executor)
    assert orchestrator.run_claude("prompt", tmp_path, 10, "medium") == repaired
    assert efforts == ["medium", "medium"]


def test_real_orchestration_still_owns_round_robin_after_executor_extraction(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    payloads = [
        {"convergences": [], "contests": [], "new_points": [{"summary": "Opening", "body": "Codex point"}]},
        {"convergences": [{"point": "D1", "marker": "一致", "line": "Claude agrees"}], "contests": [], "new_points": []},
    ]

    def fake_executor(script, arguments, prompt, root, timeout_s):
        del arguments, prompt, root, timeout_s
        expected = orchestrator.CALL_CODEX if len(payloads) == 2 else orchestrator.CALL_CLAUDE
        assert script == expected
        return json.dumps(payloads.pop(0))

    monkeypatch.setattr(orchestrator, "run_executor", fake_executor)
    assert orchestrator.orchestrate(root=tmp_path, topic="Happy", slug="happy", agents=["codex", "claude"], max_rounds=2, fake=False, timeout_s=10) == 0
    status = orchestrator.ledger.get_status(root=tmp_path, slug="happy")
    assert status.frontmatter["status"] == orchestrator.ledger.STATUS_AGREED


def test_max_rounds_means_full_participant_cycles(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    speakers = []

    def fake_call_agent(agent, prompt, root, status, fake, timeout_s, claude_effort):
        del prompt, root, fake, timeout_s
        assert claude_effort == "medium"
        speakers.append(agent)
        if not status.open_points:
            return {"convergences": [], "contests": [], "new_points": [{"summary": "Open", "body": "Open point"}]}
        return {
            "convergences": [],
            "contests": [{"point": "D1", "body": f"{agent} continues", "movement": True}],
            "new_points": [],
        }

    monkeypatch.setattr(orchestrator, "call_agent", fake_call_agent)
    assert orchestrator.orchestrate(
        root=tmp_path,
        topic="Cycle semantics",
        slug="cycle-semantics",
        agents=["codex", "claude"],
        max_rounds=2,
        fake=False,
        timeout_s=10,
        claude_effort="medium",
    ) == 0

    assert speakers == ["codex", "claude", "codex", "claude"]
    status = orchestrator.ledger.get_status(root=tmp_path, slug="cycle-semantics")
    assert status.frontmatter["round"] == 3
    assert status.open_points == [{"id": "D1", "summary": "Open", "status": "分歧", "rounds": "2"}]
    text = (tmp_path / "docs" / "exchange" / "discuss" / "discuss-cycle-semantics.md").read_text(encoding="utf-8")
    assert "### 轮次 1 · codex" in text and "### 轮次 1 · claude" in text
    assert "### 轮次 2 · codex" in text and "### 轮次 2 · claude" in text


def test_invalid_point_reference_still_retries_as_new_point(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    payloads = [
        {"convergences": [{"point": "D9", "marker": "一致", "line": "invalid"}], "contests": [], "new_points": []},
        {"convergences": [], "contests": [], "new_points": [{"summary": "New", "body": "valid"}]},
    ]
    prompts = []

    def fake_call_agent(agent, prompt, root, status, fake, timeout_s, claude_effort):
        del agent, root, status, fake, timeout_s
        assert claude_effort == "medium"
        prompts.append(prompt)
        return payloads.pop(0)

    monkeypatch.setattr(orchestrator, "call_agent", fake_call_agent)
    assert orchestrator.orchestrate(
        root=tmp_path,
        topic="Retry",
        slug="retry",
        agents=["claude"],
        max_rounds=1,
        fake=False,
        timeout_s=10,
        claude_effort="medium",
    ) == 0
    assert "Current legal open point IDs: (none)" in prompts[1]


def test_run_process_wraps_windows_powershell_shims(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    calls = []
    monkeypatch.setattr(orchestrator.shutil, "which", lambda exe: f"C:/tools/{exe}.ps1")

    class FakePopen:
        pid = 123
        returncode = 0

        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))

        def communicate(self, input=None, timeout=None):
            return "", ""

    monkeypatch.setattr(orchestrator.subprocess, "Popen", FakePopen)
    orchestrator.run_process(["codex", "--version"])
    assert calls[0][0][:5] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


def test_timeout_kills_posix_process_group(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    killed = []
    monkeypatch.setattr(orchestrator.os, "name", "posix")
    monkeypatch.setattr(orchestrator.os, "killpg", lambda pid, sig: killed.append((pid, sig)), raising=False)
    orchestrator.terminate_process_tree(123)
    assert killed == [(123, orchestrator.signal.SIGTERM)]
