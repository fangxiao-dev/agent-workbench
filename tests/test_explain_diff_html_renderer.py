import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "skills" / "explain-diff-html" / "scripts" / "render_explanation.py"
SPEC = importlib.util.spec_from_file_location("explain_diff_renderer", SCRIPT)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def make_spec():
    sections = [
        {"id": "background", "title": "Background", "blocks": [{"type": "paragraph", "text": "<unsafe>"}]},
        {"id": "intuition", "title": "Intuition", "blocks": [{"type": "flow", "steps": [{"label": "A", "text": "B"}]}]},
        {"id": "code", "title": "Code", "blocks": [{"type": "code", "language": "ts", "code": "const x = 1;\n"}]},
    ]
    quiz = []
    for index in range(5):
        quiz.append(
            {
                "question": f"Question {index}",
                "options": [
                    {"text": "Wrong one", "correct": False, "feedback": "Not this one."},
                    {"text": "Right one", "correct": True, "feedback": "Correct."},
                    {"text": "Another wrong", "correct": False, "feedback": "This mixes two paths."},
                ],
            }
        )
    return {"title": "Demo", "summary": "Summary", "assumption": "", "sections": sections, "quiz": quiz}


def test_validate_requires_exactly_five_questions():
    spec = make_spec()
    spec["quiz"].pop()

    with pytest.raises(ValueError, match="exactly five"):
        renderer.validate_spec(spec)


def test_validate_rejects_non_boolean_correct_and_wrong_section_order():
    spec = make_spec()
    spec["quiz"][0]["options"][0]["correct"] = "yes"

    with pytest.raises(ValueError, match="must be boolean"):
        renderer.validate_spec(spec)

    spec = make_spec()
    spec["sections"] = list(reversed(spec["sections"]))

    with pytest.raises(ValueError, match="in that order"):
        renderer.validate_spec(spec)

    spec = make_spec()
    spec["assumption"] = {"not": "text"}

    with pytest.raises(ValueError, match="assumption must be a string"):
        renderer.validate_spec(spec)


def test_render_is_escaped_offline_and_has_five_quiz_cards():
    spec = make_spec()
    spec["quiz"][0]["options"][0]["feedback"] = 'Bad" onmouseover="alert(1)'
    output = renderer.render(renderer.validate_spec(spec))

    assert "&lt;unsafe&gt;" in output
    assert output.count('class="quiz-card"') == 5
    assert "<pre><code class=\"language-ts\">" in output
    assert "white-space: pre-wrap" in output
    assert "<script src=" not in output
    assert "<link" not in output
    assert "<img" not in output
    assert "<iframe" not in output
    assert "url(" not in output
    assert "fetch(" not in output
    assert "XMLHttpRequest" not in output
    assert "https://" not in output
    assert "data-correct" not in output
    assert "data-feedback" not in output
    assert "<template data-option-index=" in output
    assert "addEventListener('click'" in output
    assert "feedback.textContent" in output


def test_quiz_correct_positions_are_not_fixed():
    spec = renderer.validate_spec(make_spec())
    positions = []
    for index, question in enumerate(spec["quiz"]):
        ordered = renderer.ordered_options(spec["title"], index, question["options"])
        positions.append(next(i for i, option in enumerate(ordered) if option["correct"]))

    assert len(set(positions)) == 3
    assert max(positions.count(position) for position in set(positions)) - min(positions.count(position) for position in set(positions)) <= 1


def test_quiz_position_pattern_is_reproducible():
    spec = renderer.validate_spec(make_spec())
    first = [
        next(i for i, option in enumerate(renderer.ordered_options(spec["title"], index, question["options"])) if option["correct"])
        for index, question in enumerate(spec["quiz"])
    ]
    second = [
        next(i for i, option in enumerate(renderer.ordered_options("Another title", index, question["options"])) if option["correct"])
        for index, question in enumerate(spec["quiz"])
    ]

    assert first == [
        next(i for i, option in enumerate(renderer.ordered_options(spec["title"], index, question["options"])) if option["correct"])
        for index, question in enumerate(spec["quiz"])
    ]
    assert len(second) == 5


def test_cli_checks_date_extension_repo_boundary_and_overwrite(tmp_path):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(make_spec()), encoding="utf-8")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    today = __import__("datetime").date.today().isoformat()
    output = tmp_path / f"{today}-lesson.html"

    def run_for(path, input_path=spec_path):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(input_path),
                "--output",
                str(path),
                "--repo-root",
                str(repo_root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    first = run_for(output)
    second = run_for(output)
    inside = run_for(repo_root / f"{today}-inside.html")
    bad_extension = run_for(tmp_path / f"{today}-lesson.txt")
    bad_date = run_for(tmp_path / "1999-01-01-lesson.html")
    inside_spec = repo_root / "spec.json"
    inside_spec.write_text(json.dumps(make_spec()), encoding="utf-8")
    inside_input = run_for(tmp_path / f"{today}-other.html", inside_spec)

    assert first.returncode == 0
    assert output.is_file()
    assert second.returncode != 0
    assert "already exists" in second.stderr
    assert inside.returncode != 0
    assert "outside --repo-root" in inside.stderr
    assert bad_extension.returncode != 0
    assert ".html extension" in bad_extension.stderr
    assert bad_date.returncode != 0
    assert "today's date" in bad_date.stderr
    assert inside_input.returncode != 0
    assert "input must be outside --repo-root" in inside_input.stderr
