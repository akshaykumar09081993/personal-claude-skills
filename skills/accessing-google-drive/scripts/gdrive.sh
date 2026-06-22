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
#   ./gdrive.sh export "<fileId>" "<dest.pdf>" Export a Google Doc/Sheet/Slides (PDF default)
#   ./gdrive.sh token                    Print the current access token (debug)
#
# Listing commands (list/search/folder/find-folder) print a clean table by default.
# Add --json anywhere on the line to get raw JSON instead (handy for scripting / file IDs).
#
# If you get "token expired" or HTTP 401, the user should run in Claude Code:
#   /mcp  ->  gdrive  ->  Reauthenticate   (usually instant; refresh token persists)
# then retry. No browser dance is normally needed.

set -euo pipefail

KEYCHAIN_SERVICE="Claude Code-credentials"
API="https://www.googleapis.com/drive/v3"

# --- parse a global --json flag from anywhere in the args ---
JSON=0
ARGS=()
for a in "$@"; do
  if [ "$a" = "--json" ]; then JSON=1; else ARGS+=("$a"); fi
done
set -- "${ARGS[@]:-}"

get_token() {
  security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null | python3 -c '
import sys, json, time
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit("ERR: could not parse Claude Code credentials from keychain")
tok = exp = None
for k, v in d.get("mcpOAuth", {}).items():
    if k.startswith("gdrive"):
        tok = v.get("accessToken"); exp = v.get("expiresAt"); break
if not tok:
    sys.exit("ERR: no gdrive token. Connect it: Claude Code -> /mcp -> gdrive -> Authenticate")
if exp and (exp/1000.0) < time.time():
    sys.stderr.write("WARN: token appears expired; if calls 401, run /mcp -> gdrive -> Reauthenticate\n")
print(tok)
'
}

# Pretty-print a Drive files list (JSON on stdin) as a table, unless --json was passed.
emit() {
  if [ "$JSON" = "1" ]; then
    python3 -m json.tool
  else
    python3 -c '
import sys, json
try:
    files = json.load(sys.stdin).get("files", [])
except Exception:
    sys.exit("ERR: unexpected response (token may be expired -> /mcp -> gdrive -> Reauthenticate)")
K = {
  "application/vnd.google-apps.folder":"Folder",
  "application/vnd.google-apps.document":"Google Doc",
  "application/vnd.google-apps.spreadsheet":"Google Sheet",
  "application/vnd.google-apps.presentation":"Google Slides",
  "application/pdf":"PDF","application/zip":"ZIP",
  "image/jpeg":"JPEG","image/png":"PNG","image/heif":"HEIC",
  "text/csv":"CSV","application/octet-stream":"binary",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":"Word .docx",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":"Excel .xlsx",
}
if not files:
    print("(no files)"); sys.exit()
print("TOTAL: %d\n" % len(files))
for i, f in enumerate(files, 1):
    kind = K.get(f.get("mimeType",""), f.get("mimeType",""))
    mod  = f.get("modifiedTime","")[:10]
    fid  = f.get("id","")
    print("%3d. %-55s | %-13s | %s | %s" % (i, f.get("name","")[:55], kind, mod, fid))
'
  fi
}

urlq() { python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$1"; }

TOKEN="$(get_token)"
auth=(-H "Authorization: Bearer ${TOKEN}")

cmd="${1:-list}"; shift || true

case "$cmd" in
  token) echo "$TOKEN" ;;

  list)
    n="${1:-100}"
    curl -s "${auth[@]}" \
      "${API}/files?pageSize=${n}&fields=files(id,name,mimeType,modifiedTime)&orderBy=folder,modifiedTime%20desc" \
      | emit ;;

  search)
    q="${1:?need search text}"
    enc=$(urlq "name contains '${q//\'/\\\'}'")
    curl -s "${auth[@]}" \
      "${API}/files?q=${enc}&pageSize=100&fields=files(id,name,mimeType,modifiedTime)" | emit ;;

  folder)
    fid="${1:?need folderId}"; n="${2:-200}"
    enc=$(urlq "'${fid}' in parents")
    curl -s "${auth[@]}" \
      "${API}/files?q=${enc}&pageSize=${n}&fields=files(id,name,mimeType,modifiedTime)&orderBy=folder,name" | emit ;;

  find-folder)
    name="${1:?need folder name}"
    enc=$(urlq "mimeType='application/vnd.google-apps.folder' and name contains '${name//\'/\\\'}'")
    curl -s "${auth[@]}" \
      "${API}/files?q=${enc}&pageSize=50&fields=files(id,name,mimeType,modifiedTime)" | emit ;;

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
    curl -sL "${auth[@]}" "${API}/files/${fid}/export?mimeType=$(urlq "$mt")" -o "$dest"
    echo "Exported -> $dest ($mt)" ;;

  *)
    echo "Unknown command: $cmd" >&2
    grep '^#' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 1 ;;
esac
