# Project Research Summary

**Project:** Signals — Local Newsletter Digest Pipeline
**Domain:** Local Python email processing, privacy sanitization, and AI summarization pipeline
**Researched:** 2026-03-11
**Confidence:** HIGH

## Executive Summary

Signals is a local-first, privacy-preserving newsletter digest pipeline that fetches email via Proton Mail Bridge, sanitizes content before it reaches any AI system, summarizes using the Claude Code CLI subscription, and delivers an HTML digest back to the user's inbox via cron. The project sits in a well-understood Python pipeline pattern — staged processing with typed data boundaries — and the stack is almost entirely Python stdlib. Only two external runtime dependencies are required: `beautifulsoup4` for HTML parsing and `python-dotenv` for credential management. The minimal dependency surface is a feature, not a constraint, and is fully sufficient for the narrow use case.

The recommended approach is a staged pipeline with enforced typed boundaries: `RawMessage` → `CleanMessage` (sanitizer) → digest text (Claude CLI) → HTML email. The privacy boundary at the sanitizer is the central architectural decision — the sanitizer is not just a preprocessing step but the enforced contract that ensures PII, tracking infrastructure, and full sender identities never reach Claude. Building the sanitizer first, testing it in isolation with synthetic fixtures, and treating its output type (`CleanMessage`) as the ground truth for all downstream stages is the correct construction order.

The key risks are concentrated in three areas: IMAP UID handling (using sequence numbers causes wrong-message fetches and is a silent failure), subprocess pipe management (large newsletter batches deadlock if `Popen` is used instead of `subprocess.run(input=...)`), and the privacy boundary itself (headers and subject lines contain PII that must be explicitly stripped, not just the body). All three risks have clear, well-documented mitigations and should be treated as hard requirements from day one rather than refinements.

## Key Findings

### Recommended Stack

The pipeline requires Python 3.10+ and only two third-party packages at runtime. All I/O — IMAP, SMTP, file operations, subprocess — is handled by the Python standard library. `beautifulsoup4==4.14.3` handles HTML parsing and tracking pixel detection; `python-dotenv==1.2.2` manages credential loading from `.env`. Optional additions are `html2text==2025.4.15` if link-context in Claude prompts proves valuable over `get_text()`, and `jinja2==3.1.6` if the digest HTML template grows conditional logic. The Claude Code CLI is invoked via `subprocess.run()` — the Anthropic Python SDK is explicitly excluded because the project leverages an existing Pro/Max subscription, not API tokens.

**Core technologies:**
- `Python 3.10+`: runtime — required for `email.policy.default` stability and `match` statement support
- `imaplib` (stdlib): IMAP connection to Proton Mail Bridge on localhost:1143 via STARTTLS — no external dep needed for single-account use
- `email` (stdlib): MIME multipart parsing via `msg.walk()` with `email.policy.default` — handles nested multipart structures correctly
- `beautifulsoup4 4.14.3`: HTML-to-text conversion, tracking pixel detection — tolerates malformed newsletter HTML
- `smtplib` (stdlib): digest delivery via Bridge SMTP on localhost:1025 STARTTLS — single-recipient, no external dep needed
- `subprocess` (stdlib): Claude CLI integration via stdin pipe — `subprocess.run(input=content, capture_output=True)` is the correct pattern
- `python-dotenv 1.2.2`: `.env` credential loading — Bridge password, recipient address, config
- `urllib.parse` (stdlib): URL parameter stripping — `urlparse` + `parse_qs` + `urlencode` is sufficient for tracking param removal
- `ssl` (stdlib): custom `SSLContext` for Proton Bridge localhost self-signed cert

See `.planning/research/STACK.md` for full version compatibility matrix and alternatives considered.

### Expected Features

The pipeline's MVP is defined by 12 P1 features. Privacy sanitization is non-negotiable and must be complete before any Claude CLI integration — it is the pipeline's core value proposition relative to commercial alternatives. The differentiating features (theme-grouped synthesis, contradiction flagging, weekly rollup) are prompt-level additions for the first two and a post-MVP feature for the third.

**Must have (v1 — table stakes):**
- IMAP fetch with time-window filtering — without this there is no pipeline
- HTML-to-plaintext conversion — Claude requires clean text input
- Tracking pixel removal and UTM parameter stripping — non-negotiable privacy requirement
- PII redaction from body and headers — non-negotiable privacy requirement
- Domain-only sender identity — full addresses must not reach Claude
- Claude CLI summarization with theme-grouped prompt — the core value
- HTML digest email delivery via Bridge SMTP — the output mechanism
- Markdown archival of every digest — low-cost insurance, enables weekly rollup
- Dry-run mode (`--dry-run`) — required for safe development and testing
- Structured error handling with exit codes — required for cron reliability
- CLI args: `--dry-run`, `--since`, `--verbose`, `--prompt`

**Should have (v1.x — after daily pipeline is stable):**
- Weekly rollup — requires 7+ days of archived daily digests; same summarize() mechanism, different prompt
- Suspicious redirect URL flagging — more nuanced than UTM stripping; add after base URL handling is stable
- Contradiction flagging in prompt — incremental prompt enhancement, no implementation complexity
- Configurable digest length target — useful when newsletter volume spikes

**Defer (v2+):**
- RSS fallback — doubles input path complexity, separate sanitization rules
- Topic-based filtering — requires classification before summarization
- Web UI for browsing past digests — markdown files are sufficient for personal use
- Interactive Claude follow-up — different product, out of scope

See `.planning/research/FEATURES.md` for the full prioritization matrix and competitor feature comparison.

### Architecture Approach

The recommended architecture is a linear staged pipeline with typed data boundaries and a clear privacy boundary at the sanitizer. The project structure maps directly to pipeline stages: `fetch.py` → `sanitize.py` → `summarize.py` → `format.py` + `send.py` + `store.py`. Two entry-point scripts (`scripts/daily.py`, `scripts/weekly.py`) are thin argparse wrappers that coordinate stage execution and set exit codes. Data contracts are defined in `models.py` as dataclasses (`RawMessage`, `CleanMessage`), which enforce the privacy boundary at the type level and make the sanitizer independently testable. The weekly rollup path bypasses IMAP entirely and reads saved daily markdown files, decoupling it from the live pipeline.

**Major components:**
1. `models.py` — `RawMessage` and `CleanMessage` dataclasses; the typed privacy boundary contract
2. `config.py` — loads `.env`, validates settings, exposes `Config` dataclass to all stages
3. `fetch.py` — IMAP4 + STARTTLS to localhost:1143; UID-mode SEARCH SINCE + FETCH RFC822
4. `sanitize.py` — HTML→text, tracking pixel removal, URL sanitization (two-tier), PII redaction, domain-only sender, body truncation; returns only `CleanMessage` objects
5. `summarize.py` — `subprocess.run()` wrapper for `claude -p`; stdin pipe, stdout capture, timeout
6. `format.py` — markdown→HTML with inline styles; plain-text fallback
7. `send.py` — `smtplib.SMTP` + STARTTLS to localhost:1025; `MIMEMultipart('alternative')`
8. `store.py` — daily digest file writer; weekly rollup file reader (glob `digests/*.md`)
9. `scripts/daily.py`, `scripts/weekly.py` — entry points with argparse and exit codes

See `.planning/research/ARCHITECTURE.md` for the full build order, data flow diagrams, and anti-patterns.

### Critical Pitfalls

1. **IMAP sequence numbers instead of UIDs** — Always use `imap.uid('SEARCH', ...)` and `imap.uid('FETCH', ...)`. Sequence numbers are renumbered on message deletion/expunge; using them causes silent wrong-message fetches when Proton Bridge is syncing. This is a hard requirement from day one.

2. **PII leaking through email headers** — The sanitizer must strip PII from Subject, From, and all other headers — not just the body. Subject lines frequently contain the user's first name. `CleanMessage` must contain only `sender_domain` (not full address), a PII-stripped subject, and the sanitized body. Write an assertion test: the user's email address must never appear in sanitizer output.

3. **subprocess deadlock on large inputs** — Never use `Popen` with manual stdin write + stdout read. Always use `subprocess.run(input=content, capture_output=True, timeout=120)`. Newsletter batches easily exceed the 64KB OS pipe buffer. Test with maximum realistic input (10 newsletters × 5000 chars) before declaring the integration complete.

4. **Proton Bridge self-signed SSL certificate** — Python's SSL defaults reject the Bridge localhost cert. Build a custom `ssl.SSLContext` with `check_hostname=False` and `verify_mode=ssl.CERT_NONE` for localhost connections only (document the rationale), or export the Bridge TLS cert and load it as a CA bundle. This must be solved before any email can be fetched or sent.

5. **Claude CLI token limit exhaustion** — Enforce per-newsletter character truncation in the sanitizer before prompt assembly, not as an afterthought at the prompt level. Estimate token count (1 token ≈ 4 chars) before invoking Claude CLI. On heavy days, split into two invocations rather than sending an oversized prompt that silently fails.

See `.planning/research/PITFALLS.md` for the full pitfall catalog, "looks done but isn't" checklist, and recovery strategies.

## Implications for Roadmap

Based on the build order implied by architecture research and the dependency map from features research, the pipeline should be built in stages where each stage is independently testable before the next begins. The privacy boundary (sanitizer) must be fully tested before any real email data is involved.

### Phase 1: Foundation — Data Contracts and Configuration

**Rationale:** `models.py` and `config.py` must exist before any other module can be tested. All stages depend on `RawMessage`, `CleanMessage`, and `Config`. Getting these right upfront prevents refactoring mid-build.
**Delivers:** `RawMessage` and `CleanMessage` dataclasses; `Config` dataclass loaded from `.env`; `.env.example` template; project package structure (`signals/`)
**Addresses:** Architecture pattern 1 (typed boundaries); security requirement (.env never committed)
**Avoids:** Mixing raw and clean data (anti-pattern 1 from ARCHITECTURE.md); credential exposure (security mistake from PITFALLS.md)
**Research flag:** Standard patterns — skip phase research

### Phase 2: Privacy Sanitizer

**Rationale:** The sanitizer is the highest-value, most testable component and the project's core differentiator. It should be built and fully tested with synthetic fixtures before any IMAP connection exists. Testing it offline means the privacy boundary is verified before real email data is ever processed.
**Delivers:** `sanitize.py` with HTML→text conversion, tracking pixel removal, two-tier URL sanitization (strip UTM params / flag redirect wrappers), PII redaction via regex, domain-only sender reduction, body truncation, and subject stripping. Full unit test suite with synthetic HTML fixtures.
**Uses:** `beautifulsoup4`, `urllib.parse`, `re` (stdlib)
**Implements:** Sanitize stage; CleanMessage as the verified privacy boundary
**Avoids:** PII leaking through headers (Pitfall 3); URL over-stripping breaking legitimate links (Pitfall 8); raw email content in test fixtures (anti-pattern 4)
**Research flag:** Standard patterns — skip phase research

### Phase 3: IMAP Fetch

**Rationale:** IMAP requires a running Proton Mail Bridge. Build after the sanitizer so the full fetch→sanitize path can be verified end-to-end as soon as a real connection is available. IMAP is well-documented but has the UID pitfall that must be addressed explicitly.
**Delivers:** `fetch.py` with STARTTLS connection to localhost:1143, custom SSLContext, UID-mode SEARCH SINCE + RFC822 FETCH, MIME multipart walking, charset fallback chain
**Uses:** `imaplib`, `email`, `ssl`, `datetime` (all stdlib)
**Implements:** Fetch stage; RawMessage production
**Avoids:** UID vs. sequence number pitfall (Pitfall 1); Bridge SSL cert failure (Pitfall 2); multipart MIME body not found (Pitfall 6); charset decode errors (Pitfall 7); IMAP SEARCH date filter gotcha (Integration Gotchas)
**Research flag:** Needs attention — UID mode and STARTTLS setup require explicit verification against a running Bridge instance

### Phase 4: Claude CLI Integration and Prompt Engineering

**Rationale:** Once the sanitizer and IMAP fetch are working, the summarization layer completes the core value loop. The subprocess integration has specific pitfalls (deadlock, token limits) that must be tested with realistic data volumes. Prompt engineering for theme grouping is the main complexity here.
**Delivers:** `summarize.py` with stdin pipe pattern, timeout handling, exit code validation; base prompt for theme-grouped digest with cross-source synthesis; `--prompt` CLI override; per-run character count logging
**Uses:** `subprocess` (stdlib)
**Implements:** Summarize stage; the core AI value
**Avoids:** subprocess deadlock on large inputs (Pitfall 4); Claude CLI token limit exhaustion (Pitfall 5); assuming zero exit code means valid output (Integration Gotchas)
**Research flag:** Needs attention — prompt engineering for theme grouping and contradiction detection requires iterative tuning; Claude CLI behavior at token limits needs empirical testing

### Phase 5: Digest Formatting, Delivery, and Archival

**Rationale:** With sanitized content and a working summarizer, the output layer can be built. Format and send can be tested offline (format) and with Bridge SMTP (send). Archival is low-complexity but enables the weekly rollup.
**Delivers:** `format.py` with markdown→HTML using inline styles and plain-text fallback; `send.py` with MIMEMultipart('alternative') via localhost:1025 STARTTLS; `store.py` with datestamped digest file writer; digest subject line with date
**Uses:** `smtplib`, `email.mime`, `pathlib` (stdlib); optionally `jinja2` if template has loops/conditionals
**Implements:** Format stage, Email Sender, File Writer
**Avoids:** Digest HTML not rendering in Proton Mail (use inline CSS only); empty digests being sent (exit code 2 when no newsletters); subject line not indicating date
**Research flag:** Standard patterns — but verify HTML rendering in Proton Mail explicitly (known quirk with inline styles)

### Phase 6: Pipeline Assembly and CLI Entry Points

**Rationale:** All stages are independently tested. This phase assembles them into the full pipeline with proper orchestration, dry-run short-circuit, and exit code mapping. Entry point scripts are thin wrappers at this stage.
**Delivers:** `scripts/daily.py` with argparse (`--dry-run`, `--since`, `--verbose`, `--prompt`), pipeline orchestration, dry-run short-circuit after sanitizer, exit code mapping (1=config/auth, 2=no newsletters, 3=CLI error); end-to-end integration test
**Uses:** `argparse`, `logging` (stdlib)
**Implements:** Pipeline Orchestrator, Entry Points
**Avoids:** Graceful error handling gaps; dry-run conflicts with Claude call and SMTP send
**Research flag:** Standard patterns — skip phase research

### Phase 7: Weekly Rollup and Cron Setup

**Rationale:** Weekly rollup depends on 7+ days of saved daily digests. Build last, after the daily pipeline has proven reliable. Cron setup formalizes the schedule and validates exit codes work correctly in headless execution.
**Delivers:** `scripts/weekly.py` with weekly trends prompt; `store.py` glob reader for last N daily files; cron configuration for both daily and weekly runs; duplicate prevention via UID state tracking
**Uses:** `pathlib.glob` (stdlib)
**Implements:** Weekly Rollup Path; Cron scheduling
**Avoids:** Weekly digest re-summarizing same content as dailies (use trends/contradictions prompt, not re-summary); duplicate digest processing (state file)
**Research flag:** Standard patterns — but weekly prompt engineering requires testing once 7+ daily digests exist

### Phase Ordering Rationale

- Models and config first because every other module depends on them; they enable isolated unit testing
- Sanitizer before fetch because it can be tested fully offline and its correctness is the project's core privacy guarantee
- Fetch before summarizer because realistic email data is needed to validate sanitizer output quality before tuning prompts
- Summarizer before delivery because the output content determines formatting requirements
- Delivery and archival together because archival is a prerequisite for weekly rollup
- Weekly rollup last because it depends on data that only exists after the daily pipeline has run

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (IMAP Fetch):** Proton Bridge STARTTLS + self-signed cert behavior requires empirical verification against a running Bridge; UID mode implementation needs explicit testing
- **Phase 4 (Claude CLI Integration):** Prompt engineering for theme grouping needs iterative development; token limit behavior at the Pro/Max window boundaries needs empirical testing with real newsletter volumes

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Python dataclasses and dotenv are well-documented stdlib/near-stdlib patterns
- **Phase 2 (Sanitizer):** BeautifulSoup, urllib.parse, and regex patterns are well-documented; no integration dependencies
- **Phase 5 (Delivery):** smtplib MIMEMultipart is well-documented; only Proton Mail HTML rendering quirk needs empirical verification
- **Phase 6 (Assembly):** argparse and logging are stdlib; pipeline orchestration is straightforward given independently-tested stages
- **Phase 7 (Weekly Rollup):** pathlib glob and file I/O are stdlib; primary complexity is prompt engineering which extends Phase 4 work

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies are stdlib or pinned external packages verified on PyPI with release dates confirmed. Two external deps is a minimal, low-risk surface. |
| Features | MEDIUM | Commercial tool landscape surveyed via web search; core feature requirements validated against PROJECT.md. Privacy sanitization requirements are well-reasoned but exact PII redaction patterns need tuning against real newsletter samples. |
| Architecture | HIGH | Staged pipeline with typed boundaries is an established pattern for ETL/processing pipelines; project constraints (single user, local, no persistence) eliminate architectural ambiguity. Build order is derived from dependency analysis. |
| Pitfalls | HIGH (IMAP/MIME/subprocess), MEDIUM (Claude CLI specifics, Bridge edge cases) | IMAP UID, MIME multipart, and subprocess deadlock pitfalls are well-documented in Python official docs and community sources. Claude CLI token limit behavior and Proton Bridge edge cases have lower source confidence and need empirical validation. |

**Overall confidence:** HIGH

### Gaps to Address

- **PII redaction patterns:** The regex patterns for PII redaction need tuning against real newsletter samples. The right scope (email addresses, names, phone numbers?) and the right regex patterns will become clear during Phase 2 implementation. Start conservative; expand if needed.
- **Claude CLI token limit empirical behavior:** The 44K/88K token window estimates are from community sources. Actual behavior at the limit (error vs. truncation vs. timeout) needs testing with a real Pro/Max account during Phase 4.
- **Proton Bridge HTML rendering quirks:** Digest HTML must be tested in Proton Mail webmail and mobile specifically — documented quirk with inline style stripping. Verify during Phase 5.
- **Duplicate prevention state:** PITFALLS.md identifies no-deduplication as a "never acceptable" shortcut, but PROJECT.md does not specify a state file mechanism. A simple flat file recording processed UIDs is sufficient; design this during Phase 6 planning.
- **Prompt engineering:** Theme grouping, contradiction detection, and weekly trend synthesis all require iterative prompt development. These are not researchable in advance — they require empirical testing with real newsletter content.

## Sources

### Primary (HIGH confidence)
- [Python imaplib docs](https://docs.python.org/3/library/imaplib.html) — IMAP4, STARTTLS, UID commands
- [Python email.parser docs](https://docs.python.org/3/library/email.parser.html) — `email.policy.default`, `EmailMessage`, `msg.walk()`
- [Python subprocess docs](https://docs.python.org/3/library/subprocess.html) — `subprocess.run()`, deadlock warning, `communicate()`
- [Python urllib.parse docs](https://docs.python.org/3/library/urllib.parse.html) — `urlparse`/`parse_qs`/`urlencode` pattern
- [beautifulsoup4 on PyPI](https://pypi.org/project/beautifulsoup4/) — version 4.14.3 confirmed
- [python-dotenv releases on GitHub](https://github.com/theskumar/python-dotenv/releases) — version 1.2.2 confirmed
- [html2text on PyPI](https://pypi.org/project/html2text/) — version 2025.4.15 confirmed
- [Jinja2 on PyPI](https://pypi.org/project/jinja2/) — version 3.1.6 confirmed
- [IMAPClient on PyPI](https://pypi.org/project/IMAPClient/) — version 3.1.0 confirmed
- [Proton Mail Bridge IMAP/SMTP setup](https://proton.me/support/imap-smtp-and-pop3-setup) — ports 1143 (STARTTLS) and 1025 (SMTP) confirmed

### Secondary (MEDIUM confidence)
- [IMAPClient UID concepts](https://imapclient.readthedocs.io/en/2.1.0/concepts.html) — UID vs. sequence number explanation
- [Real Python: Sending Emails](https://realpython.com/python-send-email/) — smtplib MIMEMultipart patterns
- [Mailtrap: Python Send HTML Email](https://mailtrap.io/blog/python-send-html-email/) — MIMEMultipart('alternative') for HTML+text
- [Proton Bridge SSL connection issues](https://proton.me/support/bridge-ssl-connection-issue) — self-signed cert handling
- [6 Best AI Newsletter Summarizers 2026](https://www.readless.app/blog/best-ai-newsletter-summarizers) — competitor feature landscape
- [Claude Code token limits reference](https://gist.github.com/jtbr/4f99671d1cee06b44106456958caba8b) — Pro/Max window estimates
- [Idempotent pipeline patterns](https://dev.to/alexmercedcoder/idempotent-pipelines-build-once-run-safely-forever-2o2o) — deduplication approach

### Tertiary (LOW confidence — needs empirical validation)
- Claude CLI behavior at token limits — community reports; needs testing with real account
- Proton Mail inline CSS rendering — design blog guidance; needs testing with actual Bridge SMTP delivery

---
*Research completed: 2026-03-11*
*Ready for roadmap: yes*
