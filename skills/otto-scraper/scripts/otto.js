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

module.exports = { BASE, readCredentials, dataDir, connect, login, goto, downloadPdfLinks };
