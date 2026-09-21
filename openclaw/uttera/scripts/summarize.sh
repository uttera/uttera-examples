#!/usr/bin/env bash
# Summarise a recording: summary + transcript + tone + profile + who spoke when.
# Usage: summarize.sh file.mp3 [summary-language]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?usage: summarize.sh file.mp3 [language]}"
[ -s "$F" ] || { echo "file is missing or empty: $F" >&2; exit 1; }
Q=""; [ $# -ge 2 ] && Q="?language=$2"
# ⚠ 7200 s. A one-hour recording takes longer to upload than any default
# timeout will tolerate.
curl -sS --max-time 7200 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -F "file=@$F" "$API/v1/summarize$Q"
