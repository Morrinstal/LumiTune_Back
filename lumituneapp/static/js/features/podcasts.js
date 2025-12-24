// features/podcasts.js
// список / CRUD / проигрывание

import { debounce } from '../core/utils.js';
import { PodcastsAPI } from '../core/api.js';
import { ensureTrackDuration } from '../core/duration.js';
import { player, refreshPlayButtons } from './tracks.js';

let state = { items: [], page: 1, perPage: 7, totalPages: 1, q: '' };
let currentIndex = null;

const el = {
  tbody: document.getElementById('podcasts-tbody'),
  pager: document.getElementById('podcasts-pagination'),
  selAll: document.getElementById('select-all-podcasts'),
  search: document.getElementById('searchPodcastInput'),
  // modals
  createBtn: document.getElementById('btn-open-create-podcast'),
  createModal: document.getElementById('podcastCreateModal'),
  editModal: document.getElementById('podcastEditModal'),
  createForm: document.getElementById('podcastCreateForm'),
  editForm: document.getElementById('podcastEditForm'),
};

function renderPager(container, current, total, onGoto, withBulk = true) {
  const has = total > 1;
  const btn = (p, t=p, d=false, a=false)=>`<button class="page-btn${a?' active':''}" data-goto="${p}" ${d?'disabled':''}>${t}</button>`;
  let html = `<div class="page-numbers">`;
  if (has) {
    const win=5; let s=Math.max(1,current-Math.floor(win/2)), e=Math.min(total,s+win-1); s=Math.max(1,e-win+1);
    html += btn(Math.max(1,current-1),'◀',current===1);
    if(s>1){ html+=btn(1,'1'); if(s>2) html+=`<button class="page-btn" disabled>…</button>`; }
    for(let p=s;p<=e;p++) html+=btn(p,String(p),false,p===current);
    if(e<total){ if(e<total-1) html+=`<button class="page-btn" disabled>…</button>`; html+=btn(total,String(total)); }
    html += btn(Math.min(total,current+1),'▶',current===total);
  }
  html += `</div><button type="button" class="delete-selected-btn">Delete Selected</button>`;
  container.innerHTML = html; container.style.display = 'flex';
  container.querySelectorAll('.page-btn[data-goto]').forEach(b => b.addEventListener('click', ()=>{ const p=+b.dataset.goto; if(p && p!==current) onGoto(p); }));
  container.querySelector('.delete-selected-btn')?.addEventListener('click', bulkDeletePodcasts);
}

export function renderPodcasts(list){
  const tb = el.tbody; if(!tb) return;
  tb.innerHTML = '';
  (list||[]).forEach((pc, index)=>{
    const src = (pc.audio_url && pc.audio_url.length ? pc.audio_url : '');
    const tr = document.createElement('tr');
    tr.dataset.id = pc.id;
    tr.innerHTML = `
      <td><input type="checkbox" class="row-select" data-id="${pc.id}"></td>
      <td class="pc-name">${pc.name||''}</td>
      <td>${pc.artistid||''}</td>
      <td>${pc.albumid||''}</td>
      <td>${pc.genreid||''}</td>
      <td>${pc.tagsid||''}</td>
      <td>${pc.seqnum||''}</td>
      <td>${pc.playsnum||0}</td>
      <td class="col-adult"><input type="checkbox" class="adult-toggle" ${pc.adult?'checked':''} onchange="setPodcastAdult('${pc.id}', this)"></td>
      <td>${pc.id}</td>
      <td class="col-time">${pc.time||'0:00'}</td>
      <td>
        <button class="action-btn pc-play-btn" data-src="${src}" onclick="playPC(${index}, this)" title="Play/Pause">
          <img src="/media/iconsLuniTune/Group 132.png" width="16" height="16">
        </button>
      </td>
      <td>
        <button class="action-btn" onclick="startEditPodcast('${pc.id}')"><img src="/media/iconsLuniTune/edit.png" width="16" height="16"> Edit</button>
        <button class="action-btn delete-btn" onclick="deletePodcast('${pc.id}')"><img src="/media/iconsLuniTune/close.png" width="16" height="16"> Delete</button>
      </td>`;
    tb.appendChild(tr);

    const timeCell = tr.querySelector('.col-time');
    if (timeCell && src && (!pc.time || pc.time === '0:00')) ensureTrackDuration({id: pc.id, time: pc.time}, src, timeCell);
  });
  el.selAll && (el.selAll.checked = false);
}

export async function loadPodcasts(){
  const d = await PodcastsAPI.list({ q: state.q, page: state.page, page_size: state.perPage });
  state.items = d.items || [];
  state.page = d.page || 1;
  state.perPage = d.page_size || state.perPage;
  state.totalPages = d.total_pages || Math.max(1, Math.ceil((d.total || state.items.length)/state.perPage));
  renderPodcasts(state.items);
  renderPager(el.pager, state.page, state.totalPages, p=>{ state.page = p; loadPodcasts(); }, true);
}

export async function setPodcastAdult(id, checkbox){
  const value = checkbox.checked;
  try{
    const fd = new FormData(); fd.append('adult', value ? 'true' : 'false');
    const d = await PodcastsAPI.update(id, fd);
    if (!d?.success) throw new Error(d?.error || 'Update error');
  }catch(e){ console.error(e); checkbox.checked = !value; }
}

export function playPC(i, btn){
  const src = btn.dataset.src;
  if (!src){ alert('No audio'); return; }
  if (currentIndex === i && !player.paused){ player.pause(); return; }
  if (player.src !== src) player.src = src;
  player.play().then(()=>{ currentIndex = i; }).catch(console.error);
}

export function startEditPodcast(id){
  const u = state.items.find(x => String(x.id) === String(id));
  if (!u) return;
  document.getElementById('pce_id').value = u.id;
  document.getElementById('pce_title').value = u.name || '';
  document.getElementById('pce_show').value = u.artistid || '';
  document.getElementById('pce_host').value = u.albumid || '';
  document.getElementById('pce_genreid').value = u.genreid || '';
  document.getElementById('pce_tagsid').value = u.tagsid || '';
  document.getElementById('pce_episode').value = u.seqnum || '';
  document.getElementById('pce_info').value = u.info || '';
  el.editModal && (el.editModal.style.display = 'flex');
}

export async function deletePodcast(id){
  if (!confirm('Delete this episode?')) return;
  const d = await PodcastsAPI.delete(id);
  if (!d?.success) return alert(d?.error || 'Delete error');
  loadPodcasts();
}

export async function bulkDeletePodcasts(){
  const ids = Array.from(document.querySelectorAll('#podcasts-tbody .row-select:checked')).map(cb => cb.dataset.id || cb.closest('tr')?.dataset.id).filter(Boolean);
  if (!ids.length) return alert('Выберите хотя бы один эпизод.');
  if (!confirm(`Удалить выбранные (${ids.length})?`)) return;
  const d = await PodcastsAPI.bulkDelete(ids);
  if (!d?.success) return alert(d?.error || 'Bulk delete error');
  loadPodcasts();
}

export function initPodcastsUI(){
  const run = debounce(()=>{ state.page=1; state.q=(el.search?.value||'').trim(); loadPodcasts(); }, 300);
  el.search?.addEventListener('input', run);
  el.selAll?.addEventListener('change', function(){ document.querySelectorAll('#podcasts-tbody .row-select').forEach(cb => cb.checked = this.checked); });
  document.getElementById('btn-open-create-podcast')?.addEventListener('click', ()=>{ el.createModal && (el.createModal.style.display='flex'); });
  document.getElementById('podcastCreateForm')?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const fd = new FormData();
    fd.append('title', (document.getElementById('pc_title').value||'').trim());
    fd.append('show', (document.getElementById('pc_show').value||'').trim());
    fd.append('host', (document.getElementById('pc_host').value||'').trim());
    fd.append('genreid', (document.getElementById('pc_genreid').value||'').trim());
    fd.append('tagsid', (document.getElementById('pc_tagsid').value||'').trim());
    fd.append('episode', (document.getElementById('pc_episode').value||'').trim());
    fd.append('info', (document.getElementById('pc_info').value||'').trim());
    const af = document.getElementById('pc_audio')?.files?.[0];
    const cf = document.getElementById('pc_cover')?.files?.[0];
    if (af) fd.append('audio_file', af);
    if (cf) fd.append('cover_image', cf);
    const d = await PodcastsAPI.create(fd);
    if (!d?.success) return alert(d?.error || 'Create error');
    el.createModal && (el.createModal.style.display='none'); state.page=1; loadPodcasts();
  });
  document.getElementById('podcastEditForm')?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const id = document.getElementById('pce_id').value;
    const fd = new FormData();
    fd.append('title', (document.getElementById('pce_title').value||'').trim());
    fd.append('show', (document.getElementById('pce_show').value||'').trim());
    fd.append('host', (document.getElementById('pce_host').value||'').trim());
    fd.append('genreid', (document.getElementById('pce_genreid').value||'').trim());
    fd.append('tagsid', (document.getElementById('pce_tagsid').value||'').trim());
    fd.append('episode', (document.getElementById('pce_episode').value||'').trim());
    fd.append('info', (document.getElementById('pce_info').value||'').trim());
    const af = document.getElementById('pce_audio')?.files?.[0];
    const cf = document.getElementById('pce_cover')?.files?.[0];
    if (af) fd.append('audio_file', af);
    if (cf) fd.append('cover_image', cf);
    const d = await PodcastsAPI.update(id, fd);
    if (!d?.success) return alert(d?.error || 'Update error');
    el.editModal && (el.editModal.style.display='none'); loadPodcasts();
  });
}

if (typeof window !== 'undefined') {
  Object.assign(window, { initPodcastsUI, loadPodcasts, renderPodcasts, playPC, setPodcastAdult, deletePodcast, bulkDeletePodcasts });
}
