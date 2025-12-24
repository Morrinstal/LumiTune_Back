// router.js
// SPA: hash-маршрутизация + ленивые импорты секций

const SECTION_IDS = {
  dashboard: 'dash-overview',
  tracks: 'dashboard-section',
  customers: 'customers-section',
  playlists: 'playlists-section',
  audiobooks: 'audiobooks-section',
  podcasts: 'podcasts-section',
  moods: 'moods-section',
};

const initFlags = new Map(); // section -> bool

function getSectionEl(name){ const id = SECTION_IDS[name]; return id ? document.getElementById(id) : null; }
function hideAll(){ Object.values(SECTION_IDS).forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; }); }
function show(name){ hideAll(); const el = getSectionEl(name); if (el) el.style.display = 'block'; }

function normalizedHash(){
  const h = (location.hash || '').toLowerCase().replace('#','');
  if (!h) return 'tracks';
  if (h in SECTION_IDS) return h;
  if (h === 'overview' || h === 'home') return 'dashboard';
  return 'tracks';
}

async function ensureInit(name, initFn){
  if (initFlags.get(name)) return;
  await initFn();
  initFlags.set(name, true);
}

export async function route(){
  const h = normalizedHash();

  switch (h) {
    case 'dashboard': {
      const mod = await import('./features/dashboard.js');
      await ensureInit('dashboard', async () => mod.initDashboardUI?.());
      await mod.loadDashboard?.();
      show('dashboard');
      break;
    }
    case 'customers': {
      const mod = await import('./features/customers.js');
      await ensureInit('customers', async () => mod.initCustomersUI?.());
      await mod.loadCustomers?.();
      show('customers');
      break;
    }
    case 'playlists': {
      const mod = await import('./features/playlists.js');
      await ensureInit('playlists', async () => mod.initPlaylistsUI?.());
      show('playlists');
      break;
    }
    case 'audiobooks': {
      const mod = await import('./features/audiobooks.js');
      await ensureInit('audiobooks', async () => mod.initAudiobooksUI?.());
      await mod.loadAudiobooks?.();
      show('audiobooks');
      break;
    }
    case 'podcasts': {
      const mod = await import('./features/podcasts.js');
      await ensureInit('podcasts', async () => mod.initPodcastsUI?.());
      await mod.loadPodcasts?.();
      show('podcasts');
      break;
    }
    case 'moods': {
      show('moods');
      break;
    }
    case 'tracks':
    default: {
      const mod = await import('./features/tracks.js');
      await ensureInit('tracks', async () => mod.initTracksUI?.());
      await mod.loadTracks?.();
      show('tracks');
      break;
    }
  }
}

// Боковые меню (Elements и т.д.) — держим здесь, без отдельного menu.js
export function initSideMenus() {
  const exp = document.querySelector('.menu-item.expandable');
  const submenu = document.getElementById('elements');
  if (exp && submenu) {
    exp.addEventListener('click', (e) => {
      e.preventDefault();
      exp.classList.toggle('open');
      submenu.classList.toggle('open');
    });
  }

  document.addEventListener('click', async (e) => {
    const el = e.target.closest('#elements .menu-item');
    if (el) {
      e.preventDefault();
      document.querySelectorAll('#elements .menu-item').forEach(x=>x.classList.remove('active'));
      el.classList.add('active');

      if (el.id === 'nav-playlists' || el.id === 'nav-audiobooks' || el.id === 'nav-podcasts') {
        location.hash = '#' + el.id.replace('nav-','');
        return;
      }
      if (el.id === 'nav-tracks') { location.hash = '#tracks'; return; }

      // albumid/genreid/tagid/artistid группы
      const by = el.dataset.by;
      if (by) {
        const { showTracksSection, loadByField } = await import('./features/tracks.js');
        const q = (document.getElementById('searchInput')?.value || '').trim();
        if (location.hash.toLowerCase() !== '#tracks') {
          const onHash = () => { window.removeEventListener('hashchange', onHash); showTracksSection(); loadByField(by, '', q); };
          window.addEventListener('hashchange', onHash, { once: true });
          location.hash = '#tracks';
        } else {
          showTracksSection();
          loadByField(by, '', q);
        }
        return;
      }
    }

    // "New Item" → модалка плейлиста
    const newPl = e.target.closest('#btn-new-playlist');
    if (newPl) {
      e.preventDefault();
      const { openPlaylistCreateModal } = await import('./features/playlists.js');
      openPlaylistCreateModal?.();
    }
  });

  document.getElementById('nav-dashboard')?.addEventListener('click', (e) => { e.preventDefault(); location.hash = '#dashboard'; });
  document.getElementById('nav-customers')?.addEventListener('click', (e) => { e.preventDefault(); location.hash = '#customers'; });
}

export function navigateTo(hash){
  const h = hash.startsWith('#') ? hash : `#${hash}`;
  if (location.hash.toLowerCase() === h.toLowerCase()) route();
  else location.hash = h;
}

export function init(){
  if (!location.hash) location.hash = '#tracks';

  // Ненавязчиво перехватываем только <a href="#...">
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const dest = (a.getAttribute('href') || '').trim();
    if (!dest) return;
    e.preventDefault();
    navigateTo(dest);
  });

  window.addEventListener('hashchange', route);
  route();
}

// удобный доступ из консоли
if (typeof window !== 'undefined') window.appRouter = { init, route, navigateTo };
