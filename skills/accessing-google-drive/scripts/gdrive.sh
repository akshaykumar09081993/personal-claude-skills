#!/usr/bin/env bash
# gdrive.sh — access the user's Google Drive WITHOUT the (broken) drivemcp MCP server.
#
# Reads the OAuth access token that Claude Code already stored in the macOS keychain
# (from authenticating the "gdrive" MCP server) and calls the regular Google Drive
# REST API v3 directly. The token carries full Drive scopes.
#
# Usage:
#   ./gdrive.sh list [N]                 List up to N recent items (default 100)
#   ./gdrive.sh search "<text>"          Search files whose name contains <text>
#   ./gdrive.sh folder "<folderId>" [N]  List contents of a folder by ID
#   ./gdrive.sh find-folder "<name>"     Find a folder's ID by name
#   ./gdrive.sh meta "<fileId>"          Show metadata for one file
#   ./gdrive.sh download "<fileId>" "<dest>"   Download a binary file
#   ./gdrive.sh export "<fileId>" "<dest.pdf>" Export a Google Doc/Sheet/Slides (as PDF by default)
#   ./gdrive.sh token                    Print the current access token (debug)
#
# If you get "token expired" or HTTP 401, the user should run in Claude Code:
#   /mcp  ->  gdrive  ->  Reauthenticate   (usually instant; refresh token persists)
# then retry. No browser dance is normally needed.

set -euo pipefail

KEYCHAIN_SERVICE="Claude Code-credentials"
API="https://www.googleapis.com/drive/v3"

get_token() {
  security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null | python3 -c '
import sys, json, time
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit("ERR: could not parse Claude Code credentials from keychain")
tok = None
exp = None
for k, v in d.get("mcpOAuth", {}).items():
    if k.startswith("gdrive"):
        tok = v.get("accessToken")
        exp = v.get("expiresAt")
        break
if not tok:
    sys.exit("ERR: no gdrive token found. Connect it: Claude Code -> /mcp -> gdrive -> Authenticate")
if exp and (exp/1000.0) < time.time():
    sys.stderr.write("WARN: token appears expired; if calls 401, run /mcp -> gdrive -> Reauthenticate\n")
print(tok)
'
}

TOKEN="$(get_token)"
auth=(-H "Authorization: Bearer ${TOKEN}")

cmd="${1:-list}"; shift || true

case "$cmd" in
  token)
    echo "$TOKEN" ;;

  list)
    n="${1:-100}"
    curl -s "${auth[@]}" \
      "${API}/files?pageSize=${n}&fields=files(id,name,mimeType,modifiedTime)&orderBy=folder,modifiedTime%20desc" \
      | python3 -m json.tool ;;

  search)
    q="${1:?need search text}"
    # URL-encode the q parameter
    enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(\"name contains '\"+sys.argv[1].replace(chr(39),chr(92)+chr(39))+\"'\"))" "$q")
    curl -s "${auth[@]}" \
      "${API}/files?q=${enc}&pageSize=100&fields=files(id,name,mimeType,modifiedTime)" \
      | python3 -m json.tool ;;

  folder)
    fid="${1:?need folderId}"; n="${2:-200}"
    enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(\"'\"+sys.argv[1]+\"' in parents\"))" "$fid")
    curl -s "${auth[@]}" \
      "${API}/files?q=${enc}&pageSize=${n}&fields=files(id,name,mimeType,modifiedTime)&orderBy=folder,name" \
      | python3 -m json.tool ;;

  find-folder)
    name="${1:?need folder name}"
    enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(\"mimeType='application/vnd.google-apps.folder' and name contains '\"+sys.argv[1].replace(chr(39),chr(92)+chr(39))+\"'\"))" "$name")
    curl -s "${auth[@]}" \
      "${API}/files?q=${enc}&pageSize=50&fields=files(id,name,modifiedTime)" \
      | python3 -m json.tool ;;

  meta)
    fid="${1:?need fileId}"
    curl -s "${auth[@]}" \
      "${API}/files/${fid}?fields=id,name,mimeType,size,modifiedTime,parents,owners(emailAddress)" \
      | python3 -m json.tool ;;

  download)
    fid="${1:?need fileId}"; dest="${2:?need dest path}"
    curl -sL "${auth[@]}" "${API}/files/${fid}?alt=media" -o "$dest"
    echo "Saved -> $dest" ;;

  export)
    fid="${1:?need fileId}"; dest="${2:?need dest path}"; mt="${3:-application/pdf}"
    enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$mt")
    curl -sL "${auth[@]}" "${API}/files/${fid}/export?mimeType=${enc}" -o "$dest"
    echo "Exported -> $dest ($mt)" ;;

  *)
    echo "Unknown command: $cmd" >&2
    grep '^#' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 1 ;;
esac
