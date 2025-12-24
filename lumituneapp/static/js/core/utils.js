// core/utils.js
// Общие утилиты: debounce, cookies, экранирование, форматтеры

/** debounce с сохранением последнего this/args */
export function debounce(fn, wait = 300) {
  let t;
  return function debounced(...args) {
    const ctx = this;
    clearTimeout(t);
    t = setTimeout(() => fn.apply(ctx, args), wait);
  };
}

/** получить cookie по имени (совместимо с Django csrftoken) */
export function getCookie(name) {
  if (!document?.cookie) return null;
  const cookies = document.cookie.split(';');
  for (const raw of cookies) {
    const c = raw.trim();
    if (c.startsWith(name + '=')) return decodeURIComponent(c.slice(name.length + 1));
  }
  return null;
}

/** безопасное экранирование HTML */
export function escapeHtml(s = '') {
  return String(s).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}

/** человекочитаемые байты */
export function niceBytes(n) {
  n = Number(n) || 0;
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  const v = i ? n.toFixed(1) : Math.round(n);
  return `${v} ${u[i]}`;
}

/** форматирование длительности в секундах -> mm:ss */
export function formatDuration(sec) {
  if (!isFinite(sec) || sec <= 0) return '0:00';
  const s = String(Math.floor(sec % 60)).padStart(2, '0');
  const m = Math.floor(sec / 60);
  return `${m}:${s}`;
}

/** нормализация даты строкой в локально читабельный YYYY-MM-DD HH:mm */
export function fmtRecentDate(s) {
  if (!s) return '';
  const canon = String(s).replace(' ', 'T').replace('+00:00', 'Z');
  const d = new Date(canon);
  if (isNaN(d)) return String(s).split('.')[0].replace('T', ' ').slice(0, 16);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// (необяз.) экспорт в window для плавной миграции
if (typeof window !== 'undefined') {
  Object.assign(window, { debounce, getCookie, escapeHtml, niceBytes, formatDuration, fmtRecentDate });
}
