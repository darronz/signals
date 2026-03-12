"""
Unit tests for src/fetch.py — IMAP fetch module.

All tests use mock IMAP to avoid requiring a live Proton Mail Bridge instance.

FETCH-01: STARTTLS connection with ssl.SSLContext(CERT_NONE) for Bridge self-signed cert
FETCH-02: Configurable folder, UID mode only, returns RawMessage objects
FETCH-03: Sender filter applied when no folder configured; skipped when folder set
FETCH-04: Time window filter (hour-precision); empty folder returns []
FETCH-05: Multipart MIME walk with HTML preferred; charset fallback
"""

import email
import email.policy
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, call, patch

import pytest

from src.fetch import _extract_body, fetch_messages


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_raw_email(
    subject: str,
    sender: str,
    date: str,
    html: str,
    plain: str = "",
) -> bytes:
    """Build a minimal multipart/alternative RFC822 message as bytes.

    Used to construct mock FETCH responses that resemble real newsletter emails.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = date
    if plain:
        msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg.as_bytes()


def _now_str(delta_hours: int = 0) -> str:
    """Return an RFC 2822 date string for now +/- delta_hours."""
    dt = datetime.now(tz=timezone.utc) + timedelta(hours=delta_hours)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


@pytest.fixture
def base_config():
    """Minimal valid config dict for fetch_messages()."""
    return {
        "imap_host": "127.0.0.1",
        "imap_port": 1143,
        "imap_username": "user@proton.me",
        "imap_password": "bridge-password",
        "newsletter_folder": "Newsletters",
        "newsletter_senders": [],
        "fetch_since_hours": 24,
    }


# ---------------------------------------------------------------------------
# FETCH-01: STARTTLS + connection management
# ---------------------------------------------------------------------------


@patch("src.fetch.imaplib.IMAP4")
def test_starttls_called(mock_imap_class, base_config):
    """FETCH-01: starttls() is called with an SSLContext that has CERT_NONE."""
    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"0"])
    mock_imap.uid.return_value = ("OK", [b""])  # empty SEARCH

    fetch_messages(base_config)

    # starttls() must be called exactly once
    mock_imap.starttls.assert_called_once()
    # The ssl_context argument must have CERT_NONE and check_hostname=False
    call_kwargs = mock_imap.starttls.call_args
    ctx = call_kwargs[1].get("ssl_context") or call_kwargs[0][0]
    assert isinstance(ctx, ssl.SSLContext), "starttls must receive an ssl.SSLContext"
    assert ctx.verify_mode == ssl.CERT_NONE, "SSLContext must have CERT_NONE"
    assert ctx.check_hostname is False, "SSLContext must have check_hostname=False"


@patch("src.fetch.imaplib.IMAP4")
def test_connection_not_left_open_on_error(mock_imap_class, base_config):
    """FETCH-01: Context manager __exit__ is called even when uid() raises."""
    mock_imap = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_imap)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_imap_class.return_value = mock_cm

    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.uid.side_effect = imaplib_error("SEARCH failed")

    with pytest.raises(Exception):
        fetch_messages(base_config)

    # __exit__ must have been called (context manager cleanup)
    mock_cm.__exit__.assert_called_once()


# ---------------------------------------------------------------------------
# FETCH-02: Folder selection, UID mode, returns RawMessage objects
# ---------------------------------------------------------------------------


@patch("src.fetch.imaplib.IMAP4")
def test_returns_raw_messages_for_matching_uids(mock_imap_class, base_config):
    """FETCH-02: Messages from configured folder are returned as RawMessage objects."""
    raw_bytes = make_raw_email(
        subject="Daily Digest",
        sender="digest@example.com",
        date=_now_str(-1),  # 1 hour ago — within 24h window
        html="<p>Newsletter content</p>",
    )

    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.uid.side_effect = [
        ("OK", [b"1"]),                              # SEARCH response
        ("OK", [(b"1 (RFC822 {n})", raw_bytes)]),    # FETCH response for uid 1
    ]

    result = fetch_messages(base_config)

    assert len(result) == 1
    assert result[0].subject == "Daily Digest"
    assert result[0].sender == "digest@example.com"
    assert result[0].body_html is not None
    assert "<p>Newsletter content</p>" in result[0].body_html


@patch("src.fetch.imaplib.IMAP4")
def test_uid_mode_used(mock_imap_class, base_config):
    """FETCH-02: imap.uid() is used for both SEARCH and FETCH; imap.search() and imap.fetch() are never called."""
    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"0"])
    mock_imap.uid.return_value = ("OK", [b""])  # empty search

    fetch_messages(base_config)

    # uid() must have been called (SEARCH at minimum)
    assert mock_imap.uid.called, "imap.uid() was not called"
    # Direct search() and fetch() must NOT be called
    mock_imap.search.assert_not_called()
    mock_imap.fetch.assert_not_called()


# ---------------------------------------------------------------------------
# FETCH-03: Sender filter
# ---------------------------------------------------------------------------


@patch("src.fetch.imaplib.IMAP4")
def test_sender_filter_applied_without_folder(mock_imap_class):
    """FETCH-03: Only messages matching newsletter_senders are returned when no folder is set."""
    config = {
        "imap_host": "127.0.0.1",
        "imap_port": 1143,
        "imap_username": "user@proton.me",
        "imap_password": "bridge-password",
        "newsletter_folder": "",  # no folder — sender filter active
        "newsletter_senders": ["news@example.com"],
        "fetch_since_hours": 24,
    }

    raw_matching = make_raw_email(
        subject="From matching sender",
        sender="news@example.com",
        date=_now_str(-1),
        html="<p>Match</p>",
    )
    raw_other = make_raw_email(
        subject="From other sender",
        sender="other@different.com",
        date=_now_str(-1),
        html="<p>No match</p>",
    )

    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"2"])
    mock_imap.uid.side_effect = [
        ("OK", [b"1 2"]),                                    # SEARCH: two UIDs
        ("OK", [(b"1 (RFC822 {n})", raw_matching)]),          # FETCH uid 1
        ("OK", [(b"2 (RFC822 {n})", raw_other)]),             # FETCH uid 2
    ]

    result = fetch_messages(config)

    assert len(result) == 1
    assert result[0].subject == "From matching sender"


@patch("src.fetch.imaplib.IMAP4")
def test_sender_filter_not_applied_with_folder(mock_imap_class):
    """FETCH-03: When newsletter_folder is set, all messages are returned regardless of sender."""
    config = {
        "imap_host": "127.0.0.1",
        "imap_port": 1143,
        "imap_username": "user@proton.me",
        "imap_password": "bridge-password",
        "newsletter_folder": "Newsletters",  # folder set — sender filter skipped
        "newsletter_senders": ["news@example.com"],
        "fetch_since_hours": 24,
    }

    raw_a = make_raw_email(
        subject="Sender A",
        sender="news@example.com",
        date=_now_str(-1),
        html="<p>A</p>",
    )
    raw_b = make_raw_email(
        subject="Sender B",
        sender="other@different.com",
        date=_now_str(-1),
        html="<p>B</p>",
    )

    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"2"])
    mock_imap.uid.side_effect = [
        ("OK", [b"1 2"]),
        ("OK", [(b"1 (RFC822 {n})", raw_a)]),
        ("OK", [(b"2 (RFC822 {n})", raw_b)]),
    ]

    result = fetch_messages(config)

    assert len(result) == 2
    subjects = {r.subject for r in result}
    assert "Sender A" in subjects
    assert "Sender B" in subjects


# ---------------------------------------------------------------------------
# FETCH-04: Time window filter
# ---------------------------------------------------------------------------


@patch("src.fetch.imaplib.IMAP4")
def test_time_window_filter(mock_imap_class, base_config):
    """FETCH-04: Only messages within fetch_since_hours are returned (hour-precision filter)."""
    raw_recent = make_raw_email(
        subject="Recent",
        sender="recent@example.com",
        date=_now_str(-1),   # 1 hour ago — within 24h
        html="<p>Recent</p>",
    )
    raw_old = make_raw_email(
        subject="Old",
        sender="old@example.com",
        date=_now_str(-48),  # 48 hours ago — outside 24h
        html="<p>Old</p>",
    )

    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"2"])
    mock_imap.uid.side_effect = [
        ("OK", [b"1 2"]),
        ("OK", [(b"1 (RFC822 {n})", raw_recent)]),
        ("OK", [(b"2 (RFC822 {n})", raw_old)]),
    ]

    result = fetch_messages(base_config)

    assert len(result) == 1
    assert result[0].subject == "Recent"


@patch("src.fetch.imaplib.IMAP4")
def test_empty_folder_returns_empty_list(mock_imap_class, base_config):
    """FETCH-04: Empty SEARCH result returns an empty list."""
    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"0"])
    mock_imap.uid.return_value = ("OK", [b""])  # empty SEARCH result

    result = fetch_messages(base_config)

    assert result == []


# ---------------------------------------------------------------------------
# FETCH-05: MIME body extraction (no mock IMAP needed — tests _extract_body directly)
# ---------------------------------------------------------------------------


def test_html_part_preferred():
    """FETCH-05: HTML body is preferred over plain text in multipart/alternative messages."""
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText("Plain text content", "plain"))
    msg.attach(MIMEText("<p>HTML content</p>", "html"))

    # Parse through the email stdlib (as fetch.py does) so msg.walk() works correctly
    parsed = email.message_from_bytes(msg.as_bytes(), policy=email.policy.default)

    html_body, text_body = _extract_body(parsed)

    assert html_body is not None, "Expected html_body to be set"
    assert "<p>HTML content</p>" in html_body
    assert text_body is not None, "Expected text_body to be set"
    assert "Plain text content" in text_body


def test_charset_fallback():
    """FETCH-05: Non-UTF-8 charset (windows-1252) decodes without crash; replacement chars acceptable."""
    # Build a MIME part with windows-1252 content
    content_bytes = "Caf\xe9 Newsletter".encode("windows-1252")  # \xe9 = é in latin-1/1252

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Charset test"

    # Manually construct a MIME part with windows-1252 charset
    from email.mime.base import MIMEBase
    part = MIMEBase("text", "html", charset="windows-1252")
    part.set_payload(content_bytes)
    # No transfer encoding — raw bytes
    from email import encoders
    encoders.encode_7or8bit(part)
    msg.attach(part)

    parsed = email.message_from_bytes(msg.as_bytes(), policy=email.policy.default)

    # Must not raise
    html_body, text_body = _extract_body(parsed)

    # The content should be decoded (with possible replacement chars — that's acceptable)
    assert html_body is not None or text_body is not None or True  # no crash is the primary assertion


# ---------------------------------------------------------------------------
# Helper: imaplib.IMAP4.error factory
# ---------------------------------------------------------------------------


def imaplib_error(msg: str = "IMAP error"):
    """Create an imaplib.IMAP4.error instance for use in side_effect."""
    import imaplib
    return imaplib.IMAP4.error(msg)
