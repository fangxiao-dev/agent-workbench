"""Mermaid renderer and Markdown sync for the package mainline in pipeline.json."""

from __future__ import annotations

from pathlib import Path

DIAGRAM_BEGIN = "<!-- BEGIN:PIPELINE_DIAGRAM -->"
DIAGRAM_END = "<!-- END:PIPELINE_DIAGRAM -->"


def render_mermaid(pipeline: dict) -> str:
    lines = ["flowchart TD"]
    for stage in pipeline["stages"]:
        shape = '(["{}"])' if stage["id"] == pipeline["terminal"] else '["{}"]'
        lines.append(f"    {stage['id']}{shape.format(stage['label'])}")
    lines.append("")
    for edge in pipeline["transitions"]:
        lines.append(f'    {edge["src"]} -->|"{edge["label"]}"| {edge["dst"]}')
    return "\n".join(lines) + "\n"


def sync_markdown(path: str | Path, diagram: str, check_only: bool = False) -> bool:
    """Replace the marked block; return False when check_only finds it stale."""
    target = Path(path)
    content = target.read_text(encoding="utf-8")
    start, end = content.find(DIAGRAM_BEGIN), content.find(DIAGRAM_END)
    if start == -1 or end < start:
        raise ValueError(f"{target} 缺少图表标记 {DIAGRAM_BEGIN} ... {DIAGRAM_END}")
    block = f"{DIAGRAM_BEGIN}\n```mermaid\n{diagram.rstrip()}\n```\n{DIAGRAM_END}"
    updated = content[:start] + block + content[end + len(DIAGRAM_END):]
    if check_only:
        return updated == content
    if updated != content:
        target.write_text(updated, encoding="utf-8")
    return True
