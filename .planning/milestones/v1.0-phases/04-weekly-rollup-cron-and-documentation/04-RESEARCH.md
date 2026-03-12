# Phase 4: Weekly Rollup, Cron, and Documentation - Research

**Researched:** 2026-03-12
**Domain:** Python file I/O for markdown aggregation, Claude CLI subprocess integration (reuse), HTML email delivery (reuse), shell scripting, README documentation patterns
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DLVR-03 | Weekly digest re-summarizes daily markdown files into higher-level trends | `scripts/weekly.py` reads `output/digest-YYYY-MM-DD.md` files via `pathlib.glob`; concatenates them as Claude stdin input; reuses `call_claude()` from `src/summarize.py` with a new `prompts/weekly.txt` prompt |
| DLVR-04 | Weekly digest is sent as HTML email and saved as markdown file | Reuses `send_digest_email()` and `save_archive()` from `src/deliver.py`; archive filename `weekly-YYYY-WXX.md`; email subject "Weekly Digest — Week XX, YYYY" |
| DOCS-01 | README.md with setup guide, usage docs, configuration reference, and examples | README covers: prerequisites, venv setup, `.env` config, first dry-run, cron setup, weekly rollup usage; configuration reference table mirrors `.env.example` keys from `src/config.py` |
</phase_requirements>

## Summary

Phase 4 adds two deliverables: a weekly rollup script (`scripts/weekly.py`) and a README (`README.md`). Both are largely additive — they build on existing modules with no new external dependencies.

The weekly rollup script reads all `output/digest-YYYY-MM-DD.md` files within a configurable window (default: last 7 days), concatenates them as Claude stdin input using the same `call_claude()` pattern already in `src/summarize.py`, and delivers the result via the same `send_digest_email()` and `save_archive()` functions already in `src/deliver.py`. A new prompt file (`prompts/weekly.txt`) directs Claude to synthesize week-over-week themes rather than single-day events. The script also needs a `--dry-run` flag that verifies the 7+ daily files exist and shows what would be sent without invoking Claude.

The README is the only truly new content type in this phase. It must be good enough that a new user who has never seen the codebase can configure `.env`, install dependencies, and successfully run `--dry-run` without needing to read any Python source. The configuration reference must mirror the actual keys in `src/config.py` exactly — this is the highest-risk area for staleness.

**Primary recommendation:** Build `scripts/weekly.py` first (it exercises all reused modules and produces a testable artifact), then `prompts/weekly.txt`, then `README.md` (which documents what already exists).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pathlib` | stdlib | Glob daily digest files, construct weekly archive filename | Already used in `src/deliver.py`; `Path.glob()` for file discovery |
| `subprocess` | stdlib | Reuse `call_claude()` from `src/summarize.py` | Phase 2/3 decision: `subprocess.run(input=...)` pattern mandatory |
| `smtplib` | stdlib | Reuse `send_digest_email()` from `src/deliver.py` | No new SMTP code needed — direct function reuse |
| `argparse` | stdlib | CLI flags for `scripts/weekly.py` (`--dry-run`, `--since`, `--output`) | Matches `scripts/daily.py` pattern exactly |
| `datetime` | stdlib | Date arithmetic for 7-day window, ISO week number for filename | `date.today()`, `timedelta(days=7)`, `date.isocalendar()` for week number |
| `logging` | stdlib | Same pattern as `scripts/daily.py` | Consistency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` | 1.2.2 (installed) | Config loading via `load_config()` | Already imported in `src/config.py`; no change needed |
| `beautifulsoup4` | 4.14.3 (installed) | Not used in this phase | Ignore |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pathlib.glob("digest-*.md")` | Manual directory scan with `os.listdir()` | `pathlib.glob` is cleaner and already the project pattern |
| ISO week number filename (`weekly-YYYY-WXX.md`) | Date-range filename (`weekly-YYYY-MM-DD-to-MM-DD.md`) | ISO week is shorter and standard; date-range is more human-readable but longer |
| Reuse `call_claude()` from `src/summarize.py` | Copy-paste the subprocess call into `scripts/weekly.py` | Reuse is correct — no duplication; `weekly.py` imports from `src.summarize` and `src.deliver` |

**Installation:**
```bash
# No new packages required — all stdlib + already-installed deps
# Existing setup is sufficient:
pip install -r requirements.txt
```

## Architecture Patterns

### Recommended Project Structure
```
signals/
├── scripts/
│   ├── daily.py           # existing — no changes
│   ├── weekly.py          # NEW: weekly rollup script
│   ├── run-digest.sh      # existing — no changes
│   └── dry-run.sh         # existing — no changes
├── prompts/
│   ├── summarize.txt      # existing — no changes
│   └── weekly.txt         # NEW: weekly synthesis prompt
├── output/
│   ├── digest-YYYY-MM-DD.md   # existing daily archives
│   └── weekly-YYYY-WXX.md     # NEW: weekly archive files
├── README.md              # NEW: setup and usage documentation
└── tests/
    └── test_weekly.py     # NEW: unit tests for weekly.py
```

### Pattern 1: Weekly Script Structure (weekly.py)
**What:** Discover daily digest files for the last N days, concatenate their content with date headers, pipe to Claude with the weekly prompt, save archive and optionally email.
**When to use:** This is the full weekly.py implementation pattern.

```python
# Source: mirrors scripts/daily.py structure exactly; stdlib pathlib + datetime
"""
CLI entry point for the Signals weekly digest rollup.

Reads daily digest markdown files from the output directory,
re-summarizes them into weekly trends using Claude CLI.

Exit codes (mirror daily.py OPS-03):
  0 — success (or --dry-run)
  1 — config/auth error or missing daily files
  2 — no daily digest files found in window
  3 — Claude CLI error
"""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from src.config import load_config
from src.summarize import call_claude
from src.deliver import save_archive, send_digest_email, markdown_to_html

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_PROMPT = _PROJECT_ROOT / "prompts" / "weekly.txt"


def find_daily_digests(output_dir: Path, since_days: int = 7) -> list[Path]:
    """Return daily digest files from the last N days, sorted oldest-first."""
    cutoff = date.today() - timedelta(days=since_days)
    files = []
    for f in sorted(output_dir.glob("digest-*.md")):
        # filename: digest-YYYY-MM-DD.md
        try:
            file_date = date.fromisoformat(f.stem.replace("digest-", ""))
        except ValueError:
            continue
        if file_date >= cutoff:
            files.append(f)
    return files


def format_weekly_input(digest_files: list[Path]) -> str:
    """Concatenate daily digest files with date headers for Claude input."""
    parts = []
    for f in digest_files:
        date_str = f.stem.replace("digest-", "")
        content = f.read_text(encoding="utf-8").strip()
        parts.append(f"---\nDate: {date_str}\n\n{content}")
    return "\n\n".join(parts)


def weekly_archive_filename(today: date) -> str:
    """Return weekly archive filename: weekly-YYYY-WXX.md"""
    iso = today.isocalendar()
    return f"weekly-{iso.year}-W{iso.week:02d}.md"
```

### Pattern 2: Daily Digest File Discovery
**What:** Use `pathlib.glob("digest-*.md")` to find daily digest files; filter by date parsed from filename.
**When to use:** This is the only correct way to find daily files — do not assume files are contiguous or sorted by mtime.

```python
# Source: Python stdlib pathlib + datetime docs
from pathlib import Path
from datetime import date, timedelta

def find_daily_digests(output_dir: Path, since_days: int = 7) -> list[Path]:
    cutoff = date.today() - timedelta(days=since_days)
    files = []
    for f in sorted(output_dir.glob("digest-*.md")):
        try:
            file_date = date.fromisoformat(f.stem.replace("digest-", ""))
        except ValueError:
            continue  # skip malformed filenames
        if file_date >= cutoff:
            files.append(f)
    return files
```

### Pattern 3: ISO Week Number for Filename
**What:** Use `date.isocalendar()` to generate the weekly archive filename in `weekly-YYYY-WXX.md` format.
**When to use:** Generating the weekly output filename.

```python
# Source: Python stdlib datetime docs — date.isocalendar() returns IsoCalendarDate
from datetime import date

def weekly_archive_filename(today: date) -> str:
    iso = today.isocalendar()
    return f"weekly-{iso.year}-W{iso.week:02d}.md"

# Examples:
# date(2026, 3, 12).isocalendar() -> IsoCalendarDate(year=2026, week=11, weekday=4)
# -> "weekly-2026-W11.md"
```

**Critical:** Use `iso.year` not `today.year` — they differ in the last days of December (ISO week 1 of next year).

### Pattern 4: save_archive Reuse for Weekly Files
**What:** `src/deliver.save_archive()` uses `date.today().strftime("%Y-%m-%d")` for the filename. For weekly files, the archive filename must be passed directly. The `save_archive()` function will need a small adaptation or the weekly script should write the file directly using `pathlib`.
**When to use:** Saving the weekly markdown archive.

Looking at the existing `save_archive()` signature:
```python
def save_archive(digest_md: str, config: dict) -> Path:
    output_dir = Path(config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    filepath = output_dir / f"digest-{today}.md"
    filepath.write_text(digest_md, encoding="utf-8")
    return filepath
```

This function hardcodes `digest-{today}.md`. The weekly script must either:
1. Write the weekly file directly: `(output_dir / weekly_archive_filename(date.today())).write_text(...)`
2. Or add an optional `filename` parameter to `save_archive()` — but this modifies existing code

**Recommendation:** Write the weekly file directly in `weekly.py` using the same pathlib pattern. Do NOT modify `save_archive()` — it has 13 tests covering it. The weekly file uses a different naming convention anyway (`weekly-YYYY-WXX.md` vs `digest-YYYY-MM-DD.md`).

### Pattern 5: Weekly Prompt (prompts/weekly.txt)
**What:** The Claude prompt for weekly synthesis focuses on trends across days, not single-day events.
**When to use:** Created once; `--prompt` flag overrides path (same as daily).

```
You are a newsletter digest assistant. You will receive several daily digest
summaries, each separated by a "---" divider with a header showing the date.

Produce a weekly digest with these sections:

## Week in Review
2-3 paragraphs summarizing the dominant themes and narratives across the week.

## Key Trends
Top 3-5 themes that appeared consistently across multiple days.

## Notable Developments
Specific announcements, releases, or events that stand out for the week.

## Signals to Watch
Emerging patterns or early indicators worth monitoring in the coming week.

## Sources Overview
Brief listing of the daily digests included (dates covered).

Be concise. Target ~600 words total. Focus on week-over-week patterns,
not just what happened on individual days.
Do not include personal information, email addresses, or names.
```

### Pattern 6: README Structure
**What:** The README must enable a new user to go from zero to a working `--dry-run` without reading source code.
**When to use:** Single README.md at project root.

Required sections (verified against DOCS-01 success criterion):
1. **What this is** (1-2 sentences)
2. **Prerequisites** (Proton Mail Bridge, Claude CLI, Python 3.10+)
3. **Quick start** (clone, venv, pip install, copy .env.example, edit .env, first run)
4. **Configuration reference** (table of all .env keys with descriptions and defaults)
5. **Usage** (daily.py, weekly.py, shell wrappers, cron setup example)
6. **Dry-run verification** (explicit step to verify setup without sending email)
7. **Troubleshooting** (exit codes, common errors)

**Configuration reference must match `src/config.py` exactly.** The authoritative source for all config keys and defaults is `src/config.py load_config()`. Cross-reference every key.

### Anti-Patterns to Avoid
- **Modifying `src/deliver.save_archive()` to support weekly filenames:** The function has 13 tests. Add weekly file writing directly in `scripts/weekly.py` instead.
- **Using `date.today().year` for ISO week filename:** Use `date.isocalendar().year` — they differ in late December when ISO week 1 of next year starts.
- **`glob("*.md")` without date filtering:** Will pick up `weekly-*.md` files too. Always filter by filename prefix pattern `digest-*.md` for daily files.
- **`sys.exit()` in `find_daily_digests()`:** Keep it a pure function that returns empty list. The orchestrator in `main()` maps empty result to exit code 2.
- **README config table derived from `.env.example` instead of `src/config.py`:** The `.env.example` may not have been updated when config keys changed. `src/config.py load_config()` is the ground truth.
- **Calling `load_dotenv()` at module import time in `weekly.py`:** Established anti-pattern from Phase 1. Always call inside function bodies.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reading markdown files | Custom file parser | `Path.read_text(encoding="utf-8")` | Files are already well-formed markdown; just read the raw text |
| Date arithmetic for 7-day window | Manual date math | `date.today() - timedelta(days=7)` | stdlib datetime; one line |
| ISO week number | Custom week calculator | `date.isocalendar().week` | stdlib; handles year boundaries correctly |
| Claude invocation | Re-implementing subprocess call | Import `call_claude` from `src.summarize` | Already written, tested, and handles all edge cases |
| SMTP email delivery | Re-implementing smtplib calls | Import `send_digest_email` from `src.deliver` | Already written, tested, handles STARTTLS correctly |
| HTML conversion | New markdown-to-HTML converter | Import `markdown_to_html` from `src.deliver` | Already written for the same digest structure |
| Config loading | New .env parsing | Import `load_config` from `src.config` | Already handles all keys, validation, and dotenv loading |

**Key insight:** Phase 4 is almost entirely module reuse. The new code is the file discovery logic, the weekly prompt, and the README. Any code that re-implements what Phase 3 already built is wrong.

## Common Pitfalls

### Pitfall 1: ISO Week Year vs Calendar Year
**What goes wrong:** `date(2026, 12, 31).isocalendar()` returns `IsoCalendarDate(year=2027, week=1, weekday=4)`. If you use `date.today().year` instead of `iso.year` for the filename, the file gets named `weekly-2026-W01.md` instead of `weekly-2027-W01.md`.
**Why it happens:** ISO week 1 of a new year can start in the last days of December. The calendar year and ISO year diverge.
**How to avoid:** Always use `iso = today.isocalendar(); filename = f"weekly-{iso.year}-W{iso.week:02d}.md"`.
**Warning signs:** Weekly file dated to wrong year in the last week of December.

### Pitfall 2: Glob Picks Up Weekly Files
**What goes wrong:** `output_dir.glob("*.md")` returns both `digest-YYYY-MM-DD.md` and `weekly-YYYY-WXX.md`. The weekly script reads its own previous output as input.
**Why it happens:** Broad glob pattern matches all markdown files.
**How to avoid:** Use `output_dir.glob("digest-*.md")` — prefix-specific pattern excludes weekly files.
**Warning signs:** Weekly digest includes meta-text from a previous weekly digest rather than raw daily content.

### Pitfall 3: Missing Daily Files Not the Same as No Newsletters
**What goes wrong:** Script exits with code 2 ("no files found") even though the user ran daily digests — they just haven't run it 7 times yet.
**Why it happens:** New users on first week of use won't have 7 daily files.
**How to avoid:** The success criterion says "7+ saved daily digest files" — this is a test precondition, not a hard requirement in the code. The `--dry-run` flag should report how many daily files were found, not fail silently. Exit code 2 is appropriate when zero files are found; having fewer than 7 should warn but not fail.
**Warning signs:** Script exits 2 on a machine that has 3 daily digests.

### Pitfall 4: Prompt Path Resolution in Cron Context
**What goes wrong:** `prompts/weekly.txt` resolves relative to cwd, which is wrong in cron.
**Why it happens:** Same pitfall as Phase 3 Pitfall 3 — cron cwd is not the project directory.
**How to avoid:** Always resolve prompt path relative to `__file__`:
```python
_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_PROMPT = _PROJECT_ROOT / "prompts" / "weekly.txt"
```
**Warning signs:** `FileNotFoundError: prompts/weekly.txt` in cron logs only.

### Pitfall 5: README Config Reference Out of Sync with Code
**What goes wrong:** README documents config keys that don't exist in `load_config()`, or omits keys that do exist. New user follows README, sets wrong env vars, gets confusing errors.
**Why it happens:** README written from memory rather than from `src/config.py`.
**How to avoid:** Write the config reference table by reading `src/config.py load_config()` line by line. Every key returned by `load_config()` must appear in the README. Every default must match the code.
**Warning signs:** User reports `--dry-run` fails even after following README exactly.

### Pitfall 6: Weekly Script Hardcodes 7-Day Window
**What goes wrong:** `since_days` is hardcoded as 7 and not configurable. User can't run a 14-day retrospective.
**Why it happens:** Requirement says "7+ saved daily digest files" but doesn't say the window must be fixed.
**How to avoid:** Default to 7 days but accept `--since DAYS` as a CLI arg (mirrors `daily.py --since HOURS`). For weekly, `--since 14` means look back 14 days.
**Warning signs:** User can't generate a two-week retrospective without editing source code.

## Code Examples

Verified patterns from stdlib (all HIGH confidence):

### Date Arithmetic for 7-Day Window
```python
# Source: Python stdlib datetime docs
from datetime import date, timedelta

cutoff = date.today() - timedelta(days=7)
# date(2026, 3, 12) - timedelta(days=7) == date(2026, 3, 5)
```

### ISO Week Filename
```python
# Source: Python stdlib datetime docs — IsoCalendarDate namedtuple
from datetime import date

def weekly_archive_filename(today: date) -> str:
    iso = today.isocalendar()
    return f"weekly-{iso.year}-W{iso.week:02d}.md"
# date(2026, 3, 12).isocalendar() -> IsoCalendarDate(year=2026, week=11, weekday=4)
# -> "weekly-2026-W11.md"
```

### Glob with Date Filtering
```python
# Source: Python stdlib pathlib + datetime docs
from pathlib import Path
from datetime import date, timedelta

output_dir = Path("./output")
cutoff = date.today() - timedelta(days=7)

digest_files = []
for f in sorted(output_dir.glob("digest-*.md")):
    try:
        file_date = date.fromisoformat(f.stem.replace("digest-", ""))
    except ValueError:
        continue
    if file_date >= cutoff:
        digest_files.append(f)
# Returns sorted list of Path objects for files within the window
```

### Writing Weekly Archive (not using save_archive)
```python
# Source: Python stdlib pathlib; mirrors src/deliver.save_archive() pattern
from pathlib import Path
from datetime import date

def save_weekly_archive(digest_md: str, config: dict) -> Path:
    output_dir = Path(config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = weekly_archive_filename(date.today())
    filepath = output_dir / filename
    filepath.write_text(digest_md, encoding="utf-8")
    return filepath
```

### Mocking find_daily_digests in Tests
```python
# Source: Python stdlib unittest.mock + tmp_path pytest fixture
from unittest.mock import patch
from pathlib import Path
import pytest

def test_weekly_dry_run_shows_file_count(tmp_path, capsys):
    # Create fake daily digest files
    for day in ["2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09",
                "2026-03-10", "2026-03-11", "2026-03-12"]:
        (tmp_path / f"digest-{day}.md").write_text(f"# Digest {day}\n\nContent.", encoding="utf-8")

    import scripts.weekly as weekly_module
    with patch.object(weekly_module, "load_config", return_value={
        "output_dir": str(tmp_path), "claude_cmd": "claude", "claude_model": "",
        "output_format": "markdown", "digest_recipient": "",
        "imap_username": "test@proton.me", "imap_password": "pass",
        "smtp_host": "127.0.0.1", "smtp_port": 1025,
    }), patch("sys.argv", ["weekly.py", "--dry-run"]):
        with pytest.raises(SystemExit) as exc_info:
            weekly_module.main()
    assert exc_info.value.code == 0
    assert "7" in capsys.readouterr().out  # shows file count
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Copy-paste subprocess logic | Import `call_claude()` from `src.summarize` | This phase | Reuse eliminates duplication; tested code |
| `os.path.exists()` + `os.listdir()` | `pathlib.Path.glob()` | Python 3.6+ standard | Cleaner; returns `Path` objects directly |
| `date.strftime("%V")` for week | `date.isocalendar().week` | Python 3.9+ (IsoCalendarDate named fields) | Named access is clearer than positional index |

**Note on `date.isocalendar()` API:** In Python 3.9+, `date.isocalendar()` returns `IsoCalendarDate` with named attributes `.year`, `.week`, `.weekday`. In Python 3.8 and earlier it returned a plain tuple. This project requires Python 3.10+ (per `pyproject.toml`), so named access is safe.

**Deprecated/outdated:**
- `date.isocalendar()[0]` and `date.isocalendar()[1]` (tuple index access): Replaced by `.year` and `.week` named attributes in Python 3.9+. Use named access in all new code.

## Open Questions

1. **Weekly email subject line format**
   - What we know: Daily email is `f"Daily Digest — {today}"`. No equivalent specified for weekly.
   - What's unclear: Whether "Weekly Digest — Week 11, 2026" or "Weekly Digest — Mar 6–12, 2026" is preferable.
   - Recommendation: Use "Weekly Digest — Week {week:02d}, {year}" (matches ISO week filename convention). Simple, consistent.

2. **`--dry-run` behavior for weekly.py**
   - What we know: `daily.py --dry-run` prints the sanitized newsletter text and exits 0.
   - What's unclear: For `weekly.py`, should `--dry-run` print the concatenated daily digest content, or just report how many files were found?
   - Recommendation: Print a summary of files found (count + filenames) and the total character count, then exit 0 without calling Claude. This satisfies the success criterion "checks that 7+ saved daily digest files produce an HTML weekly digest email" — the dry-run can verify the file count prerequisite.

3. **Weekly archive filename collision (same as daily Pitfall 6)**
   - What we know: Running `weekly.py` twice in the same ISO week overwrites the file.
   - What's unclear: Whether to warn, fail, or silently overwrite.
   - Recommendation: Silently overwrite (same behavior as `save_archive()` for daily files). Document in README that re-running in the same week regenerates the digest.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (already installed in .venv) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` already configured |
| Quick run command | `pytest tests/test_weekly.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DLVR-03 | `find_daily_digests` returns files in date window | unit | `pytest tests/test_weekly.py::test_find_daily_digests_returns_files_in_window -x` | Wave 0 |
| DLVR-03 | `find_daily_digests` excludes files outside window | unit | `pytest tests/test_weekly.py::test_find_daily_digests_excludes_old_files -x` | Wave 0 |
| DLVR-03 | `find_daily_digests` skips weekly-*.md files | unit | `pytest tests/test_weekly.py::test_find_daily_digests_ignores_weekly_files -x` | Wave 0 |
| DLVR-03 | `format_weekly_input` concatenates files with date headers | unit | `pytest tests/test_weekly.py::test_format_weekly_input -x` | Wave 0 |
| DLVR-03 | `call_claude` invoked with weekly prompt and daily content | unit | `pytest tests/test_weekly.py::test_weekly_calls_claude_with_weekly_prompt -x` | Wave 0 |
| DLVR-04 | Weekly archive saved with `weekly-YYYY-WXX.md` filename | unit | `pytest tests/test_weekly.py::test_weekly_archive_filename_format -x` | Wave 0 |
| DLVR-04 | Weekly archive written to output directory | unit | `pytest tests/test_weekly.py::test_save_weekly_archive_creates_file -x` | Wave 0 |
| DLVR-04 | Email sent when output_format=email | unit | `pytest tests/test_weekly.py::test_weekly_sends_email_when_configured -x` | Wave 0 |
| DLVR-03/04 | Exit code 2 when zero daily files found | unit | `pytest tests/test_weekly.py::test_exit_2_no_daily_files -x` | Wave 0 |
| DLVR-03/04 | `--dry-run` exits 0 without calling Claude | unit | `pytest tests/test_weekly.py::test_dry_run_no_claude_call -x` | Wave 0 |
| DLVR-03/04 | Exit code 3 on Claude CLI error | unit | `pytest tests/test_weekly.py::test_exit_3_claude_error -x` | Wave 0 |
| DOCS-01 | README.md exists at project root | smoke | `pytest tests/test_weekly.py::test_readme_exists -x` | Wave 0 |
| DOCS-01 | README.md contains all required .env keys | smoke | `pytest tests/test_weekly.py::test_readme_contains_all_config_keys -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_weekly.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_weekly.py` — covers DLVR-03, DLVR-04, and DOCS-01 smoke checks
- [ ] `scripts/weekly.py` — new weekly rollup script
- [ ] `prompts/weekly.txt` — weekly synthesis prompt for Claude
- [ ] `README.md` — project documentation (DOCS-01)

*(No framework install needed — pytest already configured in pyproject.toml)*

## Sources

### Primary (HIGH confidence)
- Python stdlib `datetime` docs (python.org) — `date.isocalendar()` named attributes available since Python 3.9; `timedelta(days=N)`; `date.fromisoformat()` available since Python 3.7
- Python stdlib `pathlib` docs (python.org) — `Path.glob()`, `Path.read_text()`, `Path.write_text()`, `Path.mkdir(parents=True, exist_ok=True)`
- `src/deliver.py` (codebase, read directly) — `save_archive()`, `send_digest_email()`, `markdown_to_html()` signatures and behavior confirmed
- `src/summarize.py` (codebase, read directly) — `call_claude()`, `format_newsletter_input()` signatures confirmed
- `src/config.py` (codebase, read directly) — all config keys and defaults confirmed for README reference
- `scripts/daily.py` (codebase, read directly) — CLI pattern, exit codes, argparse structure for weekly.py to mirror
- Phase 3 RESEARCH.md (`.planning/phases/03-*/03-RESEARCH.md`) — pitfalls 3, 5, 6, 7 directly applicable to Phase 4

### Secondary (MEDIUM confidence)
- Phase 3 VERIFICATION.md — confirms all Phase 3 functions are tested and working; safe to import and reuse
- Python stdlib `datetime.isocalendar()` behavior at year boundary — verified by reading official docs description; test at boundary recommended

### Tertiary (LOW confidence)
- Weekly prompt effectiveness — the `prompts/weekly.txt` content is speculative until tested against 7+ real daily digest files. The structure follows the daily prompt pattern but week-over-week synthesis quality requires empirical validation with real data.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib; no new external dependencies; all reuse modules are tested and verified in Phase 3
- Architecture: HIGH — `find_daily_digests`, `format_weekly_input`, and `save_weekly_archive` are simple pathlib + datetime operations; module reuse is direct
- Weekly prompt: MEDIUM — structure is principled but effectiveness requires testing with real daily digest files (noted as open concern in STATE.md)
- README completeness: HIGH for structure; requires cross-reference with `src/config.py` at write time to ensure config table is accurate

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stdlib APIs are stable; verify `src/config.py` has not changed before writing README config table)
