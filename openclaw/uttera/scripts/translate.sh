#!/usr/bin/env bash
# Translate a recording. Usage: translate.sh file.mp3 target-language [mode]
#   mode: text (default) | both | audio
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?usage: translate.sh file.mp3 en [text|both|audio]}"
DEST="${2:?missing target language}"; MODE="${3:-text}"
[ -s "$F" ] || { echo "file is missing or empty: $F" >&2; exit 1; }
# ⚠ Only nine languages have a VOICE. Ask for audio in another and the request
# is rejected with 422 BEFORE spending anything, returning the valid list.
curl -sS --max-time 7200 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -F "file=@$F" "$API/v1/translate?target=$DEST&response=$MODE"
