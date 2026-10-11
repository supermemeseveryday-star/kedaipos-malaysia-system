// Kedai POS customer ordering page: scan the table QR → choose dishes → pay online → order goes to the kitchen.
'use strict';

const STR = {
  zh: {
    table: '桌号', all: '全部', add: '加入', sold_out: '已售完', cart: '购物车', items: '件', view_cart: '去结账',
    your_order: '你的订单', note_ph: '备注（例如：少辣、不要葱）', subtotal: '小计', total: '合计', pay_with: '选择付款方式',
    pay: '付款', empty: '还没有选菜', loading: '加载中…', paid_title: '付款成功！', paid_sub: '厨房已收到你的订单，请稍候。',
    receipt: '收据号码', pending_title: '正在确认付款…', pending_sub: '请不要关闭此页面。', failed_title: '付款未完成',
    failed_sub: '没有扣款。你可以重新付款。', try_again: '重新付款', refunded_title: '已自动退款', expired_title: '订单已过期',
    expired_sub: '请重新下单。', order_more: '继续点单', closed: '暂时无法扫码点餐', method: '付款方式',
    test_mode: '测试模式：付款为模拟，不会真的扣款', choose_method: '请先选择付款方式',
  },
  en: {
    table: 'Table', all: 'All', add: 'Add', sold_out: 'Sold out', cart: 'Cart', items: 'items', view_cart: 'Checkout',
    your_order: 'Your order', note_ph: 'Note (e.g. less spicy, no spring onion)', subtotal: 'Subtotal', total: 'Total',
    pay_with: 'Pay with', pay: 'Pay', empty: 'Nothing added yet', loading: 'Loading…', paid_title: 'Payment successful!',
    paid_sub: 'The kitchen has your order. Please wait a moment.', receipt: 'Receipt no.', pending_title: 'Confirming payment…',
    pending_sub: 'Please keep this page open.', failed_title: 'Payment not completed', failed_sub: 'You were not charged. You can try again.',
    try_again: 'Try again', refunded_title: 'Refunded automatically', expired_title: 'Order expired', expired_sub: 'Please order again.',
    order_more: 'Order more', closed: 'Scan-to-order is unavailable', method: 'Payment',
    test_mode: 'Test mode: payments are simulated, no money is charged', choose_method: 'Please choose a payment method',
  },
  ms: {
    table: 'Meja', all: 'Semua', add: 'Tambah', sold_out: 'Habis', cart: 'Troli', items: 'item', view_cart: 'Bayar',
    your_order: 'Pesanan anda', note_ph: 'Nota (cth: kurang pedas, tanpa daun bawang)', subtotal: 'Jumlah kecil', total: 'Jumlah',
    pay_with: 'Bayar dengan', pay: 'Bayar', empty: 'Belum ada pilihan', loading: 'Memuatkan…', paid_title: 'Pembayaran berjaya!',
    paid_sub: 'Dapur telah menerima pesanan anda. Sila tunggu sebentar.', receipt: 'No. resit', pending_title: 'Mengesahkan pembayaran…',
    pending_sub: 'Sila jangan tutup halaman ini.', failed_title: 'Pembayaran tidak selesai', failed_sub: 'Anda tidak dicaj. Sila cuba lagi.',
    try_again: 'Cuba lagi', refunded_title: 'Dipulangkan secara automatik', expired_title: 'Pesanan tamat tempoh',
    expired_sub: 'Sila buat pesanan semula.', order_more: 'Pesan lagi', closed: 'Imbas untuk pesan tidak tersedia', method: 'Bayaran',
    test_mode: 'Mod ujian: bayaran disimulasikan, tiada wang dicaj', choose_method: 'Sila pilih kaedah bayaran',
  },
};
// Brand-neutral colour chips so customers can spot their wallet quickly.
const METHOD_STYLE = {
  tng: ['#1554b8', 'TNG'], grabpay: ['#00a85a', 'G'], boost: ['#e2231a', 'B'], shopeepay: ['#ee4d2d', 'S'],
  applepay: ['#111111', ''], googlepay: ['#4285f4', 'G'], card: ['#5b6670', '▭'], fpx: ['#00346b', 'FPX'],
};

const params = new URLSearchParams(location.search);
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
const tableCode = params.get('table') || store.get('kedai-order-table', '');
const state = {
  lang: store.get('kedai-order-lang', /^zh/i.test(navigator.language) ? 'zh' : /^ms/i.test(navigator.language) ? 'ms' : 'en'),
  menu: null, category: 'all', cart: store.get(`kedai-cart-${tableCode}`, {}), method: store.get('kedai-order-method', ''),
  note: '', sheet: false, busy: false,
};
const app = document.getElementById('app');
const t = k => (STR[state.lang] || STR.en)[k] || STR.en[k] || k;
const rm = c => 'RM ' + (c / 100).toFixed(2);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.className = 'show';
  clearTimeout(toast.timer); toast.timer = setTimeout(() => (el.className = ''), 2600);
}
async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || 'Error'), { status: res.status });
  return data;
}
// "3" → "Table 3", but a name like "桌 1" or "Takeaway" is shown as is.
const tableLabel = name => (/^\d+$/.test(String(name)) ? `${t('table')} ${name}` : String(name));
const saveCart = () => store.set(`kedai-cart-${tableCode}`, state.cart);
const cartLines = () => (state.menu?.products || []).filter(p => state.cart[p.id] > 0).map(p => ({ ...p, qty: state.cart[p.id] }));
function totals() {
  const subtotal = cartLines().reduce((s, l) => s + l.price_cents * l.qty, 0);
  const tax = Math.round(subtotal * (state.menu?.tax.rate || 0) / 100);
  return { subtotal, tax, total: subtotal + tax, count: cartLines().reduce((n, l) => n + l.qty, 0) };
}

function header(shop, table) {
  return `<header class="top"><div class="wrap"><div><h1 class="shop-name">${esc(shop)}</h1>
    ${table ? `<span class="table-chip">🍽 ${esc(tableLabel(table))}</span>` : ''}</div>
    <div class="langs">${['zh', 'en', 'ms'].map(l => `<button data-lang="${l}" class="${state.lang === l ? 'on' : ''}">${{ zh: '中', en: 'EN', ms: 'BM' }[l]}</button>`).join('')}</div>
  </div></header>`;
}

function renderMenu() {
  const m = state.menu;
  const cats = [...new Set(m.products.map(p => p.category || 'General'))];
  const shown = m.products.filter(p => state.category === 'all' || p.category === state.category);
  const groups = state.category === 'all' ? cats.map(c => [c, shown.filter(p => p.category === c)]) : [[state.category, shown]];
  const { total, count } = totals();
  app.innerHTML = header(m.shop.name, m.table.name) +
    `${m.test_mode ? `<div class="wrap"><div class="test-ribbon">⚠ ${t('test_mode')}</div></div>` : ''}
    <nav class="cats"><div class="wrap">${['all', ...cats].map(c => `<button class="cat ${state.category === c ? 'on' : ''}" data-cat="${esc(c)}">${c === 'all' ? t('all') : esc(c)}</button>`).join('')}</div></nav>
    <main class="wrap menu">${groups.map(([c, items]) => `${state.category === 'all' ? `<div class="cat-title">${esc(c)}</div>` : ''}${items.map(dish).join('')}`).join('')}</main>
    ${count ? `<div class="bar"><button class="btn primary wide big" data-open-cart><span class="count">${count}</span><span class="grow">${t('view_cart')}</span><span>${rm(total)}</span></button></div>` : ''}
    ${state.sheet ? renderSheet() : ''}`;
}
function dish(p) {
  const qty = state.cart[p.id] || 0;
  return `<article class="dish ${p.sold_out ? 'sold' : ''}">
    ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : '<div class="ph">🍜</div>'}
    <div><div class="dish-name">${esc(p.name)}</div><div class="dish-price">${rm(p.price_cents)}</div>${p.sold_out ? `<div class="sold-tag">${t('sold_out')}</div>` : ''}</div>
    <div class="stepper">${p.sold_out ? '' : qty ? `<button data-dec="${p.id}" aria-label="-">−</button><span class="n">${qty}</span><button class="add" data-inc="${p.id}" aria-label="+">+</button>`
      : `<button class="add" data-inc="${p.id}" aria-label="${t('add')}">+</button>`}</div></article>`;
}
function renderSheet() {
  const lines = cartLines();
  const { subtotal, tax, total } = totals();
  const methods = state.menu.methods;
  return `<div class="sheet-bg" data-close-sheet><section class="sheet" role="dialog" aria-label="${t('your_order')}"><div class="grab"></div>
    <h2>${t('your_order')} · ${esc(tableLabel(state.menu.table.name))}</h2>
    ${lines.length ? lines.map(l => `<div class="line"><div><div class="nm">${esc(l.name)}</div><div class="pr">${rm(l.price_cents)} × ${l.qty}</div></div>
      <div class="stepper"><button data-dec="${l.id}">−</button><span class="n">${l.qty}</span><button class="add" data-inc="${l.id}">+</button></div></div>`).join('')
      : `<p class="muted">${t('empty')}</p>`}
    <textarea class="note" id="note" maxlength="200" placeholder="${t('note_ph')}">${esc(state.note)}</textarea>
    <div class="sum"><span>${t('subtotal')}</span><span>${rm(subtotal)}</span></div>
    ${tax ? `<div class="sum"><span>${esc(state.menu.tax.label)}</span><span>${rm(tax)}</span></div>` : ''}
    <div class="sum total"><span>${t('total')}</span><span>${rm(total)}</span></div>
    <div class="section-title">${t('pay_with')}</div>
    <div class="methods">${methods.map(m => { const [color, mark] = METHOD_STYLE[m.id] || ['#5b6670', '•'];
      return `<button class="method ${state.method === m.id ? 'on' : ''}" data-method="${m.id}"><span class="dot" style="background:${color}">${m.id === 'applepay' ? '' : esc(mark)}</span>${esc(m.label)}</button>`; }).join('')}</div>
    <div style="height:14px"></div>
    <button class="btn primary wide big" data-pay ${!lines.length || state.busy ? 'disabled' : ''}>${t('pay')} ${rm(total)}</button>
  </section></div>`;
}

async function pay() {
  if (!state.method) return toast(t('choose_method'));
  state.busy = true; renderMenu();
  try {
    const r = await api('/api/public/checkout', { method: 'POST', body: JSON.stringify({
      table: tableCode, method: state.method, note: state.note,
      items: cartLines().map(l => ({ product_id: l.id, quantity: l.qty })) }) });
    store.set('kedai-order-table', tableCode);
    location.href = r.pay_url;
  } catch (e) {
    state.busy = false; toast(e.message);
    await loadMenu();  // prices or stock may have changed
  }
}

async function loadMenu() {
  if (!tableCode) { app.innerHTML = header('Kedai POS') + `<div class="empty">${t('closed')}</div>`; return; }
  try {
    state.menu = await api('/api/public/menu?table=' + encodeURIComponent(tableCode));
  } catch (e) {
    app.innerHTML = header('Kedai POS') + `<div class="empty"><p><strong>${t('closed')}</strong></p><p>${esc(e.message)}</p></div>`;
    return;
  }
  // Drop anything from a saved cart that is gone or sold out.
  const ok = new Set(state.menu.products.filter(p => !p.sold_out).map(p => String(p.id)));
  Object.keys(state.cart).forEach(id => { if (!ok.has(id)) delete state.cart[id]; });
  if (state.method && !state.menu.methods.some(m => m.id === state.method)) state.method = '';
  saveCart(); renderMenu();
}

async function showStatus(session) {
  if (!state.menu && tableCode) state.menu = await api('/api/public/menu?table=' + encodeURIComponent(tableCode)).catch(() => null);
  let s;
  try { s = await api('/api/public/checkout/' + encodeURIComponent(session)); }
  catch (e) { app.innerHTML = header('Kedai POS') + `<div class="empty">${esc(e.message)}</div>`; return; }
  const view = {
    paid: ['✓', '', 'paid_title', 'paid_sub'], pending: ['…', 'wait', 'pending_title', 'pending_sub'],
    failed: ['!', 'bad', 'failed_title', 'failed_sub'], refunded: ['↺', 'bad', 'refunded_title', ''],
    expired: ['⌛', 'bad', 'expired_title', 'expired_sub'],
  }[s.status];
  if (s.status === 'paid') { store.set(`kedai-cart-${tableCode}`, {}); }
  app.innerHTML = header(state.menu?.shop.name || '', s.table) + `<main class="wrap status">
    <div class="icon ${view[1]}">${view[0]}</div><h1>${t(view[2])}</h1>
    <p class="muted">${s.status === 'refunded' ? esc(s.message) : view[3] ? t(view[3]) : ''}</p>
    <div class="receipt">
      ${s.receipt_no ? `<div class="head"><span>${t('receipt')}</span><span>${esc(s.receipt_no)}</span></div>` : ''}
      ${s.items.map(i => `<div class="sum"><span>${esc(i.name)} × ${i.quantity}</span><span>${rm(i.line_total_cents)}</span></div>`).join('')}
      <div class="sum total"><span>${t('total')}</span><span>${rm(s.total_cents)}</span></div>
      <div class="sum"><span>${t('method')}</span><span>${esc(s.method_label)}</span></div>
    </div>
    ${s.status === 'failed' ? `<button class="btn primary wide big" data-back>${t('try_again')}</button>`
      : s.status !== 'pending' ? `<button class="btn soft wide" data-back>${t('order_more')}</button>` : ''}
  </main>`;
  if (s.status === 'pending') setTimeout(() => showStatus(session), 2000);
}

app.addEventListener('click', e => {
  const el = e.target.closest('button, [data-close-sheet]');
  if (!el) return;
  const d = el.dataset;
  if (d.lang) { state.lang = d.lang; store.set('kedai-order-lang', d.lang); return params.get('session') ? showStatus(params.get('session')) : renderMenu(); }
  if (d.back !== undefined) { location.href = '/order?table=' + encodeURIComponent(tableCode); return; }
  if (d.cat) { state.category = d.cat; return renderMenu(); }
  if (d.inc) { state.cart[d.inc] = (state.cart[d.inc] || 0) + 1; saveCart(); return renderMenu(); }
  if (d.dec) { state.cart[d.dec] = Math.max(0, (state.cart[d.dec] || 0) - 1); if (!state.cart[d.dec]) delete state.cart[d.dec]; saveCart(); if (!totals().count) state.sheet = false; return renderMenu(); }
  if (d.openCart !== undefined) { state.sheet = true; return renderMenu(); }
  if (d.method) { state.method = d.method; store.set('kedai-order-method', d.method); return renderMenu(); }
  if (d.pay !== undefined) return pay();
  if (d.closeSheet !== undefined && e.target === el) { state.sheet = false; return renderMenu(); }
});
app.addEventListener('input', e => { if (e.target.id === 'note') state.note = e.target.value; });

document.documentElement.lang = state.lang === 'zh' ? 'zh-Hans' : state.lang;
if (params.get('session')) showStatus(params.get('session'));
else { app.innerHTML = `<div class="empty">${t('loading')}</div>`; loadMenu(); }
