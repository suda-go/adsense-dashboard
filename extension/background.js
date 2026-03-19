// Background Service Worker — 处理来自页面的 API 请求
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ADSENSE_API_REQUEST') {
    console.log('[BG] 收到请求:', msg.method, msg.url);
    handleApiRequest(msg).then(sendResponse);
    return true; // 异步响应
  }
});

async function handleApiRequest(msg) {
  try {
    console.log('[BG] 开始 fetch:', msg.url);
    const resp = await fetch(msg.url, {
      method: msg.method || 'GET',
      headers: msg.headers || {},
      body: msg.body || undefined,
    });

    const text = await resp.text();
    console.log('[BG] 响应:', resp.status, resp.statusText, text.substring(0, 200));
    return {
      ok: resp.ok,
      status: resp.status,
      statusText: resp.statusText,
      body: text,
    };
  } catch(e) {
    console.error('[BG] Fetch 失败:', e.name, e.message);
    return { ok: false, status: 0, statusText: 'Network Error', body: `${e.name}: ${e.message}` };
  }
}
