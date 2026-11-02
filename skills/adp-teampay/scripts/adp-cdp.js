// Drive the user's REAL Chrome (over CDP on :9222) to log into ADP TeamPay and download PDFs.
// Prereq: run scripts/cdp-chrome.sh first.  NODE_PATH must point at a Playwright install.
//   NODE_PATH=/Users/avu/Documents/Claude/node_modules ADP_USER=.. ADP_PASS=.. \
//     node adp-cdp.js paystubs "<EMPLOYEE NAME OR SEARCH>"
//   node adp-cdp.js reports <YYYY-MM-DD start> <YYYY-MM-DD end>
const { chromium } = require('playwright');
const fs = require('fs');
const MODE = process.argv[2];
const USER = process.env.ADP_USER, PASS = process.env.ADP_PASS;
const OUT = process.env.ADP_OUT || `${process.env.HOME}/Documents/adp-download`;
const isTeamPay = (u) => { try { return new URL(u).hostname === 'teampay.adp.com'; } catch { return false; } };

async function ensureLoggedIn(ctx) {
  let page = ctx.pages().find(p => /adp\.com/.test(p.url())) || ctx.pages()[0] || await ctx.newPage();
  await page.bringToFront(); await page.waitForTimeout(2500);
  if (isTeamPay(page.url())) return page;
  // optional User ID step
  const uf = page.locator('#login-form_username input').first();
  if (await uf.count() && await uf.isVisible().catch(() => false)) {
    await uf.click(); await uf.fill(USER);
    const next = page.locator('#verifUseridBtn, button:has-text("Next")').first();
    if (await next.count()) await next.click();
    await page.waitForTimeout(3000);
  }
  const pf = page.locator('#login-form_password input').first();
  await pf.waitFor({ timeout: 15000 });
  await pf.click(); await pf.fill(''); await pf.pressSequentially(PASS, { delay: 50 });
  await page.locator('#signBtn, button:has-text("Sign in")').first().click();
  for (let i = 0; i < 25; i++) {
    await page.waitForTimeout(1500);
    if (isTeamPay(page.url())) return page;
    const b = (await page.locator('body').innerText().catch(() => '')) || '';
    if (/incorrect|try again/i.test(b)) throw new Error('ADP rejected credentials (check ADP_USER/ADP_PASS; are you on the real-Chrome CDP?)');
    if (/verif|one-time|security question|send.*code/i.test(b)) throw new Error('ADP wants an MFA code — complete it in the Chrome window, then re-run.');
  }
  throw new Error('login timed out at ' + page.url());
}

// Generic dijit-grid downloader: click each row's hyperlink -> Download.aspx popup -> fetch -> save.
async function downloadGrid(ctx, page, gridPrefix, cellIdx, nameFn, filter) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.locator(`#${gridPrefix}_first_link`).click().catch(() => {});
  await page.waitForTimeout(2000);
  const used = new Set(); let saved = 0, pg = 0;
  while (true) {
    pg++;
    const n = await page.locator(`a[id^="${gridPrefix}_row_"][id$="_cell_${cellIdx}_hyperlink"]`).count();
    for (let i = 0; i < n; i++) {
      const cell = async c => (await page.locator(`#${gridPrefix}_row_${i}_cell_${c}`).innerText().catch(() => '')).replace(/\s+/g, ' ').trim();
      if (filter && !(await filter(cell))) continue;
      const link = page.locator(`#${gridPrefix}_row_${i}_cell_${cellIdx}_hyperlink`);
      const [popup] = await Promise.all([ctx.waitForEvent('page', { timeout: 20000 }).catch(() => null), link.click().catch(() => null)]);
      if (!popup) continue;
      let url = popup.url();
      for (let t = 0; t < 20 && !/Download\.aspx/i.test(url); t++) { await popup.waitForTimeout(300); url = popup.url(); }
      if (/Download\.aspx/i.test(url)) {
        const buf = await (await ctx.request.get(url)).body();
        let fn = (await nameFn(cell, i)).replace(/[\/\\:*?"<>|]+/g, '-'); let k = 2;
        while (used.has(fn)) { fn = fn.replace(/\.pdf$/, '') + '_' + (k++) + '.pdf'; }
        used.add(fn); fs.writeFileSync(`${OUT}/${fn}`, buf); saved++;
        console.log('  saved', fn, `(${buf.length}b)`);
      }
      await popup.close().catch(() => {});
      await page.waitForTimeout(250);
    }
    const nextCls = (await page.locator(`#${gridPrefix}_next`).getAttribute('class').catch(() => '')) || '';
    const firstBefore = await page.locator(`#${gridPrefix}_row_0_cell_${cellIdx}`).innerText().catch(() => '');
    if (/disabled/i.test(nextCls)) break;
    await page.locator(`#${gridPrefix}_next_link`).click().catch(() => {});
    let changed = false;
    for (let t = 0; t < 25; t++) { await page.waitForTimeout(400); const now = await page.locator(`#${gridPrefix}_row_0_cell_${cellIdx}`).innerText().catch(() => ''); if (now && now !== firstBefore) { changed = true; break; } }
    if (!changed || pg > 15) break;
  }
  console.log(`DONE: saved ${saved} -> ${OUT}`);
}

(async () => {
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const ctx = browser.contexts()[0];
  const page = await ensureLoggedIn(ctx);
  console.log('logged in:', page.url());

  if (MODE === 'paystubs') {
    const who = process.argv[3];
    await page.locator(`text=${who}`).first().click();          // click employee card
    await page.waitForTimeout(3000);
    await page.locator('text=Pay Statements').first().click();  // Pay Statements tab
    await page.waitForTimeout(4000);
    const G = 'MainContent_tabManageEmployee_emPractitionerPayStatements_payStatementDataGrid';
    await downloadGrid(ctx, page, G, 4, async (cell) => `PayStub_${(await cell(4)).replace(/\//g, '-')}.pdf`);
  } else if (MODE === 'reports') {
    const [start, end] = [process.argv[3], process.argv[4]];
    await page.getByText('View Reports', { exact: true }).first().click({ timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(4500);
    const P = 'MainContent_ucPayrollOutputReports';
    const toDMY = s => { const [y, m, d] = s.split('-'); return `${d}/${m}/${y}`; };
    if (start) { const f = page.locator(`#${P}_txtStartDate`); await f.click(); await f.fill(toDMY(start)); await f.press('Tab'); }
    if (end) { const f = page.locator(`#${P}_txtEndDate`); await f.click(); await f.fill(toDMY(end)); await f.press('Tab'); }
    await page.getByRole('button', { name: /^Filter$/i }).first().click().catch(() => {});
    await page.waitForTimeout(5000);
    await downloadGrid(ctx, page, `${P}_payrollDataGrid`, 0, async (cell) => {
      const t = (await cell(0)), pp = (await cell(4)), fn = (await cell(5)), payee = (await cell(1));
      return `PP${pp}_${fn}_${t}${payee ? '_' + payee : ''}.pdf`;
    });
  } else {
    console.log('usage: node adp-cdp.js paystubs "<name>" | reports <start YYYY-MM-DD> <end YYYY-MM-DD>');
  }
  await browser.close();
})().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
