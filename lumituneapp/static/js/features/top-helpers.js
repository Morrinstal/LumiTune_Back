// features/top-helpers.js
// Кэш аудио-URL для Top + ограничитель параллельных прогоев (pLimit)

import { TracksAPI, toQuery } from '../core/api.js';

const TOP_SRC_CACHE = new Map();     // key -> url
const TOP_SRC_MISS  = new Map();     // key -> timestamp
const TOP_SRC_TTL_MS = 5 * 60 * 1000;

function topSrcKey(row) {
  return String(row?.id ?? `title::${row?.name || ''}::${row?.artist || row?.author || row?.show || ''}`);
}

async function fetchAudioSrcForTop(row) {
  try {
    const rid = row.id || row.track_id || row.pk;
    if (rid) {
      const d = await TracksAPI.list({ id: rid, page: 1, page_size: 1 });
      const t = (d?.tracks || d?.items || [])[0];
      if (t) return t.audio_url || t.stream_url || '';
    }
  } catch {}
  try {
    const title = (row.name || row.title || '').trim();
    const meta  = (row.artist || row.author || row.show || '').trim();
    const q     = [title, meta].filter(Boolean).join(' ');
    if (!q) return '';
    const d  = await TracksAPI.list({ page: 1, page_size: 5, q });
    const ls = d?.tracks || d?.items || [];
    if (!ls.length) return '';
    const tn  = title.toLowerCase();
    const hit = ls.find(t => String(t.name || '').trim().toLowerCase() === tn) || ls[0];
    return hit ? (hit.audio_url || hit.stream_url || '') : '';
  } catch {}
  return '';
}

export async function getTopAudioSrc(row) {
  const key = topSrcKey(row);
  const now = Date.now();

  if (TOP_SRC_CACHE.has(key)) return TOP_SRC_CACHE.get(key);

  const missAt = TOP_SRC_MISS.get(key);
  if (missAt && (now - missAt) < TOP_SRC_TTL_MS) return '';

  let src = row.audio_url || row.stream_url || '';
  if (!src) src = await fetchAudioSrcForTop(row);

  if (src) TOP_SRC_CACHE.set(key, src);
  else TOP_SRC_MISS.set(key, now);

  return src || '';
}

export function pLimit(limit = 3) {
  let active = 0;
  const q = [];
  const next = () => {
    if (active >= limit || q.length === 0) return;
    active++;
    const { fn, resolve, reject } = q.shift();
    fn().then(resolve, reject).finally(() => { active--; next(); });
  };
  return (fn) => new Promise((resolve, reject) => { q.push({ fn, resolve, reject }); next(); });
}

export const scheduleTopProbe = pLimit(3);

if (typeof window !== 'undefined') {
  Object.assign(window, { getTopAudioSrc, scheduleTopProbe });
}
