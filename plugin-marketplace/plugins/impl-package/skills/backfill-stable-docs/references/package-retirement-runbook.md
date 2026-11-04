# Package Retirement

A package is only a retirement candidate when:

1. its current Gate is terminal and names an available Git comparison commit;
2. the implementation is reachable from the configured target branch;
3. every durable delta is absorbed, already covered, or explicitly closed;
4. durable deltas are absorbed or closed in `records.done`, optional pending no longer needs the package, and inbound repository references no longer need it;
5. the directory contains no active attempt or unique evidence still required.

Audit reports candidates; deletion requires separate owner authorization and an exact repository-relative path list.

## Decision → ADR（退役前必做）

package 的 `decision.md` 记录了「为什么这样选」、比较过的方案和放弃的承诺，stable docs 只写当前行为，不承接这些内容，所以删包前先把它转成 ADR：

1. **模板**：优先用仓库本地模板（按仓库的 ADR 路由找，例如 `docs/adr/TEMPLATE.md` 或 ADR README 指定的模板）；没有本地模板时用 [assets/adr-template.md](../assets/adr-template.md)。
2. **位置与编号**：按仓库 ADR 路由放到 repo-wide 或 owner-local 的 `adr/` 下，编号接续该目录，并更新对应索引。
3. **内容**：保留原 decision 的背景、选项对比表、选中方向与理由、Owner 决定表、约束和已知限制，不压缩成摘要；删去 Gate 记录、委派、Ticket、证据指针等过程材料。patch plan、amendment 里后续补充的决定并入「后续补充决定」，没有新决定的材料列一行说明。被后续包撤回或取代的承诺写进「后果」，指向取代它的 ADR 或当前文档。
4. **链接**：ADR 是 stable doc，不得链接 implementation package；来源写纯文本包 ID。「当前事实所在」链接承接当前行为的 canonical docs / runbook。
5. **退役记录**：退役记录（如 `docs/implementations/retired.json`）写明包 ID、路径、退役日期、最后含包的提交、终态和 ADR 路径。包内没有 `decision.md` 时，确认关键选择已进 canonical docs，记录里注明「无 decision」。

**终态无法写入 Gate 时**：旧 schema 的包，Gate CLI 可能因校验失败拒绝写终态。此时以 Owner 明确的终态决定（例如「接受为终态，不补跑」）写入退役记录即可，不为待删的包补 spec 或状态。

Terminal Gate 或实现已进入 target branch 单独都不足以证明可退役；仍需确认 durable meaning 已吸收/关闭、没有活动证据且没有 inbound reference。
