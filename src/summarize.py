"""
Summarization module for the Signals newsletter digest pipeline.

Pipes sanitized newsletter text to Claude CLI via subprocess stdin
and captures the digest response.

Anti-patterns avoided (per Phase 2 decisions and research):
- No Popen (deadlock risk on large newsletter batches)
- No sys.exit() in library code — raises exceptions for orchestrator
- No load_dotenv() at import time — receives config as parameter
- No hardcoded prompt text — loaded from external prompts/summarize.txt
"""

import os
import subprocess
from pathlib import Path

from src.models import CleanMessage


def format_newsletter_input(messages: list[CleanMessage]) -> str:
    """Concatenate clean messages for Claude stdin.

    Each message is prefixed with a source header and separated by '---' dividers.
    The format is: Source: {domain} | Subject: {subject} | Date: {date}

    Args:
        messages: List of sanitized CleanMessage objects.

    Returns:
        Formatted string ready for Claude stdin, or empty string if list is empty.
    """
    if not messages:
        return ""

    parts = []
    for msg in messages:
        header = f"Source: {msg.sender_domain} | Subject: {msg.subject} | Date: {msg.date}"
        parts.append(f"---\n{header}\n\n{msg.clean_text}")

    return "\n\n".join(parts)


def call_claude(prompt_file: str, newsletter_text: str, config: dict) -> str:
    """Call Claude CLI and return the digest text.

    Reads the prompt from prompt_file, then calls the Claude CLI binary
    with the prompt as a -p argument and newsletter_text piped via stdin.
    Uses subprocess.run(input=...) — never Popen (Phase 2 decision).

    Args:
        prompt_file: Path to the prompt file (e.g. prompts/summarize.txt).
        newsletter_text: Concatenated sanitized newsletter content (from
            format_newsletter_input).
        config: Dict with 'claude_cmd' (str) and 'claude_model' (str) keys.

    Returns:
        Claude's response text (the digest), stripped of leading/trailing whitespace.

    Raises:
        FileNotFoundError: If the prompt file does not exist, or if the claude
            binary is not found in PATH.
        RuntimeError: If claude exits with a non-zero return code (message
            includes the exit code and stderr), or if claude returns empty stdout.
    """
    prompt = Path(prompt_file).read_text(encoding="utf-8")
    word_target = config.get("digest_word_target", 500)
    prompt = prompt.format(word_target=word_target)

    cmd = [config["claude_cmd"], "-p", prompt, "--output-format", "text"]
    if config.get("claude_model"):
        cmd += ["--model", config["claude_model"]]

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=newsletter_text,
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Claude CLI exited {result.returncode}: {result.stderr}"
        )

    digest = result.stdout.strip()
    if not digest:
        raise RuntimeError("Claude CLI returned empty output")

    return digest
