# Badge proxy

Cloudflare Worker that proxies the README badge endpoints so the upstream
hostnames (Kromgo, Gatus) don't appear in the public README.

## Routes

| Path prefix | Forwarded to (set as Worker secret) |
|-------------|-------------------------------------|
| `/k/<path>` | `KROMGO_TARGET` (cluster metrics) |
| `/s/<path>` | `STATUS_TARGET` (Gatus status page) |

## Deploy

```bash
# 1. Install wrangler (one-off)
bun install -g wrangler   # or pnpm / npm

# 2. Authenticate against your Cloudflare account
wrangler login

# 3. Set the upstream targets (stored in Cloudflare's secret store, never in this repo)
cd scripts/badge-proxy
wrangler secret put KROMGO_TARGET   # paste e.g. https://kromgo.<your-domain>
wrangler secret put STATUS_TARGET   # paste e.g. https://status.<your-domain>

# 4. Deploy
wrangler deploy
```

Wrangler prints the public URL on success, of the form
`https://homelab-badges.<account>.workers.dev`. Use that hostname in the root
README badge URLs.
