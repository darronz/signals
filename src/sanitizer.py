"""
Privacy sanitizer stub for the Signals newsletter digest pipeline.

This stub allows tests to import the module and fail at runtime (RED phase),
not at import time. The full implementation is provided in Plan 02.

Function signature is the privacy contract:
  sanitize(raw: RawMessage, config: SanitizerConfig) -> CleanMessage

The return type physically cannot contain email headers, PII, or tracking
artifacts — the data contract enforces this at the type level (PRIV-08).
"""

from src.models import RawMessage, CleanMessage, SanitizerConfig


def sanitize(raw: RawMessage, config: SanitizerConfig) -> CleanMessage:
    """Sanitize a raw email message for safe delivery to Claude.

    Transforms RawMessage (raw HTML/text, full sender, etc.) into CleanMessage
    (plain text, domain-only sender, PII-redacted, no tracking artifacts).

    Args:
        raw: The raw email message with HTML/text body.
        config: Sanitizer configuration including user PII to redact.

    Returns:
        CleanMessage with clean_text, sender_domain, subject, and date.

    Raises:
        NotImplementedError: Implementation provided in Plan 02.
    """
    raise NotImplementedError("Sanitizer implementation in Plan 02")
