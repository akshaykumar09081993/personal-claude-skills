---
name: otto-download-statements
description: >-
  Log into the Bimbo Canada "OTTO" portal (orderonotto.ca) and download the weekly "Distributor Weekly
  Statement" PDFs, saving them into the user's bookkeeping folder (~/Documents/bookeeping/<year>/<Month>/Checking).
  Use whenever the user asks to download/pull/grab OTTO statements, get the weekly distributor statements,
  or collect the statements for the payments received in a given month (Bimbo settles weekly on a lag — the
  statement generated last in the previous month is usually the one paid early the next month). OTTO is an
  Angular Material SPA that MUST be driven with a real headless browser (Playwright/Chromium), NOT raw HTTP.
  macOS. Login/nav mechanics are shared with `orderonotto-ordering`. Follow with `otto-bookkeeping` to build
  the ledger.
---

# OTTO — download weekly Distributor Statements

Downloads the **STATEMENTS** (`orderonotto.ca/statements`) — the weekly *Distributor Weekly Statement* PDFs
(OTTO retains ~52 weeks) — and files them into the user's bookkeeping tree so they can be reconciled.

This is **step 1** of a two-step flow:
1. **`otto-download-statements`** (this skill) → fetch the PDFs into `~/Documents/bookeeping/<year>/<Month>/Checking`.
2. **`otto-bookkeeping`** → parse those PDFs into a CSV ledger + monthly summary.

## Prerequisites
- **Playwright + Chromium** (OTTO is a JS-rendered SPA; curl/HTTP returns an empty shell):
  ```bash
  npm i playwright && npx playwright install chromium
  ```
- **Credentials** — supply at runtime, NEVER commit them (this repo is public):
  - env: `OTTO_USERNAME`, `OTTO_PASSWORD` (optionally `OTTO_URL`)
  - or a local, git-ignored file `~/.config/otto/credentials.json` → `{"username":"…","password":"…"}`
- The user's route is **1702**.

## Quick start
```bash
# All statements whose payment landed in June 2026 (auto out-dir: ~/Documents/bookeeping/2026/June/Checking)
OTTO_USERNAME='...' OTTO_PASSWORD='...' \
  node scripts/otto-statements.js --paid-month 2026-06

# Explicit week-ending window + explicit out dir
node scripts/otto-statements.js --from 2026-05-01 --to 2026-06-30 \
  --out ~/Documents/bookeeping/2026/June/Checking

# Everything OTTO retains
node scripts/otto-statements.js --all --out /tmp/otto-statements
```
Prints a JSON manifest (`downloaded`, `skipped`, `errors`) and saves PDFs named exactly like the OTTO
originals: `Distributor Weekly Statement Route 1702 From YYYY-MM-DD To YYYY-MM-DD.pdf`.

## "Payments received in <month>" selection — the payment rule
Each statement covers a week that **ends Saturday**, is **generated Sunday**, and is **paid the next Friday**
(= week-ending Saturday **+ 6 days**). So `--paid-month YYYY-MM` selects exactly the weeks whose Friday
payment lands in that month. For **June 2026** that is the four week-endings **2026-05-30 → 06-06 → 06-13 →
06-20** (05-30 pays Jun 5; 06-20 pays Jun 26). Note **06-27 pays Jul 3 → belongs to July**, and the last May
week (05-30) correctly counts as June because it pays Jun 5 ("the last one from the previous month"). Use
`--from/--to` (on the week-ending date) for an exact window, or `--all` for everything OTTO retains.

## Where files go
Matches the user's existing layout: `~/Documents/bookeeping/<year>/<Month>/Checking/` (e.g.
`~/Documents/bookeeping/2026/June/Checking/`). "Checking" is the bank-account bucket these OTTO deposits
reconcile against. Override with `--out DIR`.

## How the statements page works (verified live)
- Login (shared with `orderonotto-ordering`): `goto` `login.php` → fill `#mat-input-0`/`#mat-input-1` →
  click `LOG IN`; SPA sometimes paints blank → wait-loop, reload once.
- `/statements` has, on the right, **Route #** (`mat-select` nth 0) and **Week Ending** (`mat-select` nth 1)
  dropdowns + a **View Reports** button. The Week Ending list is a rolling **~52 weeks**.
- Select a week → **View Reports** → the "Reports Available" panel lists 3 links per week: **Distributor
  Weekly Statement**, Distributor_Revenue_Route, Distributor_Route_Activity. We download **only the
  "Distributor Weekly Statement"**. Each link is a direct `lambda.ribon.ca/.../get-file?token=<JWT>` URL;
  the script fetches it through the authenticated context (`ctx.request.get`).
- **Reload `/statements` before EACH week.** Switching weeks without a reload leaves stale links in the DOM
  and can fetch the wrong file. The script reloads per week and also decodes the token's `fileKey` to confirm
  the served path matches the selected week before saving.
- Debug artifacts always written to the out dir: `_statements-page.png`, `_dom-dump.json` (use if selectors
  ever change / nothing downloads).

## Internal-date quirk (some OTTO PDFs print the prior-year date)
For some week slots the served PDF prints the *previous year* in its `FOR WEEK` line and carries an
out-of-sequence statement number (seen June 2026: weeks 06-06 & 06-13 show 2025 / #0006-#0007). Per the user
these are still the **correct statements for that week** — OTTO's **filename/fileKey week is authoritative**,
so the download keeps them. The `otto-bookkeeping` parser surfaces the discrepancy as a note (and via the
`content_week_to` column); use its `--strict` flag only if you want to drop such files.

## Statement PDF anatomy (for reference / downstream parsing)
Header: `ROUTE ID: 1702`, `STATEMENT NUMBER: WST…`, `FOR WEEK: YYYY-MM-DD - YYYY-MM-DD`. Money table has a
7-day breakdown then a **Current Week** column then **YTD Total**. Key weekly rows: `Product Total`,
`Total Credit`, `Distributor Fees` (+ GST/HST), `Fixed Distributor Fee`, `Deposit`, `Total Manual Adjustment`,
and **`Balance Due`** (the net settled for the week). See `otto-bookkeeping` for the parser.

## Related
`orderonotto-ordering` (login/nav + REPORTING/STATEMENTS overview) · `otto-bookkeeping` (parse → ledger).
