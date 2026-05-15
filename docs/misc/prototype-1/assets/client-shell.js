/* Client app shell — header markup injected at the top of every client page. */
window.renderClientHeader = (active = '') => {
  const html = `
  <header class="hdr">
    <div class="container hdr-row">
      <a class="brand" href="branches.html" aria-label="Bosh sahifa">
        <span class="mk">M</span><span class="nm">Mebel Pro</span>
      </a>
      <nav class="hdr-nav" aria-label="Asosiy navigatsiya">
        <a data-href="branches.html" href="branches.html">Sehlar</a>
        <a data-href="cutting-drafts.html" href="cutting-drafts.html">Kesim chizmalari</a>
        <a data-href="orders.html" href="orders.html">Buyurtmalar</a>
      </nav>
      <div class="hdr-actions">
        <button class="ib" type="button" onclick="location.href='notifications.html'" aria-label="Bildirishnomalar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
          <span class="badge" data-count="3">3</span>
        </button>
        <a class="user-btn" href="profile.html">
          <span class="av">A</span>
          <span class="nm">Akmal N.<small>@akmal_n</small></span>
        </a>
      </div>
    </div>
  </header>`;
  document.body.insertAdjacentHTML('afterbegin', html);
  if (active) {
    document.querySelectorAll('.hdr-nav a').forEach(a => {
      a.classList.toggle('on', a.dataset.href === active);
    });
  } else {
    autoMarkNav();
  }
};
