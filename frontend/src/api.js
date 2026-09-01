const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');

export async function generatePlan(payload) {
  const response = await fetch(`${API_BASE_URL}/generate-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'The fitness engine could not process this request.';
    throw new Error(detail);
  }
  return data;
}

export async function streamPlan(payload, { onToken, onStage } = {}) {
  const response = await fetch(`${API_BASE_URL}/generate-plan/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    const detail = typeof data.detail === 'string' ? data.detail : '';
    if (response.status === 429 || /rate_limit|rate limit|tokens per minute/i.test(detail)) {
      throw new Error('The coach is temporarily busy. Please try again in a few seconds.');
    }
    throw new Error(detail || 'The streaming fitness engine could not process this request.');
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
      if (eventName === 'stage') onStage?.(data.node);
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

export async function clearSession(sessionId) {
  if (!sessionId) return;
  const response = await fetch(`${API_BASE_URL}/clear-session/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not clear the current session.');
}

export { API_BASE_URL };
