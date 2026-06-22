---
name: accessing-google-drive
description: >-
  Access the user's Google Drive (sparklinxgroup@gmail.com) — list, search,
  browse folders, read, and download files. Use whenever the user asks to see,
  find, list, open, or download their Google Drive / Drive files. IMPORTANT: the
  Google "drivemcp" MCP server is broken (returns 403 PERMISSION_DENIED even when
  fully configured); this skill bypasses it by calling the regular Google Drive
  REST API with the OAuth token Claude Code already stored in the macOS keychain.
---

# Accessing Google Drive

## Why this skill exists

The user connected Google's `drivemcp.googleapis.com` MCP server in Claude Code.
Authentication succeeds, but **every Drive call through that MCP returns
`403 PERMISSION_DENIED` ("The caller does not have permission")** — even with the
Drive MCP API + Google Drive API enabled, all Drive scopes registered on the OAuth
consent screen, and the account added as a test user. The `drivemcp` preview API
rejects Testing-mode / unverified-app tokens at its own gateway, which is not
fixable through normal Google Cloud configuration.

**The fix:** ignore the MCP tools entirely. Claude Code already stored a valid
Google OAuth access token (with full Drive scopes) in the macOS keychain when the
MCP server was authenticated. Use that token to call the standard **Google Drive
REST API v3** directly. This works reliably.

## Quick start

A helper script is bundled. From this skill's directory:

```bash
chmod +x scripts/gdrive.sh   # first time only

scripts/gdrive.sh list 50                 # 50 most-recent items
scripts/gdrive.sh search "invoice"        # files whose name contains "invoice"
scripts/gdrive.sh find-folder "HST"       # get a folder's ID by name
scripts/gdrive.sh folder "<folderId>"     # list a folder's contents
scripts/gdrive.sh meta "<fileId>"         # metadata for one file
scripts/gdrive.sh download "<fileId>" out.pdf       # download a binary file
scripts/gdrive.sh export "<fileId>" out.pdf         # export a Google Doc/Sheet as PDF
```

## How it works (do this manually if the script is unavailable)

1. **Read the token from the keychain:**

   ```bash
   security find-generic-password -s "Claude Code-credentials" -w \
   | python3 -c 'import sys,json; d=json.load(sys.stdin); print(next(v["accessToken"] for k,v in d["mcpOAuth"].items() if k.startswith("gdrive")))'
   ```

   The keychain JSON has `mcpOAuth["gdrive|<id>"].accessToken` — a `ya29.…` Google
   token — plus `expiresAt` (ms) and `scope` (includes `.../auth/drive`).

2. **Call the Drive API** with `Authorization: Bearer <token>`:

   ```bash
   TOKEN=...   # from step 1
   curl -s -H "Authorization: Bearer $TOKEN" \
     "https://www.googleapis.com/drive/v3/files?pageSize=200&fields=files(id,name,mimeType,modifiedTime)&orderBy=folder,modifiedTime desc"
   ```

   Useful endpoints / `q` queries:
   - List: `/files?pageSize=N&fields=files(id,name,mimeType,modifiedTime)`
   - Search by name: `q=name contains 'TEXT'`
   - Folder contents: `q='<folderId>' in parents`
   - Only folders: `q=mimeType='application/vnd.google-apps.folder'`
   - By type: `q=mimeType='application/pdf'`
   - Download binary: `/files/<id>?alt=media`
   - Export Google-native file: `/files/<id>/export?mimeType=application/pdf`
   - Paginate with `nextPageToken` → add `&pageToken=<token>`

## Authentication / token refresh

- The **refresh token persists in the keychain across sessions**, so you normally do
  **not** need to re-authenticate. Just read the access token and go.
- If a call returns **HTTP 401** or the token is expired, ask the user to run in
  Claude Code: **`/mcp` → `gdrive` → Reauthenticate** (leave the dialog open so the
  `localhost:8585` listener completes it). Because the refresh token is still valid,
  this is usually instant and needs no browser. Then re-read the token and retry.
- The OAuth client is `272436447517-…` in Google Cloud project **sparklinxgroup**,
  callback port **8585**. Both the Drive MCP API and Google Drive API are enabled
  there; the consent screen is in Testing mode with `sparklinxgroup@gmail.com` as a
  test user. (Background only — you should not need to touch any of this.)

## Notes

- macOS only (uses the `security` keychain command).
- Do not print the access token into shared output unnecessarily — it grants Drive access.
- If Google ever fixes / GAs the `drivemcp` API, the MCP tools
  (`mcp__gdrive__list_recent_files`, `mcp__gdrive__search_files`, etc.) may start
  working; this REST workaround will keep working regardless.
