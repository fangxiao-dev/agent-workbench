"""CLI over the board's state-management capabilities (also the tool surface for the assistant)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import session_board_chat as chat

DEFAULT_DB = Path(r"D:\vibe-code-life\SessionBoard\board.sqlite3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="会话看板状态管理")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--claude-home", type=Path, default=Path.home() / ".claude")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出会话")
    p_list.add_argument("--lane", default="全部", choices=["进行中", "待查看", "已完成", "暂不关注", "全部"])
    p_list.add_argument("--title", help="标题包含")
    p_list.add_argument("--limit", type=int, default=40)

    p_set = sub.add_parser("set", help="批量修改状态/分组/备注/隐藏")
    p_set.add_argument("--lane", choices=["进行中", "待查看", "已完成", "暂不关注", "全部"])
    p_set.add_argument("--title", help="标题包含")
    p_set.add_argument("--ids", help="逗号分隔的会话 ID")
    p_set.add_argument("--no-activity-days", type=float, help="最近活动早于 N 天")
    p_set.add_argument("--state", choices=list(chat.STATES))
    p_set.add_argument("--group")
    p_set.add_argument("--note")
    p_set.add_argument("--hidden", choices=["true", "false"])

    args = parser.parse_args(argv)
    if args.cmd == "list":
        out = chat.list_items(args.db, args.claude_home, {"lane": args.lane, "title_contains": args.title, "limit": args.limit})
    else:
        payload: dict = {}
        if args.lane:
            payload["lane"] = args.lane
        if args.title:
            payload["title_contains"] = args.title
        if args.ids:
            payload["ids"] = [i.strip() for i in args.ids.split(",") if i.strip()]
        if args.no_activity_days is not None:
            payload["no_activity_days"] = args.no_activity_days
        for key in ("state", "group", "note"):
            value = getattr(args, key)
            if value is not None:
                payload["group_name" if key == "group" else key] = value
        if args.hidden:
            payload["hidden"] = args.hidden == "true"
        try:
            out = chat.update_items(args.db, args.claude_home, payload)
        except ValueError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
