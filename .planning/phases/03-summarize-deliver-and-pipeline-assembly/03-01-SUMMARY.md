---
phase: 03-summarize-deliver-and-pipeline-assembly
plan: 01
subsystem: summarization
tags: [subprocess, claude-cli, prompt-engineering, pathlib, tdd]

# Dependency graph
requires:
  - phase: 01-foundation-and-privacy-sanitizer
    provides: CleanMessage dataclass with subject, sender_domain, date, clean_text fields
  - phase: 02-imap-fetch
    provides: subprocess.run(input=...) pattern decision mandated in STATE.md
provides:
  - call_claude() function piping newsletter text to Claude CLI via subprocess stdin
  - format_newsletter_input() concatenating CleanMessages with source headers and dividers
  - prompts/summarize.txt digest prompt with theme grouping, contradiction flagging, source listing
affects: [03-summarize-deliver-and-pipeline-assembly, 03-02, 03-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "subprocess.run(input=..., capture_output=True, text=True) for Claude CLI — never Popen"
    - "Prompt loaded from external file via Path.read_text() — never hardcoded in Python source"
    - "Library modules raise exceptions; only scripts/daily.py calls sys.exit()"

key-files:
  created:
    - src/summarize.py
    - prompts/summarize.txt
    - tests/test_summarize.py
  modified: []

key-decisions:
  - "Prompt text lives in prompts/summarize.txt, not Python source — SUMM-07 requirement and anti-hardcoding rule"
  - "call_claude raises RuntimeError for non-zero exit AND empty stdout — Pitfall 4 (empty output silently accepted)"
  - "FileNotFoundError propagates unchanged for missing binary — orchestrator (daily.py) maps to exit code 3"
  - "format_newsletter_input returns empty string for empty list — no special-case exception"

patterns-established:
  - "Pattern: subprocess.run(cmd, input=text, capture_output=True, text=True) for all external CLI calls"
  - "Pattern: Path(prompt_file).read_text(encoding='utf-8') for prompt loading"
  - "Pattern: TDD red-green with skipif guard on prompt content tests (file may not exist during RED)"

requirements-completed: [SUMM-01, SUMM-02, SUMM-03, SUMM-04, SUMM-05, SUMM-06, SUMM-07]

# Metrics
duration: 8min
completed: 2026-03-12
---

# Phase 3 Plan 1: Summarization Module Summary

**Claude CLI subprocess wrapper with prompt-file loading, newsletter concatenation, and full error handling using subprocess.run(input=...) pattern**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-12T12:20:00Z
- **Completed:** 2026-03-12T12:27:19Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3 created

## Accomplishments

- `src/summarize.py` implementing `call_claude()` and `format_newsletter_input()` with full error handling
- `prompts/summarize.txt` with theme-grouped digest prompt per Pattern 7 from research
- 14 unit tests covering all SUMM-01 through SUMM-07 requirements
- Full test suite green: 51 passed, 3 skipped (no regressions from 23 baseline)

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests for summarization module** - `27382fb` (test)
2. **GREEN: Implement summarization module and prompt file** - `4c083e2` (feat)

_TDD plan: two commits (test → feat)_

## Files Created/Modified

- `src/summarize.py` — call_claude() + format_newsletter_input(), subprocess.run pattern, exception-based error handling
- `prompts/summarize.txt` — system prompt grouping by topic, contradiction flagging, ~500 word target, sources section
- `tests/test_summarize.py` — 14 unit tests for SUMM-01 through SUMM-07, uses @pytest.mark.skipif guards for prompt content tests

## Decisions Made

- RuntimeError raised for both non-zero exit AND empty stdout — research Pitfall 4 explicitly warns against silently accepting empty output
- FileNotFoundError is not caught in call_claude() — it propagates naturally so the orchestrator can map it to exit code 3
- `@pytest.mark.skipif(not PROMPT_PATH.exists(), ...)` guards on prompt content tests — allows RED phase to run without prompt file existing yet
- format_newsletter_input returns `""` for empty list (not an exception) — orchestrator checks for empty list upstream with exit code 2

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all tests passed on first GREEN run. Full suite baseline (23 tests) remained intact.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `src/summarize.py` ready for use by `scripts/daily.py` orchestrator (03-03)
- `prompts/summarize.txt` ready; can be overridden via `--prompt FILE` CLI flag
- Note: `src/deliver.py` already exists from plan 03-02 (committed out of order in git history)

## Self-Check: PASSED

- src/summarize.py: FOUND
- prompts/summarize.txt: FOUND
- tests/test_summarize.py: FOUND
- 03-01-SUMMARY.md: FOUND
- commit 27382fb (test RED): FOUND
- commit 4c083e2 (feat GREEN): FOUND

---
*Phase: 03-summarize-deliver-and-pipeline-assembly*
*Completed: 2026-03-12*
