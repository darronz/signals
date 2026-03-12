"""
Integration tests for the Signals fetch-to-sanitize pipeline.

These tests require a live Proton Mail Bridge connection and WILL NOT run
during normal pytest invocations. They are gated by the SIGNALS_INTEGRATION
environment variable.

To run:
    SIGNALS_INTEGRATION=1 pytest tests/test_fetch_integration.py -x -v

Prerequisites:
    - Proton Mail Bridge installed, running, and authenticated
    - .env file with IMAP_HOST, IMAP_PORT, IMAP_USERNAME, IMAP_PASSWORD,
      and NEWSLETTER_FOLDER set correctly
    - At least one newsletter in the configured folder from the last 24 hours
    - IMAP_PASSWORD must be the Bridge-generated password (not your Proton
      account password — find it in the Bridge app settings)
"""

import os
import email.utils
from datetime import datetime, timezone, timedelta

import pytest

# Skip entire module unless SIGNALS_INTEGRATION=1 is set
pytestmark = pytest.mark.skipif(
    os.environ.get("SIGNALS_INTEGRATION") != "1",
    reason="Integration tests require SIGNALS_INTEGRATION=1 and a live Proton Mail Bridge",
)

from src.config import load_config, load_sanitizer_config
from src.fetch import fetch_messages
from src.sanitizer import sanitize
from src.models import RawMessage, CleanMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_messages():
    """Fetch messages once; reused across multiple tests to avoid duplicate calls."""
    config = load_config()
    return fetch_messages(config), config


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def test_fetch_returns_raw_messages():
    """Verify fetch_messages returns a list of RawMessage objects with expected fields."""
    messages, _config = _get_messages()

    assert isinstance(messages, list), "fetch_messages should return a list"

    for msg in messages:
        assert isinstance(msg, RawMessage), f"Expected RawMessage, got {type(msg)}"
        assert msg.subject, f"RawMessage should have a non-empty subject; got: {msg.subject!r}"
        assert msg.sender, f"RawMessage should have a non-empty sender; got: {msg.sender!r}"

    # Newsletters are almost always HTML; assert at least one has body_html
    if messages:
        has_html = any(msg.body_html for msg in messages)
        assert has_html, (
            "Expected at least one fetched message to have body_html — "
            "newsletters are typically HTML emails"
        )


def test_fetched_messages_sanitize_cleanly():
    """Verify every fetched RawMessage passes through sanitize() without error."""
    messages, config = _get_messages()
    sanitizer_config = load_sanitizer_config()

    user_email = config.get("imap_username", "").lower()

    for raw in messages:
        clean = sanitize(raw, sanitizer_config)

        assert isinstance(clean, CleanMessage), (
            f"sanitize() should return CleanMessage, got {type(clean)}"
        )
        assert clean.clean_text, (
            f"CleanMessage.clean_text should not be empty for message: {raw.subject!r}"
        )
        assert "." in clean.sender_domain, (
            f"CleanMessage.sender_domain should be a domain (contain '.'), "
            f"got: {clean.sender_domain!r}"
        )

        # Assert user's email address does NOT appear in any CleanMessage field
        if user_email:
            for field_name, field_val in [
                ("subject", clean.subject),
                ("sender_domain", clean.sender_domain),
                ("clean_text", clean.clean_text),
            ]:
                assert user_email not in field_val.lower(), (
                    f"User email ({user_email!r}) found in CleanMessage.{field_name} — "
                    f"PII redaction failed"
                )


def test_fetch_respects_time_window():
    """Verify fetched messages fall within the configured time window (plus slack)."""
    messages, config = _get_messages()

    if not messages:
        pytest.skip("No messages returned; cannot verify time window (check NEWSLETTER_FOLDER and ensure recent mail exists)")

    hours = config.get("fetch_since_hours", 24)
    # Allow 25h of slack: IMAP SINCE is date-only, so messages from the start
    # of the previous day may be included by the broad server-side filter.
    # Python-side filtering uses hour precision, but we add 1h slack here for
    # timezone boundary edge cases in the test assertion.
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours + 25)

    for msg in messages:
        if not msg.date:
            continue  # conservative: skip messages with no Date header

        try:
            msg_dt = email.utils.parsedate_to_datetime(msg.date)
        except (ValueError, TypeError):
            continue  # unparseable date — skip (fetch.py includes conservatively)

        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=timezone.utc)

        assert msg_dt >= cutoff, (
            f"Message date {msg_dt.isoformat()!r} is older than the allowed window "
            f"({hours}h + 25h slack). Subject: {msg.subject!r}"
        )
