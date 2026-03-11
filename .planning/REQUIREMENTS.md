# Requirements: Newsletter Digest Pipeline

**Defined:** 2026-03-11
**Core Value:** A single skimmable email each morning that distills all newsletter content into themed insights

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Email Fetching

- [ ] **FETCH-01**: Pipeline connects to Proton Mail Bridge via IMAP on localhost:1143 with STARTTLS
- [ ] **FETCH-02**: Pipeline fetches all messages from a configurable IMAP folder (e.g. Newsletters)
- [ ] **FETCH-03**: Pipeline filters by configurable sender list as fallback when no folder configured
- [ ] **FETCH-04**: Pipeline fetches only messages within a configurable time window (default 24h)
- [ ] **FETCH-05**: Pipeline parses multipart MIME bodies, preferring HTML for richer extraction

### Privacy Sanitization

- [ ] **PRIV-01**: Sanitizer converts HTML email bodies to clean plain text
- [ ] **PRIV-02**: Sanitizer strips all tracking pixels (1x1 images, hidden imgs)
- [ ] **PRIV-03**: Sanitizer removes known tracking URL parameters (utm_*, mc_eid, fbclid, etc.)
- [ ] **PRIV-04**: Sanitizer redacts user's email address and name from body text
- [ ] **PRIV-05**: Sanitizer supports configurable extra PII redaction regex patterns
- [ ] **PRIV-06**: Sanitizer reduces sender identity to domain-only before passing to Claude
- [ ] **PRIV-07**: Sanitizer truncates individual newsletter bodies to configurable character limit
- [ ] **PRIV-08**: No email headers (To, CC, BCC, Message-ID, X-headers) ever reach Claude

### Summarization

- [ ] **SUMM-01**: Pipeline pipes sanitized text to Claude Code CLI (`claude -p`) via subprocess stdin
- [ ] **SUMM-02**: Digest is grouped by theme/topic across all sources, not per-newsletter
- [ ] **SUMM-03**: Digest highlights key trends, notable announcements, and actionable insights
- [ ] **SUMM-04**: Digest flags contradictions between sources
- [ ] **SUMM-05**: Digest target length is configurable (default ~500 words)
- [ ] **SUMM-06**: Digest lists sources (sender domain + subject) at end
- [ ] **SUMM-07**: Summarization prompt is loaded from an external file (prompts/summarize.txt)

### Delivery & Archival

- [ ] **DLVR-01**: Digest is sent as rendered HTML email via Bridge SMTP to configurable recipient
- [ ] **DLVR-02**: Markdown file of every digest is saved to output directory (digest-YYYY-MM-DD.md)
- [ ] **DLVR-03**: Weekly digest re-summarizes daily markdown files into higher-level trends
- [ ] **DLVR-04**: Weekly digest is sent as HTML email and saved as markdown file

### Operations

- [ ] **OPS-01**: `--dry-run` flag fetches and sanitizes without calling Claude or sending email
- [ ] **OPS-02**: CLI supports `--since`, `--verbose`, `--prompt`, `--output` arguments
- [ ] **OPS-03**: Exit codes: 0 success, 1 config/auth error, 2 no newsletters found, 3 Claude CLI error
- [ ] **OPS-04**: Cron wrapper script (run-digest.sh) checks Bridge is running and Claude CLI is available
- [ ] **OPS-05**: Dry-run wrapper script (dry-run.sh) for quick inspection

### Documentation

- [ ] **DOCS-01**: README.md with setup guide, usage docs, configuration reference, and examples
- [ ] **DOCS-02**: .env.example with placeholder values and descriptive comments

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
| FETCH-01 | — | Pending |
| FETCH-02 | — | Pending |
| FETCH-03 | — | Pending |
| FETCH-04 | — | Pending |
| FETCH-05 | — | Pending |
| PRIV-01 | — | Pending |
| PRIV-02 | — | Pending |
| PRIV-03 | — | Pending |
| PRIV-04 | — | Pending |
| PRIV-05 | — | Pending |
| PRIV-06 | — | Pending |
| PRIV-07 | — | Pending |
| PRIV-08 | — | Pending |
| SUMM-01 | — | Pending |
| SUMM-02 | — | Pending |
| SUMM-03 | — | Pending |
| SUMM-04 | — | Pending |
| SUMM-05 | — | Pending |
| SUMM-06 | — | Pending |
| SUMM-07 | — | Pending |
| DLVR-01 | — | Pending |
| DLVR-02 | — | Pending |
| DLVR-03 | — | Pending |
| DLVR-04 | — | Pending |
| OPS-01 | — | Pending |
| OPS-02 | — | Pending |
| OPS-03 | — | Pending |
| OPS-04 | — | Pending |
| OPS-05 | — | Pending |
| DOCS-01 | — | Pending |
| DOCS-02 | — | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 0
- Unmapped: 31 ⚠️

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after initial definition*
