"""
Configuration loader for the Signals newsletter digest pipeline.

IMPORTANT: load_dotenv() is NOT called at module import time.
It is only called inside functions to avoid test import failures
when no .env file is present. Tests inject SanitizerConfig directly.

See: 01-RESEARCH.md Pitfall 5 — "Config Loaded at Import Time Breaks Tests"
"""

import os
from dotenv import load_dotenv

from src.models import SanitizerConfig


def load_config() -> dict:
    """Load and validate configuration from .env file.

    Calls load_dotenv() to read .env, validates required keys are present,
    and returns a dict with all config values.

    Raises:
        ValueError: If any required config keys are missing.
    """
    load_dotenv()

    required = ["IMAP_HOST", "IMAP_PORT", "IMAP_USERNAME", "IMAP_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")

    return {
        "imap_host": os.environ["IMAP_HOST"],
        "imap_port": int(os.environ["IMAP_PORT"]),
        "imap_username": os.environ["IMAP_USERNAME"],
        "imap_password": os.environ["IMAP_PASSWORD"],
        "smtp_host": os.environ.get("SMTP_HOST", "127.0.0.1"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "1025")),
        "smtp_security": os.environ.get("SMTP_SECURITY", "STARTTLS"),
        "newsletter_folder": os.environ.get("NEWSLETTER_FOLDER", "Newsletters"),
        "newsletter_senders": [
            s.strip()
            for s in os.environ.get("NEWSLETTER_SENDERS", "").split(",")
            if s.strip()
        ],
        "fetch_since_hours": int(os.environ.get("FETCH_SINCE_HOURS", "24")),
        "claude_cmd": os.environ.get("CLAUDE_CMD", "claude"),
        "claude_model": os.environ.get("CLAUDE_MODEL", ""),
        "output_format": os.environ.get("OUTPUT_FORMAT", "markdown"),
        "output_dir": os.environ.get("OUTPUT_DIR", "./output"),
        "digest_recipient": os.environ.get("DIGEST_RECIPIENT", ""),
        "user_display_name": os.environ.get("USER_DISPLAY_NAME", ""),
        "user_email": os.environ.get("IMAP_USERNAME", ""),
        "redact_patterns": [
            p.strip()
            for p in os.environ.get("REDACT_PATTERNS", "").split(",")
            if p.strip()
        ],
        "max_body_chars": int(os.environ.get("MAX_BODY_CHARS", "15000")),
    }


def load_sanitizer_config() -> SanitizerConfig:
    """Convenience function: return a SanitizerConfig populated from environment variables.

    Calls load_dotenv() internally. Optional keys default gracefully.
    Does not require IMAP credentials to be present.
    """
    load_dotenv()

    return SanitizerConfig(
        user_email=os.environ.get("IMAP_USERNAME", ""),
        user_name=os.environ.get("USER_DISPLAY_NAME", ""),
        extra_patterns=[
            p.strip()
            for p in os.environ.get("REDACT_PATTERNS", "").split(",")
            if p.strip()
        ],
        max_body_chars=int(os.environ.get("MAX_BODY_CHARS", "15000")),
    )
