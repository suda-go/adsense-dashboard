// MAIN world — 覆盖页面的 window.fetch
(function() {
  const LOG = '[AdSense Main]';
  const originalFetch = window.fetch;
  console.log(LOG, '注入成功，原始 fetch 已保存');

  window.fetch = function(url, options) {
    const urlStr = typeof url === 'string' ? url : (url && url.url) || '';
    if (urlStr.includes('googleapis.com')) {
      console.log(LOG, '🎯 拦截:', urlStr.substring(0, 100));
      return new Promise((resolve, reject) => {
        const id = Date.now() + '_' + Math.random().toString(36).slice(2);
        const timeout = setTimeout(() => {
          document.removeEventListener('adsense-ext-response', handler);
          reject(new Error('扩展代理超时'));
        }, 25000);

        const handler = function(ev) {
          if (!ev.detail || ev.detail.id !== id) return;
          document.removeEventListener('adsense-ext-response', handler);
          clearTimeout(timeout);
          const r = ev.detail;
          if (r.error) { reject(new Error(r.error)); return; }
          resolve({
            ok: r.ok, status: r.status, statusText: r.statusText,
            json: () => JSON.parse(r.body),
            text: () => Promise.resolve(r.body),
            headers: new Headers(r.headers || {}),
          });
        };
        document.addEventListener('adsense-ext-response', handler);

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

        document.dispatchEvent(new CustomEvent('adsense-ext-request', {
          detail: { id, url: urlStr, method: options?.method || 'GET', headers: hdrs, body: options?.body || null }
        }));
      });
    }
    return originalFetch.call(this, url, options);
  };

  // 标记给页面检测用
  window.__adsenseExtension__ = { available: true, version: '4.0' };
  console.log(LOG, '✅ fetch 已覆盖');

  // 广播
  try { window.postMessage({ type: 'ADSENSE_EXT_LOADED', version: '4.0' }, '*'); } catch(e) {}
})();
