---
name: otto-stale-check
description: >-
  Check stale / over-ordering on the Bimbo Canada OTTO portal (orderonotto.ca) — find which products
  are being ordered above what they sell (returns), per customer/route, and how much. Use when the user
  asks about stale, returns, over-ordering, "too much coming back", or which products to cut. Browser
  automation (Playwright) on macOS; see the `orderonotto-ordering` skill for login/navigation mechanics.
---

# OTTO — Stale / returns check

Goal: surface **over-ordered products** (ordered > sold = stale/returns) for a customer or route, ranked,
with the numbers, so orders can be cut. **Scope to our own stores only** (our route's customers — e.g.
Walmart Mumford, GR & DL Sobeys 881, plus our additional route) — filter Reporting / select customers
accordingly; ignore other banners/operators. Two complementary data sources in OTTO:

## A. REPORTING (best for a clean stale ranking)
Top nav **REPORTING** → `https://orderonotto.ca/reporting`.
- Choose **By Product** or **By Customer**; filter by **Route / Customer / Customer Type / Location Group /
  Banner / Brand**.
- Columns: **Gross Units Sold · Units Returned · Return % · Net Units Sold · Net Sales Total ($)**, for
  **This Week, Next Week, Last Week, Rolling 4-wk avg, Rolling 8-wk avg**.
- **Stale = high Return % / Units Returned.** Sort/scan for the worst offenders. Rolling 4/8-wk avg smooths
  one-off weeks. This is the authoritative returns view (and it has $).

## B. Ordering Hub grid (per-day detail + the on-sale context)
See `orderonotto-ordering` for login + setting Route/Customer/Week. In the product grid:
- Product header shows **`4wk Rtn%`** (4-week average return rate) — quick stale flag per SKU.
- Weekly Totals column shows **SFO = actual sales** with a small **superscript = SFO − F.O.** (sales minus
  order): **negative = stale/over-ordered (cut)**, positive = sold out (raise). This is the per-week truth.
- Cross-check the **★ (on-sale)** flag: a high-return week on a non-sale item is real over-ordering; on a
  sale item, demand is just lumpy — judge accordingly.

## Workflow
1. Log in (see core skill). Pick the route/customer.
2. REPORTING → By Product for that customer → rank by **Return %** (use Rolling 4-wk to avoid noise).
3. For the worst items, open the Ordering Hub grid → confirm the **SFO−F.O. variance** and recent order vs
   sales, and whether it's a ★ sale week.
4. Output: a ranked list — product · ordered (F.O.) · sold (SFO) · stale units · return % · recommended cut.

## Notes
- Real example (GR Sobeys 881): whole-grain loaves ordered ~50, selling ~30–33 → ~17–20 units/week stale each.
- Don't cut on-sale (★) weeks to the non-sale level — check the feature calendar (see `otto-week-execution`).
- Orders move in **TF multiples** — recommend cuts to a valid multiple.
