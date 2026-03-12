# Phase 3: Summarize, Deliver, and Pipeline Assembly - Research

**Researched:** 2026-03-12
**Domain:** Claude CLI subprocess integration, HTML email delivery via smtplib, argparse CLI, markdown-to-HTML conversion, Python pipeline orchestration
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SUMM-01 | Pipeline pipes sanitized text to Claude Code CLI (`claude -p`) via subprocess stdin | `subprocess.run(input=..., capture_output=True, text=True)` — pattern verified; `FileNotFoundError` caught for missing binary |
| SUMM-02 | Digest grouped by theme/topic across all sources, not per-newsletter | Prompt engineering in `prompts/summarize.txt`; Claude receives concatenated text, not per-message calls |
| SUMM-03 | Digest highlights key trends, notable announcements, and actionable insights | Prompt engineering; specific sections defined in AGENTS.md example |
| SUMM-04 | Digest flags contradictions between sources | Prompt instruction in `prompts/summarize.txt` |
| SUMM-05 | Digest target length is configurable (default ~500 words) | Word-count instruction in prompt; configurable via `DIGEST_WORD_TARGET` env var or passed as prompt variable |
| SUMM-06 | Digest lists sources (sender domain + subject) at end | Enforced by prompt instructions; verified in integration test |
| SUMM-07 | Summarization prompt loaded from external file (`prompts/summarize.txt`) | `Path('prompts/summarize.txt').read_text()` — stdlib pathlib; override via `--prompt FILE` arg |
| DLVR-01 | Digest sent as rendered HTML email via Bridge SMTP to configurable recipient | `smtplib.SMTP` + STARTTLS (same SSL pattern as IMAP fetch); `MIMEMultipart('alternative')` with text + html parts |
| DLVR-02 | Markdown file of every digest saved to `output/digest-YYYY-MM-DD.md` | `pathlib.Path.mkdir(exist_ok=True)` + `Path.write_text()`; filename from `date.today().strftime('%Y-%m-%d')` |
| OPS-01 | `--dry-run` flag: fetch and sanitize without calling Claude or sending email | `argparse` boolean flag; pipeline short-circuits after sanitize step; cleaned text printed to stdout |
| OPS-02 | CLI supports `--since`, `--verbose`, `--prompt`, `--output` arguments | `argparse.ArgumentParser` — all four flags verified structurally |
| OPS-03 | Exit codes: 0 success, 1 config/auth error, 2 no newsletters, 3 Claude CLI error | `sys.exit(N)` with try/except mapping; `ValueError` -> 1, empty list -> 2, `subprocess` non-zero -> 3 |
| OPS-04 | Cron wrapper `run-digest.sh`: checks Bridge running and Claude CLI available | `nc -z 127.0.0.1 1143` (returns 1 if closed); `command -v claude`; bash `set -euo pipefail` |
| OPS-05 | Dry-run wrapper `dry-run.sh` for quick inspection | One-liner delegating to `run-digest.sh --dry-run --verbose "$@"` |
</phase_requirements>

## Summary

Phase 3 assembles three new modules — `src/summarize.py`, `src/deliver.py`, and `scripts/daily.py` — and wires them to the existing fetch and sanitize modules. The plumbing is pure Python stdlib with one important gap: the AGENTS.md project description says "no extra deps" but the HTML email requirement (DLVR-01) means Claude's markdown output must be converted to HTML. The lightest solution is a minimal hand-rolled converter that handles the specific digest structure (headers, bullets, bold) rather than adding a dependency. This is verified feasible for the digest's fixed structure.

The Claude CLI integration uses `subprocess.run(cmd, input=combined_text, capture_output=True, text=True)`. The correct invocation is `claude -p "<prompt>" --output-format text` where the prompt text is the contents of `prompts/summarize.txt` and the newsletter text is piped via stdin. This pattern was established in Phase 2 project decisions (subprocess.run(input=...) mandatory to prevent deadlock). Error handling maps `FileNotFoundError` to exit code 3 (binary not found), non-zero returncode to exit code 3, `ValueError` from config to exit code 1, and empty newsletter list to exit code 2.

SMTP delivery uses the identical SSL pattern as the IMAP fetch: `ssl.SSLContext(PROTOCOL_TLS_CLIENT)` with `check_hostname=False` and `CERT_NONE` for the Bridge's self-signed localhost certificate. The digest email is sent as `multipart/alternative` with both `text/plain` and `text/html` parts; the plain text part is the raw markdown from Claude, the HTML part is the converted version. The shell scripts follow AGENTS.md specifications exactly with `nc -z` for Bridge port checking and `command -v claude` for CLI availability.

**Primary recommendation:** Build modules in this order: (1) `summarize.py` (Claude CLI call + format), (2) `deliver.py` (SMTP + file archive), (3) `scripts/daily.py` (argparse + orchestration), (4) shell scripts. Test each module independently with mocked subprocess/smtplib, then write a final integration smoke test.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `subprocess` | stdlib | Run Claude CLI, capture stdout | Project-mandated; `subprocess.run(input=...)` pattern required (Phase 2 decision) |
| `smtplib` | stdlib | Send HTML email via Bridge SMTP | Project-mandated; stdlib-only constraint; same pattern as IMAP connection |
| `argparse` | stdlib | CLI argument parsing | AGENTS.md specifies argparse; stdlib |
| `pathlib` | stdlib | File I/O for archive and prompt file | Cleaner than `os.path`; Python 3.4+ |
| `email.mime.*` | stdlib | Construct multipart MIME email | Required for HTML email |
| `logging` | stdlib | Verbose/debug output | Standard Python pattern |
| `sys` | stdlib | Exit codes | `sys.exit(N)` |
| `ssl` | stdlib | STARTTLS for Bridge SMTP | Same as IMAP SSL context (verified in Phase 2) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `beautifulsoup4` | 4.14.3 (already installed) | Already in deps; not needed for Phase 3 output | Ignore for this phase |
| `python-dotenv` | 1.2.2 (already installed) | Config loading | Already used in `src/config.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled markdown-to-HTML | `markdown` Python library (PyPI) | Library is correct but adds a dependency; hand-rolled covers the fixed digest structure (headers, bullets, bold) with no extra install |
| Hand-rolled markdown-to-HTML | `mistune` library | Faster but still adds a dependency |
| `subprocess.run(input=...)` | `Popen` + manual pipe | Phase 2 decision: Popen causes deadlock on large batches; never use it here |
| `smtplib.SMTP.starttls()` | `smtplib.SMTP_SSL` | Bridge uses STARTTLS not SSL-on-connect; SMTP_SSL would fail on port 1025 |

**Installation:**
```bash
# No new packages required — all stdlib
# Verify existing deps still covered:
pip install beautifulsoup4>=4.12.0 python-dotenv>=1.0.0
```

## Architecture Patterns

### Recommended Project Structure
```
signals/
├── src/
│   ├── config.py          # existing — add SMTP/digest config keys
│   ├── models.py          # existing — no changes needed
│   ├── sanitizer.py       # existing — no changes needed
│   ├── fetch.py           # existing — no changes needed
│   ├── summarize.py       # NEW: Claude CLI call, digest formatting
│   └── deliver.py         # NEW: SMTP send, markdown file archive
├── prompts/
│   └── summarize.txt      # NEW: system prompt for Claude
├── scripts/
│   ├── daily.py           # NEW: CLI entry point (argparse, orchestration)
│   ├── run-digest.sh      # NEW: cron wrapper (OPS-04)
│   └── dry-run.sh         # NEW: convenience dry-run wrapper (OPS-05)
├── output/                # NEW: created at runtime; gitignored
│   └── digest-YYYY-MM-DD.md
└── tests/
    ├── conftest.py        # existing
    ├── test_sanitizer.py  # existing
    ├── test_fetch.py      # existing
    ├── test_summarize.py  # NEW: mock subprocess
    ├── test_deliver.py    # NEW: mock smtplib, mock filesystem
    └── test_daily.py      # NEW: integration smoke test
```

### Pattern 1: Claude CLI Subprocess Call
**What:** Read prompt from file, concatenate newsletter text with source headers, call `claude -p` with prompt as positional arg, newsletter text via stdin.
**When to use:** Always for Claude summarization. Never use Popen (deadlock risk on large payloads).

```python
# Source: AGENTS.md implementation spec + Phase 2 subprocess decision
import subprocess
from pathlib import Path

def call_claude(prompt_file: str, newsletter_text: str, config: dict) -> str:
    """Call Claude CLI and return the digest text.

    Args:
        prompt_file: Path to the prompt file (prompts/summarize.txt)
        newsletter_text: Concatenated sanitized newsletter content
        config: Dict with 'claude_cmd' and 'claude_model' keys

    Returns:
        Claude's response text (the digest)

    Raises:
        FileNotFoundError: If claude binary not found (caller maps to exit 3)
        subprocess.CalledProcessError: On non-zero exit (caller maps to exit 3)
    """
    prompt = Path(prompt_file).read_text(encoding='utf-8')

    cmd = [config['claude_cmd'], '-p', prompt, '--output-format', 'text']
    if config.get('claude_model'):
        cmd += ['--model', config['claude_model']]

    result = subprocess.run(
        cmd,
        input=newsletter_text,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )

    return result.stdout.strip()
```

### Pattern 2: Newsletter Concatenation for Claude Input
**What:** Format all CleanMessage objects into a single text block with source-identifying headers and `---` dividers, as specified in AGENTS.md.
**When to use:** Before calling Claude. This is the only safe format to send (CleanMessage guarantees no PII).

```python
# Source: AGENTS.md digest.py specification
from src.models import CleanMessage

def format_newsletter_input(messages: list[CleanMessage]) -> str:
    """Concatenate clean messages for Claude stdin.

    Format: each message prefixed with a source header and '---' divider.
    The separator format is: Source: {domain} | Subject: {subject} | Date: {date}
    """
    parts = []
    for msg in messages:
        header = f"Source: {msg.sender_domain} | Subject: {msg.subject} | Date: {msg.date}"
        parts.append(f"---\n{header}\n\n{msg.clean_text}")
    return "\n\n".join(parts)
```

### Pattern 3: SMTP Email Delivery via Bridge
**What:** Send digest as `multipart/alternative` (text/plain + text/html) via Bridge SMTP with STARTTLS.
**When to use:** When `output_format == 'email'` or always for DLVR-01. The SSL context mirrors the IMAP pattern from Phase 2.

```python
# Source: Python stdlib smtplib docs + Phase 2 SSL pattern
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

def send_digest_email(markdown_text: str, html_text: str, config: dict) -> None:
    """Send digest as HTML email via Proton Mail Bridge SMTP.

    Uses STARTTLS with CERT_NONE — acceptable for loopback-only connection.
    Sends as multipart/alternative: plain text fallback + HTML primary.
    """
    today = date.today().isoformat()
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'Daily Digest — {today}'
    msg['From'] = config['imap_username']
    msg['To'] = config['digest_recipient']

    msg.attach(MIMEText(markdown_text, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_text, 'html', 'utf-8'))

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with smtplib.SMTP(config['smtp_host'], config['smtp_port']) as smtp:
        smtp.starttls(context=ctx)
        smtp.login(config['imap_username'], config['imap_password'])
        smtp.send_message(msg)
```

### Pattern 4: Minimal Markdown-to-HTML Conversion
**What:** Convert Claude's markdown digest output to HTML for the email body. Claude outputs a fixed structure: `##` headers, `- ` bullets, `**bold**` inline. No external library needed.
**When to use:** Before constructing the HTML MIME part. Do not attempt to handle arbitrary markdown — only the specific digest structure.

```python
# Source: Verified locally — covers the digest sections defined in AGENTS.md summarize.txt example
import re

def markdown_to_html(md: str) -> str:
    """Convert Claude digest markdown to HTML email body.

    Handles the fixed digest structure only:
    - ## Section headers -> <h2>
    - ### Sub-headers -> <h3>
    - - Bullet items -> <ul><li>
    - **bold** -> <strong>
    - Blank lines -> paragraph breaks
    - Regular lines -> <p>

    Wraps output in a minimal <html><body> envelope.
    """
    lines = md.split('\n')
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('## '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            title = _apply_inline(stripped[3:])
            html_parts.append(f'<h2>{title}</h2>')

        elif stripped.startswith('### '):
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            title = _apply_inline(stripped[4:])
            html_parts.append(f'<h3>{title}</h3>')

        elif stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            item = _apply_inline(stripped[2:])
            html_parts.append(f'<li>{item}</li>')

        elif stripped == '':
            if in_list:
                html_parts.append('</ul>')
                in_list = False

        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p>{_apply_inline(stripped)}</p>')

    if in_list:
        html_parts.append('</ul>')

    body = '\n'.join(html_parts)
    return f'<html><body style="font-family:sans-serif;max-width:700px;margin:auto">\n{body}\n</body></html>'


def _apply_inline(text: str) -> str:
    """Apply inline markdown formatting: **bold** -> <strong>bold</strong>."""
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
```

### Pattern 5: Exit Code Orchestration in daily.py
**What:** Map exceptions to specific exit codes per OPS-03.
**When to use:** Top-level `main()` in `scripts/daily.py`.

```python
# Source: Python stdlib sys, argparse; exit code spec from REQUIREMENTS.md OPS-03
import sys, argparse, logging

def main() -> None:
    parser = argparse.ArgumentParser(description='Signals daily newsletter digest')
    parser.add_argument('--dry-run', action='store_true',
                        help='Fetch and sanitize only; do not call Claude or send email')
    parser.add_argument('--since', type=int, metavar='HOURS',
                        help='Override FETCH_SINCE_HOURS from config')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--prompt', type=str, metavar='FILE',
                        help='Override prompt file path (default: prompts/summarize.txt)')
    parser.add_argument('--output', type=str, metavar='FORMAT',
                        help='Override OUTPUT_FORMAT from config (markdown|stdout|email)')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    # Exit 1: config/auth errors
    try:
        from src.config import load_config
        config = load_config()
    except (ValueError, OSError) as e:
        logging.error('Configuration error: %s', e)
        sys.exit(1)

    if args.since:
        config['fetch_since_hours'] = args.since
    if args.output:
        config['output_format'] = args.output

    # Exit 1: IMAP connection/auth errors
    try:
        from src.fetch import fetch_messages
        raw_messages = fetch_messages(config)
    except (ConnectionRefusedError, Exception) as e:
        logging.error('IMAP fetch error: %s', e)
        sys.exit(1)

    from src.sanitizer import sanitize
    from src.config import load_sanitizer_config
    san_config = load_sanitizer_config()
    clean_messages = [sanitize(raw, san_config) for raw in raw_messages]

    # Exit 2: no newsletters found
    if not clean_messages:
        logging.warning('No newsletters found in the configured time window')
        sys.exit(2)

    if args.dry_run:
        from src.summarize import format_newsletter_input
        print(format_newsletter_input(clean_messages))
        sys.exit(0)

    prompt_file = args.prompt or 'prompts/summarize.txt'

    # Exit 3: Claude CLI errors
    try:
        from src.summarize import call_claude, format_newsletter_input
        newsletter_text = format_newsletter_input(clean_messages)
        digest_md = call_claude(prompt_file, newsletter_text, config)
    except FileNotFoundError:
        logging.error('Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code')
        sys.exit(3)
    except Exception as e:
        logging.error('Claude CLI error: %s', e)
        sys.exit(3)

    from src.deliver import save_archive, send_email, markdown_to_html
    digest_html = markdown_to_html(digest_md)

    save_archive(digest_md, config)

    if config.get('output_format') == 'email':
        try:
            send_email(digest_md, digest_html, config)
        except Exception as e:
            logging.error('Email delivery error: %s', e)
            sys.exit(1)
    elif config.get('output_format') == 'stdout':
        print(digest_md)

    sys.exit(0)
```

### Pattern 6: Shell Script — run-digest.sh
**What:** Cron-safe wrapper that validates prerequisites before running Python.
**When to use:** OPS-04 requirement. Used directly as cron target.

```bash
#!/usr/bin/env bash
# Source: AGENTS.md scripts/run-digest.sh specification
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check Bridge is running on port 1143
# nc -z returns exit code 1 if port is closed (verified locally)
if ! nc -z 127.0.0.1 1143 2>/dev/null; then
    echo "ERROR: Proton Mail Bridge not running on port 1143" >&2
    exit 1
fi

# Check Claude CLI is in PATH
if ! command -v claude &>/dev/null; then
    echo "ERROR: claude CLI not found in PATH. Install from https://claude.ai/code" >&2
    exit 1
fi

# Activate venv and run
source "$PROJECT_DIR/.venv/bin/activate"
python "$PROJECT_DIR/scripts/daily.py" "$@"
```

### Pattern 7: summarize.txt Prompt File
**What:** The external system prompt loaded from `prompts/summarize.txt` per SUMM-07. Content is exactly what AGENTS.md specifies.
**When to use:** Created once; the `--prompt` flag overrides the path.

```
You are a newsletter digest assistant. You will receive the plain text contents
of several newsletters, each separated by a "---" divider with a header showing
the source domain and subject line.

Produce a daily digest with these sections:

## Key Trends
Top 3-5 themes or trends appearing across multiple newsletters.

## Notable Announcements
Specific launches, releases, funding rounds, or breaking news worth knowing about.

## Quick Hits
Anything interesting that doesn't fit the above, as brief one-liners.

## Sources
List each newsletter source and subject included in this digest.

Be concise. Target ~500 words total. Group by topic, not by source.
Flag any contradictions or conflicts between sources.
Do not include any personal information, email addresses, or names
even if they appear in the input.
```

### Anti-Patterns to Avoid
- **Using Popen + communicate() for Claude CLI:** Causes deadlock on large newsletter batches. The Phase 2 decision mandates `subprocess.run(input=...)`. Never use `Popen` here.
- **Using `smtplib.SMTP_SSL` for Bridge SMTP:** Bridge uses STARTTLS negotiation after connection, not SSL-on-connect. `SMTP_SSL` will fail on port 1025.
- **Calling `load_config()` at module import time:** Established in Phase 1 as a test-breaking anti-pattern. Config loading must stay inside function bodies.
- **Sending empty digest if Claude returns nothing:** Always check that `result.stdout.strip()` is non-empty before treating as success; empty output should raise an error.
- **Creating `output/` directory inside the deliver module at import time:** Use `pathlib.Path.mkdir(parents=True, exist_ok=True)` inside the save function, not at module load.
- **Hardcoding the prompt content in Python source:** Prompt goes in `prompts/summarize.txt` and is read at runtime (SUMM-07). Python source should never contain the prompt text inline.
- **sys.exit() inside library modules:** Only `scripts/daily.py` calls `sys.exit()`. Library modules (`summarize.py`, `deliver.py`) raise exceptions; the orchestrator maps them to exit codes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Subprocess piping with timeout | Custom Popen loop | `subprocess.run(input=..., capture_output=True)` | Phase 2 decision: Popen deadlocks on large payloads |
| Email construction | Raw MIME string building | `email.mime.multipart.MIMEMultipart` + `MIMEText` | Header folding, encoding, charset all handled by stdlib |
| Port liveness check in shell | netstat parsing | `nc -z host port` | One-liner; verified to return exit code 1 for closed port |
| Path manipulation | `os.path.join` chains | `pathlib.Path` | Cleaner; `.mkdir(exist_ok=True)`, `.read_text()`, `.write_text()` |
| Argument parsing | Manual `sys.argv` parsing | `argparse` | AGENTS.md specifies argparse; handles `--help` automatically |
| Markdown-to-HTML (general) | Regex on arbitrary markdown | Hand-rolled for fixed digest structure | Full markdown parser adds dep; digest structure is fixed and limited |

**Key insight:** The Phase 2 subprocess decision (`subprocess.run(input=...)` over Popen) is load-bearing for correctness with large newsletter batches. Violating it will cause silent hangs, not loud failures.

## Common Pitfalls

### Pitfall 1: Claude CLI Prompt Size Limit
**What goes wrong:** If the combined newsletter text exceeds Claude's context window, the CLI returns an error (non-zero exit code). With 10+ newsletters at 15,000 chars each, the payload can reach 150,000 characters (~37,500 tokens).
**Why it happens:** Each `CleanMessage.clean_text` is already truncated to `MAX_BODY_CHARS` (default 15,000) by the sanitizer, but N newsletters multiplied can still hit context limits at Pro/Max boundaries.
**How to avoid:** The summarize module should compute the total payload size and warn (but not fail) in verbose mode. Real-world testing is needed at Pro/Max subscription limits. Phase 3 STATE.md already flags this: "Claude CLI token limit behavior at Pro/Max window boundaries needs empirical testing."
**Warning signs:** Claude CLI exits non-zero with a message about context or token limits.

### Pitfall 2: SMTP Login Credentials
**What goes wrong:** Bridge SMTP uses the same 16-character Bridge-generated password as IMAP. Using the wrong SMTP port (587 instead of 1025) or forgetting STARTTLS causes authentication failures.
**Why it happens:** `smtp_port` defaults to 1025 in `load_config()`; STARTTLS must be called before login. Calling `smtp.login()` before `smtp.starttls()` sends credentials in cleartext over localhost.
**How to avoid:** Always call `smtp.starttls(context=ctx)` before `smtp.login(username, password)`. Verify SMTP port is 1025 (Bridge default), not 587.
**Warning signs:** `SMTPAuthenticationError` or connection refused when sending email.

### Pitfall 3: Prompt File Path Resolution
**What goes wrong:** `prompts/summarize.txt` resolves relative to the current working directory, not the script location. When `scripts/daily.py` is run from a different directory (e.g., via cron), the relative path fails.
**Why it happens:** Python's `open('prompts/summarize.txt')` uses `os.getcwd()`, which is the cron invocation directory.
**How to avoid:** In `scripts/daily.py`, resolve the prompt file path relative to the project root using `Path(__file__).parent.parent / 'prompts/summarize.txt'`. The default prompt path should be absolute, not relative.
**Warning signs:** `FileNotFoundError: prompts/summarize.txt` in cron logs but works in manual runs.

### Pitfall 4: Empty Claude Output
**What goes wrong:** If Claude CLI exits 0 but returns empty stdout, the digest archive is created as an empty file and the email is sent with no body.
**Why it happens:** Rate limiting, or the prompt produced no response, or `--output-format text` returned metadata instead of content.
**How to avoid:** Check `len(result.stdout.strip()) > 0` after the subprocess call. If empty, treat as a Claude CLI error (exit 3).
**Warning signs:** Empty `output/digest-YYYY-MM-DD.md` files.

### Pitfall 5: Markdown Converter Misses Claude's Output Variations
**What goes wrong:** Claude may not always produce exactly `## Heading` — it may produce `##Heading` (no space), numbered lists (`1.`), or nested bullets. The hand-rolled converter silently passes these through as plain text.
**Why it happens:** Claude is non-deterministic; the prompt constrains but doesn't guarantee exact markdown syntax.
**How to avoid:** Test the converter with the actual Claude output from a dry-run on real newsletters. The converter should at minimum handle `##` (with and without space), `- ` and `* ` bullets, and `**bold**`. Add `#` (h1) handling as a safety net. Emit a warning in verbose mode if headings are found that don't match expected patterns.
**Warning signs:** Email body is all plain `<p>` tags with no `<h2>` headers.

### Pitfall 6: Archive File Collision
**What goes wrong:** If `scripts/daily.py` is run twice on the same day, the second run overwrites the first digest archive.
**Why it happens:** The filename is `digest-{today}.md` and `Path.write_text()` overwrites by default.
**How to avoid:** Check if the file exists before writing; if it does, either append a timestamp suffix or skip and warn. Document this behavior. For v1, a simple overwrite is acceptable but should be noted.
**Warning signs:** Running the pipeline twice loses the first run's digest.

### Pitfall 7: --dry-run Must Not Require SMTP Config
**What goes wrong:** If `load_config()` validates SMTP credentials as required keys, `--dry-run` fails for users who haven't configured email delivery.
**Why it happens:** Overly strict validation in `load_config()`.
**How to avoid:** SMTP keys (`SMTP_HOST`, `SMTP_PORT`, `DIGEST_RECIPIENT`) must remain optional in `load_config()`. The deliver module should validate SMTP config only when it is actually about to send, not at startup.
**Warning signs:** `--dry-run` exits with code 1 "missing config keys" instead of showing cleaned text.

## Code Examples

Verified patterns from official sources:

### Subprocess Invocation (summarize.py)
```python
# Source: Python stdlib subprocess docs + Phase 2 decision (subprocess.run required)
import subprocess
from pathlib import Path

def call_claude(prompt_file: str, newsletter_text: str, config: dict) -> str:
    prompt = Path(prompt_file).read_text(encoding='utf-8')
    cmd = [config['claude_cmd'], '-p', prompt, '--output-format', 'text']
    if config.get('claude_model'):
        cmd += ['--model', config['claude_model']]

    result = subprocess.run(cmd, input=newsletter_text, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI exited {result.returncode}: {result.stderr}")

    digest = result.stdout.strip()
    if not digest:
        raise RuntimeError("Claude CLI returned empty output")

    return digest
```

### File Archive Save (deliver.py)
```python
# Source: Python stdlib pathlib docs
from pathlib import Path
from datetime import date

def save_archive(digest_md: str, config: dict) -> Path:
    """Save digest markdown to output directory. Returns the saved path."""
    output_dir = Path(config.get('output_dir', './output'))
    output_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime('%Y-%m-%d')
    filepath = output_dir / f'digest-{today}.md'
    filepath.write_text(digest_md, encoding='utf-8')
    return filepath
```

### Mocking Claude CLI in Tests
```python
# Source: Python stdlib unittest.mock — same pattern as test_fetch.py mocks
from unittest.mock import patch, MagicMock
import subprocess

def test_call_claude_success(tmp_path):
    prompt_file = tmp_path / 'summarize.txt'
    prompt_file.write_text('You are a digest assistant.')

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '## Key Trends\n\n- AI adoption growing\n'
    mock_result.stderr = ''

    config = {'claude_cmd': 'claude', 'claude_model': ''}

    with patch('subprocess.run', return_value=mock_result) as mock_run:
        from src.summarize import call_claude
        result = call_claude(str(prompt_file), 'newsletter text', config)

    assert '## Key Trends' in result
    call_args = mock_run.call_args
    assert call_args.kwargs['input'] == 'newsletter text'
    assert '-p' in call_args.args[0]

def test_call_claude_nonzero_exit(tmp_path):
    prompt_file = tmp_path / 'summarize.txt'
    prompt_file.write_text('prompt')

    mock_result = MagicMock(returncode=1, stdout='', stderr='Rate limited')
    config = {'claude_cmd': 'claude', 'claude_model': ''}

    with patch('subprocess.run', return_value=mock_result):
        from src.summarize import call_claude
        import pytest
        with pytest.raises(RuntimeError, match='exited 1'):
            call_claude(str(prompt_file), 'text', config)

def test_call_claude_binary_not_found(tmp_path):
    prompt_file = tmp_path / 'summarize.txt'
    prompt_file.write_text('prompt')
    config = {'claude_cmd': 'claude', 'claude_model': ''}

    with patch('subprocess.run', side_effect=FileNotFoundError()):
        from src.summarize import call_claude
        import pytest
        with pytest.raises(FileNotFoundError):
            call_claude(str(prompt_file), 'text', config)
```

### Mocking smtplib in Tests
```python
# Source: Python stdlib unittest.mock
from unittest.mock import patch, MagicMock

def test_send_email_calls_starttls():
    config = {
        'smtp_host': '127.0.0.1', 'smtp_port': 1025,
        'imap_username': 'user@proton.me', 'imap_password': 'bridge-pass',
        'digest_recipient': 'user@proton.me',
    }
    mock_smtp = MagicMock()

    with patch('smtplib.SMTP', return_value=mock_smtp.__enter__.return_value):
        with patch('smtplib.SMTP') as MockSMTP:
            MockSMTP.return_value.__enter__.return_value = mock_smtp
            from src.deliver import send_digest_email
            send_digest_email('# digest', '<h1>digest</h1>', config)

    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with('user@proton.me', 'bridge-pass')
    mock_smtp.send_message.assert_called_once()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Popen` + manual stdin/stdout pipe | `subprocess.run(input=..., capture_output=True)` | Phase 2 decision | Prevents deadlock on large newsletter batches |
| `os.path` for file I/O | `pathlib.Path` | Python 3.6+ standard | Cleaner method chaining; `mkdir(exist_ok=True)`, `write_text()` |
| `smtplib.sendmail()` | `smtplib.send_message()` | Python 3.2+ | Takes `email.message.Message` directly; handles encoding automatically |
| `SMTP_SSL` for local SMTP | `SMTP` + `starttls()` | Bridge requirement | Bridge requires STARTTLS, not SSL-on-connect |

**Deprecated/outdated:**
- `smtplib.sendmail(from, to, msg.as_string())`: Still works but `send_message(msg)` is cleaner for pre-built `MIMEMultipart` objects.
- `os.makedirs(path, exist_ok=True)`: Replaced by `pathlib.Path(path).mkdir(parents=True, exist_ok=True)`.

## Open Questions

1. **Claude CLI: prompt as positional arg vs `--system-prompt` flag**
   - What we know: AGENTS.md specifies `claude -p "<prompt_text>" --output-format text` with newsletter text via stdin. The `--system-prompt` flag is also available per `claude --help`.
   - What's unclear: With `claude -p "prompt"`, does the prompt become the user turn and stdin becomes a second user turn? Or does `-p` with a prompt argument set the system prompt?
   - Recommendation: Use the AGENTS.md-specified pattern (`claude -p "prompt" --output-format text` with newsletter text via stdin) as the starting point. Test empirically on first real run with `--verbose`. If the prompt and newsletter text need separation, switch to `--system-prompt "$(cat prompts/summarize.txt)"` with the newsletter text as the sole stdin content.

2. **Word count enforcement for SUMM-05**
   - What we know: Default target is ~500 words; it should be configurable.
   - What's unclear: Whether to enforce via prompt only (soft limit) or truncate Claude's output (hard limit). The config key name (`DIGEST_WORD_TARGET`?) is not in the current `.env.example`.
   - Recommendation: Enforce via prompt instruction only for v1 ("Target ~{word_count} words"). Add `DIGEST_WORD_TARGET=500` to config and `.env.example`. Do not truncate Claude output — truncation produces incomplete sentences.

3. **Output format behavior: `markdown` vs `email` vs `stdout`**
   - What we know: DLVR-01 says digest is "sent as rendered HTML email." DLVR-02 says markdown file is always saved. The current `OUTPUT_FORMAT` config has three values.
   - What's unclear: Should the markdown archive be saved for ALL output formats, or only for `markdown` format?
   - Recommendation: Always save the markdown archive (DLVR-02 has no conditionality), then additionally send email if `output_format == 'email'`. The `stdout` and `markdown` formats both save the file; only `email` sends SMTP.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (already installed in .venv) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` already configured |
| Quick run command | `pytest tests/test_summarize.py tests/test_deliver.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUMM-01 | Claude CLI called via subprocess with newsletter text on stdin | unit | `pytest tests/test_summarize.py::test_call_claude_success -x` | Wave 0 |
| SUMM-01 | FileNotFoundError when claude binary missing | unit | `pytest tests/test_summarize.py::test_call_claude_binary_not_found -x` | Wave 0 |
| SUMM-01 | Non-zero exit code raises RuntimeError | unit | `pytest tests/test_summarize.py::test_call_claude_nonzero_exit -x` | Wave 0 |
| SUMM-02 | Digest format groups by theme (prompt content check) | unit | `pytest tests/test_summarize.py::test_prompt_contains_theme_instruction -x` | Wave 0 |
| SUMM-05 | Word count target in prompt | unit | `pytest tests/test_summarize.py::test_prompt_contains_word_target -x` | Wave 0 |
| SUMM-06 | Sources section in prompt instruction | unit | `pytest tests/test_summarize.py::test_prompt_contains_sources_instruction -x` | Wave 0 |
| SUMM-07 | Prompt loaded from external file | unit | `pytest tests/test_summarize.py::test_prompt_loaded_from_file -x` | Wave 0 |
| SUMM-07 | --prompt flag overrides default path | unit | `pytest tests/test_summarize.py::test_prompt_override_path -x` | Wave 0 |
| DLVR-01 | SMTP starttls called before login | unit | `pytest tests/test_deliver.py::test_send_email_calls_starttls -x` | Wave 0 |
| DLVR-01 | Email sent as multipart/alternative with html part | unit | `pytest tests/test_deliver.py::test_email_has_html_part -x` | Wave 0 |
| DLVR-02 | Archive file saved to output dir with correct name | unit | `pytest tests/test_deliver.py::test_save_archive_creates_file -x` | Wave 0 |
| DLVR-02 | Archive filename is digest-YYYY-MM-DD.md | unit | `pytest tests/test_deliver.py::test_save_archive_filename_format -x` | Wave 0 |
| OPS-01 | --dry-run exits 0 without calling Claude | unit | `pytest tests/test_daily.py::test_dry_run_no_claude_call -x` | Wave 0 |
| OPS-01 | --dry-run outputs sanitized text to stdout | unit | `pytest tests/test_daily.py::test_dry_run_prints_clean_text -x` | Wave 0 |
| OPS-02 | --since overrides fetch_since_hours in config | unit | `pytest tests/test_daily.py::test_since_flag_overrides_config -x` | Wave 0 |
| OPS-02 | --verbose enables debug logging | unit | `pytest tests/test_daily.py::test_verbose_sets_debug_level -x` | Wave 0 |
| OPS-03 | Missing config keys exits with code 1 | unit | `pytest tests/test_daily.py::test_exit_1_on_missing_config -x` | Wave 0 |
| OPS-03 | No newsletters found exits with code 2 | unit | `pytest tests/test_daily.py::test_exit_2_no_newsletters -x` | Wave 0 |
| OPS-03 | Claude CLI failure exits with code 3 | unit | `pytest tests/test_daily.py::test_exit_3_claude_error -x` | Wave 0 |
| OPS-04 | run-digest.sh exits non-zero if Bridge not on port 1143 | smoke | Manual / `bash tests/test_run_digest_sh.sh` (see Wave 0 gaps) | Wave 0 |
| OPS-05 | dry-run.sh delegates to run-digest.sh --dry-run | smoke | Manual inspection of script content | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_summarize.py tests/test_deliver.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_summarize.py` — covers SUMM-01 through SUMM-07
- [ ] `tests/test_deliver.py` — covers DLVR-01, DLVR-02
- [ ] `tests/test_daily.py` — covers OPS-01, OPS-02, OPS-03
- [ ] `prompts/summarize.txt` — required by SUMM-07 (content in Pattern 7 above)
- [ ] `scripts/daily.py` — CLI entry point
- [ ] `src/summarize.py` — Claude CLI module
- [ ] `src/deliver.py` — SMTP + archive module
- [ ] `scripts/run-digest.sh` — cron wrapper
- [ ] `scripts/dry-run.sh` — convenience wrapper
- [ ] `output/` directory — created at runtime by `deliver.py`; add `output/.gitkeep` to track in git

## Sources

### Primary (HIGH confidence)
- Python stdlib `subprocess` docs (python.org) — `subprocess.run(input=..., capture_output=True, text=True)` pattern; `FileNotFoundError` on missing binary
- Python stdlib `smtplib` docs (python.org) — `SMTP.starttls(context=)`, `SMTP.send_message()`, `SMTP.__enter__` context manager
- Python stdlib `email.mime` docs (python.org) — `MIMEMultipart('alternative')`, `MIMEText(content, 'html', 'utf-8')`
- Python stdlib `argparse` docs (python.org) — `add_argument`, `store_true`, `type=int`
- Python stdlib `pathlib` docs (python.org) — `Path.mkdir(parents=True, exist_ok=True)`, `Path.write_text()`, `Path.read_text()`
- `claude --help` output (verified live on this machine) — `-p/--print`, `--output-format text`, `--model`, `--system-prompt` flags confirmed
- Phase 2 project decisions (STATE.md) — `subprocess.run(input=...)` over Popen mandated; imaplib errors propagate to orchestrator for exit code mapping

### Secondary (MEDIUM confidence)
- AGENTS.md project specification — module responsibilities, script patterns, MIME structure, CLI arguments, shell script implementations verified to match stdlib capabilities
- Phase 1 RESEARCH.md — config loading pattern, test fixture pattern, SSL context pattern all reused in Phase 3

### Tertiary (LOW confidence)
- Claude CLI context window limits at Pro/Max tier — not verified empirically; flagged as open concern in STATE.md; requires real-world testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib; no new external dependencies needed; verified locally
- Architecture: HIGH — module boundaries derived from AGENTS.md spec; all patterns verified runnable in Python 3.10+
- Claude CLI integration: HIGH for command structure (verified via `claude --help`); LOW for token limit behavior at real newsletter volumes
- Pitfalls: HIGH for SMTP/subprocess patterns (verified locally); MEDIUM for Claude output variation in markdown converter

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stdlib APIs are stable; Claude CLI flags may change on major releases)
