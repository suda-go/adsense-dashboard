// ISOLATED world — 与 Service Worker 通信，通过 postMessage 与 MAIN 世界通信
(function() {
  const LOG = '[AdSense Isolated]';
  let port = null;
  let connected = false;

  function connect() {
    try {
      port = chrome.runtime.connect({ name: 'adsense-proxy' });
      connected = true;
      console.log(LOG, '✅ Port 已连接');

      port.onMessage.addListener((msg) => {
        if (msg.requestId) {
          console.log(LOG, '← SW 响应:', msg.requestId, msg.status || msg.error);
          window.postMessage({
            type: 'ADSENSE_EXT_RESPONSE',
            id: msg.requestId,
            ok: msg.ok,
            status: msg.status,
            statusText: msg.statusText,
            body: msg.body,
            error: msg.error,
          }, '*');
        }
      });

      port.onDisconnect.addListener(() => {
        console.warn(LOG, 'Port 断开，重连...');
        connected = false;
        port = null;
        setTimeout(connect, 500);
      });
    } catch(e) {
      console.error(LOG, '连接失败:', e.message);
      connected = false;
      setTimeout(connect, 1000);
    }
  }
  connect();

  // 监听 MAIN world 的请求
  window.addEventListener('message', function(e) {
    if (e.source !== window) return;
    const req = e.data;
    if (!req || req.type !== 'ADSENSE_EXT_REQUEST' || !req.id) return;
    console.log(LOG, '→ 收到请求:', req.method, req.url?.substring(0, 80));

    const send = () => {
      try {
        port.postMessage({
          requestId: req.id,
          type: 'ADSENSE_API_REQUEST',
          url: req.url,
          method: req.method,
          headers: req.headers || {},
          body: req.body,
        });
      } catch(err) {
        console.error(LOG, '发送失败:', err.message);
        window.postMessage({
          type: 'ADSENSE_EXT_RESPONSE',
          id: req.id,
          error: 'Port 发送失败: ' + err.message,
        }, '*');
      }
    };

    if (connected) { send(); }
    else {
      const wait = setInterval(() => {
        if (connected) { clearInterval(wait); send(); }
      }, 100);
      setTimeout(() => clearInterval(wait), 5000);
    }
  });

  console.log(LOG, '✅ 已就绪，监听 postMessage...');
})();
