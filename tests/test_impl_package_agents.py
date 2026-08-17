from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin-marketplace/plugins/impl-package/scripts/install_codex_agents.py"
EXPECTED = {
    "review-track-code",
    "review-track-safety",
    "review-track-spec",
    "review-track-standards",
}


def load_installer():
    spec = importlib.util.spec_from_file_location("install_codex_agents", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_codex_roles_are_projected_from_the_claude_agent_sources() -> None:
    installer = load_installer()
    profiles = installer.load_profiles()

    assert {profile.name for profile in profiles} == EXPECTED
    for profile in profiles:
        parsed = tomllib.loads(installer.render_codex_role(profile))
        assert set(parsed) == {"name", "description", "developer_instructions"}
        assert parsed["name"] == profile.name
        assert parsed["description"]
        assert "verdict:" in parsed["developer_instructions"]
        assert installer.MANAGED_MARKER in installer.render_codex_role(profile)


def test_global_role_install_is_idempotent_and_non_destructive(tmp_path: Path) -> None:
    installer = load_installer()
    target = tmp_path / "codex" / "agents"

    first = installer.install_profiles(target)
    assert set(first["installed"]) == {f"{name}.toml" for name in EXPECTED}
    assert first["updated"] == []
    assert first["skipped"] == []

    second = installer.install_profiles(target)
    assert second["installed"] == []
    assert second["updated"] == []
    assert set(second["skipped"]) == {f"{name}.toml" for name in EXPECTED}

    changed = target / "review-track-code.toml"
    changed.write_text("name = 'user-owned'\n", encoding="utf-8")
    with pytest.raises(installer.InstallConflictError):
        installer.install_profiles(target)
    with pytest.raises(installer.InstallConflictError):
        installer.install_profiles(target, force=True)

    profile = next(profile for profile in installer.load_profiles() if profile.name == "review-track-code")
    changed.write_text(installer._render_legacy_codex_role(profile), encoding="utf-8")
    forced = installer.install_profiles(target, force=True)
    assert forced["updated"] == ["review-track-code.toml"]
    assert installer.MANAGED_MARKER in changed.read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse-point behavior is host-specific")
def test_install_rejects_reparse_point_target(tmp_path: Path) -> None:
    installer = load_installer()
    real_target = tmp_path / "real-agents"
    real_target.mkdir()
    linked_target = tmp_path / "linked-agents"
    try:
        linked_target.symlink_to(real_target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"cannot create test junction/symlink: {exc}")

    with pytest.raises(installer.UnsafePathError):
        installer.install_profiles(linked_target, force=True)
    assert list(real_target.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse-point behavior is host-specific")
def test_install_rejects_reparse_point_destination(tmp_path: Path) -> None:
    installer = load_installer()
    target = tmp_path / "agents"
    target.mkdir()
    outside = tmp_path / "outside.toml"
    destination = target / "review-track-code.toml"
    try:
        destination.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"cannot create test symlink: {exc}")

    with pytest.raises(installer.UnsafePathError):
        installer.install_profiles(target, force=True)
    assert not outside.exists()
