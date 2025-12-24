// main.js — единая точка входа
import { init as initRouter, initSideMenus } from './router.js';

// если нужны полифилы/глобальные шими — подключи их отдельной строкой:
// import './global-shim.js';

document.addEventListener('DOMContentLoaded', () => {
  initSideMenus();   // боковое меню (Elements и т.д.)
  initRouter();      // запуск роутера (лениво подтянет features/tracks.js)

  // Быстрые действия (кнопки на дашборде)
  const qa = {
    'qa-upload-track': async () => {
      const mod = await import('./features/tracks.js');
      mod.openModal?.();
    },
    'qa-new-ab': async () => {
      location.hash = '#audiobooks';
      const mod = await import('./features/audiobooks.js');
      document.getElementById('audiobookCreateModal')?.style && (document.getElementById('audiobookCreateModal').style.display = 'flex');
    },
    'qa-new-pc': async () => {
      location.hash = '#podcasts';
      await import('./features/podcasts.js');
      document.getElementById('podcastCreateModal')?.style && (document.getElementById('podcastCreateModal').style.display = 'flex');
    },
    'qa-new-pl': async () => {
      location.hash = '#playlists';
      const mod = await import('./features/playlists.js');
      mod.openPlaylistCreateModal?.();
    },
  };

  Object.entries(qa).forEach(([id, handler]) => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', (e) => { e.preventDefault(); handler().catch(console.error); });
  });
});
