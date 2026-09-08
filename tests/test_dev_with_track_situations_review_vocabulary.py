from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITUATIONS = (
    ROOT
    / "plugin-marketplace"
    / "plugins"
    / "impl-package"
    / "skills"
    / "dev-with-track"
    / "situations.yaml"
)


def test_situations_do_not_reference_retired_sdd_review_or_worker_vocabulary() -> None:
    text = SITUATIONS.read_text(encoding="utf-8")

    for retired in (
        "mode=review",
        "checkpoint|closure",
        "scope=closure",
        "scope=<",
        "worker=<",
    ):
        assert retired not in text


def test_situations_dispatch_review_through_do_review_phases_owned_by_do_review() -> None:
    text = SITUATIONS.read_text(encoding="utf-8")

    # `ticket.review_required`/`ticket.review_trigger` (T9-L) retired the fact-triggered
    # `phase=initial` situation slug; formal initial-review admission is SDD material-risk
    # judgment (do-review rubric R9), not a situations.yaml trigger. finding-closure and
    # terminal-final remain fact-triggered here.
    assert "/impl-package:do-review phase=terminal-final" in text
    assert "/impl-package:do-review phase=finding-closure" in text


def test_situations_schedule_confirmed_findings_as_independent_candidates() -> None:
    text = SITUATIONS.read_text(encoding="utf-8")

    assert text.count("finding 作为当前候选安排；可独立隔离时单独修复") == 2
    assert "/impl-package:subagent-driven-development" not in text
