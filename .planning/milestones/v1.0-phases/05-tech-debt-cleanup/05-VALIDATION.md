---
phase: 5
slug: tech-debt-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pyproject.toml [tool.pytest.ini_options]) |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/ -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | SUMM-05 | unit | `.venv/bin/python -m pytest tests/test_summarize.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | DLVR-04 | unit | `.venv/bin/python -m pytest tests/test_weekly.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | OPS-04 | manual/smoke | `grep 'IMAP_PORT' scripts/run-digest.sh` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 1 | OPS-04 | smoke | `bash -n scripts/run-weekly.sh` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_summarize.py` — new test for SUMM-05 word target injection into prompt
- [ ] `tests/test_weekly.py` — new test for DLVR-04 weekly subject line
- [ ] Shell script verification via grep/syntax check (no bash test framework)

*Existing infrastructure covers framework needs; only new test cases required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `run-digest.sh` reads IMAP_PORT from .env | OPS-04 | No bash test framework in project | `grep 'IMAP_PORT' scripts/run-digest.sh` — verify variable used instead of 1143 |
| `run-weekly.sh` has prerequisite checks | OPS-04 | Shell script, not Python | `bash -n scripts/run-weekly.sh` + manual review of check structure |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
