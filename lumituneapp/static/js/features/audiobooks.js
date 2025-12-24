// features/audiobooks.js
// список / CRUD / проигрывание

import { debounce } from '../core/utils.js';
import { AudiobooksAPI } from '../core/api.js';
import { ensureTrackDuration } from '../core/duration.js';
import { player, refreshPlayButtons } from './tracks.js';

let state = { items: [], page: 1, perPage: 7, totalPages: 1, q: '' };
let currentIndex = null;

const el = {
  tbody: document.getElementById('audiobooks-tbody'),
  pager: document.getElementById('audiobooks-pagination'),
  selAll: document.getElementById('select-all-audiobooks'),
  search: document.getElementById('searchAudiobookInput'),
  // modals
  createBtn: document.getElementById('btn-open-create-audiobook'),
  createModal: document.getElementById('audiobookCreateModal'),
  editModal: document.getElementById('audiobookEditModal'),
  createForm: document.getElementById('audiobookCreateForm'),
  editForm: document.getElementById('audiobookEditForm'),
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
  container.querySelector('.delete-selected-btn')?.addEventListener('click', bulkDeleteAudiobooks);
}

export function renderAudiobooks(list){
  const tb = el.tbody; if(!tb) return;
  tb.innerHTML = '';
  (list||[]).forEach((ab, index)=>{
    const src = (ab.audio_url && ab.audio_url.length ? ab.audio_url : '');
    const tr = document.createElement('tr');
    tr.dataset.id = ab.id;
    tr.innerHTML = `
      <td><input type="checkbox" class="row-select" data-id="${ab.id}"></td>
      <td class="ab-name">${ab.name||''}</td>
      <td>${ab.artistid||''}</td>
      <td>${ab.albumid||''}</td>
      <td>${ab.genreid||''}</td>
      <td>${ab.tagsid||''}</td>
      <td>${ab.seqnum||''}</td>
      <td>${ab.playsnum||0}</td>
      <td class="col-adult"><input type="checkbox" class="adult-toggle" ${ab.adult?'checked':''} onchange="setAudiobookAdult('${ab.id}', this)"></td>
      <td>${ab.id}</td>
      <td class="col-time">${ab.time||'0:00'}</td>
      <td>
        <button class="action-btn ab-play-btn" data-src="${src}" onclick="playAB(${index}, this)" title="Play/Pause">
          <img src="/media/iconsLuniTune/Group 132.png" width="16" height="16">
        </button>
      </td>
      <td>
        <button class="action-btn" onclick="startEditAudiobook('${ab.id}')"><img src="/media/iconsLuniTune/edit.png" width="16" height="16"> Edit</button>
        <button class="action-btn delete-btn" onclick="deleteAudiobook('${ab.id}')"><img src="/media/iconsLuniTune/close.png" width="16" height="16"> Delete</button>
      </td>`;
    tb.appendChild(tr);

    const timeCell = tr.querySelector('.col-time');
    if (timeCell && src && (!ab.time || ab.time === '0:00')) ensureTrackDuration({id: ab.id, time: ab.time}, src, timeCell);
  });
  el.selAll && (el.selAll.checked = false);
}

export async function loadAudiobooks(){
  const d = await AudiobooksAPI.list({ q: state.q, page: state.page, page_size: state.perPage });
  state.items = d.items || [];
  state.page = d.page || 1;
  state.perPage = d.page_size || state.perPage;
  state.totalPages = d.total_pages || Math.max(1, Math.ceil((d.total || state.items.length)/state.perPage));
  renderAudiobooks(state.items);
  renderPager(el.pager, state.page, state.totalPages, p=>{ state.page = p; loadAudiobooks(); }, true);
}

export async function setAudiobookAdult(id, checkbox){
  const value = checkbox.checked;
  try{
    const fd = new FormData(); fd.append('adult', value ? 'true' : 'false');
    const d = await AudiobooksAPI.update(id, fd);
    if (!d?.success) throw new Error(d?.error || 'Update error');
  }catch(e){ console.error(e); checkbox.checked = !value; }
}

export function playAB(i, btn){
  const src = btn.dataset.src;
  if (!src){ alert('No audio'); return; }
  if (currentIndex === i && !player.paused){ player.pause(); return; }
  if (player.src !== src) player.src = src;
  player.play().then(()=>{ currentIndex = i; }).catch(console.error);
}

export function startEditAudiobook(id){
  const u = state.items.find(x => String(x.id) === String(id));
  if (!u) return;
  document.getElementById('abe_id').value = u.id;
  document.getElementById('abe_title').value = u.name || '';
  document.getElementById('abe_author').value = u.artistid || '';
  document.getElementById('abe_narrator').value = u.albumid || '';
  document.getElementById('abe_genreid').value = u.genreid || '';
  document.getElementById('abe_tagsid').value = u.tagsid || '';
  document.getElementById('abe_seqnum').value = u.seqnum || '';
  document.getElementById('abe_info').value = u.info || '';
  el.editModal && (el.editModal.style.display = 'flex');
}

export async function deleteAudiobook(id){
  if (!confirm('Delete this audiobook?')) return;
  const d = await AudiobooksAPI.delete(id);
  if (!d?.success) return alert(d?.error || 'Delete error');
  loadAudiobooks();
}

export async function bulkDeleteAudiobooks(){
  const ids = Array.from(document.querySelectorAll('#audiobooks-tbody .row-select:checked')).map(cb => cb.dataset.id || cb.closest('tr')?.dataset.id).filter(Boolean);
  if (!ids.length) return alert('Выберите хотя бы одну аудиокнигу.');
  if (!confirm(`Удалить выбранные (${ids.length})?`)) return;
  const d = await AudiobooksAPI.bulkDelete(ids);
  if (!d?.success) return alert(d?.error || 'Bulk delete error');
  loadAudiobooks();
}

export function initAudiobooksUI(){
  const run = debounce(()=>{ state.page=1; state.q=(el.search?.value||'').trim(); loadAudiobooks(); }, 300);
  el.search?.addEventListener('input', run);
  el.selAll?.addEventListener('change', function(){ document.querySelectorAll('#audiobooks-tbody .row-select').forEach(cb => cb.checked = this.checked); });
  document.getElementById('btn-open-create-audiobook')?.addEventListener('click', ()=>{ el.createModal && (el.createModal.style.display='flex'); });
  document.getElementById('audiobookCreateForm')?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const fd = new FormData();
    fd.append('title', (document.getElementById('ab_title').value||'').trim());
    fd.append('author', (document.getElementById('ab_author').value||'').trim());
    fd.append('narrator', (document.getElementById('ab_narrator').value||'').trim());
    fd.append('genreid', (document.getElementById('ab_genreid').value||'').trim());
    fd.append('tagsid', (document.getElementById('ab_tagsid').value||'').trim());
    fd.append('seqnum', (document.getElementById('ab_seqnum').value||'').trim());
    fd.append('info', (document.getElementById('ab_info').value||'').trim());
    const af = document.getElementById('ab_audio')?.files?.[0];
    const cf = document.getElementById('ab_cover')?.files?.[0];
    if (af) fd.append('audio_file', af);
    if (cf) fd.append('cover_image', cf);
    const d = await AudiobooksAPI.create(fd);
    if (!d?.success) return alert(d?.error || 'Create error');
    el.createModal && (el.createModal.style.display='none'); state.page=1; loadAudiobooks();
  });
  document.getElementById('audiobookEditForm')?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const id = document.getElementById('abe_id').value;
    const fd = new FormData();
    fd.append('title', (document.getElementById('abe_title').value||'').trim());
    fd.append('author', (document.getElementById('abe_author').value||'').trim());
    fd.append('narrator', (document.getElementById('abe_narrator').value||'').trim());
    fd.append('genreid', (document.getElementById('abe_genreid').value||'').trim());
    fd.append('tagsid', (document.getElementById('abe_tagsid').value||'').trim());
    fd.append('seqnum', (document.getElementById('abe_seqnum').value||'').trim());
    fd.append('info', (document.getElementById('abe_info').value||'').trim());
    const af = document.getElementById('abe_audio')?.files?.[0];
    const cf = document.getElementById('abe_cover')?.files?.[0];
    if (af) fd.append('audio_file', af);
    if (cf) fd.append('cover_image', cf);
    const d = await AudiobooksAPI.update(id, fd);
    if (!d?.success) return alert(d?.error || 'Update error');
    el.editModal && (el.editModal.style.display='none'); loadAudiobooks();
  });
}

if (typeof window !== 'undefined') {
  Object.assign(window, { initAudiobooksUI, loadAudiobooks, renderAudiobooks, playAB, setAudiobookAdult, deleteAudiobook, bulkDeleteAudiobooks });
}
