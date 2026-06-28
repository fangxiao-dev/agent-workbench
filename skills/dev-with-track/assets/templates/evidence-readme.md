# [Project / Slice] Evidence

日期：[YYYY-MM-DD]

本轮目标：[一句话说明 preview / harness / real route evidence 要证明什么。]

## 本地入口

- Worktree / repo：[path]
- Route / preview：[path-or-url]
- Guard：[production guard / access guard]
- Data boundary：[fixture-only / real read-only / real route]
- Mutation boundary：[none / disabled / approved smoke]

## 截图或证据文件

- `[surface]-desktop-[size].png`
- `[surface]-constrained-[size].png`
- `[dom-geometry-or-console-dump].txt`

## 检查结果

- [ ] 目标 surface 已覆盖。
- [ ] Desktop viewport 已检查。
- [ ] Constrained viewport 已检查。
- [ ] Console 无 error / warning，或已记录。
- [ ] Hydration 状态已检查。
- [ ] 可见 clipping / overflow / density 问题已记录到 findings。
- [ ] fixture 没有生产数据或外部 mutation。

## 发现的后续问题

- [finding]
- [finding]

## 下一步建议

1. [next step]
2. [next step]
