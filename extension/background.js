// Background Service Worker — 使用 port 持久连接处理请求
console.log('[BG] Service Worker 启动');

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== 'adsense-proxy') return;
  console.log('[BG] Port 连接已建立');

  port.onMessage.addListener(async (msg) => {
    if (msg.type === 'ADSENSE_API_REQUEST') {
      const id = msg.requestId;
      console.log('[BG] === 请求详情 ===');
      console.log('[BG] URL:', msg.url);
      console.log('[BG] Method:', msg.method);
      console.log('[BG] Headers:', JSON.stringify(msg.headers));
      console.log('[BG] Body:', msg.body);

      try {
        // 补充 Google API 需要的 headers
        const headers = {
          ...msg.headers,
          'Accept': 'application/json',
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
          'X-Goog-Api-Client': 'gdcl/1.0.0',
        };
        const fetchOpts = {
          method: msg.method || 'GET',
          headers: headers,
          body: msg.body || undefined,
        };
        console.log('[BG] fetch 调用:', msg.url?.substring(0, 100), JSON.stringify(fetchOpts.headers).substring(0, 200));
        const resp = await fetch(msg.url, fetchOpts);
        const text = await resp.text();
        console.log('[BG] 响应状态:', resp.status, resp.statusText);
        console.log('[BG] 响应体前100字:', text.substring(0, 100));
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
