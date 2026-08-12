---
name: review-code
description: 当需要审查 pull request、固定 comparison point 的代码 diff 或相关实现变更时使用；重点检查运行行为、错误处理、安全、性能、资源、并发/原子性、测试风险与一般代码质量。
allowed-tools: Read Grep Glob
metadata:
  tags: review-code, code-review, code-quality, security, best-practices, PR-review
  platforms: Codex, Claude, ChatGPT, Gemini
---


# Review Code

## 审查偏重

优先关注变更后的行为、错误处理、安全、性能、资源、并发/原子性和测试风险；下方既有审查知识与 checklist 仍完整适用，不因该偏重而失效。

结构、模块归属、抽象与一般 code-quality 现象同样可以继续被发现和报告。审查偏重是选择注意力的启发式，不是能力禁令；每项输出只说明自身证据、风险与建议。

## When to use this skill
- Reviewing pull requests
- Checking code quality
- Providing feedback on implementations
- Identifying potential bugs
- Suggesting improvements
- Security audits
- Performance analysis

## Instructions

### Step 1: Understand the context

**Choose the smallest review profile that matches the diff**:
- Code/behavior changes use the full workflow below.
- Docs/evidence/config-metadata-only changes use a focused profile: verify factual consistency with canonical sources, links/paths, ownership, authorization claims, generated-vs-source boundaries, and whether the delta accidentally changes executable behavior. Skip function/class/performance/testing checklists that cannot apply. Escalate to the full profile only when the diff changes runtime behavior or hides an unresolved contract/safety change.
- Deletions and direction corrections are reviewed against what remains authoritative; do not demand replacement content or broader tests unless removal changes an observable contract.

**Read the PR description**:
- What is the goal of this change?
- Which issues does it address?
- Are there any special considerations?

**Check the scope**:
- How many files changed?
- What type of changes? (feature, bugfix, refactor)
- Are tests included?

### Step 2: High-level review

**Architecture and design**:
- Does the approach make sense?
- Is it consistent with existing patterns?
- Are there simpler alternatives?
- Is the code in the right place?

**Code organization**:
- Clear separation of concerns?
- Appropriate abstraction levels?
- Logical file/folder structure?

### Step 3: Detailed code review

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

### Step 4: Security review

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

### Step 5: Performance review

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

### Step 6: Testing review

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
详见 [审查示例](references/examples.md#test-naming)。

### Step 7: Documentation review

**Code comments**:
- [ ] Complex logic explained
- [ ] No obvious comments
- [ ] TODOs have tickets
- [ ] Comments are accurate

**Function documentation**:
详见 [审查示例](references/examples.md#function-documentation)。

**README/docs**:
- [ ] README updated if needed
- [ ] API docs updated
- [ ] Migration guide if breaking changes

### Step 8: Provide feedback

**No-finding evidence (required)**:
- Do not return a bare `PASS` or "no issues found".
- Include a concise Coverage record: changed production entry points/modules inspected, review dimensions applied (for example behavior, errors, security, resource handling, tests), and the result.
- Name high-risk paths that were inspected without a finding, and any paths that could not be verified from the diff or supplied context.
- This is review evidence, not a requirement to invent findings or run unrelated tools.

**Be constructive**:
详见 [审查示例](references/examples.md#constructive-feedback)。

**Be specific**:
详见 [审查示例](references/examples.md#specific-feedback)。

**Prioritize issues**:
- 🔴 Critical: Security, data loss, major bugs
- 🟡 Important: Performance, maintainability
- 🟢 Nice-to-have: Style, minor improvements

**Acknowledge good work**:
详见 [审查示例](references/examples.md#acknowledge-good-work)。

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

详见 [审查示例](references/examples.md#common-issues)。

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

## Examples

### Example 1: Basic usage
<!-- Add example content here -->

### Example 2: Advanced usage
<!-- Add advanced example content here -->
