#!/usr/bin/env bash
# Transcribe one Asterisk recording and write the text next to it.
#
# This is the version we run in production, with the site-specific bits removed.
# It is called by MixMonitor as a background sidecar, so it starts WHILE the call
# is still being recorded:
#
#   exten => s,n,MixMonitor(${MONITOR_FILE}.wav,b,transcribe-recording.sh ${UNIQUEID} &)
#
#   reads   <DIR>/<uniqueid>.wav    (still growing while the call is live)
#   writes  <DIR>/<uniqueid>.txt    the transcript
#   writes  <DIR>/<uniqueid>-analysis.json   tone, speaker profile, speakers
#
# Config comes from the environment or from an env file. The API key never goes
# in this script and never in the dialplan.
set -u

ID="${1:-}"
[[ -n "$ID" ]] || { echo "usage: $0 <uniqueid>" >&2; exit 1; }

ENV_FILE="${UTTERA_ENV:-/etc/uttera/uttera.env}"
[[ -r "$ENV_FILE" ]] && . "$ENV_FILE"

DIR="${RECORDINGS_DIR:-/var/spool/asterisk/monitor}"
API="${UTTERA_API:-https://api.uttera.ai}"
KEY="${UTTERA_API_KEY:-}"
LANG_CODE="${UTTERA_LANG:-es}"
MODEL="${UTTERA_MODEL:-whisper-1}"
# Set to 0 to skip the analysis and only transcribe.
ANALYSE="${UTTERA_ANALYSE:-1}"
LOG="${UTTERA_LOG:-/var/log/uttera-recordings.log}"

AUDIO="$DIR/$ID.wav"
TEXT="$DIR/$ID.txt"
ANALYSIS="$DIR/$ID-analysis.json"

[[ -w "$(dirname "$LOG")" ]] || LOG=/tmp/uttera-recordings.log
log() { printf '[%s] %s: %s\n' "$(date '+%F %T')" "$ID" "$*" >>"$LOG" 2>/dev/null; }

[[ -n "$KEY" ]] || { log "no UTTERA_API_KEY"; echo "missing UTTERA_API_KEY" >&2; exit 1; }

# A marker so the dialplan (or a dashboard) can tell "in progress" from "failed".
echo "[transcribing...]" >"$TEXT"

# ── wait for the recording to be finished ───────────────────────────────────
# Two different situations, and telling them apart matters:
#
#   live      MixMonitor is still writing. The file grows. Poll until the size
#             stops changing for three reads in a row.
#   historic  we are reprocessing an old file. It will never change, so polling
#             would just waste a minute per file.
#
# The test is the modification time: anything older than a minute is historic.
NOW=$(date +%s)
MTIME=$(stat -c%Y "$AUDIO" 2>/dev/null || echo 0)
if (( NOW - MTIME > 60 )); then
    SIZE=$(stat -c%s "$AUDIO" 2>/dev/null || echo 0)
    log "historic file ($((NOW - MTIME))s old, $SIZE bytes), not waiting"
else
    prev=0; stable=0; tries=0
    while (( tries < 60 )); do
        SIZE=$(stat -c%s "$AUDIO" 2>/dev/null || echo 0)
        if [[ "$SIZE" -eq "$prev" && "$SIZE" -gt 1024 ]]; then
            (( ++stable >= 3 )) && break
        else
            stable=0
        fi
        prev=$SIZE; sleep 2; (( ++tries ))
    done
    log "live file stable at $SIZE bytes after $tries polls"
fi

# ⚠ Do NOT send near-empty audio. Whisper does not return an empty string when
# given silence: it invents a sentence -usually something like "Thanks for
# watching" - because that is what its training data is full of. You would pay
# for a hallucination and, worse, act on it.
if [[ "${SIZE:-0}" -lt 1024 ]]; then
    echo "" >"$TEXT"
    log "file too small ($SIZE bytes), nothing to transcribe"
    exit 0
fi

# ── transcribe, and analyse in the SAME request ─────────────────────────────
# ⚠ One upload, not four. `?extras=` fans the analysis out server-side over the
# audio that is already there. Our first version called /v1/audio/{profile,
# diarize,sentiment} separately and uploaded the same recording four times.
QUERY=""
[[ "$ANALYSE" == "1" ]] && QUERY="?extras=sentiment,profile,diarize"

RESP=$(curl -sS --max-time 7200 \
    -H "Authorization: Bearer $KEY" \
    -F "file=@$AUDIO" -F "model=$MODEL" -F "language=$LANG_CODE" \
    -D /tmp/uttera-$ID.hdr \
    "$API/v1/audio/transcriptions$QUERY" 2>>"$LOG")
RC=$?

if (( RC != 0 )) || [[ -z "$RESP" ]]; then
    echo "" >"$TEXT"
    log "curl rc=$RC, empty response"
    exit 1
fi

RESP_FILE="/tmp/uttera-$ID.json"
printf '%s' "$RESP" >"$RESP_FILE"
python3 - "$TEXT" "$ANALYSIS" "$RESP_FILE" <<'PY' 2>>"$LOG"
import json, sys
text_path, analysis_path = sys.argv[1], sys.argv[2]
d = json.load(open(sys.argv[3]))
open(text_path, "w").write((d.get("text") or "").strip() + "\n")
# Only the keys that actually came back. A file full of nulls reads like a
# failure when it was simply not asked for.
extra = {k: d[k] for k in ("sentiment", "profile", "diarize") if d.get(k)}
if extra:
    json.dump(extra, open(analysis_path, "w"), ensure_ascii=False, indent=2)
# The fan-out reports what it could not do instead of staying quiet about it.
for e in d.get("errors") or []:
    print("analysis failed: %s (%s)" % (e.get("source"), e.get("status")), file=sys.stderr)
PY

SECS=$(grep -i '^x-audio-duration:' "/tmp/uttera-$ID.hdr" 2>/dev/null | tr -d '\r' | cut -d' ' -f2)
rm -f "/tmp/uttera-$ID.hdr" "$RESP_FILE"
log "done, $(wc -c <"$TEXT") bytes of text, ${SECS:-?} s billed"
exit 0
