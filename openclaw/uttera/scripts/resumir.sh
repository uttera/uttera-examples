#!/usr/bin/env bash
# Resume una grabacion: resumen + transcripcion + tono + perfil + interlocutores.
# Uso: resumir.sh fichero.mp3 [idioma-del-resumen]
set -euo pipefail
: "${UTTERA_API_KEY:?exporta tu clave: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?uso: resumir.sh fichero.mp3 [idioma]}"
[ -s "$F" ] || { echo "el fichero no existe o esta vacio: $F" >&2; exit 1; }
Q=""; [ $# -ge 2 ] && Q="?language=$2"
# ⚠ 7200 s. Una grabacion de una hora tarda mas en subir de lo que tolera
# cualquier valor por defecto.
curl -sS --max-time 7200 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -F "file=@$F" "$API/v1/summarize$Q"
