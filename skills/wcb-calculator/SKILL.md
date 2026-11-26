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

## Where it goes — the WCB tracking sheet (⚠️ APPEND, never overwrite)
The WCB total is logged in the **`WCB` tab** of the Google Sheet **WORK SCHEDULE SHEET**
(ID `18_BWXOARekLXgM4Br9tbQ1q6d2gX5SVRm0kk7fYY7h4`; write via the `accessing-google-drive` keychain
token, Sheets API, `values:batchUpdate` + `USER_ENTERED`). It holds **one stacked block per month**,
newest below older. The user's block format (match it):
```
<MONTH> 2026 — WCB (employees only, not contractors)
Employee              | <Mon> Gross
<name>                | <gross $>
… (one row per employee) …
Total employee gross  | =SUM(...)
WCB rate              | 0.0493
WCB @ $4.93 per $100  | =total*rate
```
- **ALWAYS read the WCB tab's CURRENT contents immediately before writing, and append the new month in
  the first free rows BELOW the last block.** Do NOT write to a fixed range like `A1:E12`.
  *(Hard lesson: an early "the tab is empty" read went stale while the user added the October block; a
  later fixed-range November write clobbered October rows 6–12 and left the October summary formulas
  re-summing November cells. Re-read right before writing.)*
- Keep the user's simple two-column style (`Employee | Gross`), not a fancy multi-column layout.
- `WCB-OLD` is a 160-row historical pay ledger in the same file — **never touch it.**

## Notes
- Use the **Approve** (final) registers, not **Calculate** (pre-approval) copies.
- "Payroll_Register" (small PDF) is enough; the big "Register" has the same figures.
- WCB is on wages only — it is an employer cost, separate from CPP/EI.
- **An employee's assessability can change month to month.** Harinder, e.g., is paid REGULAR+COMMISS
  (→ has T4 GROSS, counted) some months and all-CONTRACT (→ blank GROSS, excluded) others — Oct 2026 he
  was $4,308 assessable, Nov 2026 he was contract-only and correctly dropped. Trust the GROSS column per
  period; don't carry a person's status over from last month.
- **Pay-period map (2-week periods ending Saturday; group by period-END month):** Nov 2026 = PP23 (end
  11/06) + PP24 (end 11/20); Oct 2026 = PP21 (end 10/09) + PP22 (end 10/23); Sep 2026 = ends 09/11 + 09/25.
  Each month = the two periods whose END date lands in it. Confirm the two period-ends with the user.
