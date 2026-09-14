#!/usr/bin/env bash
# Transcribe un audio. Uso: transcribir.sh fichero.mp3 [idioma]
set -euo pipefail
: "${UTTERA_API_KEY:?exporta tu clave: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?uso: transcribir.sh fichero.mp3 [idioma]}"
[ -s "$F" ] || { echo "el fichero no existe o esta vacio: $F" >&2; exit 1; }

args=(-sS --max-time 7200 -H "Authorization: Bearer $UTTERA_API_KEY"
      -F "file=@$F" -F "model=whisper-1" -F "response_format=text")
[ $# -ge 2 ] && args+=(-F "language=$2")
curl "${args[@]}" -D /tmp/uttera.hdr "$API/v1/audio/transcriptions"
echo
grep -i '^x-audio-duration:' /tmp/uttera.hdr | tr -d '\r' | sed 's/^/# segundos facturados: /' || true
rm -f /tmp/uttera.hdr
