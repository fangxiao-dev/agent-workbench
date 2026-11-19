from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts"))
from impl_package_runtime import engine  # noqa: E402


def test_git_query_cache_reuses_result_within_command_scope(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "abc123\n", "")

    with patch.object(engine.subprocess, "run", side_effect=run):
        with engine.git_query_scope():
            assert engine._run_git(tmp_path, "rev-parse", "HEAD") == "abc123"
            assert engine._run_git(tmp_path, "rev-parse", "HEAD") == "abc123"

    assert len(calls) == 1


def test_git_query_cache_does_not_cross_command_scopes(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "abc123\n", "")

    with patch.object(engine.subprocess, "run", side_effect=run):
        for _ in range(2):
            with engine.git_query_scope():
                engine._run_git(tmp_path, "rev-parse", "HEAD")

    assert len(calls) == 2


def test_writing_a_hashed_file_invalidates_its_cached_blob(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, f"blob-{len(calls)}\n", "")

    with patch.object(engine.subprocess, "run", side_effect=run):
        with engine.git_query_scope():
            first = engine._run_git(tmp_path, "hash-object", "--", "tracked.md")
            assert engine._run_git(tmp_path, "hash-object", "--", "tracked.md") == first
            engine._write_text(tmp_path / "tracked.md", "changed\n")
            assert engine._run_git(tmp_path, "hash-object", "--", "tracked.md") == "blob-2"

            metrics_file = tmp_path / "metrics.json"
            first_metrics_hash = engine._run_git(tmp_path, "hash-object", "--", "metrics.json")
            assert engine._run_git(tmp_path, "hash-object", "--", "metrics.json") == first_metrics_hash
            engine._write_json(metrics_file, {})
            assert engine._run_git(tmp_path, "hash-object", "--", "metrics.json") == "blob-4"

    assert len(calls) == 4


def test_commit_to_commit_name_only_diff_is_cached_but_worktree_diff_is_not(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "a.py\0", "")

    a, b = "a" * 40, "b" * 40
    diff = ("diff", "--name-only", "--no-renames", "-z", a, b, "--", ".", ":!pkg")
    with patch.object(engine.subprocess, "run", side_effect=run):
        with engine.git_query_scope():
            engine._run_git_result(tmp_path, *diff)
            engine._run_git_result(tmp_path, "merge-base", "--is-ancestor", a, b)
            engine._run_git_result(tmp_path, *diff)  # still cached: only cacheable queries ran in between
            assert len(calls) == 2
            worktree = ("diff", "--name-only", "-z", "HEAD", "--", ".")
            engine._run_git_result(tmp_path, *worktree)
            engine._run_git_result(tmp_path, *worktree)
            assert len(calls) == 4
