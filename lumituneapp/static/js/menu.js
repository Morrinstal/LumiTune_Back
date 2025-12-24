// ui/menu.js
// Сайдбар/меню: раскрытие Elements, переходы, делегирование кликов.

export function initSideMenus(){
  // Кнопка “Elements” (убрали inline из html)
  const exp = document.querySelector('.menu-item.expandable');
  const submenu = document.getElementById('elements');
  if (exp && submenu){
    exp.addEventListener('click', (e) => {
      e.preventDefault();
      exp.classList.toggle('open');
      submenu.classList.toggle('open');
    });
  }

  // Делегирование кликов по подпунктам Elements
  document.addEventListener('click', async (e) => {
    const el = e.target.closest('#elements .menu-item');
    if (!el) {
      // Отдельно: New Item (плейлист)
      const newPl = e.target.closest('#btn-new-playlist');
      if (newPl){
        e.preventDefault();
        const { openPlaylistCreateModal } = await import('../features/playlists.js');
        openPlaylistCreateModal?.();
      }
      return;
    }

    e.preventDefault();

    // Активное состояние
    document.querySelectorAll('#elements .menu-item').forEach(x => x.classList.remove('active'));
    el.classList.add('active');

    // Простые секции с hash
    if (el.id === 'nav-playlists' || el.id === 'nav-audiobooks' || el.id === 'nav-podcasts'){
      location.hash = '#' + el.id.replace('nav-','');
      return;
    }
    if (el.id === 'nav-tracks'){
      location.hash = '#tracks';
      return;
    }

    // Группы каталога: albumid / genreid / tagid / artistid
    const by = el.dataset.by;
    if (by){
      const { showTracksSection, loadByField } = await import('../features/tracks.js');
      const q = (document.getElementById('searchInput')?.value || '').trim();

      if (location.hash.toLowerCase() !== '#tracks'){
        // дождёмся смены хэша и подгрузки секции, затем загрузим группу
        const onHash = () => {
          window.removeEventListener('hashchange', onHash);
          showTracksSection?.();
          loadByField?.(by, '', q);
        };
        window.addEventListener('hashchange', onHash, { once: true });
        location.hash = '#tracks';
      } else {
        showTracksSection?.();
        loadByField?.(by, '', q);
      }
    }
  });

  // Верхние пункты: Dashboard / Customers
  document.getElementById('nav-dashboard')?.addEventListener('click', (e) => {
    e.preventDefault();
    location.hash = '#dashboard';
  });
  document.getElementById('nav-customers')?.addEventListener('click', (e) => {
    e.preventDefault();
    location.hash = '#customers';
  });
}
