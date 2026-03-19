// Background Service Worker — 使用 port 持久连接处理请求
console.log('[BG] Service Worker 启动');

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== 'adsense-proxy') return;
  console.log('[BG] Port 连接已建立');

  port.onMessage.addListener(async (msg) => {
    if (msg.type === 'ADSENSE_API_REQUEST') {
      const id = msg.requestId;
      console.log('[BG] 收到请求:', msg.method, msg.url?.substring(0, 80));

      try {
        const resp = await fetch(msg.url, {
          method: msg.method || 'GET',
          headers: msg.headers || {},
          body: msg.body || undefined,
        });
        const text = await resp.text();
        console.log('[BG] 响应:', resp.status, text.substring(0, 100));
        port.postMessage({
          requestId: id,
          ok: resp.ok,
          status: resp.status,
          statusText: resp.statusText,
          body: text,
        });
      } catch(e) {
        console.error('[BG] Fetch 失败:', e.name, e.message);
        port.postMessage({
          requestId: id,
          error: `${e.name}: ${e.message}`,
        });
      }
    }
  });

  port.onDisconnect.addListener(() => {
    console.log('[BG] Port 断开');
  });
});

// 也保留 onMessage 作为兼容
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ADSENSE_PING') {
    console.log('[BG] Ping');
    sendResponse({ pong: true });
    return false;
  }
});
