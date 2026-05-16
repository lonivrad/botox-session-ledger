// ── State ──────────────────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let allClients  = [];
let allVials    = [];
let activeVials = [];
let vialFilter  = 'all';
let revenueChart = null;
let selectedClientId = null;

// ── Utilities ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const fmt$ = n => n != null ? '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2}) : '—';
const fmtPct = n => n != null ? Number(n).toFixed(1) + '%' : '—';
const fmtDate = d => d ? new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : '—';
const fmtDateShort = d => d ? new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : '—';

function marginClass(pct) {
  if (pct == null) return '';
  if (pct >= 15) return 'm-ok';
  if (pct >= 5)  return 'm-warn';
  return 'm-err';
}

function fmtDaysUntil(d) {
  if (!d) return '';
  const diff = Math.round((new Date(d) - new Date()) / 86400000);
  if (diff < 0)  return `<span style="color:var(--err);font-weight:600;">${Math.abs(diff)}d overdue</span>`;
  if (diff === 0) return `<span style="color:var(--warn);font-weight:600;">Today</span>`;
  if (diff <= 7)  return `<span style="color:var(--warn);font-weight:600;">in ${diff}d</span>`;
  return `<span style="color:var(--muted);">in ${diff}d</span>`;
}

function toast(msg, isErr = false) {
  const el = $('toast');
  el.innerHTML = (isErr
    ? `<svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`
    : `<svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`) + msg;
  el.className = 'toast show' + (isErr ? ' error' : '');
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.className = 'toast'; }, 3800);
}

// ── Navigation ─────────────────────────────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('[id^="page-"]').forEach(el => el.classList.add('hidden'));
  $(`page-${name}`)?.classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const navKey = name === 'client-detail' ? 'clients' : name;
  $(`nav-${navKey}`)?.classList.add('active');
  currentPage = name;
  if (name === 'dashboard') loadDashboard();
  if (name === 'clients')   loadClients();
  if (name === 'sessions')  loadSessions();
  if (name === 'vials')     loadVials();
  if (name === 'reports')   { loadRevenue('month'); loadWaste(); loadProfitability(); }
}

// ── Modals ─────────────────────────────────────────────────────────────────────
function openModal(id) {
  if (id === 'modal-new-session') refreshSessionFormSelects();
  $(id).classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}
function closeModal(id) {
  $(id).classList.add('hidden');
  document.body.style.overflow = '';
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-bg')) {
    e.target.classList.add('hidden');
    document.body.style.overflow = '';
  }
});

// ── Dashboard ─────────────────────────────────────────────────────────────────
function setGreeting() {
  const h = new Date().getHours();
  const greet = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  $('greeting').textContent = greet;
  $('greeting-date').textContent = new Date().toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'});
}

async function loadDashboard() {
  setGreeting();
  try {
    const [revenue, reorder, touchup, sessions, vialsResp] = await Promise.all([
      fetch('/analytics/revenue?period=month').then(r=>r.json()),
      fetch('/analytics/reorder-alert').then(r=>r.json()),
      fetch('/analytics/clients/touchup-due').then(r=>r.json()),
      fetch('/sessions').then(r=>r.json()),
      fetch('/vials/active').then(r=>r.json()),
    ]);

    // Revenue KPI
    const now = new Date();
    const mk = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    const tm = revenue.periods?.find(p => p.period === mk);
    $('kpi-revenue').textContent = tm ? fmt$(tm.total_revenue) : '$0.00';
    $('kpi-revenue-sub').textContent = tm ? `${fmt$(tm.gross_margin)} gross margin` : 'No sessions yet';

    // Sessions KPI
    $('kpi-sessions').textContent = tm ? tm.sessions : '0';
    $('kpi-sessions-sub').textContent = tm ? `${tm.total_units} total units` : 'No sessions this month';

    // Vials KPI
    $('kpi-vials').textContent = vialsResp.length;
    const totalRem = vialsResp.reduce((s,v) => s + (v.units_remaining||0), 0);
    $('kpi-vials-sub').textContent = vialsResp.length ? `${totalRem.toFixed(0)} units remaining` : 'No active vials';

    // Reorder KPI
    const rEl = $('kpi-reorder');
    const rIcon = $('kpi-reorder-icon');
    if (reorder.alert) {
      rEl.textContent = '⚠ Reorder now';
      rEl.style.color = 'var(--err)';
      rIcon.style.background = 'var(--err-bg)';
      rIcon.querySelector('svg').style.stroke = 'var(--err)';
    } else {
      rEl.textContent = '✓ Well stocked';
      rEl.style.color = 'var(--ok)';
      rIcon.style.background = 'var(--ok-bg)';
      rIcon.querySelector('svg').style.stroke = 'var(--ok)';
    }
    $('kpi-reorder-msg').textContent = reorder.message || '';

    // Touch-up list
    const tuEl = $('touchup-list');
    if (!touchup.length) {
      tuEl.innerHTML = '<div class="empty" style="padding:24px 0;"><div class="empty-icon">📅</div><div class="empty-title">No touch-ups due soon</div><div class="empty-desc">Clients with sessions will appear here as they approach the 14-week mark.</div></div>';
    } else {
      tuEl.innerHTML = touchup.map(c => `
        <div class="list-row">
          <span style="font-size:13.5px;font-weight:500;cursor:pointer;color:var(--text);" onclick="openClientDetail(${c.client_id})">${c.client_name}</span>
          <span style="font-size:12.5px;">${fmtDaysUntil(c.next_appointment_estimate)}</span>
        </div>`).join('');
    }

    // Recent sessions
    const recent = Array.isArray(sessions) ? sessions.slice(0, 6) : [];
    const rsEl = $('recent-sessions');
    if (!recent.length) {
      rsEl.innerHTML = '<div class="empty" style="padding:24px 0;"><div class="empty-icon">💉</div><div class="empty-title">No sessions yet</div><div class="empty-desc">Record your first session to get started.</div></div>';
    } else {
      rsEl.innerHTML = recent.map(s => `
        <div class="list-row">
          <div>
            <span style="font-size:13.5px;font-weight:500;">${s.client_name || '—'}</span>
            <span style="font-size:12px;color:var(--muted);margin-left:6px;">${s.total_units}u</span>
          </div>
          <div style="text-align:right;">
            <div style="font-size:13px;font-weight:600;">${fmt$(s.effective_charge)}</div>
            <div style="font-size:11.5px;color:var(--muted);">${fmtDateShort(s.session_date)}</div>
          </div>
        </div>`).join('');
    }
  } catch(e) { toast('Failed to load dashboard: ' + e.message, true); }
}

// ── Clients ───────────────────────────────────────────────────────────────────
async function loadClients() {
  try {
    allClients = await fetch('/clients').then(r=>r.json());
    renderClients(allClients);
  } catch(e) { toast('Failed to load clients: ' + e.message, true); }
}

function renderClients(list) {
  const tbody = $('clients-table');
  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty"><div class="empty-icon">👥</div><div class="empty-title">No clients yet</div><div class="empty-desc">Add your first client to start tracking sessions.</div></div></td></tr>`;
    return;
  }
  tbody.innerHTML = list.map(c => `
    <tr class="tbl-click" onclick="openClientDetail(${c.id})">
      <td class="tbl-td" style="font-weight:600;color:var(--primary);">${c.name}</td>
      <td class="tbl-td tbl-muted">${c.email || c.phone || '—'}</td>
      <td class="tbl-td" style="text-align:center;">${c.session_count}</td>
      <td class="tbl-td tbl-muted">${fmtDateShort(c.last_session_date)}</td>
      <td class="tbl-td">${c.next_appointment_estimate
        ? `<span style="font-size:13px;">${fmtDateShort(c.next_appointment_estimate)}</span> <span style="font-size:12px;">${fmtDaysUntil(c.next_appointment_estimate)}</span>`
        : '<span class="tbl-muted">—</span>'}</td>
      <td class="tbl-td" style="text-align:right;">
        <button class="btn-ghost" onclick="event.stopPropagation();openNewSessionForClientId(${c.id})" style="font-size:12px;">+ Session</button>
      </td>
    </tr>`).join('');
}

function filterClients(q) {
  const filtered = allClients.filter(c => c.name.toLowerCase().includes(q.toLowerCase()) || (c.email||'').toLowerCase().includes(q.toLowerCase()));
  renderClients(filtered);
}

async function openClientDetail(clientId) {
  selectedClientId = clientId;
  try {
    const [client, sessions] = await Promise.all([
      fetch(`/clients/${clientId}`).then(r=>r.json()),
      fetch(`/sessions?client_id=${clientId}`).then(r=>r.json()),
    ]);
    $('detail-client-name').textContent = client.name;
    $('detail-client-contact').textContent = [client.email, client.phone].filter(Boolean).join(' · ') || 'No contact info on file';
    $('detail-sessions').textContent = client.session_count;
    const rev = (Array.isArray(sessions) ? sessions : []).reduce((s,x) => s + (x.effective_charge||0), 0);
    $('detail-revenue').textContent = fmt$(rev);
    $('detail-next').textContent = client.next_appointment_estimate ? fmtDateShort(client.next_appointment_estimate) : '—';

    const tbody = $('detail-sessions-table');
    if (!sessions.length) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty" style="padding:28px 0;"><div class="empty-icon">💉</div><div class="empty-title">No sessions yet</div></div></td></tr>`;
    } else {
      tbody.innerHTML = sessions.map(s => `
        <tr>
          <td class="tbl-td">${fmtDateShort(s.session_date)}</td>
          <td class="tbl-td" style="font-weight:600;">${s.total_units}u</td>
          <td class="tbl-td tbl-muted">—</td>
          <td class="tbl-td">${fmt$(s.effective_charge)}</td>
          <td class="tbl-td ${marginClass(s.gross_margin_percent)}">${fmtPct(s.gross_margin_percent)}</td>
          <td class="tbl-td" style="text-align:right;"><button class="btn-ghost" style="font-size:12px;" onclick="viewSession(${s.id})">View</button></td>
        </tr>`).join('');
    }
    showPage('client-detail');
  } catch(e) { toast('Failed to load client: ' + e.message, true); }
}

function openNewSessionForClient() { openNewSessionForClientId(selectedClientId); }
function openNewSessionForClientId(clientId) {
  showPage('sessions');
  setTimeout(() => {
    openModal('modal-new-session');
    if (clientId) $('session-client-select').value = clientId;
  }, 80);
}

$('form-add-client').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const data = Object.fromEntries([...fd.entries()].filter(([,v]) => v));
  try {
    await fetch('/clients', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
    toast('Client added successfully');
    closeModal('modal-add-client');
    e.target.reset();
    loadClients();
  } catch(err) { toast('Error: ' + err.message, true); }
});

// ── Sessions ──────────────────────────────────────────────────────────────────
async function loadSessions() {
  try {
    const sessions = await fetch('/sessions').then(r=>r.json());
    const tbody = $('sessions-table');
    if (!sessions.length) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty"><div class="empty-icon">📄</div><div class="empty-title">No sessions recorded</div><div class="empty-desc">Sessions will appear here after you record them.</div></div></td></tr>`;
      return;
    }
    tbody.innerHTML = sessions.map(s => `
      <tr class="tbl-click" onclick="viewSession(${s.id})">
        <td class="tbl-td tbl-muted">${fmtDate(s.session_date)}</td>
        <td class="tbl-td" style="font-weight:600;">${s.client_name || '—'}</td>
        <td class="tbl-td">${s.total_units}u</td>
        <td class="tbl-td">${fmt$(s.effective_charge)}</td>
        <td class="tbl-td ${marginClass(s.gross_margin_percent)}">${fmtPct(s.gross_margin_percent)}</td>
      </tr>`).join('');
  } catch(e) { toast('Failed to load sessions: ' + e.message, true); }
}

async function viewSession(id) {
  try {
    const s = await fetch(`/sessions/${id}`).then(r=>r.json());
    $('session-detail-content').innerHTML = `
      <div class="ig" style="margin-bottom:16px;">
        <div class="ig-cell"><div class="ig-label">Client</div><div class="ig-value">${s.client_name||'—'}</div></div>
        <div class="ig-cell"><div class="ig-label">Date</div><div class="ig-value">${fmtDate(s.session_date)}</div></div>
        <div class="ig-cell"><div class="ig-label">Total units</div><div class="ig-value" style="color:var(--primary);">${s.total_units}u</div></div>
        <div class="ig-cell"><div class="ig-label">Total volume</div><div class="ig-value">${s.total_volume_ml?.toFixed(2)} mL</div></div>
        <div class="ig-cell"><div class="ig-label">Session cost</div><div class="ig-value">${fmt$(s.total_session_cost)}</div></div>
        <div class="ig-cell"><div class="ig-label">Charge</div><div class="ig-value">${fmt$(s.effective_charge)}</div></div>
        <div class="ig-cell"><div class="ig-label">Gross margin</div><div class="ig-value">${fmt$(s.gross_margin)}</div></div>
        <div class="ig-cell"><div class="ig-label">Margin %</div><div class="ig-value ${marginClass(s.gross_margin_percent)}">${fmtPct(s.gross_margin_percent)}</div></div>
      </div>
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin-bottom:10px;">Treatment Areas</div>
      <table class="tbl" style="border:1px solid var(--border);border-radius:10px;overflow:hidden;">
        <thead><tr>
          <th class="tbl-th" style="border-radius:0;">Area</th>
          <th class="tbl-th" style="text-align:right;">Units</th>
          <th class="tbl-th" style="text-align:right;">Volume</th>
          <th class="tbl-th" style="text-align:right;">U-100</th>
        </tr></thead>
        <tbody>${(s.areas||[]).map(a=>`
          <tr>
            <td class="tbl-td">${a.area_name}</td>
            <td class="tbl-td" style="text-align:right;font-weight:600;">${a.units}u</td>
            <td class="tbl-td" style="text-align:right;">${a.volume_ml?.toFixed(2)} mL</td>
            <td class="tbl-td" style="text-align:right;">${a.u100_markings?.toFixed(0)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      ${s.notes ? `<div style="margin-top:14px;background:var(--warn-bg);border-radius:8px;padding:12px 14px;font-size:13px;color:var(--text2);"><span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--warn);display:block;margin-bottom:4px;">Notes</span>${s.notes}</div>` : ''}
    `;
    openModal('modal-session-detail');
  } catch(e) { toast('Failed to load session: ' + e.message, true); }
}

async function refreshSessionFormSelects() {
  try {
    const [cl, vl] = await Promise.all([fetch('/clients').then(r=>r.json()), fetch('/vials/active').then(r=>r.json())]);
    allClients = cl; activeVials = vl;
    $('session-client-select').innerHTML = '<option value="">Select client…</option>' +
      cl.map(c=>`<option value="${c.id}">${c.name}</option>`).join('');
    $('session-vial-select').innerHTML = '<option value="">Select active vial…</option>' +
      vl.map(v=>`<option value="${v.id}">${v.product} · ${v.units_remaining.toFixed(1)}u left · ${v.concentration.toFixed(0)} u/mL</option>`).join('');
  } catch(e) { console.error(e); }
}

$('session-pricing-mode').addEventListener('change', e => {
  $('custom-price-field').classList.toggle('hidden', e.target.value !== 'custom');
});

$('form-new-session').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const data = {
    client_id: parseInt(fd.get('client_id')),
    vial_id: parseInt(fd.get('vial_id')),
    treatment_plan: fd.get('treatment_plan'),
    pricing_mode: fd.get('pricing_mode'),
    client_charge: fd.get('client_charge') || null,
    custom_price: fd.get('custom_price') || null,
    notes: fd.get('notes') || null,
  };
  try {
    const session = await fetch('/sessions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)})
      .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.detail); }); return r.json(); });
    toast(`Session saved — ${session.total_units}u · ${fmt$(session.effective_charge)} · ${fmtPct(session.gross_margin_percent)} margin`);
    closeModal('modal-new-session');
    e.target.reset();
    loadSessions();
    loadVials();
  } catch(err) { toast(err.message, true); }
});

// ── Vials ─────────────────────────────────────────────────────────────────────
async function loadVials() {
  try {
    allVials = await fetch('/vials').then(r=>r.json());
    renderVials();
  } catch(e) { toast('Failed to load vials: ' + e.message, true); }
}

function filterVials(status) {
  vialFilter = status;
  document.querySelectorAll('[data-vf]').forEach(el => {
    el.classList.toggle('active', el.dataset.vf === status);
  });
  renderVials();
}

function renderVials() {
  const list = vialFilter === 'all' ? allVials : allVials.filter(v => v.status === vialFilter);
  const grid = $('vials-grid');
  if (!list.length) {
    grid.innerHTML = `<div style="grid-column:1/-1;"><div class="empty"><div class="empty-icon">🧪</div><div class="empty-title">No vials ${vialFilter === 'all' ? 'recorded' : `with status "${vialFilter}"`}</div><div class="empty-desc">${vialFilter === 'all' ? 'Open a vial to start tracking inventory.' : 'Try a different filter.'}</div></div></div>`;
    return;
  }
  grid.innerHTML = list.map(v => {
    const badgeCls = { active:'badge-active', expired:'badge-expired', depleted:'badge-depleted', unopened:'badge-unopened' }[v.status] || 'badge-depleted';
    const remPct = Math.max(0, Math.min(100, 100 - (v.percent_used_pct||0)));
    const fillColor = remPct > 50 ? 'var(--ok)' : remPct > 20 ? 'var(--warn)' : 'var(--err)';
    const expColor  = v.status === 'active' ? 'var(--warn)' : 'var(--muted)';
    return `
    <div class="vcard">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:14px;">
        <div>
          <div style="font-size:15px;font-weight:700;">${v.product}</div>
          ${v.lot_number ? `<div style="font-size:11.5px;color:var(--muted);margin-top:2px;">Lot ${v.lot_number}</div>` : ''}
        </div>
        <span class="badge ${badgeCls}">${v.status}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px;">
        <div>
          <div style="font-size:10.5px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:3px;">Remaining</div>
          <div style="font-size:18px;font-weight:700;color:var(--primary);letter-spacing:-0.02em;">${v.units_remaining.toFixed(1)}<span style="font-size:12px;font-weight:500;"> u</span></div>
        </div>
        <div>
          <div style="font-size:10.5px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:3px;">Conc.</div>
          <div style="font-size:16px;font-weight:600;">${v.concentration.toFixed(0)}<span style="font-size:11px;font-weight:500;"> u/mL</span></div>
        </div>
        <div>
          <div style="font-size:10.5px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:3px;">Expires</div>
          <div style="font-size:13px;font-weight:600;color:${expColor};">${fmtDateShort(v.expires_at)}</div>
        </div>
      </div>
      <div class="prog-track">
        <div class="prog-fill" style="width:${remPct}%;background:${fillColor};"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:6px;">
        <span style="font-size:11.5px;color:var(--muted);">${remPct.toFixed(0)}% remaining</span>
        <span style="font-size:11.5px;color:var(--muted);">${(v.units_used||0).toFixed(1)}u used of ${v.units_total}u</span>
      </div>
    </div>`;
  }).join('');
}

$('form-open-vial').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const data = {
    product: fd.get('product') || 'Botox',
    lot_number: fd.get('lot_number') || null,
    units_total: parseFloat(fd.get('units_total')),
    diluent_ml: parseFloat(fd.get('diluent_ml')),
    cost: parseFloat(fd.get('cost')),
    expiry_hours: parseInt(fd.get('expiry_hours')),
  };
  try {
    const vial = await fetch('/vials', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)})
      .then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.detail); }); return r.json(); });
    toast(`Vial opened — ${vial.concentration.toFixed(0)} u/mL · expires ${fmtDateShort(vial.expires_at)}`);
    closeModal('modal-open-vial');
    e.target.reset();
    $('concentration-preview').textContent = 'Enter diluent amount to see concentration';
    loadVials();
  } catch(err) { toast(err.message, true); }
});

// Live concentration preview
document.querySelector('[name="diluent_ml"]').addEventListener('input', e => {
  const ml = parseFloat(e.target.value);
  const units = parseFloat(document.querySelector('[name="units_total"]').value) || 100;
  const el = $('concentration-preview');
  el.textContent = ml > 0 ? `Concentration: ${(units/ml).toFixed(1)} units/mL (${(1/(units/ml)*100).toFixed(1)} U-100 markings per unit)` : 'Enter diluent amount to see concentration';
});

// ── Reports ───────────────────────────────────────────────────────────────────
async function loadRevenue(period) {
  $('btn-period-month').className   = 'ptbtn' + (period === 'month'   ? ' active' : '');
  $('btn-period-quarter').className = 'ptbtn' + (period === 'quarter' ? ' active' : '');
  try {
    const data = await fetch(`/analytics/revenue?period=${period}`).then(r=>r.json());
    const periods  = data.periods || [];
    const labels   = periods.map(p => p.period);
    const revenues = periods.map(p => p.total_revenue);
    const margins  = periods.map(p => p.gross_margin);

    // Populate summary KPIs from totals
    const t = data.totals;
    if (t) {
      $('rpt-total-revenue').textContent = fmt$(t.total_revenue);
      $('rpt-revenue-sub').textContent   = `${t.sessions} sessions · ${fmt$(t.total_cost)} cost`;
      $('rpt-avg-margin').textContent    = fmtPct(t.gross_margin_percent);
      $('rpt-margin-sub').textContent    = `${fmt$(t.gross_margin)} gross profit`;
      $('rpt-chart-sub').textContent     = `${t.sessions} sessions total`;
    }

    // Period breakdown table
    const ptbody = $('period-table');
    if (!periods.length) {
      ptbody.innerHTML = `<tr><td colspan="3" class="tbl-td" style="text-align:center;color:var(--muted);padding:20px;">No data</td></tr>`;
    } else {
      ptbody.innerHTML = [...periods].reverse().map(p => `
        <tr>
          <td class="tbl-td" style="padding:9px 14px;font-weight:500;">${p.period}</td>
          <td class="tbl-td" style="padding:9px 14px;text-align:right;">${fmt$(p.total_revenue)}</td>
          <td class="tbl-td ${marginClass(p.gross_margin_percent)}" style="padding:9px 14px;text-align:right;">${fmtPct(p.gross_margin_percent)}</td>
        </tr>`).join('');
    }

    const ctx = $('revenue-chart').getContext('2d');
    if (revenueChart) revenueChart.destroy();
    revenueChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Revenue',      data: revenues, backgroundColor: '#C04F7B', borderRadius: 5, borderSkipped: false },
          { label: 'Gross Margin', data: margins,  backgroundColor: '#F3BDCF', borderRadius: 5, borderSkipped: false },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 10, font: { size: 12, family: 'Inter' }, padding: 16 } },
          tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: $${Number(ctx.parsed.y).toLocaleString('en-US',{minimumFractionDigits:2})}` } }
        },
        scales: {
          y: { beginAtZero: true, grid: { color: '#F2F1EC' }, ticks: { font: { size: 11, family: 'Inter' }, callback: v => '$' + Number(v).toLocaleString() } },
          x: { grid: { display: false }, ticks: { font: { size: 11, family: 'Inter' } } }
        }
      },
    });
  } catch(e) { toast('Failed to load revenue: ' + e.message, true); }
}

async function loadWaste() {
  try {
    const w = await fetch('/analytics/vials/waste').then(r=>r.json());

    // Populate top KPI
    const wasteKpi = $('rpt-waste-cost');
    if (wasteKpi) {
      wasteKpi.textContent = fmt$(w.estimated_waste_cost);
      wasteKpi.style.color = w.estimated_waste_cost > 0 ? 'var(--err)' : 'var(--ok)';
      $('rpt-waste-sub').textContent = w.estimated_waste_cost > 0
        ? `${w.estimated_waste_units}u across ${w.total_vials_expired} expired vial${w.total_vials_expired !== 1 ? 's' : ''}`
        : 'No vial waste recorded';
    }

    // Inline waste card
    const deplPct = w.total_vials_opened > 0 ? Math.round(w.total_vials_depleted / w.total_vials_opened * 100) : 0;
    $('waste-summary').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
        <div class="stat-box">
          <div class="stat-box-label">Opened</div>
          <div class="stat-box-value">${w.total_vials_opened}</div>
        </div>
        <div class="stat-box">
          <div class="stat-box-label">Depleted</div>
          <div class="stat-box-value" style="color:var(--ok);">${w.total_vials_depleted}</div>
        </div>
        <div class="stat-box">
          <div class="stat-box-label">Expired</div>
          <div class="stat-box-value" style="color:${w.total_vials_expired > 0 ? 'var(--err)' : 'var(--text)'};">${w.total_vials_expired}</div>
        </div>
        <div class="stat-box">
          <div class="stat-box-label">Depletion rate</div>
          <div class="stat-box-value" style="color:${deplPct >= 80 ? 'var(--ok)' : deplPct >= 50 ? 'var(--warn)' : 'var(--err)'};">${deplPct}%</div>
        </div>
      </div>
      ${w.estimated_waste_cost > 0
        ? `<div style="background:var(--err-bg);border-radius:10px;padding:12px 14px;">
            <div style="font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--err);margin-bottom:3px;">Waste cost</div>
            <div style="font-size:22px;font-weight:700;color:var(--err);letter-spacing:-0.02em;">${fmt$(w.estimated_waste_cost)}</div>
            <div style="font-size:11.5px;color:var(--err);opacity:0.7;margin-top:2px;">${w.estimated_waste_units}u lost</div>
           </div>`
        : `<div style="background:var(--ok-bg);border-radius:10px;padding:12px 14px;display:flex;align-items:center;gap:8px;">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="var(--ok)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            <span style="font-size:13px;font-weight:600;color:var(--ok);">No waste — all vials fully used</span>
           </div>`}`;
  } catch(e) { console.error(e); }
}

async function loadProfitability() {
  try {
    const data = await fetch('/analytics/clients/profitability').then(r=>r.json());
    const tbody = $('profitability-table');
    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty" style="padding:32px 0;"><div class="empty-icon">📊</div><div class="empty-title">No data yet</div></div></td></tr>`;
      return;
    }
    tbody.innerHTML = data.map(c => `
      <tr class="tbl-click" onclick="openClientDetail(${c.client_id})">
        <td class="tbl-td" style="font-weight:600;color:var(--primary);">${c.client_name}</td>
        <td class="tbl-td" style="text-align:center;">${c.sessions}</td>
        <td class="tbl-td" style="text-align:right;">${fmt$(c.total_revenue)}</td>
        <td class="tbl-td" style="text-align:right;">${fmt$(c.gross_margin)}</td>
        <td class="tbl-td ${marginClass(c.gross_margin_percent)}" style="text-align:right;">${fmtPct(c.gross_margin_percent)}</td>
      </tr>`).join('');
  } catch(e) { console.error(e); }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
loadDashboard();
