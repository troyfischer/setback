# SSE Authentication Guide

## 1. What SSE is

Server-Sent Events (SSE) is a way for a server to push updates to a client over one long-lived HTTP response.

- Client opens a normal HTTP `GET` request.
- Server keeps that response open.
- Server writes messages over time.
- Client receives them as they arrive.

SSE is one-way: server -> client only.

## 2. What `EventSource` is

`EventSource` is the browser API for SSE.

Example:

```js
const es = new EventSource('/game/123/subscribe');
es.onmessage = (event) => {
  const payload = JSON.parse(event.data);
  console.log(payload);
};
es.onerror = (err) => {
  console.error('stream error', err);
};
```

Key behavior of `EventSource`:

- Uses `GET` only.
- Automatically reconnects when disconnected.
- Expects `text/event-stream` response format.
- Cannot set custom request headers like `Authorization` in browsers.

That last point is the main auth difference.

## 3. SSE wire format basics

SSE messages are plain text lines.

Typical payload from server:

```text
retry: 3000

data: {"event_type":"bid_placed","game_id":42,"data":{...}}

```

- `data:` contains message data.
- Blank line ends one message.
- `retry:` tells client reconnect delay.
- Lines beginning with `:` are comments (often used as keepalive heartbeats).

## 4. Why SSE auth is different from normal API auth

For regular REST calls, browser code can do:

```js
fetch('/game/create', {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
});
```

For browser SSE via `EventSource`, you cannot add `Authorization` header.

Result:

- Endpoints that require bearer token header are hard to use directly with browser `EventSource`.
- If your backend expects `Authorization: Bearer ...`, browser SSE clients usually fail authentication.

## 5. Common SSE auth patterns

### Pattern A: Cookie/session auth (browser-friendly)

- User logs in; server sets auth cookie (HttpOnly recommended).
- Browser sends cookie automatically on `EventSource` request.
- Backend authenticates from cookie/session.

Pros:

- Native browser behavior.
- No token in URL.

Cons:

- Requires correct cookie/CORS/CSRF setup.

### Pattern B: Signed short-lived token in query string

- Backend issues short-lived SSE token (for this stream only).
- Client connects to `/subscribe?sse_token=...`.
- Backend validates token.

Pros:

- Works with `EventSource` despite no custom headers.

Cons:

- Query parameters can leak via logs/history/referrers.
- Must keep token short-lived and narrowly scoped.

### Pattern C: Use non-browser client that can set headers

- CLI/service/mobile custom client connects and sends `Authorization` header.

Pros:

- Works with existing bearer design.

Cons:

- Not suitable for browser `EventSource` without custom transport.

## 6. Security considerations specific to SSE

### 6.1 Long-lived connection

SSE stays open for a long time.

Implications:

- Auth is checked at connection time; decide whether/how to handle mid-stream expiry.
- Reconnect events will trigger auth checks repeatedly.

### 6.2 URL token leakage risk (if query auth is used)

Anything in query string may appear in:

- Access logs
- Browser history
- Monitoring/tracing tools
- Potential referrer contexts

Mitigations:

- Use very short token TTL (e.g. 30-120 seconds).
- Scope token to `user_id + game_id + endpoint`.
- One-time-use or nonce-based token if possible.
- Avoid sensitive long-lived credentials in URL.

### 6.3 CORS + credentials

If cross-origin and using cookies:

- Must set explicit allowed origin (not `*`).
- Must allow credentials on server and client side.
- Ensure cookie `SameSite` and `Secure` are correct for your deployment.

### 6.4 Authorization checks

For game streams, enforce:

- Game exists.
- User is authenticated.
- User is authorized for this game (participant, spectator role, etc).

Do not rely only on obscurity of `game_id`.

## 7. Reliability concerns often mistaken for auth failures

### 7.1 Idle timeout

Proxies/load balancers may close idle streams.

Mitigation:

- Send heartbeat comments periodically (for example every 10-30s).

### 7.2 Proxy buffering

Some proxies buffer responses, preventing live delivery.

Mitigation:

- Disable buffering for SSE response path (for example `X-Accel-Buffering: no` on Nginx path).

### 7.3 Slow consumers

If client reads slowly and server keeps queueing, memory can grow.

Mitigation:

- Use bounded per-client queues.
- Define drop policy (drop oldest vs disconnect).

## 8. Current codebase implications

In this repo, game routes depend on bearer auth globally. That means:

- Non-browser clients can authenticate to `/game/{id}/subscribe` with `Authorization` header.
- Browser `EventSource` cannot do that directly.

So if browser SSE is a requirement, you need one of:

1. Cookie/session auth for subscribe route.
2. Short-lived signed query token flow for subscribe route.
3. Different browser transport strategy.

## 9. Recommended next step (practical)

If your existing APIs stay bearer-based, the least disruptive browser-compatible approach is:

1. Add `POST /game/{id}/subscribe-token` (bearer-protected).
2. Return short-lived, scoped token.
3. Browser opens `new EventSource('/game/{id}/subscribe?sse_token=...')`.
4. Server validates token and user/game scope before opening stream.

This keeps normal REST auth unchanged while making SSE browser-compatible.

## 10. Quick decision checklist

- Do browser clients need live updates through native `EventSource`?
- Do you want to avoid tokens in URLs?
- Are cookies/session already part of your auth model?
- Do you need cross-origin browser SSE?

Your answers determine whether cookie-based or short-lived-query-token SSE auth is better.
