#!/usr/bin/env bash
# Score how well a recording pronounces a target sentence.
# Usage: pronounce.sh recording.webm "the sentence you were reading" [language]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?usage: pronounce.sh file.webm \"target text\" [language]}"
TEXT="${2:?missing the target text}"; LANG_="${3:-es}"
[ -s "$F" ] || { echo "file is missing or empty: $F" >&2; exit 1; }
# ⚠ `explain=false` is much cheaper. The phoneme comparison is quick; writing
# the explanation calls a language model and costs ~30x more. Ask for it when
# you want to know WHAT is going wrong, not on every repetition.
EXPLAIN="${4:-true}"
curl -sS --max-time 300 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -F "file=@$F" -F "text=$TEXT" -F "language=$LANG_" -F "explain=$EXPLAIN" \
     "$API/v1/pronunciation"
