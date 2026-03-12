"""
Unit tests for scripts/daily.py CLI entry point.

Tests cover:
- Exit codes 0/1/2/3 for all error conditions (OPS-03)
- --dry-run short-circuits before Claude and email
- CLI argument parsing: --since, --verbose, --prompt, --output
- Pipeline integration: save_archive always called, send_digest_email conditional

All external modules are mocked to isolate daily.py logic.
"""

import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers: fake CleanMessage and RawMessage stubs for mock return values
# ---------------------------------------------------------------------------

def _make_raw_msg(subject="Test Newsletter", sender="news@example.com", body="Hello body"):
    """Return a minimal RawMessage-like object."""
    msg = MagicMock()
    msg.subject = subject
    msg.sender = sender
    msg.body = body
    return msg


def _make_clean_msg(subject="Test Newsletter", sender_domain="example.com",
                    date="2026-03-12", clean_text="Clean body text"):
    """Return a minimal CleanMessage-like object."""
    msg = MagicMock()
    msg.subject = subject
    msg.sender_domain = sender_domain
    msg.date = date
    msg.clean_text = clean_text
    return msg


# ---------------------------------------------------------------------------
# Base mock config used across all tests
# ---------------------------------------------------------------------------

BASE_CONFIG = {
    "imap_host": "127.0.0.1",
    "imap_port": 1143,
    "imap_username": "test@proton.me",
    "imap_password": "testpass",
    "smtp_host": "127.0.0.1",
    "smtp_port": 1025,
    "smtp_security": "STARTTLS",
    "newsletter_folder": "Newsletters",
    "newsletter_senders": [],
    "fetch_since_hours": 24,
    "claude_cmd": "claude",
    "claude_model": "",
    "output_format": "markdown",
    "output_dir": "./output",
    "digest_recipient": "",
    "user_display_name": "",
    "user_email": "test@proton.me",
    "redact_patterns": [],
    "max_body_chars": 15000,
    "digest_word_target": 500,
}


# ---------------------------------------------------------------------------
# Utility: import and call main() with given argv, expecting SystemExit
# ---------------------------------------------------------------------------

def _run_main(argv, mock_config=None, mock_fetch_return=None,
              mock_sanitize_return=None, mock_claude_return="Digest text",
              mock_archive_return=None, fetch_side_effect=None,
              config_side_effect=None, claude_side_effect=None):
    """
    Import scripts.daily and call main() with patched argv and all dependencies.

    Returns (exit_code, mock_call_claude, mock_save_archive, mock_send_email, mock_print).
    """
    if mock_config is None:
        mock_config = BASE_CONFIG.copy()
    if mock_fetch_return is None:
        mock_fetch_return = [_make_raw_msg()]
    if mock_sanitize_return is None:
        mock_sanitize_return = _make_clean_msg()
    if mock_archive_return is None:
        mock_archive_return = MagicMock()
        mock_archive_return.__str__ = lambda self: "./output/digest-2026-03-12.md"

    patches = {
        "src.config.load_config": MagicMock(
            side_effect=config_side_effect,
            return_value=None if config_side_effect else mock_config,
        ),
        "src.config.load_sanitizer_config": MagicMock(return_value=MagicMock()),
        "src.fetch.fetch_messages": MagicMock(
            side_effect=fetch_side_effect,
            return_value=None if fetch_side_effect else mock_fetch_return,
        ),
        "src.sanitizer.sanitize": MagicMock(return_value=mock_sanitize_return),
        "src.summarize.call_claude": MagicMock(
            side_effect=claude_side_effect,
            return_value=None if claude_side_effect else mock_claude_return,
        ),
        "src.summarize.format_newsletter_input": MagicMock(return_value="Formatted newsletters"),
        "src.deliver.save_archive": MagicMock(return_value=mock_archive_return),
        "src.deliver.send_digest_email": MagicMock(return_value=None),
        "src.deliver.markdown_to_html": MagicMock(return_value="<html>Digest</html>"),
    }

    with patch("sys.argv", ["daily.py"] + argv):
        with patch.multiple("scripts.daily", **{
            k.split(".")[-1]: v for k, v in patches.items()
        }):
            # Re-import to pick up mocked dependencies
            import scripts.daily as daily_module
            # Patch directly on the module to intercept calls
            with patch.object(daily_module, "load_config",
                               patches["src.config.load_config"]), \
                 patch.object(daily_module, "load_sanitizer_config",
                               patches["src.config.load_sanitizer_config"]), \
                 patch.object(daily_module, "fetch_messages",
                               patches["src.fetch.fetch_messages"]), \
                 patch.object(daily_module, "sanitize",
                               patches["src.sanitizer.sanitize"]), \
                 patch.object(daily_module, "call_claude",
                               patches["src.summarize.call_claude"]), \
                 patch.object(daily_module, "format_newsletter_input",
                               patches["src.summarize.format_newsletter_input"]), \
                 patch.object(daily_module, "save_archive",
                               patches["src.deliver.save_archive"]), \
                 patch.object(daily_module, "send_digest_email",
                               patches["src.deliver.send_digest_email"]), \
                 patch.object(daily_module, "markdown_to_html",
                               patches["src.deliver.markdown_to_html"]):
                try:
                    daily_module.main()
                    exit_code = 0
                except SystemExit as exc:
                    exit_code = exc.code

    return (
        exit_code,
        patches["src.summarize.call_claude"],
        patches["src.deliver.save_archive"],
        patches["src.deliver.send_digest_email"],
        patches["src.config.load_config"],
    )


# ---------------------------------------------------------------------------
# Import scripts.daily once at module level to ensure it can be imported
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_scripts_importable():
    """Ensure scripts/ package is importable. daily.py must exist."""
    import scripts.daily  # noqa: F401 — will fail if daily.py missing


# ---------------------------------------------------------------------------
# Tests: exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:
    """OPS-03: exit codes 0/1/2/3 mapped to all error conditions."""

    def test_exit_1_on_missing_config(self):
        """ValueError from load_config -> sys.exit(1)."""
        import scripts.daily as daily_module
        with patch.object(daily_module, "load_config",
                          side_effect=ValueError("Missing IMAP keys")), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch("sys.argv", ["daily.py"]):
            with pytest.raises(SystemExit) as exc_info:
                daily_module.main()
        assert exc_info.value.code == 1

    def test_exit_1_on_imap_error(self):
        """ConnectionRefusedError from fetch_messages -> sys.exit(1)."""
        import scripts.daily as daily_module
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          side_effect=ConnectionRefusedError("Bridge not running")), \
             patch("sys.argv", ["daily.py"]):
            with pytest.raises(SystemExit) as exc_info:
                daily_module.main()
        assert exc_info.value.code == 1

    def test_exit_2_no_newsletters(self):
        """fetch_messages returns empty list -> sys.exit(2)."""
        import scripts.daily as daily_module
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages", return_value=[]), \
             patch("sys.argv", ["daily.py"]):
            with pytest.raises(SystemExit) as exc_info:
                daily_module.main()
        assert exc_info.value.code == 2

    def test_exit_3_claude_error(self):
        """RuntimeError from call_claude -> sys.exit(3)."""
        import scripts.daily as daily_module
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize",
                          return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Newsletters text"), \
             patch.object(daily_module, "call_claude",
                          side_effect=RuntimeError("Claude CLI exited 1")), \
             patch("sys.argv", ["daily.py"]):
            with pytest.raises(SystemExit) as exc_info:
                daily_module.main()
        assert exc_info.value.code == 3

    def test_exit_3_claude_not_found(self):
        """FileNotFoundError from call_claude -> sys.exit(3)."""
        import scripts.daily as daily_module
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize",
                          return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Newsletters text"), \
             patch.object(daily_module, "call_claude",
                          side_effect=FileNotFoundError("claude not found")), \
             patch("sys.argv", ["daily.py"]):
            with pytest.raises(SystemExit) as exc_info:
                daily_module.main()
        assert exc_info.value.code == 3


# ---------------------------------------------------------------------------
# Tests: --dry-run flag
# ---------------------------------------------------------------------------

class TestDryRun:
    """OPS-01: --dry-run fetches and sanitizes without calling Claude or email."""

    def test_dry_run_no_claude_call(self, capsys):
        """--dry-run exits 0 and does NOT call Claude."""
        import scripts.daily as daily_module
        mock_call_claude = MagicMock()
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize",
                          return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Clean newsletter text"), \
             patch.object(daily_module, "call_claude", mock_call_claude), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", return_value=None), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                daily_module.main()
        assert exc_info.value.code == 0
        mock_call_claude.assert_not_called()

    def test_dry_run_prints_clean_text(self, capsys):
        """--dry-run prints formatted newsletter text to stdout."""
        import scripts.daily as daily_module
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize",
                          return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="DRY RUN OUTPUT TEXT"), \
             patch.object(daily_module, "call_claude", MagicMock()), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", return_value=None), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py", "--dry-run"]):
            with pytest.raises(SystemExit):
                daily_module.main()
        captured = capsys.readouterr()
        assert "DRY RUN OUTPUT TEXT" in captured.out

    def test_dry_run_no_send_email(self):
        """--dry-run does NOT call send_digest_email."""
        import scripts.daily as daily_module
        mock_send = MagicMock()
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize",
                          return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Clean text"), \
             patch.object(daily_module, "call_claude", MagicMock()), \
             patch.object(daily_module, "send_digest_email", mock_send), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py", "--dry-run"]):
            with pytest.raises(SystemExit):
                daily_module.main()
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: CLI argument flags
# ---------------------------------------------------------------------------

class TestCLIFlags:
    """OPS-02: --since, --verbose, --prompt, --output CLI arguments."""

    def test_since_flag_overrides_config(self):
        """--since 48 sets config['fetch_since_hours'] = 48."""
        import scripts.daily as daily_module
        captured_config = {}

        def _mock_fetch(config):
            captured_config.update(config)
            return [_make_raw_msg()]

        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages", side_effect=_mock_fetch), \
             patch.object(daily_module, "sanitize", return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Text"), \
             patch.object(daily_module, "call_claude", return_value="Digest"), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", return_value=None), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py", "--since", "48"]):
            try:
                daily_module.main()
            except SystemExit:
                pass
        assert captured_config.get("fetch_since_hours") == 48

    def test_verbose_sets_debug_level(self):
        """--verbose causes logging at DEBUG level."""
        import scripts.daily as daily_module
        import logging
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize", return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Text"), \
             patch.object(daily_module, "call_claude", return_value="Digest"), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", return_value=None), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py", "--verbose"]):
            try:
                daily_module.main()
            except SystemExit:
                pass
        # After --verbose run, root logger should have been set to DEBUG
        assert logging.getLogger().level == logging.DEBUG

    def test_prompt_flag_overrides_path(self):
        """--prompt /tmp/custom.txt passes that path to call_claude."""
        import scripts.daily as daily_module
        captured_prompt = {}

        def _mock_claude(prompt_file, text, config):
            captured_prompt["path"] = prompt_file
            return "Digest"

        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize", return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Text"), \
             patch.object(daily_module, "call_claude", side_effect=_mock_claude), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", return_value=None), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py", "--prompt", "/tmp/custom.txt"]):
            try:
                daily_module.main()
            except SystemExit:
                pass
        assert captured_prompt.get("path") == "/tmp/custom.txt"

    def test_output_flag_overrides_format(self):
        """--output email sets config['output_format'] = 'email'."""
        import scripts.daily as daily_module
        captured_config = {}

        def _mock_fetch(config):
            captured_config.update(config)
            return [_make_raw_msg()]

        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages", side_effect=_mock_fetch), \
             patch.object(daily_module, "sanitize", return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Text"), \
             patch.object(daily_module, "call_claude", return_value="Digest"), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", return_value=None), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py", "--output", "email"]):
            try:
                daily_module.main()
            except SystemExit:
                pass
        assert captured_config.get("output_format") == "email"


# ---------------------------------------------------------------------------
# Tests: successful pipeline behavior
# ---------------------------------------------------------------------------

class TestSuccessfulPipeline:
    """Tests for correct behavior on a happy-path run."""

    def test_success_saves_archive(self):
        """Successful run calls save_archive with the digest text."""
        import scripts.daily as daily_module
        mock_save = MagicMock(return_value=MagicMock())
        with patch.object(daily_module, "load_config", return_value=BASE_CONFIG.copy()), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize", return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Text"), \
             patch.object(daily_module, "call_claude",
                          return_value="THE DIGEST TEXT"), \
             patch.object(daily_module, "save_archive", mock_save), \
             patch.object(daily_module, "send_digest_email", return_value=None), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py"]):
            try:
                daily_module.main()
            except SystemExit:
                pass
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][0] == "THE DIGEST TEXT"  # first positional arg is digest text

    def test_success_sends_email_when_configured(self):
        """output_format=email calls send_digest_email."""
        import scripts.daily as daily_module
        config = BASE_CONFIG.copy()
        config["output_format"] = "email"
        mock_send = MagicMock(return_value=None)
        with patch.object(daily_module, "load_config", return_value=config), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize", return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Text"), \
             patch.object(daily_module, "call_claude",
                          return_value="Digest content"), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", mock_send), \
             patch.object(daily_module, "markdown_to_html",
                          return_value="<html>Digest</html>"), \
             patch("sys.argv", ["daily.py", "--output", "email"]):
            try:
                daily_module.main()
            except SystemExit:
                pass
        mock_send.assert_called_once()

    def test_success_no_email_for_markdown_format(self):
        """output_format=markdown does NOT call send_digest_email."""
        import scripts.daily as daily_module
        config = BASE_CONFIG.copy()
        config["output_format"] = "markdown"
        mock_send = MagicMock(return_value=None)
        with patch.object(daily_module, "load_config", return_value=config), \
             patch.object(daily_module, "load_sanitizer_config", return_value=MagicMock()), \
             patch.object(daily_module, "fetch_messages",
                          return_value=[_make_raw_msg()]), \
             patch.object(daily_module, "sanitize", return_value=_make_clean_msg()), \
             patch.object(daily_module, "format_newsletter_input",
                          return_value="Text"), \
             patch.object(daily_module, "call_claude",
                          return_value="Digest content"), \
             patch.object(daily_module, "save_archive", return_value=MagicMock()), \
             patch.object(daily_module, "send_digest_email", mock_send), \
             patch.object(daily_module, "markdown_to_html", return_value="<html/>"), \
             patch("sys.argv", ["daily.py"]):
            try:
                daily_module.main()
            except SystemExit:
                pass
        mock_send.assert_not_called()
