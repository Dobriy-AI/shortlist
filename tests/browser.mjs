import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:5420';
const server = process.env.TEST_BASE_URL ? null : spawn(process.execPath, ['scripts/serve.mjs'], { env: { ...process.env, PORT: '5420' }, stdio: 'inherit' });
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 40; attempt++) {
    try { if ((await fetch(base)).ok) { ready = true; break; } } catch {}
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  assert(ready, 'Preview must be reachable');
  await mkdir('artifacts', { recursive: true });
  browser = await chromium.launch({ headless: true });
  const results = [];
  for (const width of [1440, 1024, 768, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(base, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator('.source-card:visible').count(), 6);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No horizontal overflow at ${width}px`);
    assert(await page.evaluate(() => document.fonts.check('400 16px Poppins')), 'Local Poppins must load');
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    assert.deepEqual(accessibility.violations.map(({ id, nodes }) => ({ id, targets: nodes.map((node) => node.target) })), [], `Accessibility at ${width}px`);
    await page.screenshot({ path: `artifacts/landing-${width}.png`, fullPage: true });
    await page.getByLabel('Search funding sources').fill('Austria');
    assert.equal(await page.locator('.source-card:visible').count(), 3);
    await page.locator('label').filter({ has: page.locator('input[value="research"]') }).click();
    assert.equal(await page.locator('.source-card:visible').count(), 2);
    await page.getByLabel('Search funding sources').fill('no-such-funding-source');
    assert.equal(await page.locator('.source-card:visible').count(), 0);
    assert(await page.getByRole('heading', { name: 'No sources match yet.' }).isVisible());
    await page.getByRole('button', { name: 'Show all sources' }).click();
    assert.equal(await page.locator('.source-card:visible').count(), 6);
    assert.equal(await page.locator('#source-search').evaluate((node) => node === document.activeElement), true);
    await page.locator('summary').first().click();
    assert(await page.locator('details').first().evaluate((node) => node.open));
    if (width <= 600) {
      await page.getByRole('button', { name: 'Menu' }).click();
      assert.equal(await page.getByRole('button', { name: 'Menu' }).getAttribute('aria-expanded'), 'true');
      assert(await page.getByRole('navigation', { name: 'Main navigation' }).isVisible());
      await page.keyboard.press('Escape');
      assert.equal(await page.getByRole('button', { name: 'Menu' }).getAttribute('aria-expanded'), 'false');
      assert.equal(await page.getByRole('button', { name: 'Menu' }).evaluate((node) => node === document.activeElement), true);
      await page.getByRole('button', { name: 'Menu' }).click();
      await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Funding sources' }).click();
      assert.equal(await page.getByRole('button', { name: 'Menu' }).getAttribute('aria-expanded'), 'false');
    }
    assert.deepEqual(errors, []);
    results.push({ width, accessibilityViolations: 0, filters: 'passed', navigation: 'passed', overflow: false });
    await context.close();
  }
  const fallback = await browser.newPage({ javaScriptEnabled: false, viewport: { width: 320, height: 900 } });
  await fallback.goto(base);
  assert.equal(await fallback.locator('.source-card:visible').count(), 6);
  assert(await fallback.getByRole('navigation', { name: 'Main navigation' }).isVisible());
  assert.equal(await fallback.locator('.source-controls:visible').count(), 0);
  assert(await fallback.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await fallback.close();
  await writeFile('artifacts/browser-results.json', JSON.stringify({ base, results, withoutJavaScript: 'passed' }, null, 2) + '\n');
  console.log('Passed: five screen widths, accessibility, local fonts, filtering, empty state, mobile navigation and no-JavaScript fallback.');
} finally {
  await browser?.close();
  server?.kill('SIGTERM');
}
