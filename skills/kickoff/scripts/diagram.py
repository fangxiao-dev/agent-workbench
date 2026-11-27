"""Mermaid diagram rendering and Markdown synchronization for kickoff."""

import os

from .engine import CLI_SCRIPT_PATH, GATE_LABELS, PIPELINE, KickoffError

DIAGRAM_BEGIN = "<!-- BEGIN:PIPELINE_DIAGRAM -->"
DIAGRAM_END = "<!-- END:PIPELINE_DIAGRAM -->"


def render_mermaid(pipeline=PIPELINE):
    lines = ["flowchart TD"]
    terminal = pipeline["terminal"]
    initial = pipeline["initial"]
    limit = pipeline["convergence_limit"]
    gate_labels = pipeline.get("gate_labels", GATE_LABELS)

    for stage in pipeline["stages"]:
        stage_id = stage["id"]
        label = stage["label"]
        if stage.get("note"):
            label = f"{label}<br/>({stage['note']})"
        if stage_id == terminal:
            lines.append(f'    {stage_id}(["{label}"])')
        else:
            lines.append(f'    {stage_id}["{label}"]')

    lines.append("")

    for transition in pipeline["transitions"]:
        source, target = transition["src"], transition["dst"]
        arrow = "-.->" if transition.get("style") == "dashed" else "-->"
        conditions = [f"{key}={'on' if value else 'off'}" for key, value in transition.get("when", {}).items()]
        gates = [
            gate_labels.get(gate, gate)
            for gate in transition.get("gates", [])
            if gate != "owner_confirmed" or source == initial
        ]
        parts = []
        if conditions:
            parts.append(" & ".join(conditions))
        if gates:
            parts.append(" & ".join(gates))
        edge_label = "<br/>".join(parts)
        if edge_label:
            lines.append(f'    {source} {arrow}|"{edge_label}"| {target}')
        else:
            lines.append(f"    {source} {arrow} {target}")

    triage_nodes = [stage["id"] for stage in pipeline["stages"] if stage.get("triage")]
    if triage_nodes:
        lines.append("")
        for stage_id in triage_nodes:
            lines.append(f'    {stage_id} -->|"round (连续{limit}轮 added>0 警告)"| {stage_id}')

    return "\n".join(lines) + "\n"


def sync_markdown_diagram(md_path, diagram_text, check_only=False):
    if not os.path.isfile(md_path):
        raise KickoffError(f"Markdown 文件不存在: {md_path}")
    with open(md_path, "r", encoding="utf-8") as stream:
        content = stream.read()

    start_index = content.find(DIAGRAM_BEGIN)
    end_index = content.find(DIAGRAM_END)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise KickoffError(f"{md_path} 缺少图表标记 {DIAGRAM_BEGIN} ... {DIAGRAM_END}")

    fenced = f"{DIAGRAM_BEGIN}\n```mermaid\n{diagram_text.rstrip()}\n```\n{DIAGRAM_END}"
    updated = content[:start_index] + fenced + content[end_index + len(DIAGRAM_END):]

    if check_only:
        if updated != content:
            raise KickoffError(
                f"[diagram] {md_path} 中的流程图已过时，请运行：\n"
                f"  python {os.path.abspath(CLI_SCRIPT_PATH)} diagram --sync-md {md_path}",
                code=1,
                raw=True,
            )
        return f"[diagram] {md_path} 流程图已是最新。"

    if updated == content:
        return f"[diagram] {md_path} 无变化，已是最新。"

    with open(md_path, "w", encoding="utf-8") as stream:
        stream.write(updated)
    return f"[diagram] 已刷新 {md_path} 中的流程图。"
