/* ===========================================================================
   Mebel Pro — shared client-side helpers
   Toasts · modals · menus · branch picker · mobile drawer · UZS formatting
   =========================================================================== */

// ---------- UZS formatting ----------
window.fmt = n => (n || 0).toLocaleString('uz-UZ').replace(/,/g, ' ');
window.fmtSum = n => `${fmt(n)} so'm`;
window.fmtTiyin = t => fmtSum(Math.round((t || 0) / 100));

// ---------- Toast ----------
let _toastTimer = null;
window.toast = (msg, kind = 'ok') => {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    el.className = 'toast';
    el.innerHTML = '<span class="ic"></span><span class="msg"></span>';
    document.body.appendChild(el);
  }
  const ic = el.querySelector('.ic');
  ic.className = 'ic';
  if (kind === 'warn') ic.classList.add('warn');
  if (kind === 'danger') ic.classList.add('danger');
  const icName = kind === 'danger' ? 'x' : kind === 'warn' ? 'alert' : 'check';
  ic.innerHTML = window.icon ? window.icon(icName, { size: 13 }) : '';
  el.querySelector('.msg').textContent = msg;
  el.classList.add('on');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('on'), 2600);
};

// ---------- Modal ----------
const _focusableSel = [
  'a[href]', 'area[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])'
].join(',');
const _activeModal = () => [...document.querySelectorAll('.modal.on')].at(-1);
const _modalFocusables = modal =>
  [...modal.querySelectorAll(_focusableSel)].filter(el =>
    !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));

window.openModal = (id) => {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal._returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  if (!modal.hasAttribute('role')) modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  if (!modal.hasAttribute('tabindex')) modal.setAttribute('tabindex', '-1');
  modal.classList.add('on');
  document.getElementById('scrim')?.classList.add('on');
  document.body.classList.add('modal-open');
  requestAnimationFrame(() => {
    const fieldFirst = [
      'input:not([disabled]):not([type="hidden"])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      'button:not([disabled]):not(.x):not([data-close-modal])'
    ].join(',');
    const target = modal.querySelector('[data-initial-focus]') || modal.querySelector(fieldFirst) || _modalFocusables(modal)[0] || modal;
    target.focus?.({ preventScroll: true });
  });
};
window.closeModal = (id) => {
  const modals = id ? [document.getElementById(id)].filter(Boolean) : [...document.querySelectorAll('.modal.on')];
  modals.forEach(modal => {
    modal.classList.remove('on');
    const returnFocus = modal._returnFocus;
    if (modal.dataset.removeOnClose === 'true') setTimeout(() => modal.remove(), 220);
    if (returnFocus && document.contains(returnFocus)) {
      setTimeout(() => returnFocus.focus?.({ preventScroll: true }), 0);
    }
  });
  if (!document.querySelector('.modal.on')) {
    document.getElementById('scrim')?.classList.remove('on');
    document.body.classList.remove('modal-open');
  }
};

// Wire up generic close behaviour
document.addEventListener('click', e => {
  if (e.target.matches('[data-close-modal]')) {
    e.preventDefault();
    closeModal(e.target.dataset.closeModal || null);
  }
  if (e.target.id === 'scrim') closeModal();
});

// ---------- Dropdown menus ----------
// Capture phase: runs before any ancestor's stopPropagation() (row/card nav
// guards), so the action menu always opens even inside a clickable card/row.
document.addEventListener('click', e => {
  // open/close
  const trigger = e.target.closest('[data-menu-toggle]');
  if (trigger) {
    e.preventDefault();
    e.stopPropagation();
    const wrap = trigger.closest('.menu-wrap');
    const menu = wrap?.querySelector('.menu');
    if (!menu) return;
    const wasOpen = menu.classList.contains('on');
    document.querySelectorAll('.menu.on').forEach(m => {
      m.classList.remove('on');
      m.closest('.menu-wrap')?.querySelector('[data-menu-toggle]')?.setAttribute('aria-expanded', 'false');
    });
    if (!wasOpen) {
      menu.classList.add('on');
      trigger.setAttribute('aria-expanded', 'true');
      trigger.setAttribute('aria-haspopup', 'true');
    } else {
      trigger.setAttribute('aria-expanded', 'false');
    }
    return;
  }
  // outside click closes
  if (!e.target.closest('.menu')) {
    document.querySelectorAll('.menu.on').forEach(m => {
      m.classList.remove('on');
      m.closest('.menu-wrap')?.querySelector('[data-menu-toggle]')?.setAttribute('aria-expanded', 'false');
    });
  }
}, true);

// ---------- Branch picker pop ----------
window.toggleBranchPop = (e) => {
  e?.stopPropagation();
  const pop = document.getElementById('br-pop');
  if (!pop) return;
  const open = !pop.hidden;
  document.querySelectorAll('.br-pop').forEach(p => p.hidden = true);
  pop.hidden = open;
};
document.addEventListener('click', e => {
  if (!e.target.closest('.br-picker')) {
    document.querySelectorAll('.br-pop').forEach(p => p.hidden = true);
  }
});

// ---------- Mobile drawer ----------
window.toggleDrawer = () => {
  let drawer = document.getElementById('mob-drawer');
  if (!drawer) {
    const sb = document.querySelector('aside.sb');
    if (!sb) return;
    drawer = document.createElement('div');
    drawer.id = 'mob-drawer';
    drawer.className = 'drawer';
    drawer.innerHTML = sb.innerHTML;
    document.body.appendChild(drawer);
  }
  let scrim = document.getElementById('drawer-scrim');
  if (!scrim) {
    scrim = document.createElement('div');
    scrim.id = 'drawer-scrim';
    scrim.className = 'scrim';
    scrim.onclick = () => toggleDrawer();
    document.body.appendChild(scrim);
  }
  const on = drawer.classList.toggle('on');
  scrim.classList.toggle('on', on);
};

// ---------- Tabs ----------
window.switchTab = (id, targetId) => {
  const tabs = document.querySelectorAll(`[data-tabs="${id}"] .tab`);
  tabs.forEach(t => t.classList.toggle('on', t.dataset.target === targetId));
  document.querySelectorAll(`[data-panel-group="${id}"]`).forEach(p => {
    p.hidden = p.id !== targetId;
  });
};

// ---------- Confirm dialog (replaces window.confirm) ----------
window.confirmAction = (opts, onConfirm) => {
  const o = typeof opts === 'string' ? { msg: opts } : opts || {};
  const html = `
    <div class="modal" id="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" data-remove-on-close="true">
      <div class="modal-h">
        <h3 id="confirm-title">${o.title || 'Tasdiqlash'}</h3>
        <button class="x" type="button" data-close-modal="confirm-modal" aria-label="Yopish">✕</button>
      </div>
      <div class="modal-b">
        <p style="margin:0;color:var(--ink-8);font-size:14px;line-height:1.5">${o.msg || 'Davom etishni xohlaysizmi?'}</p>
        ${o.reasonField ? `<div class="field" style="margin-top:14px"><label for="confirm-reason">${o.reasonLabel || 'Sabab'} *</label><textarea id="confirm-reason" rows="3" placeholder="Sababni yozing..." data-initial-focus></textarea></div>` : ''}
      </div>
      <div class="modal-f">
        <button class="btn btn-outline" type="button" data-close-modal="confirm-modal">Bekor qilish</button>
        <button class="btn ${o.danger ? 'btn-danger' : 'btn-acc'}" type="button" id="confirm-ok"${o.reasonField ? '' : ' data-initial-focus'}>${o.okText || 'Davom etish'}</button>
      </div>
    </div>`;
  let scrim = document.getElementById('scrim');
  if (!scrim) {
    scrim = document.createElement('div');
    scrim.id = 'scrim';
    scrim.className = 'scrim';
    document.body.appendChild(scrim);
  }
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  const modal = wrap.firstElementChild;
  document.body.appendChild(modal);
  openModal('confirm-modal');
  modal.querySelector('#confirm-ok').onclick = () => {
    const reason = modal.querySelector('#confirm-reason')?.value?.trim();
    if (o.reasonField && !reason) {
      toast('Sabab kiritilishi shart', 'warn');
      modal.querySelector('#confirm-reason')?.focus();
      return;
    }
    closeModal('confirm-modal');
    onConfirm && onConfirm(reason);
  };
};

// ---------- One-time-secret confirmation (create / reset) ----------
// ONE standardised component reused across create-workshop, create-operator,
// and reset-password. Shows a credential exactly once, with a copy button and
// the "faqat bir marta ko'rsatiladi" warning. Keyboard-operable.
window.showSecret = (opts) => {
  const o = opts || {};
  const rows = (o.rows || []).map(r => `
    <div class="secret-row">
      <div class="secret-row-l"><span class="k">${r.k}</span><span class="v num" data-secret-val>${r.v}</span></div>
      <button class="btn btn-outline btn-sm" type="button" data-copy="${String(r.v).replace(/"/g, '&quot;')}">Nusxa</button>
    </div>`).join('');
  const html = `
    <div class="modal" id="secret-modal" role="dialog" aria-modal="true" aria-labelledby="secret-title" data-remove-on-close="true">
      <div class="modal-h">
        <h3 id="secret-title">${o.title || 'Maxfiy ma\'lumot'}</h3>
        <button class="x" type="button" data-close-modal="secret-modal" aria-label="Yopish">✕</button>
      </div>
      <div class="modal-b">
        <div class="banner warn"><div class="ic">!</div><div class="grow">${o.note || 'Bu ma\'lumot faqat bir marta ko\'rsatiladi — egasiga yetkazib, saqlab oling.'}</div></div>
        <div class="secret-box">${rows}</div>
        ${o.hint ? `<p style="margin:12px 0 0;color:var(--ink-6);font-size:12.5px">${o.hint}</p>` : ''}
      </div>
      <div class="modal-f">
        <button class="btn btn-outline btn-sm" type="button" id="secret-copy-all">Hammasini nusxalash</button>
        <button class="btn btn-acc" type="button" data-close-modal="secret-modal" data-initial-focus>Yopdim · saqladim</button>
      </div>
    </div>`;
  let scrim = document.getElementById('scrim');
  if (!scrim) {
    scrim = document.createElement('div');
    scrim.id = 'scrim';
    scrim.className = 'scrim';
    document.body.appendChild(scrim);
  }
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  const modal = wrap.firstElementChild;
  document.body.appendChild(modal);
  const copy = (txt) => {
    navigator.clipboard?.writeText(txt).then(() => toast('Nusxalandi')).catch(() => toast('Nusxalab bo\'lmadi', 'warn'));
  };
  modal.querySelectorAll('[data-copy]').forEach(b => b.onclick = () => copy(b.dataset.copy));
  modal.querySelector('#secret-copy-all').onclick = () =>
    copy((o.rows || []).map(r => `${r.k}: ${r.v}`).join('\n'));
  modal.addEventListener('click', e => {
    if (e.target.matches('[data-close-modal]')) {
      closeModal('secret-modal');
      o.onClose && o.onClose();
    }
  });
  openModal('secret-modal');
};

// ---------- Password reset warning (non-blocking) ----------
window.passwordResetRequired = (scope, principal = {}) => {
  const key = `mp.${scope}.password-reset-required`;
  const qp = new URLSearchParams(location.search);
  const fromQuery = qp.get('reset') === '1' || qp.get('password_reset_required') === '1';
  if (fromQuery) {
    try { sessionStorage.setItem(key, '1'); } catch (_) {}
  }
  let fromSession = false;
  try { fromSession = sessionStorage.getItem(key) === '1'; } catch (_) {}
  return !!principal.passwordResetRequired || fromQuery || fromSession;
};

window.clearPasswordResetRequired = (scope) => {
  try { sessionStorage.removeItem(`mp.${scope}.password-reset-required`); } catch (_) {}
  document.getElementById(`pw-reset-warning-${scope}`)?.remove();
};

window.renderPasswordResetWarning = (scope, profileHref, principal = {}) => {
  if (!window.passwordResetRequired(scope, principal)) return;
  if (document.getElementById(`pw-reset-warning-${scope}`)) return;
  const html = `
    <div class="banner warn" id="pw-reset-warning-${scope}" role="status">
      <div class="ic">${window.icon ? window.icon('alert', { size: 14 }) : '!'}</div>
      <div class="grow">Vaqtinchalik parol ishlatyapsiz. Ishni davom ettirishingiz mumkin, lekin parolni profil orqali yangilang.</div>
      <a class="btn btn-outline btn-sm" href="${profileHref}">Parolni o'zgartirish</a>
    </div>`;
  const mount = document.querySelector('main.page-content .page') || document.getElementById('page-shell');
  mount?.insertAdjacentHTML('afterbegin', html);
};

// ---------- Password strength (≥8, upper + lower + digit) ----------
window.pwStrength = (v) => {
  v = v || '';
  const hasU = /[A-Z]/.test(v), hasL = /[a-z]/.test(v), hasD = /\d/.test(v), len = v.length >= 8;
  const score = [hasU, hasL, hasD, len].filter(Boolean).length;
  const ok = hasU && hasL && hasD && len;
  return { ok, score, hasU, hasL, hasD, len };
};
window.genTempPassword = () => {
  const U = 'ABCDEFGHJKLMNPQRSTUVWXYZ', L = 'abcdefghijkmnpqrstuvwxyz', D = '23456789';
  const pick = s => s[Math.floor(Math.random() * s.length)];
  let p = pick(U) + pick(L) + pick(D);
  const all = U + L + D;
  for (let i = 0; i < 7; i++) p += pick(all);
  return p.split('').sort(() => Math.random() - 0.5).join('') + '!';
};

// ---------- Prototype state demo (?state=loading|empty|error) ----------
// Lets any data screen demonstrate its loading / empty / error states without
// a backend. Screens read window.demoState() and branch their render.
window.demoState = () => new URLSearchParams(location.search).get('state') || 'ready';
window.skRows = (cols, n = 6) => {
  let body = '';
  for (let r = 0; r < n; r++) {
    body += '<tr>';
    for (let c = 0; c < cols; c++) body += `<td><div class="sk-line w-${c === 0 ? '80' : '60'}" style="margin:2px 0"></div></td>`;
    body += '</tr>';
  }
  return body;
};
// Map any legacy Unicode glyph (still passed by some pages) → an icon name.
window._glyphIcon = g => ({
  '∅': 'inbox', '▥': 'layers', '⊞': 'grid', '⌥': 'activity', '◆': 'users',
  '≡': 'list', '✓': 'check-circle', '⊟': 'box', '!': 'alert', '▣': 'orders',
}[g] || (window.MP_ICONS && window.MP_ICONS[g] ? g : 'inbox'));

window.errState = (msg, traceId) => `
  <div class="st-error" role="alert">
    <div class="ic">${window.icon('alert', { size: 26 })}</div>
    <h3>Ma'lumotni yuklab bo'lmadi</h3>
    <p>${msg || 'Server bilan bog\'lanishda xatolik yuz berdi.'}</p>
    <p class="trace">trace_id: <b>${traceId || 'tr-' + Math.random().toString(16).slice(2, 8)}</b></p>
    <button class="btn btn-outline" type="button" onclick="location.reload()">${window.icon('refresh', { size: 13 })} Qayta urinish</button>
  </div>`;
window.emptyState = (icon, title, body) => `
  <div class="st-empty">
    <div class="ic">${window.icon(window._glyphIcon(icon || '∅'), { size: 25 })}</div>
    <h3>${title || 'Hozircha bo\'sh'}</h3>
    ${body ? `<p>${body}</p>` : ''}
  </div>`;

// ---------- Active nav helper ----------
window.markActiveNav = (key) => {
  document.querySelectorAll('.sb-it').forEach(el => {
    el.classList.toggle('on', el.dataset.nav === key);
  });
  document.querySelectorAll('.hdr-nav a').forEach(el => {
    el.classList.toggle('on', el.dataset.nav === key);
  });
};

// ---------- Tiny SVG sparkline / bar chart helper ----------
window.renderChart = (svg, data, opts = {}) => {
  if (!svg) return;
  const W = 640, H = 200, gap = 4, w = (W - gap * (data.length - 1)) / data.length;
  const max = Math.max(...data, 1);
  const bars = svg.querySelector('.bars');
  const highest = data.indexOf(max);
  const todayIdx = opts.todayIdx ?? data.length - 1;
  bars.innerHTML = data.map((v, i) => {
    const h = (v / max) * (H - 40);
    const y = H - 30 - h;
    const cls = i === todayIdx ? 'hi' : i === highest ? 'md' : '';
    const x = i * (w + gap);
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="2" class="${cls}">
      <title>${opts.labels?.[i] || ''} — ${fmt(v)}</title></rect>`;
  }).join('');
};

// ---------- Stop noisy <a href="#"> from jumping ----------
document.addEventListener('click', e => {
  const a = e.target.closest('a[href="#"]');
  if (a) { e.preventDefault(); }
});

// ---------- Highlight current page in nav based on filename ----------
window.autoMarkNav = () => {
  const file = location.pathname.split('/').pop();
  document.querySelectorAll('.sb-it[data-href], .hdr-nav a[data-href]').forEach(el => {
    el.classList.toggle('on', el.dataset.href === file);
  });
};
document.addEventListener('DOMContentLoaded', autoMarkNav);

// ---------- Static prototype accessibility helpers ----------
window.wrapTables = (root = document) => {
  root.querySelectorAll('table.tbl').forEach(tbl => {
    if (tbl.closest('.table-wrap')) return;
    const wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    tbl.parentNode.insertBefore(wrap, tbl);
    wrap.appendChild(tbl);
  });
};

window.labelPrototypeControls = (root = document) => {
  root.querySelectorAll('input[placeholder], textarea[placeholder]').forEach(el => {
    if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return;
    if (el.id && document.querySelector(`label[for="${el.id}"]`)) return;
    const text = (el.getAttribute('placeholder') || '').replace(/[.…]+$/g, '').trim();
    if (text) el.setAttribute('aria-label', text);
  });
  root.querySelectorAll('select').forEach(el => {
    if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return;
    if (el.id && document.querySelector(`label[for="${el.id}"]`)) return;
    const opt = el.options?.[0]?.textContent?.trim();
    if (opt) el.setAttribute('aria-label', opt);
  });
};

window.makeClickableTargetsAccessible = (root = document) => {
  const sel = [
    'tr.clickable', '.row-item.clickable', '.kpi[onclick]', '.board-card[onclick]',
    '.ord-card[onclick]', '.prod-cell[onclick]', 'article[onclick]', 'div[onclick]'
  ].join(',');
  root.querySelectorAll(sel).forEach(el => {
    if (el.matches('button,a,input,select,textarea') || el.dataset.a11yClick === '1') return;
    el.dataset.a11yClick = '1';
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    if (!el.hasAttribute('role')) {
      const onclick = el.getAttribute('onclick') || '';
      el.setAttribute('role', onclick.includes('location.href') ? 'link' : 'button');
    }
    if (!el.getAttribute('aria-label')) {
      const text = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (text) el.setAttribute('aria-label', text.slice(0, 140));
    }
    el.addEventListener('keydown', e => {
      if (e.target !== el) return;
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      el.click();
    });
  });
};

window.normalizeMenuButtons = (root = document) => {
  root.querySelectorAll('.menu-btn[data-menu-toggle], button[data-menu-toggle]').forEach(btn => {
    if (!btn.getAttribute('aria-label')) btn.setAttribute('aria-label', 'Amallar');
    if (btn.dataset.menuIconDone === '1') return;
    const raw = (btn.textContent || '').trim();
    if (raw === '⋯' || raw === '...') {
      btn.innerHTML = window.icon('more-horizontal', { size: 16 });
      btn.dataset.menuIconDone = '1';
    }
  });
};

window.enhancePrototypeDom = (root = document) => {
  window.wrapTables(root);
  window.labelPrototypeControls(root);
  window.makeClickableTargetsAccessible(root);
  window.normalizeMenuButtons(root);
};
document.addEventListener('DOMContentLoaded', () => window.enhancePrototypeDom());

// ---------- ESC closes any open modal / menu / drawer ----------
document.addEventListener('keydown', e => {
  const modal = _activeModal();
  if (modal && e.key === 'Tab') {
    const items = _modalFocusables(modal);
    if (!items.length) { e.preventDefault(); modal.focus(); return; }
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
  if (e.key === 'Escape') {
    document.querySelectorAll('.menu.on').forEach(m => {
      m.classList.remove('on');
      m.closest('.menu-wrap')?.querySelector('[data-menu-toggle]')?.setAttribute('aria-expanded', 'false');
    });
    if (modal) closeModal(modal.id);
    const d = document.getElementById('mob-drawer');
    if (d?.classList.contains('on')) toggleDrawer();
  }
});

/* ===========================================================================
   SVG ICON SYSTEM
   One consistent stroke set (Lucide-style: 24×24, currentColor, round caps).
   Replaces the old Unicode glyph "icons" everywhere. Two ways to use:
     • window.icon('plus')         → an <svg> string, for building markup
     • <i class="ic" data-icon="plus"></i> in HTML → auto-filled on load
   Icons inherit color from text (currentColor) and size from context CSS.
   =========================================================================== */
window.MP_ICONS = {
  // navigation — workshop
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  orders: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M9 12h6M9 16h4"/>',
  scissors: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/>',
  layers: '<path d="m12 2 9 4.5-9 4.5-9-4.5L12 2Z"/><path d="m3 12 9 4.5L21 12"/><path d="m3 17 9 4.5L21 17"/>',
  box: '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
  chart: '<line x1="6" y1="20" x2="6" y2="14"/><line x1="12" y1="20" x2="12" y2="9"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="3" y1="20" x2="21" y2="20"/>',
  wallet: '<path d="M3 7a2 2 0 0 1 2-2h12a1 1 0 0 1 1 1v2"/><path d="M3 7v10a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1v-3"/><path d="M21 11h-5a2 2 0 0 0 0 4h5a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1Z"/>',
  store: '<path d="M3.5 8 5 4h14l1.5 4"/><path d="M4 8v11a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8"/><path d="M3 8h18"/><path d="M9.5 20v-5h5v5"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>',
  // navigation — admin
  factory: '<path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9l-7 4V9l-7 4V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M7 18h.01M12 18h.01M17 18h.01"/>',
  package: '<path d="m7.5 4.3 9 5.2"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  list: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
  book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2Z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7Z"/>',
  // actions / utility
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  'check-circle': '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  'x-circle': '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
  edit: '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z"/>',
  trash: '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',
  'chevron-down': '<polyline points="6 9 12 15 18 9"/>',
  'chevron-right': '<polyline points="9 18 15 12 9 6"/>',
  'arrow-left': '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
  'arrow-right': '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  'more-horizontal': '<circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="5" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
  'more-vertical': '<circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="12" cy="5" r="1.5" fill="currentColor" stroke="none"/><circle cx="12" cy="19" r="1.5" fill="currentColor" stroke="none"/>',
  menu: '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
  user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  refresh: '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/>',
  'external-link': '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  'map-pin': '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0Z"/><circle cx="12" cy="10" r="3"/>',
  phone: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92Z"/>',
  'log-out': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  printer: '<polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  truck: '<path d="M1 3h15v13H1z"/><path d="M16 8h4l3 3v5h-7V8Z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
  save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
  send: '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  ban: '<circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 8.3-8.3M16 7l3 3M18 5l2 2"/>',
  building: '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M16 6h.01M12 6h.01M12 10h.01M16 10h.01M8 10h.01M12 14h.01M16 14h.01M8 14h.01"/>',
  home: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  undo: '<polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/>',
  play: '<polygon points="6 4 20 12 6 20 6 4" fill="currentColor" stroke="none"/>',
  'dollar-sign': '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
  _missing: '<circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
};

window.icon = (name, opts = {}) => {
  const inner = window.MP_ICONS[name] || window.MP_ICONS._missing;
  const size = opts.size || 18;
  const cls = opts.cls ? ' ' + opts.cls : '';
  const sw = opts.sw || 2;
  return `<svg class="i${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
};

// Fill any <element data-icon="name"> that hasn't been rendered yet. Safe to
// call repeatedly (e.g. after injecting markup dynamically).
window.renderIcons = (root = document) => {
  root.querySelectorAll('[data-icon]:not([data-icon-done])').forEach(el => {
    const name = el.getAttribute('data-icon');
    const size = el.getAttribute('data-icon-size');
    el.insertAdjacentHTML('afterbegin', window.icon(name, size ? { size } : {}));
    el.setAttribute('data-icon-done', '1');
  });
};
document.addEventListener('DOMContentLoaded', () => window.renderIcons());

// Catch icons added by page scripts after load (tables, cards, modals built
// dynamically) — debounced so we render once per frame, no churn.
(() => {
  let queued = false;
  const obs = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      window.renderIcons();
      window.enhancePrototypeDom?.();
    });
  });
  const start = () => obs.observe(document.body, { childList: true, subtree: true });
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);
})();
