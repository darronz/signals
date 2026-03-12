"""
CLI entry point for the Signals weekly digest rollup.

Reads daily digest markdown files from the output directory,
re-summarizes them into weekly trends using Claude CLI.

Exit codes (mirror daily.py OPS-03):
  0 — success (or --dry-run)
  1 — config/auth error (ValueError from load_config)
  2 — no daily digest files found in window
  3 — Claude CLI error (FileNotFoundError or RuntimeError from call_claude)

Usage:
  python scripts/weekly.py [--dry-run] [--since DAYS] [--verbose]
                           [--prompt FILE] [--output FORMAT]

Design constraints (per research and phase decisions):
- Prompt path resolved relative to project root via __file__ (cron-safe, Pitfall 4)
- load_dotenv() NOT called at module level — deferred to load_config() (anti-pattern)
- No sys.exit() in helper functions — only in main()
- Weekly archive written directly (not via save_archive — that hardcodes daily filename)
- glob("digest-*.md") not glob("*.md") — avoids picking up weekly files (Pitfall 2)
- weekly_archive_filename uses iso.year not today.year (Pitfall 1, year boundary)
"""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from src.config import load_config
from src.summarize import call_claude
from src.deliver import send_digest_email, markdown_to_html

# Default prompt path: resolved relative to project root so cron invocations
# from arbitrary working directories still find the file (research Pitfall 4).
_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_PROMPT = _PROJECT_ROOT / "prompts" / "weekly.txt"


def find_daily_digests(output_dir: Path, since_days: int = 7) -> list[Path]:
    """Return daily digest files from the last N days, sorted oldest-first.

    Uses glob("digest-*.md") to avoid picking up weekly-*.md files (Pitfall 2).
    Filters by date parsed from filename — does not rely on mtime.
    Skips files with unparseable date stems silently.

    Args:
        output_dir:  Directory to search for digest files.
        since_days:  Number of days to look back (inclusive of cutoff date).

    Returns:
        List of Path objects for matching files, sorted oldest-first.
    """
    cutoff = date.today() - timedelta(days=since_days)
    files = []
    for f in sorted(output_dir.glob("digest-*.md")):
        # filename: digest-YYYY-MM-DD.md
        try:
            file_date = date.fromisoformat(f.stem.replace("digest-", ""))
        except ValueError:
            continue  # skip malformed filenames
        if file_date >= cutoff:
            files.append(f)
    return files


def format_weekly_input(digest_files: list[Path]) -> str:
    """Concatenate daily digest files with date headers for Claude input.

    Each file is prefixed with "---\\nDate: YYYY-MM-DD\\n\\n{content}".
    Sections are joined with "\\n\\n".

    Args:
        digest_files: List of daily digest Path objects (ordered oldest-first).

    Returns:
        Concatenated string ready for Claude stdin, or empty string if list is empty.
    """
    if not digest_files:
        return ""

    parts = []
    for f in digest_files:
        date_str = f.stem.replace("digest-", "")
        content = f.read_text(encoding="utf-8").strip()
        parts.append(f"---\nDate: {date_str}\n\n{content}")
    return "\n\n".join(parts)


def weekly_archive_filename(today: date) -> str:
    """Return the weekly archive filename: weekly-YYYY-WXX.md.

    Uses isocalendar().year (not today.year) to handle the ISO year boundary
    correctly. In late December, ISO week 1 of the next year may start before
    December 31. (Research Pitfall 1)

    Args:
        today: The reference date (typically date.today()).

    Returns:
        Filename string, e.g. "weekly-2026-W11.md".
    """
    iso = today.isocalendar()
    return f"weekly-{iso.year}-W{iso.week:02d}.md"


def save_weekly_archive(digest_md: str, config: dict) -> Path:
    """Save the weekly digest markdown to the output directory.

    Writes directly using pathlib (not via src.deliver.save_archive which
    hardcodes the daily digest-YYYY-MM-DD.md filename).

    Creates output_dir if it does not exist.

    Args:
        digest_md: Markdown text of the weekly digest.
        config:    Dict with an 'output_dir' key (default './output').

    Returns:
        Path of the saved weekly archive file.
    """
    output_dir = Path(config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = weekly_archive_filename(date.today())
    filepath = output_dir / filename
    filepath.write_text(digest_md, encoding="utf-8")
    return filepath


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read daily digest files and produce a weekly summary using Claude CLI."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report found digest files and exit 0 without calling Claude.",
    )
    parser.add_argument(
        "--since",
        type=int,
        metavar="DAYS",
        default=7,
        help="Look back N days for daily digest files (default: 7).",
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
        help="Path to Claude prompt file (default: prompts/weekly.txt).",
    )
    parser.add_argument(
        "--output",
        metavar="FORMAT",
        default=None,
        help="Output format: markdown | email. Overrides OUTPUT_FORMAT env var.",
    )
    return parser


def main() -> None:
    """Run the weekly digest rollup pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    # Logging setup
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().setLevel(log_level)
    logger = logging.getLogger(__name__)

    # --- Step 1: Load configuration ---
    try:
        config = load_config()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    # Apply CLI overrides AFTER load_config() so they win over env vars
    if args.output is not None:
        config["output_format"] = args.output

    # Resolve prompt path
    prompt_path = args.prompt if args.prompt else str(_DEFAULT_PROMPT)

    # --- Step 2: Discover daily digest files ---
    output_dir = Path(config.get("output_dir", "./output"))
    digest_files = find_daily_digests(output_dir, since_days=args.since)

    logger.info("Found %d daily digest file(s) in the last %d days.", len(digest_files), args.since)

    # --- Step 3: Dry-run short-circuit ---
    if args.dry_run:
        print(f"Found {len(digest_files)} daily digest file(s) in the last {args.since} days:")
        for f in digest_files:
            print(f"  {f.name}")
        if digest_files:
            total_chars = sum(len(f.read_text(encoding="utf-8")) for f in digest_files)
            print(f"Total content: {total_chars} characters")
        print("Dry-run complete. No Claude call made.")
        sys.exit(0)

    # --- Step 4: Check for empty results ---
    if not digest_files:
        logger.info("No daily digest files found in the last %d days. Exiting.", args.since)
        sys.exit(2)

    # --- Step 5: Format combined input ---
    weekly_input = format_weekly_input(digest_files)

    # --- Step 6: Summarize with Claude ---
    try:
        digest = call_claude(prompt_path, weekly_input, config)
    except FileNotFoundError as exc:
        logger.error("Claude CLI not found: %s", exc)
        sys.exit(3)
    except RuntimeError as exc:
        logger.error("Claude CLI error: %s", exc)
        sys.exit(3)

    logger.info("Weekly digest generated (%d chars).", len(digest))

    # --- Step 7: Save weekly archive ---
    archive_path = save_weekly_archive(digest, config)
    logger.info("Weekly digest saved to %s", archive_path)

    # --- Step 8: Deliver ---
    output_format = config.get("output_format", "markdown")

    if output_format == "email":
        iso = date.today().isocalendar()
        subject_week = iso.week
        subject_year = iso.year
        html_digest = markdown_to_html(digest)
        send_digest_email(digest, html_digest, config)
        logger.info(
            "Weekly digest emailed to %s (Week %02d, %d)",
            config.get("digest_recipient", ""),
            subject_week,
            subject_year,
        )
    else:
        # markdown (default): archive already saved above; log path
        logger.info("Weekly digest written to %s", archive_path)

    sys.exit(0)


if __name__ == "__main__":
    main()
