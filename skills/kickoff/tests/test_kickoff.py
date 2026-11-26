#!/usr/bin/env python3
"""Unit tests for the kickoff state machine CLI (stdlib unittest only).

Run: python -m unittest discover -s C:/Users/Xiao/.claude/skills/kickoff/tests -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.abspath(os.path.join(HERE, "..", "scripts", "kickoff.py"))


class KickoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------- helpers
    def run_cli(self, *args, expect=0):
        proc = subprocess.run(
            [sys.executable, SCRIPT, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if expect is not None and proc.returncode != expect:
            self.fail(
                f"command {args} returned {proc.returncode}, expected {expect}\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        return proc

    def run_fail(self, *args):
        proc = subprocess.run(
            [sys.executable, SCRIPT, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotEqual(proc.returncode, 0, f"expected failure: {args}\n{proc.stdout}")
        return proc.stdout + proc.stderr

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)

    def write(self, path, text):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def read_state(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def init_pkg(self, pkg, *extra, research="none", prototype="none"):
        return self.run_cli(
            "init", "--pkg", pkg,
            "--research", research, "--prototype", prototype, *extra,
        )

    # ------------------------------------------------------------- tests
    def test_full_chain_with_bind_pkg_pe_plan(self):
        staging = self.path("staging")
        pkg = self.path("pkg")
        req = self.path("staging", "myreq.json")

        self.run_cli(
            "init", "--slug", "myreq", "--staging-dir", staging,
            "--goal", "示例需求",
            "--research", "doc-a.md", "--research", "none",
            "--prototype", "proto.html",
        )
        state = self.read_state(req)
        self.assertIsNone(state["pkg_dir"])
        self.assertFalse(state["owner_confirmed"])

        self.run_cli("confirm", "--state", req)
        self.run_cli("bind-pkg", "--state", req, "--pkg", pkg)
        bound = self.path("pkg", "kickoff-state.json")
        self.assertTrue(os.path.isfile(bound))
        self.assertFalse(os.path.exists(req), "staging file should be removed")
        self.assertEqual(self.read_state(bound)["pkg_dir"], os.path.abspath(pkg))

        self.run_cli("advance", "discover", "--pkg", pkg)
        self.run_cli("register", "--pkg", pkg, "--role", "pe", "--agent-id", "pe-1")
        self.run_cli("advance", "decision", "--pkg", pkg)

        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv-1")
        self.run_cli("round", "--pkg", pkg, "--stage", "decision", "--verdict", "clean", "--summary", "首轮分诊")
        self.run_cli("advance", "spec", "--pkg", pkg)

        self.run_cli("round", "--pkg", pkg, "--stage", "spec", "--verdict", "clean", "--summary", "spec 分诊")
        self.run_cli("advance", "plan", "--pkg", pkg)

        self.run_cli("register", "--pkg", pkg, "--role", "plan-reviewer", "--agent-id", "pr-a", "--label", "scope")
        self.run_cli("round", "--pkg", pkg, "--stage", "plan", "--verdict", "clean", "--summary", "plan 分诊")
        self.run_cli("advance", "ready", "--pkg", pkg)

        final = self.read_state(bound)
        self.assertEqual(final["stage"], "ready")
        self.assertEqual(final["agents"]["pe"], "pe-1")
        self.assertEqual(final["agents"]["reviewer"], "rv-1")
        self.assertEqual(final["agents"]["plan_reviewers"], [{"agent_id": "pr-a", "label": "scope"}])

    def test_skip_switches_chain_to_ready(self):
        pkg = self.path("pkg")
        self.init_pkg(pkg, "--discover", "off", "--pe", "off", "--plan", "off")
        self.run_cli("confirm", "--pkg", pkg)
        self.run_cli("advance", "decision", "--pkg", pkg)

        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")
        self.run_cli("round", "--pkg", pkg, "--stage", "decision", "--verdict", "clean", "--summary", "分诊")
        self.run_cli("advance", "spec", "--pkg", pkg)

        self.run_cli("round", "--pkg", pkg, "--stage", "spec", "--verdict", "clean", "--summary", "分诊")
        self.run_cli("advance", "ready", "--pkg", pkg)

        self.assertEqual(self.read_state(self.path("pkg", "kickoff-state.json"))["stage"], "ready")

    def test_gate_requires_owner_confirm(self):
        pkg = self.path("pkg")
        self.init_pkg(pkg)
        out = self.run_fail("advance", "discover", "--pkg", pkg)
        self.assertIn("Owner 确认", out)
        self.assertIn("confirm", out)

    def test_gate_requires_pkg_bind(self):
        staging = self.path("staging")
        req = self.path("staging", "s.json")
        self.run_cli(
            "init", "--slug", "s", "--staging-dir", staging,
            "--research", "none", "--prototype", "none", "--discover", "off",
        )
        self.run_cli("confirm", "--state", req)
        out = self.run_fail("advance", "decision", "--state", req)
        self.assertIn("包目录未绑定", out)

    def test_gate_requires_pe_registration(self):
        pkg = self.path("pkg")
        self.init_pkg(pkg, "--discover", "off")  # pe on by default
        self.run_cli("confirm", "--pkg", pkg)
        out = self.run_fail("advance", "decision", "--pkg", pkg)
        self.assertIn("PE 未登记", out)

    def _to_decision_stage(self, pkg, *init_extra, pe_agent=None):
        self.init_pkg(pkg, *init_extra)
        self.run_cli("confirm", "--pkg", pkg)
        if pe_agent:
            self.run_cli("register", "--pkg", pkg, "--role", "pe", "--agent-id", pe_agent)
        self.run_cli("advance", "decision", "--pkg", pkg)

    def test_gate_requires_reviewer(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        out = self.run_fail("advance", "spec", "--pkg", pkg)
        self.assertIn("reviewer", out)

    def test_gate_requires_decision_round(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")
        out = self.run_fail("advance", "spec", "--pkg", pkg)
        self.assertIn("分诊轮次", out)

    def test_advance_with_existing_artifact_records_path(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")
        self.run_cli("round", "--pkg", pkg, "--stage", "decision", "--verdict", "clean", "--summary", "分诊")
        art = self.path("pkg", "any-custom-note.md")
        self.write(art, "任意内容，kickoff 不解析")
        self.run_cli("advance", "spec", "--pkg", pkg, "--artifact", art)
        state = self.read_state(self.path("pkg", "kickoff-state.json"))
        self.assertEqual(state["stage"], "spec")
        self.assertEqual(state["artifacts"]["decision"], [os.path.abspath(art)])

    def test_advance_with_missing_artifact_fails(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")
        self.run_cli("round", "--pkg", pkg, "--stage", "decision", "--verdict", "clean", "--summary", "分诊")
        missing = self.path("pkg", "does-not-exist.md")
        out = self.run_fail("advance", "spec", "--pkg", pkg, "--artifact", missing)
        self.assertIn("不存在", out)

    def test_round_rejects_empty_summary(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")
        out = self.run_fail("round", "--pkg", pkg, "--stage", "decision", "--summary", "   ")
        self.assertIn("summary", out.lower())

    def test_round_requires_reviewer(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        out = self.run_fail("round", "--pkg", pkg, "--stage", "decision", "--summary", "分诊")
        self.assertIn("reviewer", out)

    def test_convergence_warning(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")

        r1 = self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                          "--added", "1", "--summary", "加分支")
        self.assertNotIn("收敛警告", r1.stdout)

        r2 = self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                          "--added", "1", "--summary", "又加分支")
        self.assertIn("收敛警告", r2.stdout)

        r3 = self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                          "--added", "0", "--summary", "只裁剪")
        self.assertNotIn("收敛警告", r3.stdout)

        r4 = self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                          "--added", "1", "--summary", "再加一条")
        self.assertNotIn("收敛警告", r4.stdout)

    def test_status_and_help(self):
        help_out = self.run_cli("--help").stdout
        self.assertIn("init", help_out)
        self.assertIn("impl-package", help_out)
        self.assertIn("分诊", help_out)

        pkg = self.path("pkg")
        self.init_pkg(pkg)
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")
        status = self.run_cli("status", "--pkg", pkg).stdout
        self.assertIn("当前阶段: init", status)
        self.assertIn("唯一必停点", status)
        self.assertIn("下一步有效命令", status)

    def test_diagram_outputs_mermaid(self):
        out = self.run_cli("diagram").stdout
        self.assertTrue(out.startswith("flowchart TD\n"))
        self.assertIn('init["init<br/>(唯一必停点: confirm)"]', out)
        self.assertIn('ready(["ready"])', out)
        self.assertIn("init -.->", out)
        self.assertIn("spec -.->", out)
        self.assertIn('decision -->|"round (连续2轮 added>0 警告)"| decision', out)

    def test_diagram_sync_and_check_roundtrip(self):
        md = self.path("doc.md")
        self.write(
            md,
            "# Title\n\n<!-- BEGIN:PIPELINE_DIAGRAM -->\nold\n<!-- END:PIPELINE_DIAGRAM -->\n",
        )
        # 尚未同步时 --check 应失败
        err = self.run_fail("diagram", "--sync-md", md, "--check")
        self.assertIn("已过时", err)

        # --sync-md 刷新后 --check 应通过
        self.run_cli("diagram", "--sync-md", md)
        self.run_cli("diagram", "--sync-md", md, "--check")

        with open(md, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("```mermaid\nflowchart TD", content)

    def test_skill_md_diagram_in_sync(self):
        skill_md = os.path.abspath(os.path.join(HERE, "..", "SKILL.md"))
        self.run_cli("diagram", "--sync-md", skill_md, "--check")

    def test_gate_requires_last_round_clean(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")

        # 默认 verdict=open，不能过门
        self.run_cli("round", "--pkg", pkg, "--stage", "decision", "--summary", "有待修项")
        err = self.run_fail("advance", "spec", "--pkg", pkg)
        self.assertIn("尚未清零", err)

        # 复验 clean 后放行
        self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                     "--verdict", "clean", "--summary", "复验清零")
        self.run_cli("advance", "spec", "--pkg", pkg)
        self.assertEqual(self.read_state(self.path("pkg", "kickoff-state.json"))["stage"], "spec")

    def test_next_command_guides_reviewer_and_rounds(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")

        st1 = self.run_cli("status", "--pkg", pkg).stdout
        self.assertIn("register", st1)
        self.assertIn("--role reviewer", st1)

        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")
        st2 = self.run_cli("status", "--pkg", pkg).stdout
        self.assertIn("round", st2)
        self.assertIn("--stage decision", st2)

        r1 = self.run_cli("round", "--pkg", pkg, "--stage", "decision", "--summary", "首轮有P1").stdout
        self.assertIn("--verdict clean", r1)

        r2 = self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                          "--verdict", "clean", "--summary", "复验清零").stdout
        self.assertIn("advance spec", r2)

    def test_register_replacement_warns(self):
        pkg = self.path("pkg")
        self.init_pkg(pkg)
        out1 = self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv-1").stdout
        self.assertNotIn("[警告]", out1)

        out2 = self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv-1").stdout
        self.assertNotIn("[警告]", out2)

        out3 = self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv-2").stdout
        self.assertIn("[警告]", out3)
        self.assertIn("rv-1 -> rv-2", out3)

    def test_round_stage_check_and_backfill(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")

        err = self.run_fail("round", "--pkg", pkg, "--stage", "spec", "--summary", "错记阶段")
        self.assertIn("--backfill", err)

        self.run_cli("round", "--pkg", pkg, "--stage", "spec", "--backfill", "--summary", "补录")
        state = self.read_state(self.path("pkg", "kickoff-state.json"))
        self.assertTrue(state["rounds"][-1]["backfill"])

    def test_high_round_reminder(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv")

        for i in range(1, 4):
            out = self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                               "--summary", f"第{i}轮").stdout
            self.assertNotIn("轮次提醒", out)

        out4 = self.run_cli("round", "--pkg", pkg, "--stage", "decision",
                            "--summary", "第4轮").stdout
        self.assertIn("轮次提醒", out4)

    def _to_plan_stage(self, pkg):
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        self.run_cli("register", "--pkg", pkg, "--role", "reviewer", "--agent-id", "rv-design")
        self.run_cli("round", "--pkg", pkg, "--stage", "decision", "--verdict", "clean", "--summary", "decision clean")
        self.run_cli("advance", "spec", "--pkg", pkg)
        self.run_cli("round", "--pkg", pkg, "--stage", "spec", "--verdict", "clean", "--summary", "spec clean")
        return self.run_cli("advance", "plan", "--pkg", pkg)

    def test_plan_reviewer_pool_gate_and_next_command(self):
        pkg = self.path("pkg")
        adv = self._to_plan_stage(pkg).stdout
        self.assertIn("/impl-package:impl-planning", adv)
        self.assertIn("/impl-package:plan-review", adv)
        self.assertIn("--role plan-reviewer", adv)

        # 未登记 plan-reviewer 时，round 和 advance ready 均应拦截
        err_round = self.run_fail("round", "--pkg", pkg, "--stage", "plan", "--summary", "plan 审阅")
        self.assertIn("plan-reviewer", err_round)
        err_adv = self.run_fail("advance", "ready", "--pkg", pkg)
        self.assertIn("plan-reviewer", err_adv)

        # 多轨追加不触发替换警告，同 ID 重复登记去重、可补标签且不传标签时保留原标签
        o1 = self.run_cli("register", "--pkg", pkg, "--role", "plan-reviewer", "--agent-id", "pr-a", "--label", "scope").stdout
        o2 = self.run_cli("register", "--pkg", pkg, "--role", "plan-reviewer", "--agent-id", "pr-b", "--label", "risk").stdout
        o3 = self.run_cli("register", "--pkg", pkg, "--role", "plan-reviewer", "--agent-id", "pr-b", "--label", "risk-v2").stdout
        o4 = self.run_cli("register", "--pkg", pkg, "--role", "plan-reviewer", "--agent-id", "pr-a").stdout
        self.assertNotIn("[警告]", o1 + o2 + o3 + o4)

        status = self.run_cli("status", "--pkg", pkg).stdout
        self.assertIn("pr-a(scope)", status)
        self.assertIn("pr-b(risk-v2)", status)
        self.assertIn("阶段 Skill:", status)
        self.assertIn("round --pkg", status)
        self.assertIn("--stage plan", status)

        r_open = self.run_cli("round", "--pkg", pkg, "--stage", "plan", "--summary", "首轮分诊").stdout
        self.assertIn("--verdict clean", r_open)

        r_clean = self.run_cli("round", "--pkg", pkg, "--stage", "plan", "--verdict", "clean", "--summary", "复验清零").stdout
        self.assertIn("advance ready", r_clean)

        state = self.read_state(self.path("pkg", "kickoff-state.json"))
        self.assertEqual(
            state["agents"]["plan_reviewers"],
            [{"agent_id": "pr-a", "label": "scope"}, {"agent_id": "pr-b", "label": "risk-v2"}],
        )

    def test_round_stage_mismatch_checked_before_role(self):
        pkg = self.path("pkg")
        self._to_decision_stage(pkg, "--discover", "off", "--pe", "off")
        err = self.run_fail("round", "--pkg", pkg, "--stage", "plan", "--summary", "错阶段")
        self.assertIn("当前阶段为 decision", err)

    def test_touched_upstream_flag_and_reminder(self):
        pkg = self.path("pkg")
        self._to_plan_stage(pkg)
        self.run_cli("register", "--pkg", pkg, "--role", "plan-reviewer", "--agent-id", "pr-a")

        r1 = self.run_cli(
            "round", "--pkg", pkg, "--stage", "plan",
            "--added", "1", "--touched-upstream",
            "--summary", "回补 spec 最小视图 DTO",
        ).stdout
        self.assertIn("[touched-upstream]", r1)
        self.assertIn("[上游变更提醒]", r1)

        status = self.run_cli("status", "--pkg", pkg).stdout
        self.assertIn("[touched-upstream]", status)

        state = self.read_state(self.path("pkg", "kickoff-state.json"))
        self.assertTrue(state["rounds"][-1]["touched_upstream"])

    def test_legacy_state_without_plan_reviewers_key(self):
        pkg = self.path("pkg")
        self._to_plan_stage(pkg)
        state_path = self.path("pkg", "kickoff-state.json")
        state = self.read_state(state_path)
        del state["agents"]["plan_reviewers"]
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        status = self.run_cli("status", "--pkg", pkg).stdout
        self.assertIn("plan-reviewer=(未登记)", status)
        self.run_cli("register", "--pkg", pkg, "--role", "plan-reviewer", "--agent-id", "pr-legacy")
        self.run_cli("round", "--pkg", pkg, "--stage", "plan", "--verdict", "clean", "--summary", "兼容旧状态")
        self.run_cli("advance", "ready", "--pkg", pkg)


if __name__ == "__main__":
    unittest.main()
