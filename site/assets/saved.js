/* Saved collections: kept only in this browser (localStorage) on this device. Nothing is uploaded.
   Clearing this site's data in the browser removes them, so the page offers a CSV export as a backup. */
'use strict';
const Saved = (() => {
  const KEY = 'breakaway-archive.collections.v1';
  let ls = null;
  try { ls = window.localStorage; const t = KEY + '.test'; ls.setItem(t, '1'); ls.removeItem(t); } catch (e) { ls = null; }

  function read() {
    if (!ls) return {v: 1, last: null, items: {}};
    try {
      const d = JSON.parse(ls.getItem(KEY) || 'null');
      if (d && d.v === 1 && d.items && typeof d.items === 'object') return d;
    } catch (e) { /* unreadable: start fresh, but never overwrite it until the visitor saves */ }
    return {v: 1, last: null, items: {}};
  }
  function write(d) {
    if (!ls) return 'This browser is not letting the site store anything (private mode or blocked site data), so collections cannot be saved here. Use Export my_cards.csv to keep a copy.';
    try { ls.setItem(KEY, JSON.stringify(d)); return null; }
    catch (e) {
      const full = e && (e.name === 'QuotaExceededError' || e.name === 'NS_ERROR_DOM_QUOTA_REACHED' || e.code === 22 || e.code === 1014);
      return full ? "This browser's storage for the site is full, so that change wasn't saved. Delete a saved collection you no longer need, or use Export my_cards.csv to keep a copy."
                  : 'The collection could not be saved in this browser (' + (e && e.message || e) + ').';
    }
  }
  const clean = mine => { const o = {}; for (const [k, v] of Object.entries(mine || {})) if (/^\d+$/.test(k)) o[k] = [...new Set((v || []).filter(n => Number.isInteger(n) && n > 0))].sort((a, b) => a - b); return o; };
  const same = (a, b) => JSON.stringify(clean(a)) === JSON.stringify(clean(b));
  const newId = () => (Date.now().toString(36) + Math.random().toString(36).slice(2, 8));
  const tidyName = s => String(s || '').trim().slice(0, 60);

  function list() { const d = read(); return Object.entries(d.items).map(([id, x]) => ({id, ...x})).sort((a, b) => (b.updated || 0) - (a.updated || 0)); }
  function get(id) { const x = read().items[id]; return x ? {id, ...x} : null; }
  function uniqueName(name, except) {
    name = tidyName(name) || 'My collection';
    const taken = new Set(list().filter(x => x.id !== except).map(x => x.name.toLowerCase()));
    if (!taken.has(name.toLowerCase())) return name;
    for (let n = 2; ; n++) if (!taken.has(`${name} ${n}`.toLowerCase())) return `${name} ${n}`;
  }
  function add(name, mine) {
    const d = read(), id = newId(), now = Date.now();
    d.items[id] = {name: uniqueName(name), mine: clean(mine), created: now, updated: now}; d.last = id;
    const error = write(d); return error ? {error} : {id, name: d.items[id].name};
  }
  function update(id, patch) {
    const d = read(), x = d.items[id]; if (!x) return {error: 'That saved collection no longer exists (it may have been deleted in another tab).'};
    if (patch.name != null) x.name = uniqueName(patch.name, id);
    if (patch.mine) x.mine = clean(patch.mine);
    x.updated = Date.now(); d.last = id;
    const error = write(d); return error ? {error} : {id, name: x.name};
  }
  function remove(id) {
    const d = read(); delete d.items[id]; if (d.last === id) d.last = null;
    const error = write(d); return error ? {error} : {};
  }
  function setLast(id) { const d = read(); if (d.items[id] && d.last !== id) { d.last = id; write(d); } }
  function last() { const d = read(); return d.last && d.items[d.last] ? get(d.last) : null; }
  function find(mine) { return list().find(x => same(x.mine, mine)) || null; }
  const onChange = fn => window.addEventListener('storage', e => { if (e.key === KEY || e.key === null) fn(); });
  return {available: !!ls, KEY, list, get, add, update, remove, setLast, last, find, uniqueName, onChange};
})();
