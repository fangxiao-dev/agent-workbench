from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/SKILL.md").read_text(encoding="utf-8")


def test_audit_apply_verify_boundaries_are_explicit() -> None:
    assert "只读 audit" in TEXT
    assert "精确 item ID" in TEXT
    assert "失败只报告，不自动修复" in TEXT


def test_paths_and_versions_use_the_lightweight_contract() -> None:
    assert "仓库相对路径" in TEXT
    assert "target Git commit" in TEXT
    assert "package-retirement" not in TEXT
