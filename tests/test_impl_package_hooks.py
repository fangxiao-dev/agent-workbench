from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugin-marketplace/plugins/impl-package/hooks/impl_package_hooks.py"
HOOK_CONFIG = ROOT / "plugin-marketplace/plugins/impl-package/hooks/codex-hooks.json"
CODEX_MANIFEST = ROOT / "plugin-marketplace/plugins/impl-package/.codex-plugin/plugin.json"
FIXTURE = ROOT / "tests/fixtures/situations/p4-satisfiable-no-trail"
PACKAGE_REL = Path("docs/implementations/hook-package")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


def make_repo(root: Path, name: str = "repo") -> tuple[Path, Path]:
    repo = root / name
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "hooks@example.test")
    git(repo, "config", "user.name", "Hook tests")
    package = repo / PACKAGE_REL
    shutil.copytree(FIXTURE, package)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "hook fixture")
    return repo, package


def run_hook(
    repo: Path,
    command: str,
    *arguments: str,
    payload: object | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK), command, *arguments],
        cwd=repo,
        input=None if payload is None else json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=child_env,
        check=False,
    )


def session_event(repo: Path, session_id: str, source: str = "startup", *, cwd: Path | None = None) -> dict[str, object]:
    return {
        "session_id": session_id,
        "transcript_path": None,
        "cwd": str((cwd or repo).resolve()),
        "hook_event_name": "SessionStart",
        "source": source,
        "permission_mode": "default",
    }


def pre_tool_event(repo: Path, command: str, *, tool_name: str = "apply_patch") -> dict[str, object]:
    return {
        "session_id": "hook-test-session",
        "cwd": str(repo.resolve()),
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_use_id": "tool-1",
        "tool_input": {"command": command},
        "permission_mode": "default",
    }


def binding_path(repo: Path, session_id: str) -> Path:
    value = Path(git(repo, "rev-parse", "--git-path", f"codex/impl-package-hooks/{session_id}.json"))
    return (value if value.is_absolute() else repo / value).resolve()


def activate(repo: Path, package: Path, session_id: str = "hook-session") -> subprocess.CompletedProcess[str]:
    return run_hook(
        repo,
        "activate",
        "--package",
        package.relative_to(repo).as_posix(),
        "--session-id",
        session_id,
    )


def assert_json_success(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stderr == ""
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)
    return parsed


def session_start(repo: Path, session_id: str, source: str = "startup", *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return run_hook(
        repo,
        "session-start",
        payload=session_event(repo, session_id, source, cwd=cwd),
    )


def capsule_text(result: subprocess.CompletedProcess[str]) -> str:
    output = assert_json_success(result)
    hook_output = output.get("hookSpecificOutput")
    assert isinstance(hook_output, dict)
    assert hook_output.get("hookEventName") == "SessionStart"
    context = hook_output.get("additionalContext")
    assert isinstance(context, str)
    assert "Impl-Package Resume Capsule v1" in context
    return context


def apply_patch(path: str, header: str = "Update File") -> str:
    return f"*** Begin Patch\n*** {header}: {path}\n@@\n+content\n*** End Patch\n"


def test_codex_manifest_and_hook_config_expose_only_the_two_approved_events() -> None:
    manifest = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["hooks"] == "./hooks/codex-hooks.json"

    config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert set(config["hooks"]) == {"PreToolUse", "SessionStart"}

    pre_tool = config["hooks"]["PreToolUse"][0]
    assert pre_tool["matcher"] == "^apply_patch$"
    pre_command = pre_tool["hooks"][0]
    assert pre_command["type"] == "command"
    assert "impl_package_hooks.py" in pre_command["command"]
    assert pre_command["command"].endswith('" pre-tool-use')
    assert pre_command["timeout"] == 5

    session = config["hooks"]["SessionStart"][0]
    assert session["matcher"] == "^(startup|resume|compact)$"
    session_command = session["hooks"][0]
    assert "impl_package_hooks.py" in session_command["command"]
    assert session_command["command"].endswith('" session-start')
    assert session_command["timeout"] == 10
    assert session_command["additionalContextLimit"] == 1200


def test_activate_writes_minimal_git_metadata_binding_and_deactivate_removes_it(tmp_path: Path) -> None:
    repo, package = make_repo(tmp_path)
    session_id = "activate-session"

    activated = assert_json_success(activate(repo, package, session_id))
    assert activated == {
        "status": "activated",
        "session_id": session_id,
        "package": PACKAGE_REL.as_posix(),
    }

    path = binding_path(repo, session_id)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": 1,
        "session_id": session_id,
        "repo_root": str(repo.resolve()),
        "package": PACKAGE_REL.as_posix(),
    }

    deactivated = assert_json_success(run_hook(repo, "deactivate", "--session-id", session_id))
    assert deactivated == {"status": "deactivated", "session_id": session_id}
    assert not path.exists()


def test_activate_accepts_codex_session_environment_and_isolates_sessions_and_worktrees(tmp_path: Path) -> None:
    repo, package = make_repo(tmp_path)
    session_a = "same-session"
    session_b = "other-session"

    assert_json_success(
        run_hook(
            repo,
            "activate",
            "--package",
            PACKAGE_REL.as_posix(),
            env={"CODEX_SESSION_ID": session_a},
        )
    )
    assert_json_success(activate(repo, package, session_b))
    assert binding_path(repo, session_a).is_file()
    assert binding_path(repo, session_b).is_file()

    worktree = tmp_path / "worktree"
    git(repo, "worktree", "add", "--detach", str(worktree))
    worktree_package = worktree / PACKAGE_REL
    assert_json_success(activate(worktree, worktree_package, session_a))

    worktree_binding = binding_path(worktree, session_a)
    assert worktree_binding != binding_path(repo, session_a)
    assert json.loads(worktree_binding.read_text(encoding="utf-8"))["repo_root"] == str(worktree.resolve())
    assert json.loads(binding_path(repo, session_a).read_text(encoding="utf-8"))["repo_root"] == str(repo.resolve())

    # A binding from another session must not leak into a SessionStart event in
    # the linked worktree.
    assert session_start(repo, session_a).stdout
    assert session_start(worktree, session_b, cwd=worktree).stdout == ""


def test_activate_rejects_outside_missing_state_and_fixture_packages(tmp_path: Path) -> None:
    repo, package = make_repo(tmp_path)

    outside = tmp_path / "outside"
    (outside / ".impl-package").mkdir(parents=True)
    (outside / ".impl-package" / "state.json").write_text("{}", encoding="utf-8")
    outside_result = run_hook(
        repo,
        "activate",
        "--package",
        str(outside),
        "--session-id",
        "outside-session",
    )
    assert outside_result.returncode != 0
    assert "inside the current Git worktree" in outside_result.stderr

    missing = repo / "docs/implementations/missing-package"
    missing.mkdir(parents=True)
    missing_result = run_hook(
        repo,
        "activate",
        "--package",
        missing.relative_to(repo).as_posix(),
        "--session-id",
        "missing-session",
    )
    assert missing_result.returncode != 0
    assert "missing .impl-package/state.json" in missing_result.stderr

    fixture = repo / "tests/fixtures/live-package"
    shutil.copytree(package, fixture)
    fixture_result = run_hook(
        repo,
        "activate",
        "--package",
        fixture.relative_to(repo).as_posix(),
        "--session-id",
        "fixture-session",
    )
    assert fixture_result.returncode != 0
    assert "fixtures" in fixture_result.stderr


def test_session_start_without_binding_or_with_mismatched_session_is_silent(tmp_path: Path) -> None:
    repo, package = make_repo(tmp_path)
    assert session_start(repo, "unbound-session").returncode == 0
    assert session_start(repo, "unbound-session").stdout == ""
    assert session_start(repo, "unbound-session").stderr == ""

    assert_json_success(activate(repo, package, "bound-session"))
    mismatched = session_start(repo, "different-session")
    assert mismatched.returncode == 0
    assert mismatched.stdout == ""
    assert mismatched.stderr == ""

    # The explicit hook also remains silent for SessionStart sources excluded by
    # the manifest matcher, such as a cleared session.
    assert session_start(repo, "bound-session", "clear").stdout == ""


@pytest.mark.parametrize("source", ["startup", "resume", "compact"])
def test_session_start_injects_read_only_resume_capsule_for_each_supported_source(tmp_path: Path, source: str) -> None:
    repo, package = make_repo(tmp_path)
    assert_json_success(activate(repo, package))
    credential = package / "execution" / "fixture-attempt" / "situation-digest.json"
    assert not credential.exists()

    context = capsule_text(session_start(repo, "hook-session", source))
    assert f"package: {PACKAGE_REL.as_posix()}" in context
    assert "attempt: fixture-attempt" in context
    assert re.search(r"head: [0-9a-f]{40}", context)
    assert "state-valid: true" in context
    assert "gate-verdict: blocked" in context
    assert re.search(r"preview-digest: [0-9a-f]{12}", context)
    assert "selected: " in context
    assert "parallel: " in context
    assert "actions: " in context
    assert re.search(r"warnings: \d+", context)
    assert re.search(r"undetermined: \d+", context)
    assert "not Evidence, Acceptance, Gate, or closure" in context
    assert "without --no-write-credential" in context
    assert not credential.exists()


def test_session_start_reports_render_failure_as_warning_without_blocking_the_session(tmp_path: Path) -> None:
    repo, package = make_repo(tmp_path)
    assert_json_success(activate(repo, package))
    (package / "situations.yaml").write_text("unknown: true\n", encoding="utf-8")

    result = session_start(repo, "hook-session")
    output = assert_json_success(result)
    assert set(output) == {"systemMessage"}
    assert output["systemMessage"].startswith("Impl-Package Hook warning:")
    assert "situations.yaml" in output["systemMessage"]


@pytest.mark.parametrize("header", ["Add File", "Update File", "Delete File"])
@pytest.mark.parametrize("separator", ["/", "\\"])
def test_pre_tool_use_denies_apply_patch_state_add_update_delete_for_live_packages(
    tmp_path: Path,
    header: str,
    separator: str,
) -> None:
    repo, _ = make_repo(tmp_path)
    relative = separator.join(PACKAGE_REL.parts + (".impl-package", "state.json"))
    result = run_hook(repo, "pre-tool-use", payload=pre_tool_event(repo, apply_patch(relative, header)))

    output = assert_json_success(result)
    hook_output = output["hookSpecificOutput"]
    assert isinstance(hook_output, dict)
    assert hook_output["hookEventName"] == "PreToolUse"
    assert hook_output["permissionDecision"] == "deny"
    assert "impl_package_state.py" in hook_output["permissionDecisionReason"]
    assert relative.replace("\\", "/") in hook_output["permissionDecisionReason"]


def test_pre_tool_use_denies_apply_patch_move_to_live_state(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    target = PACKAGE_REL.as_posix() + "/.impl-package/state.json"
    command = (
        "*** Begin Patch\n"
        "*** Update File: docs/implementations/hook-package/state-backup.json\n"
        "*** Move to: " + target + "\n"
        "@@\n"
        "+content\n"
        "*** End Patch\n"
    )
    result = run_hook(repo, "pre-tool-use", payload=pre_tool_event(repo, command))
    output = assert_json_success(result)
    hook_output = output["hookSpecificOutput"]
    assert isinstance(hook_output, dict)
    assert hook_output["permissionDecision"] == "deny"
    assert target in hook_output["permissionDecisionReason"]


def test_pre_tool_use_allows_unrelated_body_mentions_fixture_state_and_other_tools(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    cases = [
        apply_patch("README.md") + "\n# docs mention .impl-package/state.json\n",
        apply_patch("tests/fixtures/situations/example/.impl-package/state.json", "Update File"),
        apply_patch("docs/implementations/hook-package/.impl-package/progress.md", "Update File"),
    ]
    for command in cases:
        result = run_hook(repo, "pre-tool-use", payload=pre_tool_event(repo, command))
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    other_tool = run_hook(
        repo,
        "pre-tool-use",
        payload=pre_tool_event(repo, apply_patch(PACKAGE_REL.as_posix() + "/.impl-package/state.json"), tool_name="Bash"),
    )
    assert other_tool.returncode == 0
    assert other_tool.stdout == ""


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {}},
        {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": 42}},
    ],
)
def test_pre_tool_use_malformed_events_fail_open_with_optional_warning(tmp_path: Path, payload: object) -> None:
    repo, _ = make_repo(tmp_path)
    if isinstance(payload, str):
        result = subprocess.run(
            [sys.executable, str(HOOK), "pre-tool-use"],
            cwd=repo,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    else:
        result = run_hook(repo, "pre-tool-use", payload=payload)

    assert result.returncode == 0
    assert "permissionDecision" not in result.stdout
    if result.stdout:
        warning = json.loads(result.stdout)
        assert "systemMessage" in warning
