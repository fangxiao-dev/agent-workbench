from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "discuss-ledger" / "scripts"
ROUTER = SCRIPTS / "discuss_router.py"


def load_router():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("discuss_router_under_test", ROUTER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_router_defaults_to_ledger_with_original_two_participants() -> None:
    router = load_router()
    args = router.build_parser().parse_args(["--topic", "Target"])

    assert args.mode == "ledger"
    assert router.resolve_agents(args.agents) == ["codex", "claude"]


def test_router_accepts_full_or_an_explicit_pair_only() -> None:
    router = load_router()

    assert router.resolve_agents("full") == ["codex", "claude", "grok"]
    assert router.resolve_agents("grok,codex") == ["grok", "codex"]
    for invalid in ("codex", "codex,claude,grok", "codex,codex"):
        try:
            router.resolve_agents(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid router participants: {invalid}")


def test_router_dispatches_modes_without_mixing_mode_and_participant_selection(monkeypatch) -> None:
    router = load_router()
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(router.orchestrator, "main", lambda argv: calls.append(("ledger", argv)) or 10)
    monkeypatch.setattr(router.blind_opening, "main", lambda argv: calls.append(("blind", argv)) or 11)
    monkeypatch.setattr(router.blind_opening_then_ledger, "main", lambda argv: calls.append(("combined", argv)) or 12)

    assert router.main(["--topic", "T"]) == 10
    assert router.main(["--mode", "blind", "--agents", "codex,grok", "--topic", "T"]) == 11
    assert router.main(["--mode", "combined", "--agents", "full", "--topic", "T"]) == 12

    assert calls[0] == ("ledger", ["--root", ".", "--topic", "T", "--agents", "codex,claude", "--timeout-s", "300", "--max-rounds", "5"])
    assert calls[1][0] == "blind" and "codex,grok" in calls[1][1] and "--max-rounds" not in calls[1][1]
    assert calls[2][0] == "combined" and "codex,claude,grok" in calls[2][1] and "--max-rounds" in calls[2][1]
