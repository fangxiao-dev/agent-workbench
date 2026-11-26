"""Host adapters: everything that knows how a particular agent host stores sessions.

The board core (sync, items, summaries, chat) only talks to this interface, so adding a host
(e.g. Codex) means writing one adapter instead of touching board logic.

    data source (host files/CLI)  ->  adapter  ->  board state (SQLite)  ->  board UI / tools
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
HEAD_BYTES = 256 * 1024
TAIL_BYTES = 256 * 1024


@dataclass(frozen=True)
class Source:
    """One transcript file as the adapter sees it."""
    path: Path
    ident: str
    entrypoint: str = ""
    human: int = 0
    fork_of: str = ""


class HostAdapter:
    """Contract for a session host. Implement these five operations and the board works."""

    name = "generic"

    def transcripts(self, home: Path) -> list[Path]:
        raise NotImplementedError

    def classify(self, path: Path) -> tuple[str, int, str]:
        """(entrypoint, human_started, session this file rewinds, forks or compacts from)"""
        raise NotImplementedError

    def live(self, home: Path) -> dict[str, dict]:
        """session id -> {status, link, name}; only sessions the host can confirm right now."""
        raise NotImplementedError

    def describe(self, source: Source) -> dict:
        """Host-specific fields stored per item; the core treats them as opaque."""
        return {"entrypoint": source.entrypoint, "human": source.human, "fork_of": source.fork_of}

    def is_background(self, title: str, entrypoint: str, human: int) -> bool:
        """Whether an item is a worker/sub session that should stay off the board."""
        return (entrypoint or "").startswith("sdk") or (not title and not human)


class ClaudeDesktopHost(HostAdapter):
    """Claude Code / Claude Desktop: JSONL transcripts under ~/.claude/projects plus a live-agent CLI."""

    name = "claude-desktop"

    def transcripts(self, home: Path) -> list[Path]:
        projects = home / "projects"
        if not projects.is_dir():
            return []
        return [p for p in projects.glob("*/*.jsonl") if UUID.fullmatch(p.stem)]

    def classify(self, path: Path) -> tuple[str, int, str]:
        entry, human, parent = "", -1, ""
        refs: dict[str, int] = {}

        def scan(block: bytes, meta: bool) -> None:
            nonlocal entry, human
            lines = block.splitlines()
            for line in (lines[:400] if meta else lines):
                try:
                    record = json.loads(line)
                except ValueError:  # includes the line cut off at the window edge
                    continue
                if not isinstance(record, dict):
                    continue
                if meta:
                    if not entry and isinstance(record.get("entrypoint"), str):
                        entry = record["entrypoint"][:40]
                    if human < 0 and record.get("type") == "user" and not record.get("isMeta"):
                        human = int(isinstance(record.get("origin"), dict))
                ref = record.get("requestSessionId")
                if isinstance(ref, str) and UUID.fullmatch(ref) and ref != path.stem:
                    refs[ref] = refs.get(ref, 0) + 1

        with path.open("rb") as stream:
            scan(stream.read(HEAD_BYTES), True)
            # Compaction starts a new transcript that replays the whole conversation and only then
            # points back at the episode it continues, so the newest link has to be read from the tail.
            size = path.stat().st_size
            if size > HEAD_BYTES:
                stream.seek(size - TAIL_BYTES)
                scan(stream.read().split(b"\n", 1)[-1], False)
        if refs:
            parent = max(refs, key=refs.get)
        return entry, max(human, 0), parent

    def live(self, home: Path) -> dict[str, dict]:
        result: dict[str, dict] = {}
        cli = shutil.which("claude") if home.resolve() == (Path.home() / ".claude").resolve() else None
        agents = None
        if cli:
            try:
                out = subprocess.run([cli, "agents", "--json", "--all"], capture_output=True, text=True,
                                     encoding="utf-8", timeout=10, check=True)
                rows = json.loads(out.stdout)
                if isinstance(rows, list):
                    agents = {r["sessionId"]: r for r in rows if isinstance(r, dict) and isinstance(r.get("sessionId"), str)}
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        for file in (home / "sessions").glob("*.json"):
            try:
                if file.is_symlink():
                    continue
                data = json.loads(file.read_text(encoding="utf-8"))
                ident, host = data.get("sessionId"), data.get("hostSessionId")
                if not isinstance(ident, str) or not UUID.fullmatch(ident):
                    continue
                observed = agents.get(ident) if agents is not None else (data if time.time() - file.stat().st_mtime <= 300 else None)
                if not observed:
                    continue
                status = "运行中" if observed.get("status") == "busy" else "空闲" if observed.get("status") == "idle" else "未知"
                conversation = host if isinstance(host, str) else ""
                link = "claude://claude.ai/epitaxy/" + conversation if re.fullmatch(r"local_[0-9a-f-]{36}", conversation, re.I) else ""
                # The Desktop conversation id outlives a compaction while the transcript id changes,
                # so it names the earlier transcript this one continues ("" once they are the same episode).
                previous = conversation[6:] if conversation and conversation[6:].lower() != ident.lower() else ""
                result[ident] = {"status": status, "link": link, "name": str(data.get("name") or "")[:200],
                                 "previous": previous}
            except (OSError, ValueError, TypeError):
                continue
        return result


HOSTS = {ClaudeDesktopHost.name: ClaudeDesktopHost}


def get_host(name: str = ClaudeDesktopHost.name) -> HostAdapter:
    try:
        return HOSTS[name]()
    except KeyError as exc:
        raise ValueError(f"未知宿主 {name}") from exc
