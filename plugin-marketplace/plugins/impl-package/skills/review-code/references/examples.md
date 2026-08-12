# Code Review Examples

The following examples were moved from `SKILL.md` without changing their review meaning.

## Test naming

```python
# Good
def test_user_creation_with_valid_data_succeeds():
    pass

# Bad
def test1():
    pass
```

## Function documentation

```python
def calculate_total(items: List[Item], tax_rate: float) -> Decimal:
    """
    Calculate the total price including tax.

    Args:
        items: List of items to calculate total for
        tax_rate: Tax rate as decimal (e.g., 0.1 for 10%)

    Returns:
        Total price including tax

    Raises:
        ValueError: If tax_rate is negative
    """
    pass
```

## Constructive feedback

```
✅ Good:
"Consider extracting this logic into a separate function for better
testability and reusability:

def validate_email(email: str) -> bool:
    return '@' in email and '.' in email.split('@')[1]

This would make it easier to test and reuse across the codebase."

❌ Bad:
"This is wrong. Rewrite it."
```

## Specific feedback

```
✅ Good:
"On line 45, this query could cause N+1 problem. Consider using
.select_related('author') to fetch related objects in a single query."

❌ Bad:
"Performance issues here."
```

## Acknowledge good work

```
"Nice use of the strategy pattern here! This makes it easy to add
new payment methods in the future."
```

## Common issues

### Anti-patterns

**God class**:
```python
# Bad: One class doing everything
class UserManager:
    def create_user(self): pass
    def send_email(self): pass
    def process_payment(self): pass
    def generate_report(self): pass
```

**Magic numbers**:
```python
# Bad
if user.age > 18:
    pass

# Good
MINIMUM_AGE = 18
if user.age > MINIMUM_AGE:
    pass
```

**Deep nesting**:
```python
# Bad
if condition1:
    if condition2:
        if condition3:
            if condition4:
                # deeply nested code

# Good (early returns)
if not condition1:
    return
if not condition2:
    return
if not condition3:
    return
if not condition4:
    return
# flat code
```

### Security vulnerabilities

**SQL Injection**:
```python
# Bad
query = f"SELECT * FROM users WHERE id = {user_id}"

# Good
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
```

**XSS**:
```javascript
// Bad
element.innerHTML = userInput;

// Good
element.textContent = userInput;
```

**Hardcoded secrets**:
```python
# Bad
API_KEY = "sk-1234567890abcdef"

# Good
API_KEY = os.environ.get("API_KEY")
```
