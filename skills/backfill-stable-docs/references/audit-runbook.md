# Audit Runbook

Audit 对 source 只读；唯一允许写入是配置 `compactionPath` 下的新报告。先运行 `scripts/validate_config.py`，再以固定 Source HEAD、watermark、carry-forward 和配置执行 `scripts/collect_sources.py`。报告必须符合 [audit JSON contract](audit-json-contract.md)，每个 module 都有 `candidate`、`already-covered`、`conflict` 或 `no-delta` 结论，并为可处理条目生成稳定 item ID。

只把 `design.md` 和 `spec.md` 作为默认 semantic source；`findings.md` 仅作 supplemental evidence，只有被 design/spec 明确引用或出现 evidence gap / authority conflict 才读取并记录理由。`gate.md`、pending 和 commits 只做 closure/coverage 对账。先判断 durable intent，再判断可验证行为；两者皆是才是 module spec 候选。冲突不得自行裁决。

报告不能推进 watermark、清 pending、改 canonical docs 或修复链接。旧 Plugin-era 记录不能作为 apply 输入；本次 audit 必须重新固定当前 public Skill bundle 的 repository+commit 锚点。
