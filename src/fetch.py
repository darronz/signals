"""
IMAP fetch module for the Signals newsletter digest pipeline.

Connects to Proton Mail Bridge via IMAP STARTTLS, selects the configured
folder, fetches messages within the configured time window, and returns
a list of RawMessage objects ready for the sanitizer.

FETCH-01: localhost:1143 STARTTLS with ssl.SSLContext(CERT_NONE) for Bridge cert
FETCH-02: Configurable folder (NEWSLETTER_FOLDER env var); UID mode only
FETCH-03: Sender list fallback (NEWSLETTER_SENDERS env var) when no folder set
FETCH-04: Time window filter (FETCH_SINCE_HOURS env var, default 24)
FETCH-05: Multipart MIME walk, HTML preferred over plain text; charset fallback
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
    """Build SSLContext for Proton Bridge localhost self-signed certificate.

    SECURITY NOTE: CERT_NONE + check_hostname=False is acceptable ONLY because
    this connection is loopback-only (127.0.0.1). Never use this pattern for
    remote connections.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _extract_body(msg: email.message.Message) -> tuple[Optional[str], Optional[str]]:
    """Walk MIME parts and return (html_body, text_body). Either may be None.

    Prefers the first text/html part found; falls back to first text/plain.
    Attachments (Content-Disposition: attachment) are skipped.
    Charset decode errors fall back to utf-8 with replacement characters.
    """
    html_body: Optional[str] = None
    text_body: Optional[str] = None

    for part in msg.walk():
        # Skip container parts — they hold subparts, not content
        if part.get_content_maintype() == "multipart":
            continue
        # Skip attachments — only want inline body parts
        if "attachment" in part.get("Content-Disposition", ""):
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


def _is_within_window(msg: email.message.Message, since: datetime) -> bool:
    """Return True if message Date header is at or after `since` (UTC).

    Returns True conservatively if Date header is missing or unparseable.
    """
    date_header = msg.get("Date", "")
    if not date_header:
        return True  # no date — include conservatively
    try:
        msg_dt = email.utils.parsedate_to_datetime(date_header)
    except (ValueError, TypeError):
        return True  # Unparseable date — include conservatively

    # Normalize to UTC for comparison
    if msg_dt.tzinfo is None:
        # Naive datetime (-0000 timezone in RFC) — treat as UTC
        msg_dt = msg_dt.replace(tzinfo=timezone.utc)

    return msg_dt >= since.astimezone(timezone.utc)


def _sender_matches(msg: email.message.Message, allowed: list[str]) -> bool:
    """Return True if From header matches any address in allowed (case-insensitive substring)."""
    if not allowed:
        return True  # No filter — accept all
    from_header = msg.get("From", "").lower()
    return any(s.lower() in from_header for s in allowed)


def fetch_messages(config: dict) -> list[RawMessage]:
    """Fetch newsletter messages from Proton Mail Bridge.

    Connects via IMAP STARTTLS to the configured host/port, selects the
    configured folder (or INBOX as fallback), searches for recent messages
    using the SINCE criterion, fetches each as RFC822, applies hour-precision
    time window filter and optional sender filter, and returns RawMessage objects.

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

    # Hour-precision cutoff for Python-side filtering
    since_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    # IMAP SINCE is date-only — subtract extra 24h so the broad server-side
    # filter captures all messages; Python-side filter provides hour precision.
    since_date_str = (since_cutoff - timedelta(hours=24)).strftime("%d-%b-%Y")

    messages: list[RawMessage] = []

    with imaplib.IMAP4(host, port) as imap:
        imap.starttls(ssl_context=_build_ssl_context())
        imap.login(username, password)

        # Select folder or INBOX as fallback when no folder configured
        target_folder = folder if folder else "INBOX"
        typ, _ = imap.select(f'"{target_folder}"', readonly=True)
        if typ != "OK":
            return []

        # UID SEARCH: broad date filter (day precision)
        typ, data = imap.uid("SEARCH", None, "SINCE", since_date_str)
        if typ != "OK" or not data[0]:
            return []

        uids = data[0].split()

        for uid in uids:
            typ, fetch_data = imap.uid("FETCH", uid, "(RFC822)")
            if typ != "OK":
                continue
            for response_part in fetch_data:
                if not isinstance(response_part, tuple):
                    continue
                # response_part[0] = FETCH response header bytes
                # response_part[1] = raw RFC822 message bytes
                msg = email.message_from_bytes(
                    response_part[1],
                    policy=email.policy.default,
                )

                # Hour-precision time window filter (Python-side)
                if not _is_within_window(msg, since_cutoff):
                    continue

                # Sender filter — only when no folder is configured
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
