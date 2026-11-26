"""Mermaid diagram renderer and Markdown sync helper for kickoff."""

import os
import sys

from engine import CLI_SCRIPT_PATH, GATE_LABELS, PIPELINE, fail

DIAGRAM_BEGIN = "<!-- BEGIN:PIPELINE_DIAGRAM -->"
DIAGRAM_END = "<!-- END:PIPELINE_DIAGRAM -->"


def render_mermaid(pipeline=PIPELINE):
    lines = ["flowchart TD"]
    terminal = pipeline["terminal"]
    initial = pipeline["initial"]
    limit = pipeline["convergence_limit"]
    gate_labels = pipeline.get("gate_labels", GATE_LABELS)

    for st in pipeline["stages"]:
        sid = st["id"]
        label = st["label"]
        if st.get("note"):
            label = f"{label}<br/>({st['note']})"
        if sid == terminal:
            lines.append(f'    {sid}(["{label}"])')
        else:
            lines.append(f'    {sid}["{label}"]')

    lines.append("")

    for t in pipeline["transitions"]:
        src, dst = t["src"], t["dst"]
        arrow = "-.->" if t.get("style") == "dashed" else "-->"
        conds = [f"{k}={'on' if v else 'off'}" for k, v in t.get("when", {}).items()]
        gates = [
            gate_labels.get(g, g)
            for g in t.get("gates", [])
            if g != "owner_confirmed" or src == initial
        ]
        parts = []
        if conds:
            parts.append(" & ".join(conds))
        if gates:
            parts.append(" & ".join(gates))
        edge_label = "<br/>".join(parts)
        if edge_label:
            lines.append(f'    {src} {arrow}|"{edge_label}"| {dst}')
        else:
            lines.append(f"    {src} {arrow} {dst}")

    triage_nodes = [st["id"] for st in pipeline["stages"] if st.get("triage")]
    if triage_nodes:
        lines.append("")
        for sid in triage_nodes:
            lines.append(f'    {sid} -->|"round (连续{limit}轮 added>0 警告)"| {sid}')

    return "\n".join(lines) + "\n"


def sync_markdown_diagram(md_path, diagram_text, check_only=False):
    if not os.path.isfile(md_path):
        fail(f"Markdown 文件不存在: {md_path}")
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    start_idx = content.find(DIAGRAM_BEGIN)
    end_idx = content.find(DIAGRAM_END)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        fail(f"{md_path} 缺少图表标记 {DIAGRAM_BEGIN} ... {DIAGRAM_END}")

    fenced = f"{DIAGRAM_BEGIN}\n```mermaid\n{diagram_text.rstrip()}\n```\n{DIAGRAM_END}"
    updated = content[:start_idx] + fenced + content[end_idx + len(DIAGRAM_END):]

    if check_only:
        if updated != content:
            print(
                f"[diagram] {md_path} 中的流程图已过时，请运行：\n"
                f"  python {os.path.abspath(CLI_SCRIPT_PATH)} diagram --sync-md {md_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[diagram] {md_path} 流程图已是最新。")
        return

    if updated == content:
        print(f"[diagram] {md_path} 无变化，已是最新。")
        return

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"[diagram] 已刷新 {md_path} 中的流程图。")
