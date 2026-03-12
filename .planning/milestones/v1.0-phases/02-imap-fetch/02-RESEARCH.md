# Phase 2: IMAP Fetch - Research

**Researched:** 2026-03-12
**Domain:** Python IMAP client (imaplib), MIME parsing (email stdlib), Proton Mail Bridge STARTTLS, pytest mocking of live network dependencies
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FETCH-01 | Pipeline connects to Proton Mail Bridge via IMAP on localhost:1143 with STARTTLS | `imaplib.IMAP4` + `starttls(ssl_context)` pattern confirmed; ssl.SSLContext with CERT_NONE for localhost self-signed cert documented |
| FETCH-02 | Pipeline fetches all messages from a configurable IMAP folder (e.g. Newsletters) | `imap.select(folder)` + `imap.uid('SEARCH', ...)` pattern confirmed; folder name from config |
| FETCH-03 | Pipeline filters by configurable sender list as fallback when no folder configured | Server-side `SEARCH FROM` criterion or client-side filter after UID fetch; sender list from config |
| FETCH-04 | Pipeline fetches only messages within a configurable time window (default 24h) | IMAP `SINCE` date-text format (`DD-Mon-YYYY` via `strftime('%d-%b-%Y')`); secondary Python-side filter using `email.utils.parsedate_to_datetime` for hour-precision |
| FETCH-05 | Pipeline parses multipart MIME bodies, preferring HTML for richer extraction | `msg.walk()` depth-first traversal; prefer `text/html` over `text/plain`; `get_payload(decode=True)` + charset decode with fallback chain |
</phase_requirements>

## Summary

Phase 2 builds `src/fetch.py` — the IMAP client module that connects to Proton Mail Bridge on localhost:1143, selects a configured folder, searches for recent messages, fetches them as raw RFC822 bytes, parses each into MIME parts, and produces a list of `RawMessage` objects ready for the Phase 1 sanitizer.

The implementation is stdlib-only: `imaplib` for the IMAP connection, `ssl` for the STARTTLS context, and the `email` package for MIME parsing. No new external dependencies are introduced. The module's public surface is a single function `fetch_messages(config: dict) -> list[RawMessage]` that callers in the pipeline orchestrator consume.

The primary technical challenge is the Proton Mail Bridge self-signed certificate: Python rejects it by default, requiring a deliberately constructed `ssl.SSLContext` with `check_hostname=False` and `CERT_NONE` for the localhost connection. The second challenge is IMAP's two parallel numbering systems — sequence numbers (default) versus UIDs — where using sequence numbers causes silent wrong-message fetches whenever the mailbox changes. UID mode (`imap.uid('SEARCH', ...)` / `imap.uid('FETCH', ...)`) is mandatory from day one. The third challenge is MIME nesting: newsletters commonly embed their HTML body inside `multipart/alternative` inside `multipart/mixed`, requiring `msg.walk()` traversal rather than a naive `msg.get_payload()` call.

**Primary recommendation:** Implement `fetch.py` using stdlib `imaplib` + `email`, using `imap.uid()` for all SEARCH and FETCH calls, STARTTLS with a `ssl.SSLContext(CERT_NONE)` context, `msg.walk()` with HTML-first part preference, and a charset decode fallback chain. Test with `unittest.mock.patch` against a fake IMAP server — no live Bridge required for unit tests.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `imaplib` (stdlib) | built-in (Python 3.10+) | IMAP4 connection, folder select, UID SEARCH, UID FETCH | No external dep; `starttls()` and `uid()` methods are sufficient for this pipeline's narrow use case |
| `ssl` (stdlib) | built-in | Build `ssl.SSLContext` for Proton Bridge STARTTLS with self-signed cert | Required for localhost connection with Bridge-generated cert; `CERT_NONE` + `check_hostname=False` is acceptable for loopback-only connections |
| `email` (stdlib) | built-in (Python 3.10+) | Parse raw RFC822 bytes into MIME message tree; walk parts; decode payloads | `email.message_from_bytes()` with `policy=email.policy.default` returns `EmailMessage` objects with full MIME API |
| `email.utils` (stdlib) | built-in | Parse `Date` header to timezone-aware datetime; parse sender address | `parsedate_to_datetime()` raises on bad dates (handle with try/except); `parseaddr()` for sender extraction (already used in sanitizer) |
| `datetime` (stdlib) | built-in | Calculate `SINCE` date string from `FETCH_SINCE_HOURS` config; hour-precision cutoff for secondary filter | `datetime.now(tz=timezone.utc) - timedelta(hours=N)` for the time window |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock` (stdlib) | built-in | Mock `imaplib.IMAP4` in unit tests | Always in tests — no live Bridge required for unit coverage |
| `pytest` | >=8.0 (already installed) | Test runner, fixtures, parametrize | Already in requirements-dev.txt; no new installation needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `imaplib` (stdlib) | `IMAPClient 3.1.0` (PyPI) | IMAPClient offers a more Pythonic API: parsed response objects, built-in UID mode by default, cleaner error types. For this pipeline's narrow use case (login → select → search SINCE → fetch RFC822), `imaplib` is sufficient and avoids an external dep. Switch to IMAPClient if IMAP logic grows (CONDSTORE, QRESYNC, IDLE). |
| `email.message_from_bytes(policy=policy.default)` | `email.message_from_bytes()` (default compat32 policy) | `policy.default` returns `EmailMessage` (newer API with `get_body()`); `compat32` returns `Message` (older API). Use `policy.default` for `get_body()` access; fall back to `walk()` either way since `walk()` exists on both. |
| `msg.walk()` for MIME traversal | `msg.get_body(preferencelist=('html','plain'))` | `get_body()` requires `policy.default` (EmailMessage). `walk()` works with both policy families, making it more robust against policy changes. Use `walk()` as the primary traversal; `get_body()` as a convenience if policy is confirmed as `default`. |

**Installation:**
```bash
# No new dependencies needed — all stdlib.
# requirements.txt and requirements-dev.txt are unchanged.
```

## Architecture Patterns

### Recommended Module Structure

The new file is `src/fetch.py`. No other existing files change.

```
src/
├── __init__.py
├── config.py          # Already exists — provides IMAP credentials and folder config
├── models.py          # Already exists — RawMessage dataclass (the output type)
├── sanitizer.py       # Already exists — consumes RawMessage
└── fetch.py           # NEW in Phase 2 — produces list[RawMessage]

tests/
├── conftest.py        # Already exists — add IMAP mock fixtures here
├── test_sanitizer.py  # Already exists — unchanged
└── test_fetch.py      # NEW in Phase 2 — unit tests for fetch.py
```

### Pattern 1: STARTTLS Connection to Proton Mail Bridge

**What:** Open a plain IMAP4 socket to localhost:1143, immediately call `starttls()` with a permissive SSLContext, then authenticate with the Bridge-generated password.

**When to use:** Always — Bridge requires STARTTLS on port 1143; using `IMAP4_SSL` (which expects a CA-signed cert on port 993) fails.

**Example:**
```python
# Source: Python docs — imaplib.html and ssl module
import imaplib
import ssl

def _build_ssl_context() -> ssl.SSLContext:
    """Build SSLContext for Proton Bridge localhost self-signed certificate.

    SECURITY NOTE: CERT_NONE + check_hostname=False is acceptable ONLY because
    this connection is loopback-only (127.0.0.1). Never use this pattern for
    remote connections.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def connect(host: str, port: int, username: str, password: str) -> imaplib.IMAP4:
    imap = imaplib.IMAP4(host, port)
    imap.starttls(ssl_context=_build_ssl_context())
    imap.login(username, password)
    return imap
```

### Pattern 2: UID SEARCH with SINCE Criteria

**What:** Use `imap.uid('SEARCH', ...)` (not `imap.search()`) to get UIDs of messages received since a given date. Then use `imap.uid('FETCH', ...)` to retrieve those messages by UID.

**When to use:** Always. Sequence numbers (returned by the default `search()`/`fetch()`) are renumbered on EXPUNGE — any mailbox change (Bridge syncing) causes wrong-message fetches silently. UIDs are stable.

**IMAP SINCE date format:** `DD-Mon-YYYY` string. Python: `datetime.strftime('%d-%b-%Y')`.

**Note on SINCE precision:** IMAP `SINCE` is date-only (day boundary), not datetime. For a "last 24 hours" window, the `SINCE` date should be `today - 1 day` (catches extra messages), then Python-side datetime comparison provides hour precision. This is the correct two-step approach.

**Example:**
```python
# Source: Python docs — imaplib.html; RFC 3501 section 6.4.4
import imaplib
from datetime import datetime, timedelta, timezone

def search_since_uid(imap: imaplib.IMAP4, hours: int) -> list[bytes]:
    """Return list of UIDs for messages received in the last N hours."""
    # IMAP SINCE is date-only, so subtract one extra day to ensure we
    # capture all messages within the time window (Python-side filter refines)
    since_date = (datetime.now(tz=timezone.utc) - timedelta(hours=hours + 24))
    since_str = since_date.strftime("%d-%b-%Y")  # e.g. "10-Mar-2026"

    typ, data = imap.uid("SEARCH", None, "SINCE", since_str)
    if typ != "OK" or not data[0]:
        return []
    return data[0].split()  # list of uid bytes, e.g. [b'1', b'2', b'5']
```

### Pattern 3: UID FETCH and Response Parsing

**What:** Fetch full RFC822 message bytes by UID, then parse with `email.message_from_bytes()`. The response structure from `uid('FETCH', ...)` is a list where each element is a tuple `(header_bytes, message_bytes)` — only `message_bytes` (index 1 of the tuple) is the RFC822 content.

**When to use:** Always — for fetching full message bodies. For header-only prefetch (date filtering before full fetch), use `RFC822.HEADER` instead of `RFC822`.

**Example:**
```python
# Source: Python docs — imaplib.html, email.parser.html
import email
import email.policy

def fetch_message(imap: imaplib.IMAP4, uid: bytes) -> email.message.Message | None:
    """Fetch a single message by UID and parse it into an email.Message object."""
    typ, data = imap.uid("FETCH", uid, "(RFC822)")
    if typ != "OK":
        return None
    for response_part in data:
        if isinstance(response_part, tuple):
            # response_part[0] is the FETCH response header (b'1 (RFC822 {size}')
            # response_part[1] is the raw RFC822 bytes
            return email.message_from_bytes(
                response_part[1],
                policy=email.policy.default,
            )
    return None
```

### Pattern 4: MIME Walk — HTML-First Part Extraction

**What:** Use `msg.walk()` to traverse all MIME parts depth-first. Collect the first `text/html` part found; fall back to the first `text/plain` part if no HTML exists. Skip `multipart/*` parts (containers, not content).

**Why walk() over get_payload():** Many newsletters wrap `multipart/alternative` inside `multipart/mixed`. `msg.get_payload()` returns a list at the top level, not the content. Only `walk()` reliably reaches deeply nested leaf parts.

**Example:**
```python
# Source: Python docs — email.message.html (walk, get_content_type,
#         get_payload, get_content_charset)
def extract_body(msg: email.message.Message) -> tuple[str | None, str | None]:
    """Extract HTML and plain text bodies from a MIME message.

    Returns: (html_body, text_body) — either may be None.
    Prefers the first text/html part found; falls back to first text/plain.
    """
    html_body: str | None = None
    text_body: str | None = None

    for part in msg.walk():
        # Skip container parts — they hold subparts, not content
        if part.get_content_maintype() == "multipart":
            continue
        # Skip attachments — only want inline body parts
        disposition = part.get("Content-Disposition", "")
        if "attachment" in disposition:
            continue

        content_type = part.get_content_type()
        payload_bytes = part.get_payload(decode=True)  # handles base64/QP decoding
        if payload_bytes is None:
            continue

        # Decode bytes to str using charset from Content-Type header
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload_bytes.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = payload_bytes.decode("utf-8", errors="replace")

        if content_type == "text/html" and html_body is None:
            html_body = text
        elif content_type == "text/plain" and text_body is None:
            text_body = text

    return html_body, text_body
```

### Pattern 5: Date Header Parsing for Hour-Precision Filtering

**What:** After using IMAP `SINCE` as a broad filter, parse the `Date` header from each fetched message and apply Python-side filtering for hour precision. `email.utils.parsedate_to_datetime()` returns a timezone-aware datetime when the header has a timezone offset.

**Caveat:** `parsedate_to_datetime()` raises `ValueError` on malformed Date headers. Always wrap in try/except. Some very old newsletters send timezone as `-0000` (RFC semantics: UTC but unknown local time) — this returns a naive datetime. Compare using UTC throughout.

**Example:**
```python
# Source: Python docs — email.utils.html
import email.utils
from datetime import datetime, timezone

def message_is_within_window(msg: email.message.Message, since: datetime) -> bool:
    """Return True if the message Date header is at or after `since`."""
    date_header = msg.get("Date", "")
    if not date_header:
        # No date header — include by default (conservative)
        return True
    try:
        msg_dt = email.utils.parsedate_to_datetime(date_header)
    except (ValueError, TypeError):
        return True  # Unparseable date — include conservatively

    # Normalize to UTC for comparison
    if msg_dt.tzinfo is None:
        # Naive datetime (-0000 timezone in RFC) — treat as UTC
        msg_dt = msg_dt.replace(tzinfo=timezone.utc)

    # Normalize `since` to UTC if it isn't already
    since_utc = since.astimezone(timezone.utc)
    return msg_dt >= since_utc
```

### Pattern 6: Sender Fallback Filter (FETCH-03)

**What:** When `NEWSLETTER_FOLDER` is not configured (empty string), use the configured `NEWSLETTER_SENDERS` list as a filter. IMAP `SEARCH FROM` can filter server-side per sender, but for a list of senders a client-side filter on the `From` header is simpler and avoids multiple round-trips.

**Example:**
```python
def sender_matches(msg: email.message.Message, allowed_senders: list[str]) -> bool:
    """Return True if the From header matches any sender in allowed_senders.

    Matching is case-insensitive substring match on the email address portion.
    """
    if not allowed_senders:
        return True  # No filter — accept all
    from_header = msg.get("From", "").lower()
    return any(s.lower() in from_header for s in allowed_senders)
```

### Pattern 7: Building RawMessage from a Parsed MIME Message

**What:** After extracting the body parts and headers, assemble the five-field `RawMessage` dataclass. The caller (Phase 1 sanitizer) expects exactly these fields — no more, no less.

```python
# Source: src/models.py (existing Phase 1 contract)
from src.models import RawMessage

def build_raw_message(msg: email.message.Message) -> RawMessage:
    html_body, text_body = extract_body(msg)
    return RawMessage(
        subject=msg.get("Subject", "") or "",
        sender=msg.get("From", "") or "",
        date=msg.get("Date", "") or "",
        body_html=html_body,
        body_text=text_body,
        # NOTE: No To, CC, BCC, Message-ID, X-headers passed — PRIV-08
    )
```

### Anti-Patterns to Avoid

- **Using `imap.search()` instead of `imap.uid('SEARCH', ...)`:** `search()` returns sequence numbers that change on EXPUNGE. Silent wrong-message fetches result. Never use sequence number mode.
- **Using `IMAP4_SSL` instead of `IMAP4` + `starttls()`:** `IMAP4_SSL` tries to establish SSL before STARTTLS negotiation and on a different port (993 vs 1143). Bridge listens on 1143 with STARTTLS, not 993 with SSL.
- **`msg.get_payload()` at the top level of a multipart message:** Returns a list of subparts, not the body text. Must use `walk()` to reach leaf parts.
- **Storing or logging raw message bytes or full headers:** Violates the privacy model. Only log UID, sender domain (not full address), and character count of extracted body.
- **Fetching full RFC822 for all messages before date filtering:** Use `RFC822.HEADER` (headers only) as a pre-filter if the mailbox is large, then fetch full RFC822 only for in-window messages. For a typical Newsletters folder with < 100 messages, full fetch is fine.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IMAP protocol bytes | Custom TCP socket conversation | `imaplib.IMAP4` stdlib | IMAP has 200+ command variations; imaplib handles all of them |
| MIME tree traversal | Recursive string split on `Content-Type` | `msg.walk()` from `email` stdlib | MIME nesting depth is unbounded; `walk()` is depth-first recursive by design |
| Base64 / quoted-printable decoding | Manual base64.b64decode | `part.get_payload(decode=True)` | MIME transfer encoding is declared per-part; `get_payload(decode=True)` applies the correct decoder automatically |
| Email date parsing | `re.match` on date strings | `email.utils.parsedate_to_datetime()` | Email date format (RFC 2822) has at least 5 valid variant forms; hand-rolled parsing misses all of them |
| SSL context | `ssl.create_default_context()` (wrong for localhost) | `ssl.SSLContext(PROTOCOL_TLS_CLIENT)` with explicit `CERT_NONE` | Default context rejects Bridge's self-signed cert; explicit construction with comment is the correct approach |

**Key insight:** The `email` stdlib is comprehensive for RFC 2822 / MIME; every "clever" custom parser breaks on malformed real-world newsletter emails. `imaplib` handles the protocol complexity; the only tricky parts are UID mode and the SSL context configuration.

## Common Pitfalls

### Pitfall 1: Sequence Numbers Instead of UIDs
**What goes wrong:** `imap.search(None, 'SINCE', date_str)` returns sequence numbers. Any EXPUNGE between SEARCH and FETCH reassigns those numbers — the pipeline silently fetches the wrong messages.
**Why it happens:** The stdlib `imaplib` documentation examples all use `search()` / `fetch()` (sequence mode). UID mode requires using `imap.uid('SEARCH', ...)` and `imap.uid('FETCH', ...)`.
**How to avoid:** Never call `imap.search()` or `imap.fetch()` directly in this codebase. Only `imap.uid('SEARCH', ...)` and `imap.uid('FETCH', ...)`.
**Warning signs:** Fetched subject doesn't match the expected newsletter; intermittent content mismatch during Bridge sync.

### Pitfall 2: Proton Bridge Self-Signed Certificate Rejection
**What goes wrong:** `ssl.create_default_context()` or any default SSL context rejects Bridge's self-signed localhost certificate with `CERTIFICATE_VERIFY_FAILED`.
**Why it happens:** Python verifies server certificates by default; Bridge generates its own self-signed cert that is not in any CA bundle.
**How to avoid:** Build `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` with `check_hostname = False` and `verify_mode = ssl.CERT_NONE`. Document the localhost-only justification in a comment. This is the accepted pattern for loopback connections.
**Warning signs:** `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed` on first `starttls()` call.

### Pitfall 3: IMAP SINCE Is Date-Only, Not Datetime
**What goes wrong:** Setting `FETCH_SINCE_HOURS=24` and computing `SINCE` as today's date string. Messages from midnight yesterday (23+ hours ago) are excluded; messages from 23 hours ago yesterday are not in "today's" `SINCE` result.
**Why it happens:** RFC 3501 `SINCE` matches messages whose internal date is on or after the given calendar date — not an exact timestamp.
**How to avoid:** Subtract one extra day when computing the `SINCE` date string (`timedelta(hours=hours + 24)`), then apply Python-side datetime filtering using `email.utils.parsedate_to_datetime()` for hour precision.
**Warning signs:** First morning run misses newsletters that arrived after midnight.

### Pitfall 4: Multipart Body Extraction Returns None or Plain Text Only
**What goes wrong:** `msg.get_payload()` on a `multipart/mixed` message returns a list of `Message` objects (not text). Or: the HTML body is inside a nested `multipart/alternative` that is itself a part of `multipart/mixed`. Calling `get_payload()` at the top level misses it.
**Why it happens:** MIME nesting can be: `multipart/mixed` → `multipart/alternative` → `text/html`. Top-level `get_payload()` returns `[multipart/alternative, ...]` not the HTML string.
**How to avoid:** Always use `msg.walk()` and check `get_content_type()` on each leaf part.
**Warning signs:** Empty digests; summaries only contain "View in browser" links (the plain text fallback); works for some senders but not others.

### Pitfall 5: Charset Decode Crash on Non-UTF-8 Newsletters
**What goes wrong:** `part.get_payload(decode=True)` returns bytes; calling `.decode('utf-8')` on `windows-1252` or `latin-1` content raises `UnicodeDecodeError` and crashes the pipeline.
**Why it happens:** `get_payload(decode=True)` handles transfer encoding (base64/QP) but returns raw bytes — charset decoding is a separate step.
**How to avoid:** Use `part.get_content_charset()` to get the declared charset; fallback to `utf-8` with `errors='replace'`; wrap in `try/except LookupError` for unknown charset names.
**Warning signs:** `UnicodeDecodeError` in logs for specific senders; replacement characters (U+FFFD) in digest output.

### Pitfall 6: IMAP4 Connection Not Closed on Error
**What goes wrong:** An exception during fetch leaves the IMAP connection open. Proton Bridge has a connection limit; repeated errors exhaust it until Bridge is restarted.
**Why it happens:** `imaplib.IMAP4` does not auto-close on garbage collection in all Python versions.
**How to avoid:** Use `imaplib.IMAP4` as a context manager (Python 3.5+) — `with imaplib.IMAP4(host, port) as imap:` — or use try/finally with `imap.logout()`.
**Warning signs:** Bridge connection refused after a few failed runs; works after Bridge restart.

### Pitfall 7: Tests Require a Live Bridge
**What goes wrong:** Unit tests for `fetch.py` connect to `127.0.0.1:1143` and fail in any environment without a running authenticated Bridge (CI, another developer's machine, offline testing).
**Why it happens:** Not mocking the IMAP layer during tests.
**How to avoid:** All unit tests for `fetch.py` must use `unittest.mock.patch('src.fetch.imaplib.IMAP4')` to replace the IMAP4 class with a mock. Integration tests that require a live Bridge should be in a separate file (`tests/test_fetch_integration.py`) skipped by default with `pytest.mark.skip` or a custom marker.
**Warning signs:** `ConnectionRefusedError` during `pytest` runs on machines without Bridge.

## Code Examples

### Complete fetch.py Module Skeleton
```python
# src/fetch.py
"""
IMAP fetch module for the Signals newsletter digest pipeline.

Connects to Proton Mail Bridge via IMAP STARTTLS, selects the configured
folder, fetches messages within the configured time window, and returns
a list of RawMessage objects ready for the sanitizer.

FETCH-01: localhost:1143 STARTTLS with ssl.SSLContext(CERT_NONE) for Bridge cert
FETCH-02: Configurable folder (NEWSLETTER_FOLDER env var)
FETCH-03: Sender list fallback (NEWSLETTER_SENDERS env var) when no folder set
FETCH-04: Time window filter (FETCH_SINCE_HOURS env var, default 24)
FETCH-05: Multipart MIME walk, HTML preferred over plain text
"""

import email
import email.policy
import email.utils
import imaplib
import ssl
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models import RawMessage


def _build_ssl_context() -> ssl.SSLContext:
    # SECURITY NOTE: CERT_NONE is acceptable ONLY for loopback (127.0.0.1).
    # Proton Mail Bridge uses a self-signed cert that Python rejects by default.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _extract_body(msg: email.message.Message) -> tuple[Optional[str], Optional[str]]:
    """Walk MIME parts and return (html_body, text_body). Either may be None."""
    html_body: Optional[str] = None
    text_body: Optional[str] = None

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if "attachment" in part.get("Content-Disposition", ""):
            continue

        content_type = part.get_content_type()
        payload_bytes = part.get_payload(decode=True)
        if payload_bytes is None:
            continue

        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload_bytes.decode(charset, errors="replace")
        except LookupError:
            text = payload_bytes.decode("utf-8", errors="replace")

        if content_type == "text/html" and html_body is None:
            html_body = text
        elif content_type == "text/plain" and text_body is None:
            text_body = text

    return html_body, text_body


def _is_within_window(msg: email.message.Message, since: datetime) -> bool:
    """Return True if message Date header is at or after `since` (UTC)."""
    date_header = msg.get("Date", "")
    if not date_header:
        return True  # no date — include conservatively
    try:
        msg_dt = email.utils.parsedate_to_datetime(date_header)
    except (ValueError, TypeError):
        return True
    if msg_dt.tzinfo is None:
        msg_dt = msg_dt.replace(tzinfo=timezone.utc)
    return msg_dt >= since.astimezone(timezone.utc)


def _sender_matches(msg: email.message.Message, allowed: list[str]) -> bool:
    """Return True if From header matches any address in allowed (case-insensitive)."""
    if not allowed:
        return True
    from_header = msg.get("From", "").lower()
    return any(s.lower() in from_header for s in allowed)


def fetch_messages(config: dict) -> list[RawMessage]:
    """Fetch newsletter messages from Proton Mail Bridge.

    Args:
        config: Dict from src.config.load_config(), containing keys:
            imap_host, imap_port, imap_username, imap_password,
            newsletter_folder, newsletter_senders, fetch_since_hours

    Returns:
        List of RawMessage objects (may be empty if no matching messages).

    Raises:
        imaplib.IMAP4.error: On authentication or IMAP protocol errors.
        ConnectionRefusedError: If Bridge is not running on the configured port.
    """
    host = config["imap_host"]
    port = config["imap_port"]
    username = config["imap_username"]
    password = config["imap_password"]
    folder = config.get("newsletter_folder", "Newsletters")
    senders = config.get("newsletter_senders", [])
    hours = config.get("fetch_since_hours", 24)

    # SINCE date: subtract extra 24h to ensure hour-precision filter catches all
    since_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    since_date_str = (since_cutoff - timedelta(hours=24)).strftime("%d-%b-%Y")

    messages: list[RawMessage] = []

    with imaplib.IMAP4(host, port) as imap:
        imap.starttls(ssl_context=_build_ssl_context())
        imap.login(username, password)

        # Select folder or INBOX as fallback
        target_folder = folder if folder else "INBOX"
        typ, _ = imap.select(f'"{target_folder}"', readonly=True)
        if typ != "OK":
            return []

        # UID SEARCH: SINCE filter (broad, date-only)
        typ, data = imap.uid("SEARCH", None, "SINCE", since_date_str)
        if typ != "OK" or not data[0]:
            return []

        uids = data[0].split()

        for uid in uids:
            typ, fetch_data = imap.uid("FETCH", uid, "(RFC822)")
            if typ != "OK":
                continue
            for part in fetch_data:
                if not isinstance(part, tuple):
                    continue
                msg = email.message_from_bytes(part[1], policy=email.policy.default)

                # Hour-precision filter
                if not _is_within_window(msg, since_cutoff):
                    continue

                # Sender filter (only applied when no folder is configured)
                if not folder and not _sender_matches(msg, senders):
                    continue

                html_body, text_body = _extract_body(msg)

                messages.append(RawMessage(
                    subject=msg.get("Subject", "") or "",
                    sender=msg.get("From", "") or "",
                    date=msg.get("Date", "") or "",
                    body_html=html_body,
                    body_text=text_body,
                ))

    return messages
```

### Mocking Pattern for Unit Tests
```python
# tests/test_fetch.py
import email
import email.policy
from unittest.mock import MagicMock, patch, call
import pytest
from src.fetch import fetch_messages


def make_raw_email(subject: str, sender: str, date: str, html: str) -> bytes:
    """Build a minimal RFC822 message as bytes for mock FETCH responses."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = date
    msg.attach(MIMEText(html, "html"))
    return msg.as_bytes()


@pytest.fixture
def base_config():
    return {
        "imap_host": "127.0.0.1",
        "imap_port": 1143,
        "imap_username": "user@proton.me",
        "imap_password": "bridge-password",
        "newsletter_folder": "Newsletters",
        "newsletter_senders": [],
        "fetch_since_hours": 24,
    }


@patch("src.fetch.imaplib.IMAP4")
def test_returns_raw_messages_for_matching_uids(mock_imap_class, base_config):
    """FETCH-02: Messages from configured folder are returned as RawMessage objects."""
    raw_bytes = make_raw_email(
        subject="Daily Digest",
        sender="digest@example.com",
        date="Thu, 12 Mar 2026 08:00:00 +0000",
        html="<p>Newsletter content</p>",
    )

    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.starttls.return_value = None
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.uid.side_effect = [
        ("OK", [b"1"]),                          # SEARCH response
        ("OK", [(b"1 (RFC822 {n})", raw_bytes)]), # FETCH response for uid 1
    ]

    result = fetch_messages(base_config)

    assert len(result) == 1
    assert result[0].subject == "Daily Digest"
    assert result[0].sender == "digest@example.com"
    assert result[0].body_html is not None
    assert "<p>Newsletter content</p>" in result[0].body_html


@patch("src.fetch.imaplib.IMAP4")
def test_returns_empty_list_when_no_messages(mock_imap_class, base_config):
    """FETCH-04: Empty result when no messages match the time window."""
    mock_imap = MagicMock()
    mock_imap_class.return_value.__enter__.return_value = mock_imap
    mock_imap.starttls.return_value = None
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"0"])
    mock_imap.uid.return_value = ("OK", [b""])  # empty SEARCH result

    result = fetch_messages(base_config)
    assert result == []
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `email.message_from_string()` with `compat32` policy | `email.message_from_bytes()` with `policy=email.policy.default` | Python 3.6+ | Newer API; `EmailMessage` adds `get_body()` convenience method |
| `IMAP4_SSL` on port 993 | `IMAP4` + `starttls()` on port 1143 | Proton Bridge architecture | Required for Bridge's STARTTLS-on-plain-socket design |
| `email.utils.parsedate_tz()` + `mktime_tz()` | `email.utils.parsedate_to_datetime()` | Python 3.3+ | Returns datetime directly; raises ValueError on invalid dates (better error handling) |
| `imap.search()` + `imap.fetch()` | `imap.uid('SEARCH', ...)` + `imap.uid('FETCH', ...)` | Best practice established at IMAP protocol level | Eliminates wrong-message fetches on concurrent mailbox changes |

**Deprecated/outdated:**
- `email.message_from_string()` (compat32): still works but `compat32` policy's `Message` API lacks `get_body()` — prefer bytes + default policy.
- Sequence-number IMAP mode (`imap.search()` / `imap.fetch()`): never use in this pipeline.

## Open Questions

1. **What folder does the user's actual Bridge IMAP expose?**
   - What we know: Config default is `Newsletters`; Bridge mirrors Proton Mail folder structure.
   - What's unclear: The user may have folders with spaces in names (requiring quoting) or non-ASCII names.
   - Recommendation: Always quote folder names in `imap.select(f'"{folder}"')`. Test with `imap.list()` in a debug mode if the user reports folder not found.

2. **Should `fetch_messages` raise or return empty on Bridge connection failure?**
   - What we know: Project exit code 1 = config/auth error; the orchestrator should catch and map exceptions.
   - What's unclear: Whether `fetch.py` should handle its own exceptions or let them propagate.
   - Recommendation: Let `imaplib.IMAP4.error` and `ConnectionRefusedError` propagate to the orchestrator (which is built in Phase 3). Document the expected exception types in the function docstring.

3. **Sender filter (FETCH-03): server-side SEARCH FROM vs. client-side filter?**
   - What we know: IMAP `SEARCH FROM addr` is valid per RFC 3501 for single-sender matching.
   - What's unclear: For a list of senders, multiple SEARCH calls or an OR criterion is needed. Bridge may not support all search criteria optimally.
   - Recommendation: Fetch all messages from the folder (using `SINCE` for time window), then apply client-side sender filter. For a Newsletters folder, the volume is small enough that client-side filtering adds no meaningful overhead.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (already configured) |
| Quick run command | `pytest tests/test_fetch.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FETCH-01 | STARTTLS connection established; starttls() called with ssl_context | unit (mock) | `pytest tests/test_fetch.py::test_starttls_called -x` | Wave 0 |
| FETCH-02 | Messages from configured folder are returned as RawMessage list | unit (mock) | `pytest tests/test_fetch.py::test_returns_raw_messages_for_matching_uids -x` | Wave 0 |
| FETCH-03 | Sender filter applied when no folder is configured | unit (mock) | `pytest tests/test_fetch.py::test_sender_filter_applied_without_folder -x` | Wave 0 |
| FETCH-04 | Only messages within time window are included; SINCE date computed correctly | unit (mock) | `pytest tests/test_fetch.py::test_time_window_filter -x` | Wave 0 |
| FETCH-05 | Multipart MIME: HTML part preferred; plain text fallback used when no HTML | unit (no mock) | `pytest tests/test_fetch.py::test_html_part_preferred -x` | Wave 0 |

Additional tests needed:
- `test_uid_mode_used` — assert `imap.uid()` is called, never `imap.search()` or `imap.fetch()`
- `test_empty_folder_returns_empty_list` — SEARCH returns no UIDs → `[]`
- `test_charset_fallback` — latin-1 encoded part decoded without crash
- `test_connection_not_left_open_on_error` — context manager ensures logout

### Sampling Rate
- **Per task commit:** `pytest tests/test_fetch.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green (all 13 PRIV tests + all FETCH tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fetch.py` — all FETCH-0x tests using mock IMAP
- [ ] No framework changes needed — pytest already installed and configured

*(Existing infrastructure: `pyproject.toml` with `pythonpath=["."]` and `testpaths=["tests"]` covers the new test file automatically)*

## Sources

### Primary (HIGH confidence)
- [Python imaplib official docs](https://docs.python.org/3/library/imaplib.html) — `IMAP4` constructor, `starttls()`, `uid()`, `select()`, `search()`, `fetch()` method signatures confirmed
- [Python email.message official docs](https://docs.python.org/3/library/email.message.html) — `walk()`, `get_content_type()`, `get_content_maintype()`, `get_payload(decode=True)`, `get_content_charset()` confirmed
- [Python email.parser official docs](https://docs.python.org/3/library/email.parser.html) — `message_from_bytes()` signature, `policy=email.policy.default` behavior confirmed
- [Python email.utils official docs](https://docs.python.org/3/library/email.utils.html) — `parsedate_to_datetime()` signature, naive vs aware datetime behavior confirmed
- [RFC 3501 section 6.4.4](https://www.rfc-editor.org/rfc/rfc3501) — SINCE date-text format `DD-Mon-YYYY` confirmed
- Prior research: `.planning/research/STACK.md`, `.planning/research/PITFALLS.md`, `.planning/research/ARCHITECTURE.md` — all HIGH confidence; directly applicable to this phase

### Secondary (MEDIUM confidence)
- [Proton Mail Bridge settings guide](https://proton.me/support/comprehensive-guide-to-bridge-settings) — STARTTLS on port 1143, SMTP on port 1025 confirmed; self-signed certificate behavior documented
- [paperless-ngx Proton Bridge integration issues](https://github.com/paperless-ngx/paperless-ngx/issues/4043) — Real-world confirmation that CERT_NONE + check_hostname=False is the required pattern for Bridge localhost connections
- [Python unittest.mock docs](https://docs.python.org/3/library/unittest.mock.html) — `patch()` pattern for mocking `imaplib.IMAP4` class confirmed

### Tertiary (LOW confidence)
- None — all critical claims verified against official documentation or official project pages.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib modules; verified against python.org docs
- Architecture patterns: HIGH — verified against official imaplib, email, and ssl docs; patterns match existing Phase 1 code conventions
- Proton Bridge SSL behavior: MEDIUM — verified against Proton support pages and real-world integration reports; CERT_NONE pattern is the established workaround
- Pitfalls: HIGH — UID mode, SINCE date-only semantics, and MIME walk requirements all verified against official IMAP RFC and Python docs

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stdlib is stable; Bridge port/protocol behavior changes only on major Bridge version updates)
