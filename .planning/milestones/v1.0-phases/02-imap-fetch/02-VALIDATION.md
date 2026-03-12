---
phase: 2
slug: imap-fetch
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_fetch.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_fetch.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | FETCH-01 | unit (mock) | `pytest tests/test_fetch.py::test_starttls_called -x` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | FETCH-02 | unit (mock) | `pytest tests/test_fetch.py::test_returns_raw_messages_for_matching_uids -x` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | FETCH-03 | unit (mock) | `pytest tests/test_fetch.py::test_sender_filter_applied_without_folder -x` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 1 | FETCH-04 | unit (mock) | `pytest tests/test_fetch.py::test_time_window_filter -x` | ❌ W0 | ⬜ pending |
| 2-01-05 | 01 | 1 | FETCH-05 | unit (no mock) | `pytest tests/test_fetch.py::test_html_part_preferred -x` | ❌ W0 | ⬜ pending |
| 2-01-06 | 01 | 1 | FETCH-02 | unit (mock) | `pytest tests/test_fetch.py::test_uid_mode_used -x` | ❌ W0 | ⬜ pending |
| 2-01-07 | 01 | 1 | FETCH-04 | unit (mock) | `pytest tests/test_fetch.py::test_empty_folder_returns_empty_list -x` | ❌ W0 | ⬜ pending |
| 2-01-08 | 01 | 1 | FETCH-05 | unit (no mock) | `pytest tests/test_fetch.py::test_charset_fallback -x` | ❌ W0 | ⬜ pending |
| 2-01-09 | 01 | 1 | FETCH-01 | unit (mock) | `pytest tests/test_fetch.py::test_connection_not_left_open_on_error -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_fetch.py` — stubs for all FETCH-0x requirements using mock IMAP
- [ ] No framework changes needed — pytest already installed and configured

*Existing infrastructure: `pyproject.toml` with `pythonpath=["."]` and `testpaths=["tests"]` covers the new test file automatically*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Bridge connection succeeds | FETCH-01 | Requires running Proton Mail Bridge with valid credentials | Start Bridge, run `pytest tests/test_fetch_integration.py -x` (separate integration test file) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
