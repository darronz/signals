---
phase: 1
slug: foundation-and-privacy-sanitizer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0 |
| **Config file** | pyproject.toml [tool.pytest.ini_options] or pytest.ini — Wave 0 installs |
| **Quick run command** | `pytest tests/test_sanitizer.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_sanitizer.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | PRIV-01 | unit | `pytest tests/test_sanitizer.py::test_output_is_plain_text -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | PRIV-02 | unit | `pytest tests/test_sanitizer.py::test_tracking_pixels_removed -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | PRIV-03 | unit | `pytest tests/test_sanitizer.py::test_utm_params_stripped -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | PRIV-04 | unit | `pytest tests/test_sanitizer.py::test_no_user_email_in_output -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | PRIV-05 | unit | `pytest tests/test_sanitizer.py::test_extra_patterns -x` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 1 | PRIV-06 | unit | `pytest tests/test_sanitizer.py::test_sender_domain_only -x` | ❌ W0 | ⬜ pending |
| 1-01-07 | 01 | 1 | PRIV-07 | unit | `pytest tests/test_sanitizer.py::test_truncation -x` | ❌ W0 | ⬜ pending |
| 1-01-08 | 01 | 1 | PRIV-08 | static/unit | `pytest tests/test_sanitizer.py::test_clean_message_has_no_headers -x` | ❌ W0 | ⬜ pending |
| 1-01-09 | 01 | 1 | DOCS-02 | smoke | `pytest tests/test_sanitizer.py::test_env_example_exists -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — makes tests/ a package
- [ ] `tests/conftest.py` — shared `config` fixture with test values
- [ ] `tests/test_sanitizer.py` — all PRIV-0x and DOCS-02 test stubs
- [ ] `pyproject.toml [tool.pytest.ini_options]` — point at `src/` for imports
- [ ] Framework install: `pip install pytest>=8.0`

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
