const { chromium } = require('playwright');

const BASE = 'http://localhost:4321/a/water-side-control-valve-selection/carousel';
const OUT = '/Users/marcsir/workspace/ai-xinca/public/articles/slides';

const SLIDES = [
  [1, '01-hook-5-pitfalls'],
  [2, '02-problem-pipe-size'],
  [3, '03-concept-valve-authority'],
  [4, '04-comparison-globe-ball-picv'],
  [5, '05-cta-hydronic-balancing'],
];

(async () => {
  const browser = await chromium.launch();
  for (const [num, name] of SLIDES) {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
    await page.goto(`${BASE}/?slide=${num}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.carousel-panel:not(.hidden)', { timeout: 10000 });
    await page.waitForTimeout(500);
    const panel = await page.$('.carousel-panel:not(.hidden)');
    await panel.screenshot({ path: `${OUT}/${name}.png` });
    console.log(`Saved: ${name}.png`);
    await page.close();
  }
  await browser.close();
  console.log('Done — 5 slides captured');
})();
