/**
 * dl_template.js — COPY THIS to start a new OTTO scraping agent.
 *
 * The shared client (./otto) handles credentials, browser launch, login (with the SPA blank-render
 * retry) and PDF downloading — so you only write the part unique to your job.
 *
 * 1) cp dl_template.js dl_myjob.js
 * 2) change the dataDir name, the goto() target, and the "DO YOUR JOB HERE" block
 * 3) run:  NODE_PATH=~/Documents/claude/node_modules node dl_myjob.js
 */
const otto = require('./otto');
const fs = require('fs'), path = require('path');

(async () => {
  const OUT = otto.dataDir('template');            // -> ./data/template/ (change this)
  let result = { saved: [], error: null };
  let browser;
  try {
    // 1) launch + log in
    const { browser: b, ctx, page, has } = await otto.connect();
    browser = b;

    // 2) navigate to the page you need and wait for it to paint
    //    ('useful-information' | 'statements' | 'reporting' | 'ordering-hub/routes')
    await otto.goto(page, has, 'useful-information', ['Collections', 'Show More', 'Product']);

    // 3) ===== DO YOUR JOB HERE =====
    //    a) download matching PDFs:
    result.saved = await otto.downloadPdfLinks(ctx, page, {
      match: /Atlantic Promotions|What.?s In Store/i,
      outDir: OUT,
    });
    //    b) OR scrape the DOM into JSON:
    //    const rows = await page.evaluate(() => { /* read document, return array */ return []; });
    //    fs.writeFileSync(path.join(OUT, 'data.json'), JSON.stringify({ rows }));

  } catch (e) {
    result.error = e.message;
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }
  console.log(JSON.stringify(result));
  console.log('DONE');
})();
