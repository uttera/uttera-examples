#!/usr/bin/env bash
# Go through a folder of recordings and transcribe the ones that are missing it.
#
# This is the piece that turns "we have a PBX recording calls" into "we have
# every call transcribed", without touching the dialplan at all. Run it from
# cron every few minutes.
#
#   FILTER='-mtime -7' WORKERS=5 ./bulk-reprocess.sh
set -u

DIR="${RECORDINGS_DIR:-/var/spool/asterisk/monitor}"
APP="${TRANSCRIBER:-$(dirname "$0")/transcribe-recording.sh}"
WORKERS="${WORKERS:-5}"

# ⚠ THE DEFAULT IS THE LAST SEVEN DAYS, AND IT IS NOT AN ARBITRARY NUMBER.
#
# The first version had no filter and walked the whole archive on every pass.
# The day we pointed it at a real backlog it queued years of calls at once and
# took the analysis service down with it. A batch job whose size depends on how
# long the system has existed will eventually find a size nobody tested.
#
# Widen it deliberately and once -FILTER='' to process everything- rather than
# leaving it open by default.
FILTER="${FILTER--mtime -7}"

LOCK="${LOCKFILE:-/tmp/uttera-bulk.lock}"
exec 200>"$LOCK" || { echo "cannot open $LOCK" >&2; exit 1; }
# Overlapping runs would upload the same recordings twice and pay twice.
if ! flock -n 200; then
    echo "$(date '+%F %T') already running, nothing to do"
    exit 0
fi

PENDING=$(mktemp); trap 'rm -f "$PENDING"' EXIT

# shellcheck disable=SC2086
find "$DIR" -maxdepth 1 -name '*.wav' -size +1k $FILTER -printf '%f\n' 2>/dev/null \
  | sed 's/\.wav$//' \
  | while read -r ID; do
        TXT="$DIR/$ID.txt"
        # Pending = no transcript, or one left half-written by an interrupted run.
        if [[ ! -s "$TXT" ]] || head -1 "$TXT" 2>/dev/null | grep -q '^\[transcribing'; then
            printf '%s\n' "$ID"
        fi
    done > "$PENDING"

N=$(wc -l < "$PENDING")
echo "$(date '+%F %T') pending=$N workers=$WORKERS filter='$FILTER'"
(( N == 0 )) && exit 0

# Parallel, but bounded. Every stage of every request takes a concurrency slot
# on your plan, so more workers than your plan allows just earns you 429s.
xargs -a "$PENDING" -P "$WORKERS" -I {} bash -c '
    ID="$1"; APP="$2"; START=$(date +%s)
    if "$APP" "$ID" >/dev/null 2>&1; then
        printf "[ok   %3ds] %s\n" "$(( $(date +%s) - START ))" "$ID"
    else
        printf "[FAIL %3ds] %s\n" "$(( $(date +%s) - START ))" "$ID"
    fi
' _ {} "$APP"
