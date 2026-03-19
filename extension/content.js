// Content Script — 通过 Service Worker 代理 fetch（SW 的 fetch 才绕 CORS）
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

  console.log(LOG, 'v2.0 初始化中...');

  // 唤醒 Service Worker 并等待就绪
  function wakeSW() {
    return new Promise((resolve) => {
      const timer = setTimeout(resolve, 1500); // 最多等 1.5s
      try {
        chrome.runtime.sendMessage({ type: 'ADSENSE_PING' }, () => {
          clearTimeout(timer);
          // SW 收到消息后还需一点时间初始化
          setTimeout(resolve, 200);
        });
      } catch(e) {
        clearTimeout(timer);
        resolve();
      }
    });
  }

  // 通过 Service Worker 代理请求
  async function proxyViaSW(url, options = {}) {
    // 先唤醒 SW
    await wakeSW();

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error('Service Worker 响应超时（20s）'));
      }, 20000);

      const msg = {
        type: 'ADSENSE_API_REQUEST',
        url: url,
        method: options.method || 'GET',
        headers: options.headers ? Object.fromEntries(
          options.headers instanceof Headers ? options.headers.entries() : Object.entries(options.headers)
        ) : {},
        body: options.body || null,
      };

      console.log(LOG, '→ 发送到 SW:', msg.method, msg.url);

      try {
        chrome.runtime.sendMessage(msg, (response) => {
          clearTimeout(timer);
          if (chrome.runtime.lastError) {
            console.error(LOG, 'SW 错误:', chrome.runtime.lastError.message);
            reject(new Error('SW 通信: ' + chrome.runtime.lastError.message));
            return;
          }
          if (!response) {
            reject(new Error('SW 返回空响应'));
            return;
          }
          console.log(LOG, '← SW 响应:', response.status);
          resolve({
            ok: response.ok,
            status: response.status,
            statusText: response.statusText,
            json: () => JSON.parse(response.body),
            text: () => Promise.resolve(response.body),
            headers: new Headers(),
          });
        });
      } catch(e) {
        clearTimeout(timer);
        reject(e);
      }
    });
  }

  // 标记扩展可用
  window.__adsenseExtension__ = { available: true, version: '2.0' };

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
      return proxyViaSW(urlStr, options);
    }
    return originalFetch.call(this, url, options);
  };

  console.log(LOG, '✅ v2.0 就绪');

  // 徽章
  function showBadge() {
    const badge = document.createElement('div');
    badge.textContent = '🧩 扩展 v2.0 已激活';
    badge.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999;background:#1a472a;color:#4ecdc4;padding:8px 16px;border-radius:8px;font-size:14px;font-family:sans-serif;box-shadow:0 2px 10px rgba(0,0,0,0.3)';
    document.body.appendChild(badge);
    setTimeout(() => badge.remove(), 5000);
  }
  if (document.body) showBadge();
  else document.addEventListener('DOMContentLoaded', showBadge);

  // 广播
  function broadcast() {
    try { window.postMessage({ type: 'ADSENSE_EXT_LOADED', version: '2.0' }, '*'); } catch(e) {}
  }
  broadcast();
  setTimeout(broadcast, 100);
  setTimeout(broadcast, 500);
  setTimeout(broadcast, 1000);
})();
