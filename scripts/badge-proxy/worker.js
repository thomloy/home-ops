// Cloudflare Worker that proxies README badge endpoints so the upstream
// hostnames don't appear in the public README.
//
// Routes:
//   /k/<path>  -> KROMGO_TARGET (cluster metrics endpoint)
//   /s/<path>  -> STATUS_TARGET (Gatus status page)
//
// Targets are bound as secrets via `wrangler secret put` and never
// committed to this repo.

const PREFIX_TO_VAR = {
  "/k/": "KROMGO_TARGET",
  "/s/": "STATUS_TARGET",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    for (const [prefix, varName] of Object.entries(PREFIX_TO_VAR)) {
      if (!url.pathname.startsWith(prefix)) continue;

      const target = env[varName];
      if (!target) {
        return new Response(`Upstream ${varName} not configured`, { status: 502 });
      }

      const upstream = new URL(target);
      upstream.pathname = url.pathname.slice(prefix.length - 1);
      upstream.search = url.search;

      const req = new Request(upstream, request);
      req.headers.set("Host", upstream.host);
      return fetch(req);
    }

    return new Response("Not Found", { status: 404 });
  },
};
