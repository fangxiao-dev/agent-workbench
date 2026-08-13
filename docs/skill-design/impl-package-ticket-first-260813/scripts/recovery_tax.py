import json, re, collections

P = r"C:\Users\Xiao\AppData\Local\Temp\claude\D--CodeSpace-agent-workbench\5f82b0e4-78b2-4eae-a22d-30ff466025c7\scratchpad\codex-work\analysis_data\function_calls.jsonl"
CMD_RE = re.compile(r'command:\s*"((?:[^"\\]|\\.)*)"')
IMPL_RE = re.compile(r'\b(pnpm|npm|npx|jest|vitest|pytest|tsc|eslint|prisma|psql|turbo|git commit)\b')
DOC_RE = re.compile(r'(skill\.md|references/[\w\-]+\.md|agents\.md|plan\.md|spec\.md|decision\.md|contract-design\.md|dag\.md|progress\.md|execution-record\.md|handoff\.md|tickets[/\\\\])')


def get_cmd(a):
    if not a:
        return ''
    m = CMD_RE.search(a)
    if m:
        try:
            return json.loads('"' + m.group(1) + '"')
        except Exception:
            return m.group(1)
    return a[:400]


calls = collections.defaultdict(list)
for line in open(P, encoding='utf-8', errors='ignore'):
    try:
        d = json.loads(line)
    except Exception:
        continue
    calls[d['session']].append(d)

print(f"{'sess':5} {'calls_before_1st_impl':>22} {'docreads_in_prefix':>19} {'state_cli_in_prefix':>20} {'first_impl_cmd'}")
for s in sorted(calls):
    seq = calls[s]
    idx = None
    docs = state = 0
    for i, d in enumerate(seq):
        c = get_cmd(d.get('arguments')) if d.get('name') == 'exec' else ''
        low = c.lower()
        if d.get('name') == 'exec' and IMPL_RE.search(low) and 'impl_package_state.py' not in low:
            idx = i
            first = c[:70].replace('\n', ' ')
            break
        if 'impl_package_state.py' in low:
            state += 1
        elif DOC_RE.search(low):
            docs += 1
    if idx is None:
        print(f"{s:5} {'(none)':>22}")
    else:
        print(f"{s:5} {idx:22d} {docs:19d} {state:20d}  {first}")

print("\n-- 每 session 前 40 次 exec 的分类占比 --")
for s in sorted(calls):
    execs = [d for d in calls[s] if d.get('name') == 'exec'][:40]
    c = collections.Counter()
    for d in execs:
        low = get_cmd(d.get('arguments')).lower()
        if 'impl_package_state.py' in low:
            c['state'] += 1
        elif DOC_RE.search(low):
            c['doc'] += 1
        elif IMPL_RE.search(low):
            c['impl'] += 1
        else:
            c['other'] += 1
    print(f"  {s}: " + "  ".join(f"{k}={c.get(k,0)}" for k in ('doc', 'state', 'impl', 'other')))
