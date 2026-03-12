#!/usr/bin/env bash
# run-weekly.sh — cron wrapper for the Signals newsletter weekly rollup pipeline
#
# Checks prerequisites (Bridge IMAP port, claude CLI), activates the venv,
# then invokes scripts/weekly.py with any arguments passed to this script.
#
# Usage:
#   ./scripts/run-weekly.sh [--dry-run] [--verbose] ...
#
# Exit codes mirror weekly.py:
#   0 — success (or --dry-run)
#   1 — prerequisite not met, config/auth error, IMAP error
#   2 — no newsletters found
#   3 — Claude CLI error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

# --- Load IMAP_PORT from .env (default: 1143) ---
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

# --- Run the pipeline ---
python "${PROJECT_DIR}/scripts/weekly.py" "$@"
