/* Client app shell — header markup injected at the top of every client page.
   Home is the dashboard (active orders + recent drafts).
   The bell opens a real notification dropdown (no Telegram push — v1 is
   in-app only); the unread badge stays in sync with mark-all-read. */

// Notifications relevant to the demo client (c01). The client only sees
// order-status changes for their own orders — never workshop internals.
window.clientNotifications = (() => {
  const seed = (window.SEED && SEED.notifications) || [];
  // Map the shared seed to client-facing copy. Only order notifications
  // reach the client; inventory/workshop ones are filtered out.
  return seed
    .filter(n => n.kind === 'order')
    .map((n, i) => ({
      id: 'cn' + i,
      kind: n.kind,
      read: !!n.read,
      t: n.t,
      title: n.title,
      body: n.body,
      link: n.link
    }));
})();

window.clientUnreadCount = () =>
  (window.clientNotifications || []).filter(n => !n.read).length;

function renderBellBadge() {
  const badge = document.getElementById('cl-bell-badge');
  if (!badge) return;
  const n = clientUnreadCount();
  const shown = n > 9 ? '9+' : String(n);
  badge.textContent = shown;
  badge.setAttribute('data-count', n === 0 ? '0' : '1');
}

function renderBellDropdown() {
  const list = document.getElementById('cl-bell-list');
  if (!list) return;
  const items = (window.clientNotifications || []).slice(0, 10);
  if (items.length === 0) {
    list.innerHTML =
      '<div class="cl-bell-empty">Bildirishnoma yo&#39;q</div>';
    return;
  }
  list.innerHTML = items
    .map(
      n => `
    <button class="cl-bell-it ${n.read ? '' : 'unread'}" type="button"
      data-id="${n.id}" data-link="${n.link}">
      <span class="cl-bell-dot" aria-hidden="true"></span>
      <span class="cl-bell-tx">
        <span class="cl-bell-tt">${n.title}</span>
        <span class="cl-bell-bd">${n.body}</span>
        <span class="cl-bell-tm">${n.t}</span>
      </span>
    </button>`
    )
    .join('');
  list.querySelectorAll('.cl-bell-it').forEach(b => {
    b.addEventListener('click', () => {
      const it = (window.clientNotifications || []).find(
        x => x.id === b.dataset.id
      );
      if (it) it.read = true;
      location.href = b.dataset.link;
    });
  });
}

window.toggleBell = e => {
  e?.stopPropagation();
  const dd = document.getElementById('cl-bell-dd');
  if (!dd) return;
  const open = dd.classList.contains('on');
  if (open) {
    dd.classList.remove('on');
    document.getElementById('cl-bell-btn')?.setAttribute(
      'aria-expanded',
      'false'
    );
  } else {
    renderBellDropdown();
    dd.classList.add('on');
    document.getElementById('cl-bell-btn')?.setAttribute(
      'aria-expanded',
      'true'
    );
    dd.querySelector('.cl-bell-it, .cl-bell-foot a')?.focus();
  }
};

window.bellMarkAllRead = e => {
  e?.stopPropagation();
  (window.clientNotifications || []).forEach(n => (n.read = true));
  renderBellBadge();
  renderBellDropdown();
  toast("Hammasi o'qildi deb belgilandi");
};

window.renderClientHeader = (active = '') => {
  const html = `
  <header class="hdr">
    <div class="container hdr-row">
      <a class="brand" href="home.html" aria-label="Bosh sahifa">
        <span class="mk">M</span><span class="nm">Mebel Pro</span>
      </a>
      <nav class="hdr-nav" aria-label="Asosiy navigatsiya">
        <a data-href="home.html" href="home.html">${window.icon('home', { size: 15 })} Bosh sahifa</a>
        <a data-href="cutting-drafts.html" href="cutting-drafts.html">${window.icon('scissors', { size: 15 })} Chizmalar</a>
        <a data-href="orders.html" href="orders.html">${window.icon('orders', { size: 15 })} Buyurtmalar</a>
        <a data-href="branches.html" href="branches.html">${window.icon('store', { size: 15 })} Ustaxonalar</a>
      </nav>
      <div class="hdr-actions">
        <div class="cl-bell-wrap">
          <button class="ib" id="cl-bell-btn" type="button"
            aria-label="Bildirishnomalar" aria-haspopup="true"
            aria-expanded="false" onclick="toggleBell(event)">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
            <span class="badge" id="cl-bell-badge" data-count="0">0</span>
          </button>
          <div class="cl-bell-dd" id="cl-bell-dd" role="menu" aria-label="Bildirishnomalar">
            <div class="cl-bell-hd">
              <span>Bildirishnomalar</span>
              <button type="button" class="cl-bell-mark" onclick="bellMarkAllRead(event)">Hammasini o'qilgan deb belgilash</button>
            </div>
            <div class="cl-bell-list" id="cl-bell-list"></div>
            <div class="cl-bell-foot">
              <a href="notifications.html">Hammasini ko'rish ${window.icon('arrow-right', { size: 13 })}</a>
            </div>
          </div>
        </div>
        <a class="user-btn" href="profile.html">
          <span class="av">A</span>
          <span class="nm">Akmal N.</span>
        </a>
      </div>
    </div>
  </header>
  <style>
    .cl-bell-wrap { position: relative; display: inline-block; }
    .cl-bell-dd { position: absolute; right: 0; top: calc(100% + 6px); width: 340px; max-width: calc(100vw - 32px); background: var(--elev); border: 1px solid var(--line-strong); border-radius: 10px; box-shadow: var(--sh-4); z-index: 60; display: none; overflow: hidden; }
    .cl-bell-dd.on { display: block; }
    .cl-bell-hd { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 12px 14px; border-bottom: 1px solid var(--line); font: 600 13.5px var(--f-ui); color: var(--ink-12); }
    .cl-bell-mark { background: none; border: 0; color: var(--accent); font: 600 11.5px var(--f-ui); cursor: pointer; padding: 2px 4px; border-radius: 4px; }
    .cl-bell-mark:hover { text-decoration: underline; }
    .cl-bell-mark:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
    .cl-bell-list { max-height: 60vh; overflow-y: auto; padding: 4px; }
    .cl-bell-it { display: flex; gap: 10px; width: 100%; box-sizing: border-box; text-align: left; background: none; border: 0; padding: 10px 10px; border-radius: 7px; cursor: pointer; }
    .cl-bell-it:hover { background: var(--sunk); }
    .cl-bell-it:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
    .cl-bell-dot { width: 7px; height: 7px; border-radius: 50%; background: transparent; flex-shrink: 0; margin-top: 6px; }
    .cl-bell-it.unread { background: var(--accent-soft); }
    .cl-bell-it.unread .cl-bell-dot { background: var(--accent); }
    .cl-bell-tx { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .cl-bell-tt { font: 600 13px var(--f-ui); color: var(--ink-12); }
    .cl-bell-bd { font: 400 12px var(--f-ui); color: var(--ink-8); overflow: hidden; text-overflow: ellipsis; }
    .cl-bell-tm { font: 500 11px var(--f-mono); color: var(--ink-6); margin-top: 2px; }
    .cl-bell-empty { padding: 28px 16px; text-align: center; font: 500 13px var(--f-ui); color: var(--ink-6); }
    .cl-bell-foot { border-top: 1px solid var(--line); padding: 10px 14px; text-align: center; }
    .cl-bell-foot a { font: 600 12.5px var(--f-ui); color: var(--accent); text-decoration: none; }
    .cl-bell-foot a:hover { text-decoration: underline; }
    .cl-bell-foot a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
  </style>`;
  document.body.insertAdjacentHTML('afterbegin', html);
  if (active) {
    document.querySelectorAll('.hdr-nav a').forEach(a => {
      a.classList.toggle('on', a.dataset.href === active);
    });
  } else {
    autoMarkNav();
  }
  renderBellBadge();

  // Close the dropdown on outside click / Escape (keyboard-operable).
  document.addEventListener('click', e => {
    if (!e.target.closest('.cl-bell-wrap')) {
      document.getElementById('cl-bell-dd')?.classList.remove('on');
      document
        .getElementById('cl-bell-btn')
        ?.setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      const dd = document.getElementById('cl-bell-dd');
      if (dd?.classList.contains('on')) {
        dd.classList.remove('on');
        document
          .getElementById('cl-bell-btn')
          ?.setAttribute('aria-expanded', 'false');
        document.getElementById('cl-bell-btn')?.focus();
      }
    }
  });
};
