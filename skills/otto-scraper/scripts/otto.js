/**
 * otto.js — reusable OTTO (orderonotto.ca) scraping client for building new automated agents.
 *
 * OTTO is an Angular Material SPA, so it MUST be driven with a real browser (Playwright/Chromium);
 * raw HTTP returns an empty shell. This module owns the parts every scraper repeats — credentials,
 * browser launch, the login flow (with the SPA's intermittent blank-render retry), navigation and
 * PDF downloading — so a new agent only writes the bit unique to its job. See dl_template.js.
 *
 * Usage:
 *   const otto = require('./otto');
 *   (async () => {
 *     const { browser, ctx, page, has } = await otto.connect();      // launch + log in
 *     await otto.goto(page, has, 'useful-information', 'Collections');// navigate + wait
 *     const saved = await otto.downloadPdfLinks(ctx, page, {          // scrape
 *       match: /Atlantic Promotions/i, outDir: otto.dataDir('promos') });
 *     console.log('saved', saved.length);
 *     await browser.close();
 *   })();
 *
 * Credentials: ~/.config/otto/credentials.json ({username,password}), or env OTTO_USERNAME /
 * OTTO_PASSWORD (env wins). Never commit them. Output dir root = env OTTO_DATA_DIR, else ./data.
 * Run node with `playwright` on the module path (e.g. NODE_PATH=~/Documents/claude/node_modules).
 */
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), os = require('os');

const HOME = os.homedir();
const BASE = 'https://orderonotto.ca';
const CRED_PATH = path.join(HOME, '.config/otto/credentials.json');
const DATA_ROOT = process.env.OTTO_DATA_DIR || path.join(process.cwd(), 'data');

/** Read OTTO credentials (env vars win over the JSON file). Never commit these. */
function readCredentials() {
  if (process.env.OTTO_USERNAME && process.env.OTTO_PASSWORD)
    return { username: process.env.OTTO_USERNAME, password: process.env.OTTO_PASSWORD };
  const c = JSON.parse(fs.readFileSync(CRED_PATH, 'utf8'));
  if (!c.username || !c.password) throw new Error('OTTO credentials missing username/password');
  return c;
}

/** Resolve (and create) an output subfolder under OTTO_DATA_DIR (or ./data), e.g. dataDir('promos'). */
function dataDir(name) {
  const d = path.join(DATA_ROOT, name);
  fs.mkdirSync(d, { recursive: true });
  return d;
}

/** Launch Chromium + a download-enabled context + a page, and log in. Returns {browser,ctx,page,has}. */
async function connect(opts = {}) {
  const creds = opts.creds || readCredentials();
  const browser = await chromium.launch({
    headless: opts.headless !== false,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const ctx = await browser.newContext({
    viewport: { width: opts.width || 1700, height: opts.height || 1150 },
    acceptDownloads: true,
  });
  const page = await ctx.newPage();
  const has = s => page.evaluate(t => document.body.innerText.includes(t), s).catch(() => false);
  if (!(await login(page, has, creds))) throw new Error('OTTO login did not reach the app (blank render / bad creds)');
  return { browser, ctx, page, has };
}

/** Log in on an existing page. Handles the SPA blank render (waits for content, reloads once). */
async function login(page, has, creds) {
  await page.goto(`${BASE}/login.php`, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
  await page.fill('#mat-input-0', creds.username);
  await page.fill('#mat-input-1', creds.password);
  await page.click('button:has-text("LOG IN")');
  for (let i = 0; i < 16; i++) {
    await page.waitForTimeout(2000);
    if (await has('Route') || await has('Product') || await has('F.O.')) return true;
    if (i === 6) await page.goto(`${BASE}/ordering-hub/routes`, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
  }
  return false;
}

/** Navigate to an OTTO route and wait until it paints. waitText = string or array (any match = ready). */
async function goto(page, has, urlPath, waitText, opts = {}) {
  await page.goto(`${BASE}/${String(urlPath).replace(/^\//, '')}`,
    { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  const marks = (Array.isArray(waitText) ? waitText : [waitText]).filter(Boolean);
  for (let i = 0; i < (opts.tries || 12); i++) {
    await page.waitForTimeout(opts.interval || 1500);
    if (!marks.length) return true;
    for (const m of marks) if (await has(m)) return true;
  }
  return !marks.length;
}

/**
 * Download every <a> whose text matches `match` (RegExp) as a PDF into `outDir`; dedupe by
 * filename; returns the newly-saved filenames. nameFn(link) -> custom filename (optional).
 */
async function downloadPdfLinks(ctx, page, { match, outDir, nameFn }) {
  const links = await page.$$eval('a', as => as.map(a => ({ text: (a.textContent || '').trim(), href: a.href })));
  const want = links.filter(l => l.href && match.test(l.text));
  const saved = [];
  for (const l of want) {
    const fname = nameFn ? nameFn(l)
      : l.text.replace(/[\/\\]/g, '-').replace(/\s+/g, '_').replace(/\|.*/, '').slice(0, 80) + '.pdf';
    const dest = path.join(outDir, fname);
    if (fs.existsSync(dest)) continue;
    try {
      const r = await ctx.request.get(l.href);
      const buf = await r.body();
      if (buf && buf.slice(0, 4).toString() === '%PDF') { fs.writeFileSync(dest, buf); saved.push(fname); }
    } catch (e) { /* skip a bad link, keep going */ }
  }
  return saved;
}

// ============================= Ordering grid =============================
// The ordering-hub grid is NOT an HTML <table>; it is an Angular <hub-table> of divs. Each product is
// a `.row` whose DIRECT children are 17 columns: [details, 7 day-cells (selected week), week-total,
// 7 day-cells (next week), week-total]. Inside a day cell: F.O. = `.cell.fo span`, S.O. = `.cell.so`,
// ADJ = `.cell.adj`. Selecting week N shows N and N+1 side-by-side — read the FIRST 7 days (week N).
// The grid PAGINATES (10/page; size options 5/10/25/35) so you MUST walk pages to see every product.
// The bottom `.row.subline.totals` ("Grand Totals") gives the per-day F.O. total across ALL products
// on ALL pages — use it to verify: Σ product.fo[d] over all products should equal grandDays[d].
//
// Angular Material overlays leave a `.cdk-overlay-backdrop` that intercepts pointer events, so every
// click here is force:true and clearOverlays() strips the backdrops between actions. login() returns
// as soon as the app text paints, BEFORE the controls are interactive — call waitOrderingHub() first.

/** Remove CDK overlay backdrops (they intercept clicks) and close any open panel. */
async function clearOverlays(page) {
  await page.keyboard.press('Escape').catch(() => {});
  await page.evaluate(() => document.querySelectorAll('.cdk-overlay-backdrop').forEach(b => b.remove())).catch(() => {});
  await page.waitForTimeout(200);
}

/** Wait until the ordering-hub controls are actually interactive (connect() returns before this). */
async function waitOrderingHub(page, has, tries = 15) {
  for (let i = 0; i < tries; i++) {
    await page.waitForTimeout(1500);
    if ((await has('Customers')) && (await page.locator('mat-select').count()) >= 2) return true;
  }
  return false;
}

/** Every customer on the current route — the Customers autocomplete lists them all when empty. */
async function listCustomers(page) {
  const ci = page.locator('mat-form-field:has-text("Customers") input').first();
  let out = [];
  for (let attempt = 0; attempt < 6 && out.length === 0; attempt++) {
    await clearOverlays(page);
    await ci.click({ force: true }); await ci.fill(''); await page.waitForTimeout(1800);
    out = await page.evaluate(() => [...document.querySelectorAll('mat-option')].map(o => {
      const l = o.innerText.split('\n').map(s => s.trim()).filter(Boolean);
      return { id: l[0] || '', name: l[1] || '', addr: l[2] || '' };
    }));
    if (!out.length) await page.waitForTimeout(1500);
  }
  await page.keyboard.press('Escape').catch(() => {});
  return out;
}

/** Select a customer by its id/number in the Customers autocomplete. Returns true on success. */
async function selectCustomer(page, id) {
  const ci = page.locator('mat-form-field:has-text("Customers") input').first();
  for (let attempt = 0; attempt < 5; attempt++) {
    await clearOverlays(page);
    await ci.click({ force: true }); await ci.fill(''); await page.waitForTimeout(900);
    await ci.type(String(id), { delay: 40 }); await page.waitForTimeout(1800);
    const opt = page.locator('mat-option').filter({ hasText: String(id) }).first();
    if (await opt.count()) { await opt.click({ force: true }); await clearOverlays(page); return true; }
    await page.waitForTimeout(1500);
  }
  return false;
}

/** Week numbers in the Week dropdown (rolling ~12-week window), '(Current)' stripped. */
async function listWeeks(page) {
  await clearOverlays(page);
  await page.locator('mat-select').nth(1).click({ force: true }); await page.waitForTimeout(700);
  const raw = await page.evaluate(() => [...document.querySelectorAll('mat-option')].map(o => o.innerText.trim()));
  await page.keyboard.press('Escape').catch(() => {});
  return raw.map(w => w.replace(/\s*\(Current\)\s*/, '').trim());
}

/** Select a week number (Week = mat-select nth 1; Route = nth 0; page-size = nth 2). Returns bool. */
async function selectWeek(page, wk) {
  await clearOverlays(page);
  await page.locator('mat-select').nth(1).click({ force: true }); await page.waitForTimeout(800);
  const opt = page.locator('mat-option').filter({ hasText: new RegExp('^\\s*' + wk + '( \\(Current\\))?\\s*$') }).first();
  if (await opt.count()) { await opt.click({ force: true }); await page.waitForTimeout(3500); await clearOverlays(page); return true; }
  await clearOverlays(page); return false;
}

/** Set the paginator "items per page" (options 5/10/25/35). Fewer pages, but still paginate. */
async function setPageSize(page, n) {
  await clearOverlays(page);
  const sel = page.locator('mat-select').nth(2);
  if (!(await sel.count())) return;
  await sel.click({ force: true }); await page.waitForTimeout(600);
  const opt = page.locator('mat-option').filter({ hasText: new RegExp('^\\s*' + n + '\\s*$') }).first();
  if (await opt.count()) { await opt.click({ force: true }); await page.waitForTimeout(1800); }
  await clearOverlays(page);
}

/**
 * Read the CURRENT grid page for the selected week block. Returns
 * { week, days:[7 "Mmm-D Ddd"], products:[{name,sku,rtn4wk,tf,fo:[7],so:[7],weekTotalFO}],
 *   grandDays:[7], pageInfo:{from,to,total} }.
 */
function readGridPage(page) {
  return page.evaluate(() => {
    const num = t => { const m = (t || '').replace(/,/g, '').match(/-?\d+(\.\d+)?/); return m ? parseFloat(m[0]) : 0; };
    const ht = document.querySelector('hub-table');
    if (!ht) return { error: 'no hub-table' };
    const dayHdr = [...new Set([...ht.querySelectorAll('*')].map(e => ((e.childElementCount === 0 && e.innerText) || '').trim())
      .filter(t => /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d+ (Sun|Mon|Tue|Wed|Thu|Fri|Sat)$/.test(t)))];
    const days = dayHdr.slice(0, 7);
    const wkM = ht.innerText.match(/Week\s+(\d+)\s+Totals/); const week = wkM ? wkM[1] : null;
    const foOf = c => { const s = c.querySelector('.cell.fo span'); return s ? num(s.innerText) : 0; };
    const soOf = c => { const so = c.querySelector('.cell.so'); if (!so) return 0; const i = so.querySelector('input'); if (i) return num(i.value); const s = so.querySelector('span'); return s ? num(s.innerText) : 0; };
    const rows = [...ht.querySelectorAll('.row')].filter(r => r.querySelector('.details') && !r.classList.contains('subline'));
    const products = [];
    for (const r of rows) {
      const cols = [...r.children], det = cols[0];
      const nameSpan = det.querySelector('.value span'), skuP = det.querySelector('.value p');
      const rtn = det.querySelector('.wrr .value span'), tf = det.querySelector('.tray_factor');
      const dayCells = cols.slice(1).filter(c => c.classList.contains('day') && !c.classList.contains('totals')).slice(0, 7);
      const fo = dayCells.map(foOf), so = dayCells.map(soOf);
      const tot = cols.slice(1).find(c => c.classList.contains('totals'));
      products.push({ name: nameSpan ? nameSpan.innerText.trim() : '', sku: skuP ? skuP.innerText.trim() : '',
        rtn4wk: rtn ? rtn.innerText.trim() : '', tf: tf ? tf.innerText.trim() : '',
        fo, so, weekTotalFO: tot ? foOf(tot) : fo.reduce((a, x) => a + x, 0) });
    }
    const gt = [...ht.querySelectorAll('.row.subline.totals')].find(r => /Grand Totals/.test(r.innerText));
    const grandDays = gt ? [...gt.children].slice(1, 8).map(c => num(c.innerText)) : [];
    let pageInfo = null; const pg = document.querySelector('app-paginator');
    if (pg) { const m = (pg.innerText || '').replace(/\s+/g, ' ').match(/(\d+)\s*-\s*(\d+)\s*of\s*(\d+)/i); if (m) pageInfo = { from: +m[1], to: +m[2], total: +m[3] }; }
    return { week, days, products, grandDays, pageInfo };
  });
}

/**
 * Collect EVERY product for the selected week by walking the paginator (resets to page 1 first).
 * Call selectWeek(page, wk) before this. Returns { week, days, products, grandDays }.
 * Verify: for each day d, Σ product.fo[d] over products === grandDays[d].
 */
async function collectOrderGrid(page, wk) {
  await clearOverlays(page);
  let first = page.locator('app-paginator button').filter({ has: page.locator('mat-icon', { hasText: 'first_page' }) }).first();
  if (!(await first.count())) first = page.locator('app-paginator button').nth(0);
  if (await first.count() && await first.isEnabled().catch(() => false)) { await first.click({ force: true, noWaitAfter: true }); await page.waitForTimeout(1200); }
  const all = [], seen = new Set(); let grandDays = null, days = null, week = null;
  for (let guard = 0; guard < 14; guard++) {
    let g = null;
    for (let a = 0; a < 3; a++) { await page.waitForTimeout(1000); g = await readGridPage(page); if (g && g.week === String(wk) && g.products && g.products.length) break; }
    if (!g || g.error) break;
    week = g.week; days = g.days; if (!grandDays) grandDays = g.grandDays;
    for (const pr of g.products) { const k = pr.name + '|' + pr.sku; if (!seen.has(k)) { seen.add(k); all.push(pr); } }
    const pi = g.pageInfo; if (!pi || pi.to >= pi.total) break;
    // next page — noWaitAfter:true or Playwright hangs on the SPA's post-click nav-wait
    await clearOverlays(page);
    let nxt = page.locator('app-paginator button').filter({ has: page.locator('mat-icon', { hasText: 'chevron_right' }) }).first();
    if (!(await nxt.count())) nxt = page.locator('app-paginator button').nth(2);
    await nxt.click({ force: true, noWaitAfter: true }); await page.waitForTimeout(1500);
  }
  return { week, days, products: all, grandDays };
}

module.exports = {
  BASE, readCredentials, dataDir, connect, login, goto, downloadPdfLinks,
  // ordering grid
  clearOverlays, waitOrderingHub, listCustomers, selectCustomer, listWeeks, selectWeek,
  setPageSize, readGridPage, collectOrderGrid,
};
