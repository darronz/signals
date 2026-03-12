---
phase: 4
slug: weekly-rollup-cron-and-documentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (already installed in .venv) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` already configured |
| **Quick run command** | `pytest tests/test_weekly.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_weekly.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | DLVR-03 | unit | `pytest tests/test_weekly.py::test_find_daily_digests_returns_files_in_window -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | DLVR-03 | unit | `pytest tests/test_weekly.py::test_find_daily_digests_excludes_old_files -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | DLVR-03 | unit | `pytest tests/test_weekly.py::test_find_daily_digests_ignores_weekly_files -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | DLVR-03 | unit | `pytest tests/test_weekly.py::test_format_weekly_input -x` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | DLVR-03 | unit | `pytest tests/test_weekly.py::test_weekly_calls_claude_with_weekly_prompt -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | DLVR-04 | unit | `pytest tests/test_weekly.py::test_weekly_archive_filename_format -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | DLVR-04 | unit | `pytest tests/test_weekly.py::test_save_weekly_archive_creates_file -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 1 | DLVR-04 | unit | `pytest tests/test_weekly.py::test_weekly_sends_email_when_configured -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 1 | DLVR-03/04 | unit | `pytest tests/test_weekly.py::test_exit_2_no_daily_files -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 1 | DLVR-03/04 | unit | `pytest tests/test_weekly.py::test_dry_run_no_claude_call -x` | ❌ W0 | ⬜ pending |
| 04-03-03 | 03 | 1 | DLVR-03/04 | unit | `pytest tests/test_weekly.py::test_exit_3_claude_error -x` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 2 | DOCS-01 | smoke | `pytest tests/test_weekly.py::test_readme_exists -x` | ❌ W0 | ⬜ pending |
| 04-04-02 | 04 | 2 | DOCS-01 | smoke | `pytest tests/test_weekly.py::test_readme_contains_all_config_keys -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_weekly.py` — stubs for DLVR-03, DLVR-04, DOCS-01 smoke checks
- [ ] `scripts/weekly.py` — module must exist for imports
- [ ] `prompts/weekly.txt` — weekly synthesis prompt for Claude

*Existing infrastructure covers framework setup — pytest already configured in pyproject.toml.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Weekly prompt produces coherent synthesis | DLVR-03 | Requires real daily digest data + Claude API call | Run `python scripts/weekly.py` against 7+ real daily digests; review output for week-over-week themes vs individual day rehash |
| README enables new user setup | DOCS-01 | Requires fresh-eyes human walkthrough | Follow README from scratch on a clean environment; verify `--dry-run` succeeds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
