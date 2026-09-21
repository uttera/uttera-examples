#!/usr/bin/env bash
# Traduce una grabacion. Uso: translate.sh fichero.mp3 idioma-destino [modo]
#   modo: text (por defecto) | both | audio
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?usage: translate.sh file.mp3 en [text|both|audio]}"
DEST="${2:?missing target language}"; MODE="${3:-text}"
[ -s "$F" ] || { echo "file is missing or empty: $F" >&2; exit 1; }
# ⚠ Solo nueve idiomas tienen VOZ. Si pides audio en otro, la peticion se
# rechaza con 422 ANTES de gastar nada y te devuelve la lista valida.
curl -sS --max-time 7200 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -F "file=@$F" "$API/v1/translate?target=$DEST&response=$MODE"
