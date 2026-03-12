# Requirements: Newsletter Digest Pipeline

**Defined:** 2026-03-11
**Core Value:** A single skimmable email each morning that distills all newsletter content into themed insights

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Email Fetching

- [x] **FETCH-01**: Pipeline connects to Proton Mail Bridge via IMAP on localhost:1143 with STARTTLS
- [x] **FETCH-02**: Pipeline fetches all messages from a configurable IMAP folder (e.g. Newsletters)
- [x] **FETCH-03**: Pipeline filters by configurable sender list as fallback when no folder configured
- [x] **FETCH-04**: Pipeline fetches only messages within a configurable time window (default 24h)
- [x] **FETCH-05**: Pipeline parses multipart MIME bodies, preferring HTML for richer extraction

### Privacy Sanitization

- [x] **PRIV-01**: Sanitizer converts HTML email bodies to clean plain text
- [x] **PRIV-02**: Sanitizer strips all tracking pixels (1x1 images, hidden imgs)
- [x] **PRIV-03**: Sanitizer removes known tracking URL parameters (utm_*, mc_eid, fbclid, etc.)
- [x] **PRIV-04**: Sanitizer redacts user's email address and name from body text
- [x] **PRIV-05**: Sanitizer supports configurable extra PII redaction regex patterns
- [x] **PRIV-06**: Sanitizer reduces sender identity to domain-only before passing to Claude
- [x] **PRIV-07**: Sanitizer truncates individual newsletter bodies to configurable character limit
- [x] **PRIV-08**: No email headers (To, CC, BCC, Message-ID, X-headers) ever reach Claude

### Summarization

- [x] **SUMM-01**: Pipeline pipes sanitized text to Claude Code CLI (`claude -p`) via subprocess stdin
- [x] **SUMM-02**: Digest is grouped by theme/topic across all sources, not per-newsletter
- [x] **SUMM-03**: Digest highlights key trends, notable announcements, and actionable insights
- [x] **SUMM-04**: Digest flags contradictions between sources
- [x] **SUMM-05**: Digest target length is configurable (default ~500 words)
- [x] **SUMM-06**: Digest lists sources (sender domain + subject) at end
- [x] **SUMM-07**: Summarization prompt is loaded from an external file (prompts/summarize.txt)

### Delivery & Archival

- [x] **DLVR-01**: Digest is sent as rendered HTML email via Bridge SMTP to configurable recipient
- [x] **DLVR-02**: Markdown file of every digest is saved to output directory (digest-YYYY-MM-DD.md)
- [x] **DLVR-03**: Weekly digest re-summarizes daily markdown files into higher-level trends
- [x] **DLVR-04**: Weekly digest is sent as HTML email and saved as markdown file

### Operations

- [x] **OPS-01**: `--dry-run` flag fetches and sanitizes without calling Claude or sending email
- [x] **OPS-02**: CLI supports `--since`, `--verbose`, `--prompt`, `--output` arguments
- [x] **OPS-03**: Exit codes: 0 success, 1 config/auth error, 2 no newsletters found, 3 Claude CLI error
- [x] **OPS-04**: Cron wrapper script (run-digest.sh) checks Bridge is running and Claude CLI is available
- [x] **OPS-05**: Dry-run wrapper script (dry-run.sh) for quick inspection

### Documentation

- [x] **DOCS-01**: README.md with setup guide, usage docs, configuration reference, and examples
- [x] **DOCS-02**: .env.example with placeholder values and descriptive comments

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhanced Privacy

- **PRIV-09**: Suspicious redirect URL flagging (flag opaque wrappers without removing them)

### Future Extensions

- **EXT-01**: RSS fallback for newsletters that publish feeds
- **EXT-02**: Topic-based filtering (only summarize certain categories)
- **EXT-03**: Interactive Claude Code skill for follow-up questions about newsletters

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web UI / dashboard | Markdown files are readable in any editor; no server needed |
| OAuth / third-party email providers | Proton Mail Bridge is the privacy guarantor |
| API key usage for Claude | Uses existing Pro/Max subscription via CLI |
| Per-newsletter summaries | Defeats cross-source synthesis goal |
| Real-time / push delivery | Cron matches the morning briefing use case |
| Mobile app | Email delivery works on any device already |
| Automatic subscription management | Pipeline is read-only; no write-back to external services |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FETCH-01 | Phase 2 | Complete |
| FETCH-02 | Phase 2 | Complete |
| FETCH-03 | Phase 2 | Complete |
| FETCH-04 | Phase 2 | Complete |
| FETCH-05 | Phase 2 | Complete |
| PRIV-01 | Phase 1 | Complete (01-02) |
| PRIV-02 | Phase 1 | Complete (01-02) |
| PRIV-03 | Phase 1 | Complete (01-02) |
| PRIV-04 | Phase 1 | Complete (01-02) |
| PRIV-05 | Phase 1 | Complete (01-02) |
| PRIV-06 | Phase 1 | Complete (01-02) |
| PRIV-07 | Phase 1 | Complete (01-02) |
| PRIV-08 | Phase 1 | Complete (01-01) |
| SUMM-01 | Phase 3 | Complete |
| SUMM-02 | Phase 3 | Complete |
| SUMM-03 | Phase 3 | Complete |
| SUMM-04 | Phase 3 | Complete |
| SUMM-05 | Phase 3 | Complete |
| SUMM-06 | Phase 3 | Complete |
| SUMM-07 | Phase 3 | Complete |
| DLVR-01 | Phase 3 | Complete |
| DLVR-02 | Phase 3 | Complete |
| DLVR-03 | Phase 4 | Complete |
| DLVR-04 | Phase 4 | Complete |
| OPS-01 | Phase 3 | Complete |
| OPS-02 | Phase 3 | Complete |
| OPS-03 | Phase 3 | Complete |
| OPS-04 | Phase 3 | Complete |
| OPS-05 | Phase 3 | Complete |
| DOCS-01 | Phase 4 | Complete |
| DOCS-02 | Phase 1 | Complete (01-01) |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after plan 01-02 completion (PRIV-01 through PRIV-07 complete)*
