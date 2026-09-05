import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/SKILL.md").read_text(encoding="utf-8")
SCHEMA = json.loads(
    (ROOT / "plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/config/repository-config.schema.json").read_text(
        encoding="utf-8"
    )
)
VERIFY_RUNBOOK = (
    ROOT / "plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/verify-runbook.md"
).read_text(encoding="utf-8")


def test_audit_apply_verify_boundaries_are_explicit() -> None:
    assert "只读 audit" in TEXT
    assert "精确 item ID" in TEXT
    assert "验证器只读" in TEXT
    assert "本轮 apply 在已批准 destination 内造成的链接、格式等机械错误" in TEXT
    assert "回到同一授权 apply 修复并重验" in TEXT
    assert "新增语义、destination、无关问题或破坏范围变化交回 owner" in TEXT


def test_paths_and_versions_use_the_lightweight_contract() -> None:
    path_contract = SCHEMA["$defs"]["path"]
    assert path_contract["type"] == "string"
    assert path_contract["not"]["pattern"].startswith("(^/|^[A-Za-z]:")
    assert r"(^|/)\.\.(/|$)" in path_contract["not"]["pattern"]
    assert r"[*?\[]" in path_contract["not"]["pattern"]
    assert "target Git commit" in VERIFY_RUNBOOK
    assert "package-retirement" not in TEXT
