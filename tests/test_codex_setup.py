from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codex_setup.py"


def load_module():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    name = "codex_setup_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def mod():
    return load_module()


@pytest.fixture()
def git_repo(tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    (repo / "README.md").write_text("one\n", encoding="utf-8")
    first = commit(repo, "first")
    (repo / "skills").mkdir()
    (repo / "skills" / "alpha.md").write_text("two\n", encoding="utf-8")
    second = commit(repo, "second")
    (repo / ".git" / "ORIG_HEAD").write_text(first + "\n", encoding="ascii")
    monkeypatch.setattr(mod, "REPO_ROOT", repo)
    return repo, first, second


def test_tree_sha_is_stable_and_ignores_runtime_files(tmp_path: Path, mod) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "b.txt").write_text("b", encoding="utf-8")
    (tree / "a.txt").write_text("a", encoding="utf-8")
    ignored = tree / "__pycache__"
    ignored.mkdir()
    (ignored / "x.pyc").write_bytes(b"one")

    first = mod.snapshot_tree(tree)
    (ignored / "x.pyc").write_bytes(b"two")
    assert mod.snapshot_tree(tree).sha256 == first.sha256

    (tree / "a.txt").write_text("changed", encoding="utf-8")
    second = mod.snapshot_tree(tree)
    assert second.sha256 != first.sha256
    assert mod.diff_snapshots(first, second)[0].startswith("M a.txt")


def test_tree_sha_normalizes_text_line_endings_but_not_binary(tmp_path: Path, mod) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "manifest.json").write_bytes(b'{\n  "name": "demo"\n}\n')
    (right / "manifest.json").write_bytes(b'{\r\n  "name": "demo"\r\n}\r\n')
    assert mod.snapshot_tree(left).sha256 == mod.snapshot_tree(right).sha256

    (left / "payload.bin").write_bytes(b"\xff\r\n")
    (right / "payload.bin").write_bytes(b"\xff\n")
    assert mod.snapshot_tree(left).sha256 != mod.snapshot_tree(right).sha256


def test_pull_diff_uses_orig_head_and_separates_dirty_worktree(git_repo, mod) -> None:
    repo, first, second = git_repo
    (repo / "local.txt").write_text("dirty\n", encoding="utf-8")

    result = mod.pull_diff("ORIG_HEAD", "HEAD")

    assert result["before"] == first
    assert result["after"] == second
    assert result["commits"] == [[second, "second"]]
    assert result["groups"]["skills"] == ["A skills/alpha.md"]
    assert result["dirty"] == ["?? local.txt"]


def test_pull_diff_rejects_missing_or_non_ancestor_baseline(git_repo, mod) -> None:
    repo, first, _second = git_repo
    with pytest.raises(mod.SetupError, match="pass --from"):
        mod.pull_diff("missing-ref", "HEAD")

    git(repo, "checkout", "--orphan", "other")
    git(repo, "rm", "-rf", ".")
    (repo / "other.txt").write_text("other\n", encoding="utf-8")
    other = commit(repo, "other")
    with pytest.raises(mod.SetupError, match="not an ancestor"):
        mod.pull_diff(first, other)


def _make_workspace(tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "workbench"
    skills = repo / "skills"
    agents = repo / "agents"
    marketplace = repo / "plugin-marketplace"
    plugin = marketplace / "plugins" / "demo"
    (skills / "alpha").mkdir(parents=True)
    (skills / "alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
    (agents / "scout").mkdir(parents=True)
    (agents / "scout" / "agent.md").write_text("# scout\n", encoding="utf-8")
    (marketplace / ".agents" / "plugins").mkdir(parents=True)
    (marketplace / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps(
            {
                "plugins": [
                    {"name": "demo", "source": {"source": "local", "path": "./plugins/demo"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": "0.1.0"}), encoding="utf-8"
    )
    (plugin / "payload.txt").write_text("payload\n", encoding="utf-8")

    codex_home = tmp_path / "codex"
    (codex_home / "skills").mkdir(parents=True)
    (codex_home / "agents").mkdir(parents=True)
    cache = codex_home / "plugins" / "cache" / "agent-workbench" / "demo" / "0.1.0"
    cache.parent.mkdir(parents=True)
    shutil.copytree(plugin, cache)

    monkeypatch.setattr(mod, "REPO_ROOT", repo)
    monkeypatch.setattr(mod, "MARKETPLACE_ROOT", marketplace)
    monkeypatch.setattr(mod.link_skill, "WORKBENCH_ROOT", repo)
    monkeypatch.setattr(mod.link_skill, "SKILLS_ROOT", skills)
    monkeypatch.setattr(
        mod,
        "_expected_roles",
        lambda: ({"review.toml": b"# managed\nname = 'review'\n"}, "# managed"),
    )

    mod.link_skill.create_dir_link(skills / "alpha", codex_home / "skills" / "alpha")
    mod.link_skill.create_dir_link(agents / "scout", codex_home / "agents" / "scout")
    (codex_home / "agents" / "review.toml").write_bytes(b"# managed\nname = 'review'\n")
    (codex_home / "skills" / "user-owned").mkdir()

    def fake_json(args, *, env=None):
        if args[1:4] == ["plugin", "marketplace", "list"]:
            return {"marketplaces": [{"name": "agent-workbench", "root": str(marketplace)}]}
        if args[1:3] == ["plugin", "list"]:
            return {
                "installed": [
                    {"name": "demo", "version": "0.1.0", "installed": True, "enabled": True}
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr(mod, "_run_json", fake_json)
    return repo, codex_home, plugin, cache


def test_audit_only_checks_workbench_assets_and_detects_sha_drift(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, codex_home, _plugin, cache = _make_workspace(tmp_path, mod, monkeypatch)

    clean = mod.audit_codex(codex_home)
    assert clean.clean is True
    assert {item.name for item in clean.items} == {"demo", "alpha", "scout", "review.toml"}

    (cache / "payload.txt").write_text("stale\n", encoding="utf-8")
    drift = mod.audit_codex(codex_home)
    plugin_item = next(item for item in drift.items if item.kind == "plugin")
    assert plugin_item.status == "DRIFT"
    assert plugin_item.expected_sha != plugin_item.actual_sha
    assert plugin_item.differences[0].startswith("M payload.txt")


def test_audit_reports_stale_workbench_link_but_ignores_user_content(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, codex_home, _plugin, _cache = _make_workspace(tmp_path, mod, monkeypatch)
    stale_source = repo / "skills" / "removed-skill"
    stale_source.mkdir()
    mod.link_skill.create_dir_link(stale_source, codex_home / "skills" / "removed-skill")

    result = mod.audit_codex(codex_home)
    states = {(item.kind, item.name): item.status for item in result.items}
    assert states[("skill", "removed-skill")] == "INSTALL-MISMATCH"
    assert ("skill", "user-owned") not in states


def test_audit_reports_missing_and_install_mismatch(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo, codex_home, _plugin, _cache = _make_workspace(tmp_path, mod, monkeypatch)
    mod.link_skill.remove_link(codex_home / "skills" / "alpha")
    mod.link_skill.remove_link(codex_home / "agents" / "scout")
    (codex_home / "agents" / "scout").mkdir()
    (codex_home / "agents" / "review.toml").write_text("user owned\n", encoding="utf-8")

    result = mod.audit_codex(codex_home)
    states = {(item.kind, item.name): item.status for item in result.items}
    assert states[("skill", "alpha")] == "MISSING"
    assert states[("agent", "scout")] == "INSTALL-MISMATCH"
    assert states[("role", "review.toml")] == "INSTALL-MISMATCH"

    (codex_home / "agents" / "review.toml").write_bytes(b"# managed\nstale\n")
    result = mod.audit_codex(codex_home)
    role = next(item for item in result.items if item.kind == "role")
    assert role.status == "DRIFT"


def test_apply_uses_native_commands_in_order(tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / "codex"
    pre = mod.AuditResult(
        [
            mod.AuditItem("plugin", "demo", "DRIFT"),
            mod.AuditItem("skill", "alpha", "MISSING"),
            mod.AuditItem("agent", "scout", "MISSING"),
            mod.AuditItem("role", "review.toml", "DRIFT"),
        ]
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        mod,
        "_run_json",
        lambda args, env=None: {
            "marketplaces": [{"name": "agent-workbench", "root": str(mod.MARKETPLACE_ROOT)}]
        },
    )
    monkeypatch.setattr(mod, "_expected_plugins", lambda: [{"name": "demo"}])

    def command(args, *, env=None):
        calls.append(list(args))
        return True, f"PASS {' '.join(args)}"

    monkeypatch.setattr(mod, "_command_action", command)
    monkeypatch.setattr(mod, "_apply_agents", lambda home: (calls.append(["agents"]) is None, ["PASS agents"]))

    actions, ok = mod.apply_codex(pre, codex_home)

    assert ok is True
    assert calls[0] == ["codex", "plugin", "add", "--json", "demo@agent-workbench"]
    assert calls[1][1].endswith("link_skill.py")
    assert calls[2] == ["agents"]
    assert calls[3][1].endswith("install_codex_agents.py")
    assert len(actions) == 4


def test_apply_stops_after_command_failure(tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch) -> None:
    pre = mod.AuditResult(
        [
            mod.AuditItem("plugin", "demo", "DRIFT"),
            mod.AuditItem("skill", "alpha", "MISSING"),
        ]
    )
    monkeypatch.setattr(
        mod,
        "_run_json",
        lambda args, env=None: {
            "marketplaces": [{"name": "agent-workbench", "root": str(mod.MARKETPLACE_ROOT)}]
        },
    )
    monkeypatch.setattr(mod, "_expected_plugins", lambda: [{"name": "demo"}])
    calls: list[list[str]] = []

    def fail(args, *, env=None):
        calls.append(list(args))
        return False, "FAIL plugin"

    monkeypatch.setattr(mod, "_command_action", fail)
    actions, ok = mod.apply_codex(pre, tmp_path / "codex")
    assert ok is False
    assert len(calls) == 1
    assert actions == ["FAIL plugin"]


def test_apply_registers_missing_marketplace_before_plugin(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    pre = mod.AuditResult([mod.AuditItem("plugin", "demo", "MISSING")])
    monkeypatch.setattr(mod, "_run_json", lambda args, env=None: {"marketplaces": []})
    monkeypatch.setattr(mod, "_expected_plugins", lambda: [{"name": "demo"}])
    calls: list[list[str]] = []

    def command(args, *, env=None):
        calls.append(list(args))
        return True, "PASS"

    monkeypatch.setattr(mod, "_command_action", command)
    _actions, ok = mod.apply_codex(pre, tmp_path / "codex")
    assert ok is True
    assert calls[0][:5] == ["codex", "plugin", "marketplace", "add", "--json"]
    assert calls[1] == ["codex", "plugin", "add", "--json", "demo@agent-workbench"]


def test_report_groups_status_and_resolves_template(tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch) -> None:
    template = tmp_path / "report.tpl"
    template.write_text("{{mode}}\n{{summary}}\n{{body}}\n{{codex_home}}\n{{report_sha}}\n", encoding="utf-8")
    monkeypatch.setattr(mod, "TEMPLATE_PATH", template)
    monkeypatch.setattr(
        mod,
        "_git",
        lambda args: subprocess.CompletedProcess(args, 0, stdout="", stderr=""),
    )
    result = mod.AuditResult(
        [
            mod.AuditItem("skill", "alpha", "MATCH", expected_sha="a", actual_sha="a"),
            mod.AuditItem("plugin", "demo", "DRIFT", expected_sha="b", actual_sha="c"),
        ]
    )
    report = mod.render_report(mode="audit", audit=result, codex_home=tmp_path)
    assert "### DRIFT (1)" in report
    assert "### MATCH" not in report
    assert "期望 SHA-256" not in report
    assert "| plugin | `demo` | `—` |" in report
    assert "{{" not in report


def test_audit_fingerprint_changes_with_reported_state(tmp_path: Path, mod) -> None:
    first = mod.AuditResult([mod.AuditItem("skill", "alpha", "MISSING", expected_sha="a")])
    second = mod.AuditResult([mod.AuditItem("skill", "alpha", "MATCH", expected_sha="a", actual_sha="a")])
    assert mod.audit_fingerprint(first, tmp_path) == mod.audit_fingerprint(first, tmp_path)
    assert mod.audit_fingerprint(first, tmp_path) != mod.audit_fingerprint(second, tmp_path)


def test_cli_requires_report_before_apply(mod) -> None:
    with pytest.raises(SystemExit):
        mod.build_parser().parse_args(["audit", "--apply"])
    parsed = mod.build_parser().parse_args(["apply", "--expect-report", "abc"])
    assert parsed.mode == "apply"
    assert parsed.expect_report == "abc"


def test_apply_rejects_stale_report_before_mutation(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = mod.AuditResult([mod.AuditItem("skill", "alpha", "MISSING", expected_sha="a")])
    monkeypatch.setattr(mod, "audit_codex", lambda home: result)
    monkeypatch.setattr(mod, "render_report", lambda **kwargs: "report\n")
    monkeypatch.setattr(mod, "_write_report", lambda report, output: None)
    monkeypatch.setattr(
        mod,
        "apply_codex",
        lambda pre, home: (_ for _ in ()).throw(AssertionError("must not apply")),
    )
    assert mod.main(["apply", "--expect-report", "stale", "--codex-home", str(tmp_path)]) == 1


def test_apply_accepts_current_report_and_requires_clean_post_audit(
    tmp_path: Path, mod, monkeypatch: pytest.MonkeyPatch
) -> None:
    pre = mod.AuditResult([mod.AuditItem("skill", "alpha", "MISSING", expected_sha="a")])
    post = mod.AuditResult(
        [mod.AuditItem("skill", "alpha", "MATCH", expected_sha="a", actual_sha="a")]
    )
    audits = iter([pre, post])
    monkeypatch.setattr(mod, "audit_codex", lambda home: next(audits))
    monkeypatch.setattr(mod, "apply_codex", lambda result, home: (["PASS apply"], True))
    monkeypatch.setattr(mod, "render_report", lambda **kwargs: "report\n")
    monkeypatch.setattr(mod, "_write_report", lambda report, output: None)
    report_sha = mod.audit_fingerprint(pre, tmp_path)
    assert (
        mod.main(["apply", "--expect-report", report_sha, "--codex-home", str(tmp_path)])
        == mod.EXIT_OK
    )
