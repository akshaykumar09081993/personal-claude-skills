---
name: otto-pick-sheet
description: >-
  Build a printable per-day PICK SHEET of Bimbo Canada OTTO orders — one printable A4 page grid with
  products (Code + name) down the rows and stores across the columns, each cell the Final Order (F.O.)
  to pick for that product at that store on the chosen day. Use whenever the user asks for a pick
  sheet / pick list / picking sheet / "what to pull for <date>" / a load-out sheet for a delivery day.
  Products that are 0 at every store are dropped; stores can be excluded (e.g. the Sun/Mon Costco
  accounts). Needs the order data JSON first — produce it with the `otto-scraper` skill's
  `dl_orders.js` (all customers × all weeks F.O.). macOS; requires python3 + openpyxl.
---

# otto-pick-sheet — printable per-day pick sheet from OTTO orders

Turns captured OTTO order data into a clean, printable **pick sheet** for one delivery day: rows =
products (**Code** + Product name), columns = stores, cells = the **Final Order (F.O.)** quantity to
pick. All-zero products are removed so the sheet only lists what actually needs picking.

## Prereq — get the order data

The pick sheet reads a JSON file of orders (`otto-orders.json`) shaped by the **`otto-scraper`** skill's
`scripts/dl_orders.js` (all customers on the route × all selectable weeks, with per-day F.O. and
Grand-Total verification). If you don't have it yet:

```bash
NODE_PATH=~/Documents/claude/node_modules OTTO_USERNAME=.. OTTO_PASSWORD=.. \
  node <otto-scraper>/scripts/dl_orders.js          # -> ./otto-orders.json
```

The JSON already contains every day in the rolling ~12-week window, so a pick sheet for any of those
days is a pure local transform — **no re-scrape needed** to change the date.

## Build the pick sheet

```bash
python3 scripts/pick_sheet.py --date Oct-1 \
  --data otto-orders.json \
  --out PickSheet_Oct-1.xlsx \
  --exclude 1193808,1193811        # e.g. leave out SUN COSTCO + MON COSTCO accounts
```

| Flag | Meaning |
|---|---|
| `--date` | Day to pick, matched against the day-label prefix (e.g. `Oct-1`, `Sep-27`). The right week is found automatically. |
| `--data` | Orders JSON from `dl_orders.js` (default `otto-orders.json`). |
| `--out`  | Output `.xlsx` (default `PickSheet_<date>.xlsx`). |
| `--exclude` | Comma-separated **customer ids** to leave out of the columns. |

### What you get
- One worksheet, **A4 landscape, fit-to-one-page-wide, header row repeats on every printed page**,
  gridlines on, narrow margins, footer with page numbers — ready to **File ▸ Print** as-is.
- Columns: `Code | Product | <store…> | Total`; a bold **TOTAL** row sums each store column.
- **Code = the Bimbo article code** (2nd part of the sku, always present). The product name's leading
  material number is stripped from the description (handles both `1290542 NAME` and glued `197085NAME`).
- **Rows dropped** when the product is 0 at every included store that day; rows sorted by product name.
- Only stores that actually have data for that day appear as columns (minus `--exclude`).

## Gotchas
- `--date` must match how the grid labels the day (`Mmm-D`, e.g. `Oct-1` not `October 1`). Run without
  a valid date and the script lists nothing — check the labels in the JSON (`records[].days`).
- A store with orders of 0 for the whole day still shows as a column (all zeros) — tell the user, or
  add its id to `--exclude` to drop it.
- Find customer ids in the JSON (`customers[].id`) or the `otto-scraper` output log.
