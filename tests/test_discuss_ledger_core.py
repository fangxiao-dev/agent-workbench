from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "skills" / "discuss-ledger" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_core_preserves_ledger_commands_and_record_agent_turn_order(tmp_path: Path) -> None:
    from discuss_ledger_core import ledger

    result = ledger.init_ledger(
        root=tmp_path,
        topic="Architecture review",
        slug="arch",
        initiator="Codex",
        participants=["Codex", "Claude"],
    )

    assert "initialized round 1; next = Codex" in result.message

    ledger.add_point(
        root=tmp_path,
        slug="arch",
        author="Codex",
        summary="Keep CLI compatible",
        body="Existing users call the script directly.",
    )
    ledger.add_point(
        root=tmp_path,
        slug="arch",
        author="Codex",
        summary="Expose MCP tools",
        body="Hosts should be able to call tools without shell parsing.",
    )

    turn = ledger.record_agent_turn(
        root=tmp_path,
        slug="arch",
        author="Claude",
        convergences=[
            {
                "point": "D1",
                "marker": "一致",
                "line": "Keep the existing CLI command surface.",
            }
        ],
        contests=[
            {
                "point": "D2",
                "body": "The MCP server also needs resource coverage.",
                "movement": True,
            }
        ],
        new_points=[
            {
                "summary": "Orchestrator owns next speaker",
                "body": "Agents must not choose the next participant.",
            }
        ],
    )

    assert "converged D1" in turn.message
    assert "contested D2" in turn.message
    assert "added D3" in turn.message

    status = ledger.get_status(root=tmp_path, slug="arch")
    assert status.frontmatter["status"] == ledger.STATUS_OPEN
    assert status.frontmatter["round"] == 1

    markdown = ledger.read_markdown(root=tmp_path, slug="arch")
    assert markdown.index("[一致] Keep the existing CLI command surface.") < markdown.index("**D2**")
    assert markdown.index("**D2**") < markdown.index("**D3**")


def test_end_turn_and_set_next_remain_explicit(tmp_path: Path) -> None:
    from discuss_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Next speaker", slug="next", initiator="Codex")
    ledger.add_point(root=tmp_path, slug="next", author="Codex", summary="Needs Claude", body="Claude should answer.")
    ledger.end_turn(root=tmp_path, slug="next")

    status = ledger.get_status(root=tmp_path, slug="next")
    assert status.frontmatter["round"] == 2
    assert status.frontmatter["next"] == ledger.STATUS_WAITING_NEXT

    ledger.set_next(root=tmp_path, slug="next", next_agent="Claude")

    status = ledger.get_status(root=tmp_path, slug="next")
    assert status.frontmatter["next"] == "Claude"
    assert status.frontmatter["participants"] == ["Codex", "Claude"]
