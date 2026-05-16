/* Workshop app shell — sidebar + top bar injected into every workshop page. */
window.renderWorkshopShell = (active = '') => {
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
      <div class="sb-grp">
        <div class="lbl">Boshqaruv</div>
        <a class="sb-it" data-href="dashboard.html" href="dashboard.html"><span class="ic">◐</span> Asosiy</a>
        <a class="sb-it" data-href="orders.html" href="orders.html"><span class="ic">▣</span> Buyurtmalar <span class="ct">7</span></a>
        <a class="sb-it" data-href="cutting-queue.html" href="cutting-queue.html"><span class="ic">⌥</span> Chizma navbati <span class="ct">3</span></a>
        <a class="sb-it" data-href="banding-queue.html" href="banding-queue.html"><span class="ic">▥</span> Krom navbati <span class="ct">1</span></a>
        <a class="sb-it" data-href="delivery-queue.html" href="delivery-queue.html"><span class="ic">→</span> Yetkazma navbati <span class="ct">2</span></a>
        <a class="sb-it" data-href="refunds.html" href="refunds.html"><span class="ic">↺</span> Qaytarishlar <span class="ct" style="color:#F4E4CB;background:rgba(163,100,23,.25)">1</span></a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Resurslar</div>
        <a class="sb-it" data-href="inventory.html" href="inventory.html"><span class="ic">⊟</span> Ombor <span class="ct" style="color:#F4E4CB;background:rgba(163,100,23,.25)">4</span></a>
        <a class="sb-it" data-href="catalog.html" href="catalog.html"><span class="ic">⊞</span> Material katalogi</a>
        <a class="sb-it" data-href="transfers.html" href="transfers.html"><span class="ic">⇄</span> Filiallar orasi</a>
        <a class="sb-it" data-href="branches.html" href="branches.html"><span class="ic">◫</span> Filiallar <span class="ct">3</span></a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Moliya</div>
        <a class="sb-it" data-href="finance.html" href="finance.html"><span class="ic">∑</span> Hisobotlar</a>
        <a class="sb-it" data-href="payroll.html" href="payroll.html"><span class="ic">⚖</span> Maoshlar <span class="ct">17</span></a>
        <a class="sb-it" data-href="expenses.html" href="expenses.html"><span class="ic">↕</span> Xarajatlar</a>
      </div>
      <div class="sb-grp">
        <div class="lbl">Tizim</div>
        <a class="sb-it" data-href="users.html" href="users.html"><span class="ic">◆</span> Xodimlar <span class="ct">8</span></a>
        <a class="sb-it" data-href="audit.html" href="audit.html"><span class="ic">≡</span> Audit log</a>
        <a class="sb-it" data-href="settings.html" href="settings.html"><span class="ic">⚙</span> Sozlamalar</a>
      </div>
    </nav>
    <div class="sb-foot">
      <a class="sb-user" href="profile.html">
        <span class="av">H</span>
        <div class="info">
          <div class="nm">Hasan ako</div>
          <div class="rl">Egasi · barcha ruxsatlar</div>
        </div>
      </a>
    </div>
  </aside>`;

  const topbar = `
  <div class="tb">
    <button class="mobile-nav-btn" type="button" onclick="toggleDrawer()" aria-label="Menu">☰ Menu</button>
    <div class="br-picker" onclick="toggleBranchPop(event)">
      <span class="ic"></span>
      <div><div class="nm" id="br-name">Hamma filiallar</div><div class="sub">3 filial · 8 xodim</div></div>
      <div class="br-pop" id="br-pop" hidden>
        <div class="it on" onclick="pickBranch(event,'all','Hamma filiallar')"><span class="pin"></span><div class="nm">Hamma filiallar<small>3 filial · 8 xodim</small></div><span class="ck">✓</span></div>
        <div class="it" onclick="pickBranch(event,'yunusobod','Yunusobod')"><span class="pin"></span><div class="nm">Yunusobod<small>Buyuk Ipak Yo'li 142 · faol</small></div><span class="ck">✓</span></div>
        <div class="it" onclick="pickBranch(event,'chilonzor','Chilonzor')"><span class="pin"></span><div class="nm">Chilonzor<small>Chilonzor 9-mavze 32 · faol</small></div><span class="ck">✓</span></div>
        <div class="it" onclick="pickBranch(event,'yangiyol','Yangiyo\\'l')"><span class="pin cl"></span><div class="nm">Yangiyo'l<small>Mustaqillik 5 · vaqtincha yopiq</small></div><span class="ck">✓</span></div>
      </div>
    </div>
    <div class="tb-search">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="7" cy="7" r="5"/><path d="m11 11 3 3"/></svg>
      <input id="tb-search" placeholder="Buyurtma, mijoz, xodim yoki material..." onkeydown="if(event.key==='Enter'){toast('Qidiruv: '+this.value)}" />
      <span class="kbd">⌘ K</span>
    </div>
    <div class="tb-actions">
      <button class="ib" type="button" onclick="location.href='notifications.html'" aria-label="Bildirishnomalar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
        <span class="dot"></span>
      </button>
      <a class="btn btn-acc" href="orders.html">+ Buyurtmalar</a>
    </div>
  </div>`;

  document.body.insertAdjacentHTML('afterbegin', `<div class="app">${sidebar}<main class="shell-main">${topbar}<div id="page-shell"></div></main></div>`);
  // Move existing page content into the shell.
  const page = document.body.querySelector('main.page-content');
  if (page) document.getElementById('page-shell').appendChild(page);
  autoMarkNav();
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
