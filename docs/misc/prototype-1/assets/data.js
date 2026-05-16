/* ===========================================================================
   Mebel Pro — seed data shared by all prototype apps
   Static — no backend, no persistence. Demo numbers only.
   =========================================================================== */

window.SEED = (() => {
  // ----- Branches -----
  const branches = [
    { id: 'yunusobod', city: 'Toshkent', name: 'Yunusobod', addr: "Buyuk Ipak Yo'li 142", phone: '+998 71 200 30 41', status: 'active', hours: 'Du–Sh · 09:00–19:00' },
    { id: 'chilonzor', city: 'Toshkent', name: 'Chilonzor', addr: 'Chilonzor 9-mavze 32', phone: '+998 71 200 30 42', status: 'active', hours: 'Du–Sh · 09:00–19:00' },
    { id: 'yangiyol', city: 'Toshkent vil.', name: "Yangiyo'l", addr: 'Mustaqillik 5', phone: '+998 71 200 30 43', status: 'temporarily_closed', closedReason: 'Texnik ta\'mirlash · 22-maygacha', hours: 'yopiq' }
  ];

  // ----- Platform-wide material catalog -----
  const materials = [
    { id: 'm01', type: 'dsp', name: 'LDSP H1334 ST9 · Dub Sonoma', thickness: 18, color: 'Dub Sonoma', decor: 'H1334', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-1' },
    { id: 'm02', type: 'dsp', name: 'LDSP K001 PW · Belarus dub', thickness: 16, color: 'Dub Belarus', decor: 'K001', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-2' },
    { id: 'm03', type: 'dsp', name: "LDSP 8198 · Ladzio yong'oq", thickness: 18, color: "Yong'oq", decor: '8198', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-3' },
    { id: 'm04', type: 'dsp', name: 'LDSP 0011 PR · Oq baxmal', thickness: 18, color: 'Oq', decor: '0011', sheetLen: 2750, sheetWid: 1830, grain: false, status: 'active', sw: 'sw-4' },
    { id: 'm05', type: 'mdf', name: 'MDF 16 mm · qum rang', thickness: 16, color: 'Qum', sheetLen: 2800, sheetWid: 2070, grain: false, status: 'active', sw: 'sw-5' },
    { id: 'm06', type: 'plywood', name: 'Fanera berioz · 8 mm', thickness: 8, color: 'Berioz', sheetLen: 2440, sheetWid: 1220, grain: false, status: 'active', sw: 'sw-6' },
    { id: 'm07', type: 'mdf', name: 'MDF 19 mm · oq glyans', thickness: 19, color: 'Oq glyans', sheetLen: 2800, sheetWid: 2070, grain: false, status: 'active', sw: 'sw-4' },
    { id: 'm08', type: 'dsp', name: 'LDSP H3309 · Mocca', thickness: 18, color: 'Mocca', decor: 'H3309', sheetLen: 2750, sheetWid: 1830, grain: true, status: 'active', sw: 'sw-9' },
    { id: 'm09', type: 'plywood', name: 'Fanera oq qayin · 12 mm', thickness: 12, color: 'Oq qayin', sheetLen: 2440, sheetWid: 1220, grain: false, status: 'active', sw: 'sw-10' },
    { id: 'm10', type: 'mdf', name: 'MDF 8 mm · texnik', thickness: 8, color: 'Texnik', sheetLen: 2800, sheetWid: 2070, grain: false, status: 'inactive', sw: 'sw-5' }
  ];

  // Per-branch selection: branchId+materialId → { priceTiyin (price per sheet), minStock, onHand, reserved, status }
  const branchMaterials = [
    { branchId: 'yunusobod', matId: 'm01', priceTiyin: 41000000, minStock: 20, onHand: 142, reserved: 8, status: 'active' },
    { branchId: 'yunusobod', matId: 'm02', priceTiyin: 38000000, minStock: 20, onHand: 96, reserved: 4, status: 'active' },
    { branchId: 'yunusobod', matId: 'm03', priceTiyin: 42500000, minStock: 15, onHand: 61, reserved: 6, status: 'active' },
    { branchId: 'yunusobod', matId: 'm04', priceTiyin: 32000000, minStock: 30, onHand: 12, reserved: 0, status: 'active' }, // low
    { branchId: 'yunusobod', matId: 'm05', priceTiyin: 29500000, minStock: 25, onHand: 84, reserved: 7, status: 'active' },
    { branchId: 'yunusobod', matId: 'm06', priceTiyin: 24000000, minStock: 10, onHand: 42, reserved: 0, status: 'active' },
    { branchId: 'yunusobod', matId: 'm08', priceTiyin: 44500000, minStock: 15, onHand: 38, reserved: 0, status: 'active' },
    { branchId: 'chilonzor', matId: 'm01', priceTiyin: 41500000, minStock: 20, onHand: 110, reserved: 4, status: 'active' },
    { branchId: 'chilonzor', matId: 'm02', priceTiyin: 38500000, minStock: 20, onHand: 4, reserved: 0, status: 'active' }, // low
    { branchId: 'chilonzor', matId: 'm05', priceTiyin: 30000000, minStock: 20, onHand: 56, reserved: 3, status: 'active' },
    { branchId: 'chilonzor', matId: 'm06', priceTiyin: 24500000, minStock: 12, onHand: 28, reserved: 0, status: 'active' },
    { branchId: 'yangiyol', matId: 'm01', priceTiyin: 40500000, minStock: 15, onHand: 35, reserved: 0, status: 'active' },
    { branchId: 'yangiyol', matId: 'm04', priceTiyin: 31500000, minStock: 20, onHand: 8, reserved: 0, status: 'active' }, // low
  ];

  // ----- Workshop users (the owner + staff) -----
  const users = [
    { id: 'u01', name: 'Hasan Karimov', login: 'hasan', phone: '+998 90 100 30 30', isOwner: true, homeBranchId: 'yunusobod', status: 'active', comp: { type: 'salary', rate: '12 000 000 / oy' }, lastLogin: '15-may, 09:14', initials: 'HK' },
    { id: 'u02', name: 'Aziza Rasulova', login: 'aziza', phone: '+998 90 100 30 31', isOwner: false, homeBranchId: 'yunusobod', status: 'active', comp: { type: 'salary + commission', rate: '5 000 000 / oy + 1.5%' }, lastLogin: '15-may, 09:42', initials: 'AR', grants: { manage_orders: ['yunusobod', 'chilonzor'], view_dashboard: ['yunusobod', 'chilonzor'], manage_inventory: ['yunusobod'] } },
    { id: 'u03', name: 'Bahodir Tursunov', login: 'bahodir', phone: '+998 90 100 30 32', isOwner: false, homeBranchId: 'yunusobod', status: 'active', comp: { type: 'per_sheet', rate: '50 000 / list' }, lastLogin: '15-may, 08:30', initials: 'BT', grants: { process_production: ['yunusobod'] } },
    { id: 'u04', name: 'Olim Hojiyev', login: 'olim', phone: '+998 90 100 30 33', isOwner: false, homeBranchId: 'yunusobod', status: 'active', comp: { type: 'per_metre_banding', rate: '1 500 / metr' }, lastLogin: '14-may, 17:50', initials: 'OH', grants: { process_production: ['yunusobod'] } },
    { id: 'u05', name: 'Sherzod Aliyev', login: 'sherzod', phone: '+998 90 100 30 34', isOwner: false, homeBranchId: 'yunusobod', status: 'active', comp: { type: 'per_delivery', rate: '30 000 / yetkazma' }, lastLogin: '15-may, 06:15', initials: 'SA', grants: { process_delivery: ['yunusobod', 'chilonzor'] } },
    { id: 'u06', name: 'Dilshod Yo\'ldoshev', login: 'dilshod', phone: '+998 90 100 30 35', isOwner: false, homeBranchId: 'chilonzor', status: 'active', comp: { type: 'salary', rate: '4 200 000 / oy' }, lastLogin: '14-may, 18:00', initials: 'DY', grants: { manage_orders: ['chilonzor'], view_dashboard: ['chilonzor'] } },
    { id: 'u07', name: 'Komron Saidov', login: 'komron', phone: '+998 90 100 30 36', isOwner: false, homeBranchId: 'chilonzor', status: 'active', comp: { type: 'per_sheet', rate: '48 000 / list' }, lastLogin: '14-may, 16:42', initials: 'KS', grants: { process_production: ['chilonzor'] } },
    { id: 'u08', name: 'Madina Yusupova', login: 'madina', phone: '+998 90 100 30 37', isOwner: false, homeBranchId: 'yangiyol', status: 'blocked', comp: null, lastLogin: '02-may, 15:00', initials: 'MY', grants: {} }
  ];

  // ----- Clients (platform-wide) -----
  const clients = [
    { id: 'c01', name: "Akmal Norqo'ziyev", phone: '+998 90 100 30 60', initials: 'AN', status: 'active', ordersCount: 4 },
    { id: 'c02', name: 'Dilshod Tursunov', phone: '+998 90 100 30 61', initials: 'DT', status: 'active', ordersCount: 2 },
    { id: 'c03', name: "Madina Yo'ldosheva", phone: '+998 90 100 30 62', initials: 'MY', status: 'active', ordersCount: 1 },
    { id: 'c04', name: 'Sherzod Ahmedov', phone: '+998 90 100 30 63', initials: 'SA', status: 'active', ordersCount: 3 },
  ];

  // ----- Cutting drafts and results -----
  // Each cutting has a parts list (per-part material + source), and one or more
  // algorithm results (one is `chosen`). The chosen algorithm's numbers are
  // mirrored onto the cutting itself as flat fields for legacy callers.
  const cuttings = [
    {
      id: 'cr-0091', status: 'confirmed', orderId: 'MP-2026-05-0091',
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
      branchId: null, when: '15-may, 08:12',
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
    // A simpler single-material draft
    {
      id: 'cr-0086', status: 'draft', orderId: null, branchId: null, when: '14-may, 19:42',
      partList: [
        { ref: 'p01', matId: 'm05', source: 'shop', l: 1200, w: 600, qty: 1, edges: { t: null, b: null, l: null, r: null } },
        { ref: 'p02', matId: 'm05', source: 'shop', l:  800, w: 400, qty: 4, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 14.6, cutLen: 18.2, edgeLen: { 0.4: 4.8 }, sheetsByMat: { m05: 1 } }
      ],
      parts: 5, sheets: 1, wastePct: 14.6, cutLen: 18.2, edgeLen: { 0.4: 4.8 }, algoVer: 'ffd-guillotine-v1',
      matId: 'm05', source: 'shop'
    },
    {
      id: 'cr-0072', status: 'confirmed', orderId: 'MP-2026-05-0072',
      branchId: 'yunusobod', when: '13-may, 14:32',
      partList: [
        { ref: 'p01', matId: 'm05', source: 'shop', l: 1400, w: 600, qty: 2, edges: { t: 0.4, b: 0.4, l: 0.4, r: 0.4 } }
      ],
      algorithms: [
        { name: 'ffd-guillotine', ver: '1.0', chosen: true, wastePct: 6.1, cutLen: 88.4, edgeLen: { 0.4: 12.0 }, sheetsByMat: { m05: 7 } }
      ],
      parts: 8, sheets: 7, wastePct: 6.1, cutLen: 88.4, edgeLen: { 0.4: 12.0 }, algoVer: 'ffd-guillotine-v1',
      matId: 'm05', source: 'shop'
    }
  ];

  // ----- Per-branch pricing knobs the order step reads -----
  // perSheetTiyin = cutting-service rate (per sheet, integer tiyin)
  // edgeRateTiyin = edge-banding rate (per metre, by thickness in mm)
  // advancePercent = advance %% for the "advance + balance" plan
  // deliveryFeeTiyin = fixed per-zone fee (single zone in the demo)
  const branchPricing = {
    yunusobod: { perSheetTiyin: 10000000, edgeRateTiyin: { 0.4: 200000, 2.0: 450000 }, advancePercent: 50, deliveryFeeTiyin: 3500000 },
    chilonzor: { perSheetTiyin:  9500000, edgeRateTiyin: { 0.4: 200000, 2.0: 420000 }, advancePercent: 50, deliveryFeeTiyin: 4000000 },
    yangiyol:  { perSheetTiyin:  9000000, edgeRateTiyin: { 0.4: 180000, 2.0: 400000 }, advancePercent: 50, deliveryFeeTiyin: 5500000 }
  };

  // ----- Orders -----
  const orders = [
    {
      id: 'MP-2026-05-0091', state: 'cutting', branchId: 'yunusobod', clientId: 'c01',
      title: "Kuhna mebel — 4 shkaf · stol", cuttingId: 'cr-0091', source: 'shop', deliveryType: 'delivery',
      address: "Yunusobod, Buyuk Ipak Yo'li 142", deliveryFeeTiyin: 3500000,
      cuttingFeeTiyin: 60000000, materialsTiyin: 246000000, edgeFeeTiyin: 8200000, discountTiyin: 0,
      totalTiyin: 317700000, paidTiyin: 158850000, paymentType: 'advance',
      assignedCutter: 'u03', cutter: 'u03', cutStartedAt: '14-may, 11:20',
      placedAt: '14-may, 09:42', placedBy: 'c01',
      dueAt: '16-may, 14:00', priority: 5
    },
    {
      id: 'MP-2026-05-0090', state: 'edge_banding', branchId: 'yunusobod', clientId: 'c02',
      title: 'MDF · 6 list · krom', cuttingId: 'cr-mock', source: 'shop', deliveryType: 'pickup',
      cuttingFeeTiyin: 30000000, materialsTiyin: 158000000, edgeFeeTiyin: 5400000, discountTiyin: 0,
      totalTiyin: 193400000, paidTiyin: 193400000, paymentType: 'full',
      cutter: 'u03', edger: 'u04', cutCompletedAt: '15-may, 09:18', edgeStartedAt: '15-may, 09:20',
      placedAt: '13-may, 18:30', dueAt: '15-may, 17:00', priority: 4
    },
    {
      id: 'MP-2026-05-0089', state: 'ready', branchId: 'yunusobod', clientId: 'c03',
      title: 'Oshxona · LDSP · 2 list', cuttingId: 'cr-mock', source: 'shop', deliveryType: 'delivery',
      address: "Yunusobod, Tinchlik 12", deliveryFeeTiyin: 3500000,
      cuttingFeeTiyin: 12000000, materialsTiyin: 81000000, edgeFeeTiyin: 2200000, discountTiyin: 0,
      totalTiyin: 98700000, paidTiyin: 49350000, paymentType: 'advance', balanceUnpaid: true,
      cutter: 'u03', edger: 'u04', placedAt: '13-may, 11:15', dueAt: '15-may, 16:00', priority: 3
    },
    {
      id: 'MP-2026-05-0088', state: 'in_delivery', branchId: 'yunusobod', clientId: 'c04',
      title: 'Stol · fanera', cuttingId: 'cr-mock', source: 'shop', deliveryType: 'delivery',
      address: "Chilonzor 9-mavze 17", deliveryFeeTiyin: 3500000,
      cuttingFeeTiyin: 18000000, materialsTiyin: 144000000, edgeFeeTiyin: 0, discountTiyin: 0,
      totalTiyin: 165500000, paidTiyin: 165500000, paymentType: 'full',
      cutter: 'u03', driver: 'u05', driverStartedAt: '15-may, 09:30',
      placedAt: '12-may, 14:20', dueAt: 'bugun · 14:30', priority: 2
    },
    {
      id: 'MP-2026-05-0087', state: 'confirmed', branchId: 'yunusobod', clientId: 'c01',
      title: 'Krom + aksessuar', cuttingId: 'cr-mock', source: 'shop', deliveryType: 'pickup',
      cuttingFeeTiyin: 9000000, materialsTiyin: 42000000, edgeFeeTiyin: 0, discountTiyin: 0,
      totalTiyin: 51000000, paidTiyin: 51000000, paymentType: 'full',
      placedAt: '15-may, 08:10', dueAt: '17-may', priority: 6
    },
    {
      id: 'MP-2026-05-0086', state: 'pending_payment', branchId: 'yunusobod', clientId: 'c02',
      title: 'Stol oyog\'i · 1 list', cuttingId: 'cr-mock', source: 'shop', deliveryType: 'pickup',
      cuttingFeeTiyin: 6000000, materialsTiyin: 29500000, edgeFeeTiyin: 0, discountTiyin: 0,
      totalTiyin: 35500000, paidTiyin: 0, paymentType: 'full',
      placedAt: '15-may, 09:00', dueAt: '16-may', priority: 1
    },
    {
      id: 'MP-2026-05-0085', state: 'new', branchId: 'chilonzor', clientId: 'c03',
      title: 'Garderob · 8 list', cuttingId: 'cr-mock', source: 'shop', deliveryType: 'delivery',
      address: "Chilonzor 9-mavze 32", deliveryFeeTiyin: 3500000,
      cuttingFeeTiyin: 48000000, materialsTiyin: 320000000, edgeFeeTiyin: 11200000, discountTiyin: 0,
      totalTiyin: 382700000, paidTiyin: 0, paymentType: 'full',
      placedAt: '15-may, 09:30', dueAt: '18-may', priority: 7
    },
    {
      id: 'MP-2026-05-0072', state: 'completed', branchId: 'yunusobod', clientId: 'c01',
      title: 'MDF · 7 list · krom · oldingi buyurtma',
      cuttingId: 'cr-0072', source: 'shop', deliveryType: 'delivery',
      address: "Yunusobod, Toraqo'rg'on 7", deliveryFeeTiyin: 3500000,
      cuttingFeeTiyin: 42000000, materialsTiyin: 206500000, edgeFeeTiyin: 4500000, discountTiyin: 0,
      totalTiyin: 256500000, paidTiyin: 256500000, paymentType: 'advance',
      cutter: 'u03', edger: 'u04', driver: 'u05',
      placedAt: '10-may, 14:30', deliveredAt: '13-may, 14:30', priority: 0
    },
    {
      id: 'MP-2026-04-0856', state: 'cancelled', branchId: 'chilonzor', clientId: 'c01',
      title: "Fanera · oshxona", cuttingId: 'cr-mock', source: 'shop', deliveryType: 'delivery',
      address: 'Chilonzor 8-mavze 14', deliveryFeeTiyin: 3500000,
      cuttingFeeTiyin: 14000000, materialsTiyin: 48000000, edgeFeeTiyin: 0, discountTiyin: 0,
      totalTiyin: 65500000, paidTiyin: 32750000, paymentType: 'advance',
      placedAt: '08-apr, 11:00', cancelledAt: '09-apr, 14:00', cancelReason: 'Mijoz boshqa filialni tanladi',
      refundPending: true, priority: 0
    }
  ];

  // ----- Expenses -----
  const expenses = [
    { id: 'e01', branchId: 'yunusobod', category: 'rent', amountTiyin: 480000000, incurredOn: '01-may', description: 'May oyi ijarasi', vendor: 'Tinchlik Bldg LLC', status: 'recorded' },
    { id: 'e02', branchId: 'yunusobod', category: 'utilities', amountTiyin: 24000000, incurredOn: '05-may', description: 'Elektr energiya · aprel', vendor: 'Hududgaz', status: 'recorded' },
    { id: 'e03', branchId: null, category: 'marketing', amountTiyin: 80000000, incurredOn: '08-may', description: 'Reklama · Telegram kanal', vendor: 'Mediastar', status: 'recorded' },
    { id: 'e04', branchId: 'chilonzor', category: 'supplies', amountTiyin: 35000000, incurredOn: '12-may', description: 'Aksessuar va vint partiyasi', vendor: 'Hardware.uz', status: 'recorded' },
    { id: 'e05', branchId: 'yunusobod', category: 'transport', amountTiyin: 12500000, incurredOn: '13-may', description: 'Yangiyo\'lga material transport', vendor: 'JTKlogistika', status: 'recorded' },
    { id: 'e06', branchId: 'yunusobod', category: 'equipment', amountTiyin: 145000000, incurredOn: '03-may', description: 'Kromchi mashinasiga ehtiyot qism', vendor: 'IMA AG', status: 'voided', voidReason: 'Notog\'ri summa kiritilgan' }
  ];

  // ----- Payroll runs -----
  const payrollRuns = [
    { id: 'pr-2026-05', period: '01-may — 31-may', status: 'draft', generatedBy: 'u01', generatedAt: '15-may', grossTiyin: 624000000, paidTiyin: 0, entries: 17 },
    { id: 'pr-2026-04', period: '01-apr — 30-apr', status: 'finalized', generatedBy: 'u01', generatedAt: '01-may', finalizedBy: 'u01', finalizedAt: '02-may', grossTiyin: 612400000, paidTiyin: 612400000, entries: 16 },
    { id: 'pr-2026-03', period: '01-mar — 31-mar', status: 'finalized', generatedBy: 'u01', generatedAt: '01-apr', finalizedBy: 'u01', finalizedAt: '02-apr', grossTiyin: 588000000, paidTiyin: 588000000, entries: 15 }
  ];

  // ----- Permissions catalog -----
  const permissions = [
    { key: 'view_dashboard', label: 'Asosiyni ko\'rish' },
    { key: 'manage_orders', label: 'Buyurtmalarni boshqarish' },
    { key: 'process_production', label: 'Kesish / krom yopishtirish' },
    { key: 'process_delivery', label: 'Yetkazib berish' },
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
    { id: 'p01', name: 'Nuriddin Obidjonov', login: 'nuriddin', phone: '+998 90 200 00 00', status: 'active', lastLogin: '15-may, 09:00', initials: 'NO' },
    { id: 'p02', name: 'Aziza Saidova', login: 'aziza', phone: '+998 90 200 00 01', status: 'active', lastLogin: '14-may, 18:30', initials: 'AS' },
    { id: 'p03', name: 'Sardor Tursunov', login: 'sardor', phone: '+998 90 200 00 02', status: 'active', lastLogin: '12-may, 14:20', initials: 'ST' }
  ];

  // ----- Scheduled jobs -----
  const jobs = [
    { id: 'expire-stale-draft-cuttings', name: 'expire-stale-draft-cuttings', schedule: 'Kunlik · 03:00', lastRun: '15-may, 03:00', lastResult: 'ok', summary: '4 ta eskirgan draft o\'chirildi' },
    { id: 'notify-pay-later-overdue', name: 'notify-pay-later-overdue', schedule: 'Kunlik · 09:00', lastRun: '15-may, 09:00', lastResult: 'ok', summary: '0 ta muddati o\'tgan pay-later' },
    { id: 'notify-stale-refunds', name: 'notify-stale-refunds', schedule: 'Kunlik · 09:15', lastRun: '15-may, 09:15', lastResult: 'ok', summary: '1 ta stale refund (8 kun)' },
    { id: 'cleanup-expired-sessions', name: 'cleanup-expired-sessions', schedule: 'Soatlik', lastRun: '15-may, 09:00', lastResult: 'ok', summary: '142 ta sessiya o\'chirildi' },
    { id: 'daily-low-stock-summary', name: 'daily-low-stock-summary', schedule: 'Kunlik · 08:00', lastRun: '15-may, 08:00', lastResult: 'failed', summary: 'TimeoutError on workshop ws-04', error: 'Connection timeout to inventory DB at 08:00:42' }
  ];

  // ----- Error monitor -----
  const errors = [
    { code: 'insufficient_stock', module: 'inventory', count24h: 12, count7d: 38, last: '15-may, 09:14', msg: 'Reserve failed: available < requested', resolved: false },
    { code: 'optimization_timeout', module: 'cutting', count24h: 3, count7d: 7, last: '14-may, 16:42', msg: 'Cutting optimization exceeded 5s budget (84 parts)', resolved: false },
    { code: 'delivery_out_of_zone', module: 'orders', count24h: 5, count7d: 14, last: '15-may, 08:20', msg: 'No delivery zone matched (lat, lng)', resolved: false },
    { code: 'invalid_oauth_signature', module: 'identity', count24h: 1, count7d: 4, last: '15-may, 06:12', msg: 'Telegram payload HMAC mismatch', resolved: false }
  ];

  // ----- Audit log -----
  const auditLog = [
    { t: '15-may, 09:42', action: 'order.status_changed', actor: 'u02', detail: 'MP-2026-05-0090 · edge_banding → cutting', module: 'orders' },
    { t: '15-may, 09:30', action: 'order.created', actor: 'c03', detail: 'MP-2026-05-0085 · 8 list, garderob', module: 'orders' },
    { t: '15-may, 09:18', action: 'order.cut_completed', actor: 'u03', detail: 'MP-2026-05-0090 · 6 list ishlatildi', module: 'orders' },
    { t: '15-may, 09:14', action: 'inventory.stock_in', actor: 'u02', detail: 'm03 · +40 list · Egger partiya', module: 'inventory' },
    { t: '15-may, 08:20', action: 'order.delivery_out_of_zone', actor: 'c02', detail: '(41.32, 69.28) — no zone', module: 'orders' },
    { t: '14-may, 17:50', action: 'order.banding_completed', actor: 'u04', detail: 'MP-2026-05-0089 · 16.4 m', module: 'orders' },
    { t: '14-may, 11:20', action: 'order.cut_started', actor: 'u03', detail: 'MP-2026-05-0091 · 14 part', module: 'orders' },
    { t: '14-may, 09:42', action: 'order.created', actor: 'c01', detail: 'MP-2026-05-0091', module: 'orders' }
  ];

  // ----- Notifications -----
  const notifications = [
    { t: '15-may, 09:42', kind: 'order', read: false, title: "Yangi buyurtma · MP-2026-05-0085", body: "Chilonzor · 8 list, garderob — 3.8 M so'm", link: 'order-detail.html?id=MP-2026-05-0085' },
    { t: '15-may, 09:14', kind: 'inventory', read: false, title: "Past zaxira · 4 ta material", body: "Yunusobod, Chilonzor — ko'rib chiqing", link: 'inventory.html' },
    { t: '15-may, 09:00', kind: 'finance', read: false, title: "Eskirgan refund · 8 kun", body: "MP-2026-04-0856 · 327 500 so'm", link: 'refunds.html' },
    { t: '14-may, 18:20', kind: 'order', read: true, title: "Buyurtma tugatildi · MP-2026-05-0072", body: "Akmal Norqo'ziyev · 2 565 000 so'm", link: 'order-detail.html?id=MP-2026-05-0072' },
    { t: '14-may, 09:42', kind: 'order', read: true, title: "Yangi buyurtma · MP-2026-05-0091", body: "Akmal Norqo'ziyev · 4 shkaf + stol", link: 'order-detail.html?id=MP-2026-05-0091' }
  ];

  // ----- State labels -----
  const STATE_LABELS = {
    new: 'Yangi', pending_payment: "To'lov kutilmoqda", confirmed: 'Tasdiqlangan',
    cutting: 'Kesilmoqda', edge_banding: 'Krom yopishtirilmoqda', ready: 'Tayyor',
    in_delivery: 'Yetkazilmoqda', completed: 'Tugallandi', cancelled: 'Bekor qilindi'
  };
  const STATE_PILL = {
    new: 'p-new', pending_payment: 'p-pay', confirmed: 'p-conf',
    cutting: 'p-cut', edge_banding: 'p-eb', ready: 'p-rdy',
    in_delivery: 'p-del', completed: 'p-dn', cancelled: 'p-bad'
  };

  const lookup = {
    branchById: id => branches.find(b => b.id === id),
    matById: id => materials.find(m => m.id === id),
    userById: id => users.find(u => u.id === id),
    clientById: id => clients.find(c => c.id === id),
    orderById: id => orders.find(o => o.id === id),
    cuttingById: id => cuttings.find(c => c.id === id),
    branchMatFor: (branchId, matId) => branchMaterials.find(bm => bm.branchId === branchId && bm.matId === matId),
    workshopById: id => workshops.find(w => w.id === id),
    chosenAlgo: cutting => cutting.algorithms?.find(a => a.chosen) || cutting.algorithms?.[0] || null,

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

    // sheets in the chosen algorithm result that aren't fully covered by shop parts (i.e. own-source share)
    // returns a price breakdown at the branch: cuttingFee, materials, edgeFee, subtotal
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
        advancePercent: pricing.advancePercent,
        deliveryFeeTiyin: pricing.deliveryFeeTiyin,
        totalSheets,
        matLines, edgeLines
      };
    }
  };

  return {
    branches, materials, branchMaterials, branchPricing, users, clients, cuttings, orders,
    expenses, payrollRuns, permissions, workshops, platformUsers, jobs, errors,
    auditLog, notifications,
    STATE_LABELS, STATE_PILL,
    lookup
  };
})();
