#!/usr/bin/env bash
# Generate music. Usage: music.sh "description" [seconds] [out.wav] [seed]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
PROMPT="${1:?usage: music.sh \"description\" [seconds] [out.wav] [seed]}"
SECS="${2:-60}"; OUT="${3:-music.wav}"; SEED="${4:--1}"
# ⚠ Here you DO pay per second, unlike sound effects: this model generates
# variable-length output. A 3-minute piece costs less than ONE sound effect.
BODY=$(mktemp -t uttera.XXXXXX); trap 'rm -f "$BODY"' EXIT
python3 - "$PROMPT" "$SECS" "$SEED" > "$BODY" <<'PY'
import json, sys
cuerpo = {"prompt": sys.argv[1], "seconds": float(sys.argv[2]), "translate": True}
if int(sys.argv[3]) >= 0:
    cuerpo["seed"] = int(sys.argv[3])
print(json.dumps(cuerpo))
PY
curl -sS --max-time 900 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @"$BODY" \
     -o "$OUT" "$API/v1/audio/music"
echo "$OUT"
