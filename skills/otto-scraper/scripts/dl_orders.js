#!/usr/bin/env node
/*
 * dl_orders.js — EXAMPLE agent: export Final Orders (F.O.) for EVERY customer on the route across
 * EVERY selectable week to JSON, verifying each day's column sum against OTTO's on-page "Grand Totals".
 *
 * Demonstrates the ordering-grid helpers in ./otto: waitOrderingHub, listCustomers, listWeeks,
 * selectCustomer, selectWeek, setPageSize, collectOrderGrid. Writes OTTO_OUT after every week so a
 * re-run RESUMES (skips store-weeks already captured). A FRESH browser per customer keeps the SPA
 * stable on big stores (200–360 SKUs occasionally stall for minutes but recover).
 *
 *   NODE_PATH=~/Documents/claude/node_modules OTTO_USERNAME=.. OTTO_PASSWORD=.. \
 *   OTTO_OUT=./otto-orders.json node dl_orders.js
 *
 * Turn the JSON into a spreadsheet downstream (e.g. Python openpyxl) — one row per
 * store×week×product with the 7 day columns + week total, plus a verification sheet.
 */
const otto = require('./otto');
const fs = require('fs');

const OUT = process.env.OTTO_OUT || './otto-orders.json';
const log = (...a) => console.error(new Date().toISOString().slice(11, 19), ...a);

async function processCustomer(cust, weeks, doneWeeks, onRecord) {
  const { browser, page, has } = await otto.connect();
  try {
    if (!(await otto.waitOrderingHub(page, has))) { log('  hub not ready'); return; }
    if (!(await otto.selectCustomer(page, cust.id))) { log('  !! customer not selectable'); return; }
    for (let i = 0; i < 12; i++) { await page.waitForTimeout(1600); if (await has('S.O.') || await has('F.O.')) break; }
    await otto.setPageSize(page, 35);
    for (const wk of weeks) {
      if (doneWeeks.has(wk)) continue;
      try {
        if (!(await otto.selectWeek(page, wk))) { log('  week', wk, 'select failed'); continue; }
        const g = await otto.collectOrderGrid(page, wk);
        if (!g.products.length) { log('  week', wk, 'no products'); continue; }
        const colSums = [0, 0, 0, 0, 0, 0, 0];
        for (const p of g.products) p.fo.forEach((v, i) => colSums[i] += v);
        const gd = g.grandDays && g.grandDays.length ? g.grandDays : colSums.map(() => null);
        const mism = colSums.map((s, i) => ({ day: g.days[i], colSum: s, grandTotal: gd[i] }))
          .filter(x => x.grandTotal !== null && x.colSum !== x.grandTotal);
        onRecord({ customerId: cust.id, customerName: cust.name, week: g.week, days: g.days,
          products: g.products, grandDays: g.grandDays, verify: { colSums, ok: mism.length === 0, mismatches: mism } });
        doneWeeks.add(wk);
        log(`  week ${g.week}: ${g.products.length} products, ${mism.length === 0 ? 'OK' : 'MISMATCH ' + JSON.stringify(mism)}`);
      } catch (e) { log('  week', wk, 'ERROR', e.message); await otto.clearOverlays(page); }
    }
  } finally { await browser.close().catch(() => {}); }
}

(async () => {
  const data = { route: null, capturedAt: new Date().toISOString(), customers: [], weeks: [], records: [] };
  const done = new Map();
  if (fs.existsSync(OUT)) {
    try { const p = JSON.parse(fs.readFileSync(OUT, 'utf8'));
      if (p.records) { data.records = p.records; data.capturedAt = p.capturedAt || data.capturedAt;
        for (const r of p.records) { if (!done.has(r.customerId)) done.set(r.customerId, new Set()); done.get(r.customerId).add(r.week); }
        log('resume:', data.records.length, 'existing records'); }
    } catch { log('resume: bad OUT, starting fresh'); }
  }
  const save = () => fs.writeFileSync(OUT, JSON.stringify(data, null, 2));

  // bootstrap: one session to enumerate route / customers / weeks
  { const { browser, page, has } = await otto.connect();
    try { await otto.waitOrderingHub(page, has);
      data.route = (await page.locator('mat-select').nth(0).innerText().catch(() => '')).trim();
      data.customers = await otto.listCustomers(page);
      data.weeks = await otto.listWeeks(page);
    } finally { await browser.close().catch(() => {}); } }
  log('route', data.route, '| customers', data.customers.length, '| weeks', data.weeks.join(','));
  save();

  for (const cust of data.customers) {
    const dw = done.get(cust.id) || new Set();
    if (data.weeks.every(w => dw.has(w))) { log('CUSTOMER', cust.id, cust.name, '— done, skip'); continue; }
    log('CUSTOMER', cust.id, cust.name, `(${data.weeks.filter(w => !dw.has(w)).length} weeks)`);
    try { await processCustomer(cust, data.weeks, dw, r => { data.records.push(r); save(); }); }
    catch (e) { log('  CUSTOMER', cust.id, 'FAILED', e.message); }
  }
  log('DONE. records:', data.records.length);
  save();
})();
