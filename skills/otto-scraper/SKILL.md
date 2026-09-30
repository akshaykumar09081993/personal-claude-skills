---
name: otto-scraper
description: >-
  Use when BUILDING a new automated scraper/agent for the Bimbo Canada OTTO portal (orderonotto.ca)
  — e.g. "make an agent that pulls X from OTTO every day", scheduled scrapes, or reading OTTO pages
  (catalog/tray factors, promotions, Costco TPD, statements, reporting) or bulk-reading ORDER
  QUANTITIES (Final Orders per product/day/store/week) headlessly. Provides a reusable Playwright
  client (login + navigation + PDF download + ordering-grid helpers with pagination) so you never
  re-write the boilerplate. OTTO is an Angular SPA: must use a real browser (NOT raw HTTP). macOS +
  Playwright. For a quick one-off interactive look at order numbers, the `orderonotto-ordering` skill
  is simpler; use this one to build a repeatable/scheduled order export.
---

# otto-scraper — build OTTO scraping agents fast

OTTO (`orderonotto.ca`) is an Angular Material **single-page app**, so it must be driven with a real
headless browser (Playwright/Chromium) — raw HTTP/curl returns an empty shell. Every scraper needs
the same boilerplate: read credentials, launch a browser, log in (the SPA sometimes paints blank and
must be retried), navigate, and download/parse. **Don't rewrite that each time** — this skill bundles
it as `scripts/otto.js`. A new agent then only writes the bit unique to its job.

## Quick start

```bash
# 1) start from the template
cp scripts/otto.js scripts/dl_template.js  <your-project>/     # keep otto.js next to your agent
cp <template> dl_myjob.js                                       # then edit dl_myjob.js

# 2) run it (Playwright must resolve on the module path)
NODE_PATH=~/Documents/claude/node_modules \
OTTO_DATA_DIR=~/Documents/claude/otto-dashboard/data \
  node dl_myjob.js
```

Minimal agent:

```js
const otto = require('./otto');
(async () => {
  let browser;
  try {
    const { browser: b, ctx, page, has } = await otto.connect();      // launch + log in
    browser = b;
    await otto.goto(page, has, 'useful-information', 'Collections');  // navigate + wait
    const saved = await otto.downloadPdfLinks(ctx, page, {            // scrape
      match: /Atlantic Promotions/i, outDir: otto.dataDir('promos') });
    console.log('saved', saved.length);
  } catch (e) { console.error('ERR', e.message); process.exitCode = 1; }
  finally { if (browser) await browser.close(); }
})();
```

To scrape the DOM into JSON instead of files: `const rows = await page.evaluate(() => { …read document…; return [] });` then `fs.writeFileSync`.

## `scripts/otto.js` API

| Function | What it does |
|---|---|
| `readCredentials()` | `{username,password}` from `~/.config/otto/credentials.json`, or env `OTTO_USERNAME`/`OTTO_PASSWORD` (env wins). |
| `dataDir(name)` | Creates & returns `<OTTO_DATA_DIR or ./data>/<name>/`. |
| `connect(opts)` | Launches Chromium + download-enabled context + page, **and logs in**. Returns `{browser,ctx,page,has}`. |
| `login(page,has,creds)` | Login flow alone (handles the SPA blank render: waits for content, reloads once). |
| `goto(page,has,urlPath,waitText,opts)` | Navigate to an OTTO route, wait until it paints (`waitText` = string/array, any match = ready). |
| `downloadPdfLinks(ctx,page,{match,outDir,nameFn})` | Download every `<a>` whose text matches `match` (RegExp) as a PDF; dedupes; returns new filenames. |

### Ordering-grid helpers (reading order quantities — F.O. per product/day)

Use these instead of re-parsing the grid by hand or by screenshot. `connect()` returns as soon as the
app paints but **before** the controls are interactive — call `waitOrderingHub` first.

| Function | What it does |
|---|---|
| `waitOrderingHub(page,has,tries?)` | Wait until the hub controls are actually interactive (Customers box + ≥2 `mat-select`). |
| `listCustomers(page)` | Every customer on the route — the empty Customers autocomplete lists them all → `[{id,name,addr}]`. |
| `selectCustomer(page,id)` | Pick a customer by id/number (retries; force-clicks through overlays). Returns bool. |
| `listWeeks(page)` | Week numbers in the Week dropdown (rolling ~12-week window), `(Current)` stripped. |
| `selectWeek(page,wk)` | Select a week (Route=`mat-select` nth 0, Week=nth 1, page-size=nth 2). Returns bool. |
| `setPageSize(page,n)` | Paginator items-per-page (options **5/10/25/35** — max 35, so you still paginate). |
| `readGridPage(page)` | Read the current page: `{week,days[7],products[{name,sku,rtn4wk,tf,fo[7],so[7],weekTotalFO}],grandDays[7],pageInfo}`. |
| `collectOrderGrid(page,wk)` | **Walk every paginator page** for the selected week → `{week,days,products,grandDays}`. Call `selectWeek` first. |
| `clearOverlays(page)` | Remove `.cdk-overlay-backdrop` (they intercept clicks) + close open panels. |

**Grid DOM contract** (it is NOT a `<table>` — it's an Angular `<hub-table>` of divs): each product is a
`.row` whose **direct children are 17 columns** `[details, 7 day-cells, week-total, 7 day-cells, week-total]`.
In a day cell: **F.O. = `.cell.fo span`**, S.O. = `.cell.so`, ADJ = `.cell.adj`. Selecting week N shows
**N and N+1 side-by-side** — read the first 7 days (= week N). This exact-selector read is more reliable
than screenshots (which the `orderonotto-ordering` skill recommends only because *ad-hoc* innerText
parsing collapses empty cells).

**Pagination is mandatory** — the grid shows only 10 rows/page, so a single-page read silently
undercounts. `collectOrderGrid` walks all pages (paginator next/first buttons need
`click({force:true, noWaitAfter:true})` or Playwright hangs on the SPA's post-click nav-wait).

**Verification** — the bottom `.row.subline.totals` ("Grand Totals") = per-day F.O. total across **all
products on all pages**. Always check `Σ product.fo[d] === grandDays[d]` for each day; if it fails you
missed a page. See `scripts/dl_orders.js` for a full all-stores × all-weeks export that does this.

**Stability** — big stores (200–360 SKUs) can stall for minutes but recover. Use a **fresh browser per
customer** (`connect()` per customer) and save incrementally so a re-run resumes. `dl_orders.js` shows both.

## Useful OTTO routes (pass to `goto`)

- `ordering-hub/routes` — order grid (default landing). Product rows, `TF n` order multiple, ★ = on sale.
- `useful-information` — document library: Atlantic Promotions / What's In Store (features), Costco Programs (TPD), Merchandising & Execution (MOD footage). Links are files → download & parse.
- `statements` — weekly PDF statements (Route = `mat-select` nth 0, Week = nth 1, then **View Reports**).
- `reporting` — units / $ / returns by product/customer (authoritative sales numbers).

## Prereqs & gotchas

- **Playwright/Chromium** must resolve — set `NODE_PATH=~/Documents/claude/node_modules` (or install `playwright` locally).
- **Credentials never in git** — `~/.config/otto/credentials.json` (chmod 600), or env vars.
- **Blank render** after login is handled by `connect()`/`login()` (retry + reload). For the ordering
  grid, then call `waitOrderingHub()` — `connect()` returns before the controls are clickable.
- **Angular overlays** (`.cdk-overlay-backdrop`) intercept clicks — the grid helpers all force-click and
  `clearOverlays()` between actions. Do the same if you drive `mat-select`/autocomplete yourself.
- For order quantities, use the **ordering-grid helpers above** (exact `.cell.fo` selectors) rather than
  screenshots — reliable and gives every product/day in one pass.

## Manual fallback (if the bundled script is missing)

Log in by: `goto` `https://orderonotto.ca/login.php` → fill `#mat-input-0` (email) / `#mat-input-1`
(password) → click `button:has-text("LOG IN")` → wait in a loop until `document.body.innerText`
contains `Product`/`F.O.`, reloading `/ordering-hub/routes` if still blank after ~12s. Then navigate
and read/download. Full nav mechanics: see the `orderonotto-ordering` skill.

## Working examples

- `scripts/dl_orders.js` — exports Final Orders for **every customer × every week** to JSON with
  per-day Grand-Total verification (fresh browser per store, resume, pagination). Turn the JSON into
  a spreadsheet downstream (e.g. Python `openpyxl`).

Live, scheduled versions built on this client are in the RouteSalesTracker repo
(`akshaykumar09081993/routeSalesTracker`, cloned at `~/Documents/claude/otto-dashboard`):
`agents/otto/dl_catalog.js` (catalog + tray factors), `dl_promotions.js`, `dl_costco_programs.js`,
`dl_statements.js`, plus `agents/otto/README.md` for wiring an agent into the launchd schedule via
`agents/orchestrator.py`.
