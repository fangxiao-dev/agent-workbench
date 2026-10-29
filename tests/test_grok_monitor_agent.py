from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agents" / "grok-monitor"


def test_grok_monitor_profile_is_luna_max_and_reports_each_target_independently() -> None:
    config = (AGENT_DIR / "grok-monitor.toml").read_text(encoding="utf-8")
    contract = (AGENT_DIR / "agent.md").read_text(encoding="utf-8")

    assert 'model = "gpt-6-luna"' in config
    assert 'model_reasoning_effort = "max"' in config
    assert "[features]\nfast_mode = true" in config
    assert "Track every target independently" in contract
    assert "as one batch every 3 minutes" in contract
    assert "one compact batch progress brief every 6 minutes" in contract
    assert "collaboration.send_message" in contract
    assert "never wait for the whole set" in contract
    assert "grok-progress:" in contract
    assert "diff --name-status" in contract
    assert "Never read\nor send full diff contents" in contract
    assert "lightweight read-only Git summaries" in config
    assert "Never start" in contract
    assert "terminate Grok" in contract
