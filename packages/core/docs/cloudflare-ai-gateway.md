# Cloudflare AI Gateway (Grok, BYOK)

MyRoad calls Grok only through Cloudflare AI Gateway. The xAI key lives in
Cloudflare Secrets Store. MyRoad does not accept, store, or send that key.

## Server environment

Set these on the server process. Names only; do not commit values.

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_GATEWAY_ID`
- `CLOUDFLARE_AI_GATEWAY_TOKEN` (optional; only when authenticated gateway is enabled)

Optional test override of the grok base URL (not a secret):

- `CLOUDFLARE_AI_GATEWAY_BASE_URL`

Do not set or read a provider API key in MyRoad.

If `CLOUDFLARE_ACCOUNT_ID` or `CLOUDFLARE_GATEWAY_ID` is missing, `/add-path`
says the Cloudflare gateway is not configured.

## Request shape

Base URL (replaces `https://api.x.ai/v1`):

`https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/grok`

Chat: `POST {base}/v1/chat/completions`

Headers:

- `Content-Type: application/json`
- `cf-aig-authorization: Bearer …` only when `CLOUDFLARE_AI_GATEWAY_TOKEN` is set
- no provider `Authorization` header
- no `cf-aig-byok-alias` (alias `default` is used)

## Dashboard (once)

1. Create an AI Gateway and copy the account id and gateway name.
2. In Provider Keys, add the xAI key as BYOK alias `default`.
3. If authenticated gateway is on, create a Cloudflare API token for `cf-aig-authorization` and set `CLOUDFLARE_AI_GATEWAY_TOKEN` on the server.
