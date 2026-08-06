from __future__ import annotations

import re
import os
from pathlib import Path


IMPL_ROOT = Path(__file__).resolve().parents[1]
VENDORED_ENGLISH_ALLOWLIST = {Path("reviews/code-review/SKILL.md")}


def is_eval_workspace(path: Path) -> bool:
    return any(part.endswith("-workspace") for part in path.relative_to(IMPL_ROOT).parts)


def main() -> None:
    members = sorted(
        path
        for current, _, files in os.walk(IMPL_ROOT)
        for name in files
        if name == "SKILL.md"
        for path in [Path(current) / name]
        if path.parent != IMPL_ROOT and not is_eval_workspace(path)
    )
    if len(members) < 8:
        raise AssertionError(
            f"Expected Impl-Package member skills, found only {len(members)}."
        )

    for member in members:
        text = member.read_text(encoding="utf-8")
        match = re.match(r"^---\r?\n.*?\r?\n---", text, flags=re.DOTALL)
        if match is None:
            raise AssertionError(f"Missing YAML frontmatter: {member}")
        frontmatter = match.group(0)
        if "Impl-Package 体系的" in frontmatter:
            raise AssertionError(
                "Member description must lead with capability and trigger conditions, "
                f"not the suite name: {member}"
            )
        if re.search(r"^description:\s*(>|\S)", frontmatter, flags=re.MULTILINE) is None:
            raise AssertionError(f"Missing description: {member}")
        relative = member.relative_to(IMPL_ROOT)
        if relative not in VENDORED_ENGLISH_ALLOWLIST and re.search(
            r"[\u4e00-\u9fff]", frontmatter
        ) is None:
            raise AssertionError(
                "Locally maintained member description must use Chinese prose while "
                f"retaining useful English tokens: {member}"
            )

    router = (IMPL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    if "Impl-Package 体系的入口地图与路由" not in router:
        raise AssertionError(
            "The impl-package router may retain the suite name because routing the "
            "suite is its standalone capability."
        )

    print(
        "Impl-Package member descriptions are independently triggerable and local "
        "descriptions follow the Chinese-prose preference."
    )


if __name__ == "__main__":
    main()
