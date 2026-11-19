// Prints the board HTML to PDF and saves small previews of the first, a middle and the last page.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [html, pdf] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 905 } });
  await page.goto('file://' + html);
  await page.waitForTimeout(500);
  await page.pdf({ path: pdf, width: '1280px', height: '905px', printBackground: true, margin: { top: '0', bottom: '0', left: '0', right: '0' } });
  const pages = await page.$$('.page');
  const want = [...new Set([0, Math.floor(pages.length / 2), pages.length - 1])].filter(i => i >= 0 && i < pages.length);
  const out = [];
  const base = pdf.replace(/\.pdf$/, '');
  for (const i of want) {
    const p = `${base}-p${String(i + 1).padStart(2, '0')}.jpg`;
    await pages[i].screenshot({ path: p, type: 'jpeg', quality: 60 });
    out.push(p);
  }
  await browser.close();
  console.log(JSON.stringify(out));
})().catch(e => { console.error(String(e)); process.exit(1); });
