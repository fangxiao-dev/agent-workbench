from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "discuss-ledger" / "scripts"
BLIND = SCRIPTS / "blind_opening.py"
COMBINED = SCRIPTS / "blind_opening_then_ledger.py"


def load_module(name: str, path: Path):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_claude_schema_omits_draft_metadata() -> None:
    blind = load_module("blind_opening_schema_under_test", BLIND)

    schema = json.loads(blind.claude_schema_json())

    assert "$schema" not in schema
    assert "$id" not in schema
    assert schema["required"] == ["ideas", "new_points"]


def test_blind_opening_registers_grok_executor() -> None:
    blind = load_module("blind_opening_grok_under_test", BLIND)

    assert blind.executor_path("grok").name == "grok_task.py"


def test_blind_opening_extracts_schema_result_from_fenced_model_text() -> None:
    blind = load_module("blind_opening_parse_text_under_test", BLIND)
    payload = {
        "ideas": [{"summary": "Idea", "body": "Independent idea"}],
        "new_points": [{"summary": "Point", "body": "Material point"}],
    }

    assert blind.parse_result_text("Here is the result:\n```json\n" + json.dumps(payload) + "\n```") == payload


def test_blind_opening_hides_other_participant_output_and_writes_temp_artifacts(tmp_path: Path) -> None:
    blind = load_module("blind_opening_under_test", BLIND)
    prompts: list[tuple[str, str]] = []

    def runner(agent: str, prompt: str, root: Path, timeout_s: int):
        del root, timeout_s
        prompts.append((agent, prompt))
        return {
            "ideas": [{"summary": f"{agent} idea", "body": f"{agent} independent view"}],
            "new_points": [{"summary": "Same point", "body": f"{agent} evidence"}],
        }

    result = blind.run_blind_opening(
        root=tmp_path,
        topic="Independent design",
        slug="independent-design",
        agents=["codex", "claude"],
        timeout_s=10,
        output_dir=tmp_path / "user-temp" / "discuss-ledger",
        agent_runner=runner,
    )

    assert len(prompts) == 2
    codex_prompt = prompts[0][1]
    claude_prompt = prompts[1][1]
    assert "claude independent view" not in codex_prompt
    assert "codex independent view" not in claude_prompt
    assert "Current ledger markdown" not in codex_prompt
    assert len(result["initial_points"]) == 1
    assert "[codex] codex evidence" in result["initial_points"][0]["body"]
    assert "[claude] claude evidence" in result["initial_points"][0]["body"]
    markdown = Path(result["artifacts"]["markdown"])
    intermediate = Path(result["artifacts"]["json"])
    assert markdown.is_file()
    assert intermediate.is_file()
    assert "# Blind Opening: independent-design" in markdown.read_text(encoding="utf-8")


def test_combined_mode_initializes_existing_ledger_before_normal_orchestration(tmp_path: Path) -> None:
    combined = load_module("blind_opening_then_ledger_under_test", COMBINED)
    exit_code = combined.run_combined(
        root=tmp_path,
        topic="Combined design",
        slug="combined-design",
        agents=["codex", "claude"],
        max_rounds=2,
        timeout_s=10,
        output_dir=tmp_path / "user-temp" / "discuss-ledger",
        fake=True,
    )

    assert exit_code == 0
    text = (tmp_path / "docs" / "exchange" / "discuss" / "discuss-combined-design.md").read_text(encoding="utf-8")
    assert "Fake codex concern" in text
    assert "Fake claude concern" in text
    assert "participants: [codex, claude]" in text


def test_combined_mode_refuses_to_overwrite_existing_ledger(tmp_path: Path) -> None:
    combined = load_module("blind_opening_then_ledger_collision_under_test", COMBINED)
    ledger_path = tmp_path / "docs" / "exchange" / "discuss" / "discuss-already-there.md"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text("existing", encoding="utf-8")

    try:
        combined.run_combined(
            root=tmp_path,
            topic="Collision",
            slug="already-there",
            agents=["codex", "claude"],
            max_rounds=2,
            timeout_s=10,
            output_dir=tmp_path / "user-temp" / "discuss-ledger",
            fake=True,
        )
    except combined.blind_opening.BlindOpeningError as exc:
        assert "LEDGER_EXISTS" in str(exc)
    else:
        raise AssertionError("expected collision failure")
