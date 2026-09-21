#!/usr/bin/env bash
# Generate a sound effect. Usage: sound.sh "description" [seconds] [out.wav] [guidance]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
PROMPT="${1:?usage: sound.sh \"description\" [seconds] [out.wav] [guidance]}"
SECS="${2:-10}"; OUT="${3:-sound.wav}"; GUID="${4:-7}"
# ⚠ The model understands ENGLISH far better. `translate: true` has the service
# translate it before generating, and X-Prompt tells you the text it actually
# generated from.
BODY=$(mktemp -t uttera.XXXXXX); trap 'rm -f "$BODY"' EXIT
python3 - "$PROMPT" "$SECS" "$GUID" > "$BODY" <<'PY'
import json, sys
print(json.dumps({"prompt": sys.argv[1], "seconds": float(sys.argv[2]),
                  "guidance": float(sys.argv[3]), "translate": True}))
PY
curl -sS --max-time 600 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @"$BODY" \
     -o "$OUT" "$API/v1/audio/sfx"
echo "$OUT"
