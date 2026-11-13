---
name: otto-sale-week-ordering
description: >-
  Adjust and split OTTO (orderonotto.ca) orders for OUR sale stores (Route 1702 — Sobeys
  Mumford, etc.) using the SFO over/under signal, sale/feature (★) status, 4-week returns, and
  the display-vs-shelf rule — then SPLIT the week's quantity across Tue/Thu/Sat around a Thursday
  sale (Tuesday pre-build ~70%, Saturday covers Sat+Sun+Mon) and wind down the following Tuesday
  when the sale ends Wednesday. Use when the user asks to adjust/place/split the week's order for a
  sale store, "how do I order for the sale week", or to apply the Mumford/1702 ordering method.
  Browser automation (Playwright), macOS. See `orderonotto-ordering` for login/nav and the order grid.
---

# OTTO — Sale-week ordering & Tue/Thu/Sat split (Route 1702 / Sobeys Mumford)

This is the user's own ordering methodology for their **sale stores** on **Route 1702** (primary
example: **Sobeys Mumford**, 6990 Mumford Rd). It turns the week's suggested quantity into an
**adjusted order split across the three delivery days (Tue / Thu / Sat)** around the **Thursday sale
flip**, protecting the sale display's fill rate while controlling stale.

Build on `orderonotto-ordering` for **login, picking route/customer/week, filtering a product, and
reading the grid**. Use `otto-week-execution` to confirm what's on sale + where it goes (displays/MOD),
and `otto-stale-check` for the returns detail. This skill is the **decision + day-split layer** on top.

> Terminology note: in the grid, **SFO** is the week's **actual sales** number (Totals column), shown
> with a small variance superscript vs the Final Order. The user reads it by **color**: **red = we
> over-ordered (sold under the order) → DECREASE**, **green = sold over → INCREASE**.

## Step 1 — Read the signals for each product (in the week column)
1. **SFO number + color** (the week-total sales figure):
   - **RED** → **over-ordered** → **decrease** the order.
   - **GREEN** → **increase** the order.
2. **On sale this week?** A **★ (star)** in the day cell, or **"Featured – in store"** on the product
   name = the product is **on sale** that week. Sale prices are visible in the grid. Confirm the week's
   features via `otto-week-execution` (Useful Information → "1.0 Features & What's In Store").
3. **4-week returns (4wk Rtn%)** — before trusting the suggestion, look back: in the last 4 weeks, was
   this item **on sale**, and **how much came back (stale)** the week after? **High returns after a past
   sale = we over-ordered that sale** → this time **control the stale**; don't blindly ramp it just
   because it's on sale again. (Detail: `otto-stale-check`.)

## Step 2 — Decide the week's total quantity for a sale item
- **On sale + a display location is specified** (the feature doc / MOD says *where* the product goes):
  order **1–2 trays OVER** the suggested number (build the display).
- **On sale but on-shelf only** (no display assigned): size from **past sales** and land **~1 tray over**
  — enough to not run out, not so much it goes stale.
- **Not on sale:** forecast from recent non-sale sales (see `otto-ordering`); nudge per the SFO color.
- **Everything in Tray Factor (TF) units:** every adjustment (up or down) is placed in **whole TF
  multiples only** (e.g. TF 9 → …18, 27, 36…). Round to the nearest TF multiple, never a partial tray.

## Step 3 — Split the week's quantity across Tue / Thu / Sat
Sale prices normally **flip on Thursday**. Split the week's total so the display is built *before* the
sale starts and the store stays full through the weekend:

| Delivery day | Share of the sale-week total | Purpose |
|---|---|---|
| **Tuesday** (pre-sale) | **~70%** | Build the display **before** Thursday's sale starts — most of the week's product lands here. |
| **Thursday** (sale flip) | part of the remaining ~30% | Top up as the sale goes live. |
| **Saturday** | part of the remaining ~30% | **Must cover Sat + Sun + Mon** (next delivery is Tuesday). |

- The **Tuesday ~70% pre-build** is the **sale-week** behavior. On a **normal (non-sale) week**, split the
  week's quantity more **evenly** across Tue/Thu/Sat (sized to each day's coverage window), without the
  70% front-load.
- Size **Saturday** for a **3-day window (Sat/Sun/Mon)** since there's no Sun/Mon delivery.

## Step 4 — Wind down after the sale
- The sale **ends Wednesday** the following week. So the **next Tuesday's** order should be
  **significantly smaller** — the store still has product **coming off the displays**, so don't reload a
  full build. This is where over-ordering (and next-week stale) usually creeps in — keep it lean.

## Workflow (apply it)
1. Log in; select **Route 1702** → the customer (e.g. confirm **which** Mumford store — `DL SOBEYS 881`,
   `GR SOBEYS 881`, or `Mumford Walmart`) → the target week. (`orderonotto-ordering`.)
2. Confirm the week's **features/★ and display placement** via `otto-week-execution`.
3. For each product: read **SFO color**, **★/Featured**, **4wk Rtn%**; decide the **week total**
   (display → +1–2 trays; shelf-only → +~1 tray; else forecast), **rounded to TF**.
4. **Split** the total: Tuesday ~70% (sale week), remainder Thu + Sat; Saturday covers Sat/Sun/Mon.
5. Enter via **ADJ / F.O.** per day, then **Review** and **verify before submit**.
6. Plan the **following Tuesday small** (post-sale wind-down).

## Scope & assumptions
- Applies to our **own sale stores on Route 1702** — primary worked example **Sobeys Mumford**; the same
  method generalizes to other sale stores on the route. Always scope to **our stores only**.
- **Adjustments are TF-multiple, whole trays only** — never partial.
- Confirm the exact Mumford customer code with the user before trusting a number (3 stores share the
  Mumford Rd address — see `orderonotto-ordering` "Customer ambiguity").

## Related skills
- `orderonotto-ordering` — login/nav + reading the grid (S.O./ADJ/F.O./SFO/★/TF/4wk Rtn%).
- `otto-week-execution` — what's on sale/featured + what goes on which display (MOD/where).
- `otto-ordering` — general demand forecast / how much to order (non-sale baseline + factors).
- `otto-stale-check` — returns / over-ordering detail (the 4-week stale signal).
