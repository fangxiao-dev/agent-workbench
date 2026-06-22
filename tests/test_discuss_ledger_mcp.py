from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "skills" / "discuss-ledger" / "mcp_server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("discuss_ledger_mcp_under_test", SERVER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_mcp_tool_functions_delegate_to_core(tmp_path: Path) -> None:
    server = load_server()
    server.configure(root=tmp_path)

    init = server.init_ledger(topic="MCP direct", slug="mcp-direct", initiator="codex", participants=["codex"])
    assert "initialized round 1" in init["message"]

    added = server.add_point(
        slug="mcp-direct",
        author="codex",
        summary="Direct MCP wrapper",
        body="Tool functions should work without a subprocess.",
    )
    assert "added D1" in added["message"]

    status = server.get_status("mcp-direct")
    assert status["open_points"][0]["id"] == "D1"
    assert "Direct MCP wrapper" in server.markdown_resource("mcp-direct")


def test_create_server_registers_agent_visible_surface_without_set_next(monkeypatch, tmp_path: Path) -> None:
    server = load_server()
    registrations = {"tools": [], "resources": []}

    class FakeFastMCP:
        def __init__(self, name: str):
            self.name = name

        def tool(self):
            def register(func):
                registrations["tools"].append(func.__name__)
                return func

            return register

        def resource(self, uri: str):
            def register(func):
                registrations["resources"].append((uri, func.__name__))
                return func

            return register

    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)

    app = server.create_server(str(tmp_path), "docs/exchange/discuss")

    assert app.name == "discuss-ledger"
    assert registrations["tools"] == [
        "init_ledger",
        "get_status",
        "add_point",
        "contest_point",
        "converge_point",
        "end_turn",
        "record_agent_turn",
    ]
    assert "set_next" not in registrations["tools"]
    assert registrations["resources"] == [
        ("ledger://{slug}/state", "state_resource"),
        ("ledger://{slug}/markdown", "markdown_resource"),
        ("ledger://{slug}/open-points", "open_points_resource"),
        ("ledger://{slug}/convergence", "convergence_resource"),
    ]
