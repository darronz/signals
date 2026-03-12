"""
Unit tests for scripts/weekly.py — Weekly Rollup Script.

TDD cycle: tests written first (RED), then implementation makes them GREEN.

Coverage:
  - find_daily_digests: file discovery with date filtering
  - format_weekly_input: concatenation with date headers
  - weekly_archive_filename: ISO week-based filename generation
  - save_weekly_archive: writes file to output_dir
  - main(): CLI integration — dry-run, exit codes, email/markdown delivery
  - Smoke checks: README.md exists and contains all config keys
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_daily_files(tmp_path: Path, days: list[str]) -> list[Path]:
    """Create fake digest-YYYY-MM-DD.md files in tmp_path."""
    paths = []
    for day in days:
        p = tmp_path / f"digest-{day}.md"
        p.write_text(f"# Digest {day}\n\nContent for {day}.", encoding="utf-8")
        paths.append(p)
    return paths


def _minimal_config(tmp_path: Path, output_format: str = "markdown") -> dict:
    return {
        "output_dir": str(tmp_path),
        "claude_cmd": "claude",
        "claude_model": "",
        "output_format": output_format,
        "digest_recipient": "test@example.com",
        "imap_username": "sender@proton.me",
        "imap_password": "secret",
        "smtp_host": "127.0.0.1",
        "smtp_port": 1025,
    }


# ---------------------------------------------------------------------------
# find_daily_digests
# ---------------------------------------------------------------------------

class TestFindDailyDigests:
    def test_returns_files_in_window(self, tmp_path: Path) -> None:
        """Files within since_days window are returned, oldest-first."""
        import scripts.weekly as w

        today = date.today()
        days_in = [
            (today - timedelta(days=6)).isoformat(),
            (today - timedelta(days=3)).isoformat(),
            today.isoformat(),
        ]
        days_out = [(today - timedelta(days=10)).isoformat()]
        _make_daily_files(tmp_path, days_in + days_out)

        result = w.find_daily_digests(tmp_path, since_days=7)
        stems = [f.stem.replace("digest-", "") for f in result]
        assert sorted(days_in) == stems  # oldest-first == alphabetical for ISO dates
        for d in days_out:
            assert d not in stems

    def test_excludes_files_outside_window(self, tmp_path: Path) -> None:
        """Files older than since_days are excluded."""
        import scripts.weekly as w

        today = date.today()
        old_day = (today - timedelta(days=30)).isoformat()
        _make_daily_files(tmp_path, [old_day])

        result = w.find_daily_digests(tmp_path, since_days=7)
        assert result == []

    def test_ignores_weekly_files(self, tmp_path: Path) -> None:
        """weekly-YYYY-WXX.md files are not returned (digest-* prefix only)."""
        import scripts.weekly as w

        today = date.today()
        day_str = today.isoformat()
        (tmp_path / f"digest-{day_str}.md").write_text("daily content", encoding="utf-8")
        (tmp_path / "weekly-2026-W11.md").write_text("weekly content", encoding="utf-8")

        result = w.find_daily_digests(tmp_path, since_days=7)
        names = [f.name for f in result]
        assert f"digest-{day_str}.md" in names
        assert "weekly-2026-W11.md" not in names

    def test_skips_malformed_filenames(self, tmp_path: Path) -> None:
        """Files with unparseable date stems are silently skipped."""
        import scripts.weekly as w

        (tmp_path / "digest-not-a-date.md").write_text("bad", encoding="utf-8")
        today_str = date.today().isoformat()
        (tmp_path / f"digest-{today_str}.md").write_text("good", encoding="utf-8")

        result = w.find_daily_digests(tmp_path, since_days=7)
        names = [f.name for f in result]
        assert f"digest-{today_str}.md" in names
        assert "digest-not-a-date.md" not in names

    def test_returns_empty_list_when_no_files(self, tmp_path: Path) -> None:
        """Empty output_dir returns empty list."""
        import scripts.weekly as w

        result = w.find_daily_digests(tmp_path, since_days=7)
        assert result == []

    def test_sorted_oldest_first(self, tmp_path: Path) -> None:
        """Returned files are sorted oldest-first."""
        import scripts.weekly as w

        today = date.today()
        days = [
            today.isoformat(),
            (today - timedelta(days=2)).isoformat(),
            (today - timedelta(days=4)).isoformat(),
        ]
        _make_daily_files(tmp_path, days)

        result = w.find_daily_digests(tmp_path, since_days=7)
        dates = [date.fromisoformat(f.stem.replace("digest-", "")) for f in result]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# format_weekly_input
# ---------------------------------------------------------------------------

class TestFormatWeeklyInput:
    def test_concatenates_with_date_headers(self, tmp_path: Path) -> None:
        """Each file gets a --- + Date: header; content follows."""
        import scripts.weekly as w

        days = ["2026-03-06", "2026-03-07"]
        files = _make_daily_files(tmp_path, days)

        result = w.format_weekly_input(files)

        assert "---\nDate: 2026-03-06" in result
        assert "Content for 2026-03-06." in result
        assert "---\nDate: 2026-03-07" in result
        assert "Content for 2026-03-07." in result

    def test_sections_separated_by_double_newline(self, tmp_path: Path) -> None:
        """Sections are joined with \\n\\n."""
        import scripts.weekly as w

        days = ["2026-03-06", "2026-03-07"]
        files = _make_daily_files(tmp_path, days)

        result = w.format_weekly_input(files)
        # The two date-header blocks should be separated by a blank line
        assert "\n\n---\nDate: 2026-03-07" in result

    def test_empty_list_returns_empty_string(self) -> None:
        import scripts.weekly as w

        assert w.format_weekly_input([]) == ""


# ---------------------------------------------------------------------------
# weekly_archive_filename
# ---------------------------------------------------------------------------

class TestWeeklyArchiveFilename:
    def test_uses_iso_week(self) -> None:
        """Filename uses ISO week number, not calendar week."""
        import scripts.weekly as w

        d = date(2026, 3, 12)
        iso = d.isocalendar()
        expected = f"weekly-{iso.year}-W{iso.week:02d}.md"
        assert w.weekly_archive_filename(d) == expected

    def test_year_boundary_correctness(self) -> None:
        """Dec 31 that falls in ISO week 1 of next year uses next year."""
        import scripts.weekly as w

        # 2026-12-31 is in ISO week 53 of 2026
        d = date(2026, 12, 31)
        iso = d.isocalendar()
        result = w.weekly_archive_filename(d)
        assert result == f"weekly-{iso.year}-W{iso.week:02d}.md"
        # Verify we're using iso.year not d.year (they could differ)
        assert str(iso.year) in result

    def test_format_is_weekly_yyyy_wxx(self) -> None:
        """Filename format is weekly-YYYY-WXX.md with zero-padded week."""
        import scripts.weekly as w

        # Week 1 of 2026
        d = date(2026, 1, 5)
        result = w.weekly_archive_filename(d)
        assert result.startswith("weekly-")
        assert result.endswith(".md")
        # Week number should be zero-padded to 2 digits
        parts = result.replace("weekly-", "").replace(".md", "").split("-W")
        assert len(parts) == 2
        assert len(parts[1]) == 2  # zero-padded


# ---------------------------------------------------------------------------
# save_weekly_archive
# ---------------------------------------------------------------------------

class TestSaveWeeklyArchive:
    def test_creates_file_with_weekly_filename(self, tmp_path: Path) -> None:
        """Saved file uses weekly_archive_filename format."""
        import scripts.weekly as w

        config = {"output_dir": str(tmp_path)}
        path = w.save_weekly_archive("# Weekly Digest\n\nContent.", config)

        assert path.exists()
        assert path.name.startswith("weekly-")
        assert path.name.endswith(".md")

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        """output_dir is created if it doesn't exist."""
        import scripts.weekly as w

        new_dir = tmp_path / "new_output"
        config = {"output_dir": str(new_dir)}
        w.save_weekly_archive("content", config)
        assert new_dir.exists()

    def test_writes_correct_content(self, tmp_path: Path) -> None:
        """File content matches the digest_md argument."""
        import scripts.weekly as w

        content = "# Weekly\n\nTrends here."
        config = {"output_dir": str(tmp_path)}
        path = w.save_weekly_archive(content, config)
        assert path.read_text(encoding="utf-8") == content

    def test_uses_default_output_dir(self, tmp_path: Path) -> None:
        """Defaults to ./output when output_dir not in config."""
        import scripts.weekly as w

        # We patch date.today to get a predictable filename, then check default dir
        config = {}  # no output_dir key
        with patch("scripts.weekly.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 12)
            mock_date.fromisoformat = date.fromisoformat
            path = w.save_weekly_archive("content", config)
        assert str(path).startswith("./output") or "output" in str(path)


# ---------------------------------------------------------------------------
# main() — CLI integration
# ---------------------------------------------------------------------------

class TestMainDryRun:
    def test_dry_run_exits_0(self, tmp_path: Path, capsys) -> None:
        """--dry-run exits 0 without calling Claude."""
        import scripts.weekly as w

        today = date.today()
        for i in range(7):
            day = (today - timedelta(days=i)).isoformat()
            (tmp_path / f"digest-{day}.md").write_text(f"Content {day}", encoding="utf-8")

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch.object(w, "call_claude") as mock_claude, \
             patch("sys.argv", ["weekly.py", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 0
        mock_claude.assert_not_called()

    def test_dry_run_reports_file_count(self, tmp_path: Path, capsys) -> None:
        """--dry-run prints the number of files found."""
        import scripts.weekly as w

        today = date.today()
        for i in range(7):
            day = (today - timedelta(days=i)).isoformat()
            (tmp_path / f"digest-{day}.md").write_text("Content", encoding="utf-8")

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch.object(w, "call_claude"), \
             patch("sys.argv", ["weekly.py", "--dry-run"]):
            with pytest.raises(SystemExit):
                w.main()

        captured = capsys.readouterr()
        assert "7" in captured.out


class TestMainExitCodes:
    def test_exit_2_when_no_daily_files(self, tmp_path: Path) -> None:
        """Exit code 2 when zero daily digest files found."""
        import scripts.weekly as w

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 2

    def test_exit_3_on_claude_runtime_error(self, tmp_path: Path) -> None:
        """Exit code 3 when Claude CLI returns non-zero (RuntimeError)."""
        import scripts.weekly as w

        today = date.today().isoformat()
        (tmp_path / f"digest-{today}.md").write_text("Content", encoding="utf-8")

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch.object(w, "call_claude", side_effect=RuntimeError("Claude failed")), \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 3

    def test_exit_3_on_claude_file_not_found(self, tmp_path: Path) -> None:
        """Exit code 3 when Claude binary not found (FileNotFoundError)."""
        import scripts.weekly as w

        today = date.today().isoformat()
        (tmp_path / f"digest-{today}.md").write_text("Content", encoding="utf-8")

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch.object(w, "call_claude", side_effect=FileNotFoundError("claude not found")), \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 3

    def test_exit_1_on_config_value_error(self, tmp_path: Path) -> None:
        """Exit code 1 when load_config raises ValueError."""
        import scripts.weekly as w

        with patch.object(w, "load_config", side_effect=ValueError("missing key")), \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 1


class TestMainDelivery:
    def test_sends_email_when_output_format_is_email(self, tmp_path: Path) -> None:
        """send_digest_email is called when output_format=email."""
        import scripts.weekly as w

        today = date.today().isoformat()
        (tmp_path / f"digest-{today}.md").write_text("Content", encoding="utf-8")

        cfg = _minimal_config(tmp_path, output_format="email")

        with patch.object(w, "load_config", return_value=cfg), \
             patch.object(w, "call_claude", return_value="# Weekly Digest\n\nTrends."), \
             patch.object(w, "send_digest_email") as mock_send, \
             patch.object(w, "markdown_to_html", return_value="<html>html</html>"), \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 0
        mock_send.assert_called_once()

    def test_saves_weekly_archive_on_success(self, tmp_path: Path) -> None:
        """Weekly archive file is written to output_dir."""
        import scripts.weekly as w

        today = date.today().isoformat()
        (tmp_path / f"digest-{today}.md").write_text("Content", encoding="utf-8")

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch.object(w, "call_claude", return_value="# Weekly Digest\n\nTrends."), \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 0
        weekly_files = list(tmp_path.glob("weekly-*.md"))
        assert len(weekly_files) == 1

    def test_no_email_when_output_format_is_markdown(self, tmp_path: Path) -> None:
        """send_digest_email is NOT called when output_format=markdown."""
        import scripts.weekly as w

        today = date.today().isoformat()
        (tmp_path / f"digest-{today}.md").write_text("Content", encoding="utf-8")

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch.object(w, "call_claude", return_value="# Weekly Digest\n\nTrends."), \
             patch.object(w, "send_digest_email") as mock_send, \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        assert exc_info.value.code == 0
        mock_send.assert_not_called()

    def test_weekly_calls_claude_with_weekly_prompt(self, tmp_path: Path) -> None:
        """call_claude is invoked with the weekly prompt path."""
        import scripts.weekly as w

        today = date.today().isoformat()
        (tmp_path / f"digest-{today}.md").write_text("Content", encoding="utf-8")

        with patch.object(w, "load_config", return_value=_minimal_config(tmp_path)), \
             patch.object(w, "call_claude", return_value="# Weekly\n\nContent.") as mock_claude, \
             patch("sys.argv", ["weekly.py"]):
            with pytest.raises(SystemExit):
                w.main()

        assert mock_claude.called
        prompt_arg = mock_claude.call_args[0][0]
        assert "weekly" in str(prompt_arg).lower()

    def test_since_flag_overrides_default_days(self, tmp_path: Path) -> None:
        """--since N overrides the default 7-day window."""
        import scripts.weekly as w

        today = date.today()
        # Put a file 10 days ago — only visible with --since 14
        old_day = (today - timedelta(days=10)).isoformat()
        (tmp_path / f"digest-{old_day}.md").write_text("Old content", encoding="utf-8")

        cfg = _minimal_config(tmp_path)

        with patch.object(w, "load_config", return_value=cfg), \
             patch.object(w, "call_claude", return_value="# Weekly\n\nContent."), \
             patch("sys.argv", ["weekly.py", "--since", "14"]):
            with pytest.raises(SystemExit) as exc_info:
                w.main()

        # File 10 days ago should be found with --since 14 → not exit 2
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Smoke checks: README.md
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent


class TestReadmeSmoke:
    def test_readme_exists(self) -> None:
        """README.md exists at project root."""
        assert (_PROJECT_ROOT / "README.md").exists(), "README.md not found at project root"

    def test_readme_contains_all_config_keys(self) -> None:
        """README.md documents all keys returned by load_config()."""
        readme = (_PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

        # All env var keys from src/config.py load_config()
        required_keys = [
            "IMAP_HOST",
            "IMAP_PORT",
            "IMAP_USERNAME",
            "IMAP_PASSWORD",
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_SECURITY",
            "NEWSLETTER_FOLDER",
            "NEWSLETTER_SENDERS",
            "FETCH_SINCE_HOURS",
            "CLAUDE_CMD",
            "CLAUDE_MODEL",
            "OUTPUT_FORMAT",
            "OUTPUT_DIR",
            "DIGEST_RECIPIENT",
            "USER_DISPLAY_NAME",
            "REDACT_PATTERNS",
            "MAX_BODY_CHARS",
            "DIGEST_WORD_TARGET",
        ]

        missing = [k for k in required_keys if k not in readme]
        assert not missing, f"README.md missing config keys: {missing}"
