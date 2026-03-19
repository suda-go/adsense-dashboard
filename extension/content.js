// Content Script — 直接在扩展上下文中代理 fetch（绕过 CORS）
// 不再依赖 Service Worker，避免 MV3 Service Worker 休眠问题
(function() {
  const LOG = '[AdSense Extension]';

  // 检查扩展上下文是否有效
  function isAlive() {
    try {
      return typeof chrome !== 'undefined' && !!chrome.runtime;
    } catch(e) { return false; }
  }

  if (!isAlive()) {
    console.warn(LOG, '扩展上下文不可用');
    window.__adsenseExtension__ = { available: false };
    return;
  }

  console.log(LOG, 'v1.3 初始化中...');

  // 直接代理函数 — 在 content script 的扩展上下文中直接 fetch（有跨域权限）
  async function proxyFetch(url, options = {}) {
    console.log(LOG, '🔄 代理请求:', options.method || 'GET', url);
    try {
      const resp = await fetch(url, {
        method: options.method || 'GET',
        headers: options.headers || {},
        body: options.body || undefined,
      });
      const text = await resp.text();
      console.log(LOG, '✅ 响应:', resp.status, text.substring(0, 100));
      return {
        ok: resp.ok,
        status: resp.status,
        statusText: resp.statusText,
        json: () => JSON.parse(text),
        text: () => Promise.resolve(text),
        headers: resp.headers,
      };
    } catch(e) {
      console.error(LOG, '❌ 代理失败:', e.message);
      throw e;
    }
  }

  // 标记扩展可用
  window.__adsenseExtension__ = { available: true, version: '1.3' };

  // 拦截原始 fetch
  const originalFetch = window.fetch;
  window.fetch = function(url, options) {
    const urlStr = typeof url === 'string' ? url : (url && url.url);
    if (urlStr && (urlStr.includes('adsense.googleapis.com') || urlStr.includes('oauth2.googleapis.com'))) {
      if (!isAlive()) {
        console.error(LOG, '扩展上下文已失效');
        window.__adsenseExtension__ = { available: false };
        return Promise.reject(new Error('扩展上下文已失效，请刷新页面'));
      }
      return proxyFetch(urlStr, options);
    }
    return originalFetch.call(this, url, options);
  };

  console.log(LOG, '✅ v1.3 就绪，fetch 已拦截');

  // 页面徽章
  function showBadge() {
    const badge = document.createElement('div');
    badge.textContent = '🧩 扩展 v1.3 已激活';
    badge.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999;background:#1a472a;color:#4ecdc4;padding:8px 16px;border-radius:8px;font-size:14px;font-family:sans-serif;box-shadow:0 2px 10px rgba(0,0,0,0.3)';
    document.body.appendChild(badge);
    setTimeout(() => badge.remove(), 5000);
  }
  if (document.body) showBadge();
  else document.addEventListener('DOMContentLoaded', showBadge);

  // 广播状态
  try { window.postMessage({ type: 'ADSENSE_EXT_LOADED', version: '1.3' }, '*'); } catch(e) {}
})();
