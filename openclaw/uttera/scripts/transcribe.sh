#!/usr/bin/env bash
# Transcribe an audio file. Usage: transcribe.sh file.mp3 [language]
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?usage: transcribe.sh file.mp3 [language]}"
[ -s "$F" ] || { echo "file is missing or empty: $F" >&2; exit 1; }

# ⚠ Its OWN temp file, not a fixed path: a skill gets run by several agents at
# once, and with /tmp/uttera.hdr they were overwriting each other's headers.
HDR=$(mktemp -t uttera.XXXXXX)
trap 'rm -f "$HDR"' EXIT

args=(-sS --max-time 7200 -H "Authorization: Bearer $UTTERA_API_KEY"
      -F "file=@$F" -F "model=whisper-1" -F "response_format=text")
[ $# -ge 2 ] && args+=(-F "language=$2")
curl "${args[@]}" -D "$HDR" "$API/v1/audio/transcriptions"
echo
grep -i '^x-audio-duration:' "$HDR" | tr -d '\r' | sed 's/^/# seconds billed: /' || true
