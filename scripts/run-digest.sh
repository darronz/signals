#!/usr/bin/env bash
# run-digest.sh — cron wrapper for the Signals newsletter digest pipeline
#
# Checks prerequisites (Bridge IMAP port, claude CLI), activates the venv,
# then invokes scripts/daily.py with any arguments passed to this script.
#
# Usage:
#   ./scripts/run-digest.sh [--dry-run] [--since HOURS] [--verbose] ...
#
# Exit codes mirror daily.py:
#   0 — success (or --dry-run)
#   1 — prerequisite not met, config/auth error, IMAP error
#   2 — no newsletters found
#   3 — Claude CLI error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

# --- Prerequisite: Proton Mail Bridge IMAP port must be open ---
if ! nc -z 127.0.0.1 1143; then
    echo "ERROR: Proton Mail Bridge is not running on port 1143." >&2
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

# --- Run the pipeline ---
python "${PROJECT_DIR}/scripts/daily.py" "$@"
