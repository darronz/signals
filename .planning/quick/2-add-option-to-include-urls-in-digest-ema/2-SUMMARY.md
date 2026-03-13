---
phase: quick
plan: 2
subsystem: summarize, deliver, config
tags: [feature, url-rendering, html-email, tdd]
dependency_graph:
  requires: []
  provides: [DIGEST_INCLUDE_URLS config option, markdown link HTML rendering, bare URL HTML rendering]
  affects: [src/config.py, src/summarize.py, src/deliver.py, prompts/summarize.txt, .env.example]
tech_stack:
  added: []
  patterns: [conditional prompt injection, regex-based inline markdown rendering]
key_files:
  created: []
  modified:
    - src/config.py
    - src/summarize.py
    - src/deliver.py
    - prompts/summarize.txt
    - .env.example
    - tests/test_summarize.py
    - tests/test_deliver.py
decisions:
  - "URL rendering order: bold -> markdown links -> bare URLs prevents double-wrapping"
  - "url_instruction injected as empty string when disabled (no conditional in prompt template)"
  - "Bare URL regex uses negative lookbehind to avoid wrapping URLs already inside <a href=>"
metrics:
  duration: ~15 minutes
  completed: 2026-03-13
  tasks_completed: 2
  files_modified: 7
---

# Quick Task 2: Add DIGEST_INCLUDE_URLS Config Option Summary

**One-liner:** Opt-in DIGEST_INCLUDE_URLS=true injects a URL-inclusion instruction into the Claude prompt, and `_apply_inline` now converts markdown links and bare https:// URLs to clickable `<a>` tags in HTML email.

## What Was Built

### Task 1: Config option and conditional prompt instruction

Added `DIGEST_INCLUDE_URLS` environment variable support (default false) that conditionally injects a URL instruction into the Claude summarization prompt:

- `src/config.py`: New `digest_include_urls` key — reads `DIGEST_INCLUDE_URLS` env var, truthy values: `"true"`, `"1"`, `"yes"`
- `prompts/summarize.txt`: New `{url_instruction}` placeholder appended after the word-target line
- `src/summarize.py`: `call_claude()` builds `url_instruction` string (non-empty when enabled), passes both `word_target` and `url_instruction` to `prompt.format()`
- `.env.example`: Documented new option with explanatory comments

When enabled, Claude is instructed: "Include relevant source URLs as markdown links [title](url) where available. Prefer linking to the original article or announcement."

### Task 2: Markdown link and bare URL HTML rendering

Updated `_apply_inline()` in `src/deliver.py` to handle URLs in digest output:

- `[text](url)` markdown links → `<a href="url">text</a>`
- Bare `https://...` URLs → `<a href="url">url</a>`
- Processing order prevents double-wrapping: bold first, markdown links second, bare URLs last
- Negative lookbehind regex `(?<!href=")(?<!>)` skips URLs already inside `<a>` tags

## Tests Added

**tests/test_summarize.py** (4 new tests):
- `test_include_urls_true_adds_url_instruction` — verifies "source URLs" in prompt when enabled
- `test_include_urls_false_no_url_instruction` — verifies no URL text when disabled
- `test_include_urls_missing_no_url_instruction` — verifies no URL text when key absent
- `test_prompt_contains_url_instruction_placeholder` — verifies `{url_instruction}` in prompt file

**tests/test_deliver.py** (5 new tests):
- `test_apply_inline_markdown_link` — `[OpenAI](https://openai.com)` → `<a href="...">OpenAI</a>`
- `test_apply_inline_bare_url` — bare URL wrapped in `<a>` tag
- `test_apply_inline_no_double_wrap` — exactly one `<a` when using markdown link syntax
- `test_apply_inline_bold_and_link` — both `<strong>` and `<a href>` present together
- `test_markdown_to_html_with_link` — end-to-end bullet with link produces clickable anchor

**Result:** 109 tests pass, 3 integration tests skipped (require live IMAP).

## Commits

| Hash | Message |
|------|---------|
| d18d801 | test(quick-2): add failing tests for digest_include_urls config option |
| 96c10de | feat(quick-2): add DIGEST_INCLUDE_URLS config option and conditional prompt instruction |
| 9ecc363 | test(quick-2): add failing tests for markdown link and bare URL HTML rendering |
| 542a053 | feat(quick-2): render markdown links and bare URLs as clickable HTML in email |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

All modified files confirmed present. All 4 task commits confirmed in git history. Full test suite: 109 passed, 3 skipped.
