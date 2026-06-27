---
name: orderonotto-ordering
description: >-
  Navigate and read the Bimbo Canada "OTTO" ordering portal (orderonotto.ca) via headless-browser
  automation (Playwright) — log in, pick a route/customer/week, filter a product, and read the order
  grid (Suggested / Adjustment / Final Order, returns %, weekly totals). Use whenever the user asks
  about OTTO orders, bread/bun order quantities, returns/stale, or forecasting orders for a store
  (e.g. "how much Holsum White / Dempsters HB did we order for <store> on <day>"). OTTO is an Angular
  Material SPA that must be driven with a real browser (NOT raw HTTP/API). macOS + Playwright/Chromium.
---

# OrderOnOtto (OTTO) ordering portal

Bimbo Canada's bakery **ordering portal**: `https://orderonotto.ca/login.php`. It's an **Angular Material
single-page app** — you MUST drive it with a real headless browser (Playwright/Chromium). Raw HTTP / curl
returns an empty shell (the data is JS-rendered). In llmoperator, run it through the **scraper** agent /
`browser_actions`; standalone, run the bundled `scripts/otto-fetch.js`.

## Credentials (NEVER commit these)
Supply at runtime via env vars — do **not** hardcode in this repo (it is public):
- `OTTO_URL`      = `https://orderonotto.ca/login.php`
- `OTTO_USERNAME` = the user's OTTO login (their business email)
- `OTTO_PASSWORD` = the user's OTTO password
The user's route is **1702**. (Username/password were provided in chat previously; keep them in a local
secret store / env, never in git.)

## Login flow
1. `goto` the login URL (`waitUntil: networkidle`).
2. Fill `#mat-input-0` = email, `#mat-input-1` = password (Angular Material ids).
3. Click `button:has-text("LOG IN")`.
4. Lands on `https://orderonotto.ca/ordering-hub/routes`.
5. **Gotcha — intermittent blank render:** the SPA sometimes paints blank (white page, just a spinner).
   Wait in a loop until `document.body.innerText` contains `Product` / `F.O.` (or a `mat-select` count ≥ 2);
   if still blank after ~12s, `goto` the routes URL again (reload) and keep waiting.

## Top controls (the three pickers)
- **Route** — a `mat-select` (shows e.g. `1702`). It is `mat-select` **nth(0)**.
- **Customers** — an **autocomplete `<input>`**, NOT a mat-select. Target it as
  `mat-form-field:has-text("Customers") input`. Click it, clear, type a search term (e.g. `Walmart`),
  then click the matching `mat-option`.
- **Week** — a `mat-select` (shows e.g. `26 (Current)`). It is `mat-select` **nth(1)**. Open it and click
  the `mat-option` whose text is the exact week number.

### Customer ambiguity (important)
Typing a place name can return several customers at the same address. Real example — `Mumford`:
- `60453666 - DL SOBEYS 881 HALIFAX`
- `60454025 - GR SOBEYS 881 HALIFAX`
- `60454695 - Mumford Walmart`   ← "Mumford Walmart"
All at 6990 Mumford Rd. **Confirm which store with the user** before trusting a number.

### Week window = history depth
The Week dropdown is a **rolling ~12-week window** (e.g. weeks 18–29 when current = 26). The **current**
week is labelled `NN (Current)`. So you can go back ~8 weeks (~2 months) and forward ~3 weeks; older history
is NOT in the ordering grid (check **REPORTING** / **STATEMENTS** in the top nav for deeper history — unexplored).

## Reading the order grid
- **Filter products:** the "Filter / Search" box — `getByPlaceholder(/filter|search/i)`; type a product name
  (e.g. `HAMBURGER WHITE 8PK`, `HOLSUM`) to narrow the grid.
- **Columns** = 7 day columns `MMM-D Ddd` (Sun→Sat), then a **Week Totals** column, repeated for the next week.
- **Rows per product** (sub-rows):
  - `S.O.` = **Suggested Order** (system suggestion)
  - `ADJ`  = **Adjustment** (manual +/-)
  - `F.O.` = **Final Order = S.O. + ADJ**  ← *this is the actual order placed* (read this for "how much ordered")
  - `SFO`  = the week's **actual SALES** (scan/POS), shown in the weekly Totals column with a small
    **superscript = variance vs the Final Order** (i.e. `SFO − F.O.`):
    - **negative superscript** (e.g. `30 ⁻²⁰`) = sold LESS than ordered → **stale / over-ordered** (cut the order)
    - **positive superscript** (e.g. `188 ⁺⁶⁸`) = sold MORE than ordered → **sold out / under-ordered** (raise the order)
    This is the single best signal for fixing orders. (`4wk Rtn%` is the 4-week average stale rate; SFO variance is this week.)
- **★ (star) in a day's cell = that product is ON SALE / on feature that day** → expect a demand spike; order
  up for starred days (this is why on-sale items like the Holsum breads sell far over their order). Cross-check
  the Features/Promotions PDFs in **Useful Information → "1.0 Features & What's In Store"** for the week.
- **Product header** shows the SKU code, **`4wk Rtn%`** (4-week return / stale rate — over-ordering signal),
  and **`TF n`** = the **order multiple** (orders move in multiples of n; e.g. TF 9 → 9,18,27,36,45,54,63,81…).
- Products deliver only on certain days (e.g. Tue/Thu/Sat); other days are 0.

To answer "how much <product> for <store> on <day>": set customer → set week → filter product → read the
**F.O.** in that day's column.

## USEFUL INFORMATION section (displays & what's-on-sale)
Top-nav **USEFUL INFORMATION** → `https://orderonotto.ca/useful-information` is a document library
("Collections") of PDF/XLSX files, grouped into collections (each with a "Show More"). The ones that
inform ordering:
- **"… Walmart Snack Cake MOD"** + **"ATL - 2.0 Merchandising & Execution"** = **display / planogram (MOD)
  docs** — e.g. `20FT / 16FT / 12FT / 08FT / 04FT MRTM 78H 24D GON R`. These show the **display footage &
  layout** (how much shelf/display space a store has) → directly tells you where you need **more quantity**.
- **"ATL - 1.0 Features & What's In Store"** = **what's on sale / promotions**, by week — e.g.
  `Week NN 2026 Atlantic Promotions`, `Week NN 2026 What's In Store Execution`, `Atlantic <Month> Execution
  Priorities`. Use this to anticipate demand lifts on featured/on-sale items.
- Also: **3.0 Marketing & LTO** (sell sheets, limited-time offers), **4.1 Product Info** (catalogues, portfolio).
To read the actual contents you must **open/download the PDF/XLSX** (each row is a file link) and parse it —
the page itself only lists titles + dates. There's a Filter/Search box at the top of the page.

## REPORTING & STATEMENTS — real sales $, units, returns
- **REPORTING** (`/reporting`): **By Product / By Customer**, filter by Route / Customer / Customer Type /
  Location Group / Banner / Brand. Metrics per **This Week, Next Week, Last Week, Rolling 4-wk, Rolling 8-wk**:
  **Gross Units Sold · Units Returned · Return % · Net Units Sold · Net Sales Total ($)**. This is the
  authoritative source for sales $, volumes and returns — use for forecasting baselines, stale ranking, and
  real annual figures. **Scope to our own stores.**
- **STATEMENTS** (`/statements`): weekly **PDF statements** per route — Distributor Weekly Statement,
  Distributor_Revenue_Route, Distributor_Route_Activity — **52 weeks** retained → actual **$ revenue**
  (save weekly). Route Accounting contacts are listed on the page.

## Task-specific OTTO skills
For specific jobs use: **`otto-stale-check`** (returns/over-ordering), **`otto-ordering`** (demand forecast /
how much to order), **`otto-week-execution`** (what's on sale + displays/MOD from Useful Information). All
scope to our own stores and build on this skill's login/navigation mechanics.

## Quick start (bundled helper)
```bash
OTTO_USERNAME='...' OTTO_PASSWORD='...' \
  node scripts/otto-fetch.js --customer "Walmart" --week 26 --product "HAMBURGER WHITE 8PK" --out /tmp/otto.png
```
Prints the matched customer, the day headers, and the product's S.O./ADJ/F.O. block as JSON, and saves a
screenshot. Reading the **screenshot** is the most reliable way to map values to day columns (the grid's
innerText collapses empty cells, so blind text parsing is error-prone).

## Known product name mappings (Mumford Walmart, route 1702)
- "Holsum White" → `DEMPSTERS HOLSUM BREAD WHITE 570G` (921963)
- "Dempsters 8pk HB" → `DEMPSTERS HAMBURGER WHITE 8PK` (921606) — but several 8pk variants exist
  (Seeded, Sig Gold, Habanero, Potato, and a 12PK); confirm which.

## Forecasting orders (context)
A good order recommendation combines: **F.O. history** for that product/store/day + the **4wk Rtn%** (trim if
high) + external signals you research separately — **Halifax weather** (Mumford Rd is in Halifax NS), **NS
school calendar** (term ends ~Jun 30), **Canada Day Jul 1** (burger-bun spike), and **CRA benefit dates**
(GST/HST→Groceries benefit, CCB) which lift grocery spend. TimesFM (the llmoperator forecaster) only does the
numeric series — these factors are manual adjustments.

## Caveats / not yet done
- **Placing/editing orders** (editing ADJ/F.O. then **Review**/save) was NOT tested — there are
  `Email`, `Download Report`, `Review`, and `Revert All Changes` buttons. Verify carefully before submitting.
- Run `node` from a directory where `playwright`/`crawlee` resolve (or set `NODE_PATH`); use the scraper image.
