---
name: payroll-hours-reconciliation
description: >-
  Reconcile what an employee was PAID (a flat amount per pay cycle, e.g. $810) against what they
  should have earned from ACTUAL hours worked, and total the overpayment — including the prorated
  EMPLOYER CPP & EI and a WCB premium — then write a tidy breakdown into a Google Sheets tab. Use
  when the user says "I paid X a flat rate but they worked fewer hours — how much did I overpay /
  what do they owe me back", wants a per-cycle difference + total, or to reconcile a settled period
  vs an unsettled one. Reads actual hours from a "work schedule" tab (employee code per store per
  morning/afternoon, with hour annotations). macOS; python3 + the `accessing-google-drive` token for
  the Sheets API.
---

# Payroll hours reconciliation (flat pay vs actual hours)

## What it computes, per pay cycle
- **Actual earned** = hours worked × rate (from the schedule). **Wage diff** = flat pay − actual.
- **Employer CPP** and **employer EI** (from the paystub — CPP matches the employee's amount 1:1;
  **EI = 1.4 × the employee's EI**) are **prorated by `actual ÷ flat`** (CPP/EI scale with gross).
- **WCB** = the WCB rate (e.g. 4.93%, `$X per $100`) on the **total wage** overpayment.
- Then: total owed = Σ(wage + CPP + EI) + WCB, minus any amounts already repaid = remaining balance.

Important distinctions to keep straight:
- CPP/EI/WCB here are the **employer's own cost** (what you overpaid), **not** the deductions taken
  off the employee's cheque. EI employer ≠ employee (it's 1.4×); CPP employer = employee amount.
- Only the **wage** portion is money the employee received; CPP/EI/WCB are separate employer costs.
  State the figures plainly; let the user decide collection — don't lecture on CRA rules.

## Reading actual hours from the schedule tab
- Layout: a daily grid, columns per store each split Morning/Afternoon; each cell holds the employee
  **code** (e.g. `SU`), sometimes with hours in parentheses `SU(3)` or shared `MU(1.5) SU(1)`.
- **Bare cells use per-store standard hours** the user specifies (e.g. Herring Cove = 3 hrs, Mumford =
  4 hrs, other afternoons = 1 hr) — ask for these; explicit `(n)` always overrides.
- A per-period **summary block** (after the schedule columns) usually already totals each person's
  hours × rate. Cross-verify the summary against the raw grid cells (scan Morning cols AND Afternoon
  cols, matching `SU` anywhere in the cell, not just as the first name). If the user gives a confirmed
  earned total, defer to their number.
- Watch for a settlement marker (e.g. "SETTLED TILL ABOVE THIS") that splits a settled period (paid
  actual) from the flat-rate period.

## Quick start
```bash
# per-cycle actuals (dollars) and the flat amount; prints the full reconciliation:
python3 scripts/reconcile.py --flat 810 --cpp 40.19 --ei 18.48 --wcb-rate 0.0493 \
  --actual 461.50 --actual 284.00 --actual 275.125  # ... one --actual per cycle
# optional: --before-paid 6480 --before-earned 3609.25   (a prior settled period, same CPP/EI/WCB math)
#           --repaid 3000 --repaid 3000                  (amounts already collected back)
```
Then write the result into a new Google Sheets tab with the Sheets API (token via
`accessing-google-drive`): add tab, `values.update` with `USER_ENTERED` so formulas live, read back
to confirm. Keep each component on its own line (wage / CPP / EI / WCB) so the user can adjust rates.
