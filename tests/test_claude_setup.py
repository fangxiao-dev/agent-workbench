from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "claude_setup.py"


def load_module():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    name = "claude_setup_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return load_module()


def _make_workspace(tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "workbench"
    skills = repo / "skills"
    marketplace = repo / "plugin-marketplace"
    plugin = marketplace / "plugins" / "demo"
    (skills / "alpha").mkdir(parents=True)
    (skills / "alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
    (marketplace / ".claude-plugin").mkdir(parents=True)
    (marketplace / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "plugins": [
                    {"name": "demo", "source": "./plugins/demo", "version": "0.1.0"}
                ]
            }
        ),
        encoding="utf-8",
    )
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": "0.1.0"}), encoding="utf-8"
    )
    (plugin / "payload.txt").write_text("payload\n", encoding="utf-8")

    claude_home = tmp_path / "claude"
    (claude_home / "skills").mkdir(parents=True)
    cache = claude_home / "plugins" / "cache" / "agent-workbench" / "demo" / "0.1.0"
    cache.parent.mkdir(parents=True)
    shutil.copytree(plugin, cache)

    monkeypatch.setattr(mod, "REPO_ROOT", repo)
    monkeypatch.setattr(mod, "MARKETPLACE_ROOT", marketplace)
    monkeypatch.setattr(mod.link_skill, "WORKBENCH_ROOT", repo)
    monkeypatch.setattr(mod.link_skill, "SKILLS_ROOT", skills)

    mod.link_skill.create_dir_link(skills / "alpha", claude_home / "skills" / "alpha")
    (claude_home / "skills" / "user-owned").mkdir()

    marketplace_entry = {
        "name": "agent-workbench",
        "source": "directory",
        "path": str(marketplace),
        "installLocation": str(marketplace),
    }
    plugin_entry = {
        "id": "demo@agent-workbench",
        "version": "0.1.0",
        "scope": "user",
        "enabled": True,
        "installPath": str(cache),
    }

    def fake_json_list(args):
        if args[1:4] == ["plugin", "marketplace", "list"]:
            return [marketplace_entry]
        if args[1:3] == ["plugin", "list"]:
            return [plugin_entry]
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_run_json_list", fake_json_list)
    return repo, claude_home, plugin, cache, marketplace_entry, plugin_entry


def test_audit_clean_then_detects_cache_drift(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)

    clean = mod.audit_claude(claude_home)
    assert clean.clean is True
    assert {item.name for item in clean.items} == {"demo", "alpha"}
    plugin_item = next(item for item in clean.items if item.kind == "plugin")
    assert plugin_item.expected_sha == plugin_item.actual_sha

    (cache / "payload.txt").write_text("stale\n", encoding="utf-8")
    drift = mod.audit_claude(claude_home)
    plugin_item = next(item for item in drift.items if item.kind == "plugin")
    assert plugin_item.status == "DRIFT"
    assert plugin_item.expected_sha != plugin_item.actual_sha
    assert plugin_item.differences[0].startswith("M payload.txt")


def test_audit_reports_stale_workbench_link_but_ignores_user_content(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, claude_home, _plugin, _cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)
    stale_source = repo / "skills" / "removed-skill"
    stale_source.mkdir()
    mod.link_skill.create_dir_link(stale_source, claude_home / "skills" / "removed-skill")

    result = mod.audit_claude(claude_home)
    states = {(item.kind, item.name): item.status for item in result.items}
    assert states[("skill", "removed-skill")] == "INSTALL-MISMATCH"
    assert ("skill", "user-owned") not in states


def test_audit_reports_missing_link_and_real_directory(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, _cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)
    mod.link_skill.remove_link(claude_home / "skills" / "alpha")
    (claude_home / "skills" / "alpha").mkdir()

    result = mod.audit_claude(claude_home)
    states = {(item.kind, item.name): item.status for item in result.items}
    assert states[("skill", "alpha")] == "INSTALL-MISMATCH"


def test_audit_reports_missing_skill_link(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, _cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)
    mod.link_skill.remove_link(claude_home / "skills" / "alpha")

    result = mod.audit_claude(claude_home)
    states = {(item.kind, item.name): item.status for item in result.items}
    assert states[("skill", "alpha")] == "MISSING"


def test_audit_flags_disabled_plugin(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, _cache, marketplace_entry, plugin_entry = _make_workspace(
        tmp_path, mod, monkeypatch
    )

    def fake_json_list(args):
        if args[1:4] == ["plugin", "marketplace", "list"]:
            return [marketplace_entry]
        if args[1:3] == ["plugin", "list"]:
            return [{**plugin_entry, "enabled": False}]
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_run_json_list", fake_json_list)

    result = mod.audit_claude(claude_home)
    plugin_item = next(item for item in result.items if item.kind == "plugin")
    assert plugin_item.status == "INSTALL-MISMATCH"
    assert "plugin is disabled" in plugin_item.note


def test_audit_missing_marketplace_registration_reports_missing_plugin(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, _cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)

    def fake_json_list(args):
        if args[1:4] == ["plugin", "marketplace", "list"]:
            return []
        if args[1:3] == ["plugin", "list"]:
            return []
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_run_json_list", fake_json_list)

    result = mod.audit_claude(claude_home)
    plugin_item = next(item for item in result.items if item.kind == "plugin")
    assert plugin_item.status == "MISSING"
    assert "marketplace agent-workbench is not registered" in plugin_item.note


def test_audit_marketplace_pointing_elsewhere_is_install_mismatch(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, _cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    marketplace_entry = {
        "name": "agent-workbench",
        "source": "directory",
        "path": str(elsewhere),
        "installLocation": str(elsewhere),
    }

    def fake_json_list(args):
        if args[1:4] == ["plugin", "marketplace", "list"]:
            return [marketplace_entry]
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_run_json_list", fake_json_list)

    result = mod.audit_claude(claude_home)
    plugin_item = next(item for item in result.items if item.kind == "plugin")
    assert plugin_item.status == "INSTALL-MISMATCH"
    assert "points elsewhere" in plugin_item.note


def test_expected_plugins_rejects_marketplace_version_mismatch(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _claude_home, _plugin, _cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)
    marketplace = repo / "plugin-marketplace"
    manifest = marketplace / ".claude-plugin" / "marketplace.json"
    manifest.write_text(
        json.dumps(
            {
                "plugins": [
                    {"name": "demo", "source": "./plugins/demo", "version": "0.9.9"}
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(mod.SetupError, match="does not match plugin manifest version"):
        mod._expected_plugins()


def test_audit_blocks_when_plugin_entry_has_no_install_path(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, _cache, marketplace_entry, plugin_entry = _make_workspace(
        tmp_path, mod, monkeypatch
    )
    stripped = {key: value for key, value in plugin_entry.items() if key != "installPath"}

    def fake_json_list(args):
        if args[1:4] == ["plugin", "marketplace", "list"]:
            return [marketplace_entry]
        if args[1:3] == ["plugin", "list"]:
            return [stripped]
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_run_json_list", fake_json_list)

    result = mod.audit_claude(claude_home)
    plugin_item = next(item for item in result.items if item.kind == "plugin")
    assert plugin_item.status == "BLOCKED"
    assert result.operational_error is True


def test_audit_blocks_when_cache_directory_is_missing(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, cache, marketplace_entry, plugin_entry = _make_workspace(
        tmp_path, mod, monkeypatch
    )
    shutil.rmtree(cache)
    stale_entry = {**plugin_entry, "installPath": str(cache)}

    def fake_json_list(args):
        if args[1:4] == ["plugin", "marketplace", "list"]:
            return [marketplace_entry]
        if args[1:3] == ["plugin", "list"]:
            return [stale_entry]
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_run_json_list", fake_json_list)

    result = mod.audit_claude(claude_home)
    plugin_item = next(item for item in result.items if item.kind == "plugin")
    assert plugin_item.status == "MISSING"
    assert "cache directory is missing" in plugin_item.note


def test_audit_fingerprint_changes_with_reported_state(tmp_path: Path, mod) -> None:
    first = mod.AuditResult([mod.AuditItem("skill", "alpha", "MISSING", expected_sha="a")])
    second = mod.AuditResult(
        [mod.AuditItem("skill", "alpha", "MATCH", expected_sha="a", actual_sha="a")]
    )
    assert mod.audit_fingerprint(first, tmp_path) == mod.audit_fingerprint(first, tmp_path)
    assert mod.audit_fingerprint(first, tmp_path) != mod.audit_fingerprint(second, tmp_path)


def test_report_groups_status_and_resolves_template(tmp_path: Path, mod) -> None:
    template = tmp_path / "report.tpl"
    template.write_text(
        "{{mode}}\n{{summary}}\n{{body}}\n{{claude_home}}\n{{report_sha}}\n", encoding="utf-8"
    )
    result = mod.AuditResult(
        [
            mod.AuditItem("skill", "alpha", "MATCH", expected_sha="a", actual_sha="a"),
            mod.AuditItem("plugin", "demo", "DRIFT", expected_sha="b", actual_sha="c"),
        ]
    )
    report = mod.render_report(mode="audit", audit=result, claude_home=tmp_path)
    assert "### DRIFT (1)" in report
    assert "### MATCH" not in report
    assert "| plugin | `demo` | `—` |" in report
    assert "{{" not in report


def test_cli_audit_reports_drift_without_mutating_host(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, claude_home, _plugin, _cache, *_ = _make_workspace(tmp_path, mod, monkeypatch)
    output = tmp_path / "report.md"

    assert mod.main(["audit", "--claude-home", str(claude_home), "--output", str(output)]) == (
        mod.EXIT_OK
    )
    report = output.read_text(encoding="utf-8")
    assert "Claude Home" in report
    assert "未发现差异" in report

    mod.link_skill.remove_link(claude_home / "skills" / "alpha")
    assert mod.main(["audit", "--claude-home", str(claude_home), "--output", str(output)]) == (
        mod.EXIT_DRIFT
    )


def test_default_claude_home_prefers_config_dir(
    mod, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert mod.default_claude_home() == Path.home() / ".claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert mod.default_claude_home() == tmp_path
