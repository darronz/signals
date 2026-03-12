# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-12
**Phases:** 5 | **Plans:** 11

### What Was Built
- Privacy-first email sanitizer with typed data contracts (CleanMessage has no header fields by design)
- IMAP fetch module with UID-mode-only design, verified against live Proton Mail Bridge
- Claude CLI summarization producing theme-grouped digests with configurable prompts and word targets
- HTML email delivery via Bridge SMTP with automatic markdown archival
- Weekly rollup pipeline re-summarizing daily digests into weekly trend reports
- Full documentation: README setup guide, cron wrappers, .env.example, 101-test suite

### What Worked
- TDD approach: writing failing tests first then implementing kept scope tight and prevented regressions
- Phase ordering (privacy sanitizer first, offline) meant real email data was never at risk during development
- Minimal dependency strategy: stdlib for IMAP, SMTP, subprocess — only beautifulsoup4 and python-dotenv external
- Audit-driven gap closure: Phase 5 was created specifically to close gaps found by milestone audit, ensuring nothing shipped with known broken behavior

### What Was Inefficient
- ROADMAP.md plan checkboxes got out of sync with actual completion (phases 1-3 showed `[ ]` despite being complete)
- STATE.md metrics drifted significantly from reality (showed 17% when actually 100%, phase count said 4 when there were 5)
- Some phase SUMMARY.md files lacked `one_liner` frontmatter field, making automated extraction fail

### Patterns Established
- `SIGNALS_INTEGRATION=1` env var gates tests requiring live infrastructure (Proton Mail Bridge)
- Exception propagation from modules to orchestrator script for exit code mapping (no sys.exit() in library code)
- Path resolution via `Path(__file__).parent.parent` for cron-safety (scripts run from any cwd)
- Shell wrappers check prerequisites (Bridge running, Claude CLI available) before invoking Python

### Key Lessons
1. State tracking files need to be updated by the same tool that executes plans — manual updates drift
2. Milestone audit before completion is valuable — Phase 5 gap closure fixed 3 real issues (dead config key, hardcoded port, missing wrapper script)
3. Two non-critical tech debt items shipped knowingly (SMTP_SECURITY dead key, run-weekly.sh undocumented in README) — acceptable trade-off vs. another phase

### Cost Observations
- Model mix: balanced profile used throughout
- Timeline: 2 days end-to-end (project init to milestone complete)
- Notable: 54 commits, 3,652 LOC Python — rapid execution enabled by clear requirements and phase boundaries

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 11 | Initial milestone — established TDD + audit-driven gap closure pattern |

### Cumulative Quality

| Milestone | Tests | Skipped | Failed | Tech Debt Items |
|-----------|-------|---------|--------|-----------------|
| v1.0 | 101 | 3 | 0 | 2 (non-critical) |

### Top Lessons (Verified Across Milestones)

1. Audit before shipping catches real gaps — Phase 5 wouldn't have existed without the audit
2. Privacy boundaries should be enforced by type design, not runtime checks
