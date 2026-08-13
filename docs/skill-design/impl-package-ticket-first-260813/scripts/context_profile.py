import json

FILES = [
    ("S1", r"C:\Users\Xiao\.codex\sessions\2026\08\11\rollout-2026-08-11T15-51-52-019ff118-08c4-72a1-9189-aac3c4a74b7c.jsonl"),
    ("S2", r"C:\Users\Xiao\.codex\sessions\2026\08\12\rollout-2026-08-12T21-38-29-019ff77b-bd60-7d71-8035-e7410b23ab89.jsonl"),
    ("S3", r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T01-00-17-019ff834-7ee0-7a90-b36e-a1f4303c5238.jsonl"),
    ("S4", r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T06-27-26-019ff960-0217-7e83-acfa-cd1b6c7e5ab4.jsonl"),
    ("S5", r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T09-42-10-019ffa12-4994-7ea3-ac29-3ca4498304e7.jsonl"),
]

print(f"{'sess':5} {'reqs':>5} {'peak_ctx':>9} {'win':>8} {'>100k':>7} {'>150k':>7} {'>200k':>7} {'compact':>8}")
rows = []
for name, f in FILES:
    ctx = []
    win = 0
    compacts = 0
    for line in open(f, encoding='utf-8', errors='ignore'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        pl = d.get('payload') or {}
        t = pl.get('type')
        if t == 'context_compacted':
            compacts += 1
        if t == 'token_count':
            info = pl.get('info') or {}
            win = info.get('model_context_window') or win
            lu = info.get('last_token_usage') or {}
            v = lu.get('input_tokens')
            if v:
                ctx.append(v)
    if not ctx:
        continue
    n = len(ctx)
    p100 = sum(1 for v in ctx if v > 100_000) / n * 100
    p150 = sum(1 for v in ctx if v > 150_000) / n * 100
    p200 = sum(1 for v in ctx if v > 200_000) / n * 100
    print(f"{name:5} {n:5d} {max(ctx):9,d} {win:8,d} {p100:6.1f}% {p150:6.1f}% {p200:6.1f}% {compacts:8d}")
    rows.append((name, ctx))

print("\n-- 上下文占用轨迹（每 session 取 12 个等距采样点，单位 k tokens）--")
for name, ctx in rows:
    n = len(ctx)
    idx = [int(i * (n - 1) / 11) for i in range(12)]
    print(f"  {name}: " + " ".join(f"{ctx[i]//1000:>4}" for i in idx))
