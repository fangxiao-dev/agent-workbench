#!/usr/bin/env python3
"""并行跑三轨 Codex 评审，截取报告并校验报头，输出可 trail append 的 review.terminal_summary。

用法:
  python <plugin>/scripts/review/codex_round.py --package docs/implementations/<包> --run <review-run> \
    --base <基线commit> --prompt-file <正文.md> (--new | --sessions A_ID,C_ID,D_ID) --model M --effort E

提示词文件格式:
  开头是给所有轨的公共部分；之后每轨一段，段标记为独占一行的 `## Track A`、
  `## Track C`、`## Track D`（字母大写），段落延续到下一个 `## Track ` 标记或文件末尾。
  每个会话只收到公共部分 + 自己那一轨的段落 + 报头要求；缺所选轨的段落或完全没有
  段标记时直接报错退出，不发任何 codex 请求。

模型与推理强度不设默认值，但必须由调用方传入（--model / --effort）。
"""
import argparse, json, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HEADER_KEYS = ["verdict", "reviewed-head", "review-run", "review-track"]
TRACK_HEADING = re.compile(r"^## Track ([A-Z])[ \t]*$")
SESSION_ID = re.compile(r"^session id:[ \t]*(\S+)[ \t]*$", re.MULTILINE)


def split_prompt(body: str) -> tuple[str, dict[str, str]]:
    """返回 (公共部分, {轨字母: 段正文})；段标记须独占一行且字母大写。"""
    common, sections, current = [], {}, None
    for line in body.splitlines(keepends=True):
        m = TRACK_HEADING.match(line.rstrip("\r\n"))
        if m:
            current = m.group(1)
            sections[current] = []
        elif current is None:
            common.append(line)
        else:
            sections[current].append(line)
    if not sections:
        raise ValueError(
            "提示词文件没有任何 `## Track <字母>` 段标记；需改为公共部分 + 每轨一个 `## Track X` 段")
    return "".join(common), {k: "".join(v) for k, v in sections.items()}


def track_prompt(common: str, sections: dict[str, str], letter: str, base: str) -> str:
    return common + sections[letter] + f"\n\n对比基线：{base}\n"


def header_requirement(head: str, run: str, track: str) -> str:
    return (
        f"\n\n---\n本轨审阅由你自己完成，不要把审阅任务交给子代理。"
        "只有在需要调查具体细节时，才可派 Luna Max 子代理辅助取证，结论仍由你判断。\n"
        "\n报告必须以下面四行开头（之后空一行再写正文），不要在前面加任何文字：\n"
        f"verdict: PASS 或 FAIL\nreviewed-head: {head}\nreview-run: {run}\nreview-track: {track}\n"
    )


def extract_report(log: str) -> str:
    """最后一个以 `verdict:` 开头的块，截到 `tokens used` 之前（续接日志里结论可能出现两次）。"""
    lines = log.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("verdict:")]
    if not starts:
        raise ValueError("日志里没有以 verdict: 开头的报告")
    block = lines[starts[-1]:]
    for i, l in enumerate(block):
        if l.strip().lower().startswith("tokens used"):
            block = block[:i]
            break
    return "\n".join(block).strip() + "\n"


def validate_header(report: str, head: str, run: str, track: str) -> str:
    """返回 verdict；报头不符抛 ValueError。"""
    first = report.splitlines()[:4]
    got = {}
    for l in first:
        k, _, v = l.partition(":")
        got[k.strip()] = v.strip()
    expect = {"reviewed-head": head, "review-run": run, "review-track": track}
    if list(got) != HEADER_KEYS:
        raise ValueError(f"报头四行不完整: {first}")
    for k, v in expect.items():
        if got[k] != v:
            raise ValueError(f"报头 {k} 应为 {v}，实际 {got[k]}")
    if got["verdict"] not in ("PASS", "FAIL"):
        raise ValueError(f"verdict 只能是 PASS/FAIL: {got['verdict']}")
    return got["verdict"]


def extract_session_id(log: str) -> str | None:
    """codex 在输出头部打印 `session id: <id>`；续接日志里可能有多次，取最后一条。"""
    found = SESSION_ID.findall(log)
    return found[-1] if found else None


def report_paths(reviews: Path, run: str, key: str) -> tuple[Path, Path]:
    """(本轨报告, codex 原始输出备份)。"""
    return reviews / f"{run}-track-{key}.md", reviews / f"{run}-track-{key}.raw.md"


def run_track(key, track, args, body, head, codex, workdir):
    prompt = body + header_requirement(head, args.run, track)
    # body 已按轨裁剪（公共部分 + 本轨段落 + 对比基线），这里只补报头要求。
    opts = []
    if args.model:
        opts += ["-m", args.model]
    if args.effort:
        opts += ["-c", f"model_reasoning_effort={args.effort}"]
    if args.new:
        out = Path(tempfile.mkstemp(suffix=f"-{key}.md")[1])
        cmd = [codex, "exec", *opts, "-o", str(out), "-"]
    else:
        cmd = [codex, "exec", "resume", args.session_ids[key], *opts, "-"]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=workdir)
    raw = proc.stdout + "\n" + proc.stderr
    log = raw
    if args.new and out.exists():
        text = out.read_text(encoding="utf-8")
        if text.strip():
            log = text
    # log 可能只取 -o 文件内容，session id 只能从 stdout/stderr 的 raw 里取
    return key, track, log, raw, proc.returncode


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--package", required=True, help="包目录，如 docs/implementations/<包>")
    p.add_argument("--run", required=True, help="review-run 名")
    p.add_argument("--base", required=True, help="对比基线 commit")
    p.add_argument("--prompt-file", required=True, help="本轮提示词正文")
    p.add_argument("--tracks", default="A,C,D", help="轨道字母，逗号分隔，报头写成 Track <字母>")
    p.add_argument("--out-dir", help="报告目录，默认 <包>/execution/<当前 Attempt>/reviews")
    p.add_argument("--cwd", default=".", help="codex 与 git 的工作目录")
    p.add_argument("--sessions", help="与 --tracks 一一对应的会话 id，逗号分隔")
    p.add_argument("--new", action="store_true", help="新开会话而不是续接")
    p.add_argument("--model", required=True)
    p.add_argument("--effort", required=True)
    args = p.parse_args()
    for flag in ("model", "effort"):
        if not getattr(args, flag).strip():
            p.error(f"--{flag} must not be empty")
    if args.new == bool(args.sessions):
        p.error("--new 与 --sessions 二选一")
    letters = [t.strip() for t in args.tracks.split(",")]
    tracks = {l.lower(): f"Track {l.upper()}" for l in letters}
    if args.sessions:
        ids = args.sessions.split(",")
        if len(ids) != len(tracks):
            p.error("--sessions 个数需与 --tracks 一致")
        args.session_ids = dict(zip(tracks, ids))
    raw = Path(args.prompt_file).read_text(encoding="utf-8")
    common, sections = split_prompt(raw)
    missing = [l for l in letters if l.upper() not in sections]
    if missing:
        p.error("提示词文件缺少轨道段: " + ", ".join(f"## Track {l.upper()}" for l in missing))
    prompts = {k: track_prompt(common, sections, k.upper(), args.base) for k in tracks}
    codex = shutil.which("codex")
    if not codex:
        print("找不到 codex 命令", file=sys.stderr)
        return 2
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=args.cwd).strip()
    workdir = Path(args.cwd)
    package = Path(args.package) if Path(args.package).is_absolute() else workdir / args.package
    attempt = json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))["attempt"]["id"]
    reviews = Path(args.out_dir) if args.out_dir else package / "execution" / attempt / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(len(tracks)) as pool:
        results = list(pool.map(lambda k: run_track(k, tracks[k], args, prompts[k], head, codex, workdir), tracks))

    verdicts, problems, sessions = {}, [], {}
    for key, track, log, output, rc in results:
        report_path, raw_path = report_paths(reviews, args.run, key)
        raw_path.write_text(log, encoding="utf-8")
        if args.new:
            sessions[key] = extract_session_id(output)
        try:
            report = extract_report(log)
            verdicts[track] = validate_header(report, head, args.run, track)
            report_path.write_text(report, encoding="utf-8")
        except ValueError as e:
            problems.append(f"{track}: {e}（codex 退出码 {rc}）")
    if sessions:
        ids = {k.upper(): v for k, v in sessions.items()}
        if all(ids.values()):
            (reviews / f"{args.run}-sessions.json").write_text(
                json.dumps(ids, ensure_ascii=False) + "\n", encoding="utf-8")
            print("sessions: " + ",".join(f"{k}={v}" for k, v in ids.items()))
        else:
            missing = [f"Track {k}" for k, v in ids.items() if not v]
            print("未取到 session id: " + ", ".join(missing), file=sys.stderr)
    if problems:
        print("报告未通过校验：\n" + "\n".join(problems), file=sys.stderr)
        return 1
    failed = [t for t, v in verdicts.items() if v != "PASS"]
    if failed:
        print("FAIL 轨道: " + ", ".join(failed))
        return 1
    # 可直接 `trail append` 的 review.terminal_summary；artifact 为包内相对路径（--out-dir 须在包内）
    try:
        rel = reviews.resolve().relative_to(package.resolve()).as_posix()
    except ValueError:
        print("--out-dir 须在包目录内，terminal_summary 的 artifact 要求包内相对路径", file=sys.stderr)
        return 1
    print(json.dumps({"kind": "fact", "subject": "attempt", "key": "review.terminal_summary", "value": {
        "reviewRunId": args.run, "comparisonHead": head, "safetyApplicable": "Track D" in verdicts,
        "results": [{"track": t, "verdict": "PASS", "reviewedHead": head, "artifact": f"{rel}/{args.run}-track-{k}.md"}
                    for k, t in tracks.items()]}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
