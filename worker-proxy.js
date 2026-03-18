// Cloudflare Worker: AdSense API Proxy
// 部署方法：
// 1. 登录 https://dash.cloudflare.com → Workers & Pages → Create Worker
// 2. 把这段代码粘贴进去，Deploy
// 3. 把 Worker URL 填到工具的「代理地址」设置里

export default {
  async fetch(request) {
    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': '*',
    };

    // Handle preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // Get target URL from path: /https://adsense.googleapis.com/v2/...
    const url = new URL(request.url);
    const targetUrl = url.pathname.slice(1) + url.search;

    if (!targetUrl || !targetUrl.startsWith('https://')) {
      return new Response('Usage: /https://adsense.googleapis.com/v2/...', { status: 400 });
    }

    // Forward request
    const headers = new Headers(request.headers);
    headers.delete('host');

    try {
      const resp = await fetch(targetUrl, {
        method: request.method,
        headers,
        body: request.method !== 'GET' ? await request.text() : undefined,
      });

      const newResp = new Response(resp.body, {
        status: resp.status,
        statusText: resp.statusText,
        headers: { ...Object.fromEntries(resp.headers), ...corsHeaders },
      });
      return newResp;
    } catch(e) {
      return new Response('Proxy error: ' + e.message, { status: 500, headers: corsHeaders });
    }
  }
};
