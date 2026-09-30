---
name: otto-scraper
description: >-
  Use when BUILDING a new automated scraper/agent for the Bimbo Canada OTTO portal (orderonotto.ca)
  — e.g. "make an agent that pulls X from OTTO every day", scheduled scrapes, or reading OTTO pages
  (catalog/tray factors, promotions, Costco TPD, statements, reporting) headlessly. Provides a
  reusable Playwright client (login + navigation + PDF download) so you never re-write the
  boilerplate. OTTO is an Angular SPA: must use a real browser (NOT raw HTTP). macOS + Playwright.
  For reading order quantities interactively, use the `orderonotto-ordering` skill instead.
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

## Useful OTTO routes (pass to `goto`)

- `ordering-hub/routes` — order grid (default landing). Product rows, `TF n` order multiple, ★ = on sale.
- `useful-information` — document library: Atlantic Promotions / What's In Store (features), Costco Programs (TPD), Merchandising & Execution (MOD footage). Links are files → download & parse.
- `statements` — weekly PDF statements (Route = `mat-select` nth 0, Week = nth 1, then **View Reports**).
- `reporting` — units / $ / returns by product/customer (authoritative sales numbers).

## Prereqs & gotchas

- **Playwright/Chromium** must resolve — set `NODE_PATH=~/Documents/claude/node_modules` (or install `playwright` locally).
- **Credentials never in git** — `~/.config/otto/credentials.json` (chmod 600), or env vars.
- **Blank render** after login is handled by `connect()`/`login()` (retry + reload).
- Reading a **screenshot** (`page.screenshot`) is the most reliable way to map order-grid values to day columns (the grid's innerText collapses empty cells).

## Manual fallback (if the bundled script is missing)

Log in by: `goto` `https://orderonotto.ca/login.php` → fill `#mat-input-0` (email) / `#mat-input-1`
(password) → click `button:has-text("LOG IN")` → wait in a loop until `document.body.innerText`
contains `Product`/`F.O.`, reloading `/ordering-hub/routes` if still blank after ~12s. Then navigate
and read/download. Full nav mechanics: see the `orderonotto-ordering` skill.

## Working examples

Live, scheduled versions built on this client are in the RouteSalesTracker repo
(`akshaykumar09081993/routeSalesTracker`, cloned at `~/Documents/claude/otto-dashboard`):
`agents/otto/dl_catalog.js` (catalog + tray factors), `dl_promotions.js`, `dl_costco_programs.js`,
`dl_statements.js`, plus `agents/otto/README.md` for wiring an agent into the launchd schedule via
`agents/orchestrator.py`.
