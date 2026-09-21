#!/usr/bin/env bash
# Check whether a signed Uttera report is genuine and unmodified.
# Usage: verify.sh report.json
set -euo pipefail
API="${UTTERA_API:-https://api.uttera.ai}"
F="${1:?usage: verify.sh report.json}"
[ -s "$F" ] || { echo "file is missing or empty: $F" >&2; exit 1; }
# ⚠ No API key needed, on purpose: verifying a signature is a public-key
# operation. The day you need an account to check a signature, the signature
# has stopped being useful for what it was made for.
curl -sS --max-time 120 -H "Content-Type: application/json" \
     --data-binary @"$F" "$API/v1/reports/verify"
