"""
Tests for src/summarize.py — Claude CLI subprocess + prompt loading + newsletter concatenation.

Covers SUMM-01 through SUMM-07.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.models import CleanMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config():
    return {"claude_cmd": "claude", "claude_model": ""}


@pytest.fixture()
def prompt_file(tmp_path):
    p = tmp_path / "summarize.txt"
    p.write_text("You are a digest assistant.", encoding="utf-8")
    return str(p)


@pytest.fixture()
def two_messages():
    return [
        CleanMessage(
            subject="AI Weekly",
            sender_domain="morningbrew.com",
            date="2026-03-12",
            clean_text="AI is taking over the world.",
        ),
        CleanMessage(
            subject="Tech Trends",
            sender_domain="tldr.tech",
            date="2026-03-12",
            clean_text="Python 4 was announced.",
        ),
    ]


# ---------------------------------------------------------------------------
# SUMM-01 — Claude CLI call
# ---------------------------------------------------------------------------

def test_call_claude_success(prompt_file, config):
    """call_claude returns stdout from subprocess and uses input= kwarg."""
    mock_result = MagicMock(
        returncode=0,
        stdout="## Key Trends\n\n- AI adoption growing\n",
        stderr="",
    )

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from src.summarize import call_claude

        result = call_claude(prompt_file, "newsletter text", config)

    assert "## Key Trends" in result
    call_args = mock_run.call_args
    # input= kwarg must be present (Phase 2 decision: never Popen)
    assert call_args.kwargs.get("input") == "newsletter text"
    # -p flag must be in the command
    assert "-p" in call_args.args[0]


def test_call_claude_binary_not_found(prompt_file, config):
    """FileNotFoundError propagates when claude binary is missing."""
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        from src.summarize import call_claude

        with pytest.raises(FileNotFoundError):
            call_claude(prompt_file, "text", config)


def test_call_claude_nonzero_exit(prompt_file, config):
    """RuntimeError raised when claude exits non-zero; message includes exit code."""
    mock_result = MagicMock(returncode=1, stdout="", stderr="Rate limited")

    with patch("subprocess.run", return_value=mock_result):
        from src.summarize import call_claude

        with pytest.raises(RuntimeError, match="1"):
            call_claude(prompt_file, "text", config)


def test_call_claude_empty_output(prompt_file, config):
    """RuntimeError raised when claude returns empty stdout."""
    mock_result = MagicMock(returncode=0, stdout="   ", stderr="")

    with patch("subprocess.run", return_value=mock_result):
        from src.summarize import call_claude

        with pytest.raises(RuntimeError):
            call_claude(prompt_file, "text", config)


# ---------------------------------------------------------------------------
# SUMM-07 — Prompt loaded from external file
# ---------------------------------------------------------------------------

def test_prompt_loaded_from_file(tmp_path, config):
    """call_claude reads prompt content from the prompt_file path."""
    custom_prompt = tmp_path / "custom_prompt.txt"
    custom_prompt.write_text("Custom prompt content.", encoding="utf-8")

    mock_result = MagicMock(returncode=0, stdout="digest output", stderr="")

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from src.summarize import call_claude

        call_claude(str(custom_prompt), "newsletter text", config)

    # The prompt content must appear in the command
    call_args = mock_run.call_args
    cmd = call_args.args[0]
    assert "Custom prompt content." in cmd


def test_call_claude_missing_prompt_file(config):
    """FileNotFoundError raised when prompt file does not exist."""
    from src.summarize import call_claude

    with pytest.raises(FileNotFoundError):
        call_claude("/nonexistent/path/summarize.txt", "text", config)


# ---------------------------------------------------------------------------
# SUMM-02/03/04/05/06 — Prompt content assertions
# ---------------------------------------------------------------------------

PROMPT_PATH = Path("prompts/summarize.txt")


@pytest.mark.skipif(not PROMPT_PATH.exists(), reason="prompts/summarize.txt not yet created")
def test_prompt_contains_theme_instruction():
    """Prompt instructs grouping by theme/topic, not by source."""
    content = PROMPT_PATH.read_text(encoding="utf-8").lower()
    assert "topic" in content or "theme" in content


@pytest.mark.skipif(not PROMPT_PATH.exists(), reason="prompts/summarize.txt not yet created")
def test_prompt_contains_contradiction_instruction():
    """Prompt instructs Claude to flag contradictions."""
    content = PROMPT_PATH.read_text(encoding="utf-8").lower()
    assert "contradict" in content


@pytest.mark.skipif(not PROMPT_PATH.exists(), reason="prompts/summarize.txt not yet created")
def test_prompt_contains_word_target():
    """Prompt contains a word_target placeholder (templated, not static '500')."""
    content = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{word_target}" in content


# ---------------------------------------------------------------------------
# SUMM-05 — DIGEST_WORD_TARGET config key wired into prompt template
# ---------------------------------------------------------------------------

def test_word_target_injected_into_prompt(tmp_path):
    """call_claude substitutes config['digest_word_target'] into {word_target} placeholder."""
    prompt_file = tmp_path / "prompt_with_target.txt"
    prompt_file.write_text("Target ~{word_target} words.", encoding="utf-8")

    config = {"claude_cmd": "claude", "claude_model": "", "digest_word_target": 800}
    mock_result = MagicMock(returncode=0, stdout="digest output", stderr="")

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from src.summarize import call_claude
        call_claude(str(prompt_file), "newsletter text", config)

    cmd = mock_run.call_args.args[0]
    # "800" must be in the -p argument, not "500"
    prompt_arg = cmd[cmd.index("-p") + 1]
    assert "800" in prompt_arg, f"Expected '800' in prompt, got: {prompt_arg!r}"
    assert "500" not in prompt_arg, "Default '500' should NOT appear when config specifies 800"


def test_word_target_defaults_to_500_when_missing(tmp_path):
    """call_claude falls back to 500 when digest_word_target is absent from config."""
    prompt_file = tmp_path / "prompt_no_target.txt"
    prompt_file.write_text("Target ~{word_target} words.", encoding="utf-8")

    config = {"claude_cmd": "claude", "claude_model": ""}  # no digest_word_target key
    mock_result = MagicMock(returncode=0, stdout="digest output", stderr="")

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from src.summarize import call_claude
        call_claude(str(prompt_file), "newsletter text", config)

    cmd = mock_run.call_args.args[0]
    prompt_arg = cmd[cmd.index("-p") + 1]
    assert "500" in prompt_arg, f"Expected default '500' in prompt, got: {prompt_arg!r}"


@pytest.mark.skipif(not PROMPT_PATH.exists(), reason="prompts/summarize.txt not yet created")
def test_prompt_contains_sources_instruction():
    """Prompt instructs Claude to list sources."""
    content = PROMPT_PATH.read_text(encoding="utf-8").lower()
    assert "source" in content


# ---------------------------------------------------------------------------
# Newsletter concatenation — format_newsletter_input
# ---------------------------------------------------------------------------

def test_format_newsletter_input(two_messages):
    """Two CleanMessages produce correct headers and dividers."""
    from src.summarize import format_newsletter_input

    result = format_newsletter_input(two_messages)

    assert "Source: morningbrew.com" in result
    assert "Subject: AI Weekly" in result
    assert "Date: 2026-03-12" in result
    assert "Source: tldr.tech" in result
    assert "Subject: Tech Trends" in result
    assert "---" in result
    assert "AI is taking over the world." in result
    assert "Python 4 was announced." in result


def test_format_newsletter_input_empty():
    """Empty message list returns empty string."""
    from src.summarize import format_newsletter_input

    assert format_newsletter_input([]) == ""


def test_format_newsletter_input_single_message():
    """Single message produces correct header without extra dividers between messages."""
    msg = CleanMessage(
        subject="Solo Newsletter",
        sender_domain="example.com",
        date="2026-03-12",
        clean_text="Only content here.",
    )

    from src.summarize import format_newsletter_input

    result = format_newsletter_input([msg])

    assert "Source: example.com" in result
    assert "Solo Newsletter" in result
    assert "Only content here." in result


def test_call_claude_with_model_flag(tmp_path):
    """When claude_model is set, --model flag is added to command."""
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("prompt", encoding="utf-8")
    config = {"claude_cmd": "claude", "claude_model": "claude-opus-4-5"}

    mock_result = MagicMock(returncode=0, stdout="digest", stderr="")

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        from src.summarize import call_claude

        call_claude(str(prompt_file), "text", config)

    cmd = mock_run.call_args.args[0]
    assert "--model" in cmd
    assert "claude-opus-4-5" in cmd
