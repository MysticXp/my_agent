// SSE 流式客户端

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export function streamChat(endpoint, body, callbacks) {
  const controller = new AbortController();

  fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text().catch(() => '');
        callbacks.onError?.(`HTTP ${response.status}: ${text}`);
        return;
      }

      console.log('[SSE] Connected');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let count = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) { console.log('[SSE] Stream closed'); break; }

        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';

        let evt = '', dat = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) evt = line.slice(7).trim();
          else if (line.startsWith('data: ')) dat = line.slice(6).trim();
          else if (line === '' && evt && dat) {
            count++;
            console.log(`[SSE] ${evt}:`, dat.slice(0, 120));
            try {
              handleEvent(evt, JSON.parse(dat), callbacks);
            } catch (e) {
              console.warn('[SSE] parse error:', e.message);
            }
            evt = ''; dat = '';
          }
        }
      }
      console.log(`[SSE] Done, ${count} events`);
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        console.error('[SSE] Error:', err.message);
        callbacks.onError?.(err.message || '网络错误');
      }
    });

  return controller;
}

function handleEvent(type, data, cbs) {
  switch (type) {
    case 'node_start': cbs.onNodeStart?.(data.node, data.label); break;
    case 'node_end': cbs.onNodeEnd?.(data.node); break;
    case 'token': cbs.onToken?.(data.token || ''); break;
    case 'interrupt': console.log('[SSE] interrupt:', data.type); cbs.onInterrupt?.(data); break;
    case 'done': console.log('[SSE] done'); cbs.onDone?.(data); break;
    case 'error': cbs.onError?.(data.error || '未知错误'); break;
  }
}
