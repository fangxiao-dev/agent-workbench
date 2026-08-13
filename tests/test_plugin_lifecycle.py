from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "plugin-lifecycle" / "scripts" / "plugin_lifecycle.py"


def load_module():
    spec = importlib.util.spec_from_file_location("plugin_lifecycle_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_config(tmp_path: Path, *, expected_version: str = "0.2.9") -> tuple[Path, dict]:
    plugin_root = tmp_path / "plugins" / "impl-package"
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / ".claude-plugin").mkdir()
    for directory in (".codex-plugin", ".claude-plugin"):
        (plugin_root / directory / "plugin.json").write_text(
            json.dumps({"name": "impl-package", "version": expected_version}), encoding="utf-8"
        )
    marketplace_root = tmp_path / "marketplace"
    (marketplace_root / ".claude-plugin").mkdir(parents=True)
    (marketplace_root / ".agents" / "plugins").mkdir(parents=True)
    (marketplace_root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "agent-workbench", "plugins": [{"name": "impl-package", "version": expected_version}]}),
        encoding="utf-8",
    )
    (marketplace_root / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps({"name": "agent-workbench", "plugins": [{"name": "impl-package", "source": {"path": "./plugins/impl-package"}}]}),
        encoding="utf-8",
    )
    payload = {
        "plugin": {
            "name": "impl-package",
            "root": "${PLUGIN_ROOT}",
            "marketplace": "agent-workbench",
            "marketplace_root": str(marketplace_root),
            "expected_version": expected_version,
        },
        "hosts": {
            "codex": {"enabled": True, "executable": "codex", "marketplace": "agent-workbench"},
            "claude": {"enabled": True, "executable": "claude", "marketplace": "agent-workbench", "scope": "user"},
            "grok": {"enabled": True, "executable": "grok", "source": "${PLUGIN_ROOT}"},
        },
    }
    config_path = tmp_path / "lifecycle.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path, payload


def load_config(module, config_path: Path):
    return module.validate_config(module.read_json(config_path))


def test_validate_expands_paths_and_checks_manifests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    config_path, payload = make_config(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path / "plugins" / "impl-package"))

    config = load_config(module, config_path)

    assert config["root"] == (tmp_path / "plugins" / "impl-package").resolve()
    assert config["expected_version"] == "0.2.9"
    assert set(config["hosts"]) == {"codex", "claude", "grok"}


def test_version_mismatch_is_a_config_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    config_path, payload = make_config(tmp_path, expected_version="0.2.8")
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path / "plugins" / "impl-package"))
    payload["plugin"]["expected_version"] = "0.2.9"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(module.ConfigError, match="versions"):
        module.validate_config(module.read_json(config_path))


def test_command_vectors_cover_each_host_and_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    config_path, payload = make_config(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path / "plugins" / "impl-package"))
    config = load_config(module, config_path)

    assert module.command_plan(config, "refresh", "codex") == [["codex", "plugin", "add", "impl-package@agent-workbench"]]
    assert module.command_plan(config, "reinstall", "codex")[0] == ["codex", "plugin", "remove", "impl-package@agent-workbench"]
    assert module.command_plan(config, "refresh", "claude") == [
        ["claude", "plugin", "marketplace", "update", "agent-workbench"],
        ["claude", "plugin", "update", "impl-package@agent-workbench", "--scope", "user"],
    ]
    assert module.command_plan(config, "upgrade", "grok") == [["grok", "plugin", "update", "impl-package"]]
    assert module.command_plan(config, "reinstall", "grok")[-1][-2:] == [str(tmp_path / "plugins" / "impl-package"), "--trust"]


def test_dry_run_never_calls_subprocess_and_aggregates_plans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    config_path, payload = make_config(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path / "plugins" / "impl-package"))
    config = load_config(module, config_path)
    monkeypatch.setattr(module, "run_command", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("executed")))

    output = module.build_output(config, "upgrade", ["codex", "claude", "grok"], False, 10)

    assert output["ok"] is True
    assert [item["status"] for item in output["hosts"]] == ["planned", "planned", "planned"]


def test_apply_continues_after_one_host_failure_but_stops_failed_host_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    config_path, payload = make_config(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path / "plugins" / "impl-package"))
    config = load_config(module, config_path)
    calls: list[list[str]] = []

    def fake_run(command, _timeout):
        calls.append(list(command))
        if command[:4] == ["claude", "plugin", "uninstall", "impl-package@agent-workbench"]:
            return subprocess.CompletedProcess(command, 7, "", "uninstall failed")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(module, "run_command", fake_run)
    output = module.build_output(config, "reinstall", ["codex", "claude", "grok"], True, 10)

    assert output["ok"] is False
    assert output["hosts"][0]["status"] == "done"
    assert output["hosts"][1]["status"] == "failed"
    assert output["hosts"][2]["status"] == "done"
    assert ["claude", "plugin", "install", "impl-package@agent-workbench", "--scope", "user"] not in calls
    assert any(command[:3] == ["grok", "plugin", "uninstall"] for command in calls)


def test_missing_executable_and_grok_remote_source_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    config_path, payload = make_config(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path / "plugins" / "impl-package"))

    del payload["hosts"]["codex"]["executable"]
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.ConfigError, match="executable"):
        module.validate_config(module.read_json(config_path))

    payload["hosts"]["codex"]["executable"] = "codex"
    payload["hosts"]["grok"]["source"] = "https://example.invalid/plugin.git"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.ConfigError, match="source is not a directory"):
        module.validate_config(module.read_json(config_path))


def test_dry_run_does_not_change_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    config_path, payload = make_config(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path / "plugins" / "impl-package"))
    before = (tmp_path / "plugins" / "impl-package" / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    config = load_config(module, config_path)

    module.build_output(config, "refresh", ["codex"], False, 10)

    after = (tmp_path / "plugins" / "impl-package" / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    assert after == before


def test_skill_is_explicit_and_points_to_external_config() -> None:
    skill = (ROOT / "skills" / "plugin-lifecycle" / "SKILL.md").read_text(encoding="utf-8")
    assert "disable-model-invocation: true" in skill
    assert "references/config.example.json" in skill
    assert "scripts/plugin_lifecycle.py" in skill
    assert len(skill.splitlines()) <= 180


def test_main_returns_structured_config_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_module()
    missing = tmp_path / "missing.json"

    assert module.main(["--config", str(missing), "--action", "validate"]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["action"] == "validate"
    assert output["error"]["code"] == "config_error"
