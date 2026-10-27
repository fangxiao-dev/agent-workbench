# Full Review Checklist

Only read this reference when `review-code` selects **Full behavior review**. Apply the items that match the actual diff; do not invent findings for inapplicable checklist entries.

## High-level review

**Architecture and design**:
- Does the approach make sense?
- Is it consistent with existing patterns?
- Are there simpler alternatives?
- Is the code in the right place?

**Code organization**:
- Clear separation of concerns?
- Appropriate abstraction levels?
- Logical file/folder structure?

## Standards and maintainability

仓库规范、smell 与设计基线在同一份完整 diff 上与行为审查一并完成；先完成这一基线，再决定是否深挖。

- **仓库规范优先**：应用调用者提供的全部仓库规则（AGENTS.md、CODING_STANDARDS.md、CONTRIBUTING.md 等）；仓库认可的写法覆盖通用 baseline，与之冲突的 smell 不作 finding；lint/formatter/类型检查等工具已可靠执行的规则不重复报告。
- **Hard violation 与 judgement call 分开**：违反仓库规则文件是 hard violation，必须引用规则文件；Fowler smell 和 deep-module 词汇是 judgement call，点名 baseline 并引用 changed hunk，不伪装成仓库未声明的硬规则。
- **Fowler code-smell baseline**（每条落到具体 hunk）：Mysterious Name（名称说不清职责→重命名，无法诚实命名则指出设计含糊）；Duplicated Code（多处相同逻辑形状→抽取共享形状）；Feature Envy（访问他人数据多于自身→行为移到数据侧）；Data Clumps（相同字段/参数组合反复同行→提炼类型）；Primitive Obsession（primitive/string 代替值得命名的领域概念→小型领域类型）；Repeated Switches（同类 switch/条件链重复→多态或共享映射）；Shotgun Surgery（一个逻辑变化散落多文件→收拢到共同 module）；Divergent Change（一个文件因多个无关原因被修改→按变化原因拆分）；Speculative Generality（未被需求要求的抽象/参数/hook→删除）；Message Chains（调用者依赖长导航链→在起点隐藏导航）；Middle Man（主要只转发的层→移除）；Refused Bequest（子类忽略或覆盖大部分继承合同→改用组合）。
- **codebase-design 词汇**：active skill catalog 有 `codebase-design` 时优先读其 deep module 词汇，否则用此基线——interface 以小表面承载足够行为（depth/leverage）；知识与验证留在合适 seam（locality）；新增 adapter 要有真实可变性依据；interface 包含调用方必须知道的 invariant、错误模式和顺序约束，而不只是类型签名。
- **深挖选择**：普通局部 diff 做完基线即可。Owner 明确要求严格可维护性审查，或 reviewer 凭证据判断结构需要复核（shared path 出现 feature-specific 分支、同一概念的条件/flag/mode 跨 hunk 增长、adapter/wrapper/松散类型边界增加、知识离开 canonical layer、模块明显膨胀、存在可删除整层间接的机会）时，读 [strict-maintainability.md](strict-maintainability.md)。这些信号是非穷尽启发式，不自动成为 finding；不因“还能更优雅”、单一文件行数或个人偏好产生 finding。
- **证据**：structural finding 说明 changed hunk 中新增或放大的复杂度、可解释的维护风险、可行的简化或集中方向，以及它是 hard violation 还是 judgement call。

## Detailed code review

**Naming**:
- [ ] Variables: descriptive, meaningful names
- [ ] Functions: verb-based, clear purpose
- [ ] Classes: noun-based, single responsibility
- [ ] Constants: UPPER_CASE for true constants
- [ ] Avoid abbreviations unless widely known

**Functions**:
- [ ] Single responsibility
- [ ] Reasonable length (< 50 lines ideally)
- [ ] Clear inputs and outputs
- [ ] Minimal side effects
- [ ] Proper error handling

**Classes and objects**:
- [ ] Single responsibility principle
- [ ] Open/closed principle
- [ ] Liskov substitution principle
- [ ] Interface segregation
- [ ] Dependency inversion

**Error handling**:
- [ ] All errors caught and handled
- [ ] Meaningful error messages
- [ ] Proper logging
- [ ] No silent failures
- [ ] User-friendly errors for UI

**Code quality**:
- [ ] No code duplication (DRY)
- [ ] No dead code
- [ ] No commented-out code
- [ ] No magic numbers
- [ ] Consistent formatting

## Security review

**Input validation**:
- [ ] All user inputs validated
- [ ] Type checking
- [ ] Range checking
- [ ] Format validation

**Authentication & Authorization**:
- [ ] Proper authentication checks
- [ ] Authorization for sensitive operations
- [ ] Session management
- [ ] Password handling (hashing, salting)

**Data protection**:
- [ ] No hardcoded secrets
- [ ] Sensitive data encrypted
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] CSRF protection

**Dependencies**:
- [ ] No vulnerable packages
- [ ] Dependencies up-to-date
- [ ] Minimal dependency usage

## Performance review

**Algorithms**:
- [ ] Appropriate algorithm choice
- [ ] Reasonable time complexity
- [ ] Reasonable space complexity
- [ ] No unnecessary loops

**Database**:
- [ ] Efficient queries
- [ ] Proper indexing
- [ ] N+1 query prevention
- [ ] Connection pooling

**Caching**:
- [ ] Appropriate caching strategy
- [ ] Cache invalidation handled
- [ ] Memory usage reasonable

**Resource management**:
- [ ] Files properly closed
- [ ] Connections released
- [ ] Memory leaks prevented

## Testing review

**Test coverage**:
- [ ] Unit tests for new code
- [ ] Integration tests if needed
- [ ] Edge cases covered
- [ ] Error cases tested

**Test quality**:
- [ ] Tests are readable
- [ ] Tests are maintainable
- [ ] Tests are deterministic
- [ ] No test interdependencies
- [ ] Proper test data setup/teardown

**Test naming**:
详见 [审查示例](examples.md#test-naming)。

## Documentation review

**Code comments**:
- [ ] Complex logic explained
- [ ] No obvious comments
- [ ] TODOs have tickets
- [ ] Comments are accurate

**Function documentation**:
详见 [审查示例](examples.md#function-documentation)。

**README/docs**:
- [ ] README updated if needed
- [ ] API docs updated
- [ ] Migration guide if breaking changes

## Review checklist

### Functionality
- [ ] Code does what it's supposed to do
- [ ] Edge cases handled
- [ ] Error cases handled
- [ ] No obvious bugs

### Code Quality
- [ ] Clear, descriptive naming
- [ ] Functions are small and focused
- [ ] No code duplication
- [ ] Consistent with codebase style
- [ ] No code smells

### Security
- [ ] Input validation
- [ ] No hardcoded secrets
- [ ] Authentication/authorization
- [ ] No SQL injection vulnerabilities
- [ ] No XSS vulnerabilities

### Performance
- [ ] No obvious bottlenecks
- [ ] Efficient algorithms
- [ ] Proper database queries
- [ ] Resource management

### Testing
- [ ] Tests included
- [ ] Good test coverage
- [ ] Tests are maintainable
- [ ] Edge cases tested

### Documentation
- [ ] Code is self-documenting
- [ ] Comments where needed
- [ ] Docs updated
- [ ] Breaking changes documented

## Common issues

详见 [审查示例](examples.md#common-issues)。

## Best practices

1. **Review promptly**: Don't make authors wait
2. **Be respectful**: Focus on code, not the person
3. **Explain why**: Don't just say what's wrong
4. **Suggest alternatives**: Show better approaches
5. **Use examples**: Code examples clarify feedback
6. **Pick your battles**: Focus on important issues
7. **Acknowledge good work**: Positive feedback matters
8. **Review your own code first**: Catch obvious issues
9. **Use automated tools**: Let tools catch style issues
10. **Be consistent**: Apply same standards to all code

## Tools to use

**Linters**:
- Python: pylint, flake8, black
- JavaScript: eslint, prettier
- Go: golint, gofmt
- Rust: clippy, rustfmt

**Security**:
- Bandit (Python)
- npm audit (Node.js)
- OWASP Dependency-Check

**Code quality**:
- SonarQube
- CodeClimate
- Codacy

## References

- [Google Code Review Guidelines](https://google.github.io/eng-practices/review/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Clean Code by Robert C. Martin](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882)
