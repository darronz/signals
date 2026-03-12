# Signals

A daily and weekly newsletter digest pipeline that fetches newsletters via IMAP, sanitizes them for privacy, summarizes them with Claude CLI, and delivers the result as HTML email and/or markdown archive.

## What This Is

Signals fetches newsletters from a Proton Mail inbox, strips tracking links and PII, pipes the cleaned text to Claude for summarization, and sends a single skimmable digest email each morning. A weekly rollup script produces a higher-level trend summary from the week's daily digests.

## Prerequisites

- **Python 3.10+** — required for `date.isocalendar()` named attributes and `match` statements
- **Proton Mail Bridge** — must be installed, running, and authenticated; provides the IMAP/SMTP loopback interface
- **Claude CLI** — must be installed and authenticated (`claude --version` should succeed)
- **pip / venv** — standard Python tooling (or [uv](https://docs.astral.sh/uv/) as a faster alternative)

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/signals.git
cd signals

# 2. Create and activate a virtual environment
python3 -m venv .venv
# Or with uv:
# uv venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
# Or with uv:
# uv pip install -r requirements.txt

# 4. Copy the example config and fill in your values
cp .env.example .env
$EDITOR .env

# 5. Verify setup with a dry-run (no email sent, no Claude call for weekly)
python scripts/daily.py --dry-run
# Or with uv:
# uv run scripts/daily.py --dry-run
python scripts/weekly.py --dry-run
# Or with uv:
# uv run scripts/weekly.py --dry-run
```

## Configuration Reference

All configuration is loaded from a `.env` file in the project root. The table below lists every key recognized by `src/config.py`.

| Environment Variable | Required | Default | Description |
|----------------------|----------|---------|-------------|
| `IMAP_HOST` | Yes | — | IMAP server hostname (Proton Mail Bridge: `127.0.0.1`) |
| `IMAP_PORT` | Yes | — | IMAP server port (Proton Mail Bridge: `1143`) |
| `IMAP_USERNAME` | Yes | — | Your Proton Mail address (used for both IMAP login and SMTP From) |
| `IMAP_PASSWORD` | Yes | — | Your Proton Mail Bridge password (not your account password) |
| `SMTP_HOST` | No | `127.0.0.1` | SMTP server hostname for sending digest email |
| `SMTP_PORT` | No | `1025` | SMTP server port |
| `SMTP_SECURITY` | No | `STARTTLS` | SMTP security mode (`STARTTLS` recommended) |
| `NEWSLETTER_FOLDER` | No | `Newsletters` | IMAP folder to fetch newsletters from |
| `NEWSLETTER_SENDERS` | No | `` | Comma-separated list of allowed sender addresses; empty = accept all |
| `FETCH_SINCE_HOURS` | No | `24` | Fetch newsletters received in the last N hours |
| `CLAUDE_CMD` | No | `claude` | Path or name of the Claude CLI binary |
| `CLAUDE_MODEL` | No | `` | Claude model to use (empty = CLI default) |
| `OUTPUT_FORMAT` | No | `markdown` | Output mode: `markdown` (save file only), `email` (send email), `stdout` (print to terminal) |
| `OUTPUT_DIR` | No | `./output` | Directory where digest and weekly archive files are saved |
| `DIGEST_RECIPIENT` | No | `` | Email address to send the digest to (required when `OUTPUT_FORMAT=email`) |
| `USER_DISPLAY_NAME` | No | `` | Your display name for redaction purposes |
| `REDACT_PATTERNS` | No | `` | Comma-separated regex patterns to redact from newsletter content |
| `MAX_BODY_CHARS` | No | `15000` | Maximum characters per newsletter body before truncation |
| `DIGEST_WORD_TARGET` | No | `500` | Target word count hint passed to Claude via the prompt |

### Example `.env` File

```dotenv
# IMAP (Proton Mail Bridge)
IMAP_HOST=127.0.0.1
IMAP_PORT=1143
IMAP_USERNAME=you@proton.me
IMAP_PASSWORD=your-bridge-password

# SMTP (Proton Mail Bridge)
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_SECURITY=STARTTLS

# Newsletter filtering
NEWSLETTER_FOLDER=Newsletters
NEWSLETTER_SENDERS=newsletter@example.com,digest@another.com

# Claude
CLAUDE_CMD=claude
CLAUDE_MODEL=

# Output
OUTPUT_FORMAT=email
OUTPUT_DIR=./output
DIGEST_RECIPIENT=you@proton.me
USER_DISPLAY_NAME=Your Name

# Privacy
REDACT_PATTERNS=
MAX_BODY_CHARS=15000
DIGEST_WORD_TARGET=500
```

## Usage

### Daily Digest

```bash
# Full run — fetch, summarize, deliver
python scripts/daily.py
# Or with uv: uv run scripts/daily.py [same flags]

# Dry-run — fetch and sanitize only, no Claude call, no email
python scripts/daily.py --dry-run

# Override fetch window
python scripts/daily.py --since 48   # look back 48 hours

# Override output format
python scripts/daily.py --output email
python scripts/daily.py --output markdown
python scripts/daily.py --output stdout

# Use a custom prompt
python scripts/daily.py --prompt /path/to/my-prompt.txt

# Verbose logging
python scripts/daily.py --verbose
```

### Weekly Rollup

```bash
# Full run — read last 7 days of daily digests, synthesize, deliver
python scripts/weekly.py
# Or with uv: uv run scripts/weekly.py [same flags]

# Dry-run — report found files, no Claude call, no email
python scripts/weekly.py --dry-run

# Look back 14 days instead of 7
python scripts/weekly.py --since 14

# Override output format
python scripts/weekly.py --output email
python scripts/weekly.py --output markdown

# Use a custom weekly prompt
python scripts/weekly.py --prompt /path/to/weekly-prompt.txt

# Verbose logging
python scripts/weekly.py --verbose
```

### Shell Wrappers

Pre-built shell scripts are available in `scripts/`:

```bash
# Run the daily digest with prerequisite checks (Bridge + claude must be running)
scripts/run-digest.sh

# Run the weekly rollup with prerequisite checks
scripts/run-weekly.sh

# Run daily in dry-run mode
scripts/dry-run.sh
```

## Dry-Run Verification

Before enabling email delivery, verify your setup step by step:

```bash
# 1. Check that newsletters can be fetched (no email sent, no Claude)
python scripts/daily.py --dry-run
# Or with uv: uv run scripts/daily.py --dry-run

# 2. Check that daily digest files exist for weekly rollup
python scripts/weekly.py --dry-run

# 3. Test summarization to stdout (no email sent)
python scripts/daily.py --output stdout

# 4. Test full pipeline with email
python scripts/daily.py --output email
```

The dry-run for `weekly.py` reports how many daily digest files were found and their total character count, then exits 0 without calling Claude.

## Cron Setup

To run the daily digest automatically at 7 AM local time:

```cron
# Daily digest at 7:00 AM
0 7 * * * /path/to/signals/.venv/bin/python /path/to/signals/scripts/daily.py >> /var/log/signals-daily.log 2>&1
# Or with uv:
# 0 7 * * * cd /path/to/signals && uv run scripts/daily.py >> /var/log/signals-daily.log 2>&1

# Weekly rollup every Monday at 8:00 AM
0 8 * * 1 /path/to/signals/.venv/bin/python /path/to/signals/scripts/weekly.py >> /var/log/signals-weekly.log 2>&1
# Or with uv:
# 0 8 * * 1 cd /path/to/signals && uv run scripts/weekly.py >> /var/log/signals-weekly.log 2>&1
```

**Important:** Use absolute paths in cron entries. Scripts resolve the prompt file path relative to `__file__`, so they are cron-safe.

## Output Files

- **Daily archives:** `output/digest-YYYY-MM-DD.md` — one file per run
- **Weekly archives:** `output/weekly-YYYY-WXX.md` — ISO week numbering (e.g. `weekly-2026-W11.md`)

Re-running on the same day/week overwrites the existing file.

## Troubleshooting

### Exit Codes

| Code | Meaning | Common Cause |
|------|---------|--------------|
| `0` | Success (or `--dry-run`) | — |
| `1` | Config/auth error | Missing required `.env` keys, bad IMAP credentials |
| `2` | No content found | No newsletters in IMAP window (`daily.py`), or no daily digest files found (`weekly.py`) |
| `3` | Claude CLI error | `claude` binary not found, not authenticated, or returned empty output |

### Common Errors

**`ValueError: Missing required config keys: IMAP_HOST, ...`**
Fill in the required keys in your `.env` file. See the Configuration Reference above.

**`FileNotFoundError: claude`**
Install the Claude CLI and ensure it is on your `PATH`. Run `claude --version` to confirm.

**`ConnectionRefusedError` on IMAP/SMTP**
Proton Mail Bridge is not running or not authenticated. Start Bridge and log in, then retry.

**Weekly dry-run shows 0 files**
No `digest-YYYY-MM-DD.md` files exist in `OUTPUT_DIR` within the `--since` window. Run `daily.py` at least once first to create a daily digest file.

**`weekly-YYYY-WXX.md` has wrong year**
Ensure you are running Python 3.10+. The ISO week year is computed correctly via `date.isocalendar()`.

## Running Tests

```bash
# Full test suite
.venv/bin/pytest tests/ -q
# Or with uv:
# uv run pytest tests/ -q

# Weekly rollup tests only
.venv/bin/pytest tests/test_weekly.py -q

# Stop on first failure
.venv/bin/pytest tests/ -x -q
```

Integration tests (requiring live IMAP) are gated behind `SIGNALS_INTEGRATION=1`:

```bash
SIGNALS_INTEGRATION=1 .venv/bin/pytest tests/test_fetch_integration.py -q
# Or with uv:
# SIGNALS_INTEGRATION=1 uv run pytest tests/test_fetch_integration.py -q
```
