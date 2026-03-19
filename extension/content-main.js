// MAIN world — 覆盖页面的 window.fetch，通过 postMessage 与隔离世界通信
(function() {
  const LOG = '[AdSense Main]';
  const originalFetch = window.fetch;
  const pendingRequests = new Map();

  // 监听隔离世界返回的响应
  window.addEventListener('message', function(e) {
    if (e.source !== window) return;
    const d = e.data;
    if (d && d.type === 'ADSENSE_EXT_RESPONSE' && d.id && pendingRequests.has(d.id)) {
      const { resolve, reject, timer } = pendingRequests.get(d.id);
      pendingRequests.delete(d.id);
      clearTimeout(timer);
      if (d.error) { reject(new Error(d.error)); }
      else {
        resolve({
          ok: d.ok, status: d.status, statusText: d.statusText,
          json: () => JSON.parse(d.body),
          text: () => Promise.resolve(d.body),
          headers: new Headers(d.headers || {}),
        });
      }
    }
  });

  window.fetch = function(url, options) {
    const urlStr = typeof url === 'string' ? url : (url && url.url) || '';
    if (urlStr.includes('googleapis.com')) {
      console.log(LOG, '🎯 拦截:', urlStr.substring(0, 100));
      return new Promise((resolve, reject) => {
        const id = 'req_' + Date.now() + '_' + Math.random().toString(36).slice(2);
        const timer = setTimeout(() => {
          pendingRequests.delete(id);
          reject(new Error('扩展代理超时'));
        }, 25000);

        pendingRequests.set(id, { resolve, reject, timer });

        // 把 headers 转成普通对象
        let hdrs = {};
        try {
          if (options?.headers) {
            if (options.headers instanceof Headers) {
              options.headers.forEach((v, k) => { hdrs[k] = v; });
            } else if (typeof options.headers === 'object') {
              hdrs = { ...options.headers };
            }
          }
        } catch(e) {}

        // 发送给隔离世界
        window.postMessage({
          type: 'ADSENSE_EXT_REQUEST',
          id, url: urlStr,
          method: options?.method || 'GET',
          headers: hdrs,
          body: options?.body || null,
        }, '*');
      });
    }
    return originalFetch.call(this, url, options);
  };

  window.__adsenseExtension__ = { available: true, version: '4.0' };
  console.log(LOG, '✅ fetch 已覆盖，等待请求...');

  // 广播
  try { window.postMessage({ type: 'ADSENSE_EXT_LOADED', version: '4.0' }, '*'); } catch(e) {}
})();
