---
name: kaispan-ui-design-review
description: KaiSpan UI 设计审查 Skill。用户要求审查 kaispan-ui-design Skill suite、global capture、project/module readiness、Billing/Webshop 等项目 UI 迁移计划、shared UI 边界、事实源冲突或发布安全风险时使用；默认输出审查发现，不直接重写方案。
---

# KaiSpan UI Design Review

本 Skill 用于审查 UI 工具箱、全局 capture 和模块迁移计划。默认采取 code-review 式输出：先列风险和阻塞，再给简短结论。

## 使用前读取

读取 `references/review-checklist.md`。若审查对象涉及具体模块，再按模块范围读取其 readiness bridge、slice plan、PRD、实现和测试。

## 审查重点

1. Skill suite 是否变成事实仓库。
2. global assets 和 module assets 是否混放。
3. 提交版配置、模板或正式 docs 是否出现本机绝对路径。
4. locator 是否可解析；缺失时是否输出 `blocked-by-skill-missing-locator`。
5. publishability/security gate 是否覆盖 source、fonts、images、screenshots、demo data。
6. 是否把 prototype/Webshop/old POC 中未实现能力标成 `real`。
7. 是否绕过 tenant isolation、RBAC、file security、audit、API contracts、Action Center URL 不落库等 gates。
8. shared UI 是否误放业务状态、权限、scope、mutation 或 audit。

## discuss-ledger 口径

不要默认重开 `discuss-ledger`。只有用户明确要求，或审查中出现复杂多方争议且需要独立角色收敛时，才建议使用；建议时说明具体争议、参与角色和预期裁决，不把它当作普通 review 的默认步骤。

## 输出格式

优先使用：

```text
状态: PASS / PASS_WITH_CONCERNS / BLOCKED

发现:
- [P1] <问题> — <证据或文件位置>

阻塞项:
- <缺失 locator / 缺失事实源 / 缺失 gate>

建议:
- <下一步>
```

如果没有发现问题，明确说明剩余测试或事实源风险。
