'use strict';
const BA = (() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = n => Number(n).toLocaleString('en-US');
  const usd = n => n == null || n === 0 ? '—' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const RARITY_ORDER = ['Mythic', 'Legendary', 'Heroic', 'Epic', 'Rare', 'Limited', 'Core', 'Fandom'];
  const rarityClass = r => 'r-' + String(r || 'none').toLowerCase().replace(/[^a-z]+/g, '');
  let DB = null, DETAIL = {}, restoreHash = '';

  async function load() {
    if (DB) return DB;
    const res = await fetch('data/moments.json', {cache: 'force-cache'});
    if (!res.ok) throw new Error('Could not load data/moments.json (' + res.status + ')');
    const d = await res.json(), T = d.tables;
    const moments = d.moments.map((m, pos) => {
      const o = {
        id: m.i, pos, player: m.p, team: T.team[m.t], set: T.set[m.s], series: T.series[m.se], rarity: T.rarity[m.r],
        editions: m.e ?? null, date: m.d || '', play: m.pl || '', flags: m.fl || '', ask: m.la ?? null, fmv: m.fm ?? null,
        sid: m.k ? m.k[0] : '', token: m.k ? m.k[1] : '', cover: m.c || '', thumb: m.th || '', video: m.vu || '',
        tc: m.tc || '', ia: m.ia ? (d.iap || '') + m.ia : '', iaCover: m.ic ? (d.iap || '') + m.ic : '', noVideo: !!m.nv, fifth: !!m.f5, health: m.h || 'unchecked', missing: m.m || [], listed: m.ln, unverified: !!m.u,
      };
      if (!o.thumb && o.cover) o.thumb = o.cover.replace(/front\.png$/, 'front-500x.png');
      o.value = o.fmv ?? o.ask ?? null;
      o.text = norm([o.player, o.team, o.set, o.series, o.rarity, o.play, o.flags, o.id].join(' '));
      return o;
    });
    const byId = new Map(moments.map(m => [String(m.id), m]));
    DB = {moments, byId, raw: d, tables: T, nft: d.nft, mg: d.mg, ia: (d.ia || 'https://archive.org/'), iap: d.iap || '', gateways: d.gateways || [], chunk: d.chunk || 100, chunks: d.chunks || 0};
    return DB;
  }

  async function detail(m) {
    if (DETAIL[m.id]) return DETAIL[m.id];
    const chunk = Math.floor(m.pos / DB.chunk);
    if (!DETAIL['_' + chunk]) {
      const r = await fetch(`data/detail/${chunk}.json`, {cache: 'force-cache'});
      if (!r.ok) throw new Error('detail ' + chunk);
      DETAIL['_' + chunk] = await r.json();
    }
    const row = DETAIL['_' + chunk].find(x => x.i === m.id) || {};
    return DETAIL[m.id] = {
      description: row.ds || '', issued: row.is || '', position: row.pos || '', jersey: row.jn || '',
      period: row.pe || '', clock: row.cl || '', final: row.fs || '', venue: row.v || '', tagline: row.tg || '',
      audio: row.au || '', coverIpfs: row.ci || '', videoIpfs: row.vi || '',
    };
  }

  function coverSources(m) {
    const out = [];
    if (m.cover) out.push(DB.nft + m.cover);
    if (m.iaCover) out.push(DB.ia + 'download/' + m.iaCover);
    if (m.tc) for (const g of DB.gateways) out.push(g + m.tc);
    return out;
  }
  function thumbSources(m) {
    const out = [];
    if (m.thumb) out.push(DB.nft + m.thumb);
    else if (m.cover) out.push(DB.nft + m.cover);
    if (m.tc) for (const g of DB.gateways) out.push(g + m.tc);
    return out;
  }
  function videoSources(m, d) {
    const out = [];
    if (m.ia) out.push(DB.ia + 'download/' + m.ia);                 // Internet Archive copy first
    if (!m.noVideo) {
      const path = m.video || (m.sid && m.token ? `${m.sid}/${m.token}/video.mp4` : '');
      if (path) out.push(DB.mg + path);
    }
    if (d && d.videoIpfs) for (const g of DB.gateways) out.push(g + d.videoIpfs);
    return out;
  }

  const STALL_MS = 8000;
  function imgTag(srcs, alt, cls) {
    if (!srcs.length) return `<div class="noimg ${cls || ''}">No cover</div>`;
    return `<img class="${cls || ''}" loading="lazy" decoding="async" src="${esc(srcs[0])}" data-alts="${esc(srcs.slice(1).join('|'))}" alt="${esc(alt)}" onerror="BA.nextSrc(this)">`;
  }
  function nextSrc(img) {
    clearTimeout(img._t);
    const a = (img.dataset.alts || '').split('|').filter(Boolean);
    if (!a.length) { img.onerror = null; img.replaceWith(Object.assign(document.createElement('div'), {className: 'noimg ' + img.className, textContent: 'Cover unavailable'})); return; }
    img.src = a.shift(); img.dataset.alts = a.join('|'); arm(img);
  }
  function arm(img) { clearTimeout(img._t); img._t = setTimeout(() => { if (!(img.complete && img.naturalWidth)) nextSrc(img); }, STALL_MS); }
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { io.unobserve(e.target); arm(e.target); } }), {rootMargin: '300px'}) : null;
  function watch(root) {
    $$('img[data-alts]', root).forEach(i => {
      if (i._w) return; i._w = 1; i.addEventListener('load', () => clearTimeout(i._t));
      if (i.complete && i.naturalWidth) return; io ? io.observe(i) : arm(i);
    });
  }

  const RISKY = ['some_missing', 'video_missing', 'all_missing'];
  const atRisk = m => m.listed === 0 || RISKY.includes(m.health);
  const HEALTH_TEXT = {some_missing: 'some of its files are missing from IPFS', video_missing: 'its video is missing from IPFS', all_missing: 'its files are missing from IPFS'};
  function riskText(m) {
    const why = [];
    if (m.listed === 0) why.push('it is not listed on NHL Breakaway right now');
    if (RISKY.includes(m.health)) why.push(HEALTH_TEXT[m.health] + (m.health === 'some_missing' && m.missing && m.missing.length ? ' (' + m.missing.join(', ') + ')' : ''));
    return 'Heads up: ' + why.join(', and ') + '.' + (m.ia ? ' The Internet Archive copy still plays here.' : '');
  }
  function tile(m, extra) {
    const risk = atRisk(m) ? '<span class="risk">At risk</span>' : '';
    return `<button class="tile ${rarityClass(m.rarity)}" data-id="${m.id}" aria-label="${esc(m.player)}, ${esc(m.set)}, ${esc(m.rarity)}">
      <div class="art">${imgTag(thumbSources(m), m.player)}${risk}${extra && extra.badge ? extra.badge : ''}</div>
      <div class="meta">
        <b>${esc(m.player)}</b>
        <small>${esc(m.team)}</small>
        <div class="row"><span class="rar">${esc(m.rarity)}</span><span class="ed">${m.editions ? '/' + fmt(m.editions) : ''}</span></div>
        <div class="row sub"><span>${esc(m.set)}</span><span>${m.value != null ? usd(m.value) : ''}</span></div>
        ${extra && extra.line ? `<div class="own">${extra.line}</div>` : ''}
      </div></button>`;
  }

  async function open(m, eds) {
    if (!m) return;
    const d = await detail(m);
    const el = $('#modal') || Object.assign(document.body.appendChild(document.createElement('div')), {id: 'modal'});
    const vids = videoSources(m, d), covers = coverSources(m);
    const archive = m.ia ? `<a href="${esc(DB.ia + 'details/' + m.ia.split('/')[0])}" target="_blank" rel="noopener">Internet Archive copy</a> (<a href="${esc(DB.ia + 'download/' + m.ia)}" target="_blank" rel="noopener">video file</a>)` : '';
    const fifth = m.fifth ? `<a href="https://thefifthlinecode.onrender.com/player/${m.id}" target="_blank" rel="noopener">The Fifth Line</a>` : '';
    const breakaway = m.sid && m.token ? `<a href="https://nhlbreakaway.com/series/${esc(m.sid)}/${esc(m.token)}" target="_blank" rel="noopener">NHL Breakaway page</a>` : '';
    el.hidden = false; document.body.classList.add('noscroll');
    el.innerHTML = `<div class="backdrop" data-close></div>
      <div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(m.player)}">
        <button class="x" data-close aria-label="Close">×</button>
        <div class="detail ${rarityClass(m.rarity)}">
          <div class="media"><div class="player" data-state="idle">
            ${imgTag(covers, m.player, 'poster')}
            ${vids.length ? `<button class="play" type="button"><span aria-hidden="true">▶</span> Play highlight</button>` : '<div class="novid">No video on file</div>'}
            <div class="vstatus"></div>
          </div></div>
          <div class="info">
            <div class="kicker"><span class="rar">${esc(m.rarity)}</span> · ${esc(m.set)} · ${esc(m.series)}</div>
            <h2>${esc(m.player)}</h2>
            <div class="sub">${esc(m.team)}${m.editions ? ` · /${fmt(m.editions)}` : ''} · #${m.id}</div>
            <div class="chips">
              ${m.date ? `<span>${esc(m.date)}</span>` : ''}
              ${m.play ? `<span>${esc(m.play)}</span>` : ''}
              ${m.flags ? m.flags.split(/,\s*/).map(f => `<span class="flag">${esc(f)}</span>`).join('') : ''}
            </div>
            ${d.tagline ? `<p class="tag">${esc(d.tagline)}</p>` : ''}
            ${d.description ? `<p class="desc">${esc(d.description)}</p>` : ''}
            <div class="prices">
              <div><small>FMV</small><b>${usd(m.fmv)}</b></div>
              <div><small>Lowest ask</small><b>${usd(m.ask)}</b></div>
              <div><small>Editions</small><b>${m.editions ? fmt(m.editions) : '—'}</b></div>
            </div>
            <table class="facts">
              ${[['Position', d.position], ['Jersey', d.jersey], ['Period', d.period], ['Clock', d.clock], ['Final', d.final], ['Venue', d.venue], ['Issued', d.issued], ['Audio', d.audio]].filter(([,v]) => v).map(([k,v]) => `<tr><th>${k}</th><td>${esc(v)}</td></tr>`).join('')}
            </table>
            ${eds && eds.length ? `<div class="mine">You own: ${eds.map(e => '#' + e).join(', ')}</div>` : ''}
            ${atRisk(m) ? `<div class="warn">${esc(riskText(m))}</div>` : ''}
            <p class="links">${[archive, breakaway, fifth].filter(Boolean).join(' · ')}</p>
            ${(d.coverIpfs || d.videoIpfs) ? `<details class="ipfs"><summary>IPFS</summary><p>${d.coverIpfs ? 'Cover: <code>' + esc(d.coverIpfs) + '</code><br>' : ''}${d.videoIpfs ? 'Video: <code>' + esc(d.videoIpfs) + '</code>' : ''}</p></details>` : ''}
          </div>
        </div>
      </div>`;
    el.onclick = e => { if (e.target.closest('[data-close]')) close(); };
    const play = $('.play', el);
    if (play) play.onclick = () => startVideo(el, vids);
    history.replaceState(null, '', (restoreHash || location.pathname + location.search) + '#m=' + m.id);
  }
  function startVideo(el, vids) {
    const player = $('.player', el), status = $('.vstatus', el);
    const src = n => /archive\.org\//.test(vids[n]) ? 'the Internet Archive' : /\/ipfs\//.test(vids[n]) ? 'IPFS' : 'the NHL Breakaway CDN';
    let i = 0;
    const tryNext = () => {
      if (i >= vids.length) { status.textContent = 'Video unavailable'; return; }
      const v = document.createElement('video'); v.controls = true; v.autoplay = true; v.playsInline = true;
      v.src = vids[i++];
      status.textContent = 'Loading from ' + src(i - 1) + '…';
      v.onerror = () => { v.remove(); tryNext(); };
      v.onloadeddata = () => { status.textContent = 'Playing from ' + src(i - 1); player.dataset.state = 'playing'; };
      const poster = $('img.poster, .noimg', player); if (poster) poster.replaceWith(v); else player.prepend(v);
      $('.play', player)?.remove();
    };
    tryNext();
  }
  function close() {
    const el = $('#modal'); if (!el) return;
    el.hidden = true; el.innerHTML = ''; document.body.classList.remove('noscroll');
    const base = restoreHash || location.pathname + location.search;
    history.replaceState(null, '', base || location.pathname);
  }
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#modal') && !$('#modal').hidden) close(); });

  function footer() {
    const f = document.createElement('footer'); f.className = 'site-foot';
    f.innerHTML = `<p><b>Unofficial fan preservation project.</b> Not affiliated with or endorsed by the NHL, NHLPA, NHLAA, Sweet (SocialSweet Inc.) or any team.
      Media loads from fan copies on the Internet Archive, NHL Breakaway's servers and public IPFS gateways; this site hosts none of it.
      Takedown requests are honoured via a <a href="https://github.com/breakaway-vault/breakaway-data/issues/new" target="_blank" rel="noopener">GitHub issue</a>.</p>
      <p>Data from <a href="https://github.com/breakaway-vault/breakaway-data" target="_blank" rel="noopener">breakaway-data</a>. Prices are an Oct 2026 snapshot, for fun only.</p>`;
    document.body.appendChild(f);
  }

  function stats(mine, db) {
    const M = db.moments, items = Object.entries(mine || {}).map(([id, eds]) => ({m: db.byId.get(String(id)), eds})).filter(x => x.m);
    const copies = x => Math.max(1, x.eds.length);
    const sets = new Map();
    for (const a of M) { const k = a.series + '\u0000' + a.set; const s = sets.get(k) || sets.set(k, {series: a.series, set: a.set, total: 0, have: 0}).get(k); s.total++; }
    for (const x of items) sets.get(x.m.series + '\u0000' + x.m.set).have++;
    const setList = [...sets.values()].filter(s => s.have).sort((a, b) => b.have / b.total - a.have / a.total || b.total - a.total);
    const rare = [...items].sort((a, b) => (a.m.editions ?? 1e9) - (b.m.editions ?? 1e9) || (a.eds[0] ?? 1e9) - (b.eds[0] ?? 1e9) || (b.m.value ?? 0) - (a.m.value ?? 0));
    const by = f => { const t = new Map(); for (const x of items) t.set(f(x), (t.get(f(x)) || 0) + copies(x)); return t; };
    return {
      items, copies, setList, rare, teams: by(x => x.m.team), byRarity: by(x => x.m.rarity),
      editions: items.reduce((n, x) => n + x.eds.length, 0),
      value: items.reduce((s, x) => s + (x.m.fmv ?? x.m.ask ?? 0) * copies(x), 0),
      askValue: items.reduce((s, x) => s + (x.m.ask ?? 0) * copies(x), 0),
      unpriced: items.filter(x => x.m.value == null).length,
      complete: setList.filter(s => s.have === s.total).length,
    };
  }
  return {$, $$, esc, fmt, usd, norm, load, detail, tile, imgTag, open, close, watch, nextSrc, footer, stats, RARITY_ORDER, rarityClass, atRisk, coverSources, videoSources, thumbSources,
    get restoreHash() { return restoreHash; }, set restoreHash(v) { restoreHash = v; }, get db() { return DB; }};
})();
