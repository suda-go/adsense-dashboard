// ISOLATED world — 与 Service Worker 通信，转发请求
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
          document.dispatchEvent(new CustomEvent('adsense-ext-response', { detail: msg }));
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

  // 监听 MAIN world 发来的请求
  document.addEventListener('adsense-ext-request', function(e) {
    const req = e.detail;
    if (!req || !req.id) return;
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
        document.dispatchEvent(new CustomEvent('adsense-ext-response', {
          detail: { id: req.id, error: 'Port 发送失败: ' + err.message }
        }));
      }
    };

    if (connected) { send(); }
    else {
      // 等连接
      const wait = setInterval(() => {
        if (connected) { clearInterval(wait); send(); }
      }, 100);
      setTimeout(() => { clearInterval(wait); }, 5000);
    }
  });

  console.log(LOG, '✅ 已就绪，等待请求');
})();
