// Seeds a demo shop and captures the README screenshots. Run against an EMPTY data folder:
//   cd kedai-pos && KEDAI_DATA_DIR=/tmp/kedai-demo KEDAI_PORT=8797 python3 server.py
//   PWPATH=$(npm root -g)/playwright node docs/screenshots/capture.mjs docs/screenshots http://127.0.0.1:8797
// Needs Playwright with Chromium, and the Noto Color Emoji font for the product pictures.
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PWPATH);
const [OUT, B] = process.argv.slice(2);

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, locale: 'en-MY' });
await ctx.addInitScript(() => { try { if (!localStorage.getItem('kedai-lang')) localStorage.setItem('kedai-lang', 'en'); } catch {} });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
const api = (path, method = 'GET', body) => page.evaluate(async ([path, method, body]) => {
  const r = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  return r.json();
}, [path, method, body]);
const shot = async (name, opts = {}) => { await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(450); await page.screenshot({ path: `${OUT}/${name}.png`, ...opts }); console.log('saved', name); };
const go = async pageName => { await page.click(`.sidebar [data-page=${pageName}]`); await page.waitForTimeout(300); };

// 1. First-run setup screen
await page.goto(B);
await page.waitForSelector('form');
await shot('01-setup');
await page.fill('input[name=display_name]', 'Ah Seng');
await page.fill('input[name=username]', 'owner');
await page.fill('input[name=password]', 'demo-password');
await page.click('form .btn.primary');
await page.waitForSelector('.nav');

// Demo images drawn in the browser: an emoji on a soft tile, and a placeholder QR.
const tile = (emoji, bg) => page.evaluate(([emoji, bg]) => {
  const c = document.createElement('canvas'); c.width = c.height = 480; const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 480, 480); grad.addColorStop(0, bg[0]); grad.addColorStop(1, bg[1]);
  g.fillStyle = grad; g.fillRect(0, 0, 480, 480);
  g.font = '230px "Noto Color Emoji"'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(emoji, 240, 258);
  return c.toDataURL('image/jpeg', 0.86);
}, [emoji, bg]);
const sampleQr = await page.evaluate(() => {
  const n = 29, s = 14, c = document.createElement('canvas'); c.width = c.height = n * s + 80; const g = c.getContext('2d');
  g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.translate(40, 40); g.fillStyle = '#1b1b1b';
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const finder = (x, y) => { g.fillRect(x * s, y * s, 7 * s, 7 * s); g.clearRect((x + 1) * s, (y + 1) * s, 5 * s, 5 * s); g.fillStyle = '#fff'; g.fillRect((x + 1) * s, (y + 1) * s, 5 * s, 5 * s); g.fillStyle = '#1b1b1b'; g.fillRect((x + 2) * s, (y + 2) * s, 3 * s, 3 * s); };
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { const inF = (x < 8 && y < 8) || (x > n - 9 && y < 8) || (x < 8 && y > n - 9); if (!inF && rnd() > 0.52) g.fillRect(x * s, y * s, s, s); }
  finder(0, 0); finder(n - 7, 0); finder(0, n - 7);
  g.fillStyle = '#fff'; g.fillRect(9 * s, 12 * s, 11 * s, 5 * s); g.fillStyle = '#c0392b'; g.font = 'bold 34px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('SAMPLE', 14.5 * s, 14.5 * s);
  return c.toDataURL('image/png');
});

await api('/api/settings', 'POST', { shop_name: 'Kedai Runcit Ah Seng', shop_address: '12, Jalan Bunga Raya, 75100 Melaka', shop_phone: '06-123 4567', merchant_qr: sampleQr, tax_enabled: false, tax_label: 'SST', tax_rate: 6 });
const products = [
  ['Teh Tarik', 'Drinks', 2.8, 40, '🧋', ['#fdf1e3', '#f6dcc0']],
  ['Kopi O', 'Drinks', 2.2, 35, '☕', ['#f3ece6', '#e3d3c4']],
  ['Air Sirap Bandung', 'Drinks', 2.5, 4, '🥤', ['#fde8ef', '#f7c9d8']],
  ['Mineral Water 500ml', 'Drinks', 1.2, 60, '💧', ['#e6f3fb', '#cbe6f6']],
  ['Nasi Lemak', 'Food', 4.5, 25, '🍛', ['#fff5dc', '#fbe5aa']],
  ['Roti Canai', 'Food', 1.8, 30, '🫓', ['#fbf3e4', '#f1dfbf']],
  ['Mee Goreng Mamak', 'Food', 6.5, 18, '🍜', ['#fdeee4', '#f8d6c0']],
  ['Kuih Lapis', 'Food', 1.0, 3, '🍰', ['#f2ecfb', '#ddd0f5']],
  ['Tissue Pack', 'Daily goods', 3.9, 22, '🧻', ['#eef4f0', '#d6e7dc']],
  ['Dish Soap 500ml', 'Daily goods', 4.9, 12, '🧴', ['#e9f6f3', '#cdebe3']],
];
const ids = {};
for (const [name, category, price, stock, emoji, bg] of products) {
  const r = await api('/api/products', 'POST', { name, category, price, stock, sku: '955' + String(Math.floor(1e9 + Math.random() * 9e9)), image: await tile(emoji, bg) });
  ids[name] = r.id;
}
await api('/api/users', 'POST', { username: 'aisyah', display_name: 'Aisyah', password: 'demo-password' });
await api('/api/users', 'POST', { username: 'ravi', display_name: 'Ravi', password: 'demo-password' });
const sell = async (items, method, cash) => {
  const o = await api('/api/orders', 'POST', { items: items.map(([n, q]) => ({ product_id: ids[n], quantity: q })) });
  if (method) await api(`/api/orders/${o.id}/pay`, 'POST', method === 'cash' ? { method, cash_received: cash } : { method });
  return o.id;
};
await sell([['Nasi Lemak', 2], ['Teh Tarik', 2]], 'cash', 20);
await sell([['Mee Goreng Mamak', 1], ['Kopi O', 1]], 'qr');
await sell([['Roti Canai', 3], ['Teh Tarik', 1]], 'cash', 10);
await sell([['Tissue Pack', 2], ['Mineral Water 500ml', 6]], 'qr');
await sell([['Nasi Lemak', 1], ['Air Sirap Bandung', 1]], 'cash', 10);
const receiptId = await sell([['Nasi Lemak', 2], ['Roti Canai', 2], ['Teh Tarik', 3]], 'cash', 50);
await sell([['Mee Goreng Mamak', 2], ['Kopi O', 2]]); // open order, waiting for payment
await api('/api/expenses', 'POST', { description: 'Gas cylinder refill', category: 'Supplies / stock', amount: 28 });
await api('/api/expenses', 'POST', { description: 'Fresh coconut milk', category: 'Supplies / stock', amount: 15.5 });
await page.reload();
await page.waitForSelector('[data-add]');

// 2. Checkout with a filled cart
for (const [n, times] of [['Nasi Lemak', 2], ['Teh Tarik', 2], ['Roti Canai', 1]]) {
  for (let i = 0; i < times; i++) await page.click(`[data-add="${ids[n]}"] .add-product`);
}
await page.waitForTimeout(700);
await shot('02-checkout');

// 3. Cash payment with change (checkout saves the order and empties the cart)
await page.click('[data-action=checkout-cash]');
await page.waitForSelector('#cash-received');
await page.fill('#cash-received', '20');
await page.dispatchEvent('#cash-received', 'input');
await shot('03-cash-payment');
await page.click('.modal [data-action=confirm-pay]');
await page.waitForTimeout(2900);

// 4. DuitNow QR payment
for (const n of ['Mee Goreng Mamak', 'Kopi O']) await page.click(`[data-add="${ids[n]}"] .add-product`);
await page.click('[data-action=checkout-qr]');
await page.waitForSelector('.qr-display');
await shot('04-qr-payment');
await page.click('.modal [data-action=confirm-pay]');
await page.waitForTimeout(2900);

// 5. Orders + 6. Receipt
await go('orders');
await shot('05-orders');
await page.click(`[data-action=receipt][data-id="${receiptId}"]`);
await page.waitForSelector('#receipt-content');
await shot('06-receipt');
await page.click('.modal-close');

// 7. Products, 8. Inventory, 9. Ledger, 10. Reports, 11. Settings
await go('products'); await shot('07-products');
await go('stock'); await shot('08-inventory');
await go('ledger'); await shot('09-ledger');
await go('reports'); await shot('10-reports');
await go('settings'); await shot('11-settings', { fullPage: true });

// 12. Phone view (staff device on shop Wi-Fi), in Chinese
const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
await phone.addInitScript(() => { try { localStorage.setItem('kedai-lang', 'zh'); } catch {} });
const p2 = await phone.newPage();
await p2.goto(B);
await p2.waitForSelector('form');
await p2.fill('input[name=username]', 'aisyah');
await p2.fill('input[name=password]', 'demo-password');
await p2.click('form .btn.primary');
await p2.waitForSelector('[data-add]');
await p2.tap(`[data-add="${ids['Mee Goreng Mamak']}"] .add-product`);
await p2.tap(`[data-add="${ids['Kopi O']}"] .add-product`);
await p2.waitForTimeout(700);
await p2.evaluate(() => window.scrollTo(0, 0));
await p2.screenshot({ path: `${OUT}/12-phone-zh.png` });
await p2.evaluate(() => document.querySelector('.cart-panel').scrollIntoView({ block: 'end' }));
await p2.waitForTimeout(400);
await p2.screenshot({ path: `${OUT}/13-phone-cart-zh.png` });
console.log('saved 12/13 phone');

console.log('errors:', JSON.stringify(errors));
await browser.close();
