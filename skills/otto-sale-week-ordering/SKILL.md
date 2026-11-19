---
name: otto-sale-week-ordering
description: >-
  Correct OTTO (orderonotto.ca) orders for OUR sale stores (Route 1702 — Sobeys Mumford = GR SOBEYS
  881, cust 60454025) over a rolling 14-day window, using ACTUAL per-product sale sell-through from
  OTTO's ~12-week history (not OTTO's one-week forecast), the Sobeys promo/MOD display placement,
  4-week returns, and the two overlapping sales (this week's ending + next week's starting). Produces
  per-line Tue/Thu/Sat adjustments in whole tray-factors + the Nov-style wind-down/pre-build split.
  Use when the user asks to review/correct/adjust/split the week's order for a sale store, "how do I
  order for the sale week", or to apply the Mumford/1702 method. There is also a hosted agent that
  runs this every Monday and reports to Discord (see "Automated agent"). Browser automation
  (Playwright), macOS. See `orderonotto-ordering` for login/nav and the order grid.
---

# OTTO — Sale-week ordering & correction (Route 1702 / Sobeys Mumford = GR SOBEYS 881)

The user's ordering method for their sale stores. **Primary store: GR SOBEYS 881 HALIFAX, cust
`60454025`, 6990 Mumford Rd** (NOT "DL SOBEYS 881" 60453666 — that account carries 0 orders). Build on
`orderonotto-ordering` for login / pick route 1702 / customer / week / read the grid, and
`otto-week-execution` for the Features/MOD docs.

## The window: a "week" = 14 days, two overlapping sales
When the user says "week N", read **week N AND week N+1 (14 days)**. OTTO's week runs **Sun→Sat**; the
sale **flips Thursday** and **ends the following Wednesday**. So week N+1's Sun–Wed is week N's sale
*finishing*, and week N+1's **Thu onward is a DIFFERENT, NEW sale** (different featured products).
Detect per product from the grid's per-day `.featured` flag:
- featured days **[Thu,Fri,Sat] (idx 4,5,6)** = a sale **starting** that week → **build**.
- featured days only **[Sun..Wed] (idx 0–3)** = the prior week's sale **ending** → **wind down**.
The **next-week Tuesday** does double duty: a small tail for the ending sale **+** the pre-build for
the new sale's display. Re-run every Monday: window off the ending sale, build on the starting one.

## Read these signals per product (in the grid)
- **SFO / forecast:** the week-total has `.cell.predictive` (SFO) + `.variance` colored **green
  (sell over order → raise)** / **red (sell under → cut)**. **Actual SFO (sold) = F.O. + variance.**
  For FUTURE weeks the variance is OTTO's *forecast*; for PAST/current weeks it's *actual*.
- **★ / "FEATURED – In Store"** `.bubble.featured` (product) + `.cell.adj.featured` (per day) = on sale.
- **`4wk Rtn%`** (`.wrr`, colored) = stale rate — the over-ordering signal.
- **`TF n`** = tray factor; **all adjustments are WHOLE tray-factor multiples only.** ADJ goes in
  the editable `.cell.adj` input; F.O. = S.O. + ADJ.

## The method — anchor on ACTUAL sale sell-through, NOT OTTO's one-week forecast
OTTO's single-week forecast spikes are unreliable (verified: a +25 "sell 97" forecast on an item that
actually sells ~61 and sold *under* the prior week). **Pull the ~12-week history** (OTTO's Week dropdown
goes back ~8 weeks; drive explicit week numbers — `listWeeks` is flaky, `selectWeek(wk)` works) and for
each product build a timeline of **sold (F.O.+variance)** + **which weeks it was on sale**. Then:

1. **Find the last time it was on sale** and what it **sold** that week (+ the **stale the week after**
   = variance of week+1). That is the real predictor of this sale's demand.
2. **Does the ★ actually lift it here?** For many items at this store the sale produces **no lift** —
   tortillas/most bagels sell ~the same on sale as off (~24–28). **Do NOT build those to 2–3× to
   "fill the display"** — they just come back. Keep them ~1 tray over actual sale sell-through.
3. **Genuine feature-movers** DO spike on their feature week (e.g. Villaggio White 95–127, Dempsters
   WG breads 110+, Compliments Eng Muffins White 89) — build those, justified by history.
4. **Off-shelf / display placement** (from the Sobeys promo "Merch. Instruction": Front of Store
   Display, Feature Rack, Foyer, Bunker, Corrugate, Hearth Rack, Tortilla Rack) → the display needs
   filling, so order **+1–2 trays over the sale sell-through, or close to OTTO's forecast** — but
   capped by returns. **Mainline / Dairy Rack / Reg Retail = shelf** → anchor to sell-through, no pad
   (this is why on-shelf Eng Muffin Plain holds at 72, but a front-of-store Villaggio builds).
5. **Stale control:** high `4wk Rtn%` (≥25%) → cut toward the sale sell-through floor regardless of
   the sale; these are chronic over-orders the history confirms (e.g. Villaggio Sausage Bun 85%,
   Fibre Wholegrain sells 3–7 but ordered 20, Natural Rye 146%).
6. **Round everything to whole TF**; ADJ = target day F.O. − S.O.

## Weather & government payouts — a LIGHT tie-breaker for bread, not a driver
Tested against 11 weeks of this store's totals: **total bread demand barely moves with payouts or
weather** (it swings only ±15%; bread is a weekly staple). Per-product spikes are **feature/display**
driven, and Bimbo schedules features around paydays anyway (so the feature already captures it — don't
double-count). Use payout/weather only to:
- **not over-cut** a genuine feature when the window is payday-adjacent (CCB ~20th, CPP/OAS ~26th,
  Groceries/GST benefit quarterly ~Jan/Apr/Jul/Oct, month-end/biweekly paydays);
- flag the **real exceptions** — long weekends, storms (stock-up), and holiday weeks (Christmas).
Mild/neutral weather = no adjustment.

## The day split (Tue / Thu / Sat)
Sale flips Thursday, family cash (CDB/CCB) lands Thu/Fri. Build the display Tuesday but keep weight for
the Thu/Fri/Sat wave and keep bread fresh: **Tue ~45% / Thu ~25% / Sat ~30%** for sale items (Sat must
cover **Sat+Sun+Mon**). Non-sale: even-ish, Sat-heavier. The **next-week Tuesday** stays small for the
*ending* sale's items (wind-down) while building the *new* sale's items.

## Workflow (manual)
1. Login (core skill) → route 1702 → customer **60454025** → read current + next week with day detail.
2. Pull ~8 prior weeks (explicit week numbers) → per-product sold timeline + sale weeks.
3. Download this + next week's **Atlantic Promotions** + **What's In Store Execution** from Useful
   Information → parse the **SOBEYS MARITIMES** rows for each SKU's Merch. Instruction (display tier).
4. Apply the method → per-line target + Tue/Thu/Sat split in TF; enter in **ADJ**, Review, verify.
5. **Do NOT blindly order catalog-only items** (Vachon/Takis/Hostess holiday wall at 0 carried / 0
   forecast) — those are a manual display-size decision, not an auto-build. Scope bread/bakery.

## Displays, racks & planogram merchandising (the big first-order lever)
On-sale products go on a display per OTTO's Useful Information ("what goes where on sale"). The **sale
flips Thursday**, so stock must be in store **Tuesday** → the **first order** (Tuesday drop) adds the
display's **capacity** (a few trays **over** the suggested number, typically **+2–4 trays**) to build the
setup and capture the sale; **after** that first fill, order **predictively** from how it sold and what
**returned after** the previous time it was on this display. Displays are configured in the dashboard
Auto Order tab (`auto_order_displays`) as **permanent** or **temporary (end date)**, one product each.

**Standard rack types (shelves × volume/shelf = capacity units):**
| Rack | Shelves | Vol/shelf | Capacity |
|---|---|---|---|
| Front Lobby rack | 4 | 10 | 40 |
| Grocery End Cap / Demo Notices | 4 | 20 | 80 |
| Bunker Meat Dept. Standard | 4 | 15 | 60 |
| Dairy Rack | 4 | 7 | 28 |
| Book shelf slim | 4 | 7 | 28 |
| Bread towers | 4 | 12 | 48 |
First-order fill = `shelves × vol × count`, rounded **up** to whole trays, on the **Tuesday** drop.

**Which product / how to stock a family's display (merch standards):**
- **Brand priority:** if both **Compliments and Dempsters** are listed for a slot → stock **Dempsters only**.
- **Buns:** if it lists **hamburger + sausage** → **1 tray sausage, the rest hamburger**.
- **Grains:** **1 of each** variety **except honey oat and fibre** (leave those out of the "1 of each").
- **Holsum whites (shelf order, top→bottom):** **Xtra/Thick** on the top 2 shelves, then **Holsum WW**,
  then **Holsum White** on the bottom 1–2.
- **Villaggio (top→bottom):** **Rustico** top, then **Multigrain (MG)**, then **Artesano**, then
  **Villaggio WW**, then **Villaggio White** on the bottom to fill whatever's left.
- **Bagels (top→bottom):** **Cinnamon** top, then **Original**, then **Everything** across the bottom.

**The order = synthesis.** Final F.O. blends **OTTO's suggestion (S.O.)** + **all factors** (display
capacity + the merch arrangement above, 4-week returns, the brand × display × sale matrix, actual
sale sell-through / post-sale returns, weather-neutral, payout timing) + **judgment** — set in **ADJ**
(never S.O.), tray-round, split Tue/Thu/Sat with the Tuesday pre-build for the Thursday sale.

## Automated agent (hosted — runs every Monday)
The RouteSalesTracker app (`akshaykumar09081993/routeSalesTracker`, hosted at sparklinxgroup.ca)
runs this every Monday and posts a Discord report of what it would increase/decrease and why:
- Scraper: `agents/otto/dl_order_review.js` (current + next week day-detail, ~8 history weeks, promo
  PDFs) → `data/order_review/<cust>.json`.
- Analyzer: `ingest/order_corrector.py` (applies this method, posts Discord via `ORDER_WEBHOOK`).
- Orchestrator agent id **`order_review`**, scheduled Monday ~08:00. It **reports recommendations**
  (view + corrections + reasons) — it does **not** auto-submit orders to OTTO.

## Related skills
`orderonotto-ordering` (login/nav + grid), `otto-week-execution` (features/MOD/displays),
`otto-ordering` (general forecast), `otto-stale-check` (returns detail), `otto-scraper` (build agents).
