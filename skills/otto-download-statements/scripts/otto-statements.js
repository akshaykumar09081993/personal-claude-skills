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

// Payment date for a weekly statement:
//   statement week ENDS Saturday -> generated Sunday -> payment received the NEXT Friday
//   = week-ending Saturday + 6 days.
function paymentDate(weekEndingISO) {
  const d = new Date(weekEndingISO + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + 6);
  return d.toISOString().slice(0, 10);
}

// Predicate: should we download the statement whose week ENDS on `wk` (YYYY-MM-DD)?
function makeWantWeek(opts) {
  if (opts.all) return () => true;
  if (opts.from || opts.to) {
    const lo = opts.from || '0000-00-00', hi = opts.to || '9999-99-99';
    return wk => wk >= lo && wk <= hi; // explicit window is on the week-ending date
  }
  if (opts.paidMonth && opts.paidMonth !== true) {
    return wk => paymentDate(wk).slice(0, 7) === opts.paidMonth; // payment lands in that month
  }
  return () => true;
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
  const wantWeek = makeWantWeek(opts);
  const outDir = (opts.out && opts.out !== true) ? opts.out.replace(/^~/, os.homedir()) : defaultOutDir(opts.paidMonth);
  fs.mkdirSync(outDir, { recursive: true });

  const URL = process.env.OTTO_URL || 'https://orderonotto.ca/login.php';
  const manifest = { outDir, paidMonth: opts.paidMonth || null, downloaded: [], skipped: [], errors: [] };

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

    // The page shows ONE week at a time via the "Week Ending" mat-select (nth 1; Route # is nth 0).
    // Selecting a week + "View Reports" lists that week's PDF links (direct tokenized URLs).
    // IMPORTANT: reload /statements BEFORE each week — switching weeks without a reload leaves stale
    // links in the DOM and can serve the wrong (prior-year) file. Enumerate weeks first, then loop.
    const weekSel0 = p.locator('mat-select').nth(1);
    await weekSel0.click().catch(() => {});
    await p.waitForTimeout(1200);
    let weeks = (await p.locator('mat-option').allInnerTexts().catch(() => []))
      .map(s => s.trim()).filter(s => /^\d{4}-\d{2}-\d{2}$/.test(s));
    weeks = [...new Set(weeks)];
    await p.keyboard.press('Escape').catch(() => {});
    await p.waitForTimeout(400);
    manifest.weeksAvailable = weeks;

    const targets = weeks.filter(wantWeek);
    manifest.weeksSelected = targets.map(w => ({ weekEnding: w, paid: paymentDate(w) }));
    for (const w of weeks) if (!wantWeek(w)) manifest.skipped.push({ week: w, paid: paymentDate(w), reason: 'payment not in target month' });

    const tokenFileKey = href => { // decode the JWT payload in ?token= to verify what OTTO will serve
      try { const t = new URL(href).searchParams.get('token'); let s = t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; return JSON.parse(Buffer.from(s, 'base64').toString('utf8')).fileKey || ''; } catch (_) { return ''; }
    };

    for (const wk of targets) {
      try {
        await p.goto('https://orderonotto.ca/statements', { waitUntil: 'networkidle', timeout: 30000 });
        for (let i = 0; i < 8; i++) { await p.waitForTimeout(1500); if (await has('Available Statements')) break; }
        const weekSel = p.locator('mat-select').nth(1);
        await weekSel.click(); await p.waitForTimeout(1400);
        await p.locator('mat-option').filter({ hasText: new RegExp('^\\s*' + wk + '\\s*$') }).first().click();
        await p.waitForTimeout(1200);
        await p.click('button:has-text("View Reports")').catch(() => {});
        for (let i = 0; i < 8; i++) { await p.waitForTimeout(1300); if (await p.locator(`a:has-text("${wk}")`).count().catch(() => 0)) break; }

        const links = await p.$$eval('a', els => els.map(a => ({
          text: (a.innerText || '').trim().replace(/\s+/g, ' '), href: a.href || ''
        })).filter(a => /get-file|\.pdf/i.test(a.href))).catch(() => []);
        // ONLY the "Distributor Weekly Statement" file for THIS week (skip Revenue_Route / Route_Activity).
        const wkLinks = links.filter(l => l.text.includes(wk) && /Distributor Weekly Statement/i.test(l.text));
        if (!wkLinks.length) { manifest.errors.push({ week: wk, error: 'no Distributor Weekly Statement link found' }); continue; }
        for (const l of wkLinks) {
          const served = tokenFileKey(l.href);
          if (served && !served.includes(wk)) { manifest.errors.push({ week: wk, error: 'served wrong file: ' + served }); continue; }
          let name = l.text.replace(/[\/\\]/g, '-');
          if (!/\.pdf$/i.test(name)) name += '.pdf';
          const dest = path.join(outDir, name);
          const resp = await ctx.request.get(l.href);
          const buf = await resp.body();
          if (buf && buf.slice(0, 4).toString() === '%PDF') { fs.writeFileSync(dest, buf); manifest.downloaded.push({ weekEnding: wk, paid: paymentDate(wk), file: name }); }
          else manifest.errors.push({ week: wk, file: name, error: 'not a PDF (status ' + resp.status() + ')' });
        }
      } catch (e) {
        manifest.errors.push({ week: wk, error: e.message });
      }
    }

    if (!weeks.length) manifest.hint = 'No week options parsed from the Week Ending dropdown. Inspect _statements-page.png / _dom-dump.json and refine the mat-select selector.';
  } catch (e) {
    manifest.fatal = e.message;
  }
  console.log(JSON.stringify(manifest, null, 2));
  await b.close();
})();
