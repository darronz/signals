# Phase 1: Foundation and Privacy Sanitizer - Research

**Researched:** 2026-03-11
**Domain:** Python HTML email sanitization, PII redaction, typed data contracts, privacy boundary enforcement
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PRIV-01 | Sanitizer converts HTML email bodies to clean plain text | BeautifulSoup4 `get_text()` with `html.parser` backend; tag decomposition pattern confirmed |
| PRIV-02 | Sanitizer strips all tracking pixels (1x1 images, hidden imgs) | BS4 `find_all('img')` + attribute inspection for width/height==1 or 0, plus ALL img removal strategy |
| PRIV-03 | Sanitizer removes known tracking URL parameters (utm_*, mc_eid, fbclid, etc.) | `urllib.parse` parse_qs + urlencode round-trip; comprehensive parameter list documented below |
| PRIV-04 | Sanitizer redacts user's email address and name from body text | `re.sub()` with compiled patterns; re.escape() for literal email addresses |
| PRIV-05 | Sanitizer supports configurable extra PII redaction regex patterns | `re.compile()` on patterns loaded from config; applied in sequence after PRIV-04 |
| PRIV-06 | Sanitizer reduces sender identity to domain-only before passing to Claude | `email.utils.parseaddr()` + `urllib.parse.urlparse()` on the addr-spec to extract host part |
| PRIV-07 | Sanitizer truncates individual newsletter bodies to configurable character limit | Plain Python string slice `text[:limit]` after all other transforms |
| PRIV-08 | No email headers (To, CC, BCC, Message-ID, X-headers) ever reach Claude | Enforced by data contract: `CleanMessage` dataclass has no header fields; sanitizer only accepts body HTML/text |
| DOCS-02 | .env.example with placeholder values and descriptive comments | Pattern: copy all config keys with placeholder values, comment each line explaining purpose |
</phase_requirements>

## Summary

Phase 1 is a pure offline phase — no network, no Bridge connection, no Claude call. The entire deliverable is a set of Python source files forming the data contract (`src/models.py` or inline in `src/sanitizer.py`) plus the sanitizer module itself, with a comprehensive test suite exercising every privacy guarantee.

The privacy boundary is architectural: the `CleanMessage` dataclass physically cannot carry email headers, user PII, or tracking artifacts because those fields do not exist on the type. The sanitizer's job is to transform a raw HTML body (passed as a string) into a `CleanMessage` instance that satisfies all invariants. Nothing else in the pipeline ever handles raw email — only `CleanMessage` objects flow forward.

The technical stack is minimal by design: `beautifulsoup4` with the built-in `html.parser` backend for HTML-to-text conversion and tag removal; `urllib.parse` from the standard library for URL parameter stripping; `re` from the standard library for PII redaction and pattern matching; `python-dotenv` for configuration loading; `dataclasses` from the standard library for the data contract. No additional dependencies are needed for Phase 1 — `pytest` is the only test-time addition.

**Primary recommendation:** Build the `CleanMessage` dataclass first as the contract, then implement `sanitizer.py` to fill it, then write `tests/test_sanitizer.py` that asserts invariants against the contract. The `.env.example` and `src/config.py` skeleton complete the phase.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| beautifulsoup4 | >=4.12.0 (latest: 4.14.3) | HTML parsing, tag decomposition, text extraction | Project-mandated; html.parser backend needs no C deps |
| python-dotenv | >=1.0.0 (latest: 1.2.2) | Load .env configuration at runtime | Project-mandated; 12-factor config pattern |
| pytest | >=8.0 | Unit test runner | Standard Python testing tool; project AGENTS.md references it |

### Standard Library (no install needed)
| Module | Purpose |
|--------|---------|
| `re` | Regex PII redaction, tracking parameter matching |
| `urllib.parse` | URL parsing and parameter stripping (parse_qs, urlencode, urlparse) |
| `dataclasses` | Typed data contracts (RawMessage, CleanMessage) |
| `email.utils` | Parsing email address format to extract domain |
| `os` / `os.environ` | Environment variable access |
| `typing` | Type annotations (Optional, List) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| html.parser (stdlib) | lxml | lxml is faster but adds C dependency; html.parser is sufficient for newsletters |
| html.parser (stdlib) | html5lib | html5lib is most lenient but slowest; overkill for newsletter HTML |
| dataclasses | pydantic | Pydantic adds validation/coercion but adds a dependency; dataclasses + __post_init__ is sufficient |
| re.sub for PII | Microsoft Presidio / DataFog | Heavy ML-based libraries; overkill for the simple email/name redaction needed here |

**Installation:**
```bash
pip install beautifulsoup4>=4.12.0 python-dotenv>=1.0.0 pytest>=8.0
```

## Architecture Patterns

### Recommended Project Structure
```
signals/                          # project root
├── .env.example                  # placeholder config keys with comments
├── .env                          # actual config (gitignored)
├── .gitignore
├── requirements.txt              # beautifulsoup4, python-dotenv
├── requirements-dev.txt          # pytest (test-only)
├── src/
│   ├── __init__.py
│   ├── config.py                 # loads .env, returns typed config object
│   ├── models.py                 # RawMessage, CleanMessage dataclasses
│   ├── sanitizer.py              # HTML→text, PII redaction, detracking
│   └── main.py                   # orchestration (stub in Phase 1)
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # shared fixtures (sample HTML strings)
│   └── test_sanitizer.py         # all Phase 1 tests
└── prompts/
    └── summarize.txt             # stub (content added in Phase 3)
```

### Pattern 1: Typed Data Contract with Dataclasses

**What:** Two dataclasses form the privacy contract — `RawMessage` (everything from the email, before sanitization) and `CleanMessage` (only what can reach Claude). The type boundary IS the privacy boundary.

**When to use:** Always. The sanitizer function signature is `sanitize(raw: RawMessage, config: SanitizerConfig) -> CleanMessage`. The return type physically cannot contain headers or PII fields.

**Example:**
```python
# Source: Python docs — dataclasses module
from dataclasses import dataclass
from typing import Optional

@dataclass
class RawMessage:
    """Input to the sanitizer. Never leaves this module."""
    subject: str
    sender: str          # full email address, e.g. digest@morningbrew.com
    date: str
    body_html: Optional[str]
    body_text: Optional[str]
    # NOTE: No To, CC, BCC, Message-ID, X-headers — caller must not pass them

@dataclass
class CleanMessage:
    """Output of the sanitizer. Safe to pass to Claude."""
    subject: str
    sender_domain: str   # domain-only, e.g. morningbrew.com
    date: str
    clean_text: str      # plain text, no HTML, no PII, no tracking

@dataclass
class SanitizerConfig:
    user_email: str
    user_name: str
    extra_patterns: list[str]       # from REDACT_PATTERNS config
    max_body_chars: int = 15_000    # from MAX_BODY_CHARS config
```

### Pattern 2: HTML-to-Text Extraction with BeautifulSoup4

**What:** Parse HTML body, surgically remove unwanted elements, extract plain text with structural whitespace preserved.

**When to use:** Any time body_html is not None; fall back to body_text only if body_html is absent.

**Example:**
```python
# Source: BeautifulSoup4 docs — https://www.crummy.com/software/BeautifulSoup/bs4/doc/
import re
from bs4 import BeautifulSoup

def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove entire subtrees — content is discarded
    for tag in soup.find_all(["script", "style", "head", "meta", "link"]):
        tag.decompose()

    # Remove ALL img tags (tracking pixels + content images)
    # Conservative choice: safer than trying to distinguish "real" images
    for tag in soup.find_all("img"):
        tag.decompose()

    # Extract text; separator='\n' preserves block structure
    text = soup.get_text(separator="\n", strip=True)

    # Collapse runs of blank lines to single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

**Note on `strip=True` with `get_text()`:** Per BS4 4.9.0+ docs, `script`, `style`, and `template` tag contents are excluded from `get_text()` by default even without `decompose()` — but explicitly calling `decompose()` before extraction is clearer and more defensive.

### Pattern 3: URL Tracking Parameter Stripping

**What:** For each URL found in the plain text output, parse query parameters, remove all known tracking params, and reconstruct the URL.

**When to use:** Applied to the text after HTML extraction, using regex to find URLs.

**Example:**
```python
# Source: Python docs — urllib.parse
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

# Comprehensive list of known tracking parameters
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

def strip_tracking_params(url: str) -> str:
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
```

### Pattern 4: PII Redaction with re.sub()

**What:** After text extraction, redact the user's own email address and name using compiled regex patterns.

**When to use:** Always — runs after HTML extraction, before truncation.

**Example:**
```python
# Source: Python docs — re module
import re

def build_redaction_patterns(user_email: str, user_name: str, extra: list[str]):
    patterns = []

    # Exact email match (re.escape handles dots, plus signs)
    patterns.append(re.compile(re.escape(user_email), re.IGNORECASE))

    # Name match (only if name is at least 3 chars to avoid false positives)
    if len(user_name) >= 3:
        patterns.append(re.compile(r'\b' + re.escape(user_name) + r'\b', re.IGNORECASE))

    # Extra configurable patterns
    for p in extra:
        if p.strip():
            patterns.append(re.compile(p, re.IGNORECASE))

    return patterns

def apply_redaction(text: str, patterns: list[re.Pattern]) -> str:
    for pattern in patterns:
        text = pattern.sub("[REDACTED]", text)
    return text
```

### Pattern 5: Sender Domain Extraction

**What:** Given a full sender string (e.g. `"Morning Brew" <digest@morningbrew.com>`), extract only the domain.

**When to use:** When populating `CleanMessage.sender_domain`.

**Example:**
```python
# Source: Python docs — email.utils
from email.utils import parseaddr

def extract_sender_domain(sender: str) -> str:
    _, addr = parseaddr(sender)
    # addr is now: digest@morningbrew.com
    if "@" in addr:
        return addr.split("@", 1)[1].lower()
    # Fallback: if already just a domain or malformed
    return addr.lower() or "unknown"
```

### Pattern 6: Configuration Loading with python-dotenv

**What:** Load `.env` at startup, validate required keys are present, return typed config object.

**When to use:** Called once at import time or at the top of `main()`.

**Example:**
```python
# Source: python-dotenv docs
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file relative to cwd

def load_config() -> dict:
    required = ["IMAP_HOST", "IMAP_PORT", "IMAP_USERNAME", "IMAP_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")
    return {
        "imap_host": os.environ["IMAP_HOST"],
        # ... etc
        "user_email": os.environ.get("IMAP_USERNAME", ""),
        "user_name": os.environ.get("USER_DISPLAY_NAME", ""),
        "redact_patterns": [
            p.strip() for p in
            os.environ.get("REDACT_PATTERNS", "").split(",")
            if p.strip()
        ],
        "max_body_chars": int(os.environ.get("MAX_BODY_CHARS", "15000")),
    }
```

### Anti-Patterns to Avoid

- **Stripping img tags by size only:** Tracking pixels are often 0x0 or 1x1, but some senders use invisible images with no width/height attributes or CSS `display:none`. Safest approach is removing ALL img tags, not only small ones.
- **Regex HTML parsing:** Never use `re.sub` to strip HTML tags from the body. Nested tags, attributes with > characters, and malformed email HTML all break regex-based stripping. BeautifulSoup4 handles all these cases.
- **Processing raw headers in sanitizer:** The sanitizer must accept only the body (as a string), not an `email.message.Message` object. Passing the full Message object risks accidental header exposure.
- **Mutable default argument in dataclass:** Do not use `extra_patterns: list = []` as a default — use `field(default_factory=list)`.
- **Catching bare exceptions in URL stripping silently:** Log warnings when URL parsing fails so that unusual URL formats are detectable during testing.
- **Running redaction before HTML parsing:** Apply PII redaction to the extracted plain text, not to the raw HTML. Regex patterns behave unpredictably against HTML attribute values and encoded entities.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML parsing | Custom regex HTML stripper | `beautifulsoup4` with `html.parser` | Malformed email HTML breaks all regex approaches |
| Env config loading | Custom .env parser | `python-dotenv` | Handles quoting, escaping, multi-line values |
| URL parsing | String split on `?` | `urllib.parse.urlparse` + `parse_qsl` | Handles encoding, edge cases, malformed URLs |
| Email address parsing | Split on `@` after stripping display name | `email.utils.parseaddr` | Handles `"Display Name" <addr>` RFC 2822 format |
| Test running | Custom test script | `pytest` | Parameterization, fixtures, assertion introspection |

**Key insight:** Email HTML is among the worst-formed HTML on the internet. Senders use 1990s table layouts, inline styles, conditional comments, and non-standard tags. BeautifulSoup4 with `html.parser` tolerates all of this; any hand-rolled parser will have gaps.

## Common Pitfalls

### Pitfall 1: Assuming html.parser Produces Consistent Output on All Inputs
**What goes wrong:** Newsletter HTML from different senders may render differently through html.parser vs lxml. Tests using real .eml files from one sender may not catch issues with another sender's encoding.
**Why it happens:** html.parser uses Python's built-in parser which is more strict than lxml; malformed attributes or encodings in one newsletter may be handled differently.
**How to avoid:** Write test fixtures as synthetic HTML strings that represent known edge cases (not just one real newsletter). Test against: empty body, missing closing tags, deeply nested tables, UTF-8 encoded characters, HTML entities (`&amp;`, `&nbsp;`).
**Warning signs:** Test passes on fixture but fails on first real newsletter.

### Pitfall 2: Re-Escape Issues in PII Redaction
**What goes wrong:** User email contains regex metacharacters (e.g. `user+tag@example.com` has a `+`). Passing raw email string to `re.compile` without `re.escape()` causes either a regex error or incorrect pattern.
**Why it happens:** Forgetting that `re.escape()` is required for literal string matching.
**How to avoid:** Always use `re.compile(re.escape(user_email), re.IGNORECASE)`.
**Warning signs:** Test with `user+newsletters@example.com` fails or produces wrong output.

### Pitfall 3: UTF-8 / Encoding Issues in HTML Bodies
**What goes wrong:** HTML email bodies may be encoded as quoted-printable or base64 in the MIME structure. The sanitizer receives already-decoded Python strings, but if the caller passes bytes instead of str, BeautifulSoup4 will try to detect encoding and may get it wrong.
**Why it happens:** Python's `email` module decode path requires explicit `.get_payload(decode=True).decode(charset)` — the raw payload bytes must be decoded before passing to BeautifulSoup4.
**How to avoid:** Sanitizer function signature must accept `str`, not `bytes`. Document this. Phase 2 (IMAP fetch) must decode before calling sanitize.
**Warning signs:** BeautifulSoup4 raises `UnicodeDecodeError` or garbles text with accented characters.

### Pitfall 4: URL Stripping Modifies Non-URL Text
**What goes wrong:** Regex to find URLs in plain text matches too broadly, corrupting non-URL text (e.g. email addresses, file paths).
**Why it happens:** URL regex patterns are notoriously hard to get right. Overly greedy patterns match things that aren't URLs.
**How to avoid:** Use a well-known URL regex (e.g. starting with `https?://`) and apply `strip_tracking_params` only to clearly-URL-shaped matches. Never modify the surrounding non-URL text.
**Warning signs:** Output text has corrupted words adjacent to URLs.

### Pitfall 5: Config Loaded at Import Time Breaks Tests
**What goes wrong:** If `config.py` calls `load_dotenv()` and `os.environ` access at module import time, tests fail unless a `.env` file is present in the test environment.
**Why it happens:** Eager evaluation at import time rather than deferred loading.
**How to avoid:** Wrap config loading in a `load_config()` function that tests can avoid calling. Use `os.environ.get(key, default)` with sensible defaults for optional keys. In tests, inject `SanitizerConfig` directly without going through `load_config()`.
**Warning signs:** `pytest` errors on import before any test runs.

### Pitfall 6: Test Asserts on Presence of Redacted String, Not Absence
**What goes wrong:** Test checks `assert "[REDACTED]" in output` instead of `assert user_email not in output`. The first passes even if redaction failed (e.g. if input never contained the email in the first place).
**Why it happens:** Writing positive assertions when the security invariant is a negative claim.
**How to avoid:** The canonical test for PRIV-04/PRIV-08 is: `assert config.user_email not in clean_message.clean_text` and `assert config.user_email not in clean_message.sender_domain`.
**Warning signs:** Tests pass even when redaction code is completely removed.

## Code Examples

Verified patterns from official sources:

### Full Sanitizer Module Skeleton
```python
# src/sanitizer.py
import re
from dataclasses import dataclass, field
from email.utils import parseaddr
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from bs4 import BeautifulSoup
from typing import Optional

TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "mc_cid", "mc_eid", "fbclid", "gclid", "_ga", "_gl",
    "msclkid", "ttclid", "_hsenc", "_hsmi", "_ke", "vero_conv", "vero_id",
    "ref", "ref_src", "igshid", "igsh", "li_fat_id", "mkt_tok", "yclid",
    "scid", "icid", "dclid",
})

URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')

@dataclass
class RawMessage:
    subject: str
    sender: str
    date: str
    body_html: Optional[str]
    body_text: Optional[str]

@dataclass
class CleanMessage:
    subject: str
    sender_domain: str
    date: str
    clean_text: str

@dataclass
class SanitizerConfig:
    user_email: str
    user_name: str
    extra_patterns: list = field(default_factory=list)
    max_body_chars: int = 15_000

def sanitize(raw: RawMessage, config: SanitizerConfig) -> CleanMessage:
    body = raw.body_html or raw.body_text or ""
    if raw.body_html:
        text = _html_to_text(raw.body_html)
    else:
        text = raw.body_text or ""
    text = _strip_tracking_urls(text)
    text = _redact_pii(text, config)
    text = text[:config.max_body_chars]
    return CleanMessage(
        subject=raw.subject,
        sender_domain=_extract_domain(raw.sender),
        date=raw.date,
        clean_text=text,
    )
```

### Test Pattern — Invariant Assertions
```python
# tests/test_sanitizer.py
import pytest
from src.sanitizer import RawMessage, CleanMessage, SanitizerConfig, sanitize

@pytest.fixture
def config():
    return SanitizerConfig(
        user_email="user@example.com",
        user_name="Alice",
        extra_patterns=[],
        max_body_chars=15_000,
    )

def test_no_user_email_in_output(config):
    raw = RawMessage(
        subject="Weekly Newsletter",
        sender="digest@morningbrew.com",
        date="2026-03-11",
        body_html=f"<p>Hi Alice, click <a href='http://t.co/x?utm_source=email'>here</a>. Unsubscribe: user@example.com</p>",
        body_text=None,
    )
    result = sanitize(raw, config)
    assert config.user_email not in result.clean_text
    assert config.user_email not in result.sender_domain

def test_tracking_pixels_removed(config):
    raw = RawMessage(
        subject="Test",
        sender="a@newsletter.com",
        date="2026-03-11",
        body_html='<p>Content</p><img src="https://open.tracker.com/pixel.gif" width="1" height="1"/>',
        body_text=None,
    )
    result = sanitize(raw, config)
    assert "<img" not in result.clean_text
    assert "tracker.com" not in result.clean_text

def test_utm_params_stripped(config):
    raw = RawMessage(
        subject="Test",
        sender="a@newsletter.com",
        date="2026-03-11",
        body_html='<p>Read <a href="https://example.com/article?utm_source=newsletter&utm_medium=email&keep=this">article</a></p>',
        body_text=None,
    )
    result = sanitize(raw, config)
    assert "utm_source" not in result.clean_text
    assert "utm_medium" not in result.clean_text
    assert "keep=this" in result.clean_text  # non-tracking param preserved

def test_sender_domain_only(config):
    raw = RawMessage(
        subject="Test",
        sender='"Morning Brew" <digest@morningbrew.com>',
        date="2026-03-11",
        body_html="<p>Content</p>",
        body_text=None,
    )
    result = sanitize(raw, config)
    assert result.sender_domain == "morningbrew.com"
    assert "digest@" not in result.sender_domain
    assert "@" not in result.sender_domain

def test_truncation(config):
    config.max_body_chars = 100
    long_body = "x" * 500
    raw = RawMessage(
        subject="Test",
        sender="a@b.com",
        date="2026-03-11",
        body_html=f"<p>{long_body}</p>",
        body_text=None,
    )
    result = sanitize(raw, config)
    assert len(result.clean_text) <= 100

def test_output_is_plain_text(config):
    raw = RawMessage(
        subject="Test",
        sender="a@b.com",
        date="2026-03-11",
        body_html="<html><body><h1>Title</h1><p>Para</p><script>alert(1)</script></body></html>",
        body_text=None,
    )
    result = sanitize(raw, config)
    assert "<" not in result.clean_text
    assert ">" not in result.clean_text
    assert "alert" not in result.clean_text
```

### .env.example Pattern
```bash
# .env.example — copy to .env and fill in real values
# Do NOT commit .env to version control

# Proton Mail Bridge IMAP connection
# Host is always localhost when Bridge runs on the same machine
IMAP_HOST=127.0.0.1
# Default Bridge IMAP port (non-SSL, STARTTLS negotiated after connect)
IMAP_PORT=1143
# Your Proton Mail address (used as IMAP username)
IMAP_USERNAME=you@proton.me
# The 16-character password generated by Bridge — NOT your account password
IMAP_PASSWORD=your-bridge-generated-password

# Proton Mail Bridge SMTP (for sending digest back to yourself)
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_SECURITY=STARTTLS

# Newsletter source: fetch from this IMAP folder (preferred)
NEWSLETTER_FOLDER=Newsletters
# Fallback: comma-separated sender addresses if no folder is configured
NEWSLETTER_SENDERS=

# How far back to look for newsletters (in hours)
FETCH_SINCE_HOURS=24

# Claude Code CLI settings
# Set to full path if 'claude' is not in PATH
CLAUDE_CMD=claude
# Optional: override model (e.g. claude-sonnet-4-5, claude-opus-4)
CLAUDE_MODEL=

# Output settings
# Options: markdown | stdout | email
OUTPUT_FORMAT=markdown
# Directory for saved digest files (relative to project root)
OUTPUT_DIR=./output
# Destination address for emailed digests (only used if OUTPUT_FORMAT=email)
DIGEST_RECIPIENT=you@proton.me

# Privacy: Your display name as it appears in newsletters (for redaction)
USER_DISPLAY_NAME=Your Name

# Privacy: Extra PII redaction — comma-separated regex patterns
# Example: REDACT_PATTERNS=your-referral-code,your-affiliate-id
REDACT_PATTERNS=

# Sanitizer: max characters per newsletter body before truncation
MAX_BODY_CHARS=15000
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| html2text library | BeautifulSoup4 `get_text()` | This project's explicit decision | Avoids another dependency; html.parser is sufficient |
| Manual env var handling | python-dotenv 1.2.x | Project decision | Cleaner; handles quoting, .env hierarchy |
| `script`/`style` tag handling | BS4 4.9.0+ excludes by default in `get_text()` | BS4 4.9.0 | Still call `decompose()` explicitly for clarity |
| Dataclass with mutable defaults | `field(default_factory=list)` | Python 3.7+ | Required to avoid shared-state bugs |

**Deprecated/outdated:**
- `html.parser` limitation concern: html.parser in Python 3.10+ is significantly more robust than in Python 2 era. For newsletter HTML (not arbitrary web HTML), it handles all common cases.
- `html2text`: While still maintained, it's a third dependency not needed here.

## Open Questions

1. **Where exactly does `RawMessage` get populated?**
   - What we know: Phase 1 is offline; Phase 2 (IMAP) will create `RawMessage` instances.
   - What's unclear: Should `models.py` be a separate file, or should `RawMessage` live in `sanitizer.py`?
   - Recommendation: Put both dataclasses in `src/models.py` for cleaner imports. `sanitizer.py` imports from `models.py`.

2. **Should `src/config.py` raise on missing optional keys or silently default?**
   - What we know: IMAP credentials are required; `USER_DISPLAY_NAME` and `REDACT_PATTERNS` are optional.
   - What's unclear: Boundary between required and optional may shift as later phases add keys.
   - Recommendation: Required keys raise `ValueError` on missing; optional keys use `os.environ.get(key, default)` with documented defaults.

3. **Should `CleanMessage.subject` be sanitized too?**
   - What we know: Requirements mention body PII redaction; subject is passed through as-is to `CleanMessage`.
   - What's unclear: Subjects sometimes contain the user's name (e.g. "Alice, your weekly digest").
   - Recommendation: Apply the same PII redaction to `subject` field in the sanitizer. Low cost, high safety.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | `pytest.ini` or `pyproject.toml` — see Wave 0 |
| Quick run command | `pytest tests/test_sanitizer.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRIV-01 | HTML body converted to plain text (no HTML tags) | unit | `pytest tests/test_sanitizer.py::test_output_is_plain_text -x` | Wave 0 |
| PRIV-02 | Tracking pixels (all img tags) removed | unit | `pytest tests/test_sanitizer.py::test_tracking_pixels_removed -x` | Wave 0 |
| PRIV-03 | UTM/tracking params stripped from URLs | unit | `pytest tests/test_sanitizer.py::test_utm_params_stripped -x` | Wave 0 |
| PRIV-04 | User email address redacted from body | unit | `pytest tests/test_sanitizer.py::test_no_user_email_in_output -x` | Wave 0 |
| PRIV-05 | Extra configurable PII patterns applied | unit | `pytest tests/test_sanitizer.py::test_extra_patterns -x` | Wave 0 |
| PRIV-06 | Sender reduced to domain-only | unit | `pytest tests/test_sanitizer.py::test_sender_domain_only -x` | Wave 0 |
| PRIV-07 | Body truncated at configured limit | unit | `pytest tests/test_sanitizer.py::test_truncation -x` | Wave 0 |
| PRIV-08 | No header fields on CleanMessage type | static/unit | `pytest tests/test_sanitizer.py::test_clean_message_has_no_headers -x` | Wave 0 |
| DOCS-02 | .env.example file exists with all keys | smoke | `pytest tests/test_sanitizer.py::test_env_example_exists -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_sanitizer.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — makes tests/ a package
- [ ] `tests/conftest.py` — shared `config` fixture with test values
- [ ] `tests/test_sanitizer.py` — all PRIV-0x and DOCS-02 tests
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — point at `src/` for imports
- [ ] Framework install: `pip install pytest>=8.0` — not yet present

## Sources

### Primary (HIGH confidence)
- [BeautifulSoup4 4.14.3 official docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) — `get_text()`, `decompose()`, parser selection, tag finding
- [Python stdlib urllib.parse](https://docs.python.org/3/library/urllib.parse.html) — `urlparse`, `parse_qsl`, `urlencode`, `urlunparse`
- [Python stdlib dataclasses](https://docs.python.org/3/library/dataclasses.html) — dataclass decorator, field(), __post_init__
- [Python stdlib email.utils](https://docs.python.org/3/library/email.utils.html) — `parseaddr`
- [Python stdlib re](https://docs.python.org/3/library/re.html) — `re.sub`, `re.escape`, `re.compile`
- [pypi.org — beautifulsoup4 4.14.3](https://pypi.org/project/beautifulsoup4/) — version and Python compatibility confirmed
- [pypi.org — python-dotenv 1.2.2](https://pypi.org/project/python-dotenv/) — version and Python compatibility confirmed

### Secondary (MEDIUM confidence)
- [python-dotenv GitHub](https://github.com/theskumar/python-dotenv) — `load_dotenv()` usage patterns verified against PyPI page
- [pytest parametrize docs](https://docs.pytest.org/en/stable/how-to/parametrize.html) — parametrize pattern for sanitizer test cases
- [Mailchimp tracking params](https://learndigitaladvertising.com/solved-why-how-to-remove-mc_cid-and-mc_eid-from-google-analytics/) — mc_cid and mc_eid confirmed as Mailchimp-specific params
- [BitDark blog: tracking params](https://bitdark.net/blog/how-to-detect-tracking-links-in-sms-whatsapp-utm-click-ids-ref-tags/) — comprehensive tracking parameter list cross-referenced

### Tertiary (LOW confidence)
- WebSearch results on tracking parameter lists — cross-referenced against multiple sources; comprehensive list has HIGH confidence on major params (UTM, mc_eid, fbclid, gclid), MEDIUM on lesser-known ones (icid, scid, yclid)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified on PyPI with current versions; stdlib modules documented on python.org
- Architecture: HIGH — patterns directly supported by official BS4 and Python docs; AGENTS.md confirms project structure
- Pitfalls: HIGH — encoding, regex escape, and config-at-import-time issues are well-documented Python gotchas
- Tracking param list: MEDIUM — major params HIGH (UTM, mc_eid, fbclid verified); extended list from multiple cross-checked web sources

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable libraries; BS4 and dotenv update infrequently)
