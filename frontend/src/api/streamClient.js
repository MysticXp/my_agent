// frontend/src/api/streamClient.js
// SSE 流式客户端 — 通过 EventSource 接收实时 token 流

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * 通过 fetch + ReadableStream 逐行解析 SSE 事件
 *
 * @param {string} endpoint - API 路径，如 '/chat/stream'
 * @param {object} body - POST body
 * @param {object} callbacks - 事件回调
 * @param {function} callbacks.onToken - 收到 token 时回调(tokenText)
 * @param {function} callbacks.onNodeStart - 节点开始时回调(nodeName, label)
 * @param {function} callbacks.onNodeEnd - 节点结束时回调(nodeName)
 * @param {function} callbacks.onInterrupt - 遇到 interrupt 时回调(data)
 * @param {function} callbacks.onDone - 完成时回调(data)
 * @param {function} callbacks.onError - 出错时回调(errorMsg)
 * @returns {AbortController} 用于取消请求
 */
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

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 按行分割 SSE 事件
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 剩余不完整的行留到下次

        let currentEvent = '';
        let currentData = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            currentData = line.slice(6).trim();
          } else if (line === '') {
            // 空行 = 事件结束
            if (currentEvent && currentData) {
              try {
                const parsed = JSON.parse(currentData);
                handleEvent(currentEvent, parsed, callbacks);
              } catch (e) {
                // 忽略解析失败的 data
              }
            }
            currentEvent = '';
            currentData = '';
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(err.message || '网络错误');
      }
    });

  return controller;
}

function handleEvent(eventType, data, callbacks) {
  switch (eventType) {
    case 'token':
      callbacks.onToken?.(data.token || '');
      break;
    case 'node_start':
      callbacks.onNodeStart?.(data.node, data.label);
      break;
    case 'node_end':
      callbacks.onNodeEnd?.(data.node);
      break;
    case 'interrupt':
      callbacks.onInterrupt?.(data);
      break;
    case 'done':
      callbacks.onDone?.(data);
      break;
    case 'error':
      callbacks.onError?.(data.error || '未知错误');
      break;
    default:
      break;
  }
}
