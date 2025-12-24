// features/playlists.js
// грид, модалка, локальный кэш

import { debounce, escapeHtml } from '../core/utils.js';
import { PlaylistsAPI } from '../core/api.js';

const LS_PLAYLISTS_KEY = 'dash.playlists';
let playlists = [];
const selectedTracks = new Map(); // id -> {id,name,artistid}

const el = {
  grid: document.getElementById('playlists-grid'),
  btnNew: document.getElementById('btn-new-playlist') || document.querySelector('.new-item-btn'),
  modal: document.getElementById('playlistCreateModal'),
  close: document.getElementById('pl-close'),
  cancel: document.getElementById('pl-cancel'),
  form: document.getElementById('playlistCreateForm'),
  title: document.getElementById('pl_title'),
  desc: document.getElementById('pl_desc'),
  cover: document.getElementById('pl_cover'),
  coverPrev: document.getElementById('pl-cover-preview'),
  search: document.getElementById('pl_track_search'),
  results: document.getElementById('pl_results_list'),
  chips: document.getElementById('pl_selected_chips'),
  count: document.getElementById('pl_selected_count'),
};

function saveLocal(){ try{ localStorage.setItem(LS_PLAYLISTS_KEY, JSON.stringify(playlists)); }catch{} }
function loadLocal(){
  try{ const raw = localStorage.getItem(LS_PLAYLISTS_KEY); const arr = raw ? JSON.parse(raw) : []; if(Array.isArray(arr)) playlists = arr; }catch{}
}

export function renderPlaylistsGrid(){
  if (!el.grid) return;
  el.grid.innerHTML = '';
  (playlists || []).forEach(pl=>{
    const count = Number(pl.tracks_count ?? (pl.tracks?.length ?? 0)) || 0;
    const div = document.createElement('div');
    div.className = 'pl-card'; div.dataset.id = String(pl.id);
    div.innerHTML = `
      <img class="pl-cover" src="${pl.cover_url || '/media/placeholder-cover.png'}" alt="">
      <div class="pl-actions">
        <button class="pl-action pl-edit" title="Edit"><img src="/media/iconsLuniTune/edit.png" alt=""></button>
        <button class="pl-action pl-del"  title="Delete"><img src="/media/iconsLuniTune/close.png" alt=""></button>
      </div>
      <div class="pl-title" title="${escapeHtml(pl.title)}">${pl.title}</div>
      <div class="pl-sub">${count} tracks</div>
    `;
    el.grid.appendChild(div);
  });
}

function resetForm(){
  el.form?.reset?.();
  if (el.form) delete el.form.dataset.editId;
  selectedTracks.clear();
  el.count && (el.count.textContent = '0');
  el.chips && (el.chips.innerHTML = '');
  el.results && (el.results.innerHTML = '');
  if (el.coverPrev){ el.coverPrev.src=''; el.coverPrev.style.display='none'; }
  const btn = el.form?.querySelector('[type="submit"]');
  btn && (btn.textContent = 'Create playlist', btn.classList.remove('saving-as-edit'));
}

export function openPlaylistCreateModal(){ resetForm(); el.modal && (el.modal.style.display = 'flex'); }
export function closePlaylistCreateModal(){ resetForm(); el.modal && (el.modal.style.display = 'none'); }

function updateSelectedChips(){
  if (!el.chips || !el.count) return;
  el.chips.innerHTML = '';
  selectedTracks.forEach((t, key)=>{
    const chip = document.createElement('div');
    chip.className = 'pl-chip';
    chip.innerHTML = `
      <span class="truncate">${escapeHtml(t.name||'')} — ${escapeHtml(t.artistid||'')}</span>
      <span class="x" title="Remove">×</span>
    `;
    chip.querySelector('.x').addEventListener('click', ()=>{ selectedTracks.delete(key); updateSelectedChips(); });
    el.chips.appendChild(chip);
  });
  el.count.textContent = String(selectedTracks.size);
}

export function openPlaylistEditModal(pl){
  resetForm();
  el.title && (el.title.value = pl.title || '');
  el.desc  && (el.desc.value  = pl.description || pl.desc || '');
  if (el.coverPrev){
    if (pl.cover_url){ el.coverPrev.src = pl.cover_url; el.coverPrev.style.display='block'; }
    else { el.coverPrev.src=''; el.coverPrev.style.display='none'; }
  }
  if (Array.isArray(pl.tracks)){
    pl.tracks.forEach(t=>{
      const id = String(t.id ?? t.track_id ?? '');
      if (!id) return;
      selectedTracks.set(id, { id, name: t.name ?? t.title ?? '', artistid: t.artistid ?? t.artist ?? '' });
    });
    updateSelectedChips();
  }
  if (el.form){
    el.form.dataset.editId = String(pl.id);
    const btn = el.form.querySelector('[type="submit"]');
    btn && (btn.textContent = 'Save changes', btn.classList.add('saving-as-edit'));
  }
  el.modal && (el.modal.style.display = 'flex');
}

async function loadPlaylistsFromServer(){
  try{
    const data = await PlaylistsAPI.list();
    const items = data.items || data.playlists || data.data || [];
    playlists = items.map(p => ({
      id: String(p?.id ?? p?.pk ?? ''),
      title: p?.title ?? p?.name ?? '',
      cover_url: p?.cover_url ?? p?.cover ?? p?.cover_image_url ?? '',
      tracks: Array.isArray(p?.tracks) ? p.tracks : [],
      tracks_count: Number(p?.tracks_count ?? (Array.isArray(p?.tracks) ? p.tracks.length : 0)) || 0,
    }));
    saveLocal(); renderPlaylistsGrid();
  }catch{
    loadLocal(); renderPlaylistsGrid();
  }
}

function bindGridClicks(){
  el.grid?.addEventListener('click', (e)=>{
    const editBtn = e.target.closest('.pl-edit');
    const delBtn  = e.target.closest('.pl-del');
    const card    = e.target.closest('.pl-card');
    if (!card) return;
    const id = card.dataset.id;
    if (editBtn) {
      const pl = playlists.find(p => String(p.id) === String(id));
      if (pl) openPlaylistEditModal(pl);
    } else if (delBtn) {
      deletePlaylist(id);
    }
  });
}

async function deletePlaylist(id){
  if (!id) return;
  if (!confirm('Удалить плейлист?')) return;
  try{
    const d = await PlaylistsAPI.delete(id);
    if (!d?.success) throw new Error(d?.error || 'Delete error');
    playlists = playlists.filter(p => String(p.id) !== String(id));
    saveLocal(); renderPlaylistsGrid();
  }catch(e){ console.error(e); alert(e.message || 'Network error'); }
}

function bindForm(){
  el.cover?.addEventListener('change', ()=>{
    const f = el.cover.files?.[0];
    if(!f){ el.coverPrev && (el.coverPrev.src='', el.coverPrev.style.display='none'); return; }
    const url = URL.createObjectURL(f); el.coverPrev && (el.coverPrev.src=url, el.coverPrev.style.display='block');
  });

  const searchDeb = debounce(async ()=>{
    if (!el.results) return;
    const q = (el.search?.value || '').trim();
    // простой локальный поиск не делаем здесь; обычно подгружают с API треков
    // оставим контейнер на усмотрение хоста — можно прокинуть список треков извне
  }, 250);
  el.search?.addEventListener('input', searchDeb);

  el.form?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const title = (el.title?.value || '').trim();
    if (!title) return alert('Enter playlist title');

    const fd = new FormData();
    fd.append('title', title);
    fd.append('description', (el.desc?.value || '').trim());
    if (selectedTracks.size) fd.append('tracks_json', JSON.stringify(Array.from(selectedTracks.values())));
    if (el.cover?.files?.[0]) fd.append('cover', el.cover.files[0]);

    const editId = el.form.dataset?.editId || null;
    try{
      const d = editId ? await PlaylistsAPI.update(editId, fd) : await PlaylistsAPI.create(fd);
      if (!d?.success) throw new Error(d?.error || 'Save error');
      await loadPlaylistsFromServer();
      closePlaylistCreateModal();
    }catch(e){ console.error(e); alert(e.message || 'Save error'); }
  });
}

export function initPlaylistsUI(){
  el.btnNew?.addEventListener('click', openPlaylistCreateModal);
  el.close?.addEventListener('click', closePlaylistCreateModal);
  el.cancel?.addEventListener('click', closePlaylistCreateModal);
  bindForm(); bindGridClicks();
  loadLocal(); renderPlaylistsGrid(); loadPlaylistsFromServer();
}

if (typeof window !== 'undefined') {
  Object.assign(window, { initPlaylistsUI, renderPlaylistsGrid, openPlaylistCreateModal, closePlaylistCreateModal });
}
