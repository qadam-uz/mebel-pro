/* ===========================================================================
   Mebel Pro — seed data shared by all prototype apps
   Static — no backend, no persistence. Demo numbers only.

   v1 model (PICKUP-ONLY, no delivery / no payroll / no refunds):
     order state machine: new → confirmed → cutting →
       edge_banding (only if any part is banded) → ready → completed
       + cancelled (from any pre-completed state)
     Money lives in a separate finance module (incomes + expenses),
     never on the order. Stock auto-decrements at job completion;
     revert restores it. No reservation.
   =========================================================================== */

window.SEED = (() => {
  // ----- Branches -----
  const branches = [
    { id: 'yunusobod', city: 'Toshkent', name: 'Yunusobod', addr: "Buyuk Ipak Yo'li 142", phone: '+998 71 200 30 41', status: 'active', hours: 'Du–Sh · 09:00–19:00' },
    { id: 'chilonzor', city: 'Toshkent', name: 'Chilonzor', addr: 'Chilonzor 9-mavze 32', phone: '+998 71 200 30 42', status: 'active', hours: 'Du–Sh · 09:00–19:00' },
    { id: 'yangiyol', city: 'Toshkent vil.', name: "Yangiyo'l", addr: 'Mustaqillik 5', phone: '+998 71 200 30 43', status: 'temporarily_closed', closedReason: 'Texnik ta\'mirlash · 22-maygacha', hours: 'yopiq' }
  ];

  // ----- Platform-wide material catalog -----
  // Two KINDS:
  //   kind 'sheet' — type dsp/mdf/plywood/…, thickness_mm, color, decor?,
  //                  sheetLen/sheetWid (mm), grain (bool); priced/stocked per sheet.
  //   kind 'edge'  — thickness_mm (0.4 / 2.0), color, decor?;
  //                  priced/stocked per metre; no sheet size, no grain.
  const materials = [
    // sheets
    { id: 'm01', kind: 'sheet', type: 'dsp', name: 'LDSP H1334 ST9 · Dub Sonoma · 2750×1830', thickness: 18, color: 'Dub Sonoma', decor: 'H1334', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-1' },
    { id: 'm02', kind: 'sheet', type: 'dsp', name: 'LDSP K001 PW · Belarus dub · 2750×1830', thickness: 16, color: 'Dub Belarus', decor: 'K001', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-2' },
    { id: 'm03', kind: 'sheet', type: 'dsp', name: "LDSP 8198 · Ladzio yong'oq · 2750×1830", thickness: 18, color: "Yong'oq", decor: '8198', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-3' },
    { id: 'm04', kind: 'sheet', type: 'dsp', name: 'LDSP 0011 PR · Oq baxmal · 2750×1830', thickness: 18, color: 'Oq', decor: '0011', sheetLen: 2750, sheetWid: 1830, grain: false, status: 'active', sw: 'sw-4' },
    // same spec (MDF 16 mm · Qum) carried in two sheet sizes — two separate catalog materials
    { id: 'm05', kind: 'sheet', type: 'mdf', name: 'MDF 16 mm · qum rang · 2800×2070', thickness: 16, color: 'Qum', sheetLen: 2800, sheetWid: 2070, grain: false, status: 'active', sw: 'sw-5' },
    { id: 'm11', kind: 'sheet', type: 'mdf', name: 'MDF 16 mm · qum rang · 2750×1830', thickness: 16, color: 'Qum', sheetLen: 2750, sheetWid: 1830, grain: false, status: 'active', sw: 'sw-5' },
    { id: 'm06', kind: 'sheet', type: 'plywood', name: 'Fanera berioz · 8 mm · 2440×1220', thickness: 8, color: 'Berioz', sheetLen: 2440, sheetWid: 1220, grain: false, status: 'active', sw: 'sw-6' },
    { id: 'm07', kind: 'sheet', type: 'mdf', name: 'MDF 19 mm · oq glyans · 2800×2070', thickness: 19, color: 'Oq glyans', sheetLen: 2800, sheetWid: 2070, grain: false, status: 'active', sw: 'sw-4' },
    { id: 'm08', kind: 'sheet', type: 'dsp', name: 'LDSP H3309 · Mocca · 2750×1830', thickness: 18, color: 'Mocca', decor: 'H3309', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-9' },
    { id: 'm09', kind: 'sheet', type: 'plywood', name: 'Fanera oq qayin · 12 mm · 2440×1220', thickness: 12, color: 'Oq qayin', sheetLen: 2440, sheetWid: 1220, grain: false, status: 'active', sw: 'sw-10' },
    { id: 'm10', kind: 'sheet', type: 'mdf', name: 'MDF 8 mm · texnik · 2800×2070', thickness: 8, color: 'Texnik', sheetLen: 2800, sheetWid: 2070, grain: false, status: 'inactive', sw: 'sw-5' },
    // edge band
    { id: 'eb04', kind: 'edge', name: 'Krom PVC 0.4 mm · Dub Sonoma', thickness: 0.4, color: 'Dub Sonoma', decor: 'H1334', status: 'active', sw: 'sw-1' },
    { id: 'eb20', kind: 'edge', name: 'Krom PVC 2.0 mm · Dub Sonoma', thickness: 2.0, color: 'Dub Sonoma', decor: 'H1334', status: 'active', sw: 'sw-1' },
    { id: 'eb04q', kind: 'edge', name: 'Krom PVC 0.4 mm · Qum', thickness: 0.4, color: 'Qum', status: 'active', sw: 'sw-5' },
    { id: 'eb20w', kind: 'edge', name: 'Krom PVC 2.0 mm · Oq', thickness: 2.0, color: 'Oq', status: 'active', sw: 'sw-4' }
  ];

  // Per-branch selection: branch picks materials it carries with its own
  // price + min_stock.  stock_item shape: { branchId, matId, onHand, minStock,
  // priceTiyin (per sheet for sheets, per metre for edge), status }.
  // NO reserved, NO available.
  const branchMaterials = [
    { branchId: 'yunusobod', matId: 'm01', priceTiyin: 41000000, minStock: 20, onHand: 142, status: 'active' },
    { branchId: 'yunusobod', matId: 'm02', priceTiyin: 38000000, minStock: 20, onHand: 96, status: 'active' },
    { branchId: 'yunusobod', matId: 'm03', priceTiyin: 42500000, minStock: 15, onHand: 61, status: 'active' },
    { branchId: 'yunusobod', matId: 'm04', priceTiyin: 32000000, minStock: 30, onHand: 12, status: 'active' }, // low
    { branchId: 'yunusobod', matId: 'm05', priceTiyin: 29500000, minStock: 25, onHand: 84, status: 'active' },
    { branchId: 'yunusobod', matId: 'm11', priceTiyin: 28500000, minStock: 20, onHand: 47, status: 'active' }, // same decor as m05, smaller sheet
    { branchId: 'yunusobod', matId: 'm06', priceTiyin: 24000000, minStock: 10, onHand: 42, status: 'active' },
    { branchId: 'yunusobod', matId: 'm08', priceTiyin: 44500000, minStock: 15, onHand: 38, status: 'active' },
    { branchId: 'yunusobod', matId: 'eb04', priceTiyin: 320000, minStock: 200, onHand: 1840, status: 'active' }, // per metre
    { branchId: 'yunusobod', matId: 'eb20', priceTiyin: 680000, minStock: 150, onHand: 92, status: 'active' }, // low (per metre)
    { branchId: 'chilonzor', matId: 'm01', priceTiyin: 41500000, minStock: 20, onHand: 110, status: 'active' },
    { branchId: 'chilonzor', matId: 'm02', priceTiyin: 38500000, minStock: 20, onHand: 4, status: 'active' }, // low
    { branchId: 'chilonzor', matId: 'm05', priceTiyin: 30000000, minStock: 20, onHand: 56, status: 'active' },
    { branchId: 'chilonzor', matId: 'm06', priceTiyin: 24500000, minStock: 12, onHand: 28, status: 'active' },
    { branchId: 'chilonzor', matId: 'eb04q', priceTiyin: 300000, minStock: 200, onHand: 960, status: 'active' },
    { branchId: 'chilonzor', matId: 'eb20w', priceTiyin: 640000, minStock: 150, onHand: 410, status: 'active' },
    { branchId: 'yangiyol', matId: 'm01', priceTiyin: 40500000, minStock: 15, onHand: 35, status: 'active' },
    { branchId: 'yangiyol', matId: 'm04', priceTiyin: 31500000, minStock: 20, onHand: 8, status: 'active' }, // low
    { branchId: 'yangiyol', matId: 'eb04', priceTiyin: 310000, minStock: 150, onHand: 520, status: 'active' }
  ];

  // ----- Suppliers (added on demand from stock-in) -----
  const suppliers = [
    { id: 'sup01', workshopId: 'ws-01', name: 'Egger Distribution UZ', phone: '+998 71 150 20 10', note: 'LDSP · asosiy yetkazib beruvchi', status: 'active' },
    { id: 'sup02', workshopId: 'ws-01', name: 'Kronospan Trade', phone: '+998 71 150 20 11', note: 'MDF va fanera', status: 'active' },
    { id: 'sup03', workshopId: 'ws-01', name: 'Rehau Krom', phone: '+998 90 330 40 50', note: 'PVC krom lentasi', status: 'active' },
    { id: 'sup04', workshopId: 'ws-01', name: 'Lokal bozor · Sebzor', phone: null, note: 'Tezkor mayda partiya', status: 'inactive' }
  ];

  // ----- Workshop users -----
  // No fixed roles. Coarse per-branch permission grants only; the owner holds
  // all grants implicitly (isOwner). No compensation data on users.
  const users = [
    { id: 'u01', name: 'Hasan Karimov', login: 'hasan', phone: '+998 90 100 30 30', isOwner: true, homeBranchId: 'yunusobod', status: 'active', lastLogin: '16-may, 09:14', initials: 'HK' },
    { id: 'u02', name: 'Aziza Rasulova', login: 'aziza', phone: '+998 90 100 30 31', isOwner: false, homeBranchId: 'yunusobod', status: 'active', lastLogin: '16-may, 09:42', initials: 'AR', grants: { manage_orders: ['yunusobod', 'chilonzor'], view_dashboard: ['yunusobod', 'chilonzor'], manage_inventory: ['yunusobod'] } },
    { id: 'u03', name: 'Bahodir Tursunov', login: 'bahodir', phone: '+998 90 100 30 32', isOwner: false, homeBranchId: 'yunusobod', status: 'active', lastLogin: '16-may, 08:30', initials: 'BT', grants: { process_production: ['yunusobod'] } },
    { id: 'u04', name: 'Olim Hojiyev', login: 'olim', phone: '+998 90 100 30 33', isOwner: false, homeBranchId: 'yunusobod', status: 'active', lastLogin: '15-may, 17:50', initials: 'OH', grants: { process_production: ['yunusobod'] } },
    { id: 'u05', name: 'Sherzod Aliyev', login: 'sherzod', phone: '+998 90 100 30 34', isOwner: false, homeBranchId: 'yunusobod', status: 'active', lastLogin: '16-may, 06:15', initials: 'SA', grants: { manage_finance: ['yunusobod', 'chilonzor'], view_finance_reports: ['yunusobod', 'chilonzor'] } },
    { id: 'u06', name: 'Dilshod Yo\'ldoshev', login: 'dilshod', phone: '+998 90 100 30 35', isOwner: false, homeBranchId: 'chilonzor', status: 'active', lastLogin: '15-may, 18:00', initials: 'DY', grants: { manage_orders: ['chilonzor'], view_dashboard: ['chilonzor'] } },
    { id: 'u07', name: 'Komron Saidov', login: 'komron', phone: '+998 90 100 30 36', isOwner: false, homeBranchId: 'chilonzor', status: 'active', lastLogin: '15-may, 16:42', initials: 'KS', grants: { process_production: ['chilonzor'] } },
    { id: 'u08', name: 'Madina Yusupova', login: 'madina', phone: '+998 90 100 30 37', isOwner: false, homeBranchId: 'yangiyol', status: 'blocked', lastLogin: '02-may, 15:00', initials: 'MY', grants: {} }
  ];

  // ----- Clients (platform-wide) -----
  const clients = [
    { id: 'c01', name: "Akmal Norqo'ziyev", phone: '+998 90 100 30 60', initials: 'AN', status: 'active', ordersCount: 4 },
    { id: 'c02', name: 'Dilshod Tursunov', phone: '+998 90 100 30 61', initials: 'DT', status: 'active', ordersCount: 2 },
    { id: 'c03', name: "Madina Yo'ldosheva", phone: '+998 90 100 30 62', initials: 'MY', status: 'active', ordersCount: 1 },
    { id: 'c04', name: 'Sherzod Ahmedov', phone: '+998 90 100 30 63', initials: 'SA', status: 'active', ordersCount: 3 }
  ];

  // ----- Cutting drafts and results -----
  // Each cutting has a parts list (per-part material + source), and one or more
  // algorithm results (one is `chosen`). The chosen algorithm's numbers are
  // mirrored onto the cutting itself as flat fields for legacy callers.
  const cuttings = [
    {
      id: 'cr-0091', status: 'confirmed', orderId: 'ORD-2026-000091',
      branchId: 'yunusobod', when: '14-may, 09:24',
      partList: [
        { ref: 'p01', matId: 'm01', source: 'shop', l: 1800, w: 400, qty: 2, edges: { t: 2.0, b: 2.0, l: null, r: null } },
        { ref: 'p02', matId: 'm01', source: 'shop', l:  700, w: 400, qty: 4, edges: { t: 2.0, b: 2.0, l: null, r: null } },
        { ref: 'p03', matId: 'm01', source: 'shop', l:  600, w: 350, qty: 8, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 8.2, cutLen: 124.6, edgeLen: { 0.4: 18.2, 2.0: 12.8 }, sheetsByMat: { m01: 6 } }
      ],
      // mirrored from the chosen algorithm
      parts: 14, sheets: 6, wastePct: 8.2, cutLen: 124.6, edgeLen: { 0.4: 18.2, 2.0: 12.8 }, algoVer: 'ffd-guillotine-v1',
      // legacy single-material fields some pages still read
      matId: 'm01', source: 'shop'
    },
    // A live multi-material draft for the demo — DSP shelves + MDF backs + an own-material part
    {
      id: 'cr-0085', status: 'draft', orderId: null,
      branchId: null, when: '16-may, 08:12',
      partList: [
        { ref: 'p01', matId: 'm01', source: 'shop', l: 1800, w: 400, qty: 2, edges: { t: 2.0, b: 2.0, l: null, r: null } },
        { ref: 'p02', matId: 'm01', source: 'shop', l:  700, w: 400, qty: 4, edges: { t: 2.0, b: 2.0, l: null, r: null } },
        { ref: 'p03', matId: 'm05', source: 'own',  l:  600, w: 400, qty: 2, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } },
        { ref: 'p04', matId: 'm05', source: 'shop', l:  800, w: 300, qty: 1, edges: { t: null, b: null, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true,  wastePct:  9.8, cutLen: 64.4, edgeLen: { 0.4: 4.8, 2.0: 8.2 }, sheetsByMat: { m01: 2, m05: 1 } },
        { name: 'best-fit-2d',    ver: '1.0', chosen: false, wastePct: 11.2, cutLen: 58.2, edgeLen: { 0.4: 4.8, 2.0: 8.2 }, sheetsByMat: { m01: 2, m05: 1 } },
        { name: 'shelf-pack',     ver: '1.0', chosen: false, wastePct: 18.4, cutLen: 52.8, edgeLen: { 0.4: 4.8, 2.0: 8.2 }, sheetsByMat: { m01: 3, m05: 1 } }
      ],
      parts: 9, sheets: 3, wastePct: 9.8, cutLen: 64.4, edgeLen: { 0.4: 4.8, 2.0: 8.2 }, algoVer: 'ffd-guillotine-v1',
      matId: 'm01', source: 'shop'
    },
    // A simpler single-material draft (no banding at all → would skip edge_banding)
    {
      id: 'cr-0086', status: 'draft', orderId: null, branchId: null, when: '15-may, 19:42',
      partList: [
        { ref: 'p01', matId: 'm05', source: 'shop', l: 1200, w: 600, qty: 1, edges: { t: null, b: null, l: null, r: null } },
        { ref: 'p02', matId: 'm05', source: 'shop', l:  800, w: 400, qty: 4, edges: { t: null, b: null, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 14.6, cutLen: 18.2, edgeLen: {}, sheetsByMat: { m05: 1 } }
      ],
      parts: 5, sheets: 1, wastePct: 14.6, cutLen: 18.2, edgeLen: {}, algoVer: 'ffd-guillotine-v1',
      matId: 'm05', source: 'shop'
    },
    {
      id: 'cr-0072', status: 'confirmed', orderId: 'ORD-2026-000072',
      branchId: 'yunusobod', when: '13-may, 14:32',
      partList: [
        { ref: 'p01', matId: 'm05', source: 'shop', l: 1400, w: 600, qty: 2, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 6.1, cutLen: 88.4, edgeLen: { 0.4: 12.0 }, sheetsByMat: { m05: 7 } }
      ],
      parts: 8, sheets: 7, wastePct: 6.1, cutLen: 88.4, edgeLen: { 0.4: 12.0 }, algoVer: 'ffd-guillotine-v1',
      matId: 'm05', source: 'shop'
    },

    // --- Confirmed results bound to the remaining orders (immutable, one per
    //     order; no `cr-mock`). Each is branchId = its order's branch and its
    //     metrics cohere with that order's price snapshot + production stamps. ---
    {
      id: 'cr-0090', status: 'confirmed', orderId: 'ORD-2026-000090',
      branchId: 'yunusobod', when: '13-may, 18:38',
      partList: [
        { ref: 'p01', matId: 'm05', source: 'shop', l: 900, w: 600, qty: 4, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } },
        { ref: 'p02', matId: 'm05', source: 'shop', l: 600, w: 400, qty: 2, edges: { t: 0.4, b: 0.4, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 11.4, cutLen: 71.2, edgeLen: { 0.4: 14.4 }, sheetsByMat: { m05: 6 } }
      ],
      parts: 6, sheets: 6, wastePct: 11.4, cutLen: 71.2, edgeLen: { 0.4: 14.4 }, algoVer: 'ffd-guillotine-v1',
      matId: 'm05', source: 'shop'
    },
    {
      id: 'cr-0089', status: 'confirmed', orderId: 'ORD-2026-000089',
      branchId: 'yunusobod', when: '13-may, 11:20',
      partList: [
        { ref: 'p01', matId: 'm01', source: 'shop', l: 1200, w: 500, qty: 2, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } },
        { ref: 'p02', matId: 'm01', source: 'shop', l: 800, w: 400, qty: 4, edges: { t: 0.4, b: 0.4, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 9.2, cutLen: 52.6, edgeLen: { 0.4: 16.4 }, sheetsByMat: { m01: 2 } }
      ],
      parts: 6, sheets: 2, wastePct: 9.2, cutLen: 52.6, edgeLen: { 0.4: 16.4 }, algoVer: 'ffd-guillotine-v1',
      matId: 'm01', source: 'shop'
    },
    {
      id: 'cr-0088', status: 'confirmed', orderId: 'ORD-2026-000088',
      branchId: 'yunusobod', when: '12-may, 14:26',
      partList: [
        { ref: 'p01', matId: 'm06', source: 'shop', l: 1400, w: 700, qty: 4, edges: { t: null, b: null, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 7.8, cutLen: 41.0, edgeLen: {}, sheetsByMat: { m06: 4 } }
      ],
      parts: 4, sheets: 4, wastePct: 7.8, cutLen: 41.0, edgeLen: {}, algoVer: 'ffd-guillotine-v1',
      matId: 'm06', source: 'shop'
    },
    {
      id: 'cr-0087', status: 'confirmed', orderId: 'ORD-2026-000087',
      branchId: 'yunusobod', when: '16-may, 08:06',
      partList: [
        { ref: 'p01', matId: 'm02', source: 'shop', l: 700, w: 500, qty: 3, edges: { t: null, b: null, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 13.0, cutLen: 14.8, edgeLen: {}, sheetsByMat: { m02: 1 } }
      ],
      parts: 3, sheets: 1, wastePct: 13.0, cutLen: 14.8, edgeLen: {}, algoVer: 'ffd-guillotine-v1',
      matId: 'm02', source: 'shop'
    },
    {
      id: 'cr-o086', status: 'confirmed', orderId: 'ORD-2026-000086',
      branchId: 'yunusobod', when: '16-may, 08:58',
      partList: [
        { ref: 'p01', matId: 'm05', source: 'shop', l: 720, w: 80, qty: 4, edges: { t: null, b: null, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 22.5, cutLen: 9.6, edgeLen: {}, sheetsByMat: { m05: 1 } }
      ],
      parts: 4, sheets: 1, wastePct: 22.5, cutLen: 9.6, edgeLen: {}, algoVer: 'ffd-guillotine-v1',
      matId: 'm05', source: 'shop'
    },
    {
      id: 'cr-o085', status: 'confirmed', orderId: 'ORD-2026-000085',
      branchId: 'chilonzor', when: '16-may, 09:28',
      partList: [
        { ref: 'p01', matId: 'm01', source: 'shop', l: 2000, w: 600, qty: 4, edges: { t: 2.0, b: 2.0, l: null, r: null } },
        { ref: 'p02', matId: 'm01', source: 'shop', l: 900, w: 500, qty: 8, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } },
        { ref: 'p03', matId: 'm01', source: 'shop', l: 560, w: 400, qty: 6, edges: { t: 0.4, b: 0.4, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true,  wastePct: 10.6, cutLen: 188.4, edgeLen: { 0.4: 22.0, 2.0: 14.0 }, sheetsByMat: { m01: 8 } },
        { name: 'best-fit-2d',    ver: '1.0', chosen: false, wastePct: 12.1, cutLen: 176.2, edgeLen: { 0.4: 22.0, 2.0: 14.0 }, sheetsByMat: { m01: 8 } }
      ],
      parts: 18, sheets: 8, wastePct: 10.6, cutLen: 188.4, edgeLen: { 0.4: 22.0, 2.0: 14.0 }, algoVer: 'ffd-guillotine-v1',
      matId: 'm01', source: 'shop'
    },
    {
      id: 'cr-0856', status: 'confirmed', orderId: 'ORD-2026-000856',
      branchId: 'chilonzor', when: '08-apr, 10:54',
      partList: [
        { ref: 'p01', matId: 'm06', source: 'shop', l: 1100, w: 600, qty: 3, edges: { t: null, b: null, l: null, r: null } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 9.0, cutLen: 24.2, edgeLen: {}, sheetsByMat: { m06: 2 } }
      ],
      parts: 3, sheets: 2, wastePct: 9.0, cutLen: 24.2, edgeLen: {}, algoVer: 'ffd-guillotine-v1',
      matId: 'm06', source: 'shop'
    }
  ];

  // ----- Per-branch pricing knobs the order step reads -----
  // perSheetTiyin = cutting-service rate (per sheet, integer tiyin)
  // edgeRateTiyin = edge-banding rate (per metre, by thickness in mm)
  // NO advance %, NO delivery fee (pickup-only; money is a separate module).
  const branchPricing = {
    yunusobod: { perSheetTiyin: 10000000, edgeRateTiyin: { 0.4: 200000, 2.0: 450000 } },
    chilonzor: { perSheetTiyin:  9500000, edgeRateTiyin: { 0.4: 200000, 2.0: 420000 } },
    yangiyol:  { perSheetTiyin:  9000000, edgeRateTiyin: { 0.4: 180000, 2.0: 400000 } }
  };

  // ----- Orders -----
  // v1 order: pickup-only, no money on the order (frozen price snapshot only),
  // production stamps set at transitions.
  //   price snapshot: subtotalCuttingTiyin, subtotalMaterialsTiyin,
  //     subtotalEdgeBandingTiyin, discountTiyin, discountReason, totalTiyin
  //   production stamps: assignedCutter, assignedEdger,
  //     cutter, cutCompletedAt, sheetsUsed, cutCount,
  //     edger, edgeCompletedAt, edgeLengthByThickness, pickedUpAt
  //   per-item material_source lives on the cutting partList (source 'shop'|'own')
  //   cancel: cancelledAt, cancelledBy, cancelReason (mandatory free text)
  const orders = [
    {
      id: 'ORD-2026-000091', state: 'cutting', workshopId: 'ws-01', branchId: 'yunusobod', clientId: 'c01',
      cuttingId: 'cr-0091',
      subtotalCuttingTiyin: 60000000, subtotalMaterialsTiyin: 246000000, subtotalEdgeBandingTiyin: 8200000,
      discountTiyin: 0, discountReason: null, totalTiyin: 314200000,
      assignedCutter: 'u03', assignedEdger: 'u04',
      placedAt: '14-may, 09:42', placedBy: 'c01', confirmedAt: '14-may, 10:05', confirmedBy: 'u02',
      dueAt: '17-may, 14:00', priority: 5
    },
    {
      id: 'ORD-2026-000090', state: 'edge_banding', workshopId: 'ws-01', branchId: 'yunusobod', clientId: 'c02',
      cuttingId: 'cr-0090',
      subtotalCuttingTiyin: 30000000, subtotalMaterialsTiyin: 158000000, subtotalEdgeBandingTiyin: 5400000,
      discountTiyin: 0, discountReason: null, totalTiyin: 193400000,
      assignedCutter: 'u03', assignedEdger: 'u04',
      cutter: 'u03', cutCompletedAt: '16-may, 09:18', sheetsUsed: { m05: 6 }, cutCount: 6,
      placedAt: '13-may, 18:30', confirmedAt: '13-may, 19:00', confirmedBy: 'u02',
      dueAt: '17-may, 17:00', priority: 4
    },
    {
      id: 'ORD-2026-000089', state: 'ready', workshopId: 'ws-01', branchId: 'yunusobod', clientId: 'c03',
      cuttingId: 'cr-0089',
      subtotalCuttingTiyin: 12000000, subtotalMaterialsTiyin: 81000000, subtotalEdgeBandingTiyin: 2200000,
      discountTiyin: 0, discountReason: null, totalTiyin: 95200000,
      assignedCutter: 'u03', assignedEdger: 'u04',
      cutter: 'u03', cutCompletedAt: '14-may, 14:00', sheetsUsed: { m01: 2 }, cutCount: 2,
      edger: 'u04', edgeCompletedAt: '14-may, 17:50', edgeLengthByThickness: { '0.4': 16400 },
      placedAt: '13-may, 11:15', confirmedAt: '13-may, 12:00', confirmedBy: 'u02',
      dueAt: '17-may, 16:00', priority: 3
    },
    {
      id: 'ORD-2026-000088', state: 'ready', workshopId: 'ws-01', branchId: 'yunusobod', clientId: 'c04',
      cuttingId: 'cr-0088',
      subtotalCuttingTiyin: 18000000, subtotalMaterialsTiyin: 144000000, subtotalEdgeBandingTiyin: 0,
      discountTiyin: 5000000, discountReason: 'Doimiy mijoz chegirmasi', totalTiyin: 157000000,
      assignedCutter: 'u03', assignedEdger: null,
      cutter: 'u03', cutCompletedAt: '15-may, 11:30', sheetsUsed: { m06: 4 }, cutCount: 4,
      placedAt: '12-may, 14:20', confirmedAt: '12-may, 15:00', confirmedBy: 'u02',
      dueAt: 'bugun · 14:30', priority: 2
    },
    {
      id: 'ORD-2026-000087', state: 'confirmed', workshopId: 'ws-01', branchId: 'yunusobod', clientId: 'c01',
      cuttingId: 'cr-0087',
      subtotalCuttingTiyin: 9000000, subtotalMaterialsTiyin: 42000000, subtotalEdgeBandingTiyin: 0,
      discountTiyin: 0, discountReason: null, totalTiyin: 51000000,
      assignedCutter: null, assignedEdger: null,
      placedAt: '16-may, 08:10', confirmedAt: '16-may, 08:40', confirmedBy: 'u02',
      dueAt: '18-may', priority: 6
    },
    {
      id: 'ORD-2026-000086', state: 'new', workshopId: 'ws-01', branchId: 'yunusobod', clientId: 'c02',
      cuttingId: 'cr-o086',
      subtotalCuttingTiyin: 6000000, subtotalMaterialsTiyin: 29500000, subtotalEdgeBandingTiyin: 0,
      discountTiyin: 0, discountReason: null, totalTiyin: 35500000,
      assignedCutter: null, assignedEdger: null,
      placedAt: '16-may, 09:00', placedBy: 'c02', dueAt: '17-may', priority: 1
    },
    {
      id: 'ORD-2026-000085', state: 'new', workshopId: 'ws-01', branchId: 'chilonzor', clientId: 'c03',
      cuttingId: 'cr-o085',
      subtotalCuttingTiyin: 48000000, subtotalMaterialsTiyin: 320000000, subtotalEdgeBandingTiyin: 11200000,
      discountTiyin: 0, discountReason: null, totalTiyin: 379200000,
      assignedCutter: null, assignedEdger: null,
      placedAt: '16-may, 09:30', placedBy: 'c03', dueAt: '19-may', priority: 7
    },
    {
      id: 'ORD-2026-000072', state: 'completed', workshopId: 'ws-01', branchId: 'yunusobod', clientId: 'c01',
      cuttingId: 'cr-0072',
      subtotalCuttingTiyin: 42000000, subtotalMaterialsTiyin: 206500000, subtotalEdgeBandingTiyin: 4500000,
      discountTiyin: 0, discountReason: null, totalTiyin: 253000000,
      assignedCutter: 'u03', assignedEdger: 'u04',
      cutter: 'u03', cutCompletedAt: '12-may, 11:00', sheetsUsed: { m05: 7 }, cutCount: 7,
      edger: 'u04', edgeCompletedAt: '12-may, 16:20', edgeLengthByThickness: { '0.4': 12000 },
      pickedUpAt: '13-may, 14:30',
      placedAt: '10-may, 14:30', confirmedAt: '10-may, 15:10', confirmedBy: 'u02', priority: 0
    },
    {
      id: 'ORD-2026-000856', state: 'cancelled', workshopId: 'ws-01', branchId: 'chilonzor', clientId: 'c01',
      cuttingId: 'cr-0856',
      subtotalCuttingTiyin: 14000000, subtotalMaterialsTiyin: 48000000, subtotalEdgeBandingTiyin: 0,
      discountTiyin: 0, discountReason: null, totalTiyin: 62000000,
      assignedCutter: null, assignedEdger: null,
      placedAt: '08-apr, 11:00', cancelledAt: '09-apr, 14:00', cancelledBy: 'u06',
      cancelReason: 'Mijoz boshqa filialni tanladi', priority: 0
    }
  ];

  // ----- Finance: income rows -----
  // type 'order_payment' requires orderId; 'other' has no orderId.
  // amount_tiyin > 0 (full or partial). status recorded|voided.
  // Recorded/voided ONLY by a user with manage_finance (u05 — the accountant,
  // grants on yunusobod + chilonzor). method ∈ cash|bank_transfer|other (NO
  // `card` — a terminal/karta payment is bank_transfer). An order_payment's
  // branchId equals its order's branch. Σ recorded payments per order ≤ total.
  const incomes = [
    { id: 'in01', workshopId: 'ws-01', branchId: 'yunusobod', type: 'order_payment', orderId: 'ORD-2026-000072', amountTiyin: 253000000, method: 'bank_transfer', receivedOn: '13-may', note: "To'liq to'lov", status: 'recorded', recordedByUserId: 'u05' },
    { id: 'in02', workshopId: 'ws-01', branchId: 'yunusobod', type: 'order_payment', orderId: 'ORD-2026-000089', amountTiyin: 50000000, method: 'cash', receivedOn: '14-may', note: 'Qisman to\'lov', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'in03', workshopId: 'ws-01', branchId: 'yunusobod', type: 'order_payment', orderId: 'ORD-2026-000088', amountTiyin: 157000000, method: 'cash', receivedOn: '15-may', note: null, status: 'recorded', recordedByUserId: 'u05' },
    { id: 'in04', workshopId: 'ws-01', branchId: 'yunusobod', type: 'order_payment', orderId: 'ORD-2026-000091', amountTiyin: 150000000, method: 'bank_transfer', receivedOn: '14-may', note: 'Oldindan (karta terminali)', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'in05', workshopId: 'ws-01', branchId: 'yunusobod', type: 'other', orderId: null, amountTiyin: 12000000, method: 'cash', receivedOn: '11-may', note: 'Eski qoldiq material sotuvi', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'in06', workshopId: 'ws-01', branchId: 'chilonzor', type: 'order_payment', orderId: 'ORD-2026-000856', amountTiyin: 31000000, method: 'cash', receivedOn: '08-apr', note: 'Bekor qilingan — qaytarildi', status: 'voided', voidedReason: 'Buyurtma bekor qilindi, pul xarajat sifatida qaytarildi', voidedByUserId: 'u05', recordedByUserId: 'u05' }
  ];

  // ----- Finance: expense rows -----
  // category: rent|utilities|raw_materials|supplies|transport|equipment|
  //           marketing|taxes_and_fees|salary|other
  // A worker's pay is booked here as a 'salary' expense (no payroll module).
  const expenses = [
    { id: 'e01', workshopId: 'ws-01', branchId: 'yunusobod', category: 'rent', amountTiyin: 480000000, incurredOn: '01-may', description: 'May oyi ijarasi', vendor: 'Tinchlik Bldg LLC', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e02', workshopId: 'ws-01', branchId: 'yunusobod', category: 'utilities', amountTiyin: 24000000, incurredOn: '05-may', description: 'Elektr energiya · aprel', vendor: 'Hududgaz', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e03', workshopId: 'ws-01', branchId: null, category: 'marketing', amountTiyin: 80000000, incurredOn: '08-may', description: 'Reklama · Telegram kanal', vendor: 'Mediastar', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e04', workshopId: 'ws-01', branchId: 'chilonzor', category: 'supplies', amountTiyin: 35000000, incurredOn: '12-may', description: 'Aksessuar va vint partiyasi', vendor: 'Hardware.uz', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e05', workshopId: 'ws-01', branchId: 'yunusobod', category: 'raw_materials', amountTiyin: 164000000, incurredOn: '06-may', description: 'LDSP partiya · 40 list', vendor: 'Egger Distribution UZ', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e06', workshopId: 'ws-01', branchId: 'yunusobod', category: 'salary', amountTiyin: 18500000, incurredOn: '15-may', description: 'Bahodir T. · 13–15 may · 19 list kesildi (qo\'lda hisoblandi)', vendor: null, status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e07', workshopId: 'ws-01', branchId: 'yunusobod', category: 'salary', amountTiyin: 12300000, incurredOn: '15-may', description: 'Olim H. · 13–15 may · 28.4 m krom (qo\'lda hisoblandi)', vendor: null, status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e08', workshopId: 'ws-01', branchId: 'chilonzor', category: 'transport', amountTiyin: 12500000, incurredOn: '13-may', description: 'Filiallararo material tashish', vendor: 'JTKlogistika', status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e09', workshopId: 'ws-01', branchId: 'chilonzor', category: 'other', amountTiyin: 31000000, incurredOn: '09-apr', description: 'ORD-2026-000856 bekor — mijozga pul qaytarildi', vendor: null, status: 'recorded', recordedByUserId: 'u05' },
    { id: 'e10', workshopId: 'ws-01', branchId: 'yunusobod', category: 'equipment', amountTiyin: 145000000, incurredOn: '03-may', description: 'Kromchi mashinasiga ehtiyot qism', vendor: 'IMA AG', status: 'voided', voidedReason: 'Notog\'ri summa kiritilgan', voidedByUserId: 'u05', recordedByUserId: 'u05' }
  ];

  // ----- Worker production report (derived from order stamps) -----
  // The accountant reads this per user/period to compute pay by hand,
  // then books it as a 'salary' expense. NOT a payroll entity.
  const workerProduction = [
    { userId: 'u03', period: '13–15 may', branchId: 'yunusobod', sheetsCut: 19, cutCount: 19, ordersBanded: 0, metresBanded: 0 },
    { userId: 'u04', period: '13–15 may', branchId: 'yunusobod', sheetsCut: 0, cutCount: 0, ordersBanded: 2, metresBanded: 28.4 },
    { userId: 'u07', period: '13–15 may', branchId: 'chilonzor', sheetsCut: 6, cutCount: 6, ordersBanded: 0, metresBanded: 0 }
  ];

  // ----- Permissions catalog (v1) -----
  const permissions = [
    { key: 'view_dashboard', label: 'Asosiyni ko\'rish' },
    { key: 'manage_orders', label: 'Buyurtmalarni boshqarish' },
    { key: 'process_production', label: 'Kesish / krom yopishtirish' },
    { key: 'manage_catalog', label: 'Material katalogini boshqarish' },
    { key: 'manage_inventory', label: 'Omborni boshqarish' },
    { key: 'manage_finance', label: 'Moliyani boshqarish' },
    { key: 'view_finance_reports', label: 'Moliya hisobotlarini ko\'rish' }
  ];

  // ----- Workshops (for admin app) -----
  const workshops = [
    { id: 'ws-01', name: 'Furniture House', ownerName: 'Hasan Karimov', ownerPhone: '+998 90 100 30 30', status: 'active', createdOn: '12-jan 2026', branches: 3, orders30d: 142, mk: 'FH' },
    { id: 'ws-02', name: 'Toshkent Mebel', ownerName: 'Murod Yusupov', ownerPhone: '+998 90 100 30 40', status: 'active', createdOn: '04-feb 2026', branches: 2, orders30d: 88, mk: 'TM' },
    { id: 'ws-03', name: 'Mebel Markazi', ownerName: 'Bahodir Saidov', ownerPhone: '+998 90 100 30 50', status: 'active', createdOn: '21-feb 2026', branches: 1, orders30d: 34, mk: 'MM' },
    { id: 'ws-04', name: 'Buxoro Stol', ownerName: 'Olim Najimov', ownerPhone: '+998 90 100 30 60', status: 'blocked', blockedReason: 'Hisob to\'lov muddati o\'tib ketdi', createdOn: '08-mar 2026', branches: 1, orders30d: 0, mk: 'BS' },
    { id: 'ws-05', name: 'Samarqand Yog\'och', ownerName: 'Aziz Karimov', ownerPhone: '+998 90 100 30 70', status: 'active', createdOn: '14-apr 2026', branches: 2, orders30d: 26, mk: 'SY' }
  ];

  // ----- Platform users -----
  const platformUsers = [
    { id: 'p01', name: 'Nuriddin Obidjonov', login: 'nuriddin', phone: '+998 90 200 00 00', status: 'active', lastLogin: '16-may, 09:00', initials: 'NO' },
    { id: 'p02', name: 'Aziza Saidova', login: 'aziza', phone: '+998 90 200 00 01', status: 'active', lastLogin: '15-may, 18:30', initials: 'AS' },
    { id: 'p03', name: 'Sardor Tursunov', login: 'sardor', phone: '+998 90 200 00 02', status: 'active', lastLogin: '12-may, 14:20', initials: 'ST' }
  ];

  // ----- Scheduled jobs -----
  // v1 in-process scheduler — exactly these two (see docs platform.md).
  // Cutting drafts have NO expiry job: they persist until the client deletes
  // them or hits the 50-draft cap. No auto-cleanup of drafts anywhere.
  // `running` guards a job from a concurrent run; a failed job records its
  // error and can be re-triggered manually.
  const jobs = [
    { id: 'cleanup-expired-sessions', name: 'cleanup-expired-sessions', schedule: 'Soatlik', lastRun: '19-may, 09:00', lastResult: 'ok', running: false, durationMs: 412, summary: '142 ta muddati o\'tgan sessiya o\'chirildi' },
    { id: 'daily-low-stock-summary', name: 'daily-low-stock-summary', schedule: 'Kunlik · 08:00', lastRun: '19-may, 08:00', lastResult: 'failed', running: false, durationMs: 30021, summary: 'Inventarizatsiya bazasiga ulanishda timeout', error: 'TimeoutError: connection to inventory DB timed out at 08:00:42 (trace tr-9f2a4c)', retriable: true }
  ];

  // ----- Error monitor -----
  // Per-row context so the monitor renders real per-error detail (not shared
  // literals): a real trace id, the affected workshops (nullable — null = not
  // tenant-attributable), masked context, a stack preview. `spike` flags a
  // code whose 24h count crossed the notify threshold.
  const errors = [
    { code: 'insufficient_stock', module: 'inventory', count24h: 12, count7d: 38, last: '19-may, 09:14', resolved: false, spike: true,
      msg: 'Stock decrement on Cutting done went below zero',
      traceId: 'tr-1a77e0', affectedWorkshops: ['ws-01'], affectedUser: 'u03',
      context: { order: 'ORD-2026-000090', material: 'm05', branch: 'yunusobod', onHand: 2, requested: 6 },
      stack: 'inventory/service.py:142 decrement_stock()\n  → orders/service.py:88 mark_cutting_done()' },
    { code: 'optimization_timeout', module: 'cutting', count24h: 3, count7d: 7, last: '18-may, 16:42', resolved: false, spike: false,
      msg: 'Cutting optimization exceeded 5s budget (84 parts)',
      traceId: 'tr-4c91b2', affectedWorkshops: null, affectedUser: null,
      context: { parts: 84, sheetsEstimated: 19, elapsedMs: 5012 },
      stack: 'cutting/solver.py:301 run_guillotine()\n  → cutting/api.py:54 optimise()' },
    { code: 'invalid_state_transition', module: 'orders', count24h: 2, count7d: 6, last: '19-may, 08:20', resolved: true, spike: false,
      msg: 'Attempted ready→cutting skip (revert is one step only)',
      traceId: 'tr-7d33aa', affectedWorkshops: ['ws-05'], affectedUser: null,
      context: { order: 'ORD-2026-000061', from: 'ready', to: 'cutting' },
      stack: 'orders/state_machine.py:77 assert_transition()' },
    { code: 'invalid_oauth_signature', module: 'identity', count24h: 1, count7d: 4, last: '19-may, 06:12', resolved: false, spike: false,
      msg: 'Telegram payload HMAC mismatch',
      traceId: 'tr-b50f18', affectedWorkshops: null, affectedUser: null,
      context: { authDateAgeSec: 41, ip: '213.230.•••.•••' },
      stack: 'identity/telegram.py:33 verify_hmac()' }
  ];

  // ----- Audit log (action half — support.md; status-change half = statusEvents) -----
  // workshopId on every row so the cross-workshop admin viewer renders the real
  // workshop name, never a hardcoded one.
  const auditLog = [
    { t: '19-may, 09:42', workshopId: 'ws-01', action: 'order.status_changed', actor: 'u02', detail: 'ORD-2026-000090 · cutting → edge_banding', module: 'orders' },
    { t: '19-may, 09:30', workshopId: 'ws-01', action: 'order.created', actor: 'c03', detail: 'ORD-2026-000085 · 8 list, garderob', module: 'orders' },
    { t: '19-may, 09:18', workshopId: 'ws-01', action: 'order.cut_completed', actor: 'u03', detail: 'ORD-2026-000090 · 6 list ishlatildi', module: 'orders' },
    { t: '19-may, 09:14', workshopId: 'ws-01', action: 'inventory.stock_in', actor: 'u02', detail: 'm03 · +40 list · Egger partiya', module: 'inventory' },
    { t: '15-may, 17:50', workshopId: 'ws-01', action: 'order.banding_completed', actor: 'u04', detail: 'ORD-2026-000089 · 16.4 m', module: 'orders' },
    { t: '15-may, 11:30', workshopId: 'ws-01', action: 'finance.expense_recorded', actor: 'u05', detail: 'salary · Bahodir T. · 185 000 so\'m', module: 'finance' },
    { t: '14-may, 10:05', workshopId: 'ws-01', action: 'order.confirmed', actor: 'u02', detail: 'ORD-2026-000091 · tasdiqlandi', module: 'orders' },
    { t: '14-may, 09:42', workshopId: 'ws-01', action: 'order.created', actor: 'c01', detail: 'ORD-2026-000091', module: 'orders' }
  ];

  // ----- Notifications -----
  const notifications = [
    { t: '16-may, 09:42', kind: 'order', read: false, title: "Yangi buyurtma · ORD-2026-000085", body: "Chilonzor · 8 list, garderob — tasdiqlash kerak", link: 'order-detail.html?id=ORD-2026-000085' },
    { t: '16-may, 09:14', kind: 'inventory', read: false, title: "Past zaxira · 4 ta material", body: "Yunusobod, Chilonzor — ko'rib chiqing", link: 'inventory.html' },
    { t: '16-may, 09:00', kind: 'order', read: false, title: "Tasdiqlanmagan buyurtma", body: "ORD-2026-000086 · ko'rib chiqing", link: 'order-detail.html?id=ORD-2026-000086' },
    { t: '15-may, 18:20', kind: 'order', read: true, title: "Buyurtma tugatildi · ORD-2026-000072", body: "Akmal Norqo'ziyev · mijoz olib ketdi", link: 'order-detail.html?id=ORD-2026-000072' },
    { t: '14-may, 09:42', kind: 'order', read: true, title: "Yangi buyurtma · ORD-2026-000091", body: "Akmal Norqo'ziyev · 4 shkaf + stol", link: 'order-detail.html?id=ORD-2026-000091' }
  ];

  // ----- State labels (v1: no pending_payment, no in_delivery) -----
  const STATE_LABELS = {
    new: 'Yangi', confirmed: 'Tasdiqlangan',
    cutting: 'Kesilmoqda', edge_banding: 'Krom yopishtirilmoqda', ready: 'Tayyor',
    completed: 'Tugallandi', cancelled: 'Bekor qilindi'
  };
  const STATE_PILL = {
    new: 'p-new', confirmed: 'p-conf',
    cutting: 'p-cut', edge_banding: 'p-eb', ready: 'p-rdy',
    completed: 'p-dn', cancelled: 'p-bad'
  };
  // Linear state machine (cancelled reachable from any pre-completed state).
  const ORDER_STATES = ['new', 'confirmed', 'cutting', 'edge_banding', 'ready', 'completed', 'cancelled'];

  // Client-facing 5 phases (cutting + edge_banding collapse to "Ishlab chiqarishda").
  // Single source — client app never hardcodes these.
  const CLIENT_PHASES = {
    new: 'Joylashtirildi', confirmed: 'Tasdiqlandi',
    cutting: 'Ishlab chiqarishda', edge_banding: 'Ishlab chiqarishda',
    ready: 'Tayyor', completed: 'Topshirildi', cancelled: 'Bekor qilindi'
  };

  // One demo "today" anchor (project date 2026-05-19). Every screen reads this
  // instead of inventing its own "bugun".
  const TODAY = '19-may';

  // Order status-change log (the audit "Status changes" half — support.md).
  // Generated to agree with the order seed; current = the order's live state.
  const statusEvents = orders.flatMap(o => {
    const ev = [];
    const wsId = o.workshopId || 'ws-01';
    const cut = cuttings.find(c => c.id === o.cuttingId);
    const banded = !!(cut && cut.edgeLen && Object.keys(cut.edgeLen).length > 0);
    const push = (from, to, t, actor, actorType, reason) =>
      ev.push({ orderId: o.id, workshopId: wsId, from, to, t, actor, actorType, reason: reason || null });
    push(null, 'new', o.placedAt, o.placedBy || o.clientId, 'client');
    if (o.confirmedAt) push('new', 'confirmed', o.confirmedAt, o.confirmedBy || 'u02', 'workshop_user');
    if (o.cutCompletedAt) push('cutting', banded ? 'edge_banding' : 'ready', o.cutCompletedAt, o.cutter, 'workshop_user');
    if (o.edgeCompletedAt) push('edge_banding', 'ready', o.edgeCompletedAt, o.edger, 'workshop_user');
    if (o.pickedUpAt) push('ready', 'completed', o.pickedUpAt, o.confirmedBy || 'u02', 'workshop_user');
    if (o.cancelledAt) push('new', 'cancelled', o.cancelledAt, o.cancelledBy, 'workshop_user', o.cancelReason);
    return ev;
  });

  const lookup = {
    branchById: id => branches.find(b => b.id === id),
    matById: id => materials.find(m => m.id === id),
    userById: id => users.find(u => u.id === id),
    clientById: id => clients.find(c => c.id === id),
    orderById: id => orders.find(o => o.id === id),
    cuttingById: id => cuttings.find(c => c.id === id),
    branchMatFor: (branchId, matId) => branchMaterials.find(bm => bm.branchId === branchId && bm.matId === matId),
    workshopById: id => workshops.find(w => w.id === id),
    supplierById: id => suppliers.find(s => s.id === id),
    incomesForOrder: orderId => incomes.filter(i => i.orderId === orderId && i.status === 'recorded'),
    chosenAlgo: cutting => cutting.algorithms?.find(a => a.chosen) || cutting.algorithms?.[0] || null,

    // does this cutting need an edge_banding step at all?
    isBanded: cutting => {
      const algo = lookup.chosenAlgo(cutting);
      const fromAlgo = algo && algo.edgeLen && Object.keys(algo.edgeLen).length > 0;
      const fromParts = (cutting.partList || []).some(p => p.edges && Object.values(p.edges).some(v => v != null));
      return !!(fromAlgo || fromParts);
    },

    // sum of recorded order payments → paid / balance for an order
    orderFinance: order => {
      const paid = incomes
        .filter(i => i.orderId === order.id && i.status === 'recorded')
        .reduce((a, i) => a + i.amountTiyin, 0);
      return { total: order.totalTiyin, paid, balance: Math.max(0, order.totalTiyin - paid) };
    },

    // materials this branch currently carries (active per-branch material rows)
    materialsAtBranch: branchId =>
      branchMaterials.filter(bm => bm.branchId === branchId && bm.status === 'active').map(bm => bm.matId),

    // true when every shop-source material the parts list needs is carried by the branch
    canBranchFulfil: (branchId, partList) => {
      const carried = new Set(
        branchMaterials.filter(bm => bm.branchId === branchId && bm.status === 'active').map(bm => bm.matId)
      );
      const needed = new Set(partList.filter(p => p.source === 'shop').map(p => p.matId));
      for (const m of needed) if (!carried.has(m)) return false;
      return true;
    },

    // active branches that can fulfil this parts list
    fulfillingBranches: partList =>
      branches.filter(b => b.status === 'active' && lookup.canBranchFulfil(b.id, partList)),

    // names of shop-source materials in the parts list NOT carried by `branchId`
    missingMaterialsAt: (branchId, partList) => {
      const carried = new Set(
        branchMaterials.filter(bm => bm.branchId === branchId && bm.status === 'active').map(bm => bm.matId)
      );
      const missing = new Set();
      for (const p of partList) if (p.source === 'shop' && !carried.has(p.matId)) missing.add(p.matId);
      return [...missing];
    },

    // price breakdown at the branch: cuttingFee, materials, edgeFee, subtotal.
    // No advance %, no delivery fee in v1.
    pricingAt: (branchId, cutting) => {
      const pricing = branchPricing[branchId];
      const algo = lookup.chosenAlgo(cutting);
      if (!pricing || !algo) return null;
      const totalSheets = Object.values(algo.sheetsByMat).reduce((a, b) => a + b, 0);
      const cuttingFee = pricing.perSheetTiyin * totalSheets;

      // materials: per matId in the algorithm result, the shop-source share of its sheets × per-sheet price at this branch
      let materials = 0;
      const matLines = [];
      for (const matId of Object.keys(algo.sheetsByMat)) {
        const matParts = cutting.partList.filter(p => p.matId === matId);
        const shopQty = matParts.filter(p => p.source === 'shop').reduce((a, p) => a + p.qty, 0);
        const totalQty = matParts.reduce((a, p) => a + p.qty, 0);
        const shopRatio = totalQty > 0 ? shopQty / totalQty : 0;
        const bm = branchMaterials.find(m => m.branchId === branchId && m.matId === matId);
        if (!bm) continue;
        const sheets = algo.sheetsByMat[matId];
        const shopSheets = Math.ceil(sheets * shopRatio); // round up; demo only
        const cost = shopSheets * bm.priceTiyin;
        materials += cost;
        if (shopSheets > 0) matLines.push({ matId, sheets: shopSheets, unit: bm.priceTiyin, total: cost });
      }

      // edge banding: Σ (metres × rate per thickness)
      let edgeFee = 0;
      const edgeLines = [];
      for (const thick of Object.keys(algo.edgeLen)) {
        const len_m = algo.edgeLen[thick];
        const rate = pricing.edgeRateTiyin[thick] || 0;
        const cost = Math.round(len_m * rate);
        edgeFee += cost;
        edgeLines.push({ thick, len_m, rate, total: cost });
      }

      return {
        cuttingFee, materials, edgeFee,
        subtotal: cuttingFee + materials + edgeFee,
        totalSheets,
        matLines, edgeLines
      };
    }
  };

  return {
    branches, materials, branchMaterials, branchPricing, suppliers,
    users, clients, cuttings, orders,
    incomes, expenses, workerProduction, permissions,
    workshops, platformUsers, jobs, errors,
    auditLog, statusEvents, notifications,
    STATE_LABELS, STATE_PILL, ORDER_STATES, CLIENT_PHASES, TODAY,
    lookup
  };
})();
