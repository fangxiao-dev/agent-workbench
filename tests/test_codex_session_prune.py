from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import codex_session_prune as prune


def raw_thread(
    thread_id: str,
    *,
    cwd: str | None = r"D:\CodeSpace\agent-workbench",
    updated: int | float | str | None = 1,
    created: int = 1,
    archived: bool = False,
    parent: str | None = None,
    source: str = "cli",
) -> dict[str, object]:
    return {
        "id": thread_id,
        "cwd": cwd,
        "createdAt": created,
        "updatedAt": updated,
        "parentThreadId": parent,
        "source": source,
        "sourceKind": source,
        "archived": archived,
    }


class FakeSession:
    def __init__(self, *, descendants: dict[str, dict[bool, list[dict[str, object]]]] | None = None) -> None:
        self.calls: list[tuple[int, str, dict[str, object]]] = []
        self.descendants = descendants or {}
        self.deleted: list[str] = []
        self.fail_delete: str | None = None

    def request(self, request_id: int, method: str, params: dict[str, object], timeout: float):
        self.calls.append((request_id, method, params))
        if method == "thread/list":
            ancestor = params.get("ancestorThreadId")
            if ancestor is not None:
                archived = bool(params["archived"])
                return {"data": self.descendants.get(str(ancestor), {}).get(archived, []), "nextCursor": None}, []
            return {"data": [], "nextCursor": None}, []
        if method == "thread/loaded/list":
            return {"data": []}, []
        if method == "thread/delete":
            thread_id = str(params["threadId"])
            if thread_id == self.fail_delete:
                raise RuntimeError("simulated delete failure")
            self.deleted.append(thread_id)
            return {}, []
        if method == "initialize":
            return {}, []
        raise AssertionError(f"unexpected RPC {method}")

    def close(self) -> None:
        return None


@contextmanager
def fake_context(session: FakeSession):
    yield session


def make_info(raw: dict[str, object], archived: bool = False) -> prune.ThreadInfo:
    return prune.thread_info({**raw, "archived": archived}, archived)


def empty_descendants(*roots: str) -> FakeSession:
    return FakeSession(descendants={root: {False: [], True: []} for root in roots})


def test_inventory_rows_group_active_archived_and_unknown() -> None:
    threads = [
        make_info(raw_thread("a", updated=1), False),
        make_info(raw_thread("b", updated=2), True),
        make_info(raw_thread("c", cwd=None, updated=3), True),
    ]
    assert prune.inventory_rows(threads) == [
        {"project": r"d:\codespace\agent-workbench", "active": 1, "archived": 1, "total": 2},
        {"project": prune.UNKNOWN_PROJECT, "active": 0, "archived": 1, "total": 1},
    ]


def test_collect_rollout_usage_indexes_file_sizes_without_reading_contents(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions" / "2026" / "05"
    archived = tmp_path / "archived_sessions"
    sessions.mkdir(parents=True)
    archived.mkdir()
    (sessions / "rollout-2026-05-01T00-00-00-thr_a.jsonl").write_bytes(b"12345")
    (archived / "rollout-2026-05-02T00-00-00-thr_a.jsonl").write_bytes(b"123")
    (sessions / "rollout-2026-05-03T00-00-00-thr_b.jsonl").write_bytes(b"12")

    usage = prune.collect_rollout_usage(tmp_path)

    assert usage.sizes == {"thr_a": 8, "thr_b": 2}
    assert usage.files == 3
    assert usage.total_bytes == 10
    assert not usage.errors


def test_inventory_rows_include_rollout_sizes_when_requested() -> None:
    threads = [
        make_info(raw_thread("a", updated=1), False),
        make_info(raw_thread("b", updated=2), True),
    ]
    assert prune.inventory_rows(threads, {"a": 1024, "b": 2048}) == [
        {
            "project": r"d:\codespace\agent-workbench",
            "active": 1,
            "archived": 1,
            "total": 2,
            "disk_size_bytes": 3072,
        }
    ]


def test_plan_reports_affected_rollout_size() -> None:
    root = make_info(raw_thread("root", updated=1))
    session = FakeSession(descendants={"root": {False: [raw_thread("child", parent="root", updated=2)], True: []}})
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        [root],
        [],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="active",
        take=1,
        max_affected=10,
        rollout_sizes={"root": 100, "child": 50},
        include_disk_size=True,
    )
    payload = plan.as_dict()
    assert payload["disk_size_bytes"] == 150
    assert payload["disk_size"] == "150 B"
    assert payload["details"][0]["root"]["disk_size_bytes"] == 100
    assert payload["details"][0]["descendants"][0]["disk_size_bytes"] == 50


def test_windows_project_comparison_ignores_case_and_separators() -> None:
    assert prune.normalize_project(r"D:/CodeSpace/Agent-Workbench") == r"d:\codespace\agent-workbench"
    assert prune.normalize_project(r"d:\codespace\agent-workbench") == r"d:\codespace\agent-workbench"


def test_paginate_threads_uses_all_source_kinds_and_pages() -> None:
    class PagingSession(FakeSession):
        def request(self, request_id: int, method: str, params: dict[str, object], timeout: float):
            self.calls.append((request_id, method, params))
            assert method == "thread/list"
            assert params["sourceKinds"] == list(prune.ALL_SOURCE_KINDS)
            assert params["useStateDbOnly"] is True
            assert params["sortKey"] == "updated_at"
            assert params["sortDirection"] == "asc"
            if params["cursor"] is None:
                return {"data": [raw_thread("first")], "nextCursor": "page-2"}, []
            return {"data": [raw_thread("second", updated=2)], "nextCursor": None}, []

    session = PagingSession()
    items = prune.paginate_threads(session, prune.RequestIds(), archived=False)
    assert [item.id for item in items] == ["first", "second"]
    assert [call[2]["cursor"] for call in session.calls] == [None, "page-2"]


def test_take_selects_oldest_eligible_roots() -> None:
    roots = [
        make_info(raw_thread("new", updated=30)),
        make_info(raw_thread("old", updated=10)),
        make_info(raw_thread("middle", updated=20)),
    ]
    session = empty_descendants("new", "old", "middle")
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        roots,
        [],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="active",
        take=2,
        max_affected=10,
    )
    assert [candidate.root.id for candidate in plan.selected] == ["old", "middle"]


def test_pinned_loaded_registry_roots_are_not_selected() -> None:
    roots = [make_info(raw_thread("pinned", updated=1)), make_info(raw_thread("loaded", updated=2)), make_info(raw_thread("registry", updated=3)), make_info(raw_thread("ok", updated=4))]
    session = empty_descendants("pinned", "loaded", "registry", "ok")
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        roots,
        ["loaded"],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="active",
        take=4,
        max_affected=10,
        pinned_ids=["pinned"],
        registry_ids=["registry"],
    )
    assert [candidate.root.id for candidate in plan.selected] == ["ok"]
    reasons = {candidate.root.id: candidate.reasons for candidate in plan.roots}
    assert reasons["pinned"] == ["pinned"]
    assert reasons["loaded"] == ["loaded"]
    assert reasons["registry"] == ["registry"]


def test_descendants_are_expanded_and_affected_ids_are_deduplicated() -> None:
    root = make_info(raw_thread("root", updated=1))
    children = {
        "root": {
            False: [raw_thread("child", updated=2, parent="root")],
            True: [raw_thread("grandchild", updated=3, parent="child")],
        }
    }
    session = FakeSession(descendants=children)
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        [root],
        [],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="all",
        take=1,
        max_affected=10,
    )
    assert plan.affected_ids == ["child", "grandchild", "root"]
    assert plan.total_affected == 3
    assert len(plan.selected[0].descendants) == 2


def test_protected_descendant_rejects_whole_root() -> None:
    root = make_info(raw_thread("root", updated=1))
    session = FakeSession(descendants={"root": {False: [raw_thread("child", parent="root", updated=2)], True: []}})
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        [root],
        ["child"],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="active",
        take=1,
        max_affected=10,
    )
    assert not plan.selected
    assert "descendant_loaded" in plan.roots[0].reasons


def test_cross_project_and_cross_state_descendant_are_rejected() -> None:
    root = make_info(raw_thread("root", updated=1), False)
    session = FakeSession(
        descendants={
            "root": {
                False: [],
                True: [raw_thread("child", cwd=r"D:\other", parent="root", updated=2, archived=True)],
            }
        }
    )
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        [root],
        [],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="active",
        take=1,
        max_affected=10,
    )
    assert not plan.selected
    assert "cross_project" in plan.roots[0].reasons
    assert "cross_archive_state" in plan.roots[0].reasons


def test_max_affected_blocks_apply_without_reducing_take() -> None:
    root = make_info(raw_thread("root", updated=1))
    session = FakeSession(descendants={"root": {False: [raw_thread("child", parent="root", updated=2)], True: []}})
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        [root],
        [],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="active",
        take=1,
        max_affected=1,
    )
    assert [candidate.root.id for candidate in plan.selected] == ["root"]
    assert plan.total_affected == 2
    assert not plan.apply_allowed
    assert not session.deleted


def test_unknown_project_is_never_selected_even_for_all_projects() -> None:
    root = make_info(raw_thread("unknown", cwd=None, updated=1))
    plan = prune.build_prune_plan(
        empty_descendants("unknown"),
        prune.RequestIds(),
        [root],
        [],
        project_filters=[],
        all_projects=True,
        archive_state="active",
        take=1,
        max_affected=10,
    )
    assert not plan.selected
    assert plan.roots[0].reasons == ["unknown_project"]


def test_plan_hash_is_stable_and_order_independent() -> None:
    first = prune.compute_plan_id(["b", "a"], ["c", "a", "b"], ["d:/x", "d:/y"], "active", 2, 10)
    second = prune.compute_plan_id(["a", "b"], ["b", "c", "a"], ["d:/y", "d:/x"], "active", 2, 10)
    assert first == second


def test_load_pinned_ids_reports_malformed_guard(tmp_path: Path) -> None:
    state = tmp_path / ".codex-global-state.json"
    state.write_text("{not-json", encoding="utf-8")
    ids, error = prune.load_pinned_ids(state)
    assert ids == set()
    assert error and "cannot read pinned-thread-ids" in error


def test_registry_loader_extracts_json_and_uuid_references(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"threadId": "fake-root", "nested": {"session_id": "fake-child"}})
        + "\n019f0000-0000-7000-8000-000000000001\n",
        encoding="utf-8",
    )
    assert prune.load_registry_ids([registry]) == {
        "fake-root",
        "fake-child",
        "019f0000-0000-7000-8000-000000000001",
    }


def test_default_dry_run_never_calls_thread_delete() -> None:
    parser = prune.build_parser()
    args = parser.parse_args(
        ["--project", r"D:\CodeSpace\agent-workbench", "--archive-state", "active", "--take", "1", "--max-affected", "10"]
    )
    session = empty_descendants()
    with patch.object(prune, "load_pinned_ids", return_value=(set(), None)), patch.object(prune, "load_registry_ids", return_value=set()):
        result = prune.run(args, lambda: fake_context(session))
    assert result == 0
    assert not any(method == "thread/delete" for _, method, _ in session.calls)


def test_apply_plan_drift_rejects_without_deleting() -> None:
    parser = prune.build_parser()
    args = parser.parse_args(
        [
            "--project",
            r"D:\CodeSpace\agent-workbench",
            "--archive-state",
            "active",
            "--take",
            "1",
            "--max-affected",
            "10",
            "--apply",
            "--expect-plan",
            "sha256:wrong",
        ]
    )
    session = empty_descendants()
    with patch.object(prune, "load_pinned_ids", return_value=(set(), None)), patch.object(prune, "load_registry_ids", return_value=set()):
        result = prune.run(args, lambda: fake_context(session))
    assert result == 2
    assert not session.deleted


def test_apply_stops_after_first_delete_failure_and_reports_remaining() -> None:
    parser = prune.build_parser()
    args = parser.parse_args(
        [
            "--project",
            r"D:\CodeSpace\agent-workbench",
            "--archive-state",
            "active",
            "--take",
            "2",
            "--max-affected",
            "10",
            "--apply",
            "--expect-plan",
            "sha256:placeholder",
        ]
    )
    roots = [raw_thread("first", updated=1), raw_thread("second", updated=2)]

    class ApplySession(FakeSession):
        def __init__(self) -> None:
            super().__init__(descendants={"first": {False: [], True: []}, "second": {False: [], True: []}})
            self.list_round = 0

        def request(self, request_id: int, method: str, params: dict[str, object], timeout: float):
            self.calls.append((request_id, method, params))
            if method == "thread/list" and params.get("ancestorThreadId") is None:
                archived = bool(params["archived"])
                if archived:
                    return {"data": [], "nextCursor": None}, []
                self.list_round += 1
                data = roots if self.list_round == 1 else roots
                return {"data": data, "nextCursor": None}, []
            if method == "thread/list":
                return {"data": [], "nextCursor": None}, []
            if method == "thread/loaded/list":
                return {"data": []}, []
            if method == "thread/delete":
                self.deleted.append(str(params["threadId"]))
                if params["threadId"] == "second":
                    raise RuntimeError("failed second")
                return {}, []
            raise AssertionError(method)

    session = ApplySession()
    # First calculate the plan ID against the same data and then force the second delete to fail.
    plan = prune.build_prune_plan(
        session,
        prune.RequestIds(),
        [make_info(roots[0]), make_info(roots[1])],
        [],
        project_filters=[r"d:\codespace\agent-workbench"],
        all_projects=False,
        archive_state="active",
        take=2,
        max_affected=10,
    )
    args.expect_plan = plan.plan_id
    session.list_round = 0
    with patch.object(prune, "load_pinned_ids", return_value=(set(), None)), patch.object(prune, "load_registry_ids", return_value=set()):
        result = prune.run(args, lambda: fake_context(session))
    assert result == 1
    assert session.deleted == ["first", "second"]


def test_argument_validation_requires_complete_candidate_selector() -> None:
    parser = prune.build_parser()
    args = parser.parse_args(["--project", r"D:\CodeSpace\agent-workbench", "--take", "1"])
    with pytest.raises(SystemExit):
        prune._validate_args(parser, args)
