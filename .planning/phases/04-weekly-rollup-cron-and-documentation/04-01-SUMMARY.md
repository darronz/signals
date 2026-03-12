---
phase: 04-weekly-rollup-cron-and-documentation
plan: 01
subsystem: pipeline
tags: [weekly-rollup, pathlib, datetime, argparse, tdd, claude-cli, email, markdown]

# Dependency graph
requires:
  - phase: 03-summarize-deliver-and-pipeline-assembly
    provides: call_claude, send_digest_email, markdown_to_html, save_archive from src/summarize.py and src/deliver.py
provides:
  - scripts/weekly.py: weekly rollup CLI entry point (find_daily_digests, format_weekly_input, weekly_archive_filename, save_weekly_archive, main)
  - prompts/weekly.txt: weekly synthesis prompt for Claude
  - tests/test_weekly.py: 29 unit tests covering all functions and CLI integration
  - README.md: complete setup guide with config reference for all 19 env keys
affects: [cron-setup, documentation, weekly-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "glob('digest-*.md') prefix filter to exclude weekly-*.md files from daily digest discovery"
    - "date.isocalendar().year for ISO week filenames to avoid year-boundary bug (Dec 31 edge case)"
    - "Weekly archive written directly via pathlib.write_text, not via save_archive (which hardcodes daily filename)"
    - "sys.exit() only in main() — helper functions return empty list or raise, never exit"

key-files:
  created:
    - scripts/weekly.py
    - prompts/weekly.txt
    - tests/test_weekly.py
    - README.md
  modified: []

key-decisions:
  - "Weekly archive written directly in weekly.py not via save_archive() — save_archive has 13 tests and hardcodes daily filename pattern"
  - "Weekly email subject: 'Weekly Digest -- Week {week:02d}, {year}' using ISO week number (research Open Question 1)"
  - "dry-run prints file count + filenames + total chars, exits 0 without calling Claude (research Open Question 2)"
  - "Silently overwrite weekly archive on same-week re-run (consistent with save_archive daily behavior, research Open Question 3)"
  - "README config reference derived from src/config.py load_config() line-by-line — ground truth, not .env.example"

patterns-established:
  - "Pattern: weekly digest file naming uses weekly-YYYY-WXX.md (ISO week) vs daily digest-YYYY-MM-DD.md"
  - "Pattern: smoke tests for documentation artifacts (README.md exists + contains all config keys) live in test_weekly.py"

requirements-completed: [DLVR-03, DLVR-04]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 4 Plan 01: Weekly Rollup Script Summary

**Weekly rollup script using pathlib glob + datetime isocalendar, with TDD (29 tests), weekly.txt prompt, and README documenting all 19 config keys**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T13:54:50Z
- **Completed:** 2026-03-12T13:57:58Z
- **Tasks:** 2 (RED: tests, GREEN: implementation)
- **Files modified:** 4

## Accomplishments

- `scripts/weekly.py` — full weekly rollup CLI with `find_daily_digests`, `format_weekly_input`, `weekly_archive_filename`, `save_weekly_archive`, and `main()` mirroring `daily.py` patterns
- `prompts/weekly.txt` — weekly synthesis prompt with Week in Review, Key Trends, Notable Developments, Signals to Watch, Sources Overview sections (~600 word target)
- `tests/test_weekly.py` — 29 tests covering all helper functions, CLI exit codes (0/1/2/3), dry-run behavior, email delivery, and README smoke checks
- `README.md` — complete setup guide: prerequisites, quick start, config reference table (all 19 keys from `src/config.py`), usage examples, cron setup, exit code reference, troubleshooting

## Task Commits

1. **RED: Failing tests** - `1cd495a` (test)
2. **GREEN: Implementation** - `2017922` (feat)

## Files Created/Modified

- `tests/test_weekly.py` — 29 unit tests for weekly rollup (TDD RED)
- `scripts/weekly.py` — weekly rollup CLI entry point
- `prompts/weekly.txt` — weekly synthesis prompt for Claude
- `README.md` — full project documentation with config reference

## Decisions Made

- Weekly archive written directly in `weekly.py` using pathlib, not via `save_archive()` — the existing function hardcodes `digest-YYYY-MM-DD.md` and has 13 tests; modifying it would be an architectural change
- `weekly_archive_filename` uses `date.isocalendar().year` not `date.today().year` — handles ISO year boundary correctly (Dec 31 edge case where ISO week 1 of next year starts before calendar year end)
- `glob("digest-*.md")` not `glob("*.md")` — prefix-specific pattern prevents picking up `weekly-*.md` files as input to the weekly script
- README config table derived from `src/config.py` `load_config()` line-by-line — 19 keys documented exactly matching code defaults
- Smoke test `test_readme_contains_all_config_keys` directly validates README stays in sync with code

## Deviations from Plan

None — plan executed exactly as written. TDD cycle completed cleanly: all 29 tests failed RED before implementation, all 29 passed GREEN after. Full suite: 95 passed, 3 skipped.

## Issues Encountered

None. GPG signing is disabled for commits (pre-existing project configuration).

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- Phase 4 Plan 01 complete: weekly rollup script, prompt, tests, and README delivered
- All 95 tests passing (3 skipped: IMAP integration, requires Bridge)
- DLVR-03 and DLVR-04 requirements satisfied
- Remaining Phase 4 work: cron documentation and any additional docs (per ROADMAP)

## Self-Check: PASSED

- FOUND: scripts/weekly.py
- FOUND: prompts/weekly.txt
- FOUND: tests/test_weekly.py
- FOUND: README.md
- FOUND: 04-01-SUMMARY.md
- FOUND: commit 1cd495a (test RED)
- FOUND: commit 2017922 (feat GREEN)
- Full test suite: 95 passed, 3 skipped

---
*Phase: 04-weekly-rollup-cron-and-documentation*
*Completed: 2026-03-12*
