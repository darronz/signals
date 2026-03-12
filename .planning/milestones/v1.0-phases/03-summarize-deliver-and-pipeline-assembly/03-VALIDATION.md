---
phase: 3
slug: summarize-deliver-and-pipeline-assembly
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (already installed in .venv) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` already configured |
| **Quick run command** | `pytest tests/test_summarize.py tests/test_deliver.py tests/test_daily.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_summarize.py tests/test_deliver.py tests/test_daily.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | SUMM-01 | unit | `pytest tests/test_summarize.py::test_call_claude_success -x` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | SUMM-01 | unit | `pytest tests/test_summarize.py::test_call_claude_binary_not_found -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | SUMM-01 | unit | `pytest tests/test_summarize.py::test_call_claude_nonzero_exit -x` | ❌ W0 | ⬜ pending |
| 3-01-04 | 01 | 1 | SUMM-02 | unit | `pytest tests/test_summarize.py::test_prompt_contains_theme_instruction -x` | ❌ W0 | ⬜ pending |
| 3-01-05 | 01 | 1 | SUMM-05 | unit | `pytest tests/test_summarize.py::test_prompt_contains_word_target -x` | ❌ W0 | ⬜ pending |
| 3-01-06 | 01 | 1 | SUMM-06 | unit | `pytest tests/test_summarize.py::test_prompt_contains_sources_instruction -x` | ❌ W0 | ⬜ pending |
| 3-01-07 | 01 | 1 | SUMM-07 | unit | `pytest tests/test_summarize.py::test_prompt_loaded_from_file -x` | ❌ W0 | ⬜ pending |
| 3-01-08 | 01 | 1 | SUMM-07 | unit | `pytest tests/test_summarize.py::test_prompt_override_path -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | DLVR-01 | unit | `pytest tests/test_deliver.py::test_send_email_calls_starttls -x` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | DLVR-01 | unit | `pytest tests/test_deliver.py::test_email_has_html_part -x` | ❌ W0 | ⬜ pending |
| 3-02-03 | 02 | 1 | DLVR-02 | unit | `pytest tests/test_deliver.py::test_save_archive_creates_file -x` | ❌ W0 | ⬜ pending |
| 3-02-04 | 02 | 1 | DLVR-02 | unit | `pytest tests/test_deliver.py::test_save_archive_filename_format -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 2 | OPS-01 | unit | `pytest tests/test_daily.py::test_dry_run_no_claude_call -x` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 2 | OPS-01 | unit | `pytest tests/test_daily.py::test_dry_run_prints_clean_text -x` | ❌ W0 | ⬜ pending |
| 3-03-03 | 03 | 2 | OPS-02 | unit | `pytest tests/test_daily.py::test_since_flag_overrides_config -x` | ❌ W0 | ⬜ pending |
| 3-03-04 | 03 | 2 | OPS-02 | unit | `pytest tests/test_daily.py::test_verbose_sets_debug_level -x` | ❌ W0 | ⬜ pending |
| 3-03-05 | 03 | 2 | OPS-03 | unit | `pytest tests/test_daily.py::test_exit_1_on_missing_config -x` | ❌ W0 | ⬜ pending |
| 3-03-06 | 03 | 2 | OPS-03 | unit | `pytest tests/test_daily.py::test_exit_2_no_newsletters -x` | ❌ W0 | ⬜ pending |
| 3-03-07 | 03 | 2 | OPS-03 | unit | `pytest tests/test_daily.py::test_exit_3_claude_error -x` | ❌ W0 | ⬜ pending |
| 3-04-01 | 04 | 2 | OPS-04 | smoke | `bash tests/test_run_digest_sh.sh` | ❌ W0 | ⬜ pending |
| 3-04-02 | 04 | 2 | OPS-05 | smoke | Manual inspection of script content | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_summarize.py` — stubs for SUMM-01 through SUMM-07
- [ ] `tests/test_deliver.py` — stubs for DLVR-01, DLVR-02
- [ ] `tests/test_daily.py` — stubs for OPS-01, OPS-02, OPS-03
- [ ] `prompts/summarize.txt` — required by SUMM-07

*Existing infrastructure (pytest, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| run-digest.sh exits non-zero if Bridge not on port 1143 | OPS-04 | Requires Bridge running | Start Bridge, run `bash scripts/run-digest.sh`, verify exit code |
| dry-run.sh delegates to run-digest.sh --dry-run | OPS-05 | Script inspection | `cat scripts/dry-run.sh`, confirm it calls `run-digest.sh --dry-run` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
