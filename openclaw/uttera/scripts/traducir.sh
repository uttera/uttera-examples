#!/usr/bin/env bash
# Traduce una grabacion. Uso: traducir.sh fichero.mp3 idioma-destino [modo]
#   modo: text (por defecto) | both | audio
set -euo pipefail
: "${UTTERA_API_KEY:?exporta tu clave: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?uso: traducir.sh fichero.mp3 en [text|both|audio]}"
DEST="${2:?falta el idioma destino}"; MODO="${3:-text}"
[ -s "$F" ] || { echo "el fichero no existe o esta vacio: $F" >&2; exit 1; }
# ⚠ Solo nueve idiomas tienen VOZ. Si pides audio en otro, la peticion se
# rechaza con 422 ANTES de gastar nada y te devuelve la lista valida.
curl -sS --max-time 7200 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -F "file=@$F" "$API/v1/translate?target=$DEST&response=$MODO"
