/* Workshop app shell — sidebar + top bar injected into every workshop page.

   CR4 — the access model. A single demo principal (window.ME) plus a small
   capability API the whole workshop app derives visible controls from. No
   fixed roles: capability is the per-branch grant set; the owner (isOwner)
   holds every permission on every branch implicitly. The acting user is
   switchable from the top bar for the demo and persisted in localStorage. */

// ---------- Demo principal + capability API (CR4) ----------
(() => {
  const STORE_KEY = 'mp.ws.me';
  const DEFAULT_ME = 'u01'; // the owner

  const seedUser = id => (window.SEED ? SEED.users.find(u => u.id === id) : null);

  let activeId = null;
  try { activeId = localStorage.getItem(STORE_KEY); } catch (_) {}
  if (!activeId || !seedUser(activeId)) activeId = DEFAULT_ME;

  window.ME = seedUser(activeId) || { id: activeId, name: '—', isOwner: false, grants: {} };

  window.isOwner = () => !!window.ME?.isOwner;

  // can(permission, branchId) — owner is allowed everywhere; otherwise the
  // (permission, branch) pair must be in the grant set. A blocked user can
  // do nothing.
  window.can = (permission, branchId) => {
    const me = window.ME;
    if (!me || me.status === 'blocked') return false;
    if (me.isOwner) return true;
    const branches = me.grants && me.grants[permission];
    if (!branches) return false;
    return branchId == null ? branches.length > 0 : branches.includes(branchId);
  };

  // canAny(permission) — holds the permission on at least one branch.
  window.canAny = permission => window.can(permission, null);

  // myBranches() — branch ids the user can scope to (all if owner).
  window.myBranches = () => {
    const me = window.ME;
    if (!window.SEED) return [];
    if (me?.isOwner) return SEED.branches.map(b => b.id);
    const ids = new Set();
    Object.values(me?.grants || {}).forEach(list => (list || []).forEach(id => ids.add(id)));
    return SEED.branches.filter(b => ids.has(b.id)).map(b => b.id);
  };

  // ownerOnly() — render a denied panel and return false when a non-owner
  // reaches an owner-only screen. Returns true when the owner may proceed.
  window.ownerOnly = (mountSelector = '#wrap, .page > div:last-child, .page') => {
    if (window.isOwner()) return true;
    const mount = document.querySelector('#wrap')
      || document.querySelector('.page');
    const html = `<div class="st-error" role="alert" style="margin-top:8px">
      <div class="ic">${window.icon('ban', { size: 26 })}</div>
      <h3>Bu sahifa faqat ustaxona egasiga ochiq</h3>
      <p>Sizda bu bo'limni ko'rish uchun ruxsat yo'q — ustaxona egasiga murojaat qiling.</p>
      <a class="btn btn-outline btn-sm" href="dashboard.html">← Asosiyga qaytish</a>
    </div>`;
    if (mount) {
      if (mount.id === 'wrap') mount.innerHTML = html;
      else {
        const box = document.createElement('div');
        box.innerHTML = html;
        mount.appendChild(box.firstElementChild);
      }
    }
    return false;
  };

  // A short, role-free identity summary (IN1): owner → "Egasi · barcha
  // ruxsatlar"; staff → grant + branch count, never a role name.
  window.meSummary = () => {
    const me = window.ME;
    if (!me) return '—';
    if (me.isOwner) return 'Egasi · barcha ruxsatlar';
    const grants = me.grants || {};
    const permCount = Object.keys(grants).length;
    if (permCount === 0) return 'Ruxsat berilmagan';
    const brSet = new Set();
    Object.values(grants).forEach(list => (list || []).forEach(b => brSet.add(b)));
    return `${permCount} ta grant · ${brSet.size} filial`;
  };

  // Switch the acting user (demo only) and reload so every screen re-derives.
  window.switchMe = id => {
    if (!seedUser(id)) return;
    try { localStorage.setItem(STORE_KEY, id); } catch (_) {}
    location.reload();
  };
})();

// ---------- Shared, in-memory notification state (PU10) ----------
window.notifUnreadCount = () =>
  (window.SEED ? SEED.notifications.filter(n => !n.read).length : 0);

window.markAllNotifsRead = () => {
  if (window.SEED) SEED.notifications.forEach(n => (n.read = true));
  window.refreshNotifBadge();
  document.dispatchEvent(new CustomEvent('notifschange'));
};

window.refreshNotifBadge = () => {
  const n = window.notifUnreadCount();
  document.querySelectorAll('[data-notif-badge]').forEach(el => {
    el.textContent = n > 9 ? '9+' : String(n);
    el.setAttribute('data-count', String(n));
  });
};

// ---------- Shared loading / empty / error state markup (PU11) ----------
// Uses the shared .sk / .sk-line / .st-empty / .st-error classes defined in
// app.css. ?state=loading|error|empty is honoured for the demo.
window.demoState = () => new URLSearchParams(location.search).get('state') || '';

// A skeleton table body shaped like real rows.
window.skRows = (cols, rows = 6) =>
  Array.from({ length: rows }).map(() =>
    `<tr aria-hidden="true">${Array.from({ length: cols }).map(() =>
      `<td><span class="sk-line"></span></td>`).join('')}</tr>`).join('');

window.skCards = (n = 4) =>
  Array.from({ length: n }).map(() =>
    `<div class="sk" style="height:96px;border-radius:10px;margin-bottom:10px"></div>`).join('');

window.stError = (traceId = 'tr-' + Math.random().toString(16).slice(2, 8)) =>
  `<div class="st-error" role="alert">
    <div class="ic">${window.icon('alert', { size: 26 })}</div>
    <h3>Ma'lumotni yuklab bo'lmadi</h3>
    <p>Vaqtinchalik xatolik. Birozdan keyin qayta urinib ko'ring.</p>
    <p style="font:400 11.5px var(--f-mono);color:var(--ink-6)">trace_id: ${traceId}</p>
    <button class="btn btn-outline btn-sm" type="button" onclick="location.href=location.pathname">Qayta urinish</button>
  </div>`;

window.stEmpty = (title, body = '', ic = 'inbox') =>
  `<div class="st-empty"><div class="ic">${window.icon(ic, { size: 25 })}</div><h3>${title}</h3>${body ? `<p>${body}</p>` : ''}</div>`;

// Fallback styling for the shared state classes, in a CSS @layer so the
// canonical (unlayered) app.css definitions added by the other worker always
// win. This only kicks in if app.css doesn't define them yet, keeping the
// standalone prototype legible without redefining/overriding the real ones.
(() => {
  if (document.getElementById('mp-state-fallback')) return;
  const s = document.createElement('style');
  s.id = 'mp-state-fallback';
  s.textContent = `@layer mp-fallback {
    .sk { background: var(--sunk); position: relative; overflow: hidden; }
    .sk-line { display: block; height: 12px; border-radius: 4px; background: var(--sunk); width: 80%; }
    .sk::after, .sk-line::after { content: ""; position: absolute; inset: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,.45), transparent);
      transform: translateX(-100%); animation: mp-shimmer 1.3s infinite; }
    .sk-line { position: relative; overflow: hidden; }
    @keyframes mp-shimmer { 100% { transform: translateX(100%); } }
    .st-empty, .st-error { padding: 56px 24px; text-align: center; background: var(--elev);
      border: 1px dashed var(--line-strong); border-radius: 14px; }
    .st-error { border-style: solid; border-color: var(--danger-tint); }
    .st-empty .ic, .st-error .ic { font-family: var(--f-display); font-size: 44px;
      color: var(--ink-4); line-height: 1; margin-bottom: 12px; }
    .st-error .ic { color: var(--danger); }
    .st-empty h3, .st-error h3 { font-family: var(--f-display); font-size: 21px;
      font-weight: 600; margin: 0 0 8px; }
    .st-empty p, .st-error p { color: var(--ink-8); font-size: 13.5px; margin: 0 auto 12px;
      max-width: 460px; line-height: 1.5; }
  }`;
  document.head.appendChild(s);
})();

window.renderWorkshopShell = (active = '') => {
  // --- Nav model: every item declares how it is gated. ---
  // gate: 'owner' → owner-only; or a list of permissions (any-of, any branch);
  // null → always visible (profile etc.).
  const NAV = [
    { grp: 'Boshqaruv', items: [
      { href: 'dashboard.html', ic: 'dashboard', label: 'Asosiy', gate: null },
      { href: 'orders.html', ic: 'orders', label: 'Buyurtmalar', gate: ['manage_orders', 'view_dashboard'] }
    ]},
    { grp: 'Ishlab chiqarish', items: [
      { href: 'cutting-queue.html', ic: 'scissors', label: 'Kesish navbati', gate: ['process_production'] },
      { href: 'banding-queue.html', ic: 'layers', label: 'Krom navbati', gate: ['process_production'] }
    ]},
    { grp: 'Resurslar', items: [
      { href: 'inventory.html', ic: 'box', label: 'Ombor', gate: ['manage_inventory'] },
      { href: 'catalog.html', ic: 'grid', label: 'Material katalogi', gate: ['manage_catalog'] }
    ]},
    { grp: 'Moliya', items: [
      { href: 'finance.html', ic: 'chart', label: 'Hisobotlar', gate: ['manage_finance', 'view_finance_reports'] },
      { href: 'expenses.html', ic: 'wallet', label: 'Xarajatlar', gate: ['manage_finance', 'view_finance_reports'] }
    ]},
    { grp: 'Tizim', items: [
      { href: 'branches.html', ic: 'store', label: 'Filiallar', gate: 'owner' },
      { href: 'users.html', ic: 'users', label: 'Xodimlar', gate: 'owner' },
      { href: 'settings.html', ic: 'settings', label: 'Sozlamalar', gate: 'owner' }
    ]}
  ];

  const visible = it => {
    if (it.gate == null) return true;
    if (it.gate === 'owner') return window.isOwner();
    return it.gate.some(p => window.canAny(p));
  };

  const navGroups = NAV.map(g => {
    const items = g.items.filter(visible);
    if (!items.length) return '';
    return `<div class="sb-grp">
      <div class="lbl">${g.grp}</div>
      ${items.map(it => `<a class="sb-it" data-href="${it.href}" href="${it.href}"><span class="ic">${window.icon(it.ic)}</span> ${it.label}</a>`).join('')}
    </div>`;
  }).join('');

  const me = window.ME || {};
  const avInitials = me.initials || (me.name || '?').slice(0, 1);

  const sidebar = `
  <aside class="sb">
    <a class="sb-brand" href="dashboard.html">
      <span class="mk">M</span>
      <span class="nm">Mebel Pro<small>boshqaruv</small></span>
    </a>
    <div class="sb-tenant">
      <span class="av">FH</span>
      <div class="info">
        <div class="nm">Furniture House</div>
        <div class="role">3 filial · O'Z</div>
      </div>
    </div>
    <nav class="sb-nav">
      ${navGroups || `<div class="sb-grp"><div class="lbl">Boshqaruv</div><a class="sb-it on" data-href="dashboard.html" href="dashboard.html"><span class="ic">${window.icon('dashboard')}</span> Asosiy</a></div>`}
    </nav>
    <div class="sb-foot">
      <a class="sb-user" href="profile.html" title="${me.name || ''}">
        <span class="av">${avInitials}</span>
        <div class="info" style="min-width:0;flex:1">
          <div class="nm">${me.name || '—'}${me.isOwner ? ' <span style="font-size:9.5px;background:var(--accent-tint);color:var(--accent-h);padding:1px 5px;border-radius:3px;font-weight:700;letter-spacing:.04em">EGASI</span>' : ''}</div>
          <div class="rl">${window.meSummary()}</div>
        </div>
      </a>
    </div>
  </aside>`;

  // Branch picker offers only myBranches() (all, for the owner).
  const myBr = window.myBranches();
  const brOptions = (window.SEED ? SEED.branches : []).filter(b => myBr.includes(b.id));
  const allLabel = window.isOwner() ? 'Hamma filiallar' : (brOptions.length > 1 ? 'Mening filiallarim' : '');
  const showAll = brOptions.length !== 1;
  const stClass = b => b.status === 'active' ? '' : (b.status === 'temporarily_closed' ? 'cl' : 'off');
  const stWord = b => b.status === 'active' ? 'faol' : (b.status === 'temporarily_closed' ? 'vaqtincha yopiq' : 'faol emas');

  const brPopItems = (showAll
    ? `<div class="it on" onclick="pickBranch(event,'all','${allLabel}')"><span class="pin"></span><div class="nm">${allLabel}<small>${brOptions.length} filial</small></div><span class="ck">✓</span></div>`
    : '') +
    brOptions.map((b, i) =>
      `<div class="it ${!showAll && i === 0 ? 'on' : ''}" onclick="pickBranch(event,'${b.id}','${b.name.replace(/'/g, "\\'")}')"><span class="pin ${stClass(b)}"></span><div class="nm">${b.name}<small>${b.addr} · ${stWord(b)}</small></div><span class="ck">✓</span></div>`
    ).join('');

  const firstBrLabel = showAll ? allLabel : (brOptions[0]?.name || 'Filial yo\'q');
  const brSub = showAll ? `${brOptions.length} filial` : (brOptions[0] ? stWord(brOptions[0]) : 'biriktirilmagan');

  const branchPicker = brOptions.length === 0
    ? `<div class="br-picker" style="cursor:default;opacity:.7" title="Filial biriktirilmagan"><span class="ic" style="background:var(--ink-4)"></span><div><div class="nm" id="br-name">Filial yo'q</div><div class="sub">biriktirilmagan</div></div></div>`
    : `<div class="br-picker" onclick="toggleBranchPop(event)">
      <span class="ic"></span>
      <div><div class="nm" id="br-name">${firstBrLabel}</div><div class="sub">${brSub}</div></div>
      <div class="br-pop" id="br-pop" hidden>${brPopItems}</div>
    </div>`;

  // Dev-only acting-user switcher (demo): a small "Ko'rinish: <user> ▾".
  const users = window.SEED ? SEED.users : [];
  const meId = me.id;
  const switcher = `
    <div class="me-switch menu-wrap" title="Demo · ko'rinishni almashtirish">
      <button class="ib" type="button" data-menu-toggle aria-label="Ko'rinishni almashtirish" style="width:auto;padding:0 10px;gap:6px;font:600 12px var(--f-ui)">
        <span style="color:var(--ink-6);font-weight:500">Ko'rinish:</span> ${me.name ? me.name.split(' ')[0] : '—'} ${window.icon('chevron-down', { size: 13 })}
      </button>
      <div class="menu" style="min-width:248px">
        <div style="font:700 10px var(--f-ui);text-transform:uppercase;letter-spacing:.1em;color:var(--ink-6);padding:8px 12px 4px">Demo · qaysi xodim sifatida</div>
        ${users.map(u => {
          const sum = u.isOwner ? 'Egasi · barcha' : (Object.keys(u.grants || {}).length ? `${Object.keys(u.grants).length} grant` : 'ruxsatsiz');
          const blk = u.status === 'blocked' ? ' · bloklangan' : '';
          return `<button class="mi" onclick="switchMe('${u.id}')"${u.id === meId ? ' style="background:var(--accent-tint);color:var(--accent-h)"' : ''}>
            <span style="flex:1">${u.name}<small style="display:block;color:var(--ink-6);font:400 11px var(--f-mono)">${sum}${blk}</small></span>
            ${u.id === meId ? '<span style="color:var(--accent)">✓</span>' : ''}
          </button>`;
        }).join('')}
      </div>
    </div>`;

  const topbar = `
  <div class="tb">
    <button class="mobile-nav-btn" type="button" onclick="toggleDrawer()" aria-label="Menu">${window.icon('menu', { size: 16 })} Menu</button>
    ${branchPicker}
    <div class="tb-search">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="7" cy="7" r="5"/><path d="m11 11 3 3"/></svg>
      <input id="tb-search" placeholder="Buyurtma, mijoz, xodim yoki material..." onkeydown="if(event.key==='Enter'){toast('Qidiruv: '+this.value)}" />
      <span class="kbd">⌘ K</span>
    </div>
    <div class="tb-actions">
      ${switcher}
      <div class="notif-wrap menu-wrap">
        <button class="ib" type="button" data-menu-toggle aria-label="Bildirishnomalar" aria-haspopup="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
          <span class="badge" data-notif-badge data-count="0">0</span>
        </button>
        <div class="menu notif-menu" style="min-width:340px;right:0;padding:0" role="menu" aria-label="Bildirishnomalar">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--line)">
            <b style="font:700 13px var(--f-ui)">Bildirishnomalar</b>
            <button class="btn btn-ghost btn-sm" type="button" onclick="event.stopPropagation();markAllNotifsRead()">Hammasini o'qildi</button>
          </div>
          <div id="notif-dd-list" style="max-height:360px;overflow-y:auto"></div>
          <a class="mi" href="notifications.html" style="justify-content:center;border-top:1px solid var(--line);border-radius:0;font-weight:600;padding:11px">Hammasini ko'rish ${window.icon('arrow-right', { size: 13 })}</a>
        </div>
      </div>
    </div>
  </div>`;

  document.body.insertAdjacentHTML('afterbegin', `<div class="app">${sidebar}<main class="shell-main">${topbar}<div id="page-shell"></div></main></div>`);
  const page = document.body.querySelector('main.page-content');
  if (page) document.getElementById('page-shell').appendChild(page);
  autoMarkNav();

  // Fill the notification dropdown + badge (PU10).
  window.renderNotifDropdown = () => {
    const box = document.getElementById('notif-dd-list');
    if (!box || !window.SEED) return;
    const recent = SEED.notifications.slice(0, 10);
    box.innerHTML = recent.length
      ? recent.map(n => `<a class="notif-row${n.read ? '' : ' unread'}" href="${n.link}" role="menuitem" style="display:grid;grid-template-columns:8px 1fr;gap:10px;padding:11px 14px;border-bottom:1px solid var(--line);text-decoration:none;color:inherit">
          <span style="width:8px;height:8px;border-radius:50%;margin-top:5px;background:${n.read ? 'transparent' : 'var(--accent)'}"></span>
          <span><span style="font:600 12.5px var(--f-ui);color:var(--ink-12)">${n.title}</span><br><small style="color:var(--ink-8);font-size:11.5px">${n.body}</small><br><small style="color:var(--ink-6);font:400 10.5px var(--f-mono)">${n.t}</small></span>
        </a>`).join('')
      : `<div style="padding:28px 14px;text-align:center;color:var(--ink-6);font-size:13px">Bildirishnoma yo'q</div>`;
  };
  window.renderNotifDropdown();
  window.refreshNotifBadge();
  document.addEventListener('notifschange', () => { window.renderNotifDropdown(); window.refreshNotifBadge(); });

  // Per-role critical toast (workshop: a new order awaiting review). Demo:
  // fire once per session for a user who can act on orders.
  try {
    if (!sessionStorage.getItem('mp.ws.newOrderToast') && window.SEED) {
      const newOnes = SEED.orders.filter(o => o.state === 'new'
        && (window.isOwner() || window.can('manage_orders', o.branchId)));
      if (newOnes.length) {
        sessionStorage.setItem('mp.ws.newOrderToast', '1');
        setTimeout(() => toast(`Yangi buyurtma · ${newOnes[0].id} — tasdiqlash kerak`, 'warn'), 900);
      }
    }
  } catch (_) {}
};

window.pickBranch = (e, id, label) => {
  e?.stopPropagation();
  document.getElementById('br-name').textContent = label;
  document.querySelectorAll('.br-pop .it').forEach(it => it.classList.remove('on'));
  e?.currentTarget?.classList.add('on');
  document.getElementById('br-pop').hidden = true;
  toast(`Filial: ${label}`);
  window.dispatchEvent(new CustomEvent('branchchange', { detail: { id, label } }));
};
