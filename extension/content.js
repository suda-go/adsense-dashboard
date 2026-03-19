// Content Script — 拦截页面 fetch，通过扩展转发到 Google API
(function() {
  const LOG = '[AdSense Extension]';

  // 安全检查：扩展上下文是否有效
  function isExtensionAlive() {
    try {
      return !!(typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage);
    } catch(e) {
      return false;
    }
  }

  if (!isExtensionAlive()) {
    console.warn(LOG, '扩展上下文不可用，跳过注入。请刷新页面重试。');
    window.__adsenseExtension__ = { available: false, error: 'context_invalidated' };
    return;
  }

  console.log(LOG, '脚本开始执行，当前 URL:', window.location.href);

  // 广播扩展状态到页面
  try {
    window.postMessage({ type: 'ADSENSE_EXT_LOADED', version: '1.0' }, '*');
  } catch(e) {}

  // 检测扩展是否可用
  window.__adsenseExtension__ = {
    available: true,
    version: '1.0',

    async proxy(url, options = {}) {
      return new Promise((resolve, reject) => {
        if (!isExtensionAlive()) {
          reject(new Error('扩展上下文已失效，请刷新页面'));
          return;
        }
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
      if (!window.__adsenseExtension__ || !window.__adsenseExtension__.available) {
        console.error(LOG, '扩展不可用，无法代理请求:', urlStr);
        return Promise.reject(new Error('Chrome 扩展未加载，请安装并启用 AdSense Dashboard Helper 扩展后刷新页面'));
      }
      console.log(LOG, '代理请求:', urlStr);
      return window.__adsenseExtension__.proxy(urlStr, options);
    }
    return originalFetch.call(this, url, options);
  };

  console.log(LOG, '已加载，CORS 代理已激活');

  // 页面徽章确认扩展已注入
  function showBadge() {
    const badge = document.createElement('div');
    badge.textContent = '🧩 扩展已激活';
    badge.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999;background:#1a472a;color:#4ecdc4;padding:8px 16px;border-radius:8px;font-size:14px;font-family:sans-serif;box-shadow:0 2px 10px rgba(0,0,0,0.3)';
    document.body.appendChild(badge);
    setTimeout(() => badge.remove(), 5000);
  }
  if (document.body) showBadge();
  else document.addEventListener('DOMContentLoaded', showBadge);
})();
