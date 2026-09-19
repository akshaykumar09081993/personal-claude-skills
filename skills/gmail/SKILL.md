---
name: gmail
description: >-
  Access the user's Gmail (sparklinxgroup@gmail.com) — search, read, send, reply,
  draft, label, archive, mark read/unread, trash, download attachments, and manage
  filters. Use whenever the user asks to check/search/read their email, send or reply
  to a message, draft an email, organize/label/archive mail, find an attachment, or
  set up a Gmail filter. Works through the local `gmail` MCP server
  (@gongrzhe/server-gmail-autoauth-mcp); OAuth is already configured on this Mac.
  Scopes = gmail.modify + gmail.settings.basic (can read/send/modify/label/trash and
  manage filters; cannot permanently delete beyond Trash or change core settings).
---

# Gmail

Read and act on the user's Gmail account **sparklinxgroup@gmail.com** through the
`gmail` MCP server. The tools are exposed with the **`mcp__gmail__`** prefix and are
loaded automatically at session start (the server is registered in `~/.claude.json`,
user scope). If you don't see the tools, the session was started before the server was
added — tell the user to start a new session, or run the repair steps below.

## When to use
- "Check / search / read my email", "any email from X", "what did Y send about Z"
- "Send / reply / forward an email", "draft an email to …"
- "Label / archive / mark read / trash", "download the attachment from …"
- "Set up a filter that …"

## Tools (prefix `mcp__gmail__`)

**Read / search**
- `search_emails` — Gmail query syntax (see below). Returns matching message IDs + snippets.
- `read_email` — full message by ID (headers, body, attachment metadata).
- `list_email_labels` — all labels (system + user).
- `download_attachment` — save an attachment by message ID + attachment ID.

**Compose / send**
- `send_email` — send now. Params: `to` (array), `subject`, `body` (plain text); optional
  `cc`, `bcc`, `htmlBody` (or `mimeType:"text/html"`), `attachments` (file paths),
  and for replies `threadId` + `inReplyTo`/`references`.
- `draft_email` — same params, saves a Draft instead of sending.

**Organize**
- `modify_email` — add/remove labels on one message (e.g. remove `INBOX` to archive,
  remove `UNREAD` to mark read, add a label ID).
- `batch_modify_emails` — same across many message IDs.
- `delete_email` / `batch_delete_emails` — move message(s) to Trash.
- `create_label`, `update_label`, `delete_label`, `get_or_create_label`.

**Filters**
- `list_filters`, `get_filter`, `create_filter`, `create_filter_from_template`, `delete_filter`.

## Gmail search operators (for `search_emails`)
`from:`, `to:`, `cc:`, `subject:`, `label:`, `is:unread`, `is:starred`, `is:important`,
`has:attachment`, `filename:pdf`, `after:2026/01/01`, `before:…`, `newer_than:7d`,
`older_than:1y`, `in:inbox`/`in:anywhere`, `-` to exclude, quotes for phrases.
Examples: `from:bimbo has:attachment newer_than:30d`, `subject:invoice is:unread`.

## Common recipes
- **Triage unread:** `search_emails "is:unread in:inbox newer_than:7d"` → `read_email` each.
- **Archive a message:** `modify_email` with `removeLabelIds:["INBOX"]`.
- **Mark read:** `modify_email` with `removeLabelIds:["UNREAD"]`.
- **Reply in thread:** `read_email` to get `threadId` + Message-ID, then `send_email`
  with `threadId` and `inReplyTo` set, subject prefixed `Re:`.
- **File to a label:** `get_or_create_label` → `modify_email addLabelIds:[<id>]`
  (optionally also remove `INBOX` to archive).

## Safety
- **Always show the drafted content and recipients and get the user's OK before
  `send_email`.** Sending is outward-facing and hard to undo.
- Prefer `draft_email` when the user is still deciding.
- `delete_email` only moves to Trash (recoverable 30 days); still confirm before batch deletes.

## Setup / repair (already done — for reference)
- OAuth client (Desktop, project `sparklinxgroup`): `~/.gmail-mcp/gcp-oauth.keys.json` (chmod 600).
- Stored token after consent: `~/.gmail-mcp/credentials.json` (chmod 600).
- Registered: `claude mcp add --scope user gmail -- npx -y @gongrzhe/server-gmail-autoauth-mcp`.
- Re-authenticate (if the server shows "Needs authentication" or tokens expire/revoke):
  `cd ~/.gmail-mcp && npx -y @gongrzhe/server-gmail-autoauth-mcp auth` → approve in browser.
- Health check: `claude mcp list` (look for `gmail … ✔ Connected`).
- Scopes granted: `gmail.modify` + `gmail.settings.basic`. To send from a different
  address/alias or change settings you'd need to re-auth with broader scopes.

Related: [[accessing-google-drive]] (same account, Drive REST via keychain token).
