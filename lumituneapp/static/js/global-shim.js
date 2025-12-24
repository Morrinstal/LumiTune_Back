// static/js/compat/global-shim.js
// Делает бридж для старых inline-обработчиков и кнопок

(async () => {
  try {
    const tracks     = await import('./features/tracks.js');
    const playlists  = await import('./features/playlists.js');
    const audiobooks = await import('./features/audiobooks.js');
    const podcasts   = await import('./features/podcasts.js');
    const customers  = await import('./features/customers.js');
    const duration   = await import('./core/duration.js');

    // ===== TRACKS (грид, CRUD, модалки, плеер) =====
    Object.assign(window, {
      openModal: tracks.openModal,
      closeModal: tracks.closeModal,
      editTrack: tracks.editTrack,
      deleteTrack: tracks.deleteTrack,
      playTrack: tracks.playTrack,
      setAdult: tracks.setAdult,
      bulkDeleteSelected: tracks.bulkDeleteSelected,
      showTracksSection: tracks.showTracksSection,
      loadByField: tracks.loadByField,          // для Elements → albums/genres/tags/authors
    });

    // ===== PLAYLISTS (грид + модалка) =====
    Object.assign(window, {
      openPlaylistCreateModal: playlists.openPlaylistCreateModal,
      closePlaylistCreateModal: playlists.closePlaylistCreateModal,
      deletePlaylist: playlists.deletePlaylist,
      // опционально:
      openPlaylistEditModal: playlists.openPlaylistEditModal,
    });

    // ===== AUDIOBOOKS =====
    Object.assign(window, {
      openAudiobookCreateModal: audiobooks.openAudiobookCreateModal,
      closeAudiobookCreateModal: audiobooks.closeAudiobookCreateModal,
      startEditAudiobook: audiobooks.startEditAudiobook,
      deleteAudiobook: audiobooks.deleteAudiobook,
      bulkDeleteAudiobooks: audiobooks.bulkDeleteAudiobooks,
    });

    // ===== PODCASTS =====
    Object.assign(window, {
      openPodcastCreateModal: podcasts.openPodcastCreateModal,
      closePodcastCreateModal: podcasts.closePodcastCreateModal,
      startEditPodcast: podcasts.startEditPodcast,
      deletePodcast: podcasts.deletePodcast,
      bulkDeletePodcasts: podcasts.bulkDeletePodcasts,
    });

    // ===== CUSTOMERS =====
    Object.assign(window, {
      openCustomerCreateModal: customers.openCustomerCreateModal,
      closeCustomerCreateModal: customers.closeCustomerCreateModal,
      openCustomerEditModal: customers.openCustomerEditModal,
      closeCustomerEditModal: customers.closeCustomerEditModal,
      deleteCustomer: customers.deleteCustomer,
      bulkDeleteCustomers: customers.bulkDeleteCustomers,
    });

    // ===== Duration helper (если кто-то дергает напрямую) =====
    window.ensureTrackDuration = duration.ensureTrackDuration;

  } catch (e) {
    console.error('[global-shim] init failed:', e);
  }
})();
