import json, collections, os, glob

FILES = [
    r"C:\Users\Xiao\.codex\sessions\2026\08\11\rollout-2026-08-11T15-51-52-019ff118-08c4-72a1-9189-aac3c4a74b7c.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\12\rollout-2026-08-12T21-38-29-019ff77b-bd60-7d71-8035-e7410b23ab89.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T01-00-17-019ff834-7ee0-7a90-b36e-a1f4303c5238.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T06-27-26-019ff960-0217-7e83-acfa-cd1b6c7e5ab4.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T09-42-10-019ffa12-4994-7ea3-ac29-3ca4498304e7.jsonl",
]

print(f"{'sess':5} {'thread_src':10} {'cwd_tail':34} {'patches':>8} {'compact':>8} {'tok_last':>10} {'start':>21}")
for i, f in enumerate(FILES, 1):
    patches = 0
    compacts = 0
    thread_source = ''
    cwd = ''
    start = ''
    last_tokens = None
    for line in open(f, encoding='utf-8', errors='ignore'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        t = d.get('type')
        pl = d.get('payload') or {}
        if t == 'session_meta' and not thread_source:
            thread_source = pl.get('thread_source', '')
            cwd = pl.get('cwd', '')
            start = d.get('timestamp', '')
        pt = pl.get('type')
        if pt == 'patch_apply_end':
            patches += 1
        if pt == 'context_compacted':
            compacts += 1
        if pt == 'token_count':
            info = pl.get('info') or {}
            tu = info.get('total_token_usage') or {}
            if tu.get('input_tokens'):
                last_tokens = tu
    tot = (last_tokens or {}).get('input_tokens', 0) + (last_tokens or {}).get('output_tokens', 0)
    print(f"S{i:<4} {thread_source:10} {cwd[-34:]:34} {patches:8d} {compacts:8d} {tot:10d} {start[:19]:>21}")
