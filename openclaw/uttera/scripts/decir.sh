#!/usr/bin/env bash
# Convierte texto en voz. Uso: decir.sh "texto" [voz] [salida.mp3] [idioma]
set -euo pipefail
: "${UTTERA_API_KEY:?exporta tu clave: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
TEXTO="${1:?uso: decir.sh \"texto\" [voz] [salida.mp3] [idioma]}"
VOZ="${2:-nova}"; SAL="${3:-voz.mp3}"; IDIOMA="${4:-es}"
# ⚠ Los saltos de linea meten una pausa de 1,31 s CADA UNO y se cobran. Se
# quitan a proposito: si los quieres, manda el texto con ellos por tu cuenta.
TEXTO=$(printf '%s' "$TEXTO" | tr '\n' ' ')
python3 - "$TEXTO" "$VOZ" "$IDIOMA" > /tmp/uttera.body <<'PY'
import json, sys
print(json.dumps({"model": "tts-1", "input": sys.argv[1], "voice": sys.argv[2],
                  "language": sys.argv[3], "response_format": "mp3"}))
PY
curl -sS --max-time 300 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @/tmp/uttera.body \
     -o "$SAL" "$API/v1/audio/speech"
rm -f /tmp/uttera.body
echo "$SAL"
