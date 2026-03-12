"""
Delivery module for the Signals newsletter digest pipeline.

Provides:
  send_digest_email(markdown_text, html_text, config) -> None
      Send the daily digest as a multipart/alternative HTML email via
      Proton Mail Bridge SMTP using STARTTLS.

  save_archive(digest_md, config) -> Path
      Save the markdown digest to output/digest-YYYY-MM-DD.md.

  markdown_to_html(md) -> str
      Convert the fixed digest markdown structure to an HTML email body.

Security notes:
  - STARTTLS is called before login() — credentials are never sent in cleartext
  - ssl.CERT_NONE is acceptable for the loopback Bridge connection only
  - No sys.exit() — exceptions propagate to the orchestrator (scripts/daily.py)
"""

import re
import smtplib
import ssl
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def send_digest_email(
    markdown_text: str,
    html_text: str,
    config: dict,
    subject: str | None = None,
) -> None:
    """Send digest as an HTML email via Proton Mail Bridge SMTP.

    Uses STARTTLS with CERT_NONE — acceptable for loopback-only Bridge connection.
    Sends multipart/alternative: text/plain fallback + text/html primary.

    SECURITY: starttls() is always called before login() so credentials
    are never transmitted in cleartext.

    Args:
        markdown_text: Raw markdown digest (text/plain part).
        html_text:     HTML digest (text/html part).
        config:        Dict with smtp_host, smtp_port, imap_username,
                       imap_password, digest_recipient keys.
        subject:       Optional email subject. When None (default), falls back to
                       "Daily Digest — YYYY-MM-DD" for backward compatibility.
                       Pass an explicit subject for weekly digests, e.g.
                       "Weekly Digest — Week 11, 2026".

    Raises:
        smtplib.SMTPException: On any SMTP error (auth, connection, etc.).
    """
    today = date.today().isoformat()
    email_subject = subject if subject is not None else f"Daily Digest \u2014 {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_subject
    msg["From"] = config["imap_username"]
    msg["To"] = config["digest_recipient"]

    msg.attach(MIMEText(markdown_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_text, "html", "utf-8"))

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as smtp:
        smtp.starttls(context=ctx)
        smtp.login(config["imap_username"], config["imap_password"])
        smtp.send_message(msg)


def save_archive(digest_md: str, config: dict) -> Path:
    """Save digest markdown to the output directory.

    Creates the output directory if it does not exist. The filename is
    digest-YYYY-MM-DD.md based on today's date.

    Args:
        digest_md: Markdown text of the digest.
        config:    Dict with an 'output_dir' key (default './output').

    Returns:
        Path of the saved archive file.
    """
    output_dir = Path(config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    filepath = output_dir / f"digest-{today}.md"
    filepath.write_text(digest_md, encoding="utf-8")
    return filepath


def markdown_to_html(md: str) -> str:
    """Convert the digest markdown to an HTML email body.

    Handles the fixed digest structure only:
      ## Section headers  ->  <h2>
      ### Sub-headers     ->  <h3>
      - / * bullets       ->  <ul><li>
      **bold**            ->  <strong>bold</strong>
      blank lines         ->  close open list; no output
      regular text        ->  <p>

    Output is wrapped in a minimal <html><body> envelope.

    Args:
        md: Markdown string from Claude's digest output.

    Returns:
        HTML string suitable for the text/html MIME part.
    """
    lines = md.split("\n")
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            title = _apply_inline(stripped[3:])
            html_parts.append(f"<h2>{title}</h2>")

        elif stripped.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            title = _apply_inline(stripped[4:])
            html_parts.append(f"<h3>{title}</h3>")

        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item = _apply_inline(stripped[2:])
            html_parts.append(f"<li>{item}</li>")

        elif stripped == "":
            if in_list:
                html_parts.append("</ul>")
                in_list = False

        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{_apply_inline(stripped)}</p>")

    if in_list:
        html_parts.append("</ul>")

    body = "\n".join(html_parts)
    return (
        '<html><body style="font-family:sans-serif;max-width:700px;margin:auto">\n'
        + body
        + "\n</body></html>"
    )


def _apply_inline(text: str) -> str:
    """Apply inline markdown: **bold** -> <strong>bold</strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
