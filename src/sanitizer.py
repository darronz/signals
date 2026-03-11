"""
Privacy sanitizer for the Signals newsletter digest pipeline.

Transforms RawMessage (raw HTML/text, full sender, PII, tracking artifacts)
into CleanMessage (plain text, domain-only sender, PII-redacted, no tracking).

The privacy contract:
  sanitize(raw: RawMessage, config: SanitizerConfig) -> CleanMessage

All 8 PRIV requirements are enforced in this module:
  PRIV-01: HTML-to-text conversion (no HTML tags in output)
  PRIV-02: All img tags removed (tracking pixels and content images)
  PRIV-03: Tracking URL parameters stripped (utm_*, mc_eid, fbclid, etc.)
  PRIV-04: User email address and name redacted
  PRIV-05: Extra configurable PII regex patterns applied
  PRIV-06: Sender reduced to domain-only
  PRIV-07: Body truncated to configured character limit
  PRIV-08: CleanMessage type has no header fields (enforced by data contract)

Order matters: HTML-to-text FIRST, then URL stripping, then PII redaction,
then truncation. Never run redaction on raw HTML.
"""

import re
from email.utils import parseaddr
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from bs4 import BeautifulSoup

from src.models import RawMessage, CleanMessage, SanitizerConfig


# ---------------------------------------------------------------------------
# PRIV-03: Known tracking URL parameters
# ---------------------------------------------------------------------------

TRACKING_PARAMS = frozenset({
    # UTM (universal)
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform",
    # Mailchimp
    "mc_cid", "mc_eid",
    # Facebook / Meta
    "fbclid", "fb_action_ids", "fb_action_types",
    # Google
    "gclid", "gclsrc", "_ga", "_gl", "dclid",
    # Microsoft
    "msclkid",
    # TikTok
    "ttclid",
    # HubSpot
    "_hsenc", "_hsmi",
    # Klaviyo
    "_ke",
    # Vero
    "vero_conv", "vero_id",
    # Generic referral/tracking
    "ref", "ref_src", "ref_url", "referrer",
    "igshid", "igsh",
    "li_fat_id",
    "mkt_tok",     # Marketo
    "yclid",       # Yandex
    "scid",        # Snapchat
    "icid",        # IBM campaign
})

# ---------------------------------------------------------------------------
# Internal regex for finding URLs in plain text
# ---------------------------------------------------------------------------

URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _html_to_text(html: str) -> str:
    """Convert HTML to plain text, removing scripts, styles, and all images.

    Uses BeautifulSoup4 with html.parser (no C dependencies).
    Conservative approach: removes ALL img tags, not just tracking pixels.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove entire subtrees — content discarded
    for tag in soup.find_all(["script", "style", "head", "meta", "link"]):
        tag.decompose()

    # Remove ALL img tags (tracking pixels + content images)
    # Conservative choice: safer than trying to distinguish "real" images
    for tag in soup.find_all("img"):
        tag.decompose()

    # Extract text; separator='\n' preserves block structure
    text = soup.get_text(separator="\n", strip=True)

    # Collapse runs of blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_tracking_params(url: str) -> str:
    """Strip tracking parameters from a URL using urllib.parse round-trip.

    Preserves all non-tracking query parameters. Returns original URL unchanged
    on any exception (never corrupt a URL).
    """
    try:
        parsed = urlparse(url)
        # parse_qsl preserves order, returns list of (key, value) tuples
        clean_params = [
            (k, v) for k, v in parse_qsl(parsed.query)
            if k.lower() not in TRACKING_PARAMS
            and not k.lower().startswith("utm_")  # catch any utm_ variants
        ]
        new_query = urlencode(clean_params)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url  # never corrupt a URL; return original on any error


def _strip_tracking_urls(text: str) -> str:
    """Find all URLs in plain text and strip tracking parameters from each."""
    return URL_PATTERN.sub(lambda m: _strip_tracking_params(m.group(0)), text)


def _extract_domain(sender: str) -> str:
    """Extract domain from a sender string (e.g. '"Name" <addr@domain.com>').

    Returns the domain in lowercase. Fallback: "unknown".
    """
    _, addr = parseaddr(sender)
    # addr is now: digest@morningbrew.com (or just domain if malformed)
    if "@" in addr:
        return addr.split("@", 1)[1].lower()
    # Fallback: if already just a domain or malformed
    return addr.lower() or "unknown"


def _build_redaction_patterns(config: SanitizerConfig) -> list:
    """Build compiled regex patterns for PII redaction.

    Builds patterns for:
    - user_email (re.escape to handle special chars like + in addresses)
    - user_name (word-boundary match, only if >= 3 chars)
    - each extra_pattern from config
    """
    patterns = []

    # Exact email match (re.escape handles dots, plus signs, etc.)
    if config.user_email:
        patterns.append(re.compile(re.escape(config.user_email), re.IGNORECASE))

    # Name match: word boundary, only if name is at least 3 chars
    # (avoids false positives on short names like "Al")
    if config.user_name and len(config.user_name) >= 3:
        patterns.append(
            re.compile(r"\b" + re.escape(config.user_name) + r"\b", re.IGNORECASE)
        )

    # Extra configurable patterns from config
    for p in config.extra_patterns:
        if p.strip():
            patterns.append(re.compile(p, re.IGNORECASE))

    return patterns


def _redact_pii(text: str, config: SanitizerConfig) -> str:
    """Apply all PII redaction patterns, replacing matches with [REDACTED]."""
    patterns = _build_redaction_patterns(config)
    for pattern in patterns:
        text = pattern.sub("[REDACTED]", text)
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sanitize(raw: RawMessage, config: SanitizerConfig) -> CleanMessage:
    """Sanitize a raw email message for safe delivery to Claude.

    Transforms RawMessage (raw HTML/text, full sender, PII, tracking artifacts)
    into CleanMessage (plain text, domain-only sender, PII-redacted, no tracking).

    Pipeline order (order matters — never redact raw HTML):
      1. HTML-to-text conversion (or fallback to body_text)
      2. Tracking URL parameter stripping
      3. PII redaction (user email, name, extra patterns)
      4. Truncation to max_body_chars
      5. Subject PII redaction
      6. Sender domain extraction

    Args:
        raw: The raw email message with HTML/text body and full sender info.
        config: Sanitizer configuration including user PII to redact.

    Returns:
        CleanMessage with clean_text, sender_domain, subject (PII-redacted),
        and date. The return type physically cannot contain headers or PII.
    """
    # Step 1: Extract plain text
    if raw.body_html is not None:
        text = _html_to_text(raw.body_html)
    elif raw.body_text is not None:
        text = raw.body_text
    else:
        text = ""

    # Step 2: Strip tracking URL parameters
    text = _strip_tracking_urls(text)

    # Step 3: Redact PII from body
    text = _redact_pii(text, config)

    # Step 4: Truncate to configured character limit
    text = text[:config.max_body_chars]

    # Step 5: Redact PII from subject (per research Open Question 3)
    subject = _redact_pii(raw.subject, config)

    # Step 6: Extract sender domain (no full address, no @ sign)
    sender_domain = _extract_domain(raw.sender)

    return CleanMessage(
        subject=subject,
        sender_domain=sender_domain,
        date=raw.date,
        clean_text=text,
    )
