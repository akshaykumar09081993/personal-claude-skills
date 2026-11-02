---
name: wcb-calculator
description: >-
  Work out how much WCB (Workers' Compensation Board) premium the business owes for a given month,
  for EMPLOYEES ONLY (not contractors), from the ADP "Payroll Register" PDFs. Use whenever the user
  asks "how much WCB do I owe for <month>", to total WCB, or to fill a WCB tracking sheet. WCB =
  assessable payroll (T4 gross wages) × the WCB rate ($ per $100; the user's NS rate is 4.93, i.e.
  4.93%). Contractors are excluded automatically because their CONTRACT earnings are not in ADP's
  T4 GROSS column. macOS; needs python3 + pdfplumber. Get the register PDFs via the `adp-teampay` skill.
---

# WCB calculator (employees only, from ADP Payroll Registers)

## The method that works
Each pay period's **Payroll Register** PDF lists every payee with earnings typed as
**REGULAR / COMMISS** (employees → T4 wages) or **CONTRACT** (contractors → NOT WCB-assessable).
The register's **GROSS (BRUT) column is only populated for employee wages** — contractors show
blank there — so summing the GROSS column gives employee assessable payroll and drops contractors
for free. Terminated / no-pay employees show unchanged YTD and a blank current GROSS (→ $0, excluded).

- **Parse the GROSS column by x-coordinate (~x=144), NOT by splitting text** — the REGULAR line
  interleaves units and amounts (`REGULAR <cur-units> <ytd-units> <cur-amount> <ytd-amount>`), so a
  naive text split grabs *hours* instead of dollars. Coordinate extraction of the gross number on each
  name row is reliable. Always print the per-person breakdown and have the user eyeball it.
- **Which periods = which month:** the user files WCB by the pay period's **period-END month**, not pay
  date (e.g. a period ending 09/25 but *paid* 10/02 is **September**). Pick the Approve-function
  registers whose PAY END date falls in the target month. Confirm with the user if ambiguous.
- Amounts in the PDF are in **cents** (e.g. `81000` = $810.00).
- **Rate:** `$5 per $100` = 5%; the user's actual NS rate is **4.93%** (`× 0.0493`). Always confirm.

## Quick start
```bash
# Point at the folder of Payroll Register PDFs (from adp-teampay), give the WCB rate and the
# period-END dates that belong to the target month:
python3 scripts/wcb_from_registers.py \
  --dir ~/Documents/adp-download \
  --rate 0.0493 \
  --period-end 2026-10-09 --period-end 2026-10-23
```
It prints each employee's gross per register, the monthly total, and the WCB owed, plus flags any
CONTRACT payees it excluded.

## Notes
- Use the **Approve** (final) registers, not **Calculate** (pre-approval) copies.
- "Payroll_Register" (small PDF) is enough; the big "Register" has the same figures.
- WCB is on wages only — it is an employer cost, separate from CPP/EI.
