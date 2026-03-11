# Architecture Research

**Domain:** Local email processing and summarization pipeline
**Researched:** 2026-03-11
**Confidence:** HIGH (well-established Python stdlib patterns, project constraints clearly specified)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Entry Points                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  daily.py    │  │  weekly.py   │  │  cli args    │          │
│  │  (cron)      │  │  (cron)      │  │  --dry-run   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
┌─────────▼─────────────────▼─────────────────▼───────────────────┐
│                     Pipeline Orchestrator                        │
│              (coordinates stage execution, exit codes)           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│   Fetch Stage   │  │  Sanitize Stage │  │  Summarize Stage    │
│                 │  │  (PRIVACY       │  │                     │
│  IMAP client    │  │   BOUNDARY)     │  │  claude -p via      │
│  folder filter  │  │                 │  │  subprocess.run()   │
│  time window    │  │  html→text      │  │  stdin/stdout pipe  │
│  → raw Message  │  │  strip tracking │  │  → digest text      │
│    objects      │  │  redact PII     │  └─────────────────────┘
└─────────────────┘  │  domain-only    │
                     │  sender         │
                     │  truncate body  │
                     │  → CleanMessage │
                     │    objects      │
                     └─────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│  Format Stage   │  │  Email Sender   │  │   File Writer       │
│                 │  │                 │  │                     │
│  markdown→HTML  │  │  smtplib SMTP   │  │  digests/           │
│  Jinja2 or      │  │  MIMEMultipart  │  │  YYYY-MM-DD.md      │
│  string template│  │  localhost:1025 │  │  (feeds weekly      │
│  → HTML email   │  │  STARTTLS       │  │   rollup)           │
│    body         │  └─────────────────┘  └─────────────────────┘
└─────────────────┘
```

**Weekly Rollup Path (different data source, same later stages):**

```
digests/YYYY-MM-DD.md files (last 7 days)
    ↓
Weekly Aggregator (reads markdown files, not IMAP)
    ↓
Summarize Stage → Format Stage → Email Sender + File Writer
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| Entry point scripts | Parse CLI args, configure run mode (daily/weekly/dry-run), set exit codes | Orchestrator |
| Pipeline orchestrator | Sequence stages, propagate errors, enforce dry-run short-circuit | All stages |
| IMAP client | Connect to Bridge on localhost:1143 STARTTLS, select folder, fetch by time window | Fetch stage only |
| Message parser | Decode MIME multipart, extract HTML/text parts, metadata | Sanitize stage |
| Sanitizer | HTML→text via BeautifulSoup, strip tracking params, redact PII, domain-only sender, truncate | Summarize stage input |
| Subprocess caller | Build prompt, pipe CleanMessage batch to `claude -p` via stdin, capture stdout | Summarize stage |
| Format renderer | Convert digest markdown to HTML with plain-text fallback | Email sender |
| SMTP sender | Construct MIMEMultipart, send via Bridge localhost:1025 STARTTLS | External (Bridge) |
| File writer | Write markdown digest to `digests/` with datestamped filename | Weekly aggregator |
| Weekly aggregator | Read last N daily markdown files, assemble into rollup prompt | Summarize stage |

## Recommended Project Structure

```
signals/
├── signals/                  # Main package
│   ├── __init__.py
│   ├── config.py             # Loads .env, validates settings, exposes Config dataclass
│   ├── fetch.py              # IMAP client, folder selection, time-window fetch
│   ├── sanitize.py           # HTML→text, tracking strip, PII redact, truncate
│   ├── summarize.py          # subprocess.run() wrapper for claude -p
│   ├── format.py             # Markdown→HTML, plain-text fallback construction
│   ├── send.py               # smtplib SMTP sender, MIMEMultipart construction
│   ├── store.py              # Markdown file writer and reader for weekly rollup
│   └── models.py             # RawMessage, CleanMessage dataclasses (data contracts)
├── scripts/
│   ├── daily.py              # Entry point: daily digest pipeline
│   └── weekly.py             # Entry point: weekly rollup pipeline
├── digests/                  # Output: YYYY-MM-DD.md daily digest files
├── tests/
│   ├── fixtures/             # Sample sanitized email text for offline testing
│   └── test_sanitize.py      # Sanitizer is highest-value unit test target
├── .env                      # Bridge credentials, config (never committed)
├── .env.example              # Template with all keys, no values
└── requirements.txt          # beautifulsoup4, python-dotenv (only two deps)
```

### Structure Rationale

- **signals/ package:** Enables `import signals.fetch` from tests and scripts without path games
- **models.py:** `RawMessage` and `CleanMessage` dataclasses define the contract between fetch→sanitize and sanitize→summarize; prevents leaking raw fields across the privacy boundary
- **scripts/ entry points:** Thin wrappers that handle argparse and exit codes, keeping business logic in the package
- **digests/ directory:** Flat datestamped files are the simplest rollup source; no database needed
- **tests/fixtures/:** Sanitized (not raw) email samples only — never store real email content in the repo

## Architectural Patterns

### Pattern 1: Staged Pipeline with Typed Boundaries

**What:** Each stage consumes one type and produces another. `fetch` → `RawMessage`, `sanitize` → `CleanMessage`, `summarize` → `str` (digest text). Stages only know their input and output types.

**When to use:** Any time there's a hard privacy or correctness boundary between stages. Here, `CleanMessage` is the enforced contract that the sanitizer owns.

**Trade-offs:** Slightly more upfront structure, but makes the privacy boundary testable in isolation and prevents accidental leakage of raw email fields into the prompt.

**Example:**
```python
# models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class RawMessage:
    uid: str
    subject: str           # Full subject — not passed to Claude
    sender_email: str      # Full address — not passed to Claude
    html_body: str
    text_body: Optional[str]

@dataclass
class CleanMessage:
    sender_domain: str     # domain.com only
    subject_clean: str     # subject with PII stripped
    body: str              # plain text, tracking stripped, truncated
```

### Pattern 2: subprocess.run() for Claude CLI Integration

**What:** Use `subprocess.run()` with `input=` and `capture_output=True` to pipe the full prompt+content to `claude -p` as stdin and capture stdout as the digest. Single call, no streaming needed.

**When to use:** When the LLM call is synchronous, the input fits in memory, and you want simple error handling via return code.

**Trade-offs:** `communicate()` / `run(..., input=)` avoids deadlock compared to manual Popen pipes. Timeout parameter prevents hanging if Claude CLI is slow. Cannot stream output, but digest use case doesn't require it.

**Example:**
```python
# summarize.py
import subprocess

def summarize(prompt: str, content: str, timeout: int = 120) -> str:
    full_input = f"{prompt}\n\n{content}"
    result = subprocess.run(
        ["claude", "-p", prompt],
        input=content,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr}")
    return result.stdout.strip()
```

### Pattern 3: Two-Tier URL Handling in Sanitizer

**What:** Distinguish between known tracking parameters (aggressively strip) and suspicious redirect wrappers (flag with a comment but preserve the URL). Two regex/pattern sets, separate code paths.

**When to use:** When you want privacy without breaking legitimate content links that happen to use custom redirect schemes (common in newsletters like Substack, Beehiiv).

**Trade-offs:** More complex than strip-all; requires maintaining a tracking param list and a redirect-pattern list. Worth it to preserve link utility.

**Example:**
```python
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "mc_eid", "fbclid"}
REDIRECT_PATTERNS = [r"mailchmp\.com/track/click", r"link\.hubspot\.com"]

def sanitize_url(url: str) -> tuple[str, bool]:
    """Returns (cleaned_url, is_suspicious_redirect)."""
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items()
              if k not in TRACKING_PARAMS}
    cleaned = parsed._replace(query=urlencode(params, doseq=True)).geturl()
    suspicious = any(re.search(p, url) for p in REDIRECT_PATTERNS)
    return cleaned, suspicious
```

### Pattern 4: Weekly Rollup from Markdown Files

**What:** The weekly aggregator reads the last N daily `.md` files from `digests/`, concatenates them with date headers, and pipes the assembled text to the same `summarize()` function used for daily runs. No separate weekly logic beyond file reading.

**When to use:** When daily and weekly outputs share the same summarization mechanism. Reusing `summarize()` keeps the weekly path thin and avoids duplicated prompt logic.

**Trade-offs:** Weekly prompt needs to instruct Claude to find trends across multiple days, not just summarize. Daily and weekly prompts diverge even though the mechanism is the same.

## Data Flow

### Daily Digest Flow

```
cron trigger
    ↓
daily.py (parse args: --dry-run, --since, --verbose, --prompt)
    ↓
fetch.py: imaplib STARTTLS → localhost:1143
    connect → select folder → search SINCE <date> → fetch RFC822
    → [RawMessage, ...]
    ↓
sanitize.py: for each RawMessage
    html→text (BeautifulSoup get_text())
    strip tracking params from URLs
    flag suspicious redirect URLs
    redact PII patterns (regex)
    reduce sender to domain-only
    truncate to char limit
    → [CleanMessage, ...]
    ↓
[dry-run exits here with exit code 0]
    ↓
summarize.py: build prompt + concatenated CleanMessage bodies
    subprocess.run(["claude", "-p", ...], input=content)
    → digest_text (markdown string)
    ↓
    ├── store.py: write digests/YYYY-MM-DD.md
    └── format.py: markdown → HTML + plain-text fallback
            ↓
        send.py: MIMEMultipart → smtplib → localhost:1025 STARTTLS
```

### Weekly Rollup Flow

```
cron trigger (weekly)
    ↓
weekly.py
    ↓
store.py: glob digests/*.md, sort, read last 7
    → assembled_text (concatenated daily digests with date headers)
    ↓
summarize.py: weekly trends prompt + assembled_text
    subprocess.run(["claude", "-p", ...], input=assembled_text)
    → weekly_digest_text
    ↓
    ├── store.py: write digests/YYYY-WW-weekly.md
    └── format.py → send.py (same path as daily)
```

### Key Data Flows

1. **Privacy boundary:** `RawMessage` → sanitize.py → `CleanMessage` is a one-way transformation. Nothing from `RawMessage` (full sender address, raw HTML, headers) flows past this stage.
2. **Dry-run short-circuit:** After sanitize.py produces `CleanMessage` objects, dry-run mode prints a summary and exits 0 before any subprocess or SMTP call.
3. **Error propagation:** Each stage raises typed exceptions caught by the orchestrator, which maps them to exit codes (1=config/auth, 2=no newsletters, 3=CLI error) before exiting.

## Scaling Considerations

This is a single-user local tool. Scaling is not a concern. The only relevant resource limits are:

| Concern | Reality | Mitigation |
|---------|---------|------------|
| Large newsletter volume | High-volume days may generate very long prompts | Per-message truncation limit (configurable char cap) |
| Claude CLI latency | `claude -p` may take 10-60s for large inputs | subprocess timeout parameter |
| IMAP connection reliability | Bridge may not be running | Graceful error with exit code 1, clear message |
| Disk accumulation | `digests/` grows indefinitely | Out of scope for v1; manual cleanup |

## Anti-Patterns

### Anti-Pattern 1: Mixing Raw and Clean Data

**What people do:** Pass the raw `Message` object all the way through the pipeline and let the summarizer "just use the fields it needs."

**Why it's wrong:** The privacy boundary becomes implicit and untestable. Any future refactor can accidentally pass PII to Claude. The sanitizer cannot be unit-tested in isolation.

**Do this instead:** Define `CleanMessage` as the explicit boundary. The summarizer receives only `CleanMessage` objects. The sanitizer owns the transformation and is tested independently.

### Anti-Pattern 2: Shell=True for Claude CLI Call

**What people do:** `subprocess.run(f"echo '{content}' | claude -p '{prompt}'", shell=True)`

**Why it's wrong:** Shell injection risk if email content contains single quotes or special characters. Also breaks on content longer than shell argument limits.

**Do this instead:** Use `subprocess.run(["claude", "-p", prompt], input=content, ...)` — content goes through stdin, never the shell.

### Anti-Pattern 3: Fetching All Emails Then Filtering in Python

**What people do:** Fetch all messages in the folder, then filter by date in Python.

**Why it's wrong:** Can fetch hundreds of messages over IMAP when only a handful are needed. Slow and fragile on large folders.

**Do this instead:** Use IMAP `SEARCH SINCE` criteria server-side before fetching. `imap_tools` query builder or `imaplib` `search(None, "SINCE", date_str)` reduces what crosses the wire.

### Anti-Pattern 4: Storing Raw Email Content in Test Fixtures

**What people do:** Copy real emails (with full headers, tracking pixels, PII) into `tests/fixtures/` for testing the sanitizer.

**Why it's wrong:** Real email content in a git repo is a privacy violation. Newsletter senders may have copyright concerns.

**Do this instead:** Fabricate synthetic HTML fixtures that exercise each sanitizer case (tracking params, redirect URLs, PII patterns). Sanitizer tests should never touch real email data.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Proton Mail Bridge (IMAP) | `imaplib.IMAP4` + `starttls(ssl_context)` to localhost:1143 | Bridge must be running; ssl_context with `check_hostname=False`, `CERT_NONE` for localhost self-signed cert |
| Proton Mail Bridge (SMTP) | `smtplib.SMTP` + `starttls(context=ssl_context)` to localhost:1025 | Same ssl_context approach; send-to-self only |
| Claude Code CLI | `subprocess.run(["claude", "-p", prompt], input=content, ...)` | Must be in PATH; `claude login` must have been run; exit code 0 = success |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| fetch → sanitize | `RawMessage` dataclass list | Synchronous, in-memory; no queue needed |
| sanitize → summarize | `CleanMessage` dataclass list, assembled as prompt string | Privacy boundary — CleanMessage fields are the only data Claude sees |
| summarize → format/store/send | Plain string (markdown digest) | Synchronous; format and store can both consume the same string |
| daily digests → weekly rollup | Filesystem (`digests/*.md`) | Decoupled by design; weekly reads files, not live IMAP |
| config → all stages | `Config` dataclass from `config.py` | Loaded once at startup from `.env`, passed explicitly |

## Build Order Implications

Stage dependencies dictate the implementation order. Each stage is independently testable once its input type is defined.

1. **models.py + config.py** — Define `RawMessage`, `CleanMessage`, `Config` first. No other stage can be tested without these contracts.
2. **sanitize.py** — Highest-value, most testable stage. Implement and test with synthetic fixtures before touching IMAP.
3. **fetch.py** — Requires a running Bridge. Implement after sanitize so tests can verify the full fetch→sanitize path once Bridge is available.
4. **summarize.py** — Requires Claude CLI installed and authenticated. Stub with `print(content[:200])` for dry-run testing.
5. **store.py** — Simple file I/O. Implement alongside summarize.
6. **format.py + send.py** — Implement last. Format can be tested offline; send requires Bridge SMTP.
7. **scripts/daily.py + scripts/weekly.py** — Thin wrappers assembled after all stages are stable.
8. **weekly.py aggregator** — Depends on store.py having written at least one daily file; implement and test after the full daily pipeline runs end-to-end.

## Sources

- [Python imaplib official docs](https://docs.python.org/3/library/imaplib.html) — IMAP4, IMAP4_SSL, STARTTLS
- [Python subprocess official docs](https://docs.python.org/3/library/subprocess.html) — subprocess.run(), communicate(), PIPE
- [imap-tools library](https://github.com/ikvk/imap_tools) — Higher-level IMAP wrapper with query builder
- [skeptric: Reading Email in Python with imap-tools](https://skeptric.com/python-imap/) — Practical imap-tools patterns
- [Real Python: Sending Emails With Python](https://realpython.com/python-send-email/) — smtplib MIMEMultipart patterns
- [Mailtrap: Python Send HTML Email](https://mailtrap.io/blog/python-send-html-email/) — MIMEMultipart('alternative') for HTML+text
- [Blocking unsafe resources in HTML email using BeautifulSoup](https://www.peterspython.com/en/blog/blocking-unsafe-resources-in-html-email-using-beautifulsoup) — Sanitization patterns
- [Python SSL certificate verification discussion](https://discuss.python.org/t/python-maillibs-dont-verify-server-certificates-by-default-which-is-documented-behavior-but-several-open-source-projects-failed-to-do-this-right-and-i-like-to-see-this-fixed/42313) — localhost self-signed cert handling
- [Proton Mail Bridge IMAP/SMTP configuration](https://proton.me/support/comprehensive-guide-to-bridge-settings) — Port and protocol confirmation

---
*Architecture research for: local email processing and summarization pipeline (signals)*
*Researched: 2026-03-11*
