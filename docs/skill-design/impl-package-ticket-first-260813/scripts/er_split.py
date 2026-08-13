import re, glob, os

FILES = glob.glob(r"D:/CodeSpace/kaispan-dev/.worktrees/260809-finance-assistant-mvp/docs/implementations/2026-08-10-accounting-scope-policy-ownership/execution/*/execution-record.md") + \
        glob.glob(r"D:/CodeSpace/kaispan-dev/.worktrees/260812-datev-mandant-profile-import-planning/docs/domains/finance-assistant/implementations/2026-08-11-datev-mandant-profile-import/execution/*/execution-record.md")

HEAD = re.compile(r"^## (\S+-ER-\d{3}) · (checkpoint|judgment)\s*$", re.M)


def est(t):
    c = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', t))
    return int(c * 0.9 + (len(t) - c) / 3.6)


print(f"{'package/attempt':46} {'ckpt':>6} {'judg':>6} {'ckpt_tok':>9} {'judg_tok':>9} {'ckpt%':>6}")
tc = tj = 0
for f in FILES:
    text = open(f, encoding='utf-8', errors='ignore').read()
    ms = list(HEAD.finditer(text))
    ck = jd = 0
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        size = est(text[m.start():end])
        if m.group(2) == 'checkpoint':
            ck += size
        else:
            jd += size
    tc += ck
    tj += jd
    parts = f.replace('\\', '/').split('/')
    label = parts[-4][:26] + '/' + parts[-2]
    nck = sum(1 for m in ms if m.group(2) == 'checkpoint')
    njd = len(ms) - nck
    print(f"{label:46} {nck:6d} {njd:6d} {ck:9,d} {jd:9,d} {ck/(ck+jd)*100:5.0f}%")
print(f"{'TOTAL':46} {'':6} {'':6} {tc:9,d} {tj:9,d} {tc/(tc+tj)*100:5.0f}%")
