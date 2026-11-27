"""Human-readable text for kickoff command results."""


def optional_tools_lines(optional_tools):
    if not optional_tools:
        return []
    lines = ["[可选工具（不卡门禁）]"]
    for tool in optional_tools:
        lines.append(f"  - {tool['name']}")
        if tool.get("when"):
            lines.append(f"    when: {tool['when']}")
        if tool.get("fallback"):
            lines.append(f"    fallback: {tool['fallback']}")
    return lines


def init_text(result):
    state = result["state"]
    switches = state["switches"]
    lines = [
        f"[init] 状态文件: {result['path']}",
        f"  目标: {state['goal'] or '(未填写)'}",
        f"  调研材料: {', '.join(result['research']) if result['research'] else '(空)'}",
        f"  原型: {result['prototype']}" + ("  (none=无原型)" if result["prototype"] == "none" else ""),
        f"  Docs: {', '.join(state['docs']) if state['docs'] else '(无)'}",
        "  环节开关: "
        f"discover={'on' if switches['discover'] else 'off'}, "
        f"pe={'on' if switches['pe'] else 'off'}, "
        f"plan={'on' if switches['plan'] else 'off'}",
        "  落点: " + (
            f"已绑定 pkg_dir  {state['pkg_dir']}"
            if state["pkg_dir"]
            else f"暂存(待 bind-pkg)  {state['staging_path']}"
        ),
        "\n[Step 0 原则]",
    ]
    lines.extend(f"  - {line}" for line in result["principles"])
    lines.append(f"\n下一步: {result['next_command']}")
    return "\n".join(lines)


def confirm_text(result):
    message = "Owner 已确认过，继续。" if result["already_confirmed"] else "Owner 已确认，owner_confirmed=true。"
    return f"{message}\n下一步: {result['next_command']}"


def register_text(result):
    if result["kind"] == "plan-reviewer-existing":
        tag = f" ({result['label']})" if result["label"] else ""
        return (
            f"[register] plan-reviewer 已存在并保留: {result['agent_id']}{tag}"
            f"（共 {result['count']} 位）"
        )
    if result["kind"] == "plan-reviewer-added":
        tag = f" ({result['label']})" if result["label"] else ""
        return f"[register] plan-reviewer += {result['agent_id']}{tag}（共 {result['count']} 位）"
    warning = ""
    if result["previous"] and result["previous"] != result["agent_id"]:
        warning = (
            f"[警告] 正在替换已登记的 {result['role']} "
            f"({result['previous']} -> {result['agent_id']})，"
            "确认不是误开新代理破坏续用原则。\n"
        )
    return f"{warning}[register] {result['role']} = {result['agent_id']}"


def bind_pkg_text(result):
    return (
        f"[bind-pkg] 已绑定 pkg_dir: {result['package']}\n"
        f"  状态文件: {result['path']}\n"
        f"下一步: {result['next_command']}"
    )


def round_text(result):
    entry = result["entry"]
    counts = entry["counts"]
    upstream_tag = " [touched-upstream]" if result["touched_upstream"] else ""
    lines = [
        f"[round] {result['stage']} #{entry['round']} [{entry['verdict']}]{upstream_tag}: "
        f"added={counts['added']} cut={counts['cut']} pe={counts['pe']} rejected={counts['rejected']} "
        f"— {entry['summary']}"
    ]
    if result["touched_upstream"]:
        lines.append(
            "\n[上游变更提醒] 本轮回改了上游合同（Decision / Spec / contract-design），\n"
            "  请重跑 check-spec 等确定性校验，并确认受影响合同条款已完成复验。"
        )
    if result["convergence_warning"]:
        lines.append(
            f"\n[收敛警告] 同一阶段连续 {result['convergence_limit']} 轮都在新增分支，停止继续加分支。\n"
            "  回看原型（若有），过 PE 判断能否从根部裁剪，而不是往下钻补条条框框。"
        )
    if result["high_round_reminder"]:
        lines.append(
            f"\n[轮次提醒] {result['stage']} 已进入第 {entry['round']} 轮，"
            "确认是在收尾零星不一致而非陷入细节拉锯。"
        )
    lines.append(f"\n下一步: {result['next_command']}")
    return "\n".join(lines)


def advance_text(result):
    lines = [f"[advance] {result['previous']} -> {result['target']}  已完成状态迁移。"]
    if result["skills"]:
        lines.extend(("", f"[{result['target']} 调用 Skill] {', '.join(result['skills'])}"))
    tools = optional_tools_lines(result["optional_tools"])
    if tools:
        lines.append("")
        lines.extend(tools)
    lines.extend(("", f"[{result['target']} 硬原则]"))
    lines.extend(f"  - {line}" for line in result["principles"])
    lines.append(f"\n下一步: {result['next_command']}")
    return "\n".join(lines)


def status_text(result):
    state = result["state"]
    switches = state["switches"]
    lines = [
        "== kickoff 状态 ==",
        f"  状态文件: {result['path']}",
        f"  当前阶段: {state['stage']}",
        f"  包目录: {state.get('pkg_dir') or '(未绑定)'}",
    ]
    if state.get("staging_path"):
        lines.append(f"  暂存路径: {state['staging_path']}")
    lines.append(
        f"  Owner 确认: {'是' if state.get('owner_confirmed') else '否'}"
        + (f"  ({state.get('confirmed_at')})" if state.get("confirmed_at") else "")
    )
    lines.append(f"  目标: {state.get('goal') or '(未填写)'}")
    lines.append(
        f"  输入契约: research={state['inputs']['research']}  "
        f"prototype={state['inputs']['prototype']}"
    )
    if state.get("docs"):
        lines.append(f"  Docs: {', '.join(state['docs'])}")
    lines.append(
        f"  环节开关: discover={'on' if switches['discover'] else 'off'} "
        f"pe={'on' if switches['pe'] else 'off'} plan={'on' if switches['plan'] else 'off'}"
    )

    agents = state.get("agents", {})
    plan_reviewers = agents.get("plan_reviewers") or []
    plan_reviewer_text = (
        ", ".join(
            f"{item['agent_id']}({item['label']})" if item.get("label") else item["agent_id"]
            for item in plan_reviewers
        )
        if plan_reviewers
        else "(未登记)"
    )
    lines.append(
        f"  角色: pe={agents.get('pe') or '(未登记)'}  "
        f"reviewer={agents.get('reviewer') or '(未登记)'}  "
        f"plan-reviewer={plan_reviewer_text}"
    )
    if result["skills"]:
        lines.append(f"  阶段 Skill: {', '.join(result['skills'])}")
    if state.get("artifacts"):
        lines.append("  阶段产出:")
        for stage, paths in state["artifacts"].items():
            lines.append(f"    {stage}: {', '.join(paths)}")

    lines.append("  分诊轮次:")
    if not state.get("rounds"):
        lines.append("    (无)")
    else:
        for row in result["triage_rounds"]:
            rounds = row["rounds"]
            lines.append(f"    {row['stage']}: {len(rounds)} 轮")
            for round_ in rounds:
                counts = round_["counts"]
                verdict = round_.get("verdict") or "open"
                upstream_tag = " [touched-upstream]" if round_.get("touched_upstream") else ""
                lines.append(
                    f"      #{round_['round']} [{verdict}]{upstream_tag} "
                    f"added={counts['added']} cut={counts['cut']} pe={counts['pe']} "
                    f"rejected={counts['rejected']} — {round_['summary']}"
                )

    lines.append("\n[当前阶段硬原则]")
    lines.extend(f"  - {line}" for line in result["principles"])
    tools = optional_tools_lines(result["optional_tools"])
    if tools:
        lines.append("")
        lines.extend(tools)
    lines.append(f"\n下一步有效命令: {result['next_command']}")
    return "\n".join(lines)
