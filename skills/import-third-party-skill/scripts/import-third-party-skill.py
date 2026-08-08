#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
REGISTRY_MD = REPO_ROOT / "registry" / "third-party-skills.md"


@dataclass
class ReviewSummary:
    source: str
    source_url: str | None
    upstream_path: str
    key_files: list[str]
    has_scripts: bool
    risk_notes: list[str]
    recommendation: str
    skill_sha256: str | None


def parse_package(package: str) -> dict[str, str]:
    if "@" not in package or "/" not in package:
        raise ValueError(f"Unsupported package format: {package}")
    owner_repo, skill = package.split("@", 1)
    owner, repo = owner_repo.split("/", 1)
    return {"owner": owner, "repo": repo, "skill": skill}


def normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def directory_snapshot(path: Path) -> dict[str, Any]:
    files: list[str] = []
    hash_digest = hashlib.sha256()
    skill_md_hash = None
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = normalize_path(file_path.relative_to(path))
        files.append(rel)
        hash_digest.update(rel.encode("utf-8"))
        file_bytes = file_path.read_bytes()
        hash_digest.update(hashlib.sha256(file_bytes).hexdigest().encode("ascii"))
        if rel == "SKILL.md":
            skill_md_hash = hashlib.sha256(file_bytes).hexdigest()
    return {"files": files, "skill_md_hash": skill_md_hash, "directory_hash": hash_digest.hexdigest()}


def github_api_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "agent-workbench/import-third-party-skill",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def github_fetch_review(package: str, source_url: str | None) -> ReviewSummary:
    pkg = parse_package(package)
    owner = pkg["owner"]
    repo = pkg["repo"]
    skill = pkg["skill"]
    source = f"{owner}/{repo}"
    source_url = source_url or f"https://github.com/{source}"
    upstream_path = f"skills/{skill}"
    base_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{urllib.parse.quote(upstream_path)}"

    try:
        top_level = github_api_json(base_url)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Failed to inspect upstream skill {package}: HTTP {exc.code}") from exc

    if not isinstance(top_level, list):
        raise RuntimeError(f"Unexpected GitHub response while inspecting {package}")

    top_names = sorted(item["name"] for item in top_level)
    skill_md_entry = next((item for item in top_level if item["name"] == "SKILL.md"), None)
    if not skill_md_entry:
        raise RuntimeError(f"Upstream skill {package} does not contain SKILL.md at {upstream_path}")

    skill_blob = github_api_json(skill_md_entry["url"])
    skill_bytes = base64.b64decode(skill_blob["content"])
    skill_sha256 = hashlib.sha256(skill_bytes).hexdigest()

    subdir_summaries: list[str] = []
    risk_notes: list[str] = []
    has_scripts = False
    for dirname in ("scripts", "references", "assets"):
        subdir = next((item for item in top_level if item["name"] == dirname and item["type"] == "dir"), None)
        if not subdir:
            continue
        children = github_api_json(subdir["url"])
        child_names = sorted(child["name"] for child in children if isinstance(child, dict) and "name" in child)
        preview = ", ".join(child_names[:5])
        suffix = "..." if len(child_names) > 5 else ""
        subdir_summaries.append(f"{dirname}/ ({len(child_names)}): {preview}{suffix}".rstrip())
        if dirname == "scripts":
            has_scripts = True
            risk_notes.append("Contains scripts; inspect automation before installing.")
        if dirname == "assets":
            risk_notes.append("Contains bundled assets; verify they are necessary.")

    if not risk_notes:
        risk_notes.append("No bundled scripts detected in top-level review.")

    return ReviewSummary(
        source=source,
        source_url=source_url,
        upstream_path=upstream_path,
        key_files=["SKILL.md", *(name for name in top_names if name != "SKILL.md"), *subdir_summaries],
        has_scripts=has_scripts,
        risk_notes=risk_notes,
        recommendation="Review scripts carefully before approving install." if has_scripts else "Proceed after quick review.",
        skill_sha256=skill_sha256,
    )


def render_review(summary: ReviewSummary, package: str) -> str:
    lines = [
        "Upstream review:",
        f"  - Package: {package}",
        f"  - Source: {summary.source}",
        f"  - Source URL: {summary.source_url or 'n/a'}",
        f"  - Upstream path: {summary.upstream_path}",
        f"  - Has scripts: {'yes' if summary.has_scripts else 'no'}",
        "  - Key files:",
    ]
    lines.extend(f"    - {item}" for item in summary.key_files)
    lines.append("  - Risk notes:")
    lines.extend(f"    - {item}" for item in summary.risk_notes)
    lines.append(f"  - Recommendation: {summary.recommendation}")
    return "\n".join(lines)


def run_install_command(base_command: str, package: str) -> None:
    command = f"{base_command} {package} -g -y"
    result = subprocess.run(command, shell=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Install command failed: {command}")


def resolve_installed_skill_path(skill_name: str) -> Path | None:
    home = Path.home()
    candidates = [
        REPO_ROOT / "skills" / skill_name,
        home / ".codex" / "skills" / skill_name,
        home / ".claude" / "skills" / skill_name,
        home / ".grok" / "skills" / skill_name,
        home / ".agents" / "skills" / skill_name,
        REPO_ROOT / ".claude" / "skills" / skill_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def render_conflict(skill_name: str, package: str, review: ReviewSummary | None, existing_path: Path) -> str:
    snapshot = directory_snapshot(existing_path)
    content_relation = "unknown"
    if review and review.skill_sha256 and snapshot["skill_md_hash"]:
        content_relation = "same content" if review.skill_sha256 == snapshot["skill_md_hash"] else "different content"

    lines = [
        "Conflict detected. Installation skipped.",
        f"  - Skill: {skill_name}",
        f"  - Existing path: {existing_path}",
        f"  - Candidate package: {package}",
        f"  - Content relation: {content_relation}",
        f"  - Directory hash: {snapshot['directory_hash']}",
        "  - Key files:",
    ]
    for item in snapshot["files"][:10]:
        lines.append(f"    - {item}")
    if len(snapshot["files"]) > 10:
        lines.append(f"    - ... ({len(snapshot['files']) - 10} more)")
    lines.append("  - Decision needed: keep existing, remove it, or update explicitly with --force.")
    return "\n".join(lines)


def ensure_registry_header() -> list[str]:
    if REGISTRY_MD.exists():
        return REGISTRY_MD.read_text(encoding="utf-8-sig").splitlines()
    return [
        "# Third-party Skills",
        "",
        "| Skill | 来源 | 获取方式 | 备注 |",
        "|-------|------|----------|------|",
        "",
        "## 说明",
        "",
        "- 只登记第三方 skills，不登记本仓库自建 skills。",
    ]


def update_registry_markdown(name: str, source: str, install_command: str, target_path: Path) -> None:
    rel_target = normalize_path(target_path.relative_to(REPO_ROOT))
    row = f"| {name} | `{source}` | `{install_command}` | 已放入 `{rel_target}/` |"
    lines = ensure_registry_header()
    result: list[str] = []
    inserted = False

    for line in lines:
        if line.startswith(f"| {name} |"):
            continue
        result.append(line)
        if not inserted and line == "|-------|------|----------|------|":
            result.append(row)
            inserted = True

    if not inserted:
        result.extend(["", "| Skill | 来源 | 获取方式 | 备注 |", "|-------|------|----------|------|", row])

    REGISTRY_MD.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")


def copy_into_target(source_path: Path, target_path: Path, force: bool) -> None:
    if source_path.resolve() == target_path.resolve():
        return
    if target_path.exists():
        if not force:
            raise RuntimeError(f"Target path already exists: {target_path}")
        shutil.rmtree(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_path, target_path)


def import_skill(args: argparse.Namespace, review: ReviewSummary | None) -> int:
    target_dir = args.target_dir or "skills"
    target_path = (REPO_ROOT / target_dir / args.skill_name).resolve()

    if target_path.exists() and not args.force:
        print(render_conflict(args.skill_name, args.package, review, target_path))
        return 0

    installed_path = resolve_installed_skill_path(args.skill_name)
    if not installed_path or args.force:
        if target_path.exists() and args.force:
            shutil.rmtree(target_path)
        run_install_command(args.install_command, args.package)
        installed_path = resolve_installed_skill_path(args.skill_name)

    if not installed_path:
        raise RuntimeError(f"Installed skill '{args.skill_name}' not found after installation.")

    copy_into_target(installed_path, target_path, args.force)

    source = args.package.split("@", 1)[0]
    install_command = f"{args.install_command} {args.package} -g -y"
    update_registry_markdown(args.skill_name, source, install_command, target_path)

    print("Imported third-party skill:")
    print(f"  - Name: {args.skill_name}")
    print(f"  - Source: {installed_path}")
    print(f"  - Target: {target_path}")
    print(f"  - Registry: {REGISTRY_MD}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-name", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--mode", choices=["install", "vendor"], default="install")
    parser.add_argument("--target-dir", default="skills")
    parser.add_argument("--source-type", default="github")
    parser.add_argument("--source-url")
    parser.add_argument("--install-command", default="npx skills add")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--skip-review", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    review = None
    if not args.skip_review and args.source_type == "github":
        review = github_fetch_review(args.package, args.source_url)
        print(render_review(review, args.package))
        if not args.approve:
            print("Review only. Re-run with --approve to continue.")
            return 0

    return import_skill(args, review)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
