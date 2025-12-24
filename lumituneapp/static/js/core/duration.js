// core/duration.js
// Получение длительности аудио + кэш в localStorage + удобная обёртка для ячеек таблиц

import { formatDuration } from './utils.js';

export const DURATION_LS_KEY = 'dash.trackDurations';

// простейший persistent-кэш (ключ -> секунды)
const _mem = (() => {
  try {
    const raw = localStorage.getItem(DURATION_LS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
})();

function _save() {
  try { localStorage.setItem(DURATION_LS_KEY, JSON.stringify(_mem)); } catch {}
}

function cacheKey(trackId, src) {
  return `${String(trackId ?? '')}::${String(src ?? '')}`;
}

export function getCachedDuration(trackId, src) {
  const k1 = cacheKey(trackId, src);
  const k2 = String(trackId ?? '');
  return _mem[k1] ?? _mem[k2];
}
export function setCachedDuration(trackId, src, seconds) {
  if (!isFinite(seconds) || seconds <= 0) return;
  _mem[cacheKey(trackId, src)] = seconds;
  if (trackId != null) _mem[String(trackId)] = seconds;
  _save();
}

/** Загружает только метадату и возвращает длительность в секундах */
export function probeDuration(src) {
  return new Promise((resolve, reject) => {
    if (!src) return reject(new Error('no src'));
    const a = new Audio();
    a.preload = 'metadata';
    a.crossOrigin = 'anonymous';
    const cleanup = () => {
      a.removeAttribute('src');
      try { a.load(); } catch {}
    };
    a.addEventListener('loadedmetadata', () => {
      const d = a.duration;
      cleanup();
      if (isFinite(d) && d > 0) resolve(d);
      else reject(new Error('no finite duration'));
    }, { once: true });
    a.addEventListener('error', () => { cleanup(); reject(new Error('audio error')); }, { once: true });
    a.src = src;
  });
}

/**
 * Универсальная обёртка:
 *  - берёт из кэша или пробует метадату
 *  - записывает в кэш
 *  - (опционально) проставляет текст в ячейку таблицы
 * @param {{id?:string|number,time?:string}} track
 * @param {string} src
 * @param {HTMLElement|null} cell
 * @returns {Promise<number|undefined>} seconds
 */
export async function ensureTrackDuration(track, src, cell) {
  if (!src) { if (cell) cell.textContent = '0:00'; return 0; }

  const cached = getCachedDuration(track?.id, src);
  if (isFinite(cached) && cached > 0) {
    if (cell) cell.textContent = formatDuration(cached);
    return cached;
  }

  if (track?.time && track.time !== '0:00') {
    // если уже пришло готовое человеку читаемое значение — не трогаем
    if (cell) cell.textContent = track.time;
    return undefined;
  }

  try {
    const seconds = await probeDuration(src);
    setCachedDuration(track?.id, src, seconds);
    if (cell) cell.textContent = formatDuration(seconds);
    return seconds;
  } catch {
    if (cell) cell.textContent = '0:00';
    return 0;
  }
}

// экспорт в window для совместимости
if (typeof window !== 'undefined') {
  Object.assign(window, {
    DURATION_LS_KEY,
    probeDuration,
    ensureTrackDuration,
    getCachedDuration,
    setCachedDuration
  });
}
