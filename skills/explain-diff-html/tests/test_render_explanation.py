from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "render_explanation.py"
SPEC = importlib.util.spec_from_file_location("render_explanation", MODULE_PATH)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def quiz() -> list[dict[str, object]]:
    return [
        {
            "question": f"Question {index}?",
            "options": [
                {"text": "Correct", "correct": True, "feedback": "Correct."},
                {"text": "Wrong A", "correct": False, "feedback": "Not A."},
                {"text": "Wrong B", "correct": False, "feedback": "Not B."},
            ],
        }
        for index in range(1, 6)
    ]


def base_spec() -> dict[str, object]:
    return {
        "title": "Migration architecture",
        "summary": "A concise explanation.",
        "assumption": "Target behavior is not deployed yet.",
        "lang": "zh-CN",
        "sections": [
            {
                "id": "background",
                "title": "背景",
                "blocks": [
                    {"type": "callout", "label": "旧系统", "text": "Lark", "role": "removed"},
                    {
                        "type": "list",
                        "items": [
                            "Plain context",
                            {"text": "Next.js", "role": "retained"},
                        ],
                    },
                ],
            },
            {
                "id": "intuition",
                "title": "直觉",
                "blocks": [
                    {
                        "type": "comparison",
                        "before": {"label": "Before", "text": "Lark", "role": "removed"},
                        "after": {"label": "After", "text": "Postgres", "role": "added"},
                    },
                    {
                        "type": "flow",
                        "steps": [
                            {"label": "Cutover", "text": "Owner GO", "role": "transition"},
                        ],
                    },
                ],
            },
            {
                "id": "code",
                "title": "实现",
                "blocks": [
                    {"type": "code", "language": "text", "code": "request -> target", "role": "retained"},
                    {
                        "type": "table",
                        "headers": ["Old", "New"],
                        "rows": [["Lark", {"text": "Supabase <RLS>", "role": "added"}]],
                    },
                ],
            },
        ],
        "quiz": quiz(),
    }


class RenderExplanationTests(unittest.TestCase):
    def test_semantic_roles_render_an_automatic_accessible_legend(self) -> None:
        spec = renderer.validate_spec(base_spec())
        output = renderer.render(spec)

        self.assertIn('<html lang="zh-CN">', output)
        self.assertIn('<strong>前提</strong>', output)
        self.assertIn('<h2>目录</h2>', output)
        self.assertIn('<section id="quiz"><h2>理解检查</h2>', output)
        self.assertIn('class="role-legend"', output)
        self.assertIn('class="role-panel role-removed"', output)
        self.assertIn('class="role-panel role-added"', output)
        self.assertIn('class="role-panel role-transition"', output)
        self.assertIn('<pre class="role-panel role-retained">', output)
        self.assertIn('pre.role-panel { background: #152a38 !important;', output)
        self.assertIn('class="role-chip">移除</span>', output)
        self.assertIn('class="role-chip">保留</span>', output)
        self.assertIn('class="role-chip">新增</span>', output)
        self.assertIn('class="role-chip">迁移期</span>', output)
        self.assertIn("Supabase &lt;RLS&gt;", output)

    def test_legacy_string_only_content_remains_valid_without_a_legend(self) -> None:
        spec = base_spec()
        spec.pop("lang")
        for section in spec["sections"]:
            for block in section["blocks"]:
                block.pop("role", None)
                if block["type"] == "list":
                    block["items"] = ["Plain context", "Next.js"]
                elif block["type"] == "comparison":
                    block["before"].pop("role", None)
                    block["after"].pop("role", None)
                elif block["type"] == "flow":
                    block["steps"][0].pop("role", None)
                elif block["type"] == "table":
                    block["rows"] = [["Lark", "Supabase"]]

        output = renderer.render(renderer.validate_spec(spec))
        body = output.split("<body>", 1)[1]

        self.assertIn('<html lang="en">', output)
        self.assertNotIn('class="role-legend"', output)
        self.assertNotIn('class="role-panel', body)
        self.assertIn("<td>Supabase</td>", output)

    def test_unknown_role_fails_validation(self) -> None:
        spec = deepcopy(base_spec())
        spec["sections"][1]["blocks"][1]["steps"][0]["role"] = "future"

        with self.assertRaisesRegex(ValueError, "must be one of"):
            renderer.validate_spec(spec)

    def test_invalid_language_tag_fails_validation(self) -> None:
        spec = base_spec()
        spec["lang"] = "zh_CN<script>"

        with self.assertRaisesRegex(ValueError, "BCP 47"):
            renderer.validate_spec(spec)


if __name__ == "__main__":
    unittest.main()
