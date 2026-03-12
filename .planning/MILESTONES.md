# Milestones

## v1.0 MVP (Shipped: 2026-03-12)

**Phases completed:** 5 phases, 11 plans, 0 tasks

**Key accomplishments:**
- Privacy-first sanitizer with typed data contracts enforcing PII/tracking removal at the type level
- IMAP fetch with UID-mode-only design, verified against live Proton Mail Bridge
- Claude CLI summarization producing theme-grouped digests with configurable prompts and word targets
- HTML email delivery via Bridge SMTP with automatic markdown archival
- Weekly rollup pipeline re-summarizing daily digests into trend reports
- Full documentation with README setup guide, cron wrappers, and 101-test suite

**Known Tech Debt:**
- Dead config key: `SMTP_SECURITY` loaded in `load_config()` but `deliver.py` hard-wires STARTTLS
- Missing docs: `run-weekly.sh` not mentioned in README Shell Wrappers section

**Stats:**
- 54 commits, 77 files, 3,652 LOC Python
- Timeline: 2 days (2026-03-11 → 2026-03-12)
- Tests: 101 passed, 3 skipped (opt-in IMAP integration)

---

