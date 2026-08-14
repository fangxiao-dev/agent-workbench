from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "write-skill-smartly" / "sub-skills" / "skill-creator" / "scripts" / "quick_validate.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("skill_validator_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_skill(root: Path, invocation_value: str) -> Path:
    skill = root / "example"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: example\n"
        "description: Example skill.\n"
        f"disable-model-invocation: {invocation_value}\n"
        "---\n\n"
        "# Example\n",
        encoding="utf-8",
    )
    return skill


def test_disable_model_invocation_boolean_is_valid(tmp_path: Path) -> None:
    validator = load_validator()

    assert validator.validate_skill(write_skill(tmp_path, "true")) == (True, "Skill is valid!")


def test_disable_model_invocation_false_is_also_valid(tmp_path: Path) -> None:
    validator = load_validator()

    assert validator.validate_skill(write_skill(tmp_path, "false")) == (True, "Skill is valid!")


def test_disable_model_invocation_must_be_boolean(tmp_path: Path) -> None:
    validator = load_validator()

    valid, message = validator.validate_skill(write_skill(tmp_path, "maybe"))

    assert valid is False
    assert message == "disable-model-invocation must be a boolean"
