from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agents" / "grok-monitor"


def test_grok_monitor_profile_is_luna_max_and_reports_each_target_independently() -> None:
    config = (AGENT_DIR / "grok-monitor.toml").read_text(encoding="utf-8")
    contract = (AGENT_DIR / "agent.md").read_text(encoding="utf-8")

    assert 'model = "gpt-5.6-luna"' in config
    assert 'model_reasoning_effort = "max"' in config
    assert "[features]\nfast_mode = true" in config
    assert "Track every target independently" in contract
    assert "every 60 seconds by default" in contract
    assert "collaboration.send_message" in contract
    assert "never wait for the whole set" in contract
    assert "Never start" in contract
    assert "terminate Grok" in contract
