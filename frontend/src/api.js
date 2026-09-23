const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');

async function apiError(response, fallback) {
  const data = await response.json().catch(() => ({}));
  const detail = typeof data.detail === 'string' ? data.detail : '';
  const message = response.status === 429 || /rate_limit|rate limit|tokens per minute/i.test(detail)
    ? 'The coach is temporarily busy. Please try again in a few seconds.'
    : detail || fallback;
  const error = new Error(message);
  error.status = response.status;
  return error;
}

export async function createSession(profile) {
  const response = await fetch(`${API_BASE_URL}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile }),
  });
  if (!response.ok) throw await apiError(response, 'Could not start a coaching session.');
  return response.json();
}

export async function updateProfile(sessionId, profile) {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });
  if (!response.ok) throw await apiError(response, 'Could not save your details.');
  return response.json();
}

export async function getSessionState(sessionId) {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/state`);
  if (!response.ok) throw await apiError(response, 'Could not load your plan.');
  return response.json();
}

// SSE phases emitted by the backend workflow, in the order they can occur:
// start -> planning -> executing (per task) -> evaluating -> [replanning -> executing ...] -> completed -> done
const PHASE_EVENTS = new Set(['start', 'planning', 'executing', 'evaluating', 'replanning', 'completed']);

export async function streamChat(sessionId, message, { onToken, onPhase } = {}) {
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body: JSON.stringify({ message }),
  });

  if (!response.ok || !response.body) {
    throw await apiError(response, 'The streaming fitness engine could not process this request.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalData = null;

  const consume = (chunkText) => {
    buffer += chunkText;
    const frames = buffer.split('\n\n');
    buffer = frames.pop() || '';

    for (const frame of frames) {
      const lines = frame.split('\n');
      const eventName = lines.find(line => line.startsWith('event:'))?.slice(6).trim();
      const dataLine = lines.find(line => line.startsWith('data:'))?.slice(5).trim();
      if (!dataLine) continue;

      let data;
      try { data = JSON.parse(dataLine); } catch { continue; }

      if (eventName === 'token') onToken?.(data.content || '');
      else if (eventName && PHASE_EVENTS.has(eventName)) onPhase?.(eventName, data.node || null);
      if (eventName === 'done') finalData = data;
      if (eventName === 'error') throw new Error(data.detail || 'Streaming request failed.');
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    consume(decoder.decode(value, { stream: true }));
  }

  consume(decoder.decode());

  if (!finalData) throw new Error('The streaming connection ended before the final response was received.');
  return finalData;
}

export async function deleteSession(sessionId) {
  if (!sessionId) return;
  const response = await fetch(`${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
  if (!response.ok && response.status !== 404) throw await apiError(response, 'Could not clear the current session.');
}

export { API_BASE_URL };
