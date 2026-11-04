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
2. **位置与编号**：按仓库 ADR 路由放到 repo-wide 或 owner-local 的 `adr/` 下，编号接续该目录，并更新对应索引。首次创建某个 owner 的 `adr/` 时，同步更新该 owner README 里的 ADR 路由；owner-local ADR 不需要改 repo-wide ADR 索引。
3. **内容**：保留原 decision 的背景、选项对比表、选中方向与理由、Owner 决定表、约束和已知限制，不压缩成摘要；删去 Gate 记录、委派、Ticket、证据指针等过程材料。patch plan、amendment 里后续补充的决定并入「后续补充决定」，没有新决定的材料列一行说明。被后续包撤回或取代的承诺写进「后果」，指向取代它的 ADR 或当前文档。
4. **链接**：ADR 是 stable doc，不得链接 implementation package；来源只写包 ID，不带 `docs/implementations/` 等路径前缀。「当前事实所在」链接承接当前行为的 canonical docs / runbook。退役前用 `grep -rn <package-id> docs` 核对，只允许 ADR、pending 来源栏、done/retired 记录里出现纯文本包 ID。
5. **没有 `decision.md` 时**：检查 plan 的批准范围、约束和回退约束。其中有被放弃的方案，就照常建 ADR，备选表只写材料里明确排除的方案，不补造；决定人写「Owner（原话批准）」并注明日期。没有真实取舍时不建 ADR，在退役记录里注明「无 decision」。
6. **未吸收事项迁入 pending**：包里还没做的事项（如生产开放准备项）登记到 owner 的 `_pending.md`，行格式与该文件表头一致，来源栏写纯文本包 ID；done 记 `deferred` 并带 `pendingRef`。
7. **退役记录**：退役记录（如 `docs/implementations/retired.json`）每条包含：

   | 字段 | 取值 |
   | --- | --- |
   | `package_id` | 包 ID（必填） |
   | `path` | 包的仓库相对路径 |
   | `retiredAt` | 退役日期 |
   | `lastCommitWithPackage` | 删除提交之前的 HEAD，即最后一个仍含该包的提交，可用 `git show <sha>:<path>` 查看 |
   | `terminal` | 终态说明（Gate 结论，或 Owner 的终态决定） |
   | `decisionRecord` | ADR 路径；没有时写「无 decision」 |
   | `semantics` | 吸收去向的 canonical 文档列表 |

**终态无法写入 Gate 时**：旧 schema 的包，Gate CLI 可能因校验失败拒绝写终态。此时以 Owner 明确的终态决定（例如「接受为终态，不补跑」）写入退役记录即可，不为待删的包补 spec 或状态。

Terminal Gate 或实现已进入 target branch 单独都不足以证明可退役；仍需确认 durable meaning 已吸收/关闭、没有活动证据且没有 inbound reference。
