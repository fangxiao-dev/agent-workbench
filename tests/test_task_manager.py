from __future__ import annotations

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "task-manager" / "scripts" / "task_manager.py"


def load_task_manager():
    spec = importlib.util.spec_from_file_location("task_manager_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_cli(module, *args: str) -> tuple[int, str]:
    saved_stdout = sys.stdout
    buffer = StringIO()
    try:
        sys.stdout = buffer
        exit_code = module.main(list(args))
    finally:
        sys.stdout = saved_stdout
    return exit_code, buffer.getvalue()


def write_payload(path: Path, *, progress: str = "Secret body detail should stay hidden.") -> None:
    path.write_text(
        json.dumps(
            {
                "operation": "create",
                "taskName": "Field Only Task",
                "projectId": "example-project",
                "status": "计划中",
                "priority": "当前",
                "taskType": "新增功能",
                "verificationPath": "不涉及",
                "workspace": "主工作区",
                "sourceType": "impl-plan",
                "sourceRelativePath": "docs/impl-plans/field-only.md",
                "source": "docs/impl-plans/field-only.md",
                "progress": progress,
                "nextStep": "Confirm fields before apply.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_upsert_dry_run_returns_field_only_confirmation(tmp_path: Path) -> None:
    module = load_task_manager()
    vault = tmp_path / "vault"
    (vault / "10_Tasks" / "example-project").mkdir(parents=True)
    input_path = tmp_path / "task-update.json"
    write_payload(input_path)

    exit_code, output = run_cli(
        module,
        "upsert",
        "--vault",
        str(vault),
        "--project",
        "example-project",
        "--input",
        str(input_path),
    )

    assert exit_code == 0
    result = json.loads(output)
    assert result["mode"] == "dry-run"
    assert result["operation"] == "create"
    assert result["fields"]["状态"] == ["计划中"]
    assert result["fields"]["优先级"] == ["当前"]
    assert result["fields"]["任务类型"] == ["新增功能"]
    assert result["fields"]["验证链路"] == ["不涉及"]
    assert result["fields"]["工作区"] == ["主工作区"]
    assert result["fields"]["来源类型"] == ["impl-plan"]
    assert result["fields"]["来源相对路径"] == "docs/impl-plans/field-only.md"
    assert result["fieldChanges"]["状态"]["after"] == ["计划中"]
    assert result["bodyChanged"] is True
    assert result["bodySectionsChanged"] == ["来源链接/路径", "当前进度", "下一步建议"]
    assert "markdown" not in result
    assert "frontmatter" not in result
    assert "Secret body detail should stay hidden." not in output
    assert not (vault / "10_Tasks" / "example-project" / "Field Only Task.md").exists()


def test_upsert_include_markdown_restores_rendered_body(tmp_path: Path) -> None:
    module = load_task_manager()
    vault = tmp_path / "vault"
    (vault / "10_Tasks" / "example-project").mkdir(parents=True)
    input_path = tmp_path / "task-update.json"
    write_payload(input_path, progress="Visible body detail when explicitly requested.")

    exit_code, output = run_cli(
        module,
        "upsert",
        "--vault",
        str(vault),
        "--project",
        "example-project",
        "--input",
        str(input_path),
        "--include-markdown",
    )

    assert exit_code == 0
    result = json.loads(output)
    assert "markdown" in result
    assert "### 当前进度" in result["markdown"]
    assert "Visible body detail when explicitly requested." in result["markdown"]
