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
