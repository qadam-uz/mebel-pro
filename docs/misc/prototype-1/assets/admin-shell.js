/* Admin (superadmin) app shell */
window.renderAdminShell = () => {
  const sidebar = `
  <aside class="sb">
    <a class="sb-brand" href="dashboard.html">
      <span class="mk">M</span>
      <span class="nm">Mebel Pro<small>superadmin</small></span>
    </a>
    <div class="sb-tenant">
      <span class="av" style="background:linear-gradient(135deg,#2A4D6B,#1F3A50)">PL</span>
      <div class="info">
        <div class="nm">Platforma</div>
        <div class="role">5 ta seh · O'Z</div>
      </div>
    </div>
    <nav class="sb-nav">
      <div class="sb-grp">
        <div class="lbl">Platforma</div>
        <a class="sb-it" data-href="dashboard.html" href="dashboard.html"><span class="ic">◐</span> Asosiy</a>
        <a class="sb-it" data-href="workshops.html" href="workshops.html"><span class="ic">▥</span> Sehlar <span class="ct">5</span></a>
        <a class="sb-it" data-href="orders.html" href="orders.html"><span class="ic">▣</span> Buyurtmalar (cross)</a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Katalog</div>
        <a class="sb-it" data-href="materials.html" href="materials.html"><span class="ic">⊞</span> Materiallar <span class="ct">10</span></a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Operatorlik</div>
        <a class="sb-it" data-href="jobs.html" href="jobs.html"><span class="ic">⌥</span> Background ish <span class="ct" style="color:#F2D6CE;background:rgba(140,46,28,.25)">1</span></a>
        <a class="sb-it" data-href="errors.html" href="errors.html"><span class="ic">!</span> Xatolik monitor <span class="ct">4</span></a>
        <a class="sb-it" data-href="audit.html" href="audit.html"><span class="ic">≡</span> Audit log</a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Tizim</div>
        <a class="sb-it" data-href="platform-users.html" href="platform-users.html"><span class="ic">◆</span> Operatorlar <span class="ct">3</span></a>
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

  const topbar = `
  <div class="tb">
    <button class="mobile-nav-btn" type="button" onclick="toggleDrawer()" aria-label="Menu">☰ Menu</button>
    <div class="tb-search">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="7" cy="7" r="5"/><path d="m11 11 3 3"/></svg>
      <input id="tb-search" placeholder="Seh, mijoz, buyurtma yoki xatolik kodi..." />
      <span class="kbd">⌘ K</span>
    </div>
    <div class="tb-actions">
      <button class="ib" type="button" onclick="location.href='notifications.html'" aria-label="Bildirishnomalar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
        <span class="dot"></span>
      </button>
      <a class="btn btn-acc" href="workshops.html">+ Yangi seh</a>
    </div>
  </div>`;

  document.body.insertAdjacentHTML('afterbegin', `<div class="app">${sidebar}<main class="shell-main">${topbar}<div id="page-shell"></div></main></div>`);
  const page = document.body.querySelector('main.page-content');
  if (page) document.getElementById('page-shell').appendChild(page);
  autoMarkNav();
};
