#!/bin/bash
# Smoke test for the REST API. Runs the real script.py against stub binaries
# (no iOS device or docker needed). Requires: python3, curl.
# Usage: tests/smoke.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
STUBS="$HERE/stubs"
PORT="${PORT:-5057}"
BASE="http://127.0.0.1:$PORT"
TMP="$(mktemp -d)"
BK="$TMP/backups"

cleanup() { kill "$SERVER_PID" 2>/dev/null; rm -rf "$TMP" "$(dirname "$BK" 2>/dev/null)"; }
trap cleanup EXIT

# /mnt/backups may not exist/writable on the host: point BACKUP_DIR at TMP
export BACKUP_DIR="$BK"
export API_PORT="$PORT"

mkdir -p "$STUBS/bin" "$BK"
for s in usbmuxd idevice_id idevicebackup2; do
  cp "$STUBS/$s" "$STUBS/bin/$s"
  chmod +x "$STUBS/bin/$s"
done
# make idevicebackup2 write into the test dir
sed "s|/mnt/backups|$BK|g" "$STUBS/idevicebackup2" > "$STUBS/bin/idevicebackup2"
chmod +x "$STUBS/bin/idevicebackup2"
PATH="$STUBS/bin:$PATH" python3 "$HERE/../src/script.py" >"$TMP/server.log" 2>&1 &
SERVER_PID=$!

req() { # method url [expected_status]
  local method="$1" url="$2" expected="${3:-200}"
  curl -s -o "$TMP/resp" -w '%{http_code}' -X "$method" "$BASE$url"
}

pass=0; fail=0
check() { # description actual expected
  if [ "$2" = "$3" ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1 (got $2, want $3)"; fi
}

# wait for server
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/" 2>/dev/null) && [ "$code" = "200" ] && break
  sleep 0.3
done

check "index"            "$(req GET /)"                       200
check "no backup w/o usbmuxd" "$(req GET "/backup")"          400
check "start wired"      "$(req GET "/start")"                200
check "start again"      "$(req GET "/start")"                409
check "autodetect uid"   "$(req GET "/backup")"               200
check "existing"         "$(req GET "/backup?uid=x")"         409
# wait for stub backup to finish
sleep 4
st=$(req GET /backup/status)
check "backup finished"  "$st" 200
check "exit code 0"     "$(python3 -c "import json;print(json.load(open('$TMP/resp'))['exit_code'])")" 0
check "usbmuxd kept (wired)" "$(req GET /stop)" 200

check "start wireless"    "$(req GET "/start?ip=1.2.3.4&id=000000stub-device-uid")" 200
check "wireless backup"   "$(req GET "/backup")" 200
sleep 4
code=$(req GET /backup/status)
check "wireless done"    "$code" 200
check "auto-stopped usbmuxd" "$(req GET /status)" 200
check "usbmuxd not running"  "$(python3 -c "import json;print(json.load(open('$TMP/resp'))['usbmuxd']['running'])")" False
check "list backups"     "$(req GET /backups)" 200
check "delete backup"    "$(req GET "/delete_backup?name=000000stub-device-uid")" 200
check "delete missing"   "$(req GET "/delete_backup?name=nope")" 404
check "delete traversal" "$(req GET "/delete_backup?name=..%2F..%2Fetc")" 400
check "bad dir param"    "$(req GET "/backup?uid=x&dir=/etc/scratch")" 400
check "404"              "$(req GET /nope)" 404

echo
echo "pass=$pass fail=$fail"
[ "$fail" = 0 ]
