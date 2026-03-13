"""
Tests for src/deliver.py — SMTP email delivery and markdown archive.

Covers:
  DLVR-01: send_digest_email() via Bridge SMTP with STARTTLS
  DLVR-02: save_archive() saves digest-YYYY-MM-DD.md to output dir
  Markdown-to-HTML converter: markdown_to_html()
"""

import re
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def smtp_config():
    return {
        "smtp_host": "127.0.0.1",
        "smtp_port": 1025,
        "imap_username": "user@proton.me",
        "imap_password": "bridge-password-16",
        "digest_recipient": "user@proton.me",
        "output_dir": "./output",
    }


# ---------------------------------------------------------------------------
# DLVR-01 — SMTP email delivery
# ---------------------------------------------------------------------------

def test_send_email_calls_starttls(smtp_config):
    """STARTTLS must be called when sending the email."""
    mock_smtp = MagicMock()

    with patch("smtplib.SMTP") as MockSMTP:
        MockSMTP.return_value.__enter__.return_value = mock_smtp
        from src.deliver import send_digest_email
        send_digest_email("# digest", "<h1>digest</h1>", smtp_config)

    mock_smtp.starttls.assert_called_once()


def test_send_email_login_after_starttls(smtp_config):
    """login() must be called AFTER starttls() — credentials must not go in cleartext."""
    mock_smtp = MagicMock()

    with patch("smtplib.SMTP") as MockSMTP:
        MockSMTP.return_value.__enter__.return_value = mock_smtp
        from src.deliver import send_digest_email
        send_digest_email("# digest", "<h1>digest</h1>", smtp_config)

    # Verify call order: starttls before login
    calls = mock_smtp.method_calls
    method_names = [c[0] for c in calls]
    assert "starttls" in method_names
    assert "login" in method_names
    starttls_idx = method_names.index("starttls")
    login_idx = method_names.index("login")
    assert starttls_idx < login_idx, "starttls() must be called before login()"


def test_send_email_sends_message(smtp_config):
    """send_message() must be called with a MIMEMultipart object."""
    from email.mime.multipart import MIMEMultipart

    mock_smtp = MagicMock()

    with patch("smtplib.SMTP") as MockSMTP:
        MockSMTP.return_value.__enter__.return_value = mock_smtp
        from src.deliver import send_digest_email
        send_digest_email("# digest", "<h1>digest</h1>", smtp_config)

    mock_smtp.send_message.assert_called_once()
    sent_msg = mock_smtp.send_message.call_args[0][0]
    assert isinstance(sent_msg, MIMEMultipart)


def test_email_has_html_part(smtp_config):
    """The sent message must contain a text/html MIME part."""
    mock_smtp = MagicMock()

    with patch("smtplib.SMTP") as MockSMTP:
        MockSMTP.return_value.__enter__.return_value = mock_smtp
        from src.deliver import send_digest_email
        send_digest_email("plain text", "<p>html</p>", smtp_config)

    sent_msg = mock_smtp.send_message.call_args[0][0]
    content_types = [part.get_content_type() for part in sent_msg.walk()]
    assert "text/html" in content_types


def test_email_subject_contains_date(smtp_config):
    """Subject must match 'Daily Digest — YYYY-MM-DD' with today's date."""
    mock_smtp = MagicMock()
    today = date.today().isoformat()

    with patch("smtplib.SMTP") as MockSMTP:
        MockSMTP.return_value.__enter__.return_value = mock_smtp
        from src.deliver import send_digest_email
        send_digest_email("# digest", "<h1>digest</h1>", smtp_config)

    sent_msg = mock_smtp.send_message.call_args[0][0]
    subject = sent_msg["Subject"]
    assert today in subject, f"Expected today's date {today!r} in subject {subject!r}"
    assert "Daily Digest" in subject


# ---------------------------------------------------------------------------
# DLVR-02 — Markdown archive
# ---------------------------------------------------------------------------

def test_save_archive_creates_file(tmp_path, smtp_config):
    """save_archive() must create a file with the digest content."""
    config = dict(smtp_config, output_dir=str(tmp_path / "output"))
    from src.deliver import save_archive
    save_archive("## Key Trends\n\n- AI is here", config)

    today = date.today().strftime("%Y-%m-%d")
    expected = tmp_path / "output" / f"digest-{today}.md"
    assert expected.exists()
    assert "Key Trends" in expected.read_text(encoding="utf-8")


def test_save_archive_filename_format(tmp_path, smtp_config):
    """Archive filename must be digest-YYYY-MM-DD.md."""
    config = dict(smtp_config, output_dir=str(tmp_path / "output"))
    from src.deliver import save_archive
    saved = save_archive("content", config)

    today = date.today().strftime("%Y-%m-%d")
    assert saved.name == f"digest-{today}.md"


def test_save_archive_creates_directory(tmp_path, smtp_config):
    """save_archive() must create output_dir if it doesn't exist."""
    non_existent = tmp_path / "new_dir" / "sub_dir"
    config = dict(smtp_config, output_dir=str(non_existent))
    assert not non_existent.exists()

    from src.deliver import save_archive
    save_archive("content", config)

    assert non_existent.exists()


def test_save_archive_returns_path(tmp_path, smtp_config):
    """save_archive() must return a Path object pointing to the saved file."""
    config = dict(smtp_config, output_dir=str(tmp_path / "output"))
    from src.deliver import save_archive
    result = save_archive("content", config)

    assert isinstance(result, Path)
    assert result.exists()


# ---------------------------------------------------------------------------
# Markdown-to-HTML converter
# ---------------------------------------------------------------------------

def test_markdown_to_html_headers():
    """## Title should produce an <h2> element."""
    from src.deliver import markdown_to_html
    result = markdown_to_html("## Key Trends")
    assert "<h2>" in result
    assert "Key Trends" in result


def test_markdown_to_html_h3_headers():
    """### Sub-header should produce an <h3> element."""
    from src.deliver import markdown_to_html
    result = markdown_to_html("### Sub-header")
    assert "<h3>" in result
    assert "Sub-header" in result


def test_markdown_to_html_bullets():
    """- item should produce <ul><li> structure."""
    from src.deliver import markdown_to_html
    result = markdown_to_html("- bullet item")
    assert "<ul>" in result
    assert "<li>" in result
    assert "bullet item" in result


def test_markdown_to_html_bold():
    """**bold** should produce <strong>bold</strong>."""
    from src.deliver import markdown_to_html
    result = markdown_to_html("**bold text**")
    assert "<strong>bold text</strong>" in result


def test_markdown_to_html_wraps_in_html():
    """Output must start with an <html> tag (envelope)."""
    from src.deliver import markdown_to_html
    result = markdown_to_html("## Title")
    assert result.strip().startswith("<html>")


# ---------------------------------------------------------------------------
# URL rendering — markdown links and bare URLs in HTML email
# ---------------------------------------------------------------------------

def test_apply_inline_markdown_link():
    """[text](url) is converted to <a href="url">text</a>."""
    from src.deliver import _apply_inline
    result = _apply_inline("[OpenAI](https://openai.com)")
    assert result == '<a href="https://openai.com">OpenAI</a>'


def test_apply_inline_bare_url():
    """Bare https:// URL is wrapped in an <a> tag."""
    from src.deliver import _apply_inline
    result = _apply_inline("See https://example.com for details")
    assert '<a href="https://example.com">https://example.com</a>' in result


def test_apply_inline_no_double_wrap():
    """A URL inside a markdown link is not double-wrapped."""
    from src.deliver import _apply_inline
    result = _apply_inline("[link](https://x.com)")
    assert result.count("<a") == 1, f"Expected exactly one <a tag, got: {result!r}"


def test_apply_inline_bold_and_link():
    """Both **bold** and [link](url) are handled in the same string."""
    from src.deliver import _apply_inline
    result = _apply_inline("**Bold** and [link](https://x.com)")
    assert "<strong>" in result
    assert '<a href="https://x.com">' in result


def test_markdown_to_html_with_link():
    """A bullet with a markdown link produces a clickable <a> tag."""
    from src.deliver import markdown_to_html
    result = markdown_to_html("- Check [article](https://example.com/post)")
    assert '<a href="https://example.com/post">article</a>' in result
