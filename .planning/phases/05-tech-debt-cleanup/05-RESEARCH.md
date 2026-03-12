# Phase 5: Tech Debt Cleanup - Research

**Researched:** 2026-03-12
**Domain:** Python config wiring, bash shell scripting, email subject parameterization
**Confidence:** HIGH

---

## Summary

Phase 5 closes three integration gaps identified in the v1.0 audit. All three gaps were
discovered by reading the actual source code and comparing it against requirements:

**Gap 1 (SUMM-05):** `DIGEST_WORD_TARGET` is correctly read from `.env` into `config["digest_word_target"]`
(src/config.py line 61), but `call_claude()` in `src/summarize.py` never injects this value into the
prompt. The prompt file (`prompts/summarize.txt`) hardcodes "~500 words" as a literal string. The fix
is: make the prompt template contain a placeholder like `{word_target}`, and have `call_claude()`
(or a wrapper) substitute `config["digest_word_target"]` before passing the prompt to Claude.

**Gap 2 (DLVR-04):** `scripts/weekly.py` already saves a weekly markdown archive and calls
`send_digest_email()` when `OUTPUT_FORMAT=email`. However, `send_digest_email()` in `src/deliver.py`
always sets `Subject = "Daily Digest — YYYY-MM-DD"` (hardcoded on line 51). When called from the weekly
pipeline, the subject must say "Weekly Digest — Week XX, YYYY". The function needs a `subject`
parameter (or a new `send_weekly_email()` wrapper), and the test suite must verify the weekly subject.

**Gap 3 (OPS-04):** `scripts/run-digest.sh` hardcodes port 1143 in the `nc` prerequisite check
(line 24: `nc -z 127.0.0.1 1143`) instead of reading `IMAP_PORT` from `.env`. `scripts/run-weekly.sh`
does not exist yet; it must be created with identical prerequisite checks and invoke `scripts/weekly.py`.

**Primary recommendation:** Three surgical changes — (1) prompt template substitution in summarize.py,
(2) subject parameter in send_digest_email / weekly caller, (3) fix run-digest.sh + create run-weekly.sh.
Zero new dependencies needed. All existing tests must continue to pass.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SUMM-05 | Digest target length is configurable (default ~500 words) | `config["digest_word_target"]` exists but is never read by call_claude(); prompt template substitution closes the gap |
| DLVR-04 | Weekly digest is sent as HTML email and saved as markdown file | weekly.py email path exists but subject is wrong ("Daily Digest"); send_digest_email needs a subject parameter |
| OPS-04 | Cron wrapper script checks Bridge is running and Claude CLI is available | run-digest.sh exists with checks but hardcodes port 1143; run-weekly.sh is missing entirely |
</phase_requirements>

---

## Gap Analysis: What Exists vs What's Required

### SUMM-05 — Configurable Word Target

**What exists (HIGH confidence — source code read):**
- `src/config.py` line 61: `"digest_word_target": int(os.environ.get("DIGEST_WORD_TARGET", "500"))`
- `.env.example` line 52-53: `DIGEST_WORD_TARGET=500` documented with comment
- `src/summarize.py` `call_claude()`: receives `config` dict but never reads `config["digest_word_target"]`
- `prompts/summarize.txt` line 19: hardcodes `"Target ~500 words total."`
- `tests/test_summarize.py` line 158-162: `test_prompt_contains_word_target` only checks that "500" or "word" appears — passes today but does not verify runtime injection

**What's missing:**
The config key is loaded but never used. Changing `DIGEST_WORD_TARGET=800` in `.env` has no effect on the prompt.

**Fix pattern (two options):**

Option A — Template substitution at call time (preferred):
1. Change `prompts/summarize.txt` to use `{word_target}` placeholder
2. In `call_claude()`, after reading the prompt file, do: `prompt = prompt.format(word_target=config.get("digest_word_target", 500))`
3. Weekly prompt (`prompts/weekly.txt`) may also want a word target — check if SUMM-05 scope includes weekly

Option B — Pass word target as a separate prompt suffix appended by caller:
- More fragile; pollutes the clean prompt file pattern established in SUMM-07 decision

Option A is consistent with the existing principle "prompt text lives in prompts/ file" while still
making it configurable.

**Risk:** `str.format()` will raise `KeyError` if the prompt file contains any literal `{...}` that
is NOT a placeholder. Review both prompt files. Current `prompts/summarize.txt` contains no curly
braces, so this is safe. Use `.format(word_target=...)` (keyword-only) to avoid positional conflicts.

---

### DLVR-04 — Weekly Email with Correct Subject

**What exists (HIGH confidence — source code read):**
- `scripts/weekly.py` lines 240-252: calls `send_digest_email(digest, html_digest, config)` when `output_format == "email"`
- `src/deliver.py` line 51: `msg["Subject"] = f"Daily Digest \u2014 {today}"` — hardcoded "Daily Digest"
- `tests/test_deliver.py` lines 99-112: `test_email_subject_contains_date` asserts `"Daily Digest" in subject` — this test MUST continue to pass for the daily pipeline
- `tests/test_weekly.py` lines 357-376: `TestMainDelivery.test_sends_email_when_output_format_is_email` asserts `mock_send.assert_called_once()` but does NOT assert the subject

**What's missing:**
The weekly email arrives with subject "Daily Digest — YYYY-MM-DD" instead of "Weekly Digest — Week XX, YYYY".
Success criterion 2 requires weekly emails arrive with the correct weekly subject.

**Fix pattern:**

Add a `subject` parameter to `send_digest_email()` with a default:

```python
def send_digest_email(
    markdown_text: str,
    html_text: str,
    config: dict,
    subject: str | None = None,
) -> None:
    today = date.today().isoformat()
    if subject is None:
        subject = f"Daily Digest \u2014 {today}"
    msg["Subject"] = subject
    ...
```

Then in `scripts/weekly.py` main(), compute the weekly subject before calling:

```python
iso = date.today().isocalendar()
subject = f"Weekly Digest \u2014 Week {iso.week:02d}, {iso.year}"
send_digest_email(digest, html_digest, config, subject=subject)
```

**Backward compatibility:** Existing daily pipeline calls `send_digest_email(digest, html_digest, config)` — no change needed; default subject is "Daily Digest — date". All existing tests remain green.

**New test needed:** A test in `tests/test_weekly.py` that asserts the `subject` argument passed to
`send_digest_email` contains "Weekly" and the week number.

---

### OPS-04 — Shell Script Prerequisites

**What exists (HIGH confidence — source code read):**

`scripts/run-digest.sh`:
- Line 24: `if ! nc -z 127.0.0.1 1143; then` — port **hardcoded** as 1143
- Line 31-35: Claude CLI check — correct, reads from PATH
- Does NOT source `.env` before the port check — so even after fix, we need to load `IMAP_PORT` from `.env`

**What's missing:**
1. `run-digest.sh` must read `IMAP_PORT` from `.env` instead of hardcoding 1143
2. `scripts/run-weekly.sh` does not exist; must be created

**Fix for run-digest.sh:**

Bash cannot call Python's `load_dotenv`. The standard bash pattern for reading a `.env` file is:

```bash
# Load .env if present (for IMAP_PORT etc)
if [ -f "${PROJECT_DIR}/.env" ]; then
    # Export only simple KEY=VALUE lines; skip comments and blanks
    set -a
    # shellcheck disable=SC1090
    source "${PROJECT_DIR}/.env"
    set +a
fi

IMAP_PORT="${IMAP_PORT:-1143}"

if ! nc -z 127.0.0.1 "${IMAP_PORT}"; then
    echo "ERROR: Proton Mail Bridge is not running on port ${IMAP_PORT}." >&2
    exit 1
fi
```

**Caveat:** `source .env` in bash works only if the `.env` file has no values with spaces that are unquoted, and no bash-incompatible syntax. The project's `.env.example` uses simple `KEY=VALUE` format with no subshells or complex quoting, so this is safe.

**Alternative (more robust):** Use `grep`/`awk` to extract only IMAP_PORT without sourcing:

```bash
IMAP_PORT=$(grep -E '^IMAP_PORT=' "${PROJECT_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
IMAP_PORT="${IMAP_PORT:-1143}"
```

This avoids sourcing the full `.env` in bash (avoids accidental side effects from other vars), is more portable, and matches the minimal-footprint principle. Recommended over full `source .env`.

**run-weekly.sh spec (from success criterion 4):**
- Same prerequisite checks as `run-digest.sh`: Bridge IMAP port check + Claude CLI check
- Activates `.venv`
- Invokes `python "${PROJECT_DIR}/scripts/weekly.py" "$@"`
- Same exit code contract (0/1/2/3)

Template (copy structure from `run-digest.sh`, change only the Python invocation and script name in comments):

```bash
#!/usr/bin/env bash
# run-weekly.sh — cron wrapper for the Signals weekly digest rollup
# ...same header pattern as run-digest.sh...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

# --- Load IMAP_PORT from .env ---
IMAP_PORT=$(grep -E '^IMAP_PORT=' "${PROJECT_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
IMAP_PORT="${IMAP_PORT:-1143}"

# --- Prerequisite: Proton Mail Bridge IMAP port must be open ---
if ! nc -z 127.0.0.1 "${IMAP_PORT}"; then
    echo "ERROR: Proton Mail Bridge is not running on port ${IMAP_PORT}." >&2
    echo "Please start Bridge and try again." >&2
    exit 1
fi

# --- Prerequisite: claude CLI must be available ---
if ! command -v claude &>/dev/null; then
    echo "ERROR: 'claude' CLI not found in PATH." >&2
    echo "Install Claude Code CLI and ensure it is on your PATH." >&2
    exit 1
fi

# --- Activate virtual environment ---
source "${PROJECT_DIR}/.venv/bin/activate"

# --- Run the weekly pipeline ---
python "${PROJECT_DIR}/scripts/weekly.py" "$@"
```

---

## Standard Stack

No new dependencies introduced. This phase uses only what is already installed:

### Core (all already present)
| Component | Version | Purpose |
|-----------|---------|---------|
| Python str.format() | stdlib | Template substitution for word target |
| bash grep + cut | system | Extract IMAP_PORT from .env in shell scripts |
| src/deliver.send_digest_email | project | Reused with new subject parameter |
| pytest + unittest.mock | already in dev deps | New tests for subject and run-weekly.sh |

### Installation
No new installs required.

---

## Architecture Patterns

### Pattern 1: Prompt Template Substitution at Call Time

The `call_claude()` function already reads the prompt file. Adding a single `.format()` call after
reading is the least-invasive change consistent with the "prompt text lives in file" principle:

```python
# In src/summarize.py call_claude()
prompt = Path(prompt_file).read_text(encoding="utf-8")
# Substitute configurable values before passing to Claude
word_target = config.get("digest_word_target", 500)
prompt = prompt.format(word_target=word_target)
```

And update `prompts/summarize.txt` line 19:
```
Be concise. Target ~{word_target} words total.
```

### Pattern 2: Optional Subject Parameter with Backward-Compatible Default

```python
def send_digest_email(
    markdown_text: str,
    html_text: str,
    config: dict,
    subject: str | None = None,
) -> None:
    today = date.today().isoformat()
    email_subject = subject if subject is not None else f"Daily Digest \u2014 {today}"
    msg["Subject"] = email_subject
```

This keeps all existing tests green (they call the function without a subject argument).

### Pattern 3: .env Variable Extraction in Bash (grep/cut)

Reading a single variable from `.env` in bash without sourcing the entire file:

```bash
VAR=$(grep -E '^VAR_NAME=' "${PROJECT_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
VAR="${VAR:-default_value}"
```

The `2>/dev/null` handles the case where `.env` doesn't exist. The `:-default_value` fallback handles
missing/empty values. `tr -d '[:space:]'` strips any trailing whitespace or carriage returns.

### Anti-Patterns to Avoid

- **Sourcing the full .env in bash:** `source .env` can accidentally override shell variables and
  execute arbitrary code if `.env` contains subshells. Use targeted grep/cut for the one variable needed.
- **Modifying call_claude's function signature for word_target:** Adding `word_target` as a new parameter
  would require updating all callers (daily.py, weekly.py) and all tests. Using `config.get()` inside
  the function is simpler and consistent with how `claude_cmd` and `claude_model` are already accessed.
- **Hardcoding "Weekly Digest" in deliver.py:** The delivery module should stay generic. The subject
  should be computed in the caller (weekly.py) and passed in. This keeps deliver.py focused on
  transport, not on knowing whether it's a daily or weekly digest.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var template substitution | Custom regex/replace for {word_target} | Python str.format() with keyword args | Built-in, raises KeyError on typos, no extra dep |
| Parsing .env in bash | Full bash .env parser | Single `grep \| cut` line | Only one var needed; full parse is overkill and risky |

---

## Common Pitfalls

### Pitfall 1: str.format() KeyError on Existing Prompt Content
**What goes wrong:** If `prompts/summarize.txt` or `prompts/weekly.txt` contain any literal `{text}`
(e.g., in examples), `prompt.format(word_target=500)` raises `KeyError: 'text'`.
**Why it happens:** `str.format()` interprets all `{...}` as placeholders.
**How to avoid:** Review both prompt files before adding `.format()` call. Current `prompts/summarize.txt`
and `prompts/weekly.txt` contain no curly braces — confirmed by reading file content.
**Warning signs:** `KeyError` in `call_claude()` at runtime; will also appear in unit tests.

### Pitfall 2: Breaking the Existing Daily Subject Test
**What goes wrong:** Changing `send_digest_email()` signature breaks `test_email_subject_contains_date`
which asserts `"Daily Digest" in subject`.
**Why it happens:** The default subject in the refactored function must still produce "Daily Digest".
**How to avoid:** Use `subject: str | None = None` with `if subject is None: subject = f"Daily Digest..."`.
The existing test calls without subject argument → gets daily subject → test passes.

### Pitfall 3: run-digest.sh Port Hardcode in Error Message
**What goes wrong:** Fix the `nc` command to use `${IMAP_PORT}` but forget to update the error message
on the next line, which still says "port 1143".
**How to avoid:** Update both the `nc -z` line AND the error `echo` to use `${IMAP_PORT}`.

### Pitfall 4: run-weekly.sh Missing chmod +x
**What goes wrong:** Creating `run-weekly.sh` without making it executable — cron fails silently or
with a permission error.
**How to avoid:** `chmod +x scripts/run-weekly.sh` immediately after creation, or note in plan task.

### Pitfall 5: Weekly Prompt File Also Hardcodes Word Target
**What goes wrong:** Fixing `prompts/summarize.txt` but not `prompts/weekly.txt` — weekly digest
word count remains hardcoded.
**How to avoid:** Check `prompts/weekly.txt` for a hardcoded word count and apply the same
`{word_target}` substitution. `call_claude()` is shared by both pipelines, so the fix applies once.

---

## Code Examples

### SUMM-05: Prompt Template Substitution

Updated `prompts/summarize.txt` (only line 19 changes):
```
Be concise. Target ~{word_target} words total. Group by topic, not by source.
```

Updated `src/summarize.py` `call_claude()`:
```python
def call_claude(prompt_file: str, newsletter_text: str, config: dict) -> str:
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    # Substitute configurable word target (SUMM-05)
    word_target = config.get("digest_word_target", 500)
    prompt = prompt.format(word_target=word_target)

    cmd = [config["claude_cmd"], "-p", prompt, "--output-format", "text"]
    ...
```

Test update for SUMM-05:
```python
def test_word_target_injected_into_prompt(tmp_path):
    """DIGEST_WORD_TARGET from config is substituted into the prompt."""
    prompt_file = tmp_path / "summarize.txt"
    prompt_file.write_text("Target ~{word_target} words.", encoding="utf-8")
    cfg = {"claude_cmd": "claude", "claude_model": "", "digest_word_target": 800}

    mock_result = MagicMock(returncode=0, stdout="digest", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from src.summarize import call_claude
        call_claude(str(prompt_file), "text", cfg)

    cmd = mock_run.call_args.args[0]
    assert "800" in cmd  # word_target was substituted, not 500
```

### DLVR-04: Weekly Email Subject

Updated `src/deliver.py` `send_digest_email()` signature:
```python
def send_digest_email(
    markdown_text: str,
    html_text: str,
    config: dict,
    subject: str | None = None,
) -> None:
    today = date.today().isoformat()
    email_subject = subject if subject is not None else f"Daily Digest \u2014 {today}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_subject
    ...
```

Updated `scripts/weekly.py` delivery block:
```python
if output_format == "email":
    iso = date.today().isocalendar()
    subject = f"Weekly Digest \u2014 Week {iso.week:02d}, {iso.year}"
    html_digest = markdown_to_html(digest)
    send_digest_email(digest, html_digest, config, subject=subject)
```

New test in `tests/test_weekly.py`:
```python
def test_weekly_email_subject_contains_weekly(self, tmp_path):
    """Weekly email subject contains 'Weekly' and week number, not 'Daily'."""
    import scripts.weekly as w

    today = date.today().isoformat()
    (tmp_path / f"digest-{today}.md").write_text("Content", encoding="utf-8")
    cfg = _minimal_config(tmp_path, output_format="email")

    with patch.object(w, "load_config", return_value=cfg), \
         patch.object(w, "call_claude", return_value="# Weekly\n\nContent."), \
         patch.object(w, "send_digest_email") as mock_send, \
         patch.object(w, "markdown_to_html", return_value="<html></html>"), \
         patch("sys.argv", ["weekly.py"]):
        with pytest.raises(SystemExit):
            w.main()

    call_args = mock_send.call_args
    subject_kwarg = call_args.kwargs.get("subject") or call_args.args[3]
    assert "Weekly" in subject_kwarg
    assert "Daily" not in subject_kwarg
```

### OPS-04: run-digest.sh Port Fix

Lines to change in `scripts/run-digest.sh`:

Before:
```bash
# --- Prerequisite: Proton Mail Bridge IMAP port must be open ---
if ! nc -z 127.0.0.1 1143; then
    echo "ERROR: Proton Mail Bridge is not running on port 1143." >&2
```

After:
```bash
# --- Load IMAP_PORT from .env (default: 1143) ---
IMAP_PORT=$(grep -E '^IMAP_PORT=' "${PROJECT_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
IMAP_PORT="${IMAP_PORT:-1143}"

# --- Prerequisite: Proton Mail Bridge IMAP port must be open ---
if ! nc -z 127.0.0.1 "${IMAP_PORT}"; then
    echo "ERROR: Proton Mail Bridge is not running on port ${IMAP_PORT}." >&2
```

---

## Validation Architecture

nyquist_validation is enabled (config.json: `"nyquist_validation": true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pyproject.toml [tool.pytest.ini_options]) |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/python -m pytest tests/ -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -v` |

**Current baseline:** 96 passed, 3 skipped (2026-03-12). All tests green before Phase 5 begins.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUMM-05 | DIGEST_WORD_TARGET substituted into prompt at call time | unit | `.venv/bin/python -m pytest tests/test_summarize.py -x -q` | needs new test |
| DLVR-04 | Weekly email has "Weekly Digest" subject (not "Daily Digest") | unit | `.venv/bin/python -m pytest tests/test_weekly.py -x -q` | needs new test |
| DLVR-04 | Weekly archive markdown saved (already tested) | unit | `.venv/bin/python -m pytest tests/test_weekly.py::TestMainDelivery::test_saves_weekly_archive_on_success` | ✅ exists |
| OPS-04 | run-digest.sh uses IMAP_PORT var not hardcoded 1143 | manual/smoke | `grep 'IMAP_PORT' scripts/run-digest.sh` | ❌ Wave 0 |
| OPS-04 | run-weekly.sh exists with same prerequisite checks | smoke | `bash -n scripts/run-weekly.sh` (syntax check) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/ -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -v`
- **Phase gate:** Full suite green (96+ tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test in `tests/test_summarize.py` — covers SUMM-05 word target injection
- [ ] New test in `tests/test_weekly.py` — covers DLVR-04 weekly subject
- [ ] `scripts/run-weekly.sh` does not exist (created as part of OPS-04 task, not a test gap)
- Note: Shell script behavior (IMAP_PORT reading) is verified by code review + grep, not automated tests (no bash test framework in project)

None — existing test infrastructure is sufficient; only new test cases need to be added to existing files.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Hardcoded "~500 words" in prompt | {word_target} template placeholder substituted at runtime | DIGEST_WORD_TARGET env var takes effect |
| send_digest_email always sets "Daily Digest" subject | subject parameter with daily default | Weekly caller passes "Weekly Digest" subject |
| run-digest.sh hardcodes port 1143 | Reads IMAP_PORT from .env with 1143 fallback | Port change in .env propagates to cron check |
| run-weekly.sh missing | Created with same pattern as run-digest.sh | Weekly pipeline has a cron-safe entry point |

---

## Open Questions

1. **Should weekly prompt also get {word_target} substitution?**
   - What we know: `prompts/weekly.txt` exists; SUMM-05 says "digest target length is configurable"
   - What's unclear: Whether SUMM-05 scope covers weekly digest or just daily
   - Recommendation: Apply same substitution to weekly prompt for consistency; cost is minimal

2. **Should run-weekly.sh also be wrapped by dry-run.sh?**
   - What we know: `scripts/dry-run.sh` delegates to `run-digest.sh --dry-run --verbose`
   - What's unclear: Requirements don't mention a weekly dry-run wrapper
   - Recommendation: Out of scope for Phase 5; `scripts/weekly.py --dry-run` works directly

---

## Sources

### Primary (HIGH confidence — direct source code inspection)
- `/Users/darron/Work/signals/src/config.py` — confirmed `digest_word_target` loaded but never injected
- `/Users/darron/Work/signals/src/summarize.py` — confirmed `call_claude()` never reads `digest_word_target`
- `/Users/darron/Work/signals/src/deliver.py` — confirmed `send_digest_email()` hardcodes "Daily Digest"
- `/Users/darron/Work/signals/scripts/run-digest.sh` — confirmed port 1143 hardcoded at line 24
- `/Users/darron/Work/signals/scripts/weekly.py` — confirmed email delivery calls send_digest_email without subject
- `/Users/darron/Work/signals/prompts/summarize.txt` — confirmed "~500 words" hardcoded
- `/Users/darron/Work/signals/tests/` — confirmed 96 tests pass, existing coverage scope
- `/Users/darron/Work/signals/pyproject.toml` — confirmed pytest configuration

### Secondary (MEDIUM confidence)
- Python `str.format()` documentation: keyword-only substitution pattern is stable stdlib, no version concerns
- bash `grep | cut` pattern: widely established POSIX-compatible `.env` variable extraction

---

## Metadata

**Confidence breakdown:**
- Gap identification: HIGH — confirmed by reading source code directly
- Fix patterns: HIGH — uses stdlib and established patterns with no new dependencies
- Test strategy: HIGH — follows existing test patterns in the codebase
- Shell script behavior: MEDIUM — bash `grep/cut` pattern is standard but not tested in CI (no bash test framework)

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable domain; no external dependencies changing)
