---
name: otto-ordering
description: >-
  Decide how much to order for OUR stores on the Bimbo Canada OTTO portal (orderonotto.ca) — forecast
  demand per product/store/day and set the order slightly above sales to protect fill rate while
  minimizing stale. Use when the user asks "how much should I order", to plan/adjust orders, or for a
  demand forecast. Browser automation (Playwright), macOS. See `orderonotto-ordering` for login/nav.
---

# OTTO — Ordering / demand forecasting (our stores only)

Scope: **only our own customers** (the stores on our route(s) — e.g. Route 1702: Walmart Mumford Rd,
GR & DL Sobeys 881, independents; plus our additional route). Always filter Reporting / select customers to
**our stores** — ignore other banners/operators.

## Method — order = forecast demand, set slightly ABOVE, rounded to TF
1. **Baseline** = recent **actual sales (SFO / Net Units Sold)** trend — forecast on the *non-sale* weeks,
   not the order. Pull from the **Ordering Hub grid (SFO)** and/or **REPORTING → By Product** (Rolling 4-/8-wk
   avg Net Units) for our customer.
2. **Sale-aware** = if the coming week is **on sale (★)** (confirm via Useful Information feature/promo PDFs,
   see `otto-week-execution`), scale up to the on-sale sell-through, not the normal level.
3. **Adjust for external factors**, then **add a small cushion (~5–10%)** and **round UP to the TF multiple**.

## Factors we model to predict the sale number
- Actual sell-through (SFO) trend & history
- Suggested vs adjusted vs final order (S.O. / ADJ / F.O.)
- Returns / stale (4-wk Return %, SFO−F.O. variance) — see `otto-stale-check`
- On-sale / feature (★) status + the weekly promotion calendar
- Day-of-week / delivery-day pattern
- Order multiple / Tray Factor (TF)
- Display & shelf capacity (MOD); for club (Costco) store-shared POS data
- Statutory holidays & long weekends (Canada Day → bun/BBQ lift)
- School calendar (in-session vs summer)
- CRA benefit pay-dates (GST/Groceries benefit, CCB, CPP/OAS) + paydays / club shopping cycles
- Weather (temperature, rain) + nearby local events

## Workflow
1. Log in (core skill); select our route + customer + week.
2. Filter to the product(s); read recent **SFO** (sales) across weeks + **Return %**.
3. Check the week's **features/promos & ★** (see `otto-week-execution`) and the calendar/weather factors.
4. Compute order = forecast + cushion, rounded to TF; enter in **ADJ/F.O.** then **Review** (verify before submit).

## Notes
- Costco is **delivery-only** — pure ordering: push volume, keep stale in check + high fill rate, use store
  sales data. No merchandising.
- Output per product/day: recommended F.O. with the reasoning (baseline sales, sale uplift, factor adjustments).
