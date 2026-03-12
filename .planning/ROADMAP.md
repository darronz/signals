# Roadmap: Newsletter Digest Pipeline (Signals)

## Overview

Build a local Python pipeline in four phases, each independently testable before the next begins. Phase 1 establishes the typed privacy boundary offline. Phase 2 connects to Proton Mail Bridge and proves real email flows through the sanitizer cleanly. Phase 3 completes the core value loop: sanitized content reaches Claude CLI, a digest is formatted and delivered to the inbox, and the CLI entry point wires it all together. Phase 4 adds weekly rollup, cron scheduling, and the documentation that makes the whole thing runnable from cold start.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation and Privacy Sanitizer** - Build data contracts and the sanitizer module offline, fully tested before any real email is touched
- [ ] **Phase 2: IMAP Fetch** - Connect to Proton Mail Bridge, fetch real newsletters, and verify they flow cleanly through the sanitizer
- [ ] **Phase 3: Summarize, Deliver, and Pipeline Assembly** - Complete the core value loop: Claude CLI summarization, HTML digest delivery, CLI entry point with dry-run and exit codes
- [ ] **Phase 4: Weekly Rollup, Cron, and Documentation** - Automate the daily and weekly schedules and document setup for cold-start use

## Phase Details

### Phase 1: Foundation and Privacy Sanitizer
**Goal**: The privacy boundary is enforced and fully tested — no PII, tracking pixels, or raw email structure can reach Claude
**Depends on**: Nothing (first phase)
**Requirements**: PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, PRIV-06, PRIV-07, PRIV-08, DOCS-02
**Success Criteria** (what must be TRUE):
  1. A synthetic HTML newsletter passed through the sanitizer produces clean plain text with no tracking pixels, no UTM parameters, and no user PII in the output
  2. The sanitizer reduces sender identity to domain-only and strips all email headers before producing a CleanMessage
  3. An assertion test passes: the configured user email address never appears anywhere in sanitizer output
  4. The .env.example file exists with all required configuration keys and descriptive comments
  5. The project package structure is importable and all modules can be loaded without error
**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffolding, data contracts, config, test infrastructure
- [x] 01-02-PLAN.md — TDD: Privacy sanitizer implementation

### Phase 2: IMAP Fetch
**Goal**: Real newsletter emails are fetched from Proton Mail Bridge and flow through the sanitizer cleanly
**Depends on**: Phase 1
**Requirements**: FETCH-01, FETCH-02, FETCH-03, FETCH-04, FETCH-05
**Success Criteria** (what must be TRUE):
  1. Running the fetch module against a live Proton Mail Bridge returns RawMessage objects for all newsletters in the configured folder received within the last 24 hours
  2. Fetched messages use UID mode throughout — no sequence numbers — and return correct messages even when other mail arrives or is deleted during the run
  3. Multipart MIME emails (HTML + text parts) are parsed and the HTML part is preferred for extraction
  4. All fetched messages pass through the sanitizer and produce CleanMessage objects with no PII or tracking artifacts
**Plans:** 1/2 plans executed

Plans:
- [ ] 02-01-PLAN.md — TDD: IMAP fetch module (STARTTLS, UID mode, MIME parsing, time/sender filters)
- [ ] 02-02-PLAN.md — Live Bridge integration test and human verification

### Phase 3: Summarize, Deliver, and Pipeline Assembly
**Goal**: Running the daily entry point produces a themed digest in the inbox and saves a markdown archive, with dry-run and error handling working correctly
**Depends on**: Phase 2
**Requirements**: SUMM-01, SUMM-02, SUMM-03, SUMM-04, SUMM-05, SUMM-06, SUMM-07, DLVR-01, DLVR-02, OPS-01, OPS-02, OPS-03, OPS-04, OPS-05
**Success Criteria** (what must be TRUE):
  1. Running `python scripts/daily.py` with real newsletters produces an HTML email in the inbox grouped by theme across sources, not per-newsletter, within the configured word-count target
  2. The digest email lists source domains and subjects at the end and the markdown archive file is saved to the output directory
  3. Running with `--dry-run` fetches and sanitizes without calling Claude or sending email, and exits 0
  4. When no newsletters are found the script exits with code 2; when Claude CLI fails it exits with code 3; config errors exit with code 1
  5. The `--since`, `--verbose`, and `--prompt` CLI arguments work as documented
**Plans**: TBD

### Phase 4: Weekly Rollup, Cron, and Documentation
**Goal**: The pipeline runs unattended on schedule and a new user can set it up from scratch using the README
**Depends on**: Phase 3
**Requirements**: DLVR-03, DLVR-04, DOCS-01
**Success Criteria** (what must be TRUE):
  1. Running `python scripts/weekly.py` against 7+ saved daily digest files produces an HTML weekly digest email and saves a weekly markdown file
  2. The cron wrapper script (`run-digest.sh`) checks that Proton Mail Bridge is running and Claude CLI is available before invoking the pipeline, and exits non-zero if either prerequisite is absent
  3. A new user following only the README can configure `.env`, install dependencies, and successfully run `--dry-run` to verify their setup without prior knowledge of the codebase
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Privacy Sanitizer | 2/2 | Complete | 2026-03-11 |
| 2. IMAP Fetch | 1/2 | In Progress|  |
| 3. Summarize, Deliver, and Pipeline Assembly | 0/TBD | Not started | - |
| 4. Weekly Rollup, Cron, and Documentation | 0/TBD | Not started | - |
