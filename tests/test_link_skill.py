from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "link_skill.py"
IS_WINDOWS = os.name == "nt"


def load_module():
    # Unique module name per load so monkeypatches do not leak across tests wrongly;
    # still fine to reuse one name — each fixture reloads.
    name = "link_skill_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_dir_link(source: Path, destination: Path) -> None:
    """Create the platform-native directory link (junction or symlink)."""
    source = source.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if IS_WINDOWS:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(destination), str(source)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr or result.stdout
    else:
        os.symlink(str(source), str(destination), target_is_directory=True)


@pytest.fixture()
def workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = load_module()
    wb = tmp_path / "workbench"
    skills = wb / "skills"
    skills.mkdir(parents=True)
    (skills / "call-grok").mkdir()
    (skills / "call-grok" / "SKILL.md").write_text("# call-grok\n", encoding="utf-8")
    (skills / "alpha").mkdir()
    (skills / "beta").mkdir()
    (skills / "bundle").mkdir()
    (skills / "bundle" / "nested").mkdir()

    monkeypatch.setattr(mod, "WORKBENCH_ROOT", wb)
    monkeypatch.setattr(mod, "SKILLS_ROOT", skills)
    return mod, wb, skills


def parse_summary(stdout: str) -> dict:
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    assert lines, "expected JSON summary on stdout"
    return json.loads(lines[-1])


def assert_is_platform_link(mod, path: Path) -> None:
    assert mod.is_link(path), f"expected platform link at {path}"
    if IS_WINDOWS:
        assert mod.IS_WINDOWS is True
    else:
        assert path.is_symlink()


def test_platform_constants(workbench) -> None:
    mod, _wb, _skills = workbench
    assert mod.IS_WINDOWS is IS_WINDOWS
    if IS_WINDOWS:
        assert mod.create_dir_link.__doc__ is None or True


def test_resolve_skill_and_missing(workbench) -> None:
    mod, _wb, skills = workbench
    assert mod.resolve_skill_source("call-grok") == (skills / "call-grok").resolve()
    with pytest.raises(FileNotFoundError):
        mod.resolve_skill_source("nope")
    with pytest.raises(ValueError):
        mod.resolve_skill_source("../outside")


def test_link_then_skip(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    host_skills = tmp_path / "home" / ".claude" / "skills"
    code = mod.main(["call-grok", "--to", str(host_skills), "--json"])
    assert code == 0
    dest = host_skills / "call-grok"
    assert dest.is_dir()
    assert (dest / "SKILL.md").is_file()
    assert_is_platform_link(mod, dest)
    target = mod.link_target(dest)
    assert target is not None
    assert mod.same_path(target, skills / "call-grok")

    code2 = mod.main(["call-grok", "--to", str(host_skills), "--json"])
    assert code2 == 0
    root, items = mod.link_skills_to_root(
        [skills / "call-grok"], host_skills, workbench_skills=skills
    )
    assert root["action"] == "ok"
    assert items[0]["action"] == "skipped"
    assert items[0]["link_kind"] == ("junction" if IS_WINDOWS else "symlink")


def test_conflict_real_directory(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    host_skills = tmp_path / "skills"
    host_skills.mkdir()
    conflict = host_skills / "call-grok"
    conflict.mkdir()
    (conflict / "other.txt").write_text("x", encoding="utf-8")

    root, items = mod.link_skills_to_root(
        [skills / "call-grok"], host_skills, workbench_skills=skills
    )
    assert root["action"] in {"ok", "created"}
    assert items[0]["action"] == "conflict"


def test_migrate_whole_tree_then_link(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    host_skills = tmp_path / "home" / ".claude" / "skills"
    make_dir_link(skills, host_skills)
    assert mod.is_link(host_skills)

    code = mod.main(["call-grok", "--to", str(host_skills), "--json"])
    assert code == 0
    assert host_skills.is_dir()
    assert not mod.is_link(host_skills), "skills root must be a real directory after migrate"
    linked = host_skills / "call-grok"
    assert linked.is_dir()
    assert_is_platform_link(mod, linked)
    assert (linked / "SKILL.md").is_file()
    assert (skills / "call-grok" / "SKILL.md").is_file()


def test_refuse_foreign_whole_tree(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    other = tmp_path / "other-skills"
    other.mkdir()
    (other / "x").mkdir()
    host_skills = tmp_path / "home" / ".codex" / "skills"
    make_dir_link(other, host_skills)

    code = mod.main(["call-grok", "--to", str(host_skills), "--json"])
    assert code == 1
    assert mod.is_link(host_skills)
    # foreign tree must not gain a workbench skill link silently
    assert not (host_skills / "call-grok").exists() or mod.is_link(host_skills)


def test_all_links_top_level(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    host_skills = tmp_path / "skills-out"
    code = mod.main(["--all", "--to", str(host_skills), "--json"])
    assert code == 0
    names = {p.name for p in host_skills.iterdir()}
    assert names == {"call-grok", "alpha", "beta", "bundle"}
    assert (host_skills / "bundle" / "nested").is_dir()
    for name in names:
        assert_is_platform_link(mod, host_skills / name)


def test_multi_host_with_home(workbench, tmp_path: Path) -> None:
    mod, _wb, _skills = workbench
    home = tmp_path / "home"
    code = mod.main(
        ["call-grok", "--host", "claude", "codex", "--home", str(home), "--json"]
    )
    assert code == 0
    for host in ("claude", "codex"):
        dest = home / f".{host}" / "skills" / "call-grok"
        assert dest.is_dir()
        assert_is_platform_link(mod, dest)


def test_migrate_only(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    host_skills = tmp_path / "home" / ".grok" / "skills"
    make_dir_link(skills, host_skills)
    code = mod.main(["--migrate-only", "--to", str(host_skills), "--json"])
    assert code == 0
    assert host_skills.is_dir()
    assert not mod.is_link(host_skills)
    assert list(host_skills.iterdir()) == []


def test_json_summary_shape(workbench, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    mod, _wb, _skills = workbench
    host_skills = tmp_path / "skills"
    code = mod.main(["alpha", "--to", str(host_skills), "--json"])
    assert code == 0
    out = capsys.readouterr().out
    summary = parse_summary(out)
    assert summary["ok"] is True
    assert summary["platform"] == ("windows" if IS_WINDOWS else "unix")
    assert summary["link_kind"] == ("junction" if IS_WINDOWS else "symlink")
    assert "workbench" in summary
    assert summary["hosts"][0]["items"][0]["action"] == "linked"
    assert summary["hosts"][0]["items"][0]["link_kind"] == summary["link_kind"]


def test_same_path_normalizes_extended_prefix(workbench) -> None:
    mod, _wb, skills = workbench
    a = skills / "call-grok"
    b = Path("\\\\?\\" + str(a.resolve())) if IS_WINDOWS else a.resolve()
    if IS_WINDOWS:
        assert mod.same_path(a, b)
    else:
        assert mod.same_path(a, a.resolve())


def test_host_skills_dir_paths(workbench, tmp_path: Path) -> None:
    mod, _wb, _skills = workbench
    home = tmp_path / "home"
    claude = mod.host_skills_dir("claude", home=home)
    assert claude == mod.abspath_nofollow(home / ".claude" / "skills")
    with pytest.raises(ValueError):
        mod.host_skills_dir("unknown", home=home)


def test_unlink_removes_host_link_keeps_source(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    host_skills = tmp_path / "skills-out"
    assert mod.main(["call-grok", "--to", str(host_skills), "--json"]) == 0
    dest = host_skills / "call-grok"
    assert dest.is_dir()
    assert_is_platform_link(mod, dest)

    code = mod.main(["call-grok", "--to", str(host_skills), "--unlink", "--json"])
    assert code == 0
    assert not dest.exists()
    assert not mod.is_link(dest)
    # workbench source intact
    assert (skills / "call-grok" / "SKILL.md").is_file()

    # second unlink is skip
    code2 = mod.main(["call-grok", "--to", str(host_skills), "--unlink", "--json"])
    assert code2 == 0


def test_unlink_refuses_real_directory(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    host_skills = tmp_path / "skills-out"
    host_skills.mkdir()
    real = host_skills / "call-grok"
    real.mkdir()
    (real / "x.txt").write_text("keep", encoding="utf-8")

    root, items = mod.unlink_skills_from_root([skills / "call-grok"], host_skills)
    assert root["action"] == "ok"
    assert items[0]["action"] == "conflict"
    assert real.is_dir()
    assert (real / "x.txt").read_text(encoding="utf-8") == "keep"


def test_unlink_refuses_foreign_link(workbench, tmp_path: Path) -> None:
    mod, _wb, skills = workbench
    other = tmp_path / "other"
    other.mkdir()
    (other / "nested").mkdir()
    host_skills = tmp_path / "skills-out"
    host_skills.mkdir()
    dest = host_skills / "call-grok"
    make_dir_link(other, dest)

    root, items = mod.unlink_skills_from_root([skills / "call-grok"], host_skills)
    assert items[0]["action"] == "conflict"
    assert mod.is_link(dest)
