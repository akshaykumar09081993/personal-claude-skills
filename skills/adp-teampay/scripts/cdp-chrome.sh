#!/bin/bash
# Launch a CDP-debuggable Chrome using a COPY of the user's real logged-in profile.
# Chrome refuses --remote-debugging-port on the default user-data-dir, so we copy the profile
# to /tmp (cookies come with it, so the ADP session is preserved) and launch from there.
# Usage: cdp-chrome.sh "<Profile Dir>"   e.g. "Profile 1"   (default: "Default")
set -e
PROFILE="${1:-Default}"
SRC="$HOME/Library/Application Support/Google/Chrome"
DST="/tmp/adp-chrome-profile"
PORT="${CDP_PORT:-9222}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT already in use — is a CDP Chrome already running?"; exit 1
fi

rm -rf "$DST"; mkdir -p "$DST"
cp "$SRC/Local State" "$DST/Local State" 2>/dev/null || true
rsync -a --exclude 'Cache' --exclude 'Code Cache' --exclude 'GPUCache' \
      --exclude 'Service Worker' --exclude 'Application Cache' \
      "$SRC/$PROFILE/" "$DST/$PROFILE/"

"$CHROME" --user-data-dir="$DST" --profile-directory="$PROFILE" \
  --remote-debugging-port="$PORT" --no-first-run --no-default-browser-check \
  "https://teampay.adp.com/Payroll/Admin/Main/Default.aspx" >/tmp/chrome-cdp.log 2>&1 &

for i in $(seq 1 15); do
  if curl -s "http://localhost:$PORT/json/version" >/dev/null 2>&1; then
    echo "CDP ready on :$PORT (profile '$PROFILE')"; exit 0
  fi
  sleep 1
done
echo "CDP did not come up; see /tmp/chrome-cdp.log"; tail -5 /tmp/chrome-cdp.log; exit 1
