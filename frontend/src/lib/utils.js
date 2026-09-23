export function uid() {
  return crypto?.randomUUID?.() || `ff-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function stored(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}

export function timeNow() {
  return new Intl.DateTimeFormat([], { hour: 'numeric', minute: '2-digit' }).format(new Date());
}
