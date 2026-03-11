# Stack Research

**Domain:** Local Python email processing and summarization pipeline
**Researched:** 2026-03-11
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10+ | Runtime | Project constraint; 3.10 covers `match` statements, `email` policy API stability, `imaplib` STARTTLS improvements. Already decided. |
| `imaplib` (stdlib) | built-in | IMAP connection to Proton Mail Bridge | No external dependency; handles STARTTLS on port 1143; `IMAP4.starttls()` method accepts `ssl.SSLContext`. Sufficient for single-account, single-connection use case. |
| `email` (stdlib) | built-in | Parse raw RFC 2822 / MIME messages fetched via IMAP | `email.policy.default` (Python 3.3+) produces `EmailMessage` objects with `get_body()`, `iter_parts()`, `walk()`; handles multipart/alternative and multipart/related without third-party code. |
| `smtplib` (stdlib) | built-in | Send HTML digest via Proton Bridge SMTP (port 1025) | Single-recipient local SMTP; `smtplib.SMTP` with `starttls()` is the standard pattern for non-SSL SMTP. No dependency needed. |
| `beautifulsoup4` | 4.14.3 | Parse HTML email bodies; strip tracking pixels (1x1 `<img>` tags), extract text structure | Project-mandated external dep. Best-in-class for malformed HTML tolerance — newsletters routinely ship broken markup. `html.parser` backend keeps it pure-Python (no lxml install required). |
| `python-dotenv` | 1.2.2 | Load `.env` credentials (Bridge password, user email, config) | Project-mandated external dep. Industry standard for 12-factor config. No other secrets management needed for local script. |
| `subprocess` (stdlib) | built-in | Pipe sanitized text to Claude Code CLI (`claude -p`) via stdin; capture stdout | `subprocess.run()` with `input=`, `capture_output=True`, `timeout=` is the correct pattern. Avoids deadlocks that `Popen.communicate()` manages explicitly. |
| `argparse` (stdlib) | built-in | CLI flags: `--dry-run`, `--since`, `--verbose`, `--prompt` | Standard library; Python 3.9+ added `exit_on_error=False`. Sufficient for the flag surface defined in PROJECT.md. |
| `urllib.parse` (stdlib) | built-in | Strip tracking query parameters (utm_*, mc_eid, etc.) from URLs; reconstruct clean URLs | `urlparse` + `parse_qs` + `urlencode` + `urlunparse` is the canonical stdlib pattern. No regex soup needed for param-level URL manipulation. |
| `logging` (stdlib) | built-in | Structured output for `--verbose` mode; error paths | Standard library; `--verbose` sets level to DEBUG. Avoids `print()` scatter. |
| `pathlib` (stdlib) | built-in | Digest archive paths, `.env` file location, weekly markdown glob | `pathlib.Path` is the modern replacement for `os.path`; cleaner for `glob()` patterns on daily digest files. |
| `datetime` (stdlib) | built-in | `--since` window calculation; digest filename timestamps | `datetime.datetime.now(tz=timezone.utc)` avoids naive-datetime bugs when comparing IMAP `SINCE` results. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `jinja2` | 3.1.6 | Render HTML digest email from template | Use if digest HTML has conditional sections, loops over themed sections, or inline styling logic. If the HTML is a single f-string, skip it. Threshold: more than one conditional block or loop in the template. |
| `html2text` | 2025.4.15 | Convert HTML email bodies to Markdown-flavoured plain text | Use as an alternative or complement to BeautifulSoup's `get_text()` when preserving link structure in the sanitized text matters for the Claude prompt. `get_text()` strips all links; `html2text` retains `[text](url)` pairs that give Claude richer context. |
| `ssl` (stdlib) | built-in | Build `ssl.SSLContext` for Proton Bridge STARTTLS | Required by `imaplib.IMAP4.starttls()` to configure certificate verification. Proton Bridge uses a self-signed cert on localhost; set `check_hostname=False` + `verify_mode=ssl.CERT_NONE` for localhost-only connections. |
| `re` (stdlib) | built-in | Redact PII patterns (email addresses, names) from sanitized body text | Standard; compile patterns once at module level for performance. |
| `json` (stdlib) | built-in | Persist config overrides or digest metadata if needed | Only needed if config grows beyond dotenv key-value pairs. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `venv` (stdlib) | Isolated virtual environment | `python -m venv .venv` — keeps two external deps isolated. Do not use system pip. |
| `pip` | Dependency installation | `pip install beautifulsoup4==4.14.3 python-dotenv==1.2.2` — pin versions in `requirements.txt`. |
| `pytest` | Unit and integration tests | Test sanitizer module especially; mock IMAP and subprocess calls. Not a runtime dependency. |
| `black` | Code formatting | Consistent style. Not a runtime dependency. |

## Installation

```bash
# Create environment
python -m venv .venv
source .venv/bin/activate

# Runtime dependencies (only two external)
pip install beautifulsoup4==4.14.3 python-dotenv==1.2.2

# Optional: HTML-to-text with link preservation (if chosen over bs4 get_text)
pip install html2text==2025.4.15

# Optional: HTML email templating (if digest HTML grows complex)
pip install jinja2==3.1.6

# Dev dependencies
pip install pytest black
```

Freeze after installing:

```bash
pip freeze > requirements.txt
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `imaplib` (stdlib) | `IMAPClient 3.1.0` | IMAPClient provides a more Pythonic API (parsed return types, no manual response parsing) and is actively maintained. Choose it if the IMAP logic grows complex — folder introspection, CONDSTORE, QRESYNC support. For this pipeline's narrow use case (login, select folder, search SINCE, fetch RFC822), imaplib is sufficient and eliminates an external dep. |
| `beautifulsoup4` + `html.parser` | `beautifulsoup4` + `lxml` | Add lxml if parsing thousands of emails per run becomes a bottleneck. Benchmark shows lxml 10x faster than html.parser. For a daily digest of 5-50 newsletters, html.parser is fast enough and removes a C-extension dependency. |
| `subprocess.run()` | `asyncio.create_subprocess_exec` | Use asyncio variant only if the pipeline needs to run multiple Claude CLI calls concurrently. The current design is sequential (one digest call per run), so sync subprocess is simpler and safer. |
| `jinja2` (optional) | f-strings / `string.Template` | For a digest with a fixed structure, f-strings are fine and eliminate the Jinja2 dep. Use Jinja2 when the template has loops (iterating themed sections) or conditionals (hide section if empty). |
| `html2text` | `bs4.get_text()` | `get_text()` is zero-dependency and sufficient if Claude only needs paragraph text. Use `html2text` when URL context improves summarization quality — test with a sample digest to decide. |
| `argparse` (stdlib) | `click`, `typer` | Click/Typer have better DX for complex CLIs. The five flags in PROJECT.md don't justify the dependency. If the CLI surface doubles, reconsider. |
| `python-dotenv` | `os.environ` directly | Direct env vars are fine for CI/deployment contexts. python-dotenv adds `.env` file support for local dev without exporting vars manually — worth it here given the Bridge password and config. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `mailparser` / `mail-parser` (PyPI) | Third-party MIME parsers are redundant — Python's `email` stdlib handles RFC 2822 + MIME correctly since 3.6 with `email.policy.default`. Third-party parsers add a dep without solving a real gap. | `email` stdlib with `policy=email.policy.default` |
| `bleach` for HTML sanitization | Bleach is designed for HTML allowlisting in web contexts (XSS prevention). Email privacy sanitization requires different logic: stripping tracking pixels by attribute heuristics, not by tag allowlist. Bleach also strips content; the project needs to preserve body text. | `beautifulsoup4` with custom tag/attribute traversal |
| `requests` for any purpose | Nothing in this pipeline needs HTTP. All I/O is IMAP, SMTP, subprocess, and file. Adding requests for "maybe later" is scope creep. | N/A — not needed |
| `celery` / task queues | Overkill for a cron-scheduled local script. Celery adds Redis/RabbitMQ infrastructure for zero gain. | System `cron` as stated in PROJECT.md |
| `sqlalchemy` / any database | No persistence layer needed. Daily digests are markdown files. Weekly digests glob those files. A database adds migration complexity without value. | `pathlib` + filesystem |
| `openai` Python SDK or `anthropic` SDK | PROJECT.md explicitly rules out API key usage — leverages Claude Code CLI subscription via `claude -p`. Importing the Anthropic SDK would bypass this and incur API costs. | `subprocess` calling `claude -p` |
| Python 3.8 or 3.9 | `email.policy.default` is stable on 3.10+; `match` statements (optional but useful for IMAP response parsing) require 3.10+; `argparse exit_on_error` requires 3.9+. PROJECT.md specifies 3.10+. | Python 3.10+ |

## Stack Patterns by Variant

**If digest HTML is a fixed template (no loops, no conditionals):**
- Build HTML with f-strings directly in the sender module
- Skip Jinja2 dependency entirely
- Because the template never changes shape; Jinja2 adds 6MB for zero flexibility gain

**If Claude CLI output is inconsistent (variable markdown structure):**
- Add a thin post-processor that validates the Claude output has expected section headers before rendering
- Because piping raw LLM output into an HTML email without validation can produce malformed digests

**If Proton Bridge uses a self-signed certificate on localhost:**
- Build `ssl.SSLContext` with `check_hostname=False` and `verify_mode=ssl.CERT_NONE`
- Pass to `imap.starttls(ssl_context=ctx)`
- Because localhost STARTTLS with a self-signed cert will fail default SSL verification

**If weekly digest file globbing is needed:**
- Use `pathlib.Path(archive_dir).glob("digest-*.md")` + `sorted()` by filename (date-prefixed filenames sort correctly lexicographically)
- Because stdlib pathlib glob is sufficient; no `glob` module import needed

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `beautifulsoup4==4.14.3` | Python 3.7–3.13 | Uses `html.parser` (stdlib). No lxml required. `html.parser` behavior stable across 3.10–3.13. |
| `python-dotenv==1.2.2` | Python 3.8–3.13 | No known conflicts with stdlib modules used in this project. |
| `html2text==2025.4.15` | Python 3.9–3.13 | Optional. Compatible with beautifulsoup4. |
| `jinja2==3.1.6` | Python 3.7–3.13 | Optional. Compatible with all other deps. `MarkupSafe` installed automatically as dependency. |
| `imaplib` (stdlib) | Python 3.10+ | `starttls()` method available since Python 3.3. `IMAP4_SSL` alternative available but not needed for STARTTLS-on-plain-socket pattern used by Proton Bridge port 1143. |

## Sources

- [beautifulsoup4 on PyPI](https://pypi.org/project/beautifulsoup4/) — confirmed version 4.14.3, released 2025-11-30 (HIGH confidence)
- [html2text on PyPI](https://pypi.org/project/html2text/) — confirmed version 2025.4.15, released 2025-04-15 (HIGH confidence)
- [python-dotenv releases on GitHub](https://github.com/theskumar/python-dotenv/releases) — confirmed version 1.2.2, released 2026-03-01 (HIGH confidence)
- [IMAPClient on PyPI](https://pypi.org/project/IMAPClient/) — confirmed version 3.1.0, released 2026-01-17; actively maintained (HIGH confidence)
- [Jinja2 on PyPI](https://pypi.org/project/jinja2/) — confirmed version 3.1.6, released 2025-03-05 (HIGH confidence)
- [Python imaplib docs](https://docs.python.org/3/library/imaplib.html) — STARTTLS via `starttls()` method confirmed (HIGH confidence)
- [Python email.parser docs](https://docs.python.org/3/library/email.parser.html) — `email.policy.default` and `EmailMessage` API confirmed (HIGH confidence)
- [Python subprocess docs](https://docs.python.org/3/library/subprocess.html) — `subprocess.run()` with `input=`, `timeout=`, `capture_output=True` confirmed (HIGH confidence)
- [Python urllib.parse docs](https://docs.python.org/3/library/urllib.parse.html) — `urlparse`/`parse_qs`/`urlencode`/`urlunparse` pattern confirmed (HIGH confidence)
- [Proton Mail IMAP/SMTP setup](https://proton.me/support/imap-smtp-and-pop3-setup) — Bridge ports 1143 (IMAP STARTTLS) and 1025 (SMTP) confirmed (HIGH confidence)

---
*Stack research for: Local Python email digest pipeline*
*Researched: 2026-03-11*
