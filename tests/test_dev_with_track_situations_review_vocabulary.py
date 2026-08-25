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

    assert "/impl-package:do-review phase=initial" in text
    assert "/impl-package:do-review phase=terminal-final" in text
    assert "/impl-package:do-review phase=finding-closure" in text


def test_situations_reuse_same_topic_work_lane_for_findings_by_default() -> None:
    text = SITUATIONS.read_text(encoding="utf-8")

    assert "finding 回到同 Topic work lane 修复" in text
    assert "回到同 Topic work lane 直接修复" in text
