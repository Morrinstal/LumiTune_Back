// core/api.js
// fetchJSON + константы эндпоинтов + тонкие обёртки API

import { getCookie } from './utils.js';

export const ENDPOINTS = {
  dashboard: '/api/dashboard',
  tracks:    '/api/get_tracks/',
  trackUpdate: (id) => `/api/update_track/${encodeURIComponent(id)}/`,
  trackDelete: (id) => `/api/delete_track/${encodeURIComponent(id)}/`,
  tracksBulkDelete: '/api/bulk_delete_tracks/',
  customers: '/api/customers/',
  customersCreate: '/api/customers/create/',
  customersUpdate: (id) => `/api/customers/update/${encodeURIComponent(id)}/`,
  customersDelete: (id) => `/api/customers/delete/${encodeURIComponent(id)}/`,
  customersBulkDelete: '/api/customers/bulk_delete/',
  playlists: '/api/playlists/',
  playlistCreate: '/api/playlists/create/',
  playlistUpdate: (id) => `/api/playlists/update/${encodeURIComponent(id)}/`,
  playlistDelete: (id) => `/api/playlists/delete/${encodeURIComponent(id)}/`,
  audiobooks: '/api/audiobooks/',
  audiobookCreate: '/api/audiobooks/create/',
  audiobookUpdate: (id) => `/api/audiobooks/update/${encodeURIComponent(id)}/`,
  audiobookDelete: (id) => `/api/audiobooks/delete/${encodeURIComponent(id)}/`,
  audiobooksBulkDelete: '/api/audiobooks/bulk_delete/',
  podcasts: '/api/podcasts/',
  podcastCreate: '/api/podcasts/create/',
  podcastUpdate: (id) => `/api/podcasts/update/${encodeURIComponent(id)}/`,
  podcastDelete: (id) => `/api/podcasts/delete/${encodeURIComponent(id)}/`,
  podcastsBulkDelete: '/api/podcasts/bulk_delete/',
};

/** собрать query string из объекта, игнорируя null/undefined/"" */
export function toQuery(params = {}) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === null || v === undefined || v === '') return;
    p.set(k, String(v));
  });
  const q = p.toString();
  return q ? `?${q}` : '';
}

/** безопасный fetch JSON с XHR-флагом и CSRF для методов записи */
export async function fetchJSON(url, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  const isWrite = !['GET', 'HEAD', 'OPTIONS'].includes(method);
  const headers = new Headers(opts.headers || {});
  headers.set('X-Requested-With', 'XMLHttpRequest');

  // если тело — не FormData, сериализуем в JSON автоматически (по желанию)
  let body = opts.body;
  if (isWrite) {
    const token = getCookie('csrftoken');
    if (token) headers.set('X-CSRFToken', token);
    if (body && !(body instanceof FormData) && typeof body === 'object') {
      headers.set('Content-Type', 'application/json');
      body = JSON.stringify(body);
    }
  }

  const res = await fetch(url, {
    credentials: 'same-origin',
    ...opts,
    method,
    headers,
    body
  });

  // попытка прочитать JSON/текст для понятной ошибки
  let data;
  try { data = await res.json(); }
  catch { data = null; }

  if (!res.ok) {
    const msg = data?.error || `${res.status} ${res.statusText}`;
    throw new Error(`HTTP ${res.status} at ${url}: ${msg}`);
  }
  return data;
}

/* ===== Dashboard wrappers ===== */
export const DashboardAPI = {
  summary: ({ start, end } = {}) =>
    fetchJSON(`${ENDPOINTS.dashboard}/summary/${toQuery({ start, end })}`),

  timeseries: ({ metric, object, start, end }) =>
    fetchJSON(`${ENDPOINTS.dashboard}/timeseries/${toQuery({ metric, object, start, end })}`),

  top: ({ object, limit = 10, start, end }) =>
    fetchJSON(`${ENDPOINTS.dashboard}/top/${toQuery({ object, limit, start, end })}`),

  recent: () => fetchJSON(`${ENDPOINTS.dashboard}/recent/`),
  moderation: () => fetchJSON(`${ENDPOINTS.dashboard}/moderation/`),
};

/* ===== Tracks wrappers ===== */
export const TracksAPI = {
  list: (params) => fetchJSON(`${ENDPOINTS.tracks}${toQuery(params)}`),
  update: (id, payload /* FormData | object */) =>
    fetchJSON(ENDPOINTS.trackUpdate(id), { method: 'POST', body: payload }),
  delete: (id) =>
    fetchJSON(ENDPOINTS.trackDelete(id), { method: 'DELETE' }),
  bulkDelete: (ids) =>
    fetchJSON(ENDPOINTS.tracksBulkDelete, { method: 'POST', body: { ids } }),
};

/* ===== Customers wrappers ===== */
export const CustomersAPI = {
  list: (params) => fetchJSON(`${ENDPOINTS.customers}${toQuery(params)}`),
  create: (payload) => fetchJSON(ENDPOINTS.customersCreate, { method: 'POST', body: payload }),
  update: (id, payload) => fetchJSON(ENDPOINTS.customersUpdate(id), { method: 'POST', body: payload }),
  delete: (id) => fetchJSON(ENDPOINTS.customersDelete(id), { method: 'DELETE' }),
  bulkDelete: (ids) => fetchJSON(ENDPOINTS.customersBulkDelete, { method: 'POST', body: { ids } }),
};

/* ===== Playlists wrappers ===== */
export const PlaylistsAPI = {
  list: () => fetchJSON(ENDPOINTS.playlists),
  create: (payload) => fetchJSON(ENDPOINTS.playlistCreate, { method: 'POST', body: payload }),
  update: (id, payload) => fetchJSON(ENDPOINTS.playlistUpdate(id), { method: 'POST', body: payload }),
  delete: (id) => fetchJSON(ENDPOINTS.playlistDelete(id), { method: 'DELETE' }),
};

/* ===== Audiobooks wrappers ===== */
export const AudiobooksAPI = {
  list: (params) => fetchJSON(`${ENDPOINTS.audiobooks}${toQuery(params)}`),
  create: (payload) => fetchJSON(ENDPOINTS.audiobookCreate, { method: 'POST', body: payload }),
  update: (id, payload) => fetchJSON(ENDPOINTS.audiobookUpdate(id), { method: 'POST', body: payload }),
  delete: (id) => fetchJSON(ENDPOINTS.audiobookDelete(id), { method: 'DELETE' }),
  bulkDelete: (ids) => fetchJSON(ENDPOINTS.audiobooksBulkDelete, { method: 'POST', body: { ids } }),
};

/* ===== Podcasts wrappers ===== */
export const PodcastsAPI = {
  list: (params) => fetchJSON(`${ENDPOINTS.podcasts}${toQuery(params)}`),
  create: (payload) => fetchJSON(ENDPOINTS.podcastCreate, { method: 'POST', body: payload }),
  update: (id, payload) => fetchJSON(ENDPOINTS.podcastUpdate(id), { method: 'POST', body: payload }),
  delete: (id) => fetchJSON(ENDPOINTS.podcastDelete(id), { method: 'DELETE' }),
  bulkDelete: (ids) => fetchJSON(ENDPOINTS.podcastsBulkDelete, { method: 'POST', body: { ids } }),
};

// экспорт в window для совместимости
if (typeof window !== 'undefined') {
  Object.assign(window, {
    toQuery, fetchJSON, ENDPOINTS,
    DashboardAPI, TracksAPI, CustomersAPI,
    PlaylistsAPI, AudiobooksAPI, PodcastsAPI
  });
}
