#!/usr/bin/env bash
# Uttera with nothing but curl. Same shapes as the OpenAI API.
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"

# ── text to speech ──
curl -sS --max-time 300 "$API/v1/audio/speech" \
  -H "Authorization: Bearer $UTTERA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","voice":"nova","input":"Your order ships tomorrow."}' \
  --output out.mp3
echo "wrote out.mp3 ($(stat -c%s out.mp3) bytes)"

# ── speech to text ──
# --max-time 7200: Uttera holds the connection so long recordings finish.
curl -sS --max-time 7200 "$API/v1/audio/transcriptions" \
  -H "Authorization: Bearer $UTTERA_API_KEY" \
  -F file=@out.mp3 -F model=whisper-1 -F response_format=text
