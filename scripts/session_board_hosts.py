"""Host adapters: everything that knows how a particular agent host stores sessions.

The board core (sync, items, summaries, chat) only talks to this interface, so adding a host
(e.g. Codex) means writing one adapter instead of touching board logic.

    data source (host files/CLI)  ->  adapter  ->  board state (SQLite)  ->  board UI / tools
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
HEAD_BYTES = 256 * 1024
TAIL_BYTES = 256 * 1024
REF = re.compile(rb'"requestSessionId"\s*:\s*"([0-9a-f-]{36})"', re.I)


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

    worker_paths: tuple[str, ...] = ()
    uses_temp = False          # True for hosts whose one-off workers run in the OS temp dir
    injected_prefixes: tuple[str, ...] = ()   # harness traffic that looks like a user line but is not

    def hints(self, record: dict) -> tuple[str, str]:
        """(title, cwd) carried by one transcript line; either may be empty."""
        return "", ""

    def message(self, record: dict) -> tuple[str, str, str] | None:
        """(role, text, timestamp) when the line is conversation; None for bookkeeping and wrappers."""
        return None

    def clean_text(self, text: str) -> str:
        """Undo this host's storage wrappers before text is shown."""
        return text

    def is_background(self, title: str, entrypoint: str, human: int, cwd: str = "") -> bool:
        """Whether an item is a worker/sub session that should stay off the board."""
        if (entrypoint or "").startswith("sdk") or (not title and not human):
            return True
        roots = (tempfile.gettempdir(), *self.worker_paths) if self.uses_temp else self.worker_paths
        return any(under(cwd, root) for root in roots)


def under(path: str, root: str) -> bool:
    if not path or not root:
        return False
    return os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(os.path.abspath(root)) + os.sep)


PASTED = re.compile(r"^<pasted_content[^>]*>\s*", re.I)
INJECTED_TAG = re.compile(r"^<[a-z][a-z0-9_-]*[\s>]", re.I)


def user_text(record: dict) -> str:
    """The text a transcript line carries, with this host's paste wrapper removed."""
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = chr(10).join(str(block.get("text", "")) for block in content
                            if isinstance(block, dict) and block.get("type") == "text")
    else:
        return ""
    return strip_pasted(text).lstrip()


def strip_pasted(text: str) -> str:
    text = PASTED.sub("", str(text).strip()).strip()
    if text.lower().endswith("</pasted_content>"):
        text = text[:-len("</pasted_content>")].strip()
    return text


class ClaudeDesktopHost(HostAdapter):
    """Claude Code / Claude Desktop: JSONL transcripts under ~/.claude/projects plus a live-agent CLI."""

    name = "claude-desktop"
    uses_temp = True   # one-off CLI workers (magpie and friends) run inside the OS temp dir
    # Harness traffic that arrives as a "user" line but is not the human: system notices, command echoes,
    # relays between sessions. Extend here rather than editing the parser.
    injected_prefixes = ("[Request interrupted", "[SYSTEM NOTIFICATION", "[SUGGESTION MODE",
                         "Another Claude session sent a message")

    def hints(self, record: dict) -> tuple[str, str]:
        title = record.get("customTitle") if record.get("type") == "custom-title" else None
        cwd = record.get("cwd")
        return (title[:200] if isinstance(title, str) else "",
                cwd[:1000] if isinstance(cwd, str) else "")

    def message(self, record: dict) -> tuple[str, str, str] | None:
        kind = record.get("type")
        if kind not in ("user", "assistant") or record.get("isSidechain") or record.get("isMeta"):
            return None
        message = record.get("message")
        if not isinstance(message, dict) or message.get("role") != kind:
            return None
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = chr(10).join(str(block.get("text", "")) for block in content
                             if isinstance(block, dict) and block.get("type") == "text")
        else:
            return None
        text = strip_pasted(text)
        # Injected wrappers (<task-notification>, <system-reminder>, ...) are not conversation.
        if not text or (kind == "user" and (INJECTED_TAG.match(text) or text.startswith(self.injected_prefixes))):
            return None
        if kind == "assistant" and text.lower().rstrip(".") == "no response requested":
            return None
        return kind, text[:2000], str(record.get("timestamp") or "")[:40]

    def clean_text(self, text: str) -> str:
        return strip_pasted(text)

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
                        # A worker launched by another agent gets its whole brief as the first "user"
                        # turn — a pasted block starting with "Human:" and carrying a system prompt, or
                        # a history dump. It carries an origin, but the human did not start it.
                        text = user_text(record)
                        launched = text.startswith(("Human:", "<conversation_history"))
                        human = int(isinstance(record.get("origin"), dict) and not launched)
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
            if not refs and size > HEAD_BYTES:
                # Compaction and forks replay the history, so the pointer back sits mid-file and only
                # a full pass finds it. This runs once per transcript, when the item is first seen.
                stream.seek(0)
                for match in REF.finditer(stream.read()):
                    ref = match.group(1).decode().lower()
                    if ref != path.stem:
                        refs[ref] = refs.get(ref, 0) + 1
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
