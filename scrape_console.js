const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[${msg.type().toUpperCase()}] ${msg.text()} (${msg.location().url})`);
    } else {
      console.log(`[${msg.type().toUpperCase()}] ${msg.text()}`);
    }
  });
  
  page.on('pageerror', err => {
    console.log(`[PAGE_ERROR] ${err.message}`);
  });

  page.on('requestfailed', request => {
    console.log(`[REQUEST_FAILED] ${request.url()} - ${request.failure()?.errorText}`);
  });
  
  page.on('response', response => {
    if (!response.ok()) {
      console.log(`[RESPONSE_ERROR] ${response.url()} - ${response.status()}`);
    }
  });

  try {
    await page.goto('http://localhost:5173', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await new Promise(r => setTimeout(r, 5000));
  } catch (err) {
    console.error('Navigation error:', err);
  } finally {
    await browser.close();
  }
})();
