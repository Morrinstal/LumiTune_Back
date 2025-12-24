// features/customers.js
// клиенты + CRUD + фильтры + пагинация

import { debounce, getCookie } from '../core/utils.js';
import { CustomersAPI } from '../core/api.js';

let state = { items: [], page: 1, perPage: 7, totalPages: 1, q: '', filters: { role: '' } };

const el = {
  tbody: document.getElementById('customers-tbody'),
  pager: document.getElementById('customers-pagination'),
  search: document.getElementById('searchCustomerInput'),
  selAll: document.getElementById('select-all-customers'),
  // modals
  createBtn: document.getElementById('btn-open-create-customer'),
  createModal: document.getElementById('customerCreateModal'),
  editModal: document.getElementById('customerEditModal'),
  createForm: document.getElementById('customerCreateForm'),
  editForm: document.getElementById('customerEditForm'),
  // filters popover (simple)
  filterRole: document.getElementById('filterRole'),
};

function renderPager(container, current, total, onGoto, withBulk = true) {
  const has = total > 1;
  let html = `<div class="page-numbers">`;
  const btn = (p, t=p, d=false, a=false)=>`<button class="page-btn${a?' active':''}" data-goto="${p}" ${d?'disabled':''}>${t}</button>`;
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
  container.querySelector('.delete-selected-btn')?.addEventListener('click', bulkDeleteCustomers);
}

function selectedIds(){
  return Array.from(document.querySelectorAll('#customers-tbody .row-select:checked')).map(cb => cb.dataset.id || cb.closest('tr')?.dataset.id).filter(Boolean);
}

function roleFromFlags(u){ if(u.is_admin) return 'admin'; if(u.is_staff) return 'staff'; return 'client'; }

export function renderCustomers(list){
  const tb = el.tbody; if(!tb) return;
  tb.innerHTML = '';
  (list||[]).forEach(u=>{
    const tr = document.createElement('tr'); tr.dataset.id = u.id;
    tr.innerHTML = `
      <td><input type="checkbox" class="row-select" data-id="${u.id}"></td>
      <td>${(u.full_name || u.username || '').toString()}</td>
      <td>${u.email || ''}</td>
      <td>${(u.role || roleFromFlags(u) || '').replace(/^./, s=>s.toUpperCase())}</td>
      <td>
        <button class="action-btn" onclick="startEditCustomer('${u.id}')"><img src="/media/iconsLuniTune/edit.png" width="16" height="16"> Edit</button>
        <button class="action-btn delete-btn" onclick="deleteCustomer('${u.id}')"><img src="/media/iconsLuniTune/close.png" width="16" height="16"> Delete</button>
      </td>
    `;
    tb.appendChild(tr);
  });
}

export async function loadCustomers(){
  try{
    const d = await CustomersAPI.list({ q: state.q, page: state.page, page_size: state.perPage, role: state.filters.role || '' });
    state.items = d.items || [];
    state.page = d.page || state.page;
    state.perPage = d.page_size || state.perPage;
    state.totalPages = d.total_pages || Math.max(1, Math.ceil((d.total || state.items.length) / state.perPage));
    renderCustomers(state.items);
    renderPager(el.pager, state.page, state.totalPages, p=>{ state.page = p; loadCustomers(); }, true);
    el.selAll && (el.selAll.checked = false);
  }catch(e){ console.error(e); }
}

export function startEditCustomer(id){
  const u = state.items.find(x => String(x.id) === String(id));
  if(!u) return;
  document.getElementById('e_id').value = u.id;
  document.getElementById('e_full_name').value = u.full_name || u.username || '';
  document.getElementById('e_email').value = u.email || '';
  document.getElementById('e_role').value = u.role || roleFromFlags(u);
  document.getElementById('e_password').value = '';
  document.getElementById('e_password2').value = '';
  el.editModal && (el.editModal.style.display = 'flex');
}

export async function deleteCustomer(id){
  if(!confirm('Delete this customer?')) return;
  try{ const d = await CustomersAPI.delete(id); if(!d?.success) throw new Error(d?.error||'Delete error'); loadCustomers(); }
  catch(e){ console.error(e); alert(e.message || 'Delete error'); }
}

export async function bulkDeleteCustomers(){
  const ids = selectedIds();
  if(!ids.length) return alert('Выберите хотя бы одного пользователя.');
  if(!confirm(`Удалить выбранных (${ids.length})?`)) return;
  try{ const d = await CustomersAPI.bulkDelete(ids); if(!d?.success) throw new Error(d?.error||'Bulk delete error'); loadCustomers(); }
  catch(e){ console.error(e); alert(e.message || 'Bulk delete error'); }
}

export function initCustomersUI(){
  // search
  const run = debounce(()=>{ state.page=1; state.q = (el.search?.value||'').trim(); loadCustomers(); },300);
  el.search?.addEventListener('input', run);
  el.selAll?.addEventListener('change', function(){ document.querySelectorAll('#customers-tbody .row-select').forEach(cb=> cb.checked = this.checked); });
  // create
  el.createBtn?.addEventListener('click', ()=>{ el.createModal && (el.createModal.style.display = 'flex'); });
  document.getElementById('customerCreateModalClose')?.addEventListener('click', ()=>{ el.createModal && (el.createModal.style.display='none'); });
  document.getElementById('customerEditModalClose')?.addEventListener('click', ()=>{ el.editModal && (el.editModal.style.display='none'); });
  el.createForm?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const full_name = document.getElementById('c_full_name').value.trim();
    const email = document.getElementById('c_email').value.trim();
    const role = document.getElementById('c_role').value;
    const p1 = document.getElementById('c_password').value;
    const p2 = document.getElementById('c_password2').value;
    if(p1 !== p2) return alert('Passwords do not match');
    const fd = new FormData(); fd.append('full_name', full_name); fd.append('email', email); fd.append('role', role); fd.append('password', p1);
    try{ const d = await CustomersAPI.create(fd); if(!d?.success) throw new Error(d?.error||'Create error'); el.createModal.style.display='none'; state.page=1; loadCustomers(); }
    catch(e){ console.error(e); alert(e.message || 'Create error'); }
  });
  el.editForm?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const id = document.getElementById('e_id').value;
    const full_name = document.getElementById('e_full_name').value.trim();
    const email = document.getElementById('e_email').value.trim();
    const role = document.getElementById('e_role').value;
    const p1 = document.getElementById('e_password').value;
    const p2 = document.getElementById('e_password2').value;
    if(p1 || p2){ if(p1!==p2) return alert('Passwords do not match'); }
    const fd = new FormData(); fd.append('full_name', full_name); fd.append('email', email); fd.append('role', role); if(p1) fd.append('password', p1);
    try{ const d = await CustomersAPI.update(id, fd); if(!d?.success) throw new Error(d?.error||'Update error'); el.editModal.style.display='none'; loadCustomers(); }
    catch(e){ console.error(e); alert(e.message || 'Update error'); }
  });
}

if (typeof window !== 'undefined') {
  Object.assign(window, { loadCustomers, renderCustomers, startEditCustomer, deleteCustomer, bulkDeleteCustomers, initCustomersUI });
}
