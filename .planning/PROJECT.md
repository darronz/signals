# Newsletter Digest Pipeline

## What This Is

A local Python pipeline that fetches newsletter emails from Proton Mail via Bridge IMAP, sanitizes them for privacy, and summarizes them through Claude Code CLI into a themed daily digest delivered back to the user's inbox as a rendered HTML email. Weekly digests roll up the daily outputs into higher-level trends. Everything runs locally — the only external call is the Claude Code CLI summarization using an existing Pro/Max subscription.

## Core Value

A single skimmable email each morning that distills all newsletter content into themed insights — so the user stays informed without reading everything.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Connect to Proton Mail Bridge via localhost IMAP (STARTTLS, port 1143)
- [ ] Fetch newsletters by folder (preferred) or sender list (fallback)
- [ ] Fetch only messages within a configurable time window (default 24h)
- [ ] Convert HTML email bodies to clean plain text
- [ ] Strip tracking pixels, known tracking parameters (utm_*, mc_eid, etc.)
- [ ] Flag suspicious redirect/tracking URLs without removing them
- [ ] Preserve useful content URLs with tracking params stripped
- [ ] Redact user email address, name, and other PII from body text
- [ ] Support configurable extra PII redaction patterns
- [ ] Reduce sender identity to domain-only before passing to Claude
- [ ] Truncate individual newsletter bodies to a configurable character limit
- [ ] Pipe cleaned text to Claude Code CLI (`claude -p`) for summarization
- [ ] Group digest by theme/topic, not by individual newsletter source
- [ ] Configurable digest target length (default ~500 words)
- [ ] Highlight key trends, notable announcements, and actionable insights
- [ ] Flag contradictions between sources
- [ ] List sources (sender domain + subject) at end of digest
- [ ] Send digest as rendered HTML email back to self via Bridge SMTP
- [ ] Save markdown file of every digest for archival
- [ ] Weekly digest that re-summarizes daily digest files into trends
- [ ] Schedule via cron (daily at a set time, weekly on a set day)
- [ ] Dry-run mode: fetch and sanitize without calling Claude
- [ ] CLI arguments: --dry-run, --since, --verbose, --prompt
- [ ] Clear exit codes (0 success, 1 config/auth error, 2 no newsletters, 3 CLI error)
- [ ] Graceful error handling for connection failures, auth errors, empty results

### Out of Scope

- RSS fallback for newsletters with feeds — future extension
- Topic-based filtering (only summarize certain categories) — future extension
- Web UI dashboard for browsing past digests — future extension
- Interactive Claude Code skill for follow-up questions — future extension
- Mobile app — web/email-first
- OAuth or third-party email providers — Proton Mail only
- API key usage — leverages existing Claude Code CLI subscription

## Context

- Proton Mail Bridge exposes IMAP on 127.0.0.1:1143 with STARTTLS and a 16-character Bridge-generated password
- SMTP available on 127.0.0.1:1025 for sending digest emails back to self
- Claude Code CLI (`claude -p`) accepts a prompt and stdin, outputs to stdout — no API key needed
- The sanitizer module is the privacy boundary — nothing upstream of it should reach Claude
- URL sanitization has two tiers: strip known tracking params aggressively, flag suspicious redirect wrappers for review
- Daily digests are the primary artifact; weekly digests aggregate from saved daily markdown files
- Target user experience: one HTML email in inbox each morning, skimmable over coffee
- Python 3.10+ with minimal dependencies (beautifulsoup4, python-dotenv, stdlib for everything else)

## Constraints

- **Privacy**: Email headers, user PII, and non-newsletter content must never reach Claude
- **Local-only**: No cloud services, external APIs, or data leaving the machine (except Claude CLI calls)
- **Proton Mail Bridge**: Must be installed, running, and authenticated as a prerequisite
- **Claude Code CLI**: Must be installed and authenticated (`claude login`) as a prerequisite
- **Minimal dependencies**: Prefer stdlib; only beautifulsoup4 and python-dotenv as external packages

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Claude Code CLI over API | Uses existing Pro/Max subscription, no API key management | — Pending |
| Domain-only sender identity | Privacy — full email addresses are PII | — Pending |
| Theme-grouped digest | User wants cross-source insight, not per-newsletter summaries | — Pending |
| HTML email as primary output | Skimmable in inbox, matches daily workflow | — Pending |
| Email + file always | File output feeds weekly roll-up aggregation | — Pending |
| Flag suspicious URLs, don't strip | Avoid breaking useful links from custom redirect schemes | — Pending |
| Configurable digest length | Different days have different volumes; user controls density | — Pending |

---
*Last updated: 2026-03-11 after initialization*
