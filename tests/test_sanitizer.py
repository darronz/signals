"""
Test suite for the Signals privacy sanitizer (Plan 01-02 will make these pass).

All tests are written in RED state — they will fail with NotImplementedError
against the Plan 01 stub. Plan 02 implements the sanitizer to make these GREEN.

Test coverage:
  PRIV-01: HTML bodies converted to plain text
  PRIV-02: Tracking pixels (all img tags) removed
  PRIV-03: UTM and other tracking URL parameters stripped
  PRIV-04: User email address and name redacted from body
  PRIV-05: Configurable extra PII redaction patterns applied
  PRIV-06: Sender identity reduced to domain-only
  PRIV-07: Bodies truncated to configurable character limit
  PRIV-08: CleanMessage has no email header fields (structural test)
  DOCS-02: .env.example file exists with all required config keys
  Edge cases: HTML fallback, empty body, subject PII redaction
"""

import dataclasses
from pathlib import Path

import pytest
from src.models import RawMessage, CleanMessage, SanitizerConfig
from src.sanitizer import sanitize


# ---------------------------------------------------------------------------
# PRIV-01: HTML body converted to plain text
# ---------------------------------------------------------------------------

def test_output_is_plain_text(config):
    """PRIV-01: HTML input is converted to clean plain text with no HTML tags."""
    raw = RawMessage(
        subject="Test Newsletter",
        sender="newsletter@example.com",
        date="2026-03-11",
        body_html=(
            "<html><body>"
            "<h1>Title</h1>"
            "<p>Paragraph content here.</p>"
            "<script>alert(1)</script>"
            "</body></html>"
        ),
        body_text=None,
    )
    result = sanitize(raw, config)

    # No HTML tags should remain in output
    assert "<" not in result.clean_text
    assert ">" not in result.clean_text

    # Script content should be stripped, not just the tags
    assert "alert" not in result.clean_text

    # Actual content should be preserved
    assert "Title" in result.clean_text or "Paragraph content" in result.clean_text


# ---------------------------------------------------------------------------
# PRIV-02: Tracking pixels removed
# ---------------------------------------------------------------------------

def test_tracking_pixels_removed(config):
    """PRIV-02: All img tags (including tracking pixels) are removed."""
    raw = RawMessage(
        subject="Test",
        sender="a@newsletter.com",
        date="2026-03-11",
        body_html=(
            "<p>Content here.</p>"
            '<img src="https://open.tracker.com/pixel.gif" width="1" height="1"/>'
        ),
        body_text=None,
    )
    result = sanitize(raw, config)

    # Tracking domain must not appear in output
    assert "tracker.com" not in result.clean_text

    # No img tags should be in plain text output
    assert "<img" not in result.clean_text


# ---------------------------------------------------------------------------
# PRIV-03: UTM and tracking URL parameters stripped
# ---------------------------------------------------------------------------

def test_utm_params_stripped(config):
    """PRIV-03: UTM tracking parameters are removed; non-tracking params preserved."""
    raw = RawMessage(
        subject="Test",
        sender="a@newsletter.com",
        date="2026-03-11",
        body_html=(
            '<p>Read <a href="https://example.com/article'
            "?utm_source=newsletter&utm_medium=email&keep=this"
            '">article</a></p>'
        ),
        body_text=None,
    )
    result = sanitize(raw, config)

    # UTM tracking parameters must be stripped
    assert "utm_source" not in result.clean_text
    assert "utm_medium" not in result.clean_text

    # Non-tracking parameter must be preserved
    assert "keep=this" in result.clean_text


# ---------------------------------------------------------------------------
# PRIV-04: User email address redacted
# ---------------------------------------------------------------------------

def test_no_user_email_in_output(config):
    """PRIV-04: User's email address is redacted from body text and sender field."""
    raw = RawMessage(
        subject="Weekly Newsletter",
        sender="digest@morningbrew.com",
        date="2026-03-11",
        body_html=(
            f"<p>Unsubscribe: {config.user_email}. "
            f"Email preferences for {config.user_email}.</p>"
        ),
        body_text=None,
    )
    result = sanitize(raw, config)

    # User email must not appear anywhere in output
    assert config.user_email not in result.clean_text
    assert config.user_email not in result.sender_domain


def test_no_user_name_in_output(config):
    """PRIV-04 (extra): User's display name is redacted from body text."""
    raw = RawMessage(
        subject="Weekly Newsletter",
        sender="digest@example.com",
        date="2026-03-11",
        body_html=f"<p>Hi {config.user_name}, here's your digest!</p>",
        body_text=None,
    )
    result = sanitize(raw, config)

    # User name must not appear in output
    assert config.user_name not in result.clean_text


# ---------------------------------------------------------------------------
# PRIV-05: Configurable extra PII redaction patterns
# ---------------------------------------------------------------------------

def test_extra_patterns(config):
    """PRIV-05: Extra configurable regex patterns are applied to redact PII."""
    # Override config to add an extra pattern
    custom_config = SanitizerConfig(
        user_email=config.user_email,
        user_name=config.user_name,
        extra_patterns=[r"ACME-\d+"],
        max_body_chars=config.max_body_chars,
    )
    raw = RawMessage(
        subject="Order Confirmation",
        sender="orders@acme.com",
        date="2026-03-11",
        body_html="<p>Your order code: ACME-12345. Thank you!</p>",
        body_text=None,
    )
    result = sanitize(raw, custom_config)

    # The pattern match should be redacted
    assert "ACME-12345" not in result.clean_text

    # Redaction marker should be present
    assert "[REDACTED]" in result.clean_text


# ---------------------------------------------------------------------------
# PRIV-06: Sender reduced to domain-only
# ---------------------------------------------------------------------------

def test_sender_domain_only(config):
    """PRIV-06: Sender identity is reduced to domain only (no full email address)."""
    raw = RawMessage(
        subject="Morning Digest",
        sender='"Morning Brew" <digest@morningbrew.com>',
        date="2026-03-11",
        body_html="<p>Your daily digest.</p>",
        body_text=None,
    )
    result = sanitize(raw, config)

    # Sender domain must be exact domain only
    assert result.sender_domain == "morningbrew.com"

    # No full email address format in sender_domain
    assert "@" not in result.sender_domain


# ---------------------------------------------------------------------------
# PRIV-07: Body truncation
# ---------------------------------------------------------------------------

def test_truncation(config):
    """PRIV-07: Body is truncated to configured max_body_chars limit."""
    short_config = SanitizerConfig(
        user_email=config.user_email,
        user_name=config.user_name,
        extra_patterns=[],
        max_body_chars=100,
    )
    long_body = "x" * 500
    raw = RawMessage(
        subject="Long Newsletter",
        sender="a@b.com",
        date="2026-03-11",
        body_html=f"<p>{long_body}</p>",
        body_text=None,
    )
    result = sanitize(raw, short_config)

    # Output must not exceed the configured limit
    assert len(result.clean_text) <= 100


# ---------------------------------------------------------------------------
# PRIV-08: CleanMessage has no email header fields (structural/static test)
# ---------------------------------------------------------------------------

def test_clean_message_has_no_headers():
    """PRIV-08: CleanMessage type has no email header fields — enforced by design."""
    # Common email header fields that must NOT exist on CleanMessage
    forbidden_fields = ["to", "cc", "bcc", "message_id", "reply_to", "from_", "received"]
    for field_name in forbidden_fields:
        assert not hasattr(CleanMessage, field_name), (
            f"CleanMessage must not have field '{field_name}' — "
            f"headers must never reach Claude (PRIV-08)"
        )

    # CleanMessage must have exactly these four fields
    field_names = {f.name for f in dataclasses.fields(CleanMessage)}
    expected_fields = {"subject", "sender_domain", "date", "clean_text"}
    assert field_names == expected_fields, (
        f"CleanMessage fields must be exactly {expected_fields}, got {field_names}"
    )


# ---------------------------------------------------------------------------
# DOCS-02: .env.example file exists with all required keys
# ---------------------------------------------------------------------------

def test_env_example_exists():
    """DOCS-02: .env.example file exists and contains all required config keys."""
    env_example = Path(".env.example")
    assert env_example.exists(), ".env.example file must exist (DOCS-02)"

    content = env_example.read_text()

    # All required config keys must be documented
    required_keys = [
        "IMAP_HOST",
        "IMAP_PORT",
        "IMAP_USERNAME",
        "IMAP_PASSWORD",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_SECURITY",
        "NEWSLETTER_FOLDER",
        "NEWSLETTER_SENDERS",
        "FETCH_SINCE_HOURS",
        "CLAUDE_CMD",
        "CLAUDE_MODEL",
        "OUTPUT_FORMAT",
        "OUTPUT_DIR",
        "DIGEST_RECIPIENT",
        "USER_DISPLAY_NAME",
        "REDACT_PATTERNS",
        "MAX_BODY_CHARS",
    ]
    for key in required_keys:
        assert key in content, (
            f"Required key '{key}' missing from .env.example (DOCS-02)"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_html_fallback_to_body_text(config):
    """Edge case: When body_html is None, body_text is used as fallback."""
    raw = RawMessage(
        subject="Plain Text Newsletter",
        sender="a@b.com",
        date="2026-03-11",
        body_html=None,
        body_text="plain content here",
    )
    result = sanitize(raw, config)

    assert "plain content" in result.clean_text


def test_empty_body(config):
    """Edge case: Both body_html and body_text are None — no crash, empty output."""
    raw = RawMessage(
        subject="Empty Newsletter",
        sender="a@b.com",
        date="2026-03-11",
        body_html=None,
        body_text=None,
    )
    result = sanitize(raw, config)

    # Must not crash; clean_text should be empty string
    assert result.clean_text == ""


def test_subject_pii_redacted(config):
    """Edge case: Subject containing user name should have PII redacted."""
    raw = RawMessage(
        subject=f"Hi {config.user_name}, your weekly digest is ready",
        sender="a@b.com",
        date="2026-03-11",
        body_html="<p>Your weekly summary.</p>",
        body_text=None,
    )
    result = sanitize(raw, config)

    # User name must not appear in the subject field of CleanMessage
    assert config.user_name not in result.subject
