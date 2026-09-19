#!/usr/bin/env bash
# Convierte texto en voz. Uso: decir.sh "texto" [voz] [salida.mp3] [idioma]
set -euo pipefail
: "${UTTERA_API_KEY:?exporta tu clave: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
TEXTO="${1:?uso: decir.sh \"texto\" [voz] [salida.mp3] [idioma]}"
# ⚠ La voz por defecto era `nova`, que es INGLESA, con el idioma forzado a
# `es`: eso lee castellano con reglas inglesas y suena "Mi Gasteria reservar
# una mesa". Ahora la voz por defecto es castellana y el idioma va VACIO: sin
# el, lo pone la voz, que es lo correcto y lo que documentamos. (2026-09-16)
VOZ="${2:-dora}"; SAL="${3:-voz.mp3}"; IDIOMA="${4:-}"
# ⚠ Los saltos de linea meten una pausa de 1,31 s CADA UNO y se cobran. Se
# quitan a proposito: si los quieres, manda el texto con ellos por tu cuenta.
TEXTO=$(printf '%s' "$TEXTO" | tr '\n' ' ')
python3 - "$TEXTO" "$VOZ" "$IDIOMA" > /tmp/uttera.body <<'PY'
import json, sys
cuerpo = {"model": "tts-1", "input": sys.argv[1], "voice": sys.argv[2],
          "response_format": "mp3"}
# Solo se manda `language` si lo pides: omitirlo deja que lo ponga la voz.
if len(sys.argv) > 3 and sys.argv[3]:
    cuerpo["language"] = sys.argv[3]
print(json.dumps(cuerpo))
PY
curl -sS --max-time 300 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @/tmp/uttera.body \
     -o "$SAL" "$API/v1/audio/speech"
rm -f /tmp/uttera.body
echo "$SAL"
