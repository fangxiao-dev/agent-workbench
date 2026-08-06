from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/.system/skill-creator/scripts/quick_validate.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("quick_validate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_skill(root: Path, extra: str) -> Path:
    skill = root / "example"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill.\n"
        + extra
        + "---\n\n# Example\n",
        encoding="utf-8",
    )
    return skill


def test_codex_invocation_frontmatter_is_valid() -> None:
    validator = load_validator()
    with tempfile.TemporaryDirectory() as value:
        skill = write_skill(
            Path(value),
            'argument-hint: "What should continue?"\ndisable-model-invocation: true\n',
        )
        assert validator.validate_skill(skill) == (True, "Skill is valid!")


def test_codex_invocation_frontmatter_types_are_checked() -> None:
    validator = load_validator()
    with tempfile.TemporaryDirectory() as value:
        skill = write_skill(Path(value), "disable-model-invocation: yes-please\n")
        valid, message = validator.validate_skill(skill)
        assert not valid
        assert message == "disable-model-invocation must be a boolean"
