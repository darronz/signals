---
phase: 01-foundation-and-privacy-sanitizer
plan: "02"
subsystem: privacy
tags: [python, beautifulsoup4, urllib.parse, email.utils, re, sanitizer, pii-redaction, tdd]

# Dependency graph
requires:
  - phase: 01-foundation-and-privacy-sanitizer
    plan: "01"
    provides: "RawMessage, CleanMessage, SanitizerConfig dataclasses; sanitize() stub; 13 RED tests"
provides:
  - Complete sanitize() implementation with all 8 PRIV requirements enforced
  - _html_to_text() using BeautifulSoup4 — removes script/style/img, extracts plain text
  - _strip_tracking_params() / _strip_tracking_urls() — UTM and known tracker params stripped
  - _extract_domain() — sender reduced to domain-only via email.utils.parseaddr
  - _build_redaction_patterns() / _redact_pii() — user email, name, and extra patterns redacted
  - All 13 tests GREEN: PRIV-01 through PRIV-07 + PRIV-08 + DOCS-02 + 3 edge cases
affects:
  - 01-03 (IMAP fetcher — calls sanitize(raw, config) -> CleanMessage, must understand pipeline)
  - 02-xx (Phase 2 IMAP integration — RawMessage populated here, sanitized before any Claude call)
  - 03-xx (Phase 3 Claude integration — only CleanMessage objects cross the privacy boundary)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pipeline order enforced: HTML-to-text first, URL stripping second, PII redaction third, truncation last — never redact raw HTML"
    - "Conservative img removal: all img tags removed (not just 1x1 pixels) to avoid false negatives"
    - "url.parse round-trip for URL sanitization: parse_qsl -> filter -> urlencode -> urlunparse — preserves non-tracking params"
    - "re.escape() required for PII patterns: user emails with + or . must be escaped before re.compile()"
    - "Test for href URLs must use body_text (not body_html) — get_text() does not extract href attribute values"

key-files:
  created: []
  modified:
    - src/sanitizer.py
    - tests/test_sanitizer.py

key-decisions:
  - "Pipeline order is HTML->text, URL strip, PII redact, truncate — enforced by code comments and function order"
  - "Test test_utm_params_stripped updated to use body_text for URL verification — href attributes not visible after get_text()"
  - "All img tags removed (conservative) — safer than size-based detection per research recommendation"

patterns-established:
  - "Pattern: Use body_text fixture (not body_html) in tests that assert on URL parameter preservation — href attrs are invisible after HTML extraction"
  - "Pattern: _build_redaction_patterns() builds patterns once per call — acceptable for small config; can cache if profiling shows cost"

requirements-completed: [PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, PRIV-06, PRIV-07]

# Metrics
duration: 7min
completed: 2026-03-11
---

# Phase 1 Plan 02: Privacy Sanitizer Summary

**Full sanitize() pipeline implemented via TDD: HTML-to-text via BeautifulSoup4, UTM/tracker param stripping via urllib.parse, PII redaction via compiled regex, sender domain extraction via email.utils — all 13 PRIV tests green**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-11T22:19:12Z
- **Completed:** 2026-03-11T22:26:00Z
- **Tasks:** 1 (TDD: RED verified -> GREEN implemented)
- **Files modified:** 2

## Accomplishments

- Implemented the complete privacy sanitizer: all 7 functional PRIV requirements (PRIV-01 through PRIV-07) now enforced in a single sanitize() pipeline
- 13 tests pass: full PRIV coverage plus PRIV-08 (structural), DOCS-02 (env example), and 3 edge cases (HTML fallback, empty body, subject PII redaction)
- Subject field PII redaction added per research Open Question 3 recommendation — user name never appears in CleanMessage.subject

## Task Commits

1. **Task 1: Implement sanitize() — GREEN** - `54c75a6` (feat)

## Files Created/Modified

- `src/sanitizer.py` — Complete sanitizer with all private helpers and public sanitize() function (155 lines)
- `tests/test_sanitizer.py` — test_utm_params_stripped updated to use body_text for URL assertion correctness

## Decisions Made

- Pipeline order (HTML-to-text -> URL strip -> PII redact -> truncate) is enforced and documented in code comments — this order is a security requirement, not just style
- test_utm_params_stripped was updated to use body_text with an inline URL rather than body_html with an href — BS4 get_text() does not extract href attribute values into plain text output, so the "keep=this" assertion would never be verifiable through HTML extraction. The security invariant (no UTM params in output) is still fully asserted; only the test mechanism was corrected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_utm_params_stripped: URL in href not visible after HTML extraction**
- **Found during:** GREEN phase — running tests after implementation
- **Issue:** Test asserted `"keep=this" in result.clean_text` but the URL was only in an `href` attribute; BeautifulSoup4's `get_text()` extracts visible text only, so `keep=this` never appeared in output. The security invariant (UTM params stripped) was already passing; only the non-tracking-param preservation assertion was impossible with href-only URLs.
- **Fix:** Changed test to use `body_text` with an inline URL string instead of `body_html` with an anchor tag. Both UTM stripping and non-tracking param preservation are now verifiable. Security invariant unchanged.
- **Files modified:** tests/test_sanitizer.py
- **Verification:** All 13 tests pass including test_utm_params_stripped
- **Committed in:** 54c75a6 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — test behavior correction, security invariant preserved)
**Impact on plan:** Necessary correction — the test was asserting something that could never be true given how HTML extraction works. No security assertion was weakened.

## Issues Encountered

None — implementation followed the research patterns exactly. The single deviation (test update) was a test fixture design issue, not an implementation bug.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- `sanitize(raw, config) -> CleanMessage` is fully implemented and tested
- All 13 PRIV tests pass: `pytest tests/ -q` exits 0
- PRIV-01 through PRIV-07 requirements satisfied
- Phase 2 (IMAP fetcher) can now create RawMessage instances and call sanitize() with confidence
- The sanitizer correctly handles: HTML bodies, plain text fallback, empty bodies, subject PII, sender domain extraction, configurable extra patterns, and body truncation

## Self-Check: PASSED

- FOUND: src/sanitizer.py (155 lines, exceeds min_lines: 80)
- FOUND: tests/test_sanitizer.py (340 lines, exceeds min_lines: 100)
- FOUND: sanitize export in src/sanitizer.py
- FOUND: TRACKING_PARAMS export in src/sanitizer.py
- FOUND: from src.models import RawMessage, CleanMessage, SanitizerConfig in src/sanitizer.py
- FOUND: from bs4 import BeautifulSoup in src/sanitizer.py
- FOUND: from urllib.parse import in src/sanitizer.py
- FOUND commit: 54c75a6

---
*Phase: 01-foundation-and-privacy-sanitizer*
*Completed: 2026-03-11*
