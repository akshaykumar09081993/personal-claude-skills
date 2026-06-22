#!/usr/bin/env node
/**
 * otto-fetch.js — log into the OTTO ordering portal (orderonotto.ca) and read the order grid.
 *
 * Requires Playwright (use the llmoperator scraper image, or `npm i playwright` + a Chromium with deps).
 * Credentials come from env — NEVER hardcode them:
 *   OTTO_USERNAME, OTTO_PASSWORD   (required)
 *   OTTO_URL                       (optional, default https://orderonotto.ca/login.php)
 *
 * Usage:
 *   OTTO_USERNAME=... OTTO_PASSWORD=... node otto-fetch.js \
 *     --customer "Walmart" --week 26 --product "HAMBURGER WHITE 8PK" --out /tmp/otto.png
 *
 * Args (all optional except creds):
 *   --customer <text>   search term typed into the Customers autocomplete (picks first match)
 *   --week <n>          week number to select (e.g. 26); omit to keep current
 *   --product <text>    text typed into the Filter/Search box to narrow the grid
 *   --out <path>        screenshot path (default /tmp/otto.png)
 *
 * Prints JSON: { customer, weekDays, productBlock } and saves a screenshot (read the screenshot for
 * reliable day↔value mapping — the grid's innerText collapses empty cells).
 */
const { chromium } = require('playwright');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

(async () => {
  const URL = process.env.OTTO_URL || 'https://orderonotto.ca/login.php';
  const USER = process.env.OTTO_USERNAME, PASS = process.env.OTTO_PASSWORD;
  if (!USER || !PASS) { console.error('Set OTTO_USERNAME and OTTO_PASSWORD env vars.'); process.exit(1); }
  const customer = arg('customer'), week = arg('week'), product = arg('product'), out = arg('out', '/tmp/otto.png');

  const b = await chromium.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const p = await (await b.newContext({ viewport: { width: 1700, height: 1100 } })).newPage();
  const has = s => p.evaluate(t => document.body.innerText.includes(t), s).catch(() => false);
  const result = {};
  try {
    await p.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
    await p.fill('#mat-input-0', USER);
    await p.fill('#mat-input-1', PASS);
    await p.click('button:has-text("LOG IN")');

    // Robust render wait (SPA sometimes paints blank → reload fallback)
    for (let i = 0; i < 14; i++) {
      await p.waitForTimeout(2500);
      if (await has('Product') || await has('F.O.')) break;
      if (i === 5) await p.goto('https://orderonotto.ca/ordering-hub/routes', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    }

    // Customers = autocomplete input (NOT a mat-select)
    if (customer) {
      const ci = p.locator('mat-form-field:has-text("Customers") input').first();
      await ci.click(); await ci.fill(''); await ci.type(customer, { delay: 60 }); await p.waitForTimeout(2000);
      const opt = p.locator('mat-option').filter({ hasText: new RegExp(customer, 'i') }).first();
      if (await opt.count()) { await opt.click(); for (let i = 0; i < 10; i++) { await p.waitForTimeout(1800); if (await has('Product')) break; } }
      result.customer = await ci.inputValue().catch(() => '?');
    }

    // Week = mat-select nth(1) (Route is nth(0))
    if (week) {
      const wkSel = p.locator('mat-select').nth(1);
      await wkSel.click(); await p.waitForTimeout(900);
      const opt = p.locator('mat-option').filter({ hasText: new RegExp('^\\s*' + week + '( \\(Current\\))?\\s*$') }).first();
      if (await opt.count()) { await opt.click(); await p.waitForTimeout(3500); }
      else { await p.keyboard.press('Escape'); }
    }

    // Filter products
    if (product) {
      const fbox = p.getByPlaceholder(/filter|search/i).first();
      if (await fbox.count()) { await fbox.fill(''); await p.waitForTimeout(400); await fbox.fill(product); await p.waitForTimeout(2500); }
    }

    result.weekDays = await p.evaluate(() =>
      [...new Set([...document.body.innerText.split('\n')].map(s => s.trim())
        .filter(t => /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d+ (Sun|Mon|Tue|Wed|Thu|Fri|Sat)$/.test(t)))].slice(0, 8)
    ).catch(() => []);
    result.productBlock = await p.evaluate((prod) => {
      const L = document.body.innerText.split('\n').map(s => s.trim());
      const i = prod ? L.findIndex(t => new RegExp(prod, 'i').test(t)) : L.findIndex(t => /^DEMPSTER|^VILLAGGIO|^WONDER/i.test(t));
      return i >= 0 ? L.slice(i, i + 40).filter(Boolean) : [];
    }, product || '').catch(() => []);

    await p.screenshot({ path: out, fullPage: false }).catch(() => {});
    result.screenshot = out;
  } catch (e) { result.error = e.message; }
  console.log(JSON.stringify(result, null, 2));
  await b.close();
})();
