// Content Script — 使用 port 持久连接 Service Worker
(function() {
  const LOG = '[AdSense Extension]';

  function isAlive() {
    try { return typeof chrome !== 'undefined' && !!chrome.runtime; }
    catch(e) { return false; }
  }

  if (!isAlive()) {
    console.warn(LOG, '扩展上下文不可用');
    window.__adsenseExtension__ = { available: false };
    return;
  }

  console.log(LOG, 'v3.0 初始化（port 模式）...');

  let port = null;
  let portReady = false;
  const pendingRequests = new Map();
  let requestId = 0;

  // 建立持久连接
  function connect() {
    try {
      port = chrome.runtime.connect({ name: 'adsense-proxy' });
      portReady = true;
      console.log(LOG, '✅ Port 已连接');

      port.onMessage.addListener((msg) => {
        if (msg.requestId && pendingRequests.has(msg.requestId)) {
          const { resolve, reject, timer } = pendingRequests.get(msg.requestId);
          pendingRequests.delete(msg.requestId);
          clearTimeout(timer);
          if (msg.error) {
            reject(new Error(msg.error));
          } else {
            resolve({
              ok: msg.ok,
              status: msg.status,
              statusText: msg.statusText,
              json: () => JSON.parse(msg.body),
              text: () => Promise.resolve(msg.body),
              headers: new Headers(),
            });
          }
        }
      });

      port.onDisconnect.addListener(() => {
        console.warn(LOG, 'Port 断开，重连中...');
        portReady = false;
        port = null;
        // 拒绝所有待处理请求
        for (const [id, { reject, timer }] of pendingRequests) {
          clearTimeout(timer);
          reject(new Error('扩展连接断开'));
        }
        pendingRequests.clear();
        // 自动重连
        setTimeout(connect, 500);
      });
    } catch(e) {
      console.error(LOG, '连接失败:', e.message);
      portReady = false;
      setTimeout(connect, 1000);
    }
  }

  connect();

  // 代理请求
  async function proxyFetch(url, options = {}) {
    if (!portReady || !port) {
      // 等待连接建立
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('等待扩展连接超时')), 5000);
        const check = setInterval(() => {
          if (portReady) { clearTimeout(timer); clearInterval(check); resolve(); }
        }, 100);
      });
    }

    return new Promise((resolve, reject) => {
      const id = ++requestId;
      const timer = setTimeout(() => {
        pendingRequests.delete(id);
        reject(new Error('Service Worker 响应超时（20s）'));
      }, 20000);

      pendingRequests.set(id, { resolve, reject, timer });

      console.log(LOG, '→ Port 请求:', options.method || 'GET', url.substring(0, 80));

      try {
        port.postMessage({
          requestId: id,
          type: 'ADSENSE_API_REQUEST',
          url: url,
          method: options.method || 'GET',
          headers: options.headers ? Object.fromEntries(
            options.headers instanceof Headers ? options.headers.entries() : Object.entries(options.headers)
          ) : {},
          body: options.body || null,
        });
      } catch(e) {
        clearTimeout(timer);
        pendingRequests.delete(id);
        reject(new Error('Port 发送失败: ' + e.message));
      }
    });
  }

  // 标记扩展可用
  window.__adsenseExtension__ = { available: true, version: '3.0' };

  // 拦截 fetch
  const originalFetch = window.fetch;
  window.fetch = function(url, options) {
    const urlStr = typeof url === 'string' ? url : (url && url.url);
    if (urlStr && (urlStr.includes('adsense.googleapis.com') || urlStr.includes('oauth2.googleapis.com'))) {
      if (!isAlive()) {
        window.__adsenseExtension__ = { available: false };
        return Promise.reject(new Error('扩展上下文已失效，请刷新页面'));
      }
      console.log(LOG, '🔄 拦截:', urlStr.substring(0, 80));
      return proxyFetch(urlStr, options);
    }
    return originalFetch.call(this, url, options);
  };

  console.log(LOG, '✅ v3.0 就绪');

  // 徽章
  function showBadge() {
    const badge = document.createElement('div');
    badge.textContent = '🧩 扩展 v3.0 已激活 (port)';
    badge.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999;background:#1a472a;color:#4ecdc4;padding:8px 16px;border-radius:8px;font-size:14px;font-family:sans-serif;box-shadow:0 2px 10px rgba(0,0,0,0.3)';
    document.body.appendChild(badge);
    setTimeout(() => badge.remove(), 5000);
  }
  if (document.body) showBadge();
  else document.addEventListener('DOMContentLoaded', showBadge);

  // 广播
  function broadcast() {
    try { window.postMessage({ type: 'ADSENSE_EXT_LOADED', version: '3.0' }, '*'); } catch(e) {}
  }
  broadcast();
  setTimeout(broadcast, 100);
  setTimeout(broadcast, 500);
})();
