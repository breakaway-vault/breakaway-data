'use strict';
(async () => {
  const {$, $$, esc, fmt, usd, norm} = BA;
  let db;
  try { db = await BA.load(); } catch (e) { $('#count').textContent = e.message; return; }
  BA.footer();
  const M = db.moments;
  $('#stats').textContent = `${fmt(M.length)} moments · ${fmt(new Set(M.map(m => m.player)).size)} players · ${fmt(db.tables.team.filter(Boolean).length)} teams · ${fmt(db.tables.set.filter(Boolean).length)} sets.`;
  const teamSel = $('#f_team'), setSel = $('#f_set'), rarSel = $('#f_rarity');
  for (const t of [...db.tables.team].filter(Boolean).sort()) teamSel.append(new Option(t, t));
  for (const s of [...db.tables.set].filter(Boolean).sort()) setSel.append(new Option(s, s));
  for (const r of BA.RARITY_ORDER.filter(r => db.tables.rarity.includes(r))) rarSel.append(new Option(r, r));
  let list = [], shown = 0;
  function render() {
    const q = norm($('#q').value.trim()).split(/\s+/).filter(Boolean);
    const team = teamSel.value, set = setSel.value, rar = rarSel.value, sort = $('#sort').value;
    list = M.filter(m => {
      if (team && m.team !== team) return false;
      if (set && m.set !== set) return false;
      if (rar && m.rarity !== rar) return false;
      return !q.length || q.every(t => m.text.includes(t));
    });
    const cmp = {
      'date-desc': (a, b) => (b.date || '').localeCompare(a.date || '') || b.id - a.id,
      'date-asc': (a, b) => (a.date || '').localeCompare(b.date || '') || a.id - b.id,
      rare: (a, b) => (a.editions ?? 1e9) - (b.editions ?? 1e9) || a.id - b.id,
      'value-desc': (a, b) => (b.value ?? -1) - (a.value ?? -1) || a.id - b.id,
      'value-asc': (a, b) => (a.value ?? 1e12) - (b.value ?? 1e12) || a.id - b.id,
      player: (a, b) => a.player.localeCompare(b.player) || a.id - b.id,
      id: (a, b) => a.id - b.id,
    }[sort];
    list.sort(cmp);
    $('#count').textContent = list.length === M.length ? `Showing all ${fmt(M.length)} moments` : `${fmt(list.length)} of ${fmt(M.length)} moments`;
    shown = 0; $('#grid').innerHTML = ''; more();
  }
  function more() {
    const part = list.slice(shown, shown + 60); shown += part.length;
    $('#grid').insertAdjacentHTML('beforeend', part.map(m => BA.tile(m)).join(''));
    BA.watch($('#grid'));
  }
  new IntersectionObserver(es => { if (es[0].isIntersecting && shown < list.length) more(); }, {rootMargin: '800px'}).observe($('#sentinel'));
  let t; $('#q').addEventListener('input', () => { clearTimeout(t); t = setTimeout(render, 120); });
  ['#sort', '#f_team', '#f_set', '#f_rarity'].forEach(s => $(s).addEventListener('change', () => { syncUrl(); render(); }));
  $('#reset').addEventListener('click', () => { $('#q').value = ''; teamSel.value = ''; setSel.value = ''; rarSel.value = ''; $('#sort').value = 'date-desc'; syncUrl(); render(); });
  $('#toggleFilters')?.addEventListener('click', () => $('#filters').classList.toggle('open'));
  $('#grid').addEventListener('click', e => { const c = e.target.closest('.tile'); if (c) BA.open(db.byId.get(c.dataset.id)); });
  function syncUrl() {
    const p = new URLSearchParams();
    if (teamSel.value) p.set('team', teamSel.value);
    if (setSel.value) p.set('set', setSel.value);
    if (rarSel.value) p.set('rarity', rarSel.value);
    if ($('#sort').value !== 'date-desc') p.set('sort', $('#sort').value);
    const qs = p.toString(); history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + (location.hash.startsWith('#m=') ? location.hash : ''));
  }
  function fromUrl() {
    const p = new URLSearchParams(location.search);
    if (p.get('team')) teamSel.value = p.get('team');
    if (p.get('set')) setSel.value = p.get('set');
    if (p.get('rarity')) rarSel.value = p.get('rarity');
    if (p.get('sort')) $('#sort').value = p.get('sort');
  }
  fromUrl(); render();
  const hm = location.hash.match(/^#m=(\d+)/);
  if (hm && db.byId.has(hm[1])) BA.open(db.byId.get(hm[1]));
  window.addEventListener('hashchange', () => { const m = location.hash.match(/^#m=(\d+)/); if (m && db.byId.has(m[1])) BA.open(db.byId.get(m[1])); else if (!location.hash.startsWith('#m=')) BA.close(); });
})();
