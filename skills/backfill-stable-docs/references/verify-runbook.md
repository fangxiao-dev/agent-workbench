# Verify Runbook

Verify 是独立只读阶段。运行 `scripts/verify_stable_docs.py --project-root <root> [--config <path>] [--audit-json <path>]`，检查配置路径、canonical links、危险内容规则、audit contract、method activation、pending/carry-forward 与 Project Source Watermark。

verify 不创建报告，不改 canonical docs，不清 pending，不推进 watermark，也不把失败项隐式 apply。Plugin-era audit/state 与当前 public bundle 的 repository+commit 不匹配时，结果必须 fail closed，并要求重新 audit。
