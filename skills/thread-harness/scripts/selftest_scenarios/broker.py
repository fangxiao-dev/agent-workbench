"""Stage D-1 broker/profile/token/package selftest scenario."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selftest_support import *  # noqa: F401,F403,E402


def run() -> ScenarioResult:
    fails = 0
    print("-" * 78)
    # --- Stage D-1：profile fail-closed、solo routing、token budget 与 package adapter ---
    reset_fixture(git_worktrees=True)
    run_registry("init")
    registry = json.loads((BROKER / f"{CID}.json").read_text(encoding="utf-8"))
    registry.pop("broker", None)
    write_preflight_registry(registry)
    rc, out = run_registry("preflight")
    fails += check(
        "缺失 broker.profile 的 registry 必须由 preflight 阻断",
        rc == 5 and "broker_missing" in out,
        out.strip(),
    )

    registry["broker"] = {
        "profile": "invalid-profile",
        "budget": {"smart_zone_tokens": 150000, "tail_requests": 20, "tail_p75_increment_tokens": 1720},
    }
    write_preflight_registry(registry)
    rc, out = run_registry("preflight")
    fails += check(
        "非法 broker.profile 必须由 preflight 阻断",
        rc == 5 and "broker_invalid_profile" in out,
        out.strip(),
    )

    registry["broker"] = {
        "profile": "solo",
        "budget": {"smart_zone_tokens": 1000, "tail_requests": 2, "tail_p75_increment_tokens": 600},
    }
    write_preflight_registry(registry)
    rc, out = run_registry("preflight")
    fails += check(
        "非法 profile budget threshold 必须由 preflight 阻断",
        rc == 5 and "broker_invalid_handoff_threshold" in out,
        out.strip(),
    )

    registry, package_root, package_entry, package_state, package_record = make_solo_fixture()
    run_registry("init")
    valid_package_entry = registry["children"]["alpha"]["package_entry"]
    registry["children"]["alpha"].pop("package_entry")
    write_preflight_registry(registry)
    rc, out = run_registry("preflight")
    fails += check(
        "solo package entry 缺失时由 preflight 阻断",
        rc == 5 and "solo_package_entry_missing" in out,
        out.strip(),
    )
    registry["children"]["alpha"]["package_entry"] = valid_package_entry
    registry["children"]["alpha"]["package_entry"] = str((package_root / "missing-progress.md").resolve())
    write_preflight_registry(registry)
    rc, out = run_registry("preflight")
    fails += check(
        "solo package entry 无效时由 preflight 阻断",
        rc == 5 and "package_entry_invalid" in out,
        out.strip(),
    )
    registry["children"]["alpha"]["package_entry"] = valid_package_entry
    write_preflight_registry(registry)
    rc, out = run_registry("preflight")
    fails += check(
        "solo 唯一 task package entry 通过 preflight",
        rc == 0 and "PREFLIGHT OK" in out and "profile=solo" in out and "handoff_at=115600" in out,
        out.strip(),
    )

    package_state_35 = package_state.read_bytes()
    package_state.write_text(json.dumps({"formatVersion": "3.4"}) + "\n", encoding="utf-8")
    write_preflight_registry(registry)
    rc, out = run_registry("preflight")
    fails += check(
        "package schema 不一致只提示且不阻断 preflight",
        rc == 0 and "PREFLIGHT OK" in out and "package_schema_warning" in out,
        out.strip(),
    )
    package_state.write_bytes(package_state_35)
    write_preflight_registry(registry)

    package_before = {
        path: path.read_bytes()
        for path in (package_entry, package_state, package_record)
    }
    append_wait(CALL_ALPHA, one_projection("alpha", "solo-1"), call_id="solo-1")
    rc_sync, out_sync = run_registry("sync", "--round", "1")
    fails += check(
        "solo sync 输出 budget_stage 且不产生 assignment requeue",
        rc_sync == 0 and "budget_stage:    controller=tracking, alpha=tracking" in out_sync
        and "handoff_required: -" in out_sync and "reassignment_required: -" in out_sync,
        out_sync.strip(),
    )
    rc, out = run_registry(
        "act", "--dispatch", "--seam-id", "solo-dispatch", "--producer", "alpha",
        "--deliverable", "must be rejected",
    )
    fails += check(
        "solo H3 禁止 act --dispatch",
        rc == 64 and "solo profile does not support act --dispatch" in out,
        out.strip(),
    )

    append_child_token("alpha", 115600)
    append_wait(CALL_ALPHA, one_projection("alpha", "solo-2"), call_id="solo-2")
    rc, out = run_registry("sync", "--round", "2")
    fails += check(
        "token 达到 handoff_at 后 sync 标记 handoff_due",
        rc == 0 and "budget_stage:    controller=tracking, alpha=handoff_due" in out
        and "handoff_required: alpha" in out,
        out.strip(),
    )
    handoff_args = (
        "act", "--handoff", "--node", "alpha", "--source-session", NODES["controller"],
        "--reason", "token budget reached",
    )
    rc_first, out_first = run_registry(*handoff_args)
    acts_after_first = ledger_rows("acts.jsonl")
    rc_second, out_second = run_registry(*handoff_args)
    acts_after_second = ledger_rows("acts.jsonl")
    fails += check(
        "handoff action 只追加一次并对重复调用幂等",
        rc_first == 0 and "act handoff" in out_first and rc_second == 0
        and "already requested" in out_second
        and len([row for row in acts_after_first if row.get("kind") == "handoff"]) == 1
        and len([row for row in acts_after_second if row.get("kind") == "handoff"]) == 1,
        f"first={out_first.strip()} second={out_second.strip()}",
    )

    new_session = "019fbccc-5555-7000-8000-000000000005"
    (SESSIONS / f"rollout-2026-08-01T06-00-00-{new_session}.jsonl").touch()
    rc, out = run_registry("route", "--node", "alpha", "--new-session", new_session)
    new_call = call_for([new_session])
    new_projection = json.dumps({
        "v": 1,
        "n": 1,
        "wake": None,
        "polls": [{"id": new_session, "status": "notLoaded", "turn": "solo-new", "turnStatus": "completed", "txt": "new"}],
        "timedOut": False,
    }, ensure_ascii=False)
    append_wait(new_call, new_projection, call_id="solo-new-session")
    rc_new_sync, out_new_sync = run_registry("sync", "--round", "3")
    fails += check(
        "route 到新 session 后重新建立 budget baseline",
        rc == 0 and rc_new_sync == 0 and "budget_stage:    controller=tracking, alpha=tracking" in out_new_sync
        and "handoff_required: -" in out_new_sync,
        f"route={out.strip()} sync={out_new_sync.strip()}",
    )

    facts = read_package_facts(str(package_entry), current_session_id=NODES["alpha"])
    fails += check(
        "package adapter 读取前后 package 字节保持不变",
        facts["package_entry"] == str(package_entry.resolve())
        and facts["active_checkpoint"] == str(package_record.resolve())
        and facts["next_action"] == "bounded action"
        and {path: path.read_bytes() for path in (package_entry, package_state, package_record)} == package_before,
        json.dumps(facts, ensure_ascii=False),
    )
    shutil.rmtree(BASE, ignore_errors=True)
    print("=" * 78)
    print(f"FAILURES: {fails}")
    return ScenarioResult("broker", fails)


if __name__ == "__main__":
    raise SystemExit(run().returncode)
