// POS side of scan-to-order: table QR codes, live settlement, partial/full refunds, new-order alerts.
// Loaded after app.js and extends it (app.js functions are plain globals).
'use strict';

Object.assign(STRINGS.zh, {
  nav_settlement: '结算', settlement: '每日结算', settlement_hint: '实时更新：销售按付款日计算，退款按退款日计算。',
  gross_sales: '总销售额', refunds: '退款', net_sales: '净销售额', expected_cash: '钱箱应有现金', tax_collected: '税额',
  expenses: '支出', net_after_expenses: '扣除支出后', online_payments: '线上付款净额', by_method_full: '按付款方式',
  method: '付款方式', sales: '销售', count: '笔数', net: '净额', transactions: '交易明细', time: '时间', type: '类型', sale: '销售',
  refund: '退款', reference: '参考号', source: '来源', export_csv: '导出 CSV', online_tag: '线上', close_day: '日结 / 交班',
  counted_cash: '实点现金（RM）', close_note: '备注', close_btn: '确认日结', closed_at: '已日结', variance: '差额', reclose: '重新日结',
  day_closed: '日结已保存', no_transactions: '这一天还没有交易', qr_order: '扫码', refunded_amount: '已退款',
  refund_title: '退款', refund_amount: '退款金额（RM）', refund_max: '最多可退', refund_reason: '退款原因', refund_restock: '把商品加回库存（全额退款时）',
  refund_online: '这笔是线上付款，确认后会通过支付网关原路退回。', refund_offline: '这笔是现金 / DuitNow 付款，请先把钱交还给顾客，再在这里记录。',
  confirm_refund: '确认退款', qr_ordering: '扫码点餐', qr_enable: '开启扫码点餐', public_url: '对外网址（Cloudflare Tunnel，https://…）',
  public_url_hint: '顾客用手机流量扫码时需要这个网址。没有设置的话，只有连上店里 Wi-Fi 的手机能打开。', qr_methods: '顾客可用的付款方式',
  tables: '桌子与二维码', add_table: '添加桌子', table_name: '桌名（例如：桌 1、外带）', print_qr: '打印二维码', print_all: '打印全部二维码',
  disable: '停用', enable: '启用', open_page: '打开点餐页', test_gateway: '目前是「模拟支付」测试模式：顾客不会真的被扣款。正式营业前，请先接上真正的支付网关（Fiuu / Stripe 等）。',
  new_qr_order: '新扫码订单', scan_to_order: '扫码点餐', table: '桌', no_tables: '还没有桌子', test_payments: '笔模拟（测试）付款',
});
Object.assign(STRINGS.en, {
  nav_settlement: 'Settlement', settlement: 'Daily settlement', settlement_hint: 'Live: sales count on the day paid, refunds on the day refunded.',
  gross_sales: 'Gross sales', refunds: 'Refunds', net_sales: 'Net sales', expected_cash: 'Expected cash in drawer', tax_collected: 'Tax',
  expenses: 'Expenses', net_after_expenses: 'Net after expenses', online_payments: 'Online payments (net)', by_method_full: 'By payment method',
  method: 'Method', sales: 'Sales', count: 'Count', net: 'Net', transactions: 'Transactions', time: 'Time', type: 'Type', sale: 'Sale',
  refund: 'Refund', reference: 'Reference', source: 'Source', export_csv: 'Export CSV', online_tag: 'online', close_day: 'Close the day',
  counted_cash: 'Cash counted (RM)', close_note: 'Note', close_btn: 'Close day', closed_at: 'Closed', variance: 'Variance', reclose: 'Close again',
  day_closed: 'Day closing saved', no_transactions: 'No transactions on this day', qr_order: 'Scan order', refunded_amount: 'Refunded',
  refund_title: 'Refund', refund_amount: 'Refund amount (RM)', refund_max: 'Up to', refund_reason: 'Reason', refund_restock: 'Put items back in stock (full refund)',
  refund_online: 'This was paid online. The money goes back to the customer through the payment gateway.', refund_offline: 'This was paid in cash / DuitNow. Hand the money back first, then record it here.',
  confirm_refund: 'Confirm refund', qr_ordering: 'Scan-to-order', qr_enable: 'Turn on scan-to-order', public_url: 'Public address (Cloudflare Tunnel, https://…)',
  public_url_hint: 'Needed so customers on mobile data can open the menu. Without it only phones on the shop Wi-Fi can.', qr_methods: 'Payment methods for customers',
  tables: 'Tables & QR codes', add_table: 'Add table', table_name: 'Table name (e.g. Table 1, Takeaway)', print_qr: 'Print QR', print_all: 'Print all QR codes',
  disable: 'Disable', enable: 'Enable', open_page: 'Open menu', test_gateway: 'Payments are in SIMULATED test mode: customers are not charged. Connect a real payment gateway (Fiuu, Stripe…) before going live.',
  new_qr_order: 'New scan order', scan_to_order: 'Scan to order', table: 'Table', no_tables: 'No tables yet', test_payments: 'simulated (test) payments',
});
Object.assign(STRINGS.ms, {
  nav_settlement: 'Penyelesaian', settlement: 'Penyelesaian harian', settlement_hint: 'Langsung: jualan dikira pada hari dibayar, bayaran balik pada hari dibuat.',
  gross_sales: 'Jualan kasar', refunds: 'Bayaran balik', net_sales: 'Jualan bersih', expected_cash: 'Tunai dijangka dalam laci', tax_collected: 'Cukai',
  expenses: 'Perbelanjaan', net_after_expenses: 'Bersih selepas perbelanjaan', online_payments: 'Bayaran dalam talian (bersih)', by_method_full: 'Mengikut kaedah bayaran',
  method: 'Kaedah', sales: 'Jualan', count: 'Bil.', net: 'Bersih', transactions: 'Transaksi', time: 'Masa', type: 'Jenis', sale: 'Jualan',
  refund: 'Bayaran balik', reference: 'Rujukan', source: 'Sumber', export_csv: 'Eksport CSV', online_tag: 'dalam talian', close_day: 'Tutup hari',
  counted_cash: 'Tunai dikira (RM)', close_note: 'Nota', close_btn: 'Tutup hari', closed_at: 'Ditutup', variance: 'Perbezaan', reclose: 'Tutup semula',
  day_closed: 'Penutupan hari disimpan', no_transactions: 'Tiada transaksi pada hari ini', qr_order: 'Pesanan imbas', refunded_amount: 'Dipulangkan',
  refund_title: 'Bayaran balik', refund_amount: 'Amaun bayaran balik (RM)', refund_max: 'Maksimum', refund_reason: 'Sebab', refund_restock: 'Kembalikan item ke stok (bayaran balik penuh)',
  refund_online: 'Dibayar dalam talian. Wang dipulangkan melalui gerbang pembayaran.', refund_offline: 'Dibayar tunai / DuitNow. Pulangkan wang dahulu, kemudian rekodkan di sini.',
  confirm_refund: 'Sahkan bayaran balik', qr_ordering: 'Imbas untuk pesan', qr_enable: 'Hidupkan imbas untuk pesan', public_url: 'Alamat awam (Cloudflare Tunnel, https://…)',
  public_url_hint: 'Diperlukan supaya pelanggan dengan data mudah alih boleh membuka menu.', qr_methods: 'Kaedah bayaran untuk pelanggan',
  tables: 'Meja & kod QR', add_table: 'Tambah meja', table_name: 'Nama meja (cth: Meja 1, Bungkus)', print_qr: 'Cetak QR', print_all: 'Cetak semua QR',
  disable: 'Nyahaktif', enable: 'Aktifkan', open_page: 'Buka menu', test_gateway: 'Bayaran dalam mod ujian SIMULASI: pelanggan tidak dicaj. Sambungkan gerbang pembayaran sebenar sebelum dibuka.',
  new_qr_order: 'Pesanan imbas baharu', scan_to_order: 'Imbas untuk pesan', table: 'Meja', no_tables: 'Belum ada meja', test_payments: 'bayaran simulasi (ujian)',
});

const METHOD_LABELS = { cash: { zh: '现金', en: 'Cash', ms: 'Tunai' }, qr: { zh: 'DuitNow QR', en: 'DuitNow QR', ms: 'DuitNow QR' } };
function methodLabel(m) {
  if (METHOD_LABELS[m]) return METHOD_LABELS[m][state.lang] || METHOD_LABELS[m].en;
  return (state.settings.payment_methods || []).find(x => x.id === m)?.label || m || '—';
}

NAV.splice(NAV.findIndex(n => n[0] === 'reports') + 1, 0, ['settlement', 'nav_settlement', '◫']);
Object.assign(state, { settlement: null, settlementDay: '', tables: [], lastQrOrderId: null });

// ---------------------------------------------------------------- data
const baseRefresh = refresh;
refresh = async function () {
  await baseRefresh();
  if (!state.user) return;
  const owner = state.user.role === 'owner';
  if (owner && state.page === 'settlement') state.settlement = await api('/api/settlement' + (state.settlementDay ? `?day=${state.settlementDay}` : ''));
  if (owner && state.page === 'settings') state.tables = await api('/api/tables');
  announceQrOrders();
};

// Beep + toast when a customer's paid scan order arrives, so the counter/kitchen sees it immediately.
function announceQrOrders() {
  const newest = state.orders.filter(o => o.source === 'qr').reduce((max, o) => Math.max(max, o.id), 0);
  if (state.lastQrOrderId === null) { state.lastQrOrderId = newest; return; }
  const fresh = state.orders.filter(o => o.source === 'qr' && o.id > state.lastQrOrderId);
  state.lastQrOrderId = Math.max(state.lastQrOrderId, newest);
  if (!fresh.length) return;
  const o = fresh[0];
  toast(`🔔 ${t('new_qr_order')} · ${o.table_name || ''} · ${money(o.total_cents)}${fresh.length > 1 ? ` (+${fresh.length - 1})` : ''}`);
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.18].forEach(at => {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.frequency.value = 880; gain.gain.setValueAtTime(0.2, ctx.currentTime + at);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + at + 0.15);
      osc.connect(gain).connect(ctx.destination); osc.start(ctx.currentTime + at); osc.stop(ctx.currentTime + at + 0.16);
    });
  } catch { /* audio not allowed before the first tap */ }
  if (state.page === 'orders' || state.page === 'settlement') render();
}

// Keep the settlement page live while it is open.
setInterval(() => {
  if (state.user?.role === 'owner' && state.page === 'settlement' && !state.modal && document.visibilityState === 'visible') {
    api('/api/settlement' + (state.settlementDay ? `?day=${state.settlementDay}` : '')).then(r => { state.settlement = r; render(); }).catch(() => {});
  }
}, 5000);

// ---------------------------------------------------------------- pages
const baseRenderPage = renderPage;
renderPage = function () {
  return state.page === 'settlement' && state.user.role === 'owner' ? renderSettlement() : baseRenderPage();
};

function metric(label, cents, foot = '', cls = '') {
  return `<div class="card"><div class="metric-label">${label}</div><div class="metric-value ${cls}">${money(cents)}</div>${foot ? `<div class="metric-foot">${foot}</div>` : ''}</div>`;
}

function renderSettlement() {
  const r = state.settlement;
  if (!r) return `<div class="empty">${t('loading')}</div>`;
  const c = r.closing;
  return `<div class="page-head"><div><h1>${t('settlement')}</h1><p>${t('settlement_hint')}</p></div>
    <div class="inline" style="flex:0 0 auto"><input type="date" id="settlement-day" class="btn" value="${esc(r.day)}">
    <button class="btn" data-action="settlement-export">⇩ ${t('export_csv')}</button></div></div>
    ${r.test_payments ? `<div class="login-note warn-note">⚠ ${r.test_payments} ${t('test_payments')}</div>` : ''}
    <div class="metrics">
      ${metric(t('gross_sales'), r.gross_sales_cents, `${r.sales_count} ${t('today_orders')} · ${r.qr_orders} ${t('qr_order')}`)}
      ${metric(t('refunds'), r.refunds_cents, `${r.refund_count} ${t('count')}`, r.refunds_cents ? 'neg' : '')}
      ${metric(t('net_sales'), r.net_sales_cents)}
      ${metric(t('expected_cash'), r.expected_cash_cents)}
    </div>
    <div class="metrics">
      ${metric(t('online_payments'), r.online_net_cents)}
      ${metric(t('tax_collected'), r.tax_cents)}
      ${metric(t('expenses'), r.expenses_cents)}
      ${metric(t('net_after_expenses'), r.net_after_expenses_cents)}
    </div>
    <div class="settings-grid">
      <section class="card"><h2>${t('by_method_full')}</h2>
        ${r.by_method.length ? `<table class="mini-table"><thead><tr><th>${t('method')}</th><th>${t('sales')}</th><th>${t('refunds')}</th><th>${t('net')}</th></tr></thead><tbody>
        ${r.by_method.map(m => `<tr><td>${esc(methodLabel(m.method))}${m.online ? ` <span class="badge qr">${t('online_tag')}</span>` : ''}</td><td>${m.sales_count} · ${money(m.sales_cents)}</td>
          <td class="${m.refund_cents ? 'neg' : ''}">${m.refund_count} · ${money(m.refund_cents)}</td><td><strong>${money(m.net_cents)}</strong></td></tr>`).join('')}
        </tbody></table>` : `<p class="muted">${t('no_transactions')}</p>`}
      </section>
      <form class="card" id="close-day-form"><h2>${t('close_day')}</h2>
        ${c ? `<div class="login-note">${t('closed_at')}: ${dateFmt(c.closed_at)} · ${t('counted_cash')}: ${money(c.counted_cash_cents)} · ${t('variance')}:
          <strong class="${c.counted_cash_cents - c.expected_cash_cents < 0 ? 'neg' : ''}">${money(c.counted_cash_cents - c.expected_cash_cents)}</strong>${c.note ? ` · ${esc(c.note)}` : ''}</div>` : ''}
        <div class="field"><label>${t('expected_cash')}</label><input value="${money(r.expected_cash_cents)}" disabled></div>
        <div class="field"><label>${t('counted_cash')}</label><input name="counted_cash" type="number" step="0.01" min="0" required value="${c ? (c.counted_cash_cents / 100).toFixed(2) : ''}"></div>
        <div class="field"><label>${t('close_note')}</label><input name="note" maxlength="300" value="${esc(c?.note || '')}"></div>
        <button class="btn primary">${c ? t('reclose') : t('close_btn')}</button>
      </form>
    </div>
    <h2 class="section-h">${t('transactions')}</h2>
    ${r.transactions.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>${t('time')}</th><th>${t('type')}</th><th>${t('receipt_no')}</th><th>${t('source')}</th><th>${t('method')}</th><th>${t('amount')}</th><th>${t('reference')}</th></tr></thead><tbody>
      ${r.transactions.map(x => `<tr><td>${dateFmt(x.at)}</td><td>${x.type === 'sale' ? t('sale') : `<span class="neg">${t('refund')}</span>`}</td><td>${esc(x.receipt_no || '')}</td>
        <td>${x.source === 'qr' ? `${t('qr_order')}${x.table_name ? ' · ' + esc(x.table_name) : ''}` : 'POS'}</td><td>${esc(methodLabel(x.method))}</td>
        <td class="${x.type === 'refund' ? 'neg' : ''}"><strong>${x.type === 'refund' ? '−' : ''}${money(x.type === 'sale' ? x.total_cents : x.amount_cents)}</strong></td>
        <td class="muted small-text">${esc(x.reference || x.reason || '')}</td></tr>`).join('')}
    </tbody></table></div>` : `<div class="card empty">${t('no_transactions')}</div>`}`;
}

// Scan-to-order card appended to the settings page.
const baseRenderSettings = renderSettings;
renderSettings = function () {
  const s = state.settings;
  const chosen = s.qr_payment_methods || (s.payment_methods || []).filter(m => m.online).map(m => m.id);
  const base = (s.public_base_url || location.origin).replace(/\/$/, '');
  const card = `<section class="card qr-admin"><h2>📱 ${t('qr_ordering')}</h2>
    <div class="login-note warn-note">⚠ ${t('test_gateway')}</div>
    <form id="qr-ordering-form">
      <div class="switch-row"><label for="qr-enabled">${t('qr_enable')}</label><input id="qr-enabled" name="enabled" type="checkbox" ${s.qr_ordering_enabled ? 'checked' : ''}></div>
      <div class="field" style="margin-top:12px"><label>${t('public_url')}</label><input name="public_base_url" placeholder="https://order.your-shop.com" value="${esc(s.public_base_url || '')}"><small class="muted">${t('public_url_hint')}</small></div>
      <div class="field"><label>${t('qr_methods')}</label><div class="method-checks">${(s.payment_methods || []).filter(m => m.online).map(m =>
        `<label class="check"><input type="checkbox" name="method" value="${m.id}" ${chosen.includes(m.id) ? 'checked' : ''}> ${esc(m.label)}</label>`).join('')}</div></div>
      <button class="btn primary">${t('save_settings')}</button>
    </form>
    <h3 style="margin-top:22px">${t('tables')}</h3>
    <form id="add-table-form" class="inline"><input name="name" class="btn" placeholder="${t('table_name')}" required maxlength="40" style="flex:1;text-align:left"><button class="btn soft" style="flex:0 0 auto">＋ ${t('add_table')}</button></form>
    <div class="table-list">${state.tables.length ? state.tables.map(tb => {
      const url = `${base}/order?table=${encodeURIComponent(tb.code)}`;
      return `<div class="table-row ${tb.active ? '' : 'off'}"><div class="qr-thumb">${qrSvg(url, 3)}</div>
        <div class="grow"><strong>${esc(tb.name)}</strong><div class="muted small-text">${esc(url)}</div></div>
        <div class="inline" style="flex:0 0 auto"><a class="btn small" href="${esc(url)}" target="_blank" rel="noopener">${t('open_page')}</a>
        <button class="btn small" data-action="print-table-qr" data-id="${tb.id}">${t('print_qr')}</button>
        <button class="btn small ${tb.active ? 'danger' : ''}" data-action="toggle-table" data-id="${tb.id}" data-active="${tb.active ? '0' : '1'}">${tb.active ? t('disable') : t('enable')}</button></div></div>`;
    }).join('') : `<p class="muted">${t('no_tables')}</p>`}</div>
    ${state.tables.some(tb => tb.active) ? `<button class="btn" data-action="print-table-qr" data-id="all">🖨 ${t('print_all')}</button>` : ''}
  </section>`;
  return baseRenderSettings().replace(/<\/div>$/, card + '</div>');
};

function qrSvg(text, cell = 6) {
  if (typeof qrcode !== 'function') return '';
  const qr = qrcode(0, 'M'); qr.addData(text); qr.make();
  return qr.createSvgTag({ cellSize: cell, margin: 2, scalable: true });
}

function printTableQrs(ids) {
  const base = (state.settings.public_base_url || location.origin).replace(/\/$/, '');
  const shop = state.settings.shop_name || 'Kedai POS';
  const cards = state.tables.filter(tb => tb.active && (ids === 'all' || String(tb.id) === String(ids))).map(tb =>
    `<div class="qr-card"><div class="shop">${esc(shop)}</div><div class="tb">${esc(tb.name)}</div>${qrSvg(`${base}/order?table=${encodeURIComponent(tb.code)}`, 8)}
     <div class="how">扫码点餐 · 付款<br>Scan to order &amp; pay<br>Imbas untuk pesan &amp; bayar</div><div class="pays">TNG · GrabPay · Boost · ShopeePay · Apple Pay · Google Pay</div></div>`).join('');
  const w = window.open('', '_blank');
  if (!w) return toast('Allow pop-ups to print QR codes');
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(shop)} QR</title><style>
    body{margin:0;font-family:system-ui,"Noto Sans SC",sans-serif;color:#17231e}.sheet{display:flex;flex-wrap:wrap;gap:8mm;padding:10mm}
    .qr-card{width:85mm;border:2px solid #15583d;border-radius:6mm;padding:6mm;text-align:center;break-inside:avoid}
    .shop{font-weight:800;font-size:16pt;color:#15583d}.tb{font-size:22pt;font-weight:800;margin:2mm 0}svg{width:60mm;height:60mm}
    .how{font-size:11pt;font-weight:600;margin-top:2mm}.pays{font-size:8pt;color:#76827b;margin-top:2mm}
    @page{margin:8mm}</style></head><body><div class="sheet">${cards}</div><script>onload=()=>print()<\/script></body></html>`);
  w.document.close();
}

// ---------------------------------------------------------------- refund modal
const baseRenderModal = renderModal;
renderModal = function () {
  const m = state.modal;
  if (!m || m.type !== 'refund') return baseRenderModal();
  const o = m.order;
  const left = o.total_cents - (o.refunded_cents || 0);
  const online = (state.settings.payment_methods || []).find(x => x.id === o.payment_method)?.online;
  return `<div class="modal-backdrop" data-close-modal><form class="modal" id="refund-form"><button type="button" class="modal-close" data-close-modal>×</button>
    <h2>${t('refund_title')} · #${esc(o.receipt_no || o.id)}</h2>
    <div class="login-note">${online ? t('refund_online') : t('refund_offline')}</div>
    <div class="sum-row"><span>${t('payment')}</span><strong>${esc(methodLabel(o.payment_method))}</strong></div>
    <div class="sum-row"><span>${t('total')}</span><strong>${money(o.total_cents)}</strong></div>
    ${o.refunded_cents ? `<div class="sum-row"><span>${t('refunded_amount')}</span><strong class="neg">${money(o.refunded_cents)}</strong></div>` : ''}
    <div class="field" style="margin-top:14px"><label>${t('refund_amount')} · ${t('refund_max')} ${money(left)}</label>
      <input name="amount" type="number" step="0.01" min="0.01" max="${(left / 100).toFixed(2)}" value="${(left / 100).toFixed(2)}" required></div>
    <div class="field"><label>${t('refund_reason')}</label><input name="reason" maxlength="300" required></div>
    ${o.refunded_cents ? '' : `<label class="check"><input type="checkbox" name="restock" checked> ${t('refund_restock')}</label>`}
    <button class="btn danger wide" style="margin-top:16px">${t('confirm_refund')}</button>
  </form></div>`;
};

// ---------------------------------------------------------------- actions
const baseHandleAction = handleAction;
handleAction = async function (action, data = {}) {
  try {
    switch (action) {
      case 'refund-order': {
        const order = state.orders.find(o => o.id === Number(data.id));
        if (order) { state.modal = { type: 'refund', order }; render(); }
        return;
      }
      case 'settlement-export': {
        const res = await fetch('/api/settlement/export' + (state.settlementDay ? `?day=${state.settlementDay}` : ''), { credentials: 'same-origin' });
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || t('error'));
        const a = document.createElement('a');
        a.href = URL.createObjectURL(await res.blob());
        a.download = `kedai-pos-settlement-${state.settlement?.day || 'today'}.csv`;
        a.click(); URL.revokeObjectURL(a.href);
        return;
      }
      case 'toggle-table':
        await api(`/api/tables/${data.id}`, { method: 'PUT', body: JSON.stringify({ active: data.active === '1' }) });
        state.tables = await api('/api/tables'); render();
        return;
      case 'print-table-qr':
        printTableQrs(data.id);
        return;
    }
  } catch (e) { toast(e.message || t('error')); return; }
  return baseHandleAction(action, data);
};

const baseBindPage = bindPage;
bindPage = function () {
  baseBindPage();
  document.getElementById('settlement-day')?.addEventListener('change', async e => {
    state.settlementDay = e.target.value;
    try { state.settlement = await api(`/api/settlement?day=${state.settlementDay}`); render(); } catch (err) { toast(err.message); }
  });
  document.getElementById('close-day-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    try {
      const r = await api('/api/settlement/close', { method: 'POST', body: JSON.stringify({ day: state.settlement.day, counted_cash: f.counted_cash, note: f.note }) });
      state.settlement = await api(`/api/settlement?day=${state.settlement.day}`); render();
      toast(`${t('day_closed')} · ${t('variance')}: ${money(r.variance_cents)}`);
    } catch (err) { toast(err.message); }
  });
  document.getElementById('refund-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.currentTarget, f = new FormData(form), o = state.modal.order;
    form.querySelector('button.danger').disabled = true;
    try {
      const r = await api(`/api/orders/${o.id}/refund`, { method: 'POST', body: JSON.stringify({
        amount: f.get('amount'), reason: f.get('reason'), restock: f.get('restock') === 'on' }) });
      state.modal = null; await refresh(); render();
      toast(`${t('refund_done')} · ${money(r.amount_cents)}`);
    } catch (err) { toast(err.message); form.querySelector('button.danger').disabled = false; }
  });
  document.getElementById('qr-ordering-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.currentTarget;
    try {
      await api('/api/settings', { method: 'POST', body: JSON.stringify({
        qr_ordering_enabled: form.querySelector('#qr-enabled').checked,
        public_base_url: form.elements.namedItem('public_base_url').value,
        qr_payment_methods: [...form.querySelectorAll('input[name="method"]:checked')].map(i => i.value) }) });
      await refresh(); render(); toast(t('settings_saved'));
    } catch (err) { toast(err.message); }
  });
  document.getElementById('add-table-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await api('/api/tables', { method: 'POST', body: JSON.stringify({ name: e.currentTarget.elements.namedItem('name').value }) });
      state.tables = await api('/api/tables'); render();
    } catch (err) { toast(err.message); }
  });
};
