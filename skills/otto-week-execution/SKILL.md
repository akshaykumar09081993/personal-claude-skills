---
name: otto-week-execution
description: >-
  Plan the week's execution for OUR stores from the Bimbo Canada OTTO portal (orderonotto.ca) — what's on
  sale / featured this week, what goes on which display and where, and what will sell — by reading the
  Useful Information documents. Use when the user asks about this week's features/promotions, displays/MOD,
  "what's on sale", "what goes where", or what to push. Browser automation (Playwright), macOS.
---

# OTTO — Weekly execution: what's on sale, what goes where (our stores)

Scope: **only our own stores** (our route's customers). Decisions come primarily from the
**USEFUL INFORMATION** document library — read the actual PDFs/sheets, don't guess.

## Where to look — USEFUL INFORMATION (`https://orderonotto.ca/useful-information`)
A library of PDF/XLSX "Collections" (each has a Filter/Search + "Show More"):
- **"ATL - 1.0 Features & What's In Store"** → **what's on sale / promotions**, by week:
  `Week NN 20YY Atlantic Promotions`, `Week NN What's In Store Execution`, `Atlantic <Month> Execution
  Priorities`. → tells you the **featured / on-sale items to push and order up**.
- **"… Walmart Snack Cake MOD"** and **"ATL - 2.0 Merchandising & Execution"** → **planograms / MOD (displays)**:
  `20FT / 16FT / 12FT / 08FT / 04FT MRTM …` → tells you **what display, what footage, and where** product goes
  → where we need more quantity.
- **3.0 Marketing & LTO** (sell sheets, limited-time offers) and **4.1 Product Info** (catalogues, portfolio).
- The page lists titles + dates only — **open/download the file** to read contents and make the call.

## Cross-check in the Ordering Hub grid
The **★ (star)** in a day's cell = that product is **on sale that day** — it should line up with the week's
Promotions PDF. Use it to confirm which of our SKUs are featured, then order those up (see `otto-ordering`).

## Workflow
1. Log in (see `orderonotto-ordering`). Go to **USEFUL INFORMATION**.
2. Open this week's **"Week NN Atlantic Promotions" / "What's In Store Execution"** → list the **on-sale /
   featured items** relevant to **our stores/banners** (Walmart, Sobeys, club).
3. Open the relevant **MOD** docs for our stores → note **which displays / footage / location** each gets →
   where to build and how much space (→ how much to order).
4. Cross-check the **★ on-sale flags** in the grid for our customers.
5. Output: per store — featured/on-sale items this week, display placements (what goes where), and what to push
   / order up; hand the order quantities to `otto-ordering` and watch stale via `otto-stale-check`.

## Notes
- This drives ordering: featured/★ items get higher orders (sale-aware); display footage caps how much will go.
- Decisions must be grounded in the actual Useful-Information documents, scoped to our own stores.
