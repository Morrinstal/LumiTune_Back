// features/dashboard.js
// KPIs, trends (SVG), top, recent, moderation + wiring

import { niceBytes, fmtRecentDate } from '../core/utils.js';
import { DashboardAPI } from '../core/api.js';
import { ensureTrackDuration } from '../core/duration.js';
import { getTopAudioSrc, scheduleTopProbe } from './top-helpers.js';

let dashDate = { start: null, end: null };
let dashObj = 'track';
let dashMetric = 'uploads';
let dashTop = 'track';

const el = {
  kpis: document.getElementById('dash-kpis'),
  svg:  document.getElementById('dash-line'),
  topTbody: document.querySelector('#dash-top-table tbody'),
  recent: document.getElementById('dash-recent'),
  moderation: document.getElementById('dash-moderation'),
  btnDate: document.getElementById('dashDateBtn'),
  pop: document.getElementById('dashDatePopover'),
  dStart: document.getElementById('dashDateStart'),
  dEnd: document.getElementById('dashDateEnd'),
  dApply: document.getElementById('dashDateApply'),
  dClear: document.getElementById('dashDateClear'),
};

function dashFormatBtn() {
  const span = el.btnDate?.querySelector('span');
  const { start, end } = dashDate;
  if (start || end) {
    span && (span.textContent = `${start || '...'} - ${end || '...'}`);
    el.btnDate?.classList.add('active');
  } else {
    span && (span.textContent = 'Last 7 days');
    el.btnDate?.classList.remove('active');
  }
}

function renderLine(svg, points) {
  if (!svg) return;
  svg.innerHTML = '';
  const W = 600, H = 200, pad = 18;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  if (!points?.length) {
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', W/2); t.setAttribute('y', H/2);
    t.setAttribute('text-anchor', 'middle'); t.setAttribute('fill', '#999');
    t.textContent = 'No data'; svg.appendChild(t); return;
  }
  const ys = points.map(p => +p.value || 0);
  const n = points.length - 1, minY = 0, maxY = Math.max(1, ...ys);
  const sx = (i) => pad + (i * (W - 2*pad) / Math.max(1, n));
  const sy = (v) => H - pad - ((v - minY) / (maxY - minY)) * (H - 2*pad);

  for (let g = 0; g <= 4; g++) {
    const y = H - (pad + g * ((H - 2*pad)/4));
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    Object.assign(line, { x1: pad, x2: W-pad, y1: y, y2: y });
    line.setAttribute('stroke', '#eee'); line.setAttribute('stroke-width', '1');
    svg.appendChild(line);
  }

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  let d = '';
  ys.forEach((v, i) => d += (i ? 'L' : 'M') + sx(i) + ' ' + sy(v));
  path.setAttribute('d', d); path.setAttribute('fill', 'none');
  path.setAttribute('stroke', '#111'); path.setAttribute('stroke-width', '2'); path.setAttribute('stroke-linecap', 'round');
  svg.appendChild(path);

  ys.forEach((v, i) => {
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', sx(i)); c.setAttribute('cy', sy(v)); c.setAttribute('r', '2.5'); c.setAttribute('fill', '#111');
    svg.appendChild(c);
  });
}

function renderKPIs(k) {
  if (!el.kpis) return;
  const items = [
    { label: 'Tracks (total)',     value: k.tracks_total,    sub:`+${k.tracks_new||0} in range` },
    { label: 'Audiobooks (total)', value: k.audiobooks_total, sub:`+${k.audiobooks_new||0}` },
    { label: 'Podcasts (total)',   value: k.podcasts_total,   sub:`+${k.podcasts_new||0}` },
    { label: 'Plays (overall)',    value: k.plays_total },
    { label: 'New users',          value: k.new_users },
    { label: 'Storage used',       value: niceBytes(k.storage_bytes) }
  ];
  el.kpis.innerHTML = items.map(x => `
    <div class="kpi">
      <div class="label">${x.label}</div>
      <div class="value">${x.value ?? 0}</div>
      ${x.sub ? `<div class="sub">${x.sub}</div>` : ''}
    </div>
  `).join('');
}

function renderTop(list) {
  if (!el.topTbody) return;
  el.topTbody.innerHTML = '';
  (list || []).forEach((row, idx) => {
    const meta = dashTop === 'track' ? (row.artist||'')
               : dashTop === 'audiobook' ? (row.author||'')
               : (row.show||'');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.name||''}</td>
      <td>${meta||''}</td>
      <td>${row.plays||0}</td>
      <td class="col-time">${row.time||'0:00'}</td>
    `;
    el.topTbody.appendChild(tr);

    const need = (!row.time || row.time === '0:00');
    if (!need || idx > 24) return;

    const cell = tr.querySelector('.col-time');
    scheduleTopProbe(async () => {
      const src = await getTopAudioSrc(row);
      if (!src) return;
      await ensureTrackDuration({ id: row.id, time: row.time }, src, cell);
    });
  });
}

function renderRecent(list) {
  if (!el.recent) return;
  el.recent.innerHTML = '';
  (list || []).forEach(it => {
    const meta = it.type === 'track' ? 'Track' : (it.type === 'audiobook' ? 'AudioBook' : 'Podcast');
    const li = document.createElement('li');
    li.innerHTML = `<span>${meta}</span><span class="truncate">${it.title||''}</span><span class="muted">${fmtRecentDate(it.at)}</span>`;
    el.recent.appendChild(li);
  });
}

function renderModeration(m = {}) {
  if (!el.moderation) return;
  el.moderation.innerHTML = `
    <div class="q"><div class="ttl">Adult flagged (all)</div><div class="num">${m.adult_flagged ?? 0}</div></div>
    <div class="q"><div class="ttl">Missing duration • Tracks</div><div class="num">${m.missing_duration?.tracks ?? 0}</div></div>
    <div class="q"><div class="ttl">Missing duration • Audiobooks</div><div class="num">${m.missing_duration?.audiobooks ?? 0}</div></div>
    <div class="q"><div class="ttl">Missing duration • Podcasts</div><div class="num">${m.missing_duration?.podcasts ?? 0}</div></div>
    <div class="q"><div class="ttl">Missing audio files (AB+PC)</div><div class="num">${m.missing_audio_count ?? 0}</div></div>
  `;
}

function qp() { const { start, end } = dashDate; return { start, end }; }

export async function loadDashboard() {
  const q = qp();
  await Promise.all([
    DashboardAPI.summary(q).then(d => renderKPIs(d.kpi || {})),
    DashboardAPI.timeseries({ metric: dashMetric, object: dashObj, ...q }).then(d => renderLine(el.svg, d.series || [])),
    DashboardAPI.top({ object: dashTop, limit: 10, ...q }).then(d => renderTop(d.items || [])),
    DashboardAPI.recent().then(d => renderRecent(d.items || [])),
    DashboardAPI.moderation().then(d => renderModeration(d.queues || {})),
  ]).catch(console.error);
}

export function initDashboardUI() {
  // Дата-поповер
  el.btnDate?.addEventListener('click', () => {
    if (!el.pop) return;
    el.dStart && (el.dStart.value = dashDate.start || '');
    el.dEnd   && (el.dEnd.value   = dashDate.end   || '');
    if (el.pop.hidden) {
      const r = el.btnDate.getBoundingClientRect();
      el.pop.style.left = r.left + 'px';
      el.pop.style.top  = (r.bottom + 8) + 'px';
      el.pop.hidden = false;
    } else el.pop.hidden = true;
  });
  document.addEventListener('click', (e) => {
    if (!el.pop || el.pop.hidden) return;
    if (!el.pop.contains(e.target) && !el.btnDate?.contains(e.target)) el.pop.hidden = true;
  });
  el.dApply?.addEventListener('click', () => {
    const s = el.dStart?.value || null;
    const e = el.dEnd?.value || null;
    if (s && e && s > e) return alert('Start must be before End');
    dashDate = { start: s, end: e }; dashFormatBtn(); el.pop.hidden = true; loadDashboard();
  });
  el.dClear?.addEventListener('click', () => {
    dashDate = { start: null, end: null }; dashFormatBtn(); el.pop.hidden = true; loadDashboard();
  });
  el.pop?.querySelectorAll('[data-preset]').forEach(b => {
    b.addEventListener('click', () => {
      const days = b.dataset.preset === '30d' ? 30 : 7;
      const now = new Date(); const end = now.toISOString().slice(0,10);
      const s = new Date(now.getTime() - (days-1)*86400000);
      dashDate = { start: s.toISOString().slice(0,10), end }; dashFormatBtn(); el.pop.hidden = true; loadDashboard();
    });
  });

  // Табы trends
  document.querySelectorAll('#dash-overview .tab[data-obj]').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('#dash-overview .tab[data-obj]').forEach(x => x.classList.remove('active'));
      t.classList.add('active'); dashObj = t.dataset.obj; loadDashboard();
    });
  });
  document.querySelectorAll('#dash-overview .chip[data-metric]').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#dash-overview .chip[data-metric]').forEach(x => x.classList.remove('active'));
      c.classList.add('active'); dashMetric = c.dataset.metric; loadDashboard();
    });
  });
  // Вкладки Top
  document.querySelectorAll('#dash-overview .tab[data-top]').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('#dash-overview .tab[data-top]').forEach(x => x.classList.remove('active'));
      t.classList.add('active'); dashTop = t.dataset.top; loadDashboard();
    });
  });

  // Пресет дат при первом входе
  if (!dashDate.start && !dashDate.end) {
    const now = new Date(); const end = now.toISOString().slice(0,10);
    const s7 = new Date(now.getTime() - 6*86400000);
    dashDate = { start: s7.toISOString().slice(0,10), end };
  }
  dashFormatBtn();
}

if (typeof window !== 'undefined') {
  Object.assign(window, { loadDashboard, initDashboardUI });
}
