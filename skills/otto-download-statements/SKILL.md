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

## "Payments received in <month>" selection
Bimbo pays weekly on a lag. Per the user's rule of thumb, *the statement generated last in the previous
month is the one paid early the next month*. So `--paid-month YYYY-MM` downloads every weekly statement whose
**week-ending** date falls in **[previous-month-start .. paid-month end]**. Widen with `--lag-weeks N` if a
payment covers older weeks. Use `--from/--to` for an exact window, or `--all` to grab everything and let the
bookkeeping step bucket by date.

## Where files go
Matches the user's existing layout: `~/Documents/bookeeping/<year>/<Month>/Checking/` (e.g.
`~/Documents/bookeeping/2026/June/Checking/`). "Checking" is the bank-account bucket these OTTO deposits
reconcile against. Override with `--out DIR`.

## Login flow (shared with `orderonotto-ordering`)
1. `goto` `https://orderonotto.ca/login.php` (`networkidle`).
2. Fill `#mat-input-0` = email, `#mat-input-1` = password; click `button:has-text("LOG IN")`.
3. SPA sometimes paints blank → wait-loop for known text, reload once as fallback.
4. `goto` `https://orderonotto.ca/statements`; wait for `Statement`/`Weekly`/`Distributor`.

## ⚠️ First-run verification (statements DOM not yet confirmed live)
The exact `/statements` row/link/button selectors were **not** verified against a live login when authored.
The script tries multiple strategies (authenticated fetch of `<a>.pdf` hrefs; click → browser `download`
event) and **always** writes two debug artifacts into the out dir:
- `_statements-page.png` — full-page screenshot
- `_dom-dump.json` — candidate rows/links/buttons (anything mentioning statement/distributor/weekly/a date)

If `downloaded` is empty and `candidatesFound` is 0, open those two files, identify the real download control,
and refine the selector block in `scripts/otto-statements.js` (search for "Strategy A" / "Strategy B"). Then
update this note.

## Statement PDF anatomy (for reference / downstream parsing)
Header: `ROUTE ID: 1702`, `STATEMENT NUMBER: WST…`, `FOR WEEK: YYYY-MM-DD - YYYY-MM-DD`. Money table has a
7-day breakdown then a **Current Week** column then **YTD Total**. Key weekly rows: `Product Total`,
`Total Credit`, `Distributor Fees` (+ GST/HST), `Fixed Distributor Fee`, `Deposit`, `Total Manual Adjustment`,
and **`Balance Due`** (the net settled for the week). See `otto-bookkeeping` for the parser.

## Related
`orderonotto-ordering` (login/nav + REPORTING/STATEMENTS overview) · `otto-bookkeeping` (parse → ledger).
