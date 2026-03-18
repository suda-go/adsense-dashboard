// Content Script — 拦截页面 fetch，通过扩展转发到 Google API
(function() {
  // 广播扩展状态到页面
  window.postMessage({ type: 'ADSENSE_EXT_LOADED', version: '1.0' }, '*');

  // 检测扩展是否可用
  window.__adsenseExtension__ = {
    available: true,
    version: '1.0',

    async proxy(url, options = {}) {
      return new Promise((resolve, reject) => {
        const msg = {
          type: 'ADSENSE_API_REQUEST',
          url: url,
          method: options.method || 'GET',
          headers: options.headers ? Object.fromEntries(
            options.headers instanceof Headers ? options.headers.entries() : Object.entries(options.headers)
          ) : {},
          body: options.body || null,
        };

        chrome.runtime.sendMessage(msg, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }
          resolve({
            ok: response.ok,
            status: response.status,
            statusText: response.statusText,
            json: () => JSON.parse(response.body),
            text: () => Promise.resolve(response.body),
            headers: new Headers(),
          });
        });
      });
    }
  };

  // 拦截原始 fetch，对 googleapis.com 的请求自动走扩展
  const originalFetch = window.fetch;
  window.fetch = function(url, options) {
    const urlStr = typeof url === 'string' ? url : url.url;
    if (urlStr && (urlStr.includes('adsense.googleapis.com') || urlStr.includes('oauth2.googleapis.com'))) {
      console.log('[AdSense Extension] 代理请求:', urlStr);
      return window.__adsenseExtension__.proxy(urlStr, options);
    }
    return originalFetch.call(this, url, options);
  };

  console.log('[AdSense Extension] 已加载，CORS 代理已激活');
})();
