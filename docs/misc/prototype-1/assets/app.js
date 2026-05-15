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
  ic.textContent = kind === 'danger' ? '!' : kind === 'warn' ? '!' : '✓';
  el.querySelector('.msg').textContent = msg;
  el.classList.add('on');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('on'), 2600);
};

// ---------- Modal ----------
window.openModal = (id) => {
  document.getElementById(id)?.classList.add('on');
  document.getElementById('scrim')?.classList.add('on');
};
window.closeModal = (id) => {
  if (id) document.getElementById(id)?.classList.remove('on');
  else document.querySelectorAll('.modal.on').forEach(m => m.classList.remove('on'));
  document.getElementById('scrim')?.classList.remove('on');
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
    document.querySelectorAll('.menu.on').forEach(m => m.classList.remove('on'));
    if (!wasOpen) menu.classList.add('on');
    return;
  }
  // outside click closes
  if (!e.target.closest('.menu')) {
    document.querySelectorAll('.menu.on').forEach(m => m.classList.remove('on'));
  }
});

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
    <div class="modal on" id="confirm-modal" role="dialog" aria-modal="true">
      <div class="modal-h">
        <h3>${o.title || 'Tasdiqlash'}</h3>
        <button class="x" type="button" data-close-modal="confirm-modal" aria-label="Yopish">✕</button>
      </div>
      <div class="modal-b">
        <p style="margin:0;color:var(--ink-8);font-size:14px;line-height:1.5">${o.msg || 'Davom etishni xohlaysizmi?'}</p>
        ${o.reasonField ? `<div class="field" style="margin-top:14px"><label>${o.reasonLabel || 'Sabab'} *</label><textarea id="confirm-reason" rows="3" placeholder="Sababni yozing..."></textarea></div>` : ''}
      </div>
      <div class="modal-f">
        <button class="btn btn-outline" type="button" data-close-modal="confirm-modal">Bekor qilish</button>
        <button class="btn ${o.danger ? 'btn-danger' : 'btn-acc'}" type="button" id="confirm-ok">${o.okText || 'Davom etish'}</button>
      </div>
    </div>`;
  let scrim = document.getElementById('scrim');
  if (!scrim) {
    scrim = document.createElement('div');
    scrim.id = 'scrim';
    scrim.className = 'scrim';
    document.body.appendChild(scrim);
  }
  scrim.classList.add('on');
  const wrap = document.createElement('div');
  wrap.innerHTML = html;
  const modal = wrap.firstElementChild;
  document.body.appendChild(modal);
  modal.querySelector('#confirm-ok').onclick = () => {
    const reason = modal.querySelector('#confirm-reason')?.value?.trim();
    if (o.reasonField && !reason) {
      toast('Sabab kiritilishi shart', 'warn');
      return;
    }
    closeModal('confirm-modal');
    setTimeout(() => modal.remove(), 220);
    onConfirm && onConfirm(reason);
  };
};

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

// ---------- ESC closes any open modal / menu / drawer ----------
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.menu.on').forEach(m => m.classList.remove('on'));
    closeModal();
    const d = document.getElementById('mob-drawer');
    if (d?.classList.contains('on')) toggleDrawer();
  }
});
