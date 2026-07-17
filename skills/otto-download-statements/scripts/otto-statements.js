#!/usr/bin/env node
/**
 * otto-statements.js — log into the OTTO portal (orderonotto.ca), open STATEMENTS,
 * and download the weekly "Distributor Weekly Statement" PDFs into the bookkeeping folder.
 *
 * OTTO is an Angular Material SPA — it MUST be driven with a real browser (Playwright/Chromium).
 * Login mechanics are shared with the `orderonotto-ordering` skill.
 *
 * Requires Playwright:
 *   npm i playwright && npx playwright install chromium
 *
 * Credentials come from env (NEVER hardcode / commit):
 *   OTTO_USERNAME, OTTO_PASSWORD   (required)
 *   OTTO_URL                       (optional, default https://orderonotto.ca/login.php)
 * If env is unset, the script also looks for ~/.config/otto/credentials.json  {"username","password"}.
 *
 * Usage examples:
 *   OTTO_USERNAME=... OTTO_PASSWORD=... node otto-statements.js --paid-month 2026-06
 *   node otto-statements.js --from 2026-05-01 --to 2026-06-30 --out ~/Documents/bookeeping/2026/June/Checking
 *   node otto-statements.js --all --out /tmp/statements     # grab everything OTTO retains (~52 wks)
 *
 * Selection:
 *   --paid-month YYYY-MM   payments received that month. Bimbo settles weekly on a lag, and (per the
 *                          user) "the statement generated last in the previous month" is the one paid
 *                          early this month. So this downloads every weekly statement whose week-ENDING
 *                          date falls in [previous-month-start .. paid-month-end] (tune with --lag-weeks).
 *   --from / --to YYYY-MM-DD   explicit week-ending date window (overrides --paid-month).
 *   --all                  download every statement listed.
 *   --lag-weeks N          widen the window N extra weeks earlier (default 0).
 *   --route 1702           route filter for the filename/label (default 1702).
 *   --out DIR              output dir. Default: ~/Documents/bookeeping/<year>/<Month>/Checking
 *                          derived from --paid-month (matches the user's existing folder layout).
 *   --headful              show the browser (debugging).
 *
 * Output: saves PDFs named like the OTTO originals
 *   "Distributor Weekly Statement Route 1702 From YYYY-MM-DD To YYYY-MM-DD.pdf"
 * and prints a JSON manifest of everything downloaded + skipped.
 *
 * NOTE: the /statements DOM (exact row/link/button selectors) was NOT verified against a live login
 * when this was authored. The script tries several strategies and, on first run, ALWAYS writes a
 * screenshot + a dump of candidate elements to the out dir (_statements-page.png / _dom-dump.json) so
 * you can confirm/refine the selectors. If nothing downloads, read those two files first.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  if (i < 0) return def;
  const nx = process.argv[i + 1];
  return (!nx || nx.startsWith('--')) ? true : nx; // bare flag => true
}

function creds() {
  let u = process.env.OTTO_USERNAME, p = process.env.OTTO_PASSWORD;
  if (!u || !p) {
    try {
      const f = path.join(os.homedir(), '.config', 'otto', 'credentials.json');
      const j = JSON.parse(fs.readFileSync(f, 'utf8'));
      u = u || j.username; p = p || j.password;
    } catch (_) {}
  }
  return { u, p };
}

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function defaultOutDir(paidMonth) {
  // paidMonth = 'YYYY-MM' -> ~/Documents/bookeeping/YYYY/<Month>/Checking
  const home = os.homedir();
  if (!paidMonth || paidMonth === true) return path.join('/tmp', 'otto-statements');
  const [y, m] = paidMonth.split('-').map(Number);
  return path.join(home, 'Documents', 'bookeeping', String(y), MONTHS[m - 1], 'Checking');
}

// window of week-ending dates to accept
function windowFor(opts) {
  if (opts.from || opts.to) return { from: opts.from || '0000-00-00', to: opts.to || '9999-99-99' };
  if (opts.all) return { from: '0000-00-00', to: '9999-99-99' };
  if (opts.paidMonth && opts.paidMonth !== true) {
    const [y, m] = opts.paidMonth.split('-').map(Number);
    const prev = new Date(Date.UTC(y, m - 1, 1)); // first of previous month
    prev.setUTCMonth(prev.getUTCMonth() - 1);
    prev.setUTCDate(prev.getUTCDate() - 7 * (opts.lagWeeks || 0));
    const end = new Date(Date.UTC(y, m, 0)); // last day of paid month
    const iso = d => d.toISOString().slice(0, 10);
    return { from: iso(prev), to: iso(end) };
  }
  return { from: '0000-00-00', to: '9999-99-99' };
}

const DATE_RE = /(\d{4}-\d{2}-\d{2})\s*(?:-|to|To)\s*(\d{4}-\d{2}-\d{2})/;

(async () => {
  let chromium;
  try { ({ chromium } = require('playwright')); }
  catch (_) { console.error('Playwright not installed. Run: npm i playwright && npx playwright install chromium'); process.exit(2); }

  const { u: USER, p: PASS } = creds();
  if (!USER || !PASS) { console.error('Set OTTO_USERNAME and OTTO_PASSWORD (env or ~/.config/otto/credentials.json).'); process.exit(1); }

  const opts = {
    paidMonth: arg('paid-month'), from: arg('from'), to: arg('to'), all: arg('all') === true,
    lagWeeks: parseInt(arg('lag-weeks', '0'), 10) || 0, route: arg('route', '1702'),
    out: arg('out'), headful: arg('headful') === true,
  };
  const win = windowFor(opts);
  const outDir = (opts.out && opts.out !== true) ? opts.out.replace(/^~/, os.homedir()) : defaultOutDir(opts.paidMonth);
  fs.mkdirSync(outDir, { recursive: true });

  const URL = process.env.OTTO_URL || 'https://orderonotto.ca/login.php';
  const manifest = { outDir, window: win, downloaded: [], skipped: [], errors: [] };

  const b = await chromium.launch({ headless: !opts.headful, args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 1700, height: 1100 }, acceptDownloads: true });
  const p = await ctx.newPage();
  const has = s => p.evaluate(t => document.body.innerText.includes(t), s).catch(() => false);

  try {
    // ---- login (proven flow from orderonotto-ordering) ----
    await p.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
    await p.fill('#mat-input-0', USER);
    await p.fill('#mat-input-1', PASS);
    await p.click('button:has-text("LOG IN")');
    for (let i = 0; i < 14; i++) {
      await p.waitForTimeout(2500);
      if (await has('Product') || await has('F.O.') || await has('REPORTING')) break;
      if (i === 5) await p.goto('https://orderonotto.ca/ordering-hub/routes', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    }

    // ---- go to STATEMENTS ----
    await p.goto('https://orderonotto.ca/statements', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    for (let i = 0; i < 12; i++) {
      await p.waitForTimeout(2000);
      if (await has('Statement') || await has('Weekly') || await has('Distributor')) break;
      if (i === 5) await p.goto('https://orderonotto.ca/statements', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    }

    // always drop debug artifacts (selectors here are unverified — see header note)
    await p.screenshot({ path: path.join(outDir, '_statements-page.png'), fullPage: true }).catch(() => {});
    const dump = await p.evaluate(() => {
      const rows = [];
      document.querySelectorAll('a,button,tr,mat-row,[role="row"]').forEach(el => {
        const t = (el.innerText || '').trim().replace(/\s+/g, ' ');
        const href = el.getAttribute && (el.getAttribute('href') || '');
        if (t && (/statement|distributor|weekly|\d{4}-\d{2}-\d{2}/i.test(t) || /\.pdf/i.test(href)))
          rows.push({ tag: el.tagName, text: t.slice(0, 160), href });
      });
      return rows.slice(0, 400);
    }).catch(() => []);
    fs.writeFileSync(path.join(outDir, '_dom-dump.json'), JSON.stringify(dump, null, 2));

    const inWindow = (from, to) => from >= win.from && from <= win.to || to >= win.from && to <= win.to;
    const safeName = (from, to) => `Distributor Weekly Statement Route ${opts.route} From ${from} To ${to}.pdf`;

    // ---- Strategy A: direct <a> links to PDFs whose text carries the week window ----
    const anchors = await p.$$eval('a', els => els.map(a => ({
      text: (a.innerText || '').trim().replace(/\s+/g, ' '), href: a.href || a.getAttribute('href') || ''
    })).filter(a => a.href && /\.pdf|statement|download/i.test(a.href + ' ' + a.text))).catch(() => []);

    // ---- Strategy B: clickable rows/buttons that fire a download event ----
    const clickables = await p.$$('tr, mat-row, [role="row"], button:has-text("Download"), a:has-text("Download")').catch(() => []);

    // Build a candidate list: {label, from, to, kind, ref}
    const candidates = [];
    for (const a of anchors) {
      const m = (a.text || '').match(DATE_RE) || (a.href || '').match(DATE_RE);
      if (m) candidates.push({ from: m[1], to: m[2], kind: 'anchor', href: a.href, text: a.text });
    }
    for (let i = 0; i < clickables.length; i++) {
      const t = (await clickables[i].innerText().catch(() => '')).replace(/\s+/g, ' ');
      const m = t.match(DATE_RE);
      if (m) candidates.push({ from: m[1], to: m[2], kind: 'click', handle: clickables[i], text: t });
    }

    // de-dupe by (from,to)
    const seen = new Set();
    for (const c of candidates) {
      const key = c.from + '_' + c.to;
      if (seen.has(key)) continue;
      seen.add(key);
      if (!(opts.all || inWindow(c.from, c.to))) { manifest.skipped.push({ from: c.from, to: c.to, reason: 'out of window' }); continue; }
      const dest = path.join(outDir, safeName(c.from, c.to));
      try {
        if (c.kind === 'anchor' && /^https?:/.test(c.href)) {
          // fetch the PDF through the authenticated context
          const resp = await ctx.request.get(c.href);
          const buf = await resp.body();
          if (buf && buf.slice(0, 4).toString() === '%PDF') { fs.writeFileSync(dest, buf); manifest.downloaded.push({ from: c.from, to: c.to, file: dest, via: 'anchor' }); continue; }
        }
        // fall back to a real click that triggers a browser download
        const [dl] = await Promise.all([
          p.waitForEvent('download', { timeout: 15000 }),
          (c.handle ? c.handle.click() : p.click(`a[href="${c.href}"]`)),
        ]);
        await dl.saveAs(dest);
        manifest.downloaded.push({ from: c.from, to: c.to, file: dest, via: 'download-event' });
      } catch (e) {
        manifest.errors.push({ from: c.from, to: c.to, error: e.message });
      }
    }

    manifest.candidatesFound = candidates.length;
    if (!candidates.length) manifest.hint = 'No statements parsed. Inspect _statements-page.png and _dom-dump.json in the out dir and refine selectors.';
  } catch (e) {
    manifest.fatal = e.message;
  }
  console.log(JSON.stringify(manifest, null, 2));
  await b.close();
})();
