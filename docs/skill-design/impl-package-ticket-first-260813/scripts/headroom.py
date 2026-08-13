import json, statistics

FILES = [
    ("S1", r"C:\Users\Xiao\.codex\sessions\2026\08\11\rollout-2026-08-11T15-51-52-019ff118-08c4-72a1-9189-aac3c4a74b7c.jsonl"),
    ("S2", r"C:\Users\Xiao\.codex\sessions\2026\08\12\rollout-2026-08-12T21-38-29-019ff77b-bd60-7d71-8035-e7410b23ab89.jsonl"),
    ("S3", r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T01-00-17-019ff834-7ee0-7a90-b36e-a1f4303c5238.jsonl"),
    ("S4", r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T06-27-26-019ff960-0217-7e83-acfa-cd1b6c7e5ab4.jsonl"),
    ("S5", r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T09-42-10-019ffa12-4994-7ea3-ac29-3ca4498304e7.jsonl"),
]

all_deltas = []
peaks = []
print(f"{'sess':5} {'segs':>5} {'seg_reqs(med)':>14} {'trough→peak(med)':>17} {'peak(max)':>10}")
for name, f in FILES:
    ctx = []
    for line in open(f, encoding='utf-8', errors='ignore'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        pl = d.get('payload') or {}
        if pl.get('type') == 'token_count':
            lu = (pl.get('info') or {}).get('last_token_usage') or {}
            v = lu.get('input_tokens')
            if v:
                ctx.append(v)
    # segment at drops (compaction / reset)
    segs = []
    cur = [ctx[0]]
    for a, b in zip(ctx, ctx[1:]):
        if b < a * 0.6:          # a real reset, not noise
            segs.append(cur)
            cur = [b]
        else:
            cur.append(b)
            if b > a:
                all_deltas.append(b - a)
    segs.append(cur)
    segs = [s for s in segs if len(s) >= 5]
    rises = [max(s) - min(s) for s in segs]
    lens = [len(s) for s in segs]
    peaks.append(max(ctx))
    print(f"{name:5} {len(segs):5d} {int(statistics.median(lens)):14d} "
          f"{int(statistics.median(rises)):17,d} {max(ctx):10,d}")

all_deltas.sort()
n = len(all_deltas)
print(f"\n每次请求的上下文增量（正增长 {n} 个样本）：")
for q, label in ((0.50, 'p50'), (0.75, 'p75'), (0.90, 'p90'), (0.95, 'p95')):
    print(f"  {label}: {all_deltas[int(n*q)]:>7,d} tokens")

WIN = 258_400
print(f"\n窗口 {WIN:,}，自动压缩实测触发点 ≈ {int(statistics.median(peaks)):,} "
      f"({statistics.median(peaks)/WIN*100:.0f}%)")
print("\n若在某阈值发出「准备交接」警告，收尾还要 R 次请求，落地占用为：")
p75 = all_deltas[int(n * 0.75)]
for pct in (0.45, 0.50, 0.60, 0.70):
    warn = int(WIN * pct)
    print(f"  警告线 {pct:.0%} ({warn:,})：", end='')
    for R in (10, 20, 30, 50):
        land = warn + p75 * R
        flag = "  " if land < 150_000 else ("!!" if land > statistics.median(peaks) else "! ")
        print(f"  R={R}→{land:>7,d}{flag}", end='')
    print()
print(f"\n（用 p75 增量 {p75:,}/请求估算；! = 已过 150k 智能区，!! = 已触发自动压缩）")
