from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "workbench-design" / "04-install-spec.md"
LEGACY = ROOT / "skills" / "plugin-lifecycle"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_agents_points_to_the_single_install_guide() -> None:
    agents = read(ROOT / "AGENTS.md")

    assert "docs/workbench-design/04-install-spec.md" in agents
    assert "execute the host-native CLI directly" in agents
    assert "scripts/codex_setup.py" in agents
    assert "run `audit` first" in agents
    assert "agent-workbench-manager" not in agents


def test_guide_uses_direct_cli_for_each_host() -> None:
    guide = read(GUIDE)
    commands = (
        "codex plugin list",
        "codex plugin add impl-package@agent-workbench",
        "codex plugin remove impl-package@agent-workbench",
        "claude plugin list",
        "claude plugin update impl-package@agent-workbench --scope <scope>",
        "claude plugin uninstall impl-package@agent-workbench --scope <scope> --yes",
        "grok plugin list",
        "grok plugin update impl-package",
        "grok plugin install D:\\path\\to\\agent-workbench\\plugin-marketplace\\plugins\\impl-package --trust",
    )

    for command in commands:
        assert command in guide
    assert "用户明确要求" in guide
    assert "cache" in guide
    assert "python scripts/codex_setup.py audit --output codex-audit.md" in guide
    assert "apply --expect-report <audit-sha>" in guide
    assert "唯一允许包装 Codex plugin CLI" in guide


def test_lifecycle_skill_and_wrapper_are_removed() -> None:
    assert not (LEGACY / "SKILL.md").exists()
    assert not (LEGACY / "scripts" / "plugin_lifecycle.py").exists()
    assert not (LEGACY / "references" / "config.example.json").exists()


def test_readme_links_to_the_guide_without_copying_the_wrapper() -> None:
    readme = read(ROOT / "README.md")

    assert "docs/workbench-design/04-install-spec.md#plugin-生命周期agent-直接执行" in readme
    assert "python scripts/codex_setup.py pull-diff" in readme
    assert "apply --expect-report" in readme
    assert "plugin_lifecycle.py" not in readme
    assert "config.example.json" not in readme
