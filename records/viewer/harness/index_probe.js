// RNPLens viewer track r2: load the owner package index.html, log every request (CDP), list its links.
// usage: node index_probe.js CHROME_EXE INDEX_HTML OUT_JSON
const puppeteer = require('puppeteer-core');
const fs = require('fs'), path = require('path');
(async () => {
  const [exe, idx, outp] = process.argv.slice(2);
  const browser = await puppeteer.launch({executablePath: exe, headless: 'shell', pipe: true,
      args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  const page = await browser.newPage();
  const cdp = await page.createCDPSession(); await cdp.send('Network.enable');
  const reqs = [], errs = [];
  cdp.on('Network.requestWillBeSent', e => reqs.push(e.request.url));
  page.on('pageerror', e => errs.push(String(e)));
  await page.goto('file://' + path.resolve(idx), {waitUntil: 'load', timeout: 60000});
  await new Promise(r => setTimeout(r, 1000));
  const links = await page.$$eval('a', as => as.map(a => a.href));
  const text = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(outp, JSON.stringify({requests: reqs, links, page_errors: errs, text}, null, 1));
  console.log(JSON.stringify({n_requests: reqs.length, nonfile: reqs.filter(u => !u.startsWith('file://')), n_links: links.length}));
  await browser.close();
})().catch(e => { console.log('FATAL ' + String(e).slice(0, 1500)); process.exit(1); });
