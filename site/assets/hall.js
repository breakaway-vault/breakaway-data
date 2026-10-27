/* Collector Hall index: data/hall.json (compiled from collections/ by scripts/build_site.py). */
(function () {
  'use strict';
  const {$, esc, fmt, usd} = BA;
  BA.footer();
  let all = [];

  function card(e) {
    const s = e.s, top = s.setList[0], r = s.rare[0];
    const art = r ? `<div class="hcart ${BA.rarityClass(r.m.rarity)}">${BA.imgTag(BA.thumbSources(r.m), r.m.player)}</div>` : '<div class="hcart"></div>';
    const pct = top ? Math.round(top.have / top.total * 100) : 0;
    return `<a class="hcard" href="collection.html#h=${encodeURIComponent(e.h)}">
      ${art}
      <div class="hcbody">
        <div class="hchead"><b>@${esc(e.name || e.h)}</b>${e.example ? '<span class="pill ex">Example</span>' : ''}</div>
        ${e.team ? `<small class="dim">${esc(e.team)} fan</small>` : ''}
        ${e.blurb ? `<p class="blurb">${esc(e.blurb)}</p>` : ''}
        <dl class="hcstats">
          <div><dt>Moments</dt><dd>${fmt(s.items.length)}</dd></div>
          <div><dt>Est. value</dt><dd>${s.value ? usd(s.value) : '—'}</dd></div>
          <div class="wide"><dt>Rarest card</dt><dd>${r ? `<span class="rar ${BA.rarityClass(r.m.rarity)}">${esc(r.m.rarity)}</span> ${esc(r.m.player)}${r.eds[0] ? ` <span class="ed">#${fmt(r.eds[0])}</span>` : ''}${r.m.editions ? `<span class="dim"> / ${fmt(r.m.editions)}</span>` : ''}` : '—'}</dd></div>
          <div class="wide"><dt>Top set</dt><dd>${top ? `${esc(top.set)} <span class="dim">${esc(top.series)}</span>` : '—'}
            ${top ? `<span class="track"><i style="width:${pct}%"></i></span><span class="dim">${top.have}/${top.total} · ${pct}%</span>` : ''}</dd></div>
        </dl>
      </div></a>`;
  }

  function render() {
    const q = BA.norm($('#hq').value.trim()), sort = $('#hsort').value;
    let list = all.filter(e => !q || BA.norm([e.name, e.h, e.team, e.blurb].join(' ')).includes(q));
    const by = {
      value: (a, b) => b.s.value - a.s.value, moments: (a, b) => b.s.items.length - a.s.items.length,
      sets: (a, b) => (b.s.complete - a.s.complete) || (b.top - a.top), newest: (a, b) => (b.added || '').localeCompare(a.added || ''),
      handle: (a, b) => (a.name || a.h).localeCompare(b.name || b.h, undefined, {sensitivity: 'base'}),
    }[sort];
    list.sort((a, b) => (a.example - b.example) || by(a, b) || a.h.localeCompare(b.h));
    $('#hcount').textContent = q ? `${fmt(list.length)} of ${fmt(all.length)} collectors` : `${fmt(all.length)} collector${all.length === 1 ? '' : 's'}`;
    $('#hall').innerHTML = list.length ? list.map(card).join('') : '<p class="empty">No collectors match.</p>';
    BA.watch($('#hall'));
  }

  (async () => {
    try {
      const [db, res] = await Promise.all([BA.load(), fetch('data/hall.json', {cache: 'no-cache'})]);
      if (!res.ok) throw new Error('Could not load data/hall.json (' + res.status + ')');
      const h = await res.json();
      all = (h.entries || []).map(e => { const s = BA.stats(e.mine, db); return {...e, s, top: s.setList[0] ? s.setList[0].have / s.setList[0].total : 0}; });
      const real = all.filter(e => !e.example).length;
      $('#hstats').textContent = real ? `${fmt(real)} public collection${real === 1 ? '' : 's'} so far.` : 'No real collections yet: the entry below is a made-up example.';
      render();
    } catch (err) {
      $('#hall').innerHTML = `<p class="warn">${esc(err.message)}</p>`;
    }
    $('#hq').addEventListener('input', render);
    $('#hsort').addEventListener('change', render);
  })();
})();
