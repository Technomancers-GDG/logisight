import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, channel: undefined });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(2000);
await page.screenshot({ path: 'landing-page-hero.png', fullPage: false });
await page.screenshot({ path: 'landing-page-full.png', fullPage: true });
await browser.close();
console.log('Screenshots saved: landing-page-hero.png, landing-page-full.png');
