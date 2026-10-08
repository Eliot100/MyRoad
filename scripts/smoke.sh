#!/usr/bin/env bash
# Post-deploy smoke test. Read-only: no sign-in, no publish, no feedback.
# Usage: scripts/smoke.sh https://staging.example.com
set -euo pipefail
BASE="${1:?usage: smoke.sh BASE_URL}"
BASE="${BASE%/}"
HEALTH="$(mktemp)"
trap 'rm -f "$HEALTH"' EXIT

echo "Waiting for $BASE/health"
for i in $(seq 1 30); do
  if curl -fsS "$BASE/health" -o "$HEALTH" 2>/dev/null; then break; fi
  [ "$i" = 30 ] && { echo "health never came up"; exit 1; }
  sleep 2
done

HEALTH="$HEALTH" python3 - <<'PY'
import json
h = json.load(open(__import__("os").environ["HEALTH"]))
assert h.get("status") == "ok", h
assert int(h.get("contentPaths") or 0) >= 1, f"no content loaded: {h}"
print(f"health ok, {h['contentPaths']} content paths")
PY

for page in / /login; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$page")
  case "$code" in
    200|302|303|307) echo "$page -> $code" ;;
    *) echo "$page returned $code"; exit 1 ;;
  esac
done
echo "Smoke test passed."
