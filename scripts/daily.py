"""
CLI entry point for the Signals newsletter digest pipeline.

Orchestrates: fetch -> sanitize -> summarize -> deliver

Exit codes (OPS-03):
  0 — success (or --dry-run)
  1 — config/auth error (ValueError from load_config, ConnectionRefusedError
      from fetch_messages, imaplib.IMAP4.error, OSError)
  2 — no newsletters fetched (empty result from fetch_messages)
  3 — Claude CLI error (FileNotFoundError or RuntimeError from call_claude)

Usage:
  python scripts/daily.py [--dry-run] [--since HOURS] [--verbose]
                          [--prompt FILE] [--output FORMAT]

Design constraints (per research and phase decisions):
- Prompt path resolved relative to project root via __file__ (cron-safe, Pitfall 3)
- SMTP keys NOT required by load_config — only validated when actually sending
- Library modules raise exceptions; only this script calls sys.exit()
- save_archive always called (DLVR-02 is unconditional, Open Question 3)
"""

import argparse
import imaplib
import logging
import sys
from pathlib import Path

from src.config import load_config, load_sanitizer_config
from src.fetch import fetch_messages
from src.sanitizer import sanitize
from src.summarize import call_claude, format_newsletter_input
from src.deliver import save_archive, send_digest_email, markdown_to_html

# Default prompt path: resolve relative to project root so cron invocations
# from arbitrary working directories still find the file (research Pitfall 3).
_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_PROMPT = _PROJECT_ROOT / "prompts" / "summarize.txt"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch newsletters, summarize with Claude, and deliver digest."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and sanitize only — do not call Claude or send email. Exit 0.",
    )
    parser.add_argument(
        "--since",
        type=int,
        metavar="HOURS",
        help="Override fetch_since_hours from config.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Set logging level to DEBUG.",
    )
    parser.add_argument(
        "--prompt",
        metavar="FILE",
        default=None,
        help="Path to Claude prompt file (default: prompts/summarize.txt).",
    )
    parser.add_argument(
        "--output",
        metavar="FORMAT",
        default=None,
        help="Output format: markdown | stdout | email. Overrides OUTPUT_FORMAT env var.",
    )
    return parser


def main() -> None:
    """Run the full newsletter digest pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    # Logging setup
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Ensure root logger level is set (tests check getLogger().level)
    logging.getLogger().setLevel(log_level)
    logger = logging.getLogger(__name__)

    # --- Step 1: Load configuration ---
    try:
        config = load_config()
        san_config = load_sanitizer_config()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)
    except OSError as exc:
        logger.error("OS error loading config: %s", exc)
        sys.exit(1)

    # Apply CLI overrides AFTER load_config() so they win over env vars
    if args.since is not None:
        config["fetch_since_hours"] = args.since
    if args.output is not None:
        config["output_format"] = args.output

    # Resolve prompt path
    prompt_path = args.prompt if args.prompt else str(_DEFAULT_PROMPT)

    # --- Step 2: Fetch messages ---
    try:
        raw_messages = fetch_messages(config)
    except (ConnectionRefusedError, imaplib.IMAP4.error, OSError) as exc:
        logger.error("IMAP fetch error: %s", exc)
        sys.exit(1)

    # --- Step 3: Check for empty results ---
    if not raw_messages:
        logger.info("No newsletters found in the configured time window. Exiting.")
        sys.exit(2)

    logger.info("Fetched %d newsletter(s).", len(raw_messages))

    # --- Step 4: Sanitize ---
    clean_messages = [sanitize(msg, san_config) for msg in raw_messages]
    newsletter_text = format_newsletter_input(clean_messages)

    # --- Step 5: Dry-run short-circuit ---
    if args.dry_run:
        print(newsletter_text)
        sys.exit(0)

    # --- Step 6: Summarize with Claude ---
    try:
        digest = call_claude(prompt_path, newsletter_text, config)
    except FileNotFoundError as exc:
        logger.error("Claude CLI not found: %s", exc)
        sys.exit(3)
    except RuntimeError as exc:
        logger.error("Claude CLI error: %s", exc)
        sys.exit(3)

    logger.info("Digest generated (%d chars).", len(digest))

    # --- Step 7: Save archive (always, unconditional per DLVR-02) ---
    archive_path = save_archive(digest, config)
    logger.info("Digest saved to %s", archive_path)

    # --- Step 8: Deliver ---
    output_format = config.get("output_format", "markdown")

    if output_format == "email":
        html_digest = markdown_to_html(digest)
        send_digest_email(digest, html_digest, config)
        logger.info("Digest emailed to %s", config.get("digest_recipient", ""))
    elif output_format == "stdout":
        print(digest)
    else:
        # markdown (default): archive already saved above; log path
        logger.info("Digest written to %s", archive_path)


if __name__ == "__main__":
    main()
