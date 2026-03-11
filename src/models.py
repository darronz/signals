"""
Data contracts for the Signals newsletter digest pipeline.

The privacy boundary is enforced by type design:
- RawMessage: input to sanitizer, contains full email data (never leaves sanitizer)
- CleanMessage: output of sanitizer, safe to pass to Claude (no header fields, no PII)
- SanitizerConfig: configuration for the sanitizer

PRIV-08: CleanMessage has no header fields (To, CC, BCC, Message-ID, X-headers).
         The type physically cannot carry headers — absence is enforced by design.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawMessage:
    """Input to the sanitizer. Contains raw email data. Never leaves the sanitizer module."""
    subject: str
    sender: str          # full email address, e.g. "Morning Brew" <digest@morningbrew.com>
    date: str
    body_html: Optional[str]
    body_text: Optional[str]
    # NOTE: No To, CC, BCC, Message-ID, X-headers — caller must not pass them.
    # Phase 2 (IMAP fetch) is responsible for extracting only these five fields.


@dataclass
class CleanMessage:
    """Output of the sanitizer. Safe to pass to Claude. No header fields, no PII.

    Exactly four fields — enforced by design (PRIV-08):
      subject: str         — newsletter subject (PII-redacted)
      sender_domain: str   — domain only, e.g. morningbrew.com (no full address)
      date: str            — date string from message
      clean_text: str      — plain text body (no HTML, no PII, no tracking)
    """
    subject: str
    sender_domain: str   # domain-only, e.g. morningbrew.com
    date: str
    clean_text: str      # plain text, no HTML, no PII, no tracking artifacts


@dataclass
class SanitizerConfig:
    """Configuration for the privacy sanitizer."""
    user_email: str
    user_name: str
    extra_patterns: list = field(default_factory=list)  # from REDACT_PATTERNS config
    max_body_chars: int = 15_000                         # from MAX_BODY_CHARS config
