# DATEV Tax Accounting Skill References

这些文件是 `datev-tax-accounting` 的渐进式参考资料。KaiSpan-specific current truth 仍以仓库中的 Finance context 和 module-knowledge 为准；本目录中的公开年度资料只提供可复核的标准基线。

## 入口

- [datev-glossary.md](datev-glossary.md)：DATEV、税务和 EXTF 术语。
- [source-policy.md](source-policy.md)：来源等级、适用范围、hash 和隐私边界。
- [supported-knowledge-map.md](supported-knowledge-map.md)：公开规则与当前 Finance 实现能力的对应关系。
- [sources/2026-official/README.md](sources/2026-official/README.md)：已复制的公开 2026 原始资料和 SHA-256。

## 资料边界

Mandant-specific Kontenplan、Kreditor、BWA、DTVF、发票原件和税务师内部配置不复制到 Skill。它们只通过受控外部路径、profile identity、source hash 和批准状态被引用。Skill 不提供生产 DATEV 凭证写入，也不替代税务师判断。
