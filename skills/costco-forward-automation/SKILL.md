---
name: costco-forward-automation
description: >-
  Manage/inspect the Costco daily sales email automation running in Google Cloud for
  sparklinxgroup. Each day (~9 AM Halifax) a Cloud Scheduler job triggers a Gen2 Cloud
  Function that finds the "Costco Last 7 Days Sales - CANADA BREAD" email from
  noreply@costco.com, forwards it to tlaceycanadabread@hotmail.com, saves the .xlsx
  attachment to a Drive folder "costco", and labels it "costco-forwarded" so it never
  double-sends. Use when the user asks to check/change/redeploy/debug this automation
  (schedule, recipient, folder), or asks "did the Costco email go out". Runs entirely in
  GCP (project sparklinxgroup) — no laptop needed. Managed via gcloud on macOS.
---

# Costco daily forward automation (GCP)

Fully cloud-hosted; the laptop is only used to deploy/manage via `gcloud`.

## Architecture
`Cloud Scheduler (costco-daily-9am, 0 9 * * * America/Halifax)`
→ OIDC POST → `Cloud Function Gen2 "costco-daily"` (region us-central1, entry `costco`)
→ refreshes a user OAuth token (gmail.modify + drive.file) from **Secret Manager**
→ Gmail search → **forward** to `tlaceycanadabread@hotmail.com` → **save .xlsx** to Drive
folder `costco` → add Gmail label `costco-forwarded`.

- Project: `sparklinxgroup` (number 272436447517)
- Runtime + invoker SA: `costco-fn@sparklinxgroup.iam.gserviceaccount.com`
  (roles: secretmanager.secretAccessor on the secret; run.invoker on the function)
- Secret: `costco-oauth-token` (JSON: client_id/secret, refresh_token, token_uri) — mounted as env `TOKEN_JSON`
- Env vars: `FORWARD_TO`, `SUBJECT_HINT`, `DRIVE_FOLDER`, `LABEL_NAME`
- Function URL: `https://costco-daily-cc7zaocrkq-uc.a.run.app`
- Source of truth: `scripts/main.py` (+ `requirements.txt`)

## Common tasks (run with `gcloud config set project sparklinxgroup` first)
- **Run it now (real — forwards to tlacey):** `gcloud scheduler jobs run costco-daily-9am --location us-central1`
- **See logs:** `gcloud functions logs read costco-daily --region us-central1 --gen2 --limit 50`
- **Change recipient/folder/subject:** `gcloud functions deploy costco-daily --region us-central1 --update-env-vars FORWARD_TO=...`
- **Change schedule/time:** `gcloud scheduler jobs update http costco-daily-9am --location us-central1 --schedule "0 9 * * *" --time-zone America/Halifax`
- **Redeploy code:** edit `scripts/main.py`, then
  `gcloud functions deploy costco-daily --gen2 --runtime python312 --region us-central1 --source <dir> --entry-point costco --trigger-http --no-allow-unauthenticated --service-account costco-fn@sparklinxgroup.iam.gserviceaccount.com --set-secrets TOKEN_JSON=costco-oauth-token:latest`
- **Pause / resume:** `gcloud scheduler jobs pause|resume costco-daily-9am --location us-central1`

## Token / auth notes
- The OAuth token is a **user** refresh token (a service account can't read a consumer @gmail.com).
- Re-mint it if revoked/expired: run `scripts/get_combined_token.py` locally (browser consent for
  gmail.modify + drive.file), then push a new secret version:
  `gcloud secrets versions add costco-oauth-token --data-file ~/.gmail-mcp/automation-token.json`.
- Drive scope is `drive.file` (least privilege) — the function only sees the folder/files it creates.

## Gotchas
- First deploy in a fresh project fails until the **compute default SA**
  (`272436447517-compute@developer.gserviceaccount.com`) has `roles/cloudbuild.builds.builder`
  (+ logging.logWriter, artifactregistry.writer, storage.objectAdmin). Already granted.
- Cloud Functions/Run/Scheduler require **billing enabled** (it is).
- The Costco email carries the data as an **.xlsx attachment**; forwarding preserves it and the
  archive saves that xlsx (not a PDF of the HTML).

Related: [[gmail-mcp-setup]] (interactive Gmail via MCP for ad-hoc tasks).
