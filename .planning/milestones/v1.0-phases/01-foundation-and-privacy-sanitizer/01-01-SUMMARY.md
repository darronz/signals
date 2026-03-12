---
phase: 01-foundation-and-privacy-sanitizer
plan: "01"
subsystem: testing
tags: [python, beautifulsoup4, python-dotenv, pytest, dataclasses, privacy, sanitizer]

# Dependency graph
requires: []
provides:
  - RawMessage, CleanMessage, SanitizerConfig dataclasses (src/models.py)
  - load_config() and load_sanitizer_config() config loaders (src/config.py)
  - sanitize() function stub raising NotImplementedError (src/sanitizer.py)
  - Complete .env.example with all 18 config keys and descriptive comments
  - 13-test test_sanitizer.py in RED state for Plan 02 TDD cycles
  - pytest infrastructure with conftest.py shared config fixture
  - requirements.txt + requirements-dev.txt + pyproject.toml with pytest config
affects:
  - 01-02 (sanitizer implementation — all 13 tests are the Plan 02 TDD target)
  - 01-03 and later phases (import src.models for data contracts)

# Tech tracking
tech-stack:
  added:
    - beautifulsoup4>=4.12.0 (installed 4.14.3)
    - python-dotenv>=1.0.0 (installed 1.2.2)
    - pytest>=8.0 (installed 9.0.2)
  patterns:
    - Privacy boundary enforced by type design — CleanMessage has no header fields (PRIV-08)
    - No load_dotenv() at import time — only inside functions to prevent test failures
    - Tests inject SanitizerConfig directly rather than calling load_config()
    - Virtual environment (.venv/) for dependency isolation

key-files:
  created:
    - src/models.py
    - src/config.py
    - src/sanitizer.py
    - tests/test_sanitizer.py
    - tests/conftest.py
    - tests/__init__.py
    - .env.example
    - pyproject.toml
    - requirements.txt
    - requirements-dev.txt
    - .gitignore
  modified: []

key-decisions:
  - "dataclasses used over pydantic — sufficient for contracts without extra dependency"
  - "CleanMessage has exactly 4 fields (no headers) — privacy boundary enforced by type, not runtime checks"
  - "load_dotenv() deferred to function bodies only — prevents test import failures without .env present"
  - "All img tags removed (not just 1x1 tracking pixels) — defensive approach avoids false negatives"
  - "Virtual environment (.venv/) required — system Python is externally managed on macOS"

patterns-established:
  - "Pattern: RawMessage -> sanitize() -> CleanMessage is the privacy contract; only CleanMessage crosses the boundary"
  - "Pattern: Tests inject SanitizerConfig directly without touching load_config() or dotenv"
  - "Pattern: pyproject.toml [tool.pytest.ini_options] with pythonpath=[.] enables from src.models imports in tests"

requirements-completed: [PRIV-08, DOCS-02]

# Metrics
duration: 11min
completed: 2026-03-11
---

# Phase 1 Plan 01: Foundation and Privacy Sanitizer Summary

**Typed privacy contract (RawMessage/CleanMessage dataclasses), config loader, sanitizer stub, .env.example, and 13-test TDD scaffold ready for Plan 02 implementation**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-11T22:05:21Z
- **Completed:** 2026-03-11T22:16:14Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Established the typed privacy boundary: CleanMessage has exactly 4 fields (no headers), enforcing PRIV-08 by type design rather than runtime checks
- Created complete .env.example with all 18 config keys and descriptive comments (DOCS-02)
- Built 13-test TDD scaffold covering all PRIV-01 through PRIV-08 requirements plus edge cases — 2 structural tests pass immediately, 11 fail with NotImplementedError (correct RED state for Plan 02)

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffolding, data contracts, and configuration** - `c158d54` (feat)
2. **Task 2: Test infrastructure with failing test stubs** - `d55ee59` (test)

## Files Created/Modified

- `src/models.py` — RawMessage, CleanMessage (4 fields, no headers), SanitizerConfig dataclasses
- `src/config.py` — load_config() and load_sanitizer_config(), no import-time side effects
- `src/sanitizer.py` — stub with correct signature, raises NotImplementedError
- `src/__init__.py` — makes src/ an importable package
- `tests/test_sanitizer.py` — 13 tests covering PRIV-01 through PRIV-08, DOCS-02, and 3 edge cases
- `tests/conftest.py` — shared config fixture (SanitizerConfig with known test values)
- `tests/__init__.py` — makes tests/ a package
- `.env.example` — all 18 config keys with descriptive comments
- `pyproject.toml` — project metadata + pytest config (pythonpath=["."])
- `requirements.txt` — beautifulsoup4, python-dotenv
- `requirements-dev.txt` — includes requirements.txt + pytest
- `.gitignore` — excludes .env, __pycache__, .venv, .pytest_cache, output/, dist/

## Decisions Made

- Used `dataclasses` over `pydantic` — sufficient for typed contracts without an additional dependency
- Privacy boundary enforced by type design (no header fields on CleanMessage), not by runtime validation
- `load_dotenv()` deferred to function bodies — prevents test import failures when no `.env` file is present (Pitfall 5 from research)
- Virtual environment (.venv/) required — system Python is externally managed on macOS 25.x

## Deviations from Plan

None — plan executed exactly as written.

**Note:** pip install required creating a `.venv/` virtual environment due to the externally-managed Python environment on macOS. This is normal for modern macOS Python installs. The `.venv/` directory is gitignored.

## Issues Encountered

- pip install to system Python blocked by PEP 668 (externally-managed environment). Resolved by creating `.venv/` virtual environment.
- PyPI connection initially slow (connection timeouts), succeeded on retry. No impact on deliverables.

## User Setup Required

None — no external service configuration required for this plan.

To use the virtual environment created during this plan:
```bash
source .venv/bin/activate
```

## Next Phase Readiness

- All 13 tests are in RED state — Plan 02 can immediately begin TDD cycles against them
- `from src.models import RawMessage, CleanMessage, SanitizerConfig` works
- `from src.sanitizer import sanitize` works (stub raises NotImplementedError at call time, not import)
- .env.example documents all required config keys for Phase 2 IMAP integration

## Self-Check: PASSED

- FOUND: src/models.py
- FOUND: src/config.py
- FOUND: src/sanitizer.py
- FOUND: tests/test_sanitizer.py
- FOUND: .env.example
- FOUND: 01-01-SUMMARY.md
- FOUND commit: c158d54 (feat: scaffolding)
- FOUND commit: d55ee59 (test: infrastructure)
- FOUND commit: 201d21f (docs: metadata)

---
*Phase: 01-foundation-and-privacy-sanitizer*
*Completed: 2026-03-11*
