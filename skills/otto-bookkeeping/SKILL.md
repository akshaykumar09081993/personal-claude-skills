---
name: otto-bookkeeping
description: >-
  Turn downloaded Bimbo Canada OTTO "Distributor Weekly Statement" PDFs into a bookkeeping ledger — parse the
  weekly money figures (Product Total, Total Credit, Distributor Fees, Deposit, Balance Due) into a CSV plus a
  printed monthly summary, and reconcile the payments received in a given month. Use whenever the user asks to
  do the bookkeeping / reconcile / total up / build a ledger or spreadsheet from their OTTO statements, or
  "how much did we net/pay in <month>". Reads the PDFs saved by `otto-download-statements` under
  ~/Documents/bookeeping/<year>/<Month>/Checking. macOS; requires Python + pdfplumber.
---

# OTTO — bookkeeping from weekly statements

**Step 2** of the statements flow. After `otto-download-statements` saves the weekly PDFs, this parses them
into a ledger and a summary, so the OTTO deposits can be reconciled against the bank ("Checking") account.

## Prerequisite
```bash
python3 -m pip install pdfplumber --break-system-packages
```

## Quick start
```bash
# Build a ledger for the June-2026 payment window and print a summary
python3 scripts/parse-statements.py \
  --dir ~/Documents/bookeeping/2026/June/Checking --paid-month 2026-06

# Custom CSV location; every statement in a folder (no month filter)
python3 scripts/parse-statements.py --dir ~/Documents/bookeeping/2025/December \
  --csv ~/Documents/bookeeping/2025/December/ledger-dec.csv
```

## What it does
- Recursively finds every `Distributor Weekly Statement ….pdf` under `--dir`.
- Extracts per statement: `week_from`, `week_to`, `route`, `statement_no`, and the **Current Week** values for
  `product_total`, `total_credit`, `distributor_fees` (+ tax), `fixed_distributor_fee` (+ tax), `deposit`,
  `total_manual_adj`, **`balance_due_week`** (net settled that week), and `balance_due_ytd`.
- Writes a **CSV ledger** (default `<dir>/statements-ledger.csv`) and prints a week-by-week table + totals.

Parsing rule: on each money line the **last** number is YTD and the **second-to-last** is the Current Week
value — this holds across all rows (verified against real route-1702 statements).

## Payment-month reconciliation
`--paid-month YYYY-MM` keeps only statements whose **week-ending** date falls in
`[previous-month-start .. that-month end]` — the "paid this month" window (Bimbo settles weekly on a lag;
the last statement of the previous month is usually paid early the next). Omit it to include everything found.
Note: each week's **Deposit** equals the prior week's Balance Due (the deposit clears the previous balance) —
useful as a reconciliation cross-check against the bank statement.

## Filtering
`--route 1702` (default; `all` for every route) · `--csv PATH` to place the ledger where you want (e.g. in
the month folder `~/Documents/bookeeping/2026/June/`).

## Optional: push to Google Sheets / Drive
The CSV can be uploaded with the `accessing-google-drive` skill if the user wants it in Sheets rather than a
local file — ask first.

## Related
`otto-download-statements` (step 1 — fetch the PDFs) · `orderonotto-ordering` (OTTO login/nav).
