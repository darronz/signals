"""
Shared pytest fixtures for the Signals newsletter digest pipeline tests.

The config fixture provides a SanitizerConfig with known test values so tests
can be explicit about what PII should be redacted. Tests inject SanitizerConfig
directly rather than calling load_config() — this avoids needing a .env file
present during testing (see 01-RESEARCH.md Pitfall 5).
"""

import pytest
from src.models import SanitizerConfig


@pytest.fixture
def config():
    """Shared sanitizer config with known test values for PII redaction assertions."""
    return SanitizerConfig(
        user_email="testuser@example.com",
        user_name="Alice Testington",
        extra_patterns=[],
        max_body_chars=15_000,
    )
