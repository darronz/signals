# Newsletter Digest Pipeline

## What This Is

A local Python pipeline that fetches newsletter emails from Proton Mail via Bridge IMAP, sanitizes them for privacy, and summarizes them through Claude Code CLI into a themed daily digest delivered back to the user's inbox as a rendered HTML email. Weekly digests roll up the daily outputs into higher-level trends. Everything runs locally — the only external call is the Claude Code CLI summarization using an existing Pro/Max subscription.

## Core Value

A single skimmable email each morning that distills all newsletter content into themed insights — so the user stays informed without reading everything.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Connect to Proton Mail Bridge via localhost IMAP (STARTTLS, port 1143) — v1.0
- ✓ Fetch newsletters by folder (preferred) or sender list (fallback) — v1.0
- ✓ Fetch only messages within a configurable time window (default 24h) — v1.0
- ✓ Convert HTML email bodies to clean plain text — v1.0
- ✓ Strip tracking pixels, known tracking parameters (utm_*, mc_eid, etc.) — v1.0
- ✓ Redact user email address, name, and other PII from body text — v1.0
- ✓ Support configurable extra PII redaction patterns — v1.0
- ✓ Reduce sender identity to domain-only before passing to Claude — v1.0
- ✓ Truncate individual newsletter bodies to a configurable character limit — v1.0
- ✓ Pipe cleaned text to Claude Code CLI (`claude -p`) for summarization — v1.0
- ✓ Group digest by theme/topic, not by individual newsletter source — v1.0
- ✓ Configurable digest target length (default ~500 words) — v1.0
- ✓ Highlight key trends, notable announcements, and actionable insights — v1.0
- ✓ Flag contradictions between sources — v1.0
- ✓ List sources (sender domain + subject) at end of digest — v1.0
- ✓ Send digest as rendered HTML email back to self via Bridge SMTP — v1.0
- ✓ Save markdown file of every digest for archival — v1.0
- ✓ Weekly digest that re-summarizes daily digest files into trends — v1.0
- ✓ Schedule via cron (daily at a set time, weekly on a set day) — v1.0
- ✓ Dry-run mode: fetch and sanitize without calling Claude — v1.0
- ✓ CLI arguments: --dry-run, --since, --verbose, --prompt — v1.0
- ✓ Clear exit codes (0 success, 1 config/auth error, 2 no newsletters, 3 CLI error) — v1.0
- ✓ Graceful error handling for connection failures, auth errors, empty results — v1.0

### Active

<!-- Current scope. Building toward these. -->

(None yet — define in next milestone)

### Out of Scope

- RSS fallback for newsletters with feeds — future extension
- Topic-based filtering (only summarize certain categories) — future extension
- Web UI dashboard for browsing past digests — future extension
- Interactive Claude Code skill for follow-up questions — future extension
- Mobile app — web/email-first
- OAuth or third-party email providers — Proton Mail only
- API key usage — leverages existing Claude Code CLI subscription
- Flag suspicious redirect/tracking URLs — deferred from v1.0 (conservative: all img tags removed instead)
- `SMTP_SECURITY` config flexibility — v1.0 hard-wires STARTTLS (sufficient for Bridge)

## Context

Shipped v1.0 with 3,652 LOC Python across 77 files.
Tech stack: Python 3.10+, beautifulsoup4, python-dotenv, stdlib for everything else.
Test suite: 101 tests (3 skipped: opt-in IMAP integration requiring live Bridge).
Daily and weekly pipelines verified end-to-end with live Proton Mail Bridge.

- Proton Mail Bridge exposes IMAP on 127.0.0.1:1143 with STARTTLS and a 16-character Bridge-generated password
- SMTP available on 127.0.0.1:1025 for sending digest emails back to self
- Claude Code CLI (`claude -p`) accepts a prompt and stdin, outputs to stdout — no API key needed
- The sanitizer module is the privacy boundary — nothing upstream of it should reach Claude
- Daily digests are the primary artifact; weekly digests aggregate from saved daily markdown files
- Target user experience: one HTML email in inbox each morning, skimmable over coffee

## Constraints

- **Privacy**: Email headers, user PII, and non-newsletter content must never reach Claude
- **Local-only**: No cloud services, external APIs, or data leaving the machine (except Claude CLI calls)
- **Proton Mail Bridge**: Must be installed, running, and authenticated as a prerequisite
- **Claude Code CLI**: Must be installed and authenticated (`claude login`) as a prerequisite
- **Minimal dependencies**: Prefer stdlib; only beautifulsoup4 and python-dotenv as external packages

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Claude Code CLI over API | Uses existing Pro/Max subscription, no API key management | ✓ Good — zero API cost, works reliably |
| Domain-only sender identity | Privacy — full email addresses are PII | ✓ Good — clean privacy boundary |
| Theme-grouped digest | User wants cross-source insight, not per-newsletter summaries | ✓ Good — core differentiator |
| HTML email as primary output | Skimmable in inbox, matches daily workflow | ✓ Good — natural delivery channel |
| Email + file always | File output feeds weekly roll-up aggregation | ✓ Good — enables weekly pipeline |
| Remove all img tags (conservative) | Safer than size-based tracking pixel detection | ✓ Good — no false negatives |
| Configurable digest length | Different days have different volumes; user controls density | ✓ Good — DIGEST_WORD_TARGET wired to prompt |
| dataclasses over pydantic | Sufficient for typed contracts without extra dependency | ✓ Good — minimal dependencies maintained |
| subprocess.run over Popen | Popen + manual pipe causes deadlock on large batches | ✓ Good — reliable Claude CLI integration |
| UID-mode-only IMAP | Sequence numbers cause silent wrong-message fetches | ✓ Good — correct even with concurrent mailbox changes |
| Client-side sender filter | Simpler than server-side SEARCH FROM for multi-sender lists | ✓ Good — Newsletters folder volume is small |
| str.format for prompt substitution | Keyword-only avoids positional conflicts; safe for prompts without other braces | ✓ Good — simple and effective |

---
*Last updated: 2026-03-12 after v1.0 milestone*
