#!/usr/bin/env bash
# dry-run.sh — convenience wrapper that delegates to run-digest.sh --dry-run --verbose
#
# Fetches and sanitizes newsletters without calling Claude or sending email.
# Prints the sanitized newsletter text to stdout and exits 0.
#
# Passes any additional arguments through to run-digest.sh / daily.py.
#
# Usage:
#   ./scripts/dry-run.sh [--since HOURS] [--prompt FILE] ...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${SCRIPT_DIR}/run-digest.sh" --dry-run --verbose "$@"
