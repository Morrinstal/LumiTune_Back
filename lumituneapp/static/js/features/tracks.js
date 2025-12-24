// features/tracks.js
// Треки: список, фильтры, поиск, play/pause, CRUD, пагинация, групповые списки (Albums/Genres/Tags/Authors)

import { debounce } from '../core/utils.js';
import { TracksAPI } from '../core/api.js';
import { ensureTrackDuration } from '../core/duration.js';

const state = {
  items: [],
  page: 1,
  perPage: 5,
  totalPages: 1,
  date: { start: null, end: null },
  q: '',
  filters: { artistid: null, albumid: null, genreid: null, tagsid: null, adult: null, has_audio: false },
  currentId: null, // вместо индекса
};

const el = { _ready: false };

// лениво подтягиваем DOM (нужно и для вызовов из меню до initTracksUI)
function ensureDom() {
  if (el._ready) return;
  // основная таблица
  el.tbody   = document.getElementById('tracks-tbody');
  el.pager   = document.getElementById('tracks-pagination');
  el.selAll  = document.getElementById('select-all');
  // топ-панель
  el.search  = document.getElementById('searchInput');
  el.dateBtn = document.getElementById('dateRangeBtn');
  el.pop     = document.getElementById('datePopover');
  el.dStart  = document.getElementById('dateStart');
  el.dEnd    = document.getElementById('dateEnd');
  el.dApply  = document.getElementById('dateApply');
  el.dClear  = document.getElementById('dateClear');
  // фильтры
  el.fBtn    = document.getElementById('filtersBtn');
  el.fPop    = document.getElementById('filtersPopover');
  el.fArtist = document.getElementById('fArtist');
  el.fAlbum  = document.getElementById('fAlbum');
  el.fGenre  = document.getElementById('fGenre');
  el.fTags   = document.getElementById('fTags');
  el.fAdult  = document.getElementById('fAdult');
  el.fHas    = document.getElementById('fHasAudio');
  // панель списков (группировки)
  el.mainView = document.getElementById('main-view');
  el.listView = document.getElementById('list-view');
  el.lpHead   = document.getElementById('lp-head');
  el.lpBody   = document.getElementById('lp-body');
  el.lpPager  = document.getElementById('lp-pagination');

  el._ready = true;
}

// ===== helpers (UI)
function setListTitle(main, sub, sectionId = 'dashboard-section'){
  const box = document.querySelector(`#${sectionId} .top-title`);
  if (!box) return;
  const h2 = box.querySelector('h2');
  const sm = box.querySelector('small');
  if (h2) h2.textContent = main;
  if (sm) sm.textContent = sub || '';
}
function showListPanel(){ ensureDom(); if (el.mainView) el.mainView.hidden = true; if (el.listView) el.listView.hidden = false; }
function hideListPanel(){ ensureDom(); if (el.listView) el.listView.hidden = true; if (el.mainView) el.mainView.hidden = false; }

const FIELD_ALIASES = {
  genres:'genreid', genre:'genreid',
  tags:'tagsid', tag:'tagsid', tagid:'tagid',
  authors:'artistid', artists:'artistid',
  albums:'albumid', album:'albumid',
  tracks:'tracks'
};
const TITLE_MAP = { albumid:'Albums', genreid:'Genres', tagid:'Tags', artistid:'Authors', tracks:'Tracks' };
const normalizeField = (f) => FIELD_ALIASES[(f||'').toLowerCase()] || f;

// ====== player (по id, а не по индексу)
export const player = new Audio();
player.preload = 'none';
player.addEventListener('ended', ()=>{ state.currentId = null; refreshPlayButtons(); });
player.addEventListener('play', refreshPlayButtons);
player.addEventListener('pause', refreshPlayButtons);

// ====== pager
function renderPager(containerEl, current, total, onGoto, withBulk = true) {
  const elc = containerEl;
  if (!elc) return;
  const has = total > 1;
  const btn = (p, txt = p, dis = false, act = false) =>
    `<button class="page-btn${act?' active':''}" data-goto="${p}" ${dis?'disabled':''}>${txt}</button>`;
  let html = `<div class="page-numbers">`;
  if (has) {
    const win = 5; let s = Math.max(1, current - Math.floor(win/2)); let e = Math.min(total, s + win - 1); s = Math.max(1, e - win + 1);
    html += btn(Math.max(1, current-1), '◀', current===1);
    if (s>1) { html += btn(1,'1'); if (s>2) html += `<button class="page-btn" disabled>…</button>`; }
    for (let p=s;p<=e;p++) html += btn(p, String(p), false, p===current);
    if (e<total) { if (e<total-1) html += `<button class="page-btn" disabled>…</button>`; html += btn(total,String(total)); }
    html += btn(Math.min(total, current+1), '▶', current===total);
  }
  html += `</div>` + (withBulk ? `<button type="button" class="delete-selected-btn">Delete Selected</button>` : '');
  elc.innerHTML = html;
  elc.style.display = (has || withBulk) ? 'flex' : 'none';

  elc.querySelectorAll('.page-btn[data-goto]').forEach(b => b.addEventListener('click', ()=> {
    const p = +b.dataset.goto; if (p && p !== current) onGoto(p);
  }));
  const bulk = elc.querySelector('.delete-selected-btn');
  if (withBulk && bulk) bulk.addEventListener('click', bulkDeleteSelected);
}

// ====== top bar state
function formatBtnRange() {
  ensureDom();
  const span = el.dateBtn?.querySelector('span');
  const active = (state.date.start || state.date.end);
  if (active) {
    const s = state.date.start ?? '…', e = state.date.end ?? '…';
    span && (span.textContent = `${s} - ${e}`); el.dateBtn?.classList.add('active');
  } else { span && (span.textContent = 'All time'); el.dateBtn?.classList.remove('active'); }
}
function updateFiltersBtnState() {
  ensureDom();
  const f = state.filters;
  const active = !!(f.artistid || f.albumid || f.genreid || f.tagsid || f.adult != null || f.has_audio);
  el.fBtn?.classList.toggle('active', active);
}

// ====== player controls (по id)
export function refreshPlayButtons() {
  ensureDom();
  document.querySelectorAll('.play-btn').forEach((b) => {
    const row = b.closest('tr');
    const isCur = row && row.dataset.id && row.dataset.id === String(state.currentId) && !player.paused && player.src;
    b.innerHTML = isCur
      ? '<img src="/media/iconsLuniTune/pause.png" width="16" height="16">'
      : '<img src="/media/iconsLuniTune/Group 132.png" width="16" height="16">';
  });
}
export function playTrack(id, btn) {
  const src = btn?.dataset?.src;
  if (!src) { alert('У трека нет аудио файла'); return; }
  if (state.currentId === id && !player.paused) { player.pause(); return; }
  if (player.src !== src) player.src = src;
  player.play().then(()=>{ state.currentId = id; refreshPlayButtons(); }).catch(console.error);
}

// ====== render tracks
export function renderTracks(list) {
  ensureDom();
  if (!el.tbody) return;
  el.tbody.innerHTML = '';
  (list || []).forEach((t) => {
    const src = (t.audio_url && t.audio_url.length ? t.audio_url : t.stream_url) || '';
    const tr = document.createElement('tr');
    tr.dataset.id = t.id;
    tr.innerHTML = `
      <td><input type="checkbox" class="row-select" data-id="${t.id}"></td>
      <td class="track-name">${t.name||''}</td>
      <td>${t.artistid||''}</td>
      <td>${t.genreid||''}</td>
      <td>${t.tagsid||''}</td>
      <td>${t.albumid||''}</td>
      <td>${t.seqnum||''}</td>
      <td>${t.playsnum||'0'}</td>
      <td class="col-adult"><input type="checkbox" class="adult-toggle" ${t.adult?'checked':''} onchange="setAdult('${t.id}', this)"></td>
      <td>${t.id}</td>
      <td class="col-time">${(t.time && t.time!=='0:00') ? t.time : '0:00'}</td>
      <td>
        <button class="action-btn play-btn" data-src="${src}" onclick="playTrack('${t.id}', this)" title="Play/Pause">
          <img src="/media/iconsLuniTune/Group 132.png" width="16" height="16">
        </button>
      </td>
      <td>
        <button class="action-btn edit-btn" onclick="editTrackById('${t.id}')"><img src="/media/iconsLuniTune/edit.png" width="16" height="16"></button>
        <button class="action-btn delete-btn" onclick="deleteTrackById('${t.id}')"><img src="/media/iconsLuniTune/close.png" width="16" height="16"></button>
      </td>
    `;
    el.tbody.appendChild(tr);

    const timeCell = tr.querySelector('.col-time');
    if (timeCell && src && (!t.time || t.time === '0:00')) ensureTrackDuration(t, src, timeCell);
  });
  el.selAll && (el.selAll.checked = false);
  refreshPlayButtons();
}

// ====== CRUD utils
export async function setAdult(id, checkbox) {
  const value = checkbox.checked;
  try {
    const fd = new FormData(); fd.append('adult', value ? 'true' : 'false');
    const d = await TracksAPI.update(id, fd);
    if (!d?.success) throw new Error(d?.error || 'Update failed');
    const i = state.items.findIndex(x => String(x.id) === String(id));
    if (i > -1) state.items[i].adult = value;
  } catch (e) {
    console.error(e); checkbox.checked = !value;
  }
}
export function getSelectedIds() {
  return Array.from(document.querySelectorAll('#tracks-tbody .row-select:checked'))
    .map(cb => cb.dataset.id || cb.closest('tr')?.dataset.id)
    .filter(Boolean);
}
export async function bulkDeleteSelected() {
  const ids = getSelectedIds();
  if (!ids.length) return alert('Выберите хотя бы один трек.');
  if (!confirm(`Удалить выбранные (${ids.length})?`)) return;
  try {
    const d = await TracksAPI.bulkDelete(ids);
    if (!d?.success) throw new Error(d?.error || 'Bulk delete failed');
    await loadTracks();
  } catch(e) { console.error(e); alert(e.message || 'Bulk delete error'); }
}

// ====== NEW / EDIT MODALS
export function openModal(){ ensureDom(); document.getElementById('modal')?.style && (document.getElementById('modal').style.display='flex'); }
export function closeModal(){ ensureDom(); document.getElementById('modal')?.style && (document.getElementById('modal').style.display='none'); }

function fillEditForm(t){
  (document.getElementById('edit_id')       ).value = t.id ?? '';
  (document.getElementById('edit_id_view')  ).value = t.id ?? '';
  (document.getElementById('edit_name')     ).value = t.name ?? '';
  (document.getElementById('edit_artistid') ).value = t.artistid ?? '';
  (document.getElementById('edit_albumid')  ).value = t.albumid ?? '';
  (document.getElementById('edit_seqnum')   ).value = t.seqnum ?? '';
  (document.getElementById('edit_genreid')  ).value = t.genreid ?? '';
  (document.getElementById('edit_tagsid')   ).value = (t.tagsid ?? t.tagid ?? '');
  (document.getElementById('edit_info')     ).value = t.info ?? '';
}
export function editTrackById(id){
  ensureDom();
  const t = state.items.find(x => String(x.id) === String(id));
  if (!t) return;
  const m = document.getElementById('editModal');
  if (m?.style) m.style.display = 'flex';
  fillEditForm(t);
}
export async function deleteTrackById(id) {
  const t = state.items.find(x => String(x.id) === String(id));
  if (!t) return;
  if (!confirm(`Delete "${t.name}"?`)) return;
  try {
    const d = await TracksAPI.delete(id);
    if (!d?.success) throw new Error(d?.error || 'Delete failed');
    await loadTracks();
  } catch(e) { console.error(e); alert(e.message || 'Delete error'); }
}

function bindEditForm(){
  ensureDom();
  const form = document.getElementById('editTrackForm');
  if (!form || form._bound) return;
  form._bound = true;
  form.addEventListener('submit', async (e)=>{
    e.preventDefault();

    const id = document.getElementById('edit_id').value;
    const fd = new FormData();
    fd.append('name',     document.getElementById('edit_name').value.trim());
    fd.append('artistid', document.getElementById('edit_artistid').value.trim());
    fd.append('albumid',  document.getElementById('edit_albumid').value.trim());
    fd.append('seqnum',   document.getElementById('edit_seqnum').value.trim());
    fd.append('genreid',  document.getElementById('edit_genreid').value.trim());
    fd.append('tagsid',   document.getElementById('edit_tagsid').value.trim());
    fd.append('info',     document.getElementById('edit_info').value.trim());

    const tf = document.getElementById('edit_track_file')?.files?.[0];
    const cf = document.getElementById('edit_cover_image')?.files?.[0];
    if (tf) fd.append('track_file', tf);
    if (cf) fd.append('cover_image', cf);

    try{
      const d = await TracksAPI.update(id, fd);
      if (!d?.success) { alert('Error updating track: ' + (d?.error || '')); return; }
      await loadTracks();
      closeEditModal();
    }catch(err){
      console.error(err);
      alert('Network error while updating track');
    }
  });
}
export function closeEditModal(){
  ensureDom();
  const m = document.getElementById('editModal');
  if (m?.style) m.style.display = 'none';
  document.getElementById('editTrackForm')?.reset();
}

// ====== list panel (Authors/Albums/Genres/Tags)
function renderListTable(fields, items, groupField){
  ensureDom();
  const head = el.lpHead, body = el.lpBody;
  if (!head || !body) return;
  head.innerHTML = `<th></th>` + (fields||[]).map(f => `<th>${f}</th>`).join('');
  body.innerHTML = (items||[]).map(row=>{
    const tds = (fields||[]).map(f=>{
      const v = row[f] ?? '';
      if (groupField && f === groupField && v){
        return `<td><a href="#" class="by-value" data-field="${groupField}" data-value="${v}">${v}</a></td>`;
      }
      return `<td>${v}</td>`;
    }).join('');
    return `<tr><td><input type="checkbox" class="track-checkbox"></td>${tds}</tr>`;
  }).join('');

  body.querySelectorAll('a.by-value').forEach(a=>{
    a.addEventListener('click', e=>{
      e.preventDefault();
      loadByField(a.dataset.field, a.dataset.value, (el.search?.value||'').trim());
    });
  });
}

export function showTracksSection(){
  ensureDom();
  // спрятать остальные разделы, показать dashboard-section
  ['dashboard-section','customers-section','playlists-section','audiobooks-section','podcasts-section','moods-section','dash-overview']
    .forEach(id => { const n = document.getElementById(id); if (!n) return; n.style.display = (id==='dashboard-section'?'block':'none'); });
  hideListPanel();
  setListTitle('Tracks','All tracks','dashboard-section');
}

export async function loadByField(field, value = "", q = ""){
  ensureDom();
  field = normalizeField(field);
  if (!field || field === 'tracks') {
    hideListPanel();
    setListTitle('Tracks', 'All tracks', 'dashboard-section');
    state.page = 1;
    state.q = (typeof q === 'string' ? q.trim() : '');
    await loadTracks();
    return;
  }

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  params.set('page', '1');
  params.set('page_size', '10');

  const base = `/api/tracks/by/${encodeURIComponent(field)}/${value ? encodeURIComponent(value)+'/' : ''}`;
  const url  = base + (params.toString() ? `?${params.toString()}` : '');

  try{
    const res = await fetch(url, { credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest'} });
    const data = await res.json();
    if (!res.ok || !data.success){ console.error('by-field error:', data.error || res.status); return; }

    setListTitle(TITLE_MAP[field] || field, value ? `Filter: ${TITLE_MAP[field] || field} = ${value}` : `All ${TITLE_MAP[field] || field}`, 'dashboard-section');
    showListPanel();
    renderListTable(data.fields, data.items, data.field);

    const totalPages = Number(data.total_pages) || 1;
    const page = Number(data.page) || 1;
    renderPager(el.lpPager, page, totalPages, async (p)=>{
      const u = new URL(base, location.origin);
      u.searchParams.set('page', String(p));
      u.searchParams.set('page_size','10');
      if (q) u.searchParams.set('q', q);
      const r = await fetch(u.toString(), { credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest'} });
      const d = await r.json();
      renderListTable(d.fields, d.items, d.field);
    }, false);
  }catch(err){
    console.error('loadByField failed:', err);
  }
}

// ====== API: load tracks
export async function loadTracks() {
  ensureDom();
  const params = {
    start: state.date.start, end: state.date.end, q: state.q,
    artistid: state.filters.artistid, albumid: state.filters.albumid, genreid: state.filters.genreid,
    tagsid: state.filters.tagsid, adult: state.filters.adult, has_audio: state.filters.has_audio ? 'true' : '',
    page: state.page, page_size: state.perPage
  };
  try {
    const data = await TracksAPI.list(params);

    // поддерживаем оба варианта API: с серверной пагинацией и без
    const serverPaged = Number(data.total_pages) > 0 || typeof data.page === 'number';
    state.items = data.tracks || [];
    state.perPage = data.page_size || state.perPage;
    state.page = data.page || state.page;

    if (serverPaged) {
      state.totalPages = Number(data.total_pages) || 1;
      renderTracks(state.items);
    } else {
      const total = (data.total ?? data.count_total ?? data.count ?? state.items.length);
      state.totalPages = Math.max(1, Math.ceil(total / state.perPage));
      const start = (state.page - 1) * state.perPage;
      renderTracks(state.items.slice(start, start + state.perPage));
    }

    renderPager(el.pager, state.page, state.totalPages, (p)=>{ state.page = p; loadTracks(); }, true);
  } catch (e) {
    console.error('loadTracks:', e);
  }
}

// ====== init
export function initTracksUI() {
  ensureDom();

  // Date popover
  function togglePop() {
    if (!el.pop) return;
    if (el.dStart) el.dStart.value = state.date.start || '';
    if (el.dEnd)   el.dEnd.value   = state.date.end   || '';
    el.pop.style.display = (el.pop.style.display === 'none' || !el.pop.style.display) ? 'block' : 'none';
  }
  el.dateBtn?.addEventListener('click', togglePop);
  document.addEventListener('click', (e) => { if (el.pop && !el.pop.contains(e.target) && !el.dateBtn?.contains(e.target)) el.pop.style.display = 'none'; });
  el.dApply?.addEventListener('click', () => {
    const s = el.dStart?.value || null; const e = el.dEnd?.value || null;
    if (s && e && s > e) return alert('Start date must be before End date');
    state.date = { start: s, end: e }; state.page = 1; formatBtnRange(); el.pop && (el.pop.style.display = 'none'); loadTracks();
  });
  el.dClear?.addEventListener('click', () => {
    state.date = { start: null, end: null }; state.page = 1; formatBtnRange(); el.pop && (el.pop.style.display = 'none'); loadTracks();
  });
  formatBtnRange();

  // Filters popover
  const openFilters = () => {
    if (!el.fPop || !el.fBtn) return;
    el.fArtist && (el.fArtist.value = state.filters.artistid || '');
    el.fAlbum  && (el.fAlbum.value  = state.filters.albumid  || '');
    el.fGenre  && (el.fGenre.value  = state.filters.genreid  || '');
    el.fTags   && (el.fTags.value   = state.filters.tagsid   || '');
    el.fAdult  && (el.fAdult.value  = (state.filters.adult===null ? '' : String(state.filters.adult)));
    el.fHas    && (el.fHas.checked  = !!state.filters.has_audio);
    if (el.fPop.parentElement !== document.body) document.body.appendChild(el.fPop);
    el.fPop.hidden = false;
    const r = el.fBtn.getBoundingClientRect();
    let left = r.left, top = r.bottom + 8, pw = el.fPop.offsetWidth || 360, ph = el.fPop.offsetHeight || 320, margin = 8;
    if (left + pw + margin > innerWidth) left = Math.max(margin, innerWidth - pw - margin);
    if (top + ph + margin > innerHeight) top = Math.max(margin, r.top - ph - 8);
    el.fPop.style.left = `${left}px`; el.fPop.style.top = `${top}px`;
  };
  el.fBtn?.addEventListener('click', () => el.fPop ? (el.fPop.hidden ? openFilters() : (el.fPop.hidden = true)) : null);
  document.addEventListener('click', (e)=>{ if(el.fPop && !el.fPop.hidden && !el.fPop.contains(e.target) && !el.fBtn?.contains(e.target)) el.fPop.hidden = true; });
  window.addEventListener('resize', () => { if(el.fPop && !el.fPop.hidden) openFilters(); });
  document.getElementById('filtersApply')?.addEventListener('click', ()=>{
    state.filters.artistid = (el.fArtist?.value || '').trim() || null;
    state.filters.albumid  = (el.fAlbum?.value  || '').trim() || null;
    state.filters.genreid  = (el.fGenre?.value  || '').trim() || null;
    state.filters.tagsid   = (el.fTags?.value   || '').trim() || null;
    const adultVal = el.fAdult?.value ?? '';
    state.filters.adult  = (adultVal==='' ? null : adultVal==='true');
    state.filters.has_audio = !!el.fHas?.checked;
    state.page = 1; updateFiltersBtnState(); el.fPop.hidden = true; loadTracks();
  });
  document.getElementById('filtersClear')?.addEventListener('click', ()=>{
    state.filters = { artistid:null, albumid:null, genreid:null, tagsid:null, adult:null, has_audio:false };
    updateFiltersBtnState(); state.page = 1; el.fPop && (el.fPop.hidden = true); loadTracks();
  });
  updateFiltersBtnState();

  // Search
  const runSearch = debounce(() => {
    state.page = 1;
    state.q = (el.search?.value || '').trim();
    loadTracks();
  }, 300);
  el.search?.addEventListener('input', runSearch);

  // Select all
  el.selAll?.addEventListener('change', function () {
    document
      .querySelectorAll('#tracks-tbody .row-select')
      .forEach(cb => (cb.checked = this.checked));
  });

  // UPDATE form
  bindEditForm();

  // первичная загрузка
  loadTracks();
}

// ====== экспорт в глобал (для inline-обработчиков в разметке)
if (typeof window !== 'undefined') {
  Object.assign(window, {
    // плейер
    playTrack,
    // рендер/загрузка
    renderTracks,
    loadTracks,
    // CRUD
    setAdult,
    bulkDeleteSelected,
    deleteTrackById,
    // модалки
    openModal,
    closeModal,
    editTrackById,
    closeEditModal,
    // панель списков
    showTracksSection,
    loadByField,
    // сам плеер
    player,
  });
}
