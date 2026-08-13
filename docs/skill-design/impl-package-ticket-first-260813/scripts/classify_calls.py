import json, re, collections

P = r"C:\Users\Xiao\AppData\Local\Temp\claude\D--CodeSpace-agent-workbench\5f82b0e4-78b2-4eae-a22d-30ff466025c7\scratchpad\codex-work\analysis_data\function_calls.jsonl"

CMD_RE = re.compile(r'command:\s*"((?:[^"\\]|\\.)*)"')
STATE_RE = re.compile(r'impl_package_state\.py.*?(init|status|validate|refresh-progress|set-state|er-add|checkpoint|gate)\b', re.S)
DOC_RE = re.compile(r'(skill\.md|references/[\w\-]+\.md|agents\.md|claude\.md|plan\.md|spec\.md|decision\.md|contract-design\.md|dag\.md|progress\.md|execution-record\.md|[\w\-]*handoff\.md|tickets[/\\\\][\w\-.]+\.md|rubric\.md)')
IMPL_RE = re.compile(r'\b(pnpm|npm|npx|jest|vitest|pytest|tsc|eslint|prisma|psql|docker|turbo|git commit|git add)\b')
GIT_RE = re.compile(r'\bgit (diff|log|status|show|rev-parse|grep)\b')
READ_RE = re.compile(r'(get-content|cat |type |select-string|rg |grep |ls |get-childitem|find )')


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


def classify(c):
    l = c.lower()
    if 'impl_package_state.py' in l:
        m = STATE_RE.search(l)
        return 'A_state_cli', (m.group(1) if m else 'other')
    doc = DOC_RE.findall(l)
    impl = IMPL_RE.search(l)
    if doc and not impl:
        return 'B_doc_read', doc[0]
    if impl:
        return 'C_impl', impl.group(1)
    if GIT_RE.search(l):
        return 'D_git_inspect', 'git'
    if READ_RE.search(l):
        return 'E_other_read', 'read'
    return 'F_other', 'other'


cat = collections.Counter()
statesub = collections.Counter()
docsub = collections.Counter()
per = collections.defaultdict(collections.Counter)
tot = 0

for line in open(P, encoding='utf-8', errors='ignore'):
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get('name') != 'exec':
        continue
    tot += 1
    k, s = classify(get_cmd(d.get('arguments')))
    cat[k] += 1
    per[d['session']][k] += 1
    if k == 'A_state_cli':
        statesub[s] += 1
    if k == 'B_doc_read':
        docsub[s] += 1

print(f"total exec: {tot}\n")
print(f"{'category':16} {'count':>6} {'pct':>7}")
for k, v in sorted(cat.items()):
    print(f"{k:16} {v:6d} {v / tot * 100:6.1f}%")

print("\n-- state CLI subcommands --")
for k, v in statesub.most_common():
    print(f"  {k:20} {v}")

print("\n-- top doc reads --")
for k, v in docsub.most_common(15):
    print(f"  {k:34} {v}")

print("\n-- per session --")
keys = sorted(cat)
print(f"{'sess':6}" + "".join(f"{k[:11]:>13}" for k in keys))
for s in sorted(per):
    print(f"{s:6}" + "".join(f"{per[s].get(k, 0):13d}" for k in keys))
