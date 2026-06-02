/* Admin (superadmin) app shell */

// Operator inbox (PU10): only error-spike + failed-job kinds are documented
// operator events. Built from SEED at render time.
window.adminNotifications = () => {
  const out = [];
  (SEED.errors || []).forEach(e => {
    if (e.spike) out.push({
      kind: 'error', read: !!e.resolved,
      title: `Error spike · ${e.code}`,
      body: `24 soatda ${e.count24h} ta · 7 kunda ${e.count7d} ta`,
      t: e.last, link: `errors.html?code=${e.code}`
    });
  });
  (SEED.jobs || []).forEach(j => {
    if (j.lastResult === 'failed') out.push({
      kind: 'job', read: false,
      title: `Failed ish · ${j.name}`,
      body: j.error || j.summary,
      t: j.lastRun, link: `jobs.html?job=${j.id}`
    });
  });
  return out;
};

window.renderAdminShell = () => {
  const notes = window.adminNotifications();
  const unread = notes.filter(n => !n.read).length;
  const badge = unread > 9 ? '9+' : String(unread);
  const currentOperator = (window.SEED?.platformUsers || []).find(u => u.id === 'p01') || {};

  const sidebar = `
  <aside class="sb">
    <a class="sb-brand" href="dashboard.html">
      <span class="mk">M</span>
      <span class="nm">Mebel Pro<small>superadmin</small></span>
    </a>
    <div class="sb-tenant">
      <span class="av" style="background:linear-gradient(135deg,var(--deep-2),var(--deep))">PL</span>
      <div class="info">
        <div class="nm">Platforma</div>
        <div class="role">${(SEED.workshops || []).length} ta ustaxona · O'Z</div>
      </div>
    </div>
    <nav class="sb-nav">
      <div class="sb-grp">
        <div class="lbl">Platforma</div>
        <a class="sb-it" data-href="dashboard.html" href="dashboard.html"><span class="ic">${window.icon('dashboard')}</span> Asosiy</a>
        <a class="sb-it" data-href="workshops.html" href="workshops.html"><span class="ic">${window.icon('factory')}</span> Ustaxonalar <span class="ct">${(SEED.workshops || []).length}</span></a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Katalog</div>
        <a class="sb-it" data-href="manufacturers.html" href="manufacturers.html"><span class="ic">${window.icon('factory')}</span> Manufacturerlar <span class="ct">${(SEED.manufacturers || []).length}</span></a>
        <a class="sb-it" data-href="materials.html" href="materials.html"><span class="ic">${window.icon('package')}</span> Materiallar <span class="ct">${(SEED.materials || []).length}</span></a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Operatorlik</div>
        <a class="sb-it" data-href="jobs.html" href="jobs.html"><span class="ic">${window.icon('activity')}</span> Background ish <span class="ct" style="color:var(--danger);background:var(--danger-tint)">${(SEED.jobs || []).filter(j => j.lastResult === 'failed').length}</span></a>
        <a class="sb-it" data-href="errors.html" href="errors.html"><span class="ic">${window.icon('alert')}</span> Xatolik monitor <span class="ct">${(SEED.errors || []).filter(e => !e.resolved).length}</span></a>
        <a class="sb-it" data-href="audit.html" href="audit.html"><span class="ic">${window.icon('list')}</span> Audit log</a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Tizim</div>
        <a class="sb-it" data-href="platform-users.html" href="platform-users.html"><span class="ic">${window.icon('users')}</span> Operatorlar <span class="ct">${(SEED.platformUsers || []).filter(u => u.status === 'active').length}</span></a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Ma'lumotnoma</div>
        <div class="menu-wrap" style="display:block">
          <button class="sb-it" type="button" data-menu-toggle aria-label="Hujjatlar va API havolalari"><span class="ic">${window.icon('book')}</span> Hujjatlar &amp; API <span class="ct" title="Alohida kirish — chetda HTTP-Basic" style="display:inline-flex;align-items:center">${window.icon('external-link', { size: 11 })}</span></button>
          <div class="menu" role="menu" style="left:10px;right:auto;top:calc(100% + 2px);min-width:210px">
            <a class="mi" href="/docs" target="_blank" rel="noopener">${window.icon('book', { size: 15 })} Docs</a>
            <a class="mi" href="/api-docs" target="_blank" rel="noopener">${window.icon('file', { size: 15 })} API docs</a>
            <a class="mi" href="/api-redoc" target="_blank" rel="noopener">${window.icon('file', { size: 15 })} ReDoc</a>
          </div>
        </div>
        <div style="font-size:10.5px;color:var(--ink-6);padding:2px 10px 4px;line-height:1.4">Alohida kirish: chetda HTTP-Basic, yangi oynada.</div>
      </div>
    </nav>
    <div class="sb-foot">
      <a class="sb-user" href="profile.html">
        <span class="av">N</span>
        <div class="info">
          <div class="nm">Nuriddin</div>
          <div class="rl">Platforma operatori</div>
        </div>
      </a>
    </div>
  </aside>`;

  const noteList = notes.length
    ? notes.slice(0, 10).map(n => `
      <a class="nd-item ${n.read ? '' : 'unread'}" href="${n.link}">
        <span class="nd-ic ${n.kind}">${window.icon(n.kind === 'job' ? 'activity' : 'alert', { size: 15 })}</span>
        <span class="nd-tx"><b>${n.title}</b><small>${n.body}</small></span>
        <span class="nd-t">${n.t}</span>
      </a>`).join('')
    : `<div class="nd-empty">Yangilik yo'q</div>`;

  const topbar = `
  <div class="tb">
    <button class="mobile-nav-btn" type="button" onclick="toggleDrawer()" aria-label="Menu">${window.icon('menu', { size: 16 })} Menu</button>
    <div class="tb-search">
      ${window.icon('search', { size: 15, cls: 'tb-search-i' })}
      <input id="tb-search" aria-label="Global qidiruv" placeholder="Ustaxona, mijoz, buyurtma yoki xatolik kodi..." />
      <span class="kbd">⌘ K</span>
    </div>
    <div class="tb-actions">
      <div class="menu-wrap" id="bell-wrap">
        <button class="ib" type="button" id="bell-btn" aria-label="Bildirishnomalar — ${unread} o'qilmagan" aria-haspopup="true" aria-expanded="false">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
          <span class="badge" id="bell-badge" data-count="${unread}">${badge}</span>
        </button>
        <div class="menu nd-menu" id="bell-menu" role="menu" aria-label="Bildirishnomalar">
          <div class="nd-head"><b>Bildirishnomalar</b><button class="nd-mark" type="button" id="bell-mark">Hammasini o'qilgan deb belgilash</button></div>
          <div class="nd-body" id="bell-body">${noteList}</div>
          <a class="nd-all" href="notifications.html">Hammasini ko'rish ${window.icon('arrow-right', { size: 13 })}</a>
        </div>
      </div>
      <a class="btn btn-acc" href="workshops.html">${window.icon('plus')} Yangi ustaxona</a>
    </div>
  </div>`;

  document.body.insertAdjacentHTML('afterbegin', `<div class="app">${sidebar}<main class="shell-main">${topbar}<div id="page-shell"></div></main></div>`);
  const page = document.body.querySelector('main.page-content');
  if (page) document.getElementById('page-shell').appendChild(page);
  window.renderPasswordResetWarning?.('admin', 'profile.html?tab=password', currentOperator);
  autoMarkNav();

  // Bell dropdown — keyboard-operable, badge updates on mark-all-read.
  const bellBtn = document.getElementById('bell-btn');
  const bellMenu = document.getElementById('bell-menu');
  bellBtn.addEventListener('click', e => {
    e.preventDefault();
    e.stopPropagation();
    const open = bellMenu.classList.toggle('on');
    bellBtn.setAttribute('aria-expanded', String(open));
    if (open) bellMenu.querySelector('a,button')?.focus();
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('#bell-wrap')) {
      bellMenu.classList.remove('on');
      bellBtn.setAttribute('aria-expanded', 'false');
    }
  });
  document.getElementById('bell-mark').addEventListener('click', e => {
    e.preventDefault();
    e.stopPropagation();
    document.querySelectorAll('#bell-body .nd-item.unread').forEach(el => el.classList.remove('unread'));
    const b = document.getElementById('bell-badge');
    b.dataset.count = '0';
    b.textContent = '0';
    bellBtn.setAttribute('aria-label', 'Bildirishnomalar — 0 o\'qilmagan');
    toast("Hammasi o'qilgan deb belgilandi");
  });

  // Per-role critical toast (operator: error spike / failed job) — once.
  if (!sessionStorage.getItem('admin-crit-toast')) {
    const crit = notes.find(n => !n.read);
    if (crit) {
      setTimeout(() => toast(crit.title, crit.kind === 'job' ? 'danger' : 'warn'), 700);
      sessionStorage.setItem('admin-crit-toast', '1');
    }
  }
};
