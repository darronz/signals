# Feature Research

**Domain:** Newsletter digest / email summarization pipeline (personal-use, local, privacy-first)
**Researched:** 2026-03-11
**Confidence:** MEDIUM — ecosystem surveyed via WebSearch and tool analysis; architecture confirmed against PROJECT.md requirements

## Feature Landscape

### Table Stakes (Users Expect These)

Features the pipeline must have or the product feels broken. For a personal digest tool, "user" = the operator.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| IMAP email fetching | Source of all newsletter content; without it there is no pipeline | MEDIUM | Proton Mail Bridge on 127.0.0.1:1143 with STARTTLS; stdlib imaplib handles this |
| Time-window filtering | Fetching all mail is useless; only recent newsletters matter | LOW | Configurable `--since` window; default 24h |
| HTML-to-plaintext conversion | Newsletter bodies are HTML; LLMs work best with clean text | LOW | beautifulsoup4 get_text() plus whitespace normalization |
| AI-generated summary | The whole point; without this it is just a mail reader | HIGH | Pipe clean text to `claude -p` via subprocess; prompt engineering is the hard part |
| Digest delivered to inbox | Skimmable in existing email client; zero new app to open | MEDIUM | SMTP via Bridge on 127.0.0.1:1025; send HTML email back to self |
| Source attribution in digest | User must know what newsletters each insight came from | LOW | Sender domain + subject line list at end of digest; no full addresses (privacy) |
| Configurable time window | Volume varies; user controls what gets fetched | LOW | `--since` CLI arg with sensible default |
| Dry-run mode | Safe testing without burning Claude CLI calls or sending email | LOW | `--dry-run` flag; fetch and sanitize only |
| Graceful error handling | Cron jobs must not silently fail | LOW | Structured exit codes; log errors; no partial output emitted on failure |
| Archival of digest output | Reproducibility; feeds weekly rollup | LOW | Save markdown file alongside every email send |

### Differentiators (Competitive Advantage)

Features this pipeline has that commercial tools (Meco, Readless, Summate) do not — because it is local, privacy-first, and Claude-powered.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Privacy sanitization before AI | No PII, no tracking data, no sender addresses ever reach Claude — competitor tools send raw email to cloud AI | HIGH | Two-tier URL sanitization (strip known params, flag suspicious redirects); PII redaction; domain-only sender identity |
| Theme-grouped synthesis | Digest organized by topic across all sources, not by sender — cross-source insight that commercial tools rarely do | HIGH | Prompt engineering to instruct Claude to group by theme; not per-newsletter summaries |
| Contradiction flagging | Surfaces when sources disagree — adds editorial value beyond summary | MEDIUM | Part of Claude prompt; Claude identifies conflicting claims across sources |
| Weekly trend rollup | Re-summarizes daily digest markdown files into higher-level patterns over 7 days | MEDIUM | Reads saved .md files, feeds back to Claude with week-level prompt; no external state needed |
| Local-only execution | No cloud services, no SaaS accounts, no subscription beyond existing Claude CLI | LOW | Everything runs on local machine via cron; Proton Mail Bridge is local IMAP/SMTP |
| Configurable digest density | `--prompt` override and word-count target let the user tune output length per run | LOW | Exposed as CLI args; useful when volume spikes (e.g., conference weeks) |
| Tracking pixel and UTM stripping | Prevents Claude from seeing surveillance infrastructure in URLs | MEDIUM | Strip utm_*, mc_eid, fbclid and known tracking params; detect 1x1 img tracking pixels via BeautifulSoup |
| Suspicious redirect flagging | Preserves custom redirect URLs (don't break useful links) but flags opaque wrappers for review | MEDIUM | Heuristics: known redirect domains (t.co, mailchimp redirect, etc.) flagged, not stripped |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem appealing but should be explicitly excluded from this pipeline.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Web UI / dashboard | "Would be nice to browse past digests" | Adds a server, auth, a JS frontend, and ongoing maintenance — scope creep with no core-value payoff | Use the archived markdown files directly; they are readable in any editor or file browser |
| OAuth / third-party provider support | "I want to run this on Gmail too" | OAuth flows, token refresh, scope management, and per-provider quirks destroy the minimal-dependency constraint | Proton Mail Bridge is the privacy guarantor; expanding providers expands attack surface |
| API key usage for Claude | "Direct API would be cleaner" | Requires managing an API key, adds per-token cost, and abandons the existing Pro/Max subscription | Claude Code CLI (`claude -p`) uses the subscription; no key to manage or rotate |
| Per-newsletter summaries | "I want a separate section per source" | Defeats the cross-source synthesis goal; produces a list of per-sender blurbs, not insight | Theme-grouped synthesis is the differentiator; per-sender view is available via the source attribution list |
| RSS fallback | "Some newsletters have feeds" | Different content model, different fetch path, different sanitization rules — doubles the implementation surface | Scope to future extension; email-only for v1 |
| Real-time / push delivery | "Send the digest as newsletters arrive" | Adds event loop, state tracking for partial batches, and complicates deduplication | Scheduled cron at a predictable time is simpler and matches the "morning briefing" use case |
| Interactive follow-up questions | "I want to ask Claude about a specific article" | Changes the product from a pipeline to an agent; requires persistent context, session management | Separate Claude Code skill or interactive session; out of scope for this pipeline |
| Automatic newsletter subscription management | "Unsubscribe me from low-quality senders" | Requires writing back to external services; creates liability and unpredictable side effects | User manages subscriptions manually; pipeline is read-only |
| Summarization quality scoring / feedback loop | "Rate summaries to improve prompts over time" | Requires storing feedback, running comparisons, and managing prompt versions — overkill for personal use | Tune prompt manually via `--prompt` flag; iterate on the base prompt in config |

## Feature Dependencies

```
[IMAP Fetch]
    └──requires──> [Proton Mail Bridge running + authenticated]
    └──requires──> [Time-window config]

[HTML-to-plaintext conversion]
    └──requires──> [IMAP Fetch]

[Privacy Sanitization]
    └──requires──> [HTML-to-plaintext conversion]
    │   ├── PII redaction
    │   ├── Tracking pixel removal
    │   └── URL sanitization (strip params, flag redirects)
    └──is required by──> [Claude summarization] (sanitizer is the privacy boundary)

[Claude Summarization]
    └──requires──> [Privacy Sanitization]
    └──requires──> [Claude Code CLI installed + authenticated]
    └──produces──> [Digest markdown text]

[Theme-grouped digest]
    └──is part of──> [Claude Summarization] (prompt-level, not separate feature)

[Contradiction flagging]
    └──is part of──> [Claude Summarization] (prompt-level)

[HTML email render + send]
    └──requires──> [Digest markdown text]
    └──requires──> [Proton Mail Bridge SMTP]

[Archival to markdown file]
    └──requires──> [Digest markdown text]
    └──enables──> [Weekly rollup]

[Weekly rollup]
    └──requires──> [Archival to markdown file] (reads saved daily digests)
    └──requires──> [Claude Summarization] (second pass with week-level prompt)

[Cron scheduling]
    └──requires──> [All pipeline stages stable]
    └──requires──> [CLI exit codes reliable]

[Dry-run mode] ──conflicts──> [Claude Summarization] (must short-circuit before Claude call)
[Dry-run mode] ──conflicts──> [HTML email send] (must short-circuit before send)
```

### Dependency Notes

- **Privacy sanitization requires HTML-to-plaintext:** URL extraction and PII redaction both operate on parsed text; sanitizing raw HTML is error-prone and incomplete.
- **Claude summarization requires sanitization:** This is a hard constraint — the sanitizer is the privacy boundary; no raw or partially-cleaned content may pass through.
- **Weekly rollup requires archival:** The rollup reads saved daily markdown files, not email; archival must be reliable before weekly rollup is useful.
- **Theme grouping and contradiction flagging are prompt-level:** They are not separate pipeline stages; they live in the Claude prompt. This means they add no implementation complexity beyond prompt engineering.
- **Dry-run conflicts with Claude and send:** Dry-run must be checked before the Claude subprocess call and before SMTP send; it is a pipeline gate, not a flag on individual stages.

## MVP Definition

### Launch With (v1)

Minimum viable product — the pipeline must do these to produce value.

- [ ] IMAP fetch from Proton Mail Bridge with time-window filtering — without this there is no input
- [ ] HTML-to-plaintext conversion — raw HTML is unusable for Claude
- [ ] Tracking pixel removal and UTM parameter stripping — non-negotiable privacy requirement
- [ ] PII redaction (user email, name, configurable patterns) — non-negotiable privacy requirement
- [ ] Domain-only sender identity reduction — non-negotiable privacy requirement
- [ ] Claude Code CLI summarization with theme-grouped prompt — the core value
- [ ] HTML digest email sent via Bridge SMTP — the delivery mechanism
- [ ] Markdown archival of every digest — enables weekly rollup and is low-cost insurance
- [ ] Dry-run mode with `--dry-run` flag — required for safe testing during development
- [ ] Clear exit codes and structured error handling — required for cron reliability
- [ ] CLI args: `--dry-run`, `--since`, `--verbose`, `--prompt` — operator ergonomics

### Add After Validation (v1.x)

Features to add once the daily digest is working reliably.

- [ ] Weekly rollup — add once daily archival has accumulated 7+ days of files
- [ ] Suspicious redirect URL flagging — add after basic URL stripping is stable; more nuanced logic
- [ ] Contradiction flagging in prompt — add after base prompt is tuned; incremental prompt enhancement
- [ ] Configurable digest length target — add if daily volume varies enough to matter; low effort

### Future Consideration (v2+)

Features to defer until the pipeline has proven daily value.

- [ ] RSS fallback for newsletters with feeds — doubles the input path complexity; defer
- [ ] Topic-based filtering (only summarize certain categories) — requires classification before summarization; defer
- [ ] Interactive Claude Code follow-up skill — different product; out of scope
- [ ] Web UI for browsing past digests — markdown files work fine for personal use; defer indefinitely

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| IMAP fetch + time-window filter | HIGH | MEDIUM | P1 |
| HTML-to-plaintext | HIGH | LOW | P1 |
| Tracking pixel + UTM stripping | HIGH | MEDIUM | P1 |
| PII redaction | HIGH | MEDIUM | P1 |
| Domain-only sender identity | HIGH | LOW | P1 |
| Claude CLI summarization | HIGH | HIGH | P1 |
| Theme-grouped prompt | HIGH | MEDIUM | P1 |
| HTML digest email delivery | HIGH | MEDIUM | P1 |
| Markdown archival | HIGH | LOW | P1 |
| Dry-run mode | MEDIUM | LOW | P1 |
| CLI argument handling | MEDIUM | LOW | P1 |
| Exit codes + error handling | MEDIUM | LOW | P1 |
| Weekly rollup | MEDIUM | MEDIUM | P2 |
| Suspicious redirect flagging | MEDIUM | MEDIUM | P2 |
| Contradiction flagging (prompt) | MEDIUM | LOW | P2 |
| Configurable digest length | LOW | LOW | P2 |
| RSS fallback | LOW | HIGH | P3 |
| Topic-based filtering | LOW | HIGH | P3 |
| Web UI dashboard | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

Commercial tools surveyed: Meco, Readless, Summate, Remy, SaneBox.

| Feature | Commercial Tools (Meco/Readless/Summate) | This Pipeline |
|---------|------------------------------------------|---------------|
| AI summarization | Cloud AI, raw email content sent to provider | Local Claude CLI; sanitized text only |
| Delivery | Dedicated app, web UI, or forwarded inbox | HTML email back to same inbox; no new app |
| Privacy | Email content processed by third-party cloud | PII-stripped, tracking-removed before Claude |
| Source grouping | Per-newsletter or per-source layout | Theme-grouped cross-source synthesis |
| Scheduling | In-app schedule settings | Cron; operator-controlled |
| Weekly rollup | Not common; most are daily-only | First-class feature via saved daily markdown files |
| Contradiction detection | Not a feature in any surveyed tool | Explicit prompt instruction to Claude |
| Local execution | Cloud-hosted SaaS | 100% local; no cloud services |
| Setup complexity | OAuth / forwarding setup | Requires Proton Mail Bridge + Claude CLI (pre-existing) |
| Cost | $0–$10/month SaaS subscription | Zero additional cost; uses existing Claude Pro/Max |

## Sources

- [6 Best AI Newsletter Summarizers in 2026 — Readless](https://www.readless.app/blog/best-ai-newsletter-summarizers)
- [10 Best Newsletter Management Tools in 2026 — Readless](https://www.readless.app/blog/best-newsletter-management-tools-2026)
- [Summate — Personal AI Digest](https://summate.io)
- [Meco Newsletter Reader](https://meco.app/)
- [Email Automation Local-First Architecture — xugj520.cn](https://www.xugj520.cn/en/archives/email-automation-local-first-architecture.html)
- [PII Safety for AI — DEV Community](https://dev.to/sridharcr/stop-ai-from-seeing-what-it-shouldnt-a-practical-guide-to-pii-safety-38ll)
- [Email Digest Template Design — Email Mavlers](https://www.emailmavlers.com/blog/design-email-digest-templates/)
- [pytracking — PyPI](https://pypi.org/project/pytracking/)
- PROJECT.md requirements (validated against all feature decisions above)

---
*Feature research for: newsletter digest pipeline (local, privacy-first, Claude CLI)*
*Researched: 2026-03-11*
