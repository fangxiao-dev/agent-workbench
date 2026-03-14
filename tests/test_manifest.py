from __future__ import annotations

import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agent_workbench.manifest import load_manifest
from test_bootstrap_cli import create_source_repo, write_manifest


def test_manifest_rejects_third_party_skills_field(tmp_path: Path) -> None:
    source_repo = create_source_repo(tmp_path / "source-repo")
    business_repo = tmp_path / "business-repo"
    business_repo.mkdir()
    manifest_path = write_manifest(business_repo, source_repo)
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_data["third_party_skills"] = [
        {"source": "vercel-labs/agent-skills", "skill": "vercel-react-best-practices"},
    ]
    manifest_path.write_text(yaml.safe_dump(manifest_data, sort_keys=False), encoding="utf-8")
    try:
        load_manifest(manifest_path)
    except ValueError as exc:
        assert "third_party_skills" in str(exc)
    else:
        raise AssertionError("Expected load_manifest() to reject third_party_skills after rollback")
