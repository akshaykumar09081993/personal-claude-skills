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

## Payment-month reconciliation (the payment rule)
A statement's week **ends Saturday**, is **generated Sunday**, and is **paid the next Friday** (= week-ending
Saturday **+ 6 days**). `--paid-month YYYY-MM` keeps only statements whose Friday payment lands in that month.
The ledger shows a `Paid (Fri)` column and a `payment_date` CSV field. Omit `--paid-month` to include all.
Cross-check: each week's **Deposit** equals the prior week's Balance Due (the deposit clears the previous
balance) — handy for tying out against the bank ("Checking") statement.

## ⚠️ Auto-detects OTTO's mislabeled (prior-year) files
OTTO occasionally serves a PDF whose **content is a different (prior-year) week** than its filename claims
(seen June 2026). The parser compares the filename week to the PDF's `FOR WEEK` line; on a mismatch it prints
a loud warning (with statement number + the real content week) and **excludes that file from the ledger** so
your totals stay clean. Follow up with Bimbo Route Accounting to get the correct statement, then re-run.

## Filtering
`--route 1702` (default; `all` for every route) · `--csv PATH` to place the ledger where you want (e.g. in
the month folder `~/Documents/bookeeping/2026/June/`).

## Optional: push to Google Sheets / Drive
The CSV can be uploaded with the `accessing-google-drive` skill if the user wants it in Sheets rather than a
local file — ask first.

## Related
`otto-download-statements` (step 1 — fetch the PDFs) · `orderonotto-ordering` (OTTO login/nav).
