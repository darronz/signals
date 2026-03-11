# Pitfalls Research

**Domain:** Email processing pipeline — IMAP fetch, HTML sanitization, LLM summarization, SMTP digest delivery
**Researched:** 2026-03-11
**Confidence:** HIGH (IMAP/MIME/subprocess pitfalls), MEDIUM (Claude CLI specifics, Proton Bridge edge cases)

---

## Critical Pitfalls

### Pitfall 1: Using IMAP Sequence Numbers Instead of UIDs

**What goes wrong:**
The `imaplib` SEARCH command returns message sequence numbers by default. Sequence numbers are renumbered any time messages are expunged (deleted/moved) from the mailbox. If the mailbox changes between your SEARCH and FETCH calls — which happens when Proton Bridge syncs — you fetch the wrong message entirely, silently, with no error.

**Why it happens:**
The IMAP protocol has two parallel numbering systems (sequence numbers and UIDs) and the Python stdlib `imaplib` defaults to sequence numbers. Developers copy examples that use `SEARCH` results directly in `FETCH` without switching to UID-mode commands.

**How to avoid:**
Always use `UID SEARCH` and `UID FETCH` commands, not `SEARCH`/`FETCH`. In `imaplib`: use `imap.uid('SEARCH', ...)` and `imap.uid('FETCH', ...)`. If using `imap_tools`, UIDs are used by default. Never pass sequence numbers to fetch calls.

**Warning signs:**
- Fetched email body doesn't match the expected subject
- Inconsistent results when the mailbox has recent activity
- Works fine in test but fails intermittently in production (when Bridge is actively syncing)

**Phase to address:**
IMAP connection and fetch phase — validate UID-mode usage before any other logic is built on top of it.

---

### Pitfall 2: Proton Bridge Self-Signed Certificate Causing SSL Failures

**What goes wrong:**
Proton Bridge generates a local self-signed TLS certificate for its IMAP and SMTP listeners. Python's `imaplib` and `smtplib` perform certificate verification by default. The connection fails with `[SSL: CERTIFICATE_VERIFY_FAILED]` unless the SSL context is explicitly configured to trust the Bridge certificate.

**Why it happens:**
Bridge is a localhost proxy — the self-signed cert is by design. But Python's SSL defaults treat it as an untrusted cert. Documentation for email clients (Thunderbird, Outlook) tells users to trust the cert through the OS keychain, which doesn't help Python scripts.

**How to avoid:**
Two valid approaches, in preference order:
1. Export the Bridge TLS certificate (Bridge settings > Export TLS cert) and load it as a CA bundle in a custom `ssl.SSLContext`. This is the correct approach.
2. Set `ssl_context.check_hostname = False` and `ssl_context.verify_mode = ssl.CERT_NONE` only for the localhost connection — document clearly why this is acceptable (loopback, same-process trust).

Never disable SSL entirely or disable verification without a comment explaining the localhost context.

**Warning signs:**
- `CERTIFICATE_VERIFY_FAILED` on first run
- Works if you use a third-party IMAP client but fails in Python
- Environment-specific failures (cert regenerates if Bridge is reinstalled)

**Phase to address:**
IMAP connection setup — this must be solved before any email can be fetched.

---

### Pitfall 3: PII Leaking Through Email Headers into the Sanitized Payload

**What goes wrong:**
The sanitizer strips PII from the email body but the pipeline constructs a prompt that includes the Subject line, From address, or other headers verbatim. The user's own email address, real name, or the full sender address reach Claude even though the body was cleaned. Subject lines often contain the user's first name ("Hi Darron, here's your weekly recap").

**Why it happens:**
Body sanitization is implemented first. Header handling is treated as metadata/context rather than user data. "Reduce sender to domain-only" is specified in requirements but easy to forget when assembling the final prompt string.

**How to avoid:**
Treat the sanitizer as the sole boundary point. The sanitizer module should be responsible for ALL fields that flow into the prompt — body, subject, sender — not just the body. Specifically:
- Strip or truncate `Subject` to remove personalization
- Reduce `From` to domain-only (not full address)
- Drop `To`, `Cc`, `Reply-To`, `List-Unsubscribe` entirely
- Never pass raw headers downstream of the sanitizer
Write a test: assert that the user's email address string never appears anywhere in the sanitizer's output.

**Warning signs:**
- User's email address appears in digest output
- Full sender addresses appear in source attribution section
- Subject lines contain recipient names

**Phase to address:**
Sanitizer module — the privacy boundary definition phase.

---

### Pitfall 4: subprocess Deadlock When Piping Large Input to Claude CLI

**What goes wrong:**
Using `subprocess.Popen` with `stdin=PIPE, stdout=PIPE` and writing large newsletter content to stdin, then reading stdout separately, causes a deadlock. The child process fills the OS pipe buffer waiting for the parent to read stdout, while the parent is still writing to stdin waiting for the child to accept more input.

**Why it happens:**
OS pipe buffers are small (typically 64KB). Newsletter content easily exceeds this. Developers write `proc.stdin.write(large_input); proc.stdin.close(); output = proc.stdout.read()` — the write blocks before completing.

**How to avoid:**
Always use `subprocess.run(input=content, capture_output=True, ...)` or `proc.communicate(input=content)`. Both handle bidirectional piping safely by using threads internally. Never manually write to stdin and read from stdout in sequence. Set a timeout: `subprocess.run(..., timeout=120)` and handle `subprocess.TimeoutExpired` explicitly.

**Warning signs:**
- Script hangs indefinitely with no output
- Works with small test emails, hangs with full newsletter batches
- Process visible in `ps` stuck in pipe I/O

**Phase to address:**
Claude CLI integration phase — test with maximum-sized input before declaring complete.

---

### Pitfall 5: Claude CLI Token Limit Exhaustion on Large Newsletter Batches

**What goes wrong:**
On days with many newsletters, the total sanitized content exceeds the Claude Pro context window (~44K tokens per 5-hour window for Pro; ~88K for Max5). The CLI call fails mid-batch or produces truncated output with no warning. Worse, if the pipeline retries, it burns more of the rate-limited quota.

**Why it happens:**
Each `claude -p` invocation is a fresh context. There is no streaming trim — if you send 60K tokens of newsletter text, it simply fails at the limit. The project specifies a "configurable character limit per newsletter" but it's easy to set this too high, or forget to enforce it before the prompt is assembled.

**How to avoid:**
- Enforce the per-newsletter character truncation limit strictly in the sanitizer, not as an afterthought
- Calculate approximate token count (rough estimate: 1 token ≈ 4 characters) before invoking Claude CLI
- If estimated tokens exceed a safe threshold (e.g., 30K), split into two invocations and merge summaries
- Log the character count of every prompt sent to Claude
- The `--prompt` CLI flag should allow prompt tuning without code changes

**Warning signs:**
- Claude CLI exits with a non-zero code on large batches only
- Output is cut off mid-sentence
- Cron job runs longer on days with many newsletters

**Phase to address:**
Claude CLI integration phase and configuration design phase.

---

### Pitfall 6: Multipart MIME Walking Stops at Wrong Part — Missing HTML Body

**What goes wrong:**
Many newsletters send both `text/plain` and `text/html` parts in a `multipart/alternative` container, which itself may be nested inside `multipart/mixed` or `multipart/related`. A naive `msg.get_payload()` only returns the top-level part. The HTML body — which contains the actual newsletter content — is in a nested part and is silently skipped, leaving you with an empty or minimal plain text version.

**Why it happens:**
`email.message.Message.get_payload()` without `decode=True` on a multipart message returns a list of sub-messages, not the content. Many examples show the single-level case. `msg.walk()` is the correct recursive approach but isn't widely demonstrated.

**How to avoid:**
Use `msg.walk()` to iterate all parts. For each part:
1. Check `get_content_type()` — prefer `text/html` over `text/plain`
2. Check `get_content_maintype()` — skip `multipart` parts
3. Call `get_payload(decode=True)` on the selected leaf part
4. Decode using `get_content_charset()`, defaulting to `utf-8` with `errors='replace'`

Never rely on `get_payload()` at the top level for newsletter content.

**Warning signs:**
- Empty digests with no content
- Summaries that only contain "View this email in your browser" (the plain text fallback)
- Inconsistent results — some newsletters summarize fine, others are blank

**Phase to address:**
Email parsing and HTML extraction phase.

---

### Pitfall 7: Charset/Encoding Failures Corrupting Newsletter Content

**What goes wrong:**
Email bodies arrive encoded as `quoted-printable` or `base64` with charsets like `iso-8859-1`, `windows-1252`, or `UTF-8` with a BOM. Calling `.decode('utf-8')` on content that is actually `windows-1252` raises `UnicodeDecodeError`, crashing the pipeline. Alternatively, using `errors='ignore'` silently drops characters, corrupting content (e.g., em-dashes, curly quotes, accented names become garbage).

**Why it happens:**
`get_payload(decode=True)` handles the transfer encoding (base64/QP) but returns raw bytes — the charset decoding is a separate step that developers get wrong. BeautifulSoup's auto-detection ("Unicode Dammit") guesses correctly most of the time but occasionally misidentifies Latin encodings.

**How to avoid:**
- Always retrieve charset with `part.get_content_charset()` before decoding
- Fallback chain: declared charset → BeautifulSoup detection → `utf-8` with `errors='replace'`
- Pass the known charset explicitly to BeautifulSoup: `BeautifulSoup(raw_bytes, 'html.parser', from_encoding=charset)`
- Never use bare `.decode('utf-8')` without a fallback

**Warning signs:**
- `UnicodeDecodeError` in logs for specific senders
- Replacement characters (U+FFFD, shown as `?` or ``) in digest output
- Non-ASCII subject lines display as mojibake

**Phase to address:**
Email parsing and body extraction phase.

---

### Pitfall 8: Tracking URL Stripping Breaking Legitimate Links

**What goes wrong:**
The URL sanitizer strips all UTM/tracking parameters but some newsletter platforms use custom redirect schemes (`links.newsletter.com/click?url=...` or Substack's `substack.com/redirect`) where the entire URL structure is a tracker — there is no "clean" destination URL preserved in the link. Stripping the tracking wrapper leaves a broken or nonsensical URL. The requirement to "flag suspicious redirect wrappers" rather than strip them exists precisely to prevent this, but it is easy to accidentally over-strip.

**Why it happens:**
Regex-based URL cleaning is written to handle UTM parameters (safe to strip) but the same regex accidentally matches redirect wrappers where the destination is buried in an encoded query parameter. Both look similar at the regex level.

**How to avoid:**
Two-tier approach (as specified in PROJECT.md):
1. Strip tier: only known, safe tracking-only parameters — `utm_*`, `mc_eid`, `fbclid`, `yclid`, etc. These are never the canonical URL.
2. Flag tier: URLs where the domain is a known redirect proxy (`r.newsletter.co`, `links.`, `click.`, Mailchimp's `list-manage.com`) — preserve the full URL, mark it `[tracked-link]` in the sanitized output.
Write explicit tests for both tiers with real newsletter URL samples.

**Warning signs:**
- Links in digest output point to `links.example.com` domains with no destination context
- Clicking digest links lands on 404 pages
- Links reduced to bare domain with no path

**Phase to address:**
Sanitizer module — URL handling specifically.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode IMAP folder name (`Newsletters`) | Faster MVP | Fails if user renames folder or uses different structure | Never — make configurable from day one |
| Disable SSL verification for Bridge (`CERT_NONE`) | Avoids cert setup complexity | Technically unsafe pattern; acceptable only on loopback but documents badly | Acceptable for loopback localhost ONLY if commented |
| Single regex for all PII redaction | Simple to write | Misses edge cases (email in URL, encoded in HTML attributes) | MVP only — flag as known gap |
| No message deduplication (no state file) | Simpler code | Double-sends digest if cron runs twice; re-summarizes already-seen emails after restart | Never for cron — always track processed message UIDs |
| Assemble full prompt then truncate at end | Easy concatenation logic | May cut off mid-newsletter leaving Claude with incomplete input | Never — truncate per-newsletter before assembly |
| Use raw `imaplib` without UID mode | Matches stdlib examples | Wrong-message fetches on concurrent access | Never — always UID mode |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Proton Bridge IMAP (port 1143) | Using default `imaplib.IMAP4_SSL` which expects a CA-signed cert | Use `IMAP4` with explicit STARTTLS and a custom `ssl.SSLContext` that trusts the Bridge cert |
| Proton Bridge SMTP (port 1025) | Forgetting that Bridge SMTP also requires STARTTLS and the Bridge password (not Proton account password) | Use `smtplib.SMTP` with `starttls(context=...)` and Bridge-generated password from `.env` |
| Claude Code CLI (`claude -p`) | Passing email content as a command-line argument (`subprocess.run(['claude', '-p', content])`) | Pipe via stdin using `input=` parameter to `subprocess.run`; CLI args have OS length limits |
| Claude Code CLI | Assuming zero exit code always means valid output | Check that stdout is non-empty and contains expected structure; CLI may exit 0 with error message in stdout |
| IMAP SEARCH date filter | Using `SINCE` without understanding it uses server-local date (not UTC) and is date-only, not datetime | Use `SINCE` for broad filter, then re-filter in Python using `Date` header parsed with `email.utils.parsedate_to_datetime` |
| BeautifulSoup HTML parsing | Using `html.parser` which silently drops malformed attributes common in email HTML | Use `html.parser` as primary but be aware it drops some attributes; `lxml` is stricter but adds a dependency |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching full message body for all emails before filtering by date | Slow startup, excessive data transfer | Use IMAP `FETCH` with `RFC822.HEADER` first to get dates, then fetch full body only for matching messages | Any mailbox with > 100 messages |
| No per-newsletter character truncation before building prompt | Claude CLI hangs or rate-limits on heavy news days | Enforce truncation in sanitizer, not at prompt assembly | Any day with > 8-10 newsletters |
| Synchronous subprocess call with no timeout | Pipeline hangs forever if Claude CLI freezes or rate-limits | Always pass `timeout=` to `subprocess.run`; handle `TimeoutExpired` | First occurrence of Claude CLI hanging |
| Re-reading all saved daily digest files for weekly roll-up on every run | Slow weekly runs as archive grows | Weekly digest should only need the last 7 daily files; use date-range glob pattern | After ~52 weeks of daily files |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Bridge password in plain `.env` file committed to git | Credential exposure if repo is ever shared or pushed | Add `.env` to `.gitignore` immediately; provide `.env.example` with placeholder values; check `git status` before any commit |
| Logging full email headers or body content | PII appears in log files, defeating privacy model | Log only message UID, sender domain, and character count — never body content or full headers |
| Writing sanitizer output to a temp file with predictable name | Another local process could read pre-Claude content | Use `tempfile.NamedTemporaryFile` or pipe directly via `subprocess.run(input=...)` without any intermediate file |
| No validation that sanitizer actually ran before Claude call | If sanitizer raises and is silently caught, raw email content could reach Claude | Sanitizer must return a typed result object; calling code must verify the result is a sanitized payload, not raw content |
| Including original email Message-ID in digest | Message-ID can be correlated back to the original sender and timestamp by a recipient | Strip or omit Message-ID from the sanitized content; generate a new Message-ID for the digest email itself |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Sending digest even when there are no newsletters | User receives an empty or "nothing to summarize" email — clutter | Exit with code 2 (no newsletters) and send no email; log the skip |
| Digest HTML not rendering in Proton Mail (inline styles stripped) | Digest looks like unstyled plaintext — hard to skim | Use only inline CSS in the digest HTML template; Proton Mail supports inline styles reliably |
| Subject line not indicating the date | User can't distinguish "today's digest" from yesterday's in inbox | Always include date in subject: "Signals Digest — Wed Mar 11" |
| Theme grouping produces one giant section with all content | No benefit over reading raw newsletters | Enforce minimum 2-3 themes; if content is too homogeneous, create a "General" bucket rather than one flat list |
| Weekly digest re-summarizing the same content as recent dailies | User feels they've already seen it | Weekly digest should synthesize trends and contradictions across the week, not re-list the same bullet points |

---

## "Looks Done But Isn't" Checklist

- [ ] **IMAP connection:** Verify UID mode is used for both SEARCH and FETCH — test by deleting a message mid-run and confirming no wrong-message fetch
- [ ] **Sanitizer privacy boundary:** Assert that user's own email address, full sender address, and any test PII string are absent from sanitizer output
- [ ] **Subprocess safety:** Test with maximum realistic newsletter volume (10 newsletters × 5000 chars each) — confirm no deadlock or silent truncation
- [ ] **Duplicate prevention:** Run the cron script twice in a row — confirm second run produces no digest and exits with code 2
- [ ] **SSL/TLS:** Confirm connection works with Bridge cert verification, not with `CERT_NONE` globally disabled
- [ ] **Encoding resilience:** Test with a newsletter that uses `windows-1252` or `latin-1` charset — confirm no crash and no replacement characters in output
- [ ] **SMTP delivery:** Confirm digest actually arrives in inbox (not spam folder) when sent via Bridge SMTP — Proton Bridge may have quirks with self-addressed mail
- [ ] **HTML rendering:** Open the digest in Proton Mail webmail and Proton Mail iOS — confirm inline styles render correctly and no raw HTML is visible
- [ ] **Weekly digest:** Confirm it reads from saved daily files, not from IMAP — so it works even if some daily runs were skipped
- [ ] **Exit codes:** Verify each error path (no Bridge connection, no newsletters, Claude CLI error) exits with the correct code documented in PROJECT.md

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong-message fetch via sequence numbers | MEDIUM | Identify affected date range; re-run with UID mode; compare output |
| PII leaked to Claude | HIGH | Audit all prompts in log files; add sanitizer assertion tests; if logged to file, delete logs |
| Subprocess deadlock in cron | LOW | Kill hung process; add timeout to subprocess call; re-run with `--dry-run` to verify fix |
| Token limit exceeded, partial digest | LOW | Lower per-newsletter truncation limit in config; re-run for affected date with `--since` flag |
| SSL cert error after Bridge reinstall | LOW | Re-export Bridge cert; update cert path in config; verify with `--dry-run` |
| Duplicate digest sent | LOW | Single email duplicate is low impact; add UID state file to prevent recurrence |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| UID vs. sequence number | IMAP fetch implementation | Test: delete a message between SEARCH and FETCH; confirm correct message fetched |
| Bridge SSL cert | IMAP/SMTP connection setup | Test: Python connects successfully; assert `check_hostname` is not disabled globally |
| PII leaking through headers | Sanitizer module | Test: assert user email address absent from all sanitizer outputs |
| subprocess deadlock | Claude CLI integration | Test: pipe 50K chars; confirm returns within timeout with no hang |
| Token limit exhaustion | Claude CLI integration + config | Test: generate max-volume input; confirm graceful truncation and successful call |
| Multipart MIME body not found | Email parsing | Test: multipart/alternative and nested multipart/related emails; confirm HTML body extracted |
| Charset decode errors | Email parsing | Test: latin-1 and windows-1252 encoded newsletters; confirm no crash |
| URL over-stripping | Sanitizer module | Test: Mailchimp redirect URLs and Substack links; confirm redirect wrappers are flagged not stripped |
| Duplicate digest processing | State management / cron setup | Test: run script twice; confirm second run is a no-op |
| Digest HTML not rendering | Digest template design | Test: send test digest to self and inspect in Proton Mail webmail |

---

## Sources

- Python `imaplib` docs on UID commands and sequence number reassignment: https://docs.python.org/3/library/imaplib.html
- IMAPClient concepts (UID vs sequence numbers): https://imapclient.readthedocs.io/en/2.1.0/concepts.html
- Proton Bridge self-signed certificate documentation: https://proton.me/support/apple-mail-certificate
- Proton Bridge STARTTLS/SSL connection issues: https://proton.me/support/bridge-ssl-connection-issue
- Python subprocess deadlock warning (official docs): https://docs.python.org/3/library/subprocess.html
- Claude Code subprocess token overhead analysis: https://dev.to/jungjaehoon/why-claude-code-subagents-waste-50k-tokens-per-turn-and-how-to-fix-it-41ma
- Claude Code token limits reference: https://gist.github.com/jtbr/4f99671d1cee06b44106456958caba8b
- IMAP new messages since last check (UID patterns): https://dev.to/kehers/imap-new-messages-since-last-check-44gm
- Python cpython issue on multipart invariant violations: https://github.com/python/cpython/issues/106186
- BeautifulSoup encoding documentation: https://tedboy.github.io/bs4_doc/10_encodings.html
- HTML CSS email rendering current state: https://designmodo.com/html-css-emails/
- Idempotent pipeline patterns: https://dev.to/alexmercedcoder/idempotent-pipelines-build-once-run-safely-forever-2o2o
- Paperless-ngx Proton Bridge integration issues (real-world): https://github.com/paperless-ngx/paperless-ngx/issues/4043

---
*Pitfalls research for: Email processing pipeline — IMAP/Bridge/sanitizer/Claude CLI/SMTP digest*
*Researched: 2026-03-11*
