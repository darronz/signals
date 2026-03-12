---
phase: quick
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [README.md]
autonomous: true
requirements: [QUICK-01]
must_haves:
  truths:
    - "Every python/pip/venv command in README has a commented uv alternative below it"
    - "Existing instructions are unchanged"
    - "uv is mentioned as an alternative in Prerequisites"
  artifacts:
    - path: "README.md"
      provides: "Documentation with uv alternatives"
      contains: "uv venv"
  key_links: []
---

<objective>
Add commented uv alternative instructions alongside every python/pip/venv command in README.md.

Purpose: Users who prefer uv over native Python tooling can follow the uv lines instead.
Output: Updated README.md with uv alternatives as commented lines.
</objective>

<execution_context>
@/Users/darron/.claude/get-shit-done/workflows/execute-plan.md
@/Users/darron/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@README.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add uv alternative instructions to README.md</name>
  <files>README.md</files>
  <action>
Edit README.md to add commented uv alternative lines in the following sections. Do NOT remove or modify any existing lines. Add uv alternatives as comments directly below the corresponding command.

1. **Prerequisites** (line 14): Change `- **pip / venv** — standard Python tooling` to:
   `- **pip / venv** — standard Python tooling (or [uv](https://docs.astral.sh/uv/) as a faster alternative)`

2. **Quick Start** (lines 24-29): After each relevant command, add uv alternative:

   After `python3 -m venv .venv`:
   ```
   # Or with uv:
   # uv venv
   ```

   After `pip install -r requirements.txt`:
   ```
   # Or with uv:
   # uv pip install -r requirements.txt
   ```

   After `python scripts/daily.py --dry-run`:
   ```
   # Or with uv:
   # uv run scripts/daily.py --dry-run
   ```

   After `python scripts/weekly.py --dry-run`:
   ```
   # Or with uv:
   # uv run scripts/weekly.py --dry-run
   ```

3. **Usage - Daily Digest** (lines 103-123): After the first `python scripts/daily.py` line (line 105), add a single block:
   ```
   # Or with uv: uv run scripts/daily.py [same flags]
   ```

4. **Usage - Weekly Rollup** (lines 128-146): After the first `python scripts/weekly.py` line (line 129), add a single block:
   ```
   # Or with uv: uv run scripts/weekly.py [same flags]
   ```

5. **Dry-Run Verification** (lines 167-179): After the first `python scripts/daily.py --dry-run` line, add:
   ```
   # Or with uv: uv run scripts/daily.py --dry-run
   ```

6. **Cron Setup** (lines 188-193): After each cron entry, add uv alternative:

   After the daily cron line:
   ```
   # Or with uv:
   # 0 7 * * * cd /path/to/signals && uv run scripts/daily.py >> /var/log/signals-daily.log 2>&1
   ```

   After the weekly cron line:
   ```
   # Or with uv:
   # 0 8 * * 1 cd /path/to/signals && uv run scripts/weekly.py >> /var/log/signals-weekly.log 2>&1
   ```

7. **Running Tests** (lines 234-243): After `.venv/bin/pytest tests/ -q`:
   ```
   # Or with uv:
   # uv run pytest tests/ -q
   ```

   After the integration test command:
   ```
   # Or with uv:
   # SIGNALS_INTEGRATION=1 uv run pytest tests/test_fetch_integration.py -q
   ```
  </action>
  <verify>
    <automated>grep -c "uv" README.md | xargs test 10 -le</automated>
  </verify>
  <done>README.md contains uv alternative comments in Prerequisites, Quick Start, Usage (daily + weekly), Dry-Run Verification, Cron Setup, and Running Tests sections. All original instructions remain intact.</done>
</task>

</tasks>

<verification>
- `grep "uv" README.md` shows uv alternatives in all target sections
- `diff` against git HEAD shows only additions, no deletions of existing content
</verification>

<success_criteria>
- Every python/pip/venv command block in README.md has a commented uv equivalent
- No existing instructions were removed or altered
- uv is mentioned as an alternative in Prerequisites
</success_criteria>

<output>
After completion, create `.planning/quick/1-add-uv-alternative-instructions-to-readm/1-SUMMARY.md`
</output>
