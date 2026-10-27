/* Reads a my_cards.csv / my_cards.txt list exactly like the archive app (breakaway.py mine_lines + load_mine),
   entirely in the browser. Nothing is uploaded. Also packs a collection into a short URL hash and back. */
'use strict';
const MyCards = (() => {
  const URL_RE = /(?:nft\.)?nhlbreakaway\.com\/series\/([A-Za-z0-9]{6,12})\/(\d{6,})|^([A-Za-z0-9]{6,12})\/(\d{6,})$/;
  const SITE_PLAYER_RE = /\/player\/(\d+)\b/;
  const PREF_RE = /url|link|card.?id|^id$|token|moment/;
  const LOW48 = (1n << 48n) - 1n;
  const isDigits = s => /^[0-9]+$/.test(s);
  const strip = s => s.replace(/^[\s\u00a0\ufeff]+|[\s\u00a0\ufeff]+$/g, '');

  function csvRow(line) {
    const out = []; let f = '', q = false, start = true;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (q) {
        if (c === '"') { if (line[i + 1] === '"') { f += '"'; i++; } else q = false; }
        else f += c;
      } else if (c === '"' && start) { q = true; start = false; }
      else if (c === ',') { out.push(f); f = ''; start = true; }
      else { f += c; start = false; }
    }
    out.push(f); return out;
  }
  const splitLines = txt => txt.split(/\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/);

  function mineLines(txt, name) {
    txt = txt.replace(/^\ufeff/, '');
    const lines = splitLines(txt).filter(ln => strip(ln) && !ln.replace(/^\s+/, '').startsWith('#'));
    if (!lines.length) return [];
    const isCsv = String(name || '').toLowerCase().endsWith('.csv') || (lines[0].includes(',') && !URL_RE.test(lines[0].split(',')[0] || 'x'));
    if (!isCsv) return lines.map(ln => [strip(ln), [strip(ln)], null]);
    const rows = lines.map(csvRow);
    const head = rows[0].map(h => h.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''));
    const looksHeader = !rows[0].some(c => URL_RE.test(c) || SITE_PLAYER_RE.test(c) || /^\d+$/.test(c.trim()));
    const body = looksHeader ? rows.slice(1) : rows;
    const col = (...names) => { for (let i = 0; i < head.length; i++) if (looksHeader && names.includes(head[i])) return i; return null; };
    const cId = col('card_id', 'cardid', 'id', 'card', 'card_number');
    const cUrl = col('url', 'link', 'card_url', 'breakaway_url', 'nft_url', 'site_url');
    const cSer = col('series_id', 'series'), cTok = col('token_id', 'token'), cEd = col('edition', 'edition_number', 'serial');
    const pref = head.map((h, i) => looksHeader && PREF_RE.test(h) ? i : -1).filter(i => i >= 0);
    return body.map(r => {
      const g = i => (i != null && i < r.length ? r[i].trim() : '');
      const cells = [g(cId), g(cUrl)];
      if (g(cSer) && g(cTok)) cells.push(g(cSer) + '/' + g(cTok));
      for (const i of pref) if (i < r.length) cells.push(r[i]);
      for (let i = 0; i < r.length; i++) if (!pref.includes(i) && (!pref.length || !r[i].trim().match(/^\d+$/))) cells.push(r[i]);
      const ed = g(cEd).replace(/^#/, '');
      return [r.join(','), cells.map(c => (c || '').trim()).filter(Boolean), /^\d+$/.test(ed) ? +ed : null];
    });
  }

  function parse(txt, name, moments) {
    const ids = new Set(moments.map(m => String(m.id)));
    const byMoment = new Map();
    for (const m of moments) {
      if (m.sid && m.token && /^\d+$/.test(m.token)) byMoment.set(m.sid + '\0' + (BigInt(m.token) >> 48n).toString(), String(m.id));
    }
    const cardOf = c => {
      let m = URL_RE.exec(c);
      if (m) {
        const sid = m[1] || m[3], tok = BigInt(m[2] || m[4]);
        const k = byMoment.get(sid + '\0' + (tok >> 48n).toString());
        return k ? [k, Number((tok & LOW48) + 1n)] : null;
      }
      m = SITE_PLAYER_RE.exec(c);
      if (m && ids.has(m[1])) return [m[1], null];
      if (isDigits(c) && ids.has(c) && c.length <= 6) return [c, null];
      return null;
    };
    const mine = {}, unmatched = [];
    for (const [raw, cells, ed] of mineLines(txt, name)) {
      const hit = cells.map(cardOf).find(Boolean);
      if (!hit) { unmatched.push(raw); continue; }
      let edition = ed || hit[1] || (cells.map(cardOf).find(h => h && h[0] === hit[0] && h[1]) || [])[1] || null;
      const eds = mine[hit[0]] || (mine[hit[0]] = []);
      if (edition && !eds.includes(edition)) eds.push(edition);
    }
    for (const v of Object.values(mine)) v.sort((a, b) => a - b);
    return {mine, unmatched, moments: Object.keys(mine).length, editions: Object.values(mine).reduce((n, v) => n + v.length, 0)};
  }

  function csvCell(v) {
    v = String(v ?? '');
    return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }
  function toCsv(mine, byId, compact) {
    const rows = compact ? [['card_id', 'edition']] : [['card_id', 'edition', 'player', 'team', 'set', 'rarity', 'url']];
    for (const cid of Object.keys(mine).map(Number).sort((a, b) => a - b).map(String)) {
      const m = byId.get(cid), eds = mine[cid] || [];
      const list = eds.length ? eds : [null];
      for (const e of list) {
        if (compact) { rows.push([cid, e || '']); continue; }
        let url = '';
        if (e && m && m.sid && m.token && /^\d+$/.test(m.token)) {
          url = `https://nhlbreakaway.com/series/${m.sid}/${((BigInt(m.token) >> 48n) << 48n) + BigInt(e - 1)}`;
        }
        rows.push([cid, e || '', m ? m.player : '', m ? m.team : '', m ? m.set : '', m ? m.rarity : '', url]);
      }
    }
    return rows.map(r => r.map(csvCell).join(',')).join('\n') + '\n';
  }

  function varints(nums) {
    const out = [];
    for (let n of nums) { n = n >>> 0; while (n >= 0x80) { out.push((n & 0x7f) | 0x80); n >>>= 7; } out.push(n); }
    return new Uint8Array(out);
  }
  function unvarints(u8) {
    const out = []; let n = 0, mul = 1;
    for (let i = 0; i < u8.length; i++) { const b = u8[i]; n += (b & 0x7f) * mul; if (b < 0x80) { out.push(n); n = 0; mul = 1; } else mul *= 128; }
    return out;
  }
  const b64u = u8 => { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); };
  const unb64u = s => { s = s.replace(/-/g, '+').replace(/_/g, '/'); const bin = atob(s + '==='.slice((s.length + 3) % 4)); return Uint8Array.from(bin, c => c.charCodeAt(0)); };
  async function pipe(u8, stream) { const r = new Response(new Blob([u8]).stream().pipeThrough(stream)); return new Uint8Array(await r.arrayBuffer()); }
  async function encode(mine) {
    const nums = []; let prev = 0;
    for (const id of Object.keys(mine).map(Number).sort((a, b) => a - b)) {
      const eds = [...mine[id]].sort((a, b) => a - b);
      nums.push(id - prev, eds.length); prev = id; let pe = 0;
      for (const e of eds) { nums.push(e - pe); pe = e; }
    }
    const raw = varints(nums);
    if (typeof CompressionStream !== 'undefined') {
      try { const z = await pipe(raw, new CompressionStream('deflate-raw')); if (z.length < raw.length) return 'z' + b64u(z); } catch (e) { /* plain */ }
    }
    return 'r' + b64u(raw);
  }
  async function decode(s) {
    let bytes = unb64u(s.slice(1));
    if (s[0] === 'z') {
      if (typeof DecompressionStream === 'undefined') throw new Error('This browser is too old to open compressed share links.');
      bytes = await pipe(bytes, new DecompressionStream('deflate-raw'));
    } else if (s[0] !== 'r') throw new Error('Not a collection link.');
    const n = unvarints(bytes), mine = {}; let i = 0, id = 0;
    while (i < n.length) {
      id += n[i++]; const c = n[i++] || 0, eds = []; let e = 0;
      for (let j = 0; j < c && i < n.length; j++) { e += n[i++]; eds.push(e); }
      mine[String(id)] = eds;
    }
    return mine;
  }
  return {parse, mineLines, encode, decode, csvRow, toCsv};
})();
if (typeof module !== 'undefined') module.exports = MyCards;
