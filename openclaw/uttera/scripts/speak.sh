#!/usr/bin/env bash
# Convierte texto en voz. Uso: speak.sh "texto" [voz] [salida.mp3] [idioma]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
TEXT="${1:?usage: speak.sh \"text\" [voice] [out.mp3] [language]}"
# ⚠ La voz por defecto era `nova`, que es INGLESA, con el idioma forzado a
# `es`: eso lee castellano con reglas inglesas y suena "Mi Gasteria reservar
# una mesa". Ahora la voz por defecto es castellana y el idioma va VACIO: sin
# el, lo pone la voz, que es lo correcto y lo que documentamos. (2026-09-16)
VOICE="${2:-dora}"; OUT="${3:-voice.mp3}"; LANG_="${4:-}"
# ⚠ Los saltos de linea meten una pausa de 1,31 s CADA UNO y se cobran. Se
# quitan a proposito: si los quieres, manda el texto con ellos por tu cuenta.
TEXT=$(printf '%s' "$TEXT" | tr '\n' ' ')
# ⚠ Fichero temporal PROPIO: con una ruta fija, dos agentes a la vez se
# pisaban el cuerpo de la peticion.
BODY=$(mktemp -t uttera.XXXXXX)
trap 'rm -f "$BODY"' EXIT
python3 - "$TEXT" "$VOICE" "$LANG_" > "$BODY" <<'PY'
import json, sys
cuerpo = {"model": "tts-1", "input": sys.argv[1], "voice": sys.argv[2],
          "response_format": "mp3"}
# Solo se manda `language` si lo pides: omitirlo deja que lo ponga la voz.
if len(sys.argv) > 3 and sys.argv[3]:
    cuerpo["language"] = sys.argv[3]
print(json.dumps(cuerpo))
PY
curl -sS --max-time 300 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @"$BODY" \
     -o "$OUT" "$API/v1/audio/speech"
echo "$OUT"
