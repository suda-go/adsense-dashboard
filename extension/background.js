// Background Service Worker — 处理来自页面的 API 请求
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'ADSENSE_API_REQUEST') {
    handleApiRequest(msg).then(sendResponse);
    return true; // 异步响应
  }
});

async function handleApiRequest(msg) {
  try {
    const resp = await fetch(msg.url, {
      method: msg.method || 'GET',
      headers: msg.headers || {},
      body: msg.body || undefined,
    });

    const text = await resp.text();
    return {
      ok: resp.ok,
      status: resp.status,
      statusText: resp.statusText,
      body: text,
    };
  } catch(e) {
    return { ok: false, status: 0, statusText: 'Network Error', body: e.message };
  }
}
