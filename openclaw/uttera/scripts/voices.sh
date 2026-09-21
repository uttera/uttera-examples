#!/usr/bin/env bash
# List the available voices. Usage: voices.sh [language]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
Q=""; [ $# -ge 1 ] && Q="?language=$1"
curl -sS --max-time 60 -H "Authorization: Bearer $UTTERA_API_KEY" \
     "$API/v1/audio/voices$Q"
