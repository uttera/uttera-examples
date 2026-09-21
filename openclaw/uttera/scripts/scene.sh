#!/usr/bin/env bash
# Build a whole sound scene: plan it, then generate and mix it.
# Usage: scene.sh "a long description" [seconds] [out.wav]
#
# ⚠ Two steps, and that is the point: the plan comes back as a list of events
# placed in time, and you can EDIT it before spending anything on audio. This
# script runs both steps straight through; to correct the plan, call
# /v1/audio/sfx/plan yourself, edit the JSON, and post it to /v1/audio/sfx/scene.
set -euo pipefail
: "${UTTERA_API_KEY:?export your key: export UTTERA_API_KEY=sk-echo-...}"
API="${UTTERA_API:-https://api.uttera.ai}"
PROMPT="${1:?usage: scene.sh \"description\" [seconds] [out.wav]}"
SECS="${2:-20}"; OUT="${3:-scene.wav}"
PLAN=$(mktemp -t uttera.XXXXXX); RESP=$(mktemp -t uttera.XXXXXX)
trap 'rm -f "$PLAN" "$RESP"' EXIT

# Step 1 — the plan. No audio is generated here, so it costs very little.
python3 -c 'import json,sys; print(json.dumps({"prompt":sys.argv[1],"seconds":float(sys.argv[2])}))' \
        "$PROMPT" "$SECS" > "$PLAN"
curl -sS --max-time 300 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @"$PLAN" \
     -o "$RESP" "$API/v1/audio/sfx/plan"
python3 - "$RESP" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if "events" not in d:
    print(json.dumps(d)[:400], file=sys.stderr); sys.exit(1)
for e in d["events"]:
    print("  %5.1fs  %4.1fs  %s" % (e["start"], e["duration"], e["prompt"]), file=sys.stderr)
PY

# Step 2 — generate every event and mix them. This is where it costs.
curl -sS --max-time 900 -H "Authorization: Bearer $UTTERA_API_KEY" \
     -H "Content-Type: application/json" --data-binary @"$RESP" \
     -o "$PLAN" "$API/v1/audio/sfx/scene"
python3 - "$PLAN" "$OUT" <<'PY'
import base64, json, sys
d = json.load(open(sys.argv[1]))
if "mix" not in d:
    print(json.dumps(d)[:400], file=sys.stderr); sys.exit(1)
open(sys.argv[2], "wb").write(base64.b64decode(d["mix"]))
print("%s  (%d separate pieces also returned)" % (sys.argv[2], len(d.get("clips", []))))
PY
