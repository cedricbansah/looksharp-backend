# Testing Conventions

Tests use `pytest-django` with `@pytest.mark.django_db`. Firebase calls are always mocked:

```python
@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mock:
        yield mock
```

Factories use `factory-boy`. Datetime-sensitive tests use `freezegun`.
