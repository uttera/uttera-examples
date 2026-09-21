#!/usr/bin/env bash
# Turn text into speech. Usage: speak.sh "text" [voice] [out.mp3] [language]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
TEXT="${1:?usage: speak.sh \"text\" [voice] [out.mp3] [language]}"
# ⚠ The default voice used to be `nova`, which is ENGLISH, with the language
# forced to `es`: that reads Spanish with English rules and comes out as "Mi
# Gasteria reservar una mesa". The default voice is now a Spanish one and the
# language is left EMPTY: without it, the voice sets it, which is correct and
# what we document. (2026-09-16)
VOICE="${2:-dora}"; OUT="${3:-voice.mp3}"; LANG_="${4:-}"
# ⚠ Line breaks insert a 1.31 s pause EACH and are billed. They are stripped
# on purpose: if you want them, send the text with them yourself.
TEXT=$(printf '%s' "$TEXT" | tr '\n' ' ')
# ⚠ Its OWN temp file: with a fixed path, two agents at once were overwriting
# each other's request body.
BODY=$(mktemp -t uttera.XXXXXX)
trap 'rm -f "$BODY"' EXIT
python3 - "$TEXT" "$VOICE" "$LANG_" > "$BODY" <<'PY'
import json, sys
cuerpo = {"model": "tts-1", "input": sys.argv[1], "voice": sys.argv[2],
          "response_format": "mp3"}
# `language` is only sent if you ask for it: leaving it out lets the voice set it.
if len(sys.argv) > 3 and sys.argv[3]:
    cuerpo["language"] = sys.argv[3]
print(json.dumps(cuerpo))
PY
curl -sS --max-time 300 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @"$BODY" \
     -o "$OUT" "$API/v1/audio/speech"
echo "$OUT"
