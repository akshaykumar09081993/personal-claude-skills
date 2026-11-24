---
name: payroll-hours-reconciliation
description: >-
  Work with the Sparklinx "WORK SCHEDULE SHEET" (Google Sheets) payroll. Two jobs: (1) the per-period
  PAY CALCULATION — "I made the payroll entries, do the calculations for <date> to <date>" — read the
  schedule grid for a Sat→Fri fortnight and build/append a per-period summary block (hours × rate +
  warehouse/monitoring $) in each route tab, matching the existing format; and (2) RECONCILE a flat
  amount paid (e.g. $810/cycle) vs hours actually worked, incl. prorated employer CPP & EI and a WCB
  premium. Use when the user says "do the calculations for the payroll period", "add the summary block",
  "how much did I overpay / what do they owe me back", or to tally an employee's hours/pay for a period.
  macOS; python3 + the `accessing-google-drive` keychain token for the Sheets API.
---

# Sparklinx payroll (WORK SCHEDULE SHEET)

## The spreadsheet
- **Name:** `WORK SCHEDULE SHEET` · **ID:** `18_BWXOARekLXgM4Br9tbQ1q6d2gX5SVRm0kk7fYY7h4`
- Auth: reuse the Google OAuth token from the macOS keychain exactly like the `accessing-google-drive`
  skill (`mcpOAuth["gdrive|…"].accessToken`). Call the **Sheets API v4** directly
  (`https://sheets.googleapis.com/v4/spreadsheets/<id>/...`). The drivemcp MCP is broken (403).
- **Tabs:** `Schedule-1702`, `Schedule-1736` (the two delivery routes — this is where payroll lives),
  `WCB`, `Employees`, `Stores`, `WCB-OLD`, `Sukhdev` (a standalone reconciliation — see bottom).

### Employee codes (the `Employees` tab is STALE — trust the grid)
`HA`=Harinder, `AM`=Amrinder, `MI`=Mike, `SU`=Sukhdev, `SS`, `V`, `TL`, `MT`, `AK`=Akshay,
`PA`=Parminder, `AS`, `AA`=Aman Anthal, `MU`=Mukul Sukhdev (old), `GU`=Gurvinder, `ME`=Mehul.
New codes appear without being added to `Employees` — confirm unknown ones with the user.

### The schedule grid (left side of each Schedule tab)
Row 0 = store names (merged over two cols), row 1 = `Morning`/`Afternoon`, then one row **per day**
with `Dates` (col A, `YYYY/MM/DD`) + `DAY` (col B). Each store = a Morning col + an Afternoon col.

| Tab | Morning/Afternoon store columns (C,D,E,F,G,H,I,J) | Monitoring |
|---|---|---|
| **Schedule-1702** | C/D Sobeys Herring Cove · E/F Sobeys Mumford · G/H Walmart Mumford · I/J Walmart Chainlake | K |
| **Schedule-1736** | C/D Sobeys Clayton Park · E/F Sobeys Timberlea · G/H Freshco | I |

> ⚠️ **Gotcha:** a tab can repeat a date on more than one row (e.g. Schedule-1736 has stray *empty*
> 11/19–11/20 rows far below the grid). **Sum every row whose date is in range** — do NOT key a dict by
> date (the empty duplicate silently overwrites the real row and undercounts). `period_pay.py` sums.

**Cell conventions**
- A cell holds an employee **code**, optionally with hours: `SU` (bare) or `SU(3)`. Combined/shared
  cells exist: `SS(1.5)HA(1.5)`, `V(1)SU(1)`, `V(1)HA(1)` — parse **every** `CODE(n)` token.
- Explicit `(n)` is **hours** and always overrides the standard. A **bare** cell uses the per-store
  standard hours below.
- **Monitoring column** holds a flat **$ amount**, not hours: in 1702 it's a bare number (e.g. `200`);
  in 1736 it's `CODE(amount)` (e.g. `AK(200)`, `HA(100)`, `MT(200)`). This money becomes a **warehouse**
  figure in the pay block (see below).

**Standard hours** (from the `Stores` tab — covers 1702 stores only; bare cells on 1736 are rare and
should be confirmed):
| Store (1702) | Morning | Afternoon |
|---|---|---|
| Sobeys Herring Cove | 3 (all days) | 1 (Thu, Fri, Sat, Sun) |
| Sobeys Mumford | 2 (all days) | 1 (Sat, Sun) |
| Walmart Mumford | 3 (all days) | 1 (Thu, Fri, Sat, Sun) |
| Walmart Chainlake | 3 (all days) | 1 (Thu, Fri, Sat, Sun) |

## Job 1 — the per-period pay calculation ("do the calculations for <start> to <end>")
A **pay period is a 14-day Sat→Fri fortnight** (e.g. 2026/11/07 Sat → 2026/11/20 Fri).

### The summary blocks (right side of each Schedule tab)
Per-period blocks are **stacked vertically down the right columns**, oldest at top, ~13–14 rows pitch.
They are **not** row-aligned with the date grid and carry **no dates** — the newest block is simply the
lowest one. **1702 blocks live in cols N–W; 1736 blocks live in cols K–T.** Current format (rate shown
in the header, currently **$18/hr**; it has climbed 16 → 16.50 → 17.50 → 17.75 → 18):

```
Code | Afternoon | Aft × 18 | Morning | Mor × 18 | Warehouse | TOTAL | Past Settlements | Total | Notes
```
- `Aft × 18` = `=<Aft>*18`, `Mor × 18` = `=<Mor>*18` (live formulas).
- `TOTAL` = `=SUM(Warehouse, Mor×18, Aft×18)` — gross earned for the period.
- `Total` (last money col) = the **payout**: usually = TOTAL, but overridden for flat-paid people and
  reduced by any advance in `Past Settlements`.
- Block ends with a blank row then a `Total` row: `TOTAL = SUM` of the TOTAL col, `Total = SUM` of the
  payout col.

### Special pay rules (NOT derivable from the grid — apply these)
- **SU (Sukhdev) is paid a flat $810/cycle** regardless of hours. Still record his hours, but set his
  payout `Total` = **810**. (He is the subject of the `Sukhdev` reconciliation tab.)
- **Mike (MI) is NOT paid hourly in these blocks** — he fills many morning cells but is salaried/paid
  separately. **Skip him** (default). Same default for **TL** on 1736 unless the user says otherwise.
- **Monitoring $ → Warehouse.** 1702: the bare `200`/day in col K accrues to **HA's** warehouse (e.g.
  6 days × $200 = $1,200). 1736: each `CODE(amount)` becomes that code's own warehouse row.
- **HA carries a running advance** (flight, etc.), tracked in `Past Settlements` / `Notes` as
  "`<prev> - <deduction> = <remaining>`". The per-period deduction is **not** in the grid — ask the
  user, or leave `Past Settlements` blank and flag it.
- Confirm the **rate**, Mike/TL handling, and any advance deduction before writing (one AskUserQuestion).

### Workflow
1. Read `Schedule-1702` & `Schedule-1736` fully (Sheets `values` GET per tab).
2. `scripts/period_pay.py --tab Schedule-1702 --start 2026/11/07 --end 2026/11/20` prints the per-code
   Morning/Afternoon hour tally + monitoring $ for the fortnight (bare cells → standard hours). Repeat
   for 1736. Eyeball for new codes / anomalies.
3. Find the **last** block in each tab (read the right cols with `valueRenderOption=FORMULA` to copy the
   exact layout + rate) and the first free rows below it.
4. Append the new block with Sheets **`values:batchUpdate`**, `valueInputOption=USER_ENTERED` so the
   `*18` and `=SUM(...)` formulas stay live. Apply the special rules above.
5. **Match the colours/formatting** of the previous block (the user wants them identical). After writing
   the values, do a spreadsheet **`batchUpdate`** with `copyPaste` + `"pasteType":"PASTE_FORMAT"` from the
   previous block's range onto the new one (PASTE_FORMAT copies bg colours/bold/borders and leaves values
   untouched). If the new block has fewer rows, copy in 3 parts — header row, one data row tiled over the
   data+blank rows, and the Total row — so header/data/total formats land on the right rows. Need the tab
   `sheetId` (Schedule-1702 = `0`, Schedule-1736 = `1771622848`) and 0-based grid indices. The current
   palette: header = pink `Code/Morning` + blue `Afternoon/Aft×18` cells (bold); data = light blue.
6. **Read the block back** with `UNFORMATTED_VALUE` and show the user the resolved numbers + every flag
   (skipped people, flat overrides, advances left blank, new codes).

Worked example — Nov 7–20 2026: 1702 → SU 18m(flat 810), AM 12m, SS 6a/9m, V 22m, HA 16a/12m + $1200
wh (TOTAL $2,910 / payout $3,396). 1736 → SS 48m, HA 1m + $300, AK $500, MT $1200 (TOTAL $2,882). Mike
& TL skipped; HA advance left blank.

## Job 2 — flat-pay vs actual-hours reconciliation
When the user paid a flat amount per cycle but wants to know the overpayment vs hours worked:
- **Actual earned** = hours × rate. **Wage diff** = flat − actual.
- **Employer CPP** (= employee amount 1:1) and **Employer EI** (= **1.4 ×** employee EI), from the
  paystub, **prorated by `actual ÷ flat`** (they scale with gross).
- **WCB** = the rate (e.g. 4.93% = `$4.93/$100`) on the **wage** overpayment.
- Total owed = Σ(wage + CPP + EI) + WCB − amounts already repaid.
- CPP/EI/WCB here are the **employer's own cost**, not the cheque deductions. Only wage is money the
  employee received. State figures plainly; let the user decide collection.
- Watch for a settlement marker (e.g. "SETTLED TILL ABOVE THIS") splitting a settled from a flat period.

```bash
python3 scripts/reconcile.py --flat 810 --cpp 40.19 --ei 18.48 --wcb-rate 0.0493 \
  --actual 461.50 --actual 284.00 --actual 275.125   # one --actual per cycle
# optional: --before-paid 6480 --before-earned 3609.25   (prior settled period)
#           --repaid 3000 --repaid 3000                  (already collected back)
```
Write the result into a Google Sheets tab (`values.update`, `USER_ENTERED`, one component per line so
rates stay adjustable); read back to confirm. The `Sukhdev` tab is a completed instance of this.
