'use strict';
(async () => {
  const {$, esc, fmt, usd, norm} = BA;
  const REPO = 'https://github.com/breakaway-vault/breakaway-data';
  let db;
  try { db = await BA.load(); } catch (e) { showErr(e.message); return; }
  BA.footer();
  const M = db.moments;
  let cur = null, items = [];

  function showErr(msg) { const e = $('#err'); e.textContent = msg; e.hidden = !msg; }
  const say = (msg, bad) => { const e = $('#savedMsg'); e.textContent = msg || ''; e.classList.toggle('bad', !!bad); };
  async function fileText(f) {
    if (!f) return null;
    if (f.size > 20 * 1024 * 1024) { showErr('That file is too big to be a card list.'); return null; }
    return {txt: await f.text(), name: f.name};
  }
  function parseList(txt, name) {
    const r = MyCards.parse(txt, name, M);
    if (!r.moments) return {error: `No cards matched${r.unmatched.length ? ` (${fmt(r.unmatched.length)} line(s) read, none matched an archive moment)` : ''}. Check that it is your my_cards.csv export.`};
    return r;
  }
  async function readFile(f) {
    const t = await fileText(f); if (!t) return;
    useText(t.txt, t.name);
  }
  function useText(txt, name) {
    const r = parseList(txt, name);
    if (r.error) return showErr(r.error);
    showErr(''); history.replaceState(null, '', location.pathname); BA.restoreHash = '';
    show(r.mine, {source: 'file', unmatched: r.unmatched});
  }

  function show(mine, opt) {
    cur = {mine, ...opt};
    const S = BA.stats(mine, db); items = S.items;
    const src = cur.source, hall = cur.hall;
    $('#intake').hidden = true; $('#result').hidden = false;
    $('#shared').hidden = src !== 'shared'; $('#example').hidden = !(hall && hall.example);
    document.title = 'Breakaway Archive · ' + (src === 'hall' ? '@' + (hall.name || hall.h) : 'My collection');
    $('#title').textContent = src === 'hall' ? '@' + (hall.name || hall.h) : src === 'shared' ? 'A shared collection' : src === 'saved' ? cur.name : 'My collection';
    $('#lede').innerHTML = src === 'hall'
      ? `${hall.blurb ? esc(hall.blurb) + ' · ' : ''}${hall.team ? 'Favourite team: ' + esc(hall.team) + ' · ' : ''}<a href="hall.html">Collector Hall</a>${hall.example && !hall.blurb ? ' · <b>An example entry made up to show the page, not a real collection.</b>' : ''}`
      : src === 'shared' ? 'Opened from a share link. The collection lives entirely in the link; nothing is stored on a server, and nothing is saved in your browser unless you choose to.'
      : 'Read in this browser only. Nothing was uploaded. Use “Copy share link” to show it off.';
    $('#submitHall').hidden = src === 'shared' || src === 'hall';
    $('#savedPanel').hidden = src === 'hall';
    BA.$$('.top nav a').forEach(a => { const on = a.getAttribute('href') === (src === 'hall' ? 'hall.html' : 'collection.html'); on ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'); });
    $('#shareNote').textContent = '';
    renderSaved();
    $('#summary').innerHTML = [
      ['Moments', fmt(items.length), `of ${fmt(M.length)} in the archive`],
      ['Editions', fmt(S.editions), S.editions ? 'edition numbers listed' : 'no edition numbers in the list'],
      ['Est. value (FMV)', usd(S.value), `${db.raw.price_snapshot} snapshot${S.unpriced ? `, ${S.unpriced} unpriced` : ''}`],
      ['At lowest ask', usd(S.askValue), 'same snapshot'],
      ['Sets started', fmt(S.setList.length), `${fmt(S.complete)} complete`],
    ].map(([k, v, s]) => `<div class="stat"><small>${k}</small><b>${v}</b><span>${s}</span></div>`).join('')
      + `<div class="stat rar-mix"><small>By rarity · cards owned</small><div class="mix">${BA.RARITY_ORDER.filter(r => S.byRarity.has(r)).map(r => `<span class="chip ${BA.rarityClass(r)} on">${esc(r)} ${fmt(S.byRarity.get(r))}</span>`).join('')}</div></div>`;
    const um = cur.unmatched || [];
    $('#unmatched').textContent = um.length ? `${fmt(um.length)} line(s) in your file didn't match an archive moment (e.g. ${um.slice(0, 3).map(u => u.slice(0, 60)).join(' | ')}).` : '';
    $('#rarest').innerHTML = S.rare.slice(0, 8).map(x => BA.tile(x.m, extra(x))).join('');
    $('#sets').innerHTML = S.setList.map(s => bar(`${s.set} <span class="dim">${esc(s.series)}</span>`, s.have, s.total, `${s.have}/${s.total}`, s.have === s.total ? 'done' : '')).join('');
    const tl = [...S.teams.entries()].sort((a, b) => b[1] - a[1]), tmax = tl.length ? tl[0][1] : 1;
    $('#teams').innerHTML = tl.map(([t, n]) => bar(esc(t), n, tmax, fmt(n), 'team')).join('');
    $('#allcount').textContent = `(${fmt(items.length)})`;
    $('#mq').value = ''; renderAll();
    BA.watch($('#rarest'));
  }
  const bar = (label, n, total, txt, cls) => `<div class="bar ${cls}"><div class="lbl">${label}</div><div class="track"><i style="width:${Math.max(2, Math.round(100 * n / total))}%"></i></div><div class="num">${txt}</div></div>`;
  function extra(x) {
    const e = x.eds, line = e.length ? e.slice(0, 3).map(n => '#' + n).join(', ') + (e.length > 3 ? ` +${e.length - 3}` : '') : 'owned';
    return {line: esc(line), badge: e.length > 1 ? `<span class="badge">×${e.length}</span>` : ''};
  }
  let list = [], shown = 0;
  function renderAll() {
    const q = norm($('#mq').value.trim()).split(/\s+/).filter(Boolean), s = $('#msort').value;
    list = items.filter(x => q.every(t => x.m.text.includes(t)));
    const cmp = {
      rare: (a, b) => (a.m.editions ?? 1e9) - (b.m.editions ?? 1e9) || (a.eds[0] ?? 1e9) - (b.eds[0] ?? 1e9),
      value: (a, b) => (b.m.value ?? 0) * Math.max(1, b.eds.length) - (a.m.value ?? 0) * Math.max(1, a.eds.length),
      copies: (a, b) => b.eds.length - a.eds.length, date: (a, b) => (b.m.date || '').localeCompare(a.m.date || ''),
      player: (a, b) => a.m.player.localeCompare(b.m.player),
    }[s];
    list.sort(cmp); shown = 0; $('#mine').innerHTML = ''; more();
  }
  function more() { const part = list.slice(shown, shown + 60); shown += part.length; $('#mine').insertAdjacentHTML('beforeend', part.map(x => BA.tile(x.m, extra(x))).join('')); BA.watch($('#mine')); }
  new IntersectionObserver(es => { if (es[0].isIntersecting && shown < list.length) more(); }, {rootMargin: '800px'}).observe($('#sentinel'));
  let t; $('#mq').addEventListener('input', () => { clearTimeout(t); t = setTimeout(renderAll, 120); });
  $('#msort').addEventListener('change', renderAll);
  ['#rarest', '#mine'].forEach(s => $(s).addEventListener('click', e => { const c = e.target.closest('.tile'); if (c) BA.open(db.byId.get(c.dataset.id), cur.mine[c.dataset.id]); }));

  const summaryOf = x => { const n = Object.keys(x.mine).length; return `${fmt(n)} moment${n === 1 ? '' : 's'}`; };
  function renderSaved() {
    const all = Saved.list();
    $('#savedList').hidden = !all.length;
    $('#savedItems').innerHTML = all.map(x => `<button class="ghost savedopen" data-id="${esc(x.id)}"><b>${esc(x.name)}</b><small>${summaryOf(x)}</small></button>`).join('');
    if (!cur || cur.source === 'hall') return;
    const saved = cur.source === 'saved' && Saved.get(cur.savedId);
    if (cur.source === 'saved' && !saved) { cur.source = 'file'; say('This collection was deleted from this browser (maybe in another tab). Save it again to keep it.', true); }
    const isSaved = cur.source === 'saved';
    $('#saveForm').hidden = isSaved || !Saved.available; $('#savedTools').hidden = !isSaved;
    if (!Saved.available) say('This browser is not letting the site store anything (private mode or blocked site data), so collections cannot be saved here. Use Export my_cards.csv to keep a copy.', true);
    const sel = $('#savedSel'), others = all.length > (isSaved ? 1 : 0);
    $('#switchWrap').hidden = !others;
    sel.innerHTML = (isSaved ? '' : `<option value="" selected>${cur.source === 'shared' ? 'This shared collection (not saved)' : 'This list (not saved yet)'}</option>`)
      + all.map(x => `<option value="${esc(x.id)}"${isSaved && x.id === cur.savedId ? ' selected' : ''}>${esc(x.name)} · ${summaryOf(x)}</option>`).join('');
    if (isSaved) { $('#renameInput').value = saved.name; $('#dupNote').textContent = ''; }
    else {
      if (!$('#saveName').dataset.touched) $('#saveName').value = Saved.uniqueName('My collection');
      const dup = Saved.find(cur.mine);
      $('#dupNote').textContent = dup ? `The same cards are already saved as “${dup.name}”.` : '';
    }
  }
  function openSaved(id) {
    const x = Saved.get(id); if (!x) { renderSaved(); return; }
    Saved.setLast(id); history.replaceState(null, '', location.pathname); BA.restoreHash = '';
    say(''); show(x.mine, {source: 'saved', savedId: id, name: x.name});
  }
  $('#saveName').addEventListener('input', e => { e.target.dataset.touched = '1'; });
  $('#saveForm').addEventListener('submit', e => {
    e.preventDefault();
    const r = Saved.add($('#saveName').value || 'My collection', cur.mine);
    if (r.error) return say(r.error, true);
    delete $('#saveName').dataset.touched;
    openSaved(r.id); say(`Saved as “${r.name}” in this browser. It opens automatically next time you visit this page here.`);
  });
  $('#savedSel').addEventListener('change', e => { if (e.target.value) openSaved(e.target.value); });
  $('#savedItems').addEventListener('click', e => { const b = e.target.closest('.savedopen'); if (b) openSaved(b.dataset.id); });
  $('#rename').addEventListener('click', () => {
    const r = Saved.update(cur.savedId, {name: $('#renameInput').value});
    if (r.error) return say(r.error, true);
    cur.name = r.name; $('#title').textContent = r.name; renderSaved(); say(`Renamed to “${r.name}”.`);
  });
  $('#renameInput').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#rename').click(); } });
  $('#replace').addEventListener('click', () => $('#replaceFile').click());
  $('#replaceFile').addEventListener('change', async e => {
    const f = await fileText(e.target.files[0]); e.target.value = ''; if (!f) return;
    const r = parseList(f.txt, f.name); if (r.error) return say(r.error, true);
    const u = Saved.update(cur.savedId, {mine: r.mine}); if (u.error) return say(u.error, true);
    show(r.mine, {source: 'saved', savedId: cur.savedId, name: u.name, unmatched: r.unmatched});
    say(`Replaced “${u.name}” with ${f.name}: ${fmt(r.moments)} moments, ${fmt(r.editions)} edition numbers.`);
  });
  $('#del').addEventListener('click', () => {
    const x = Saved.get(cur.savedId); if (!x) return renderSaved();
    if (!confirm(`Delete “${x.name}” from this browser?\n\nThis can't be undone. Use Export my_cards.csv first if you want a copy.`)) return;
    const r = Saved.remove(x.id); if (r.error) return say(r.error, true);
    const next = Saved.list()[0];
    if (next) { openSaved(next.id); say(`Deleted “${x.name}”. Showing “${next.name}”.`); }
    else { cur = null; toIntake(); }
  });
  Saved.onChange(() => renderSaved());

  const slug = s => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
  function download(name, text) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {type: 'text/csv;charset=utf-8'}));
    a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  $('#export').addEventListener('click', () => {
    const base = cur.source === 'saved' ? slug(cur.name) : cur.source === 'hall' ? cur.hall.h : '';
    download(`my_cards${base && base !== 'my-collection' ? '-' + base : ''}.csv`, MyCards.toCsv(cur.mine, db.byId));
    $('#shareNote').textContent = 'Downloaded. Load that file here (or in the archive app) on any device to get this collection back.';
  });
  async function copy(text, okMsg) {
    try { await navigator.clipboard.writeText(text); $('#shareNote').textContent = okMsg; return true; }
    catch (e) { $('#shareNote').innerHTML = `Copy this: <input class="copybox" readonly value="${esc(text)}" onfocus="this.select()">`; return false; }
  }
  $('#share').addEventListener('click', async () => {
    const url = cur.source === 'hall' ? location.origin + location.pathname + '#h=' + cur.hall.h
      : location.origin + location.pathname + '#c=' + await MyCards.encode(cur.mine);
    copy(url, `Link copied (${fmt(url.length)} characters). Anyone with it sees this collection; it holds card numbers and edition numbers only.`);
  });
  $('#submitHall').addEventListener('click', () => {
    window.open(`${REPO}/issues/new?template=collection.yml`, '_blank', 'noopener');
    $('#shareNote').textContent = 'The Collector Hall form opened in a new tab. Type your collector name (your NHL Breakaway name is fine, spaces and capitals too), drop your my_cards.csv into the cards box, then send it.';
  });

  function toIntake() {
    history.replaceState(null, '', location.pathname); BA.restoreHash = '';
    cur = null; $('#result').hidden = true; $('#intake').hidden = false; $('#file').value = '';
    $('#title').textContent = 'Collector showcase'; document.title = 'Breakaway Archive · My collection';
    BA.$$('.top nav a').forEach(a => a.getAttribute('href') === 'collection.html' ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
    $('#lede').innerHTML = 'Drop your <code>my_cards.csv</code> to build your collection page. Your file is read in this browser only. Nothing is uploaded or sent anywhere.';
    renderSaved();
  }

  $('#file').addEventListener('change', e => readFile(e.target.files[0]));
  const drop = $('#drop');
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => readFile(e.dataTransfer.files[0]));
  drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#file').click(); } });
  $('#usePaste').addEventListener('click', () => useText($('#pasted').value, 'pasted.txt'));
  $('#clear').addEventListener('click', toIntake);

  let hallData = null;
  async function hallEntry(h) {
    if (!hallData) { const r = await fetch('data/hall.json', {cache: 'no-cache'}); if (!r.ok) throw new Error('the Collector Hall data is missing'); hallData = await r.json(); }
    // h is the slug from the link; also accept a typed name ("Rink Rat 97", "Rink%20Rat%2097") so hand-made links still work.
    const slug = s => s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[\s.]+/g, '_').replace(/[^a-z0-9_-]/g, '')
      .replace(/[_-]{2,}/g, m => m.includes('_') ? '_' : '-').replace(/^[_-]+|[_-]+$/g, '');
    return hallData.entries.find(e => e.h === h) || hallData.entries.find(e => e.h === slug(h) || (e.name || '').toLowerCase() === h.toLowerCase());
  }
  async function fromHash(first) {
    const h = location.hash;
    const c = h.match(/^#c=([A-Za-z0-9_-]+)/), hh = h.match(/^#h=([^&]+)/);
    if (c) {
      if (cur && cur.source === 'shared' && BA.restoreHash === h) return;
      try { BA.restoreHash = h; say(''); show(await MyCards.decode(c[1]), {source: 'shared'}); } catch (e) { showErr('That share link could not be read: ' + e.message); }
      return;
    }
    if (hh) {
      let hv = hh[1]; try { hv = decodeURIComponent(hv); } catch (_) { /* keep as typed */ }
      if (cur && cur.source === 'hall' && cur.hall.h === hv) return;
      try { const e = await hallEntry(hv); if (!e) throw new Error(`no collector called @${hv}`); BA.restoreHash = h; show(e.mine, {source: 'hall', hall: e}); }
      catch (e) { showErr('Collector Hall: ' + e.message + '.'); }
      return;
    }
    const m = h.match(/^#m=(\d+)/);
    if (first) { const last = Saved.last(); if (last) openSaved(last.id); else renderSaved(); if (m) history.replaceState(null, '', h); }
    if (m && db.byId.has(m[1])) BA.open(db.byId.get(m[1]), cur && cur.mine[m[1]]);
  }
  window.addEventListener('hashchange', () => fromHash(false));
  fromHash(true);
})();
