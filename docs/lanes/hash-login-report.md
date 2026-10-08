# hash-login — magic-link admin sign-in (2026-10-08)

Owner ask: "the admin dashboard sign-in should be based on a hash URL
link, not that you can sign in. Backend shouldn't be on client side."
One link → server verifies → cookie → clean URL. Form stays as fallback.

Base: `base/v2` @ `61364f3` (+ deploy-13 tag `5d4bbf5`). Local rig:
fresh `.venv312` (homebrew py3.12) + uvicorn `:8108`, prod-style
`--no-access-log`, `ALIVE_ADMIN_TOKEN=live-test-token-7x9q`.

## What landed

- **`GET <mount>/in/{secret}`** (`server/main.py`, `include_in_schema=False`)
  — path segment vs `ALIVE_ADMIN_TOKEN` via `hmac.compare_digest`
  (same compare the form uses). Match → mints the SAME session cookie
  (`alive_admin=v1.<exp>.<sig>`, HttpOnly, SameSite=Strict, Path=/,
  `Secure` only over TLS) + `303 See Other` → bare `<mount>` +
  `cache-control: no-store` + `x-robots-tag`. Mismatch → `HTTPException(404)`
  = byte-identical `{"detail":"Not Found"}` to any unknown path —
  no "wrong token" signal, no existence leak of a valid guess.
- **Rate limit** (`server/middleware.py`) — `<mount>/in/` added to
  `_DEFAULT_PATH_LIMITS` at `(0.2, 5)`: 5-trie burst then ~1/5 s per
  socket peer, own bucket class (global budget untouched).
- **Log redaction** (`server/observability.py`) — new
  `_SECRET_PATH_PREFIXES = (<mount>/in/,)`; `RequestLoggingMiddleware._emit`
  rewrites the path to `/in/<redacted>` before the record is built.
  Verified end-to-end: both the 303 (matched) and the 404 (near-miss
  guess, still ~47/48 chars) log redacted. `route` stays the template
  `…/in/{secret}` — safe. Uvicorn access log stays off (Dockerfile
  `--no-access-log`, unchanged).
- **Console page** (`server/admin.html`) — **boot strip deleted**
  (CSS block, `#boot` node, parse-time sessionStorage gate, `bootStrip()`;
  ~120 lines). No splash: first paint → one `checkSession()` fetch →
  gate for guests or straight board. `alive_boot_v1` gone with it.
  Gate foot gains the line "your operator link opens straight in".
  Landing page keeps its own strip — untouched.
- **Stale-label fix** — `tokBtnRefresh()` now re-runs when
  `checkSession()` resolves: a signed-in first paint used to keep the
  button on "operator sign in" (pre-existing reload bug the link flow
  makes permanent — `hideGate()` masked it before).
- **Docs** — `docs/plan/admin-login.md`: `/in/<token>` is now the
  primary flow with curl chain + failure-table rows + honest limits
  (link lives in browser history; the link IS the token).

## Verified (local, `ALIVE_ADMIN_TOKEN=live-test-token-7x9q`)

```
GET <mount>/in/<real>      → 303 · location: <mount> · no-store · x-robots
                             Set-Cookie alive_admin=v1.<exp>.<sig>; HttpOnly;
                             Max-Age=28800; Path=/; SameSite=strict
GET <mount>/in/<wrong>     → 404 {"detail":"Not Found"} — identical bytes
GET /no-such-path          → 404 {"detail":"Not Found"} — to the above
cookie → <mount>/session   → {"authenticated":true}
cookie → <mount>/api       → 200  ·  <mount>/api/usage → 200
POST <mount>/login (form)  → 200 + same Set-Cookie shape (fallback intact)
10× GET /in/guess-N        → 404×5 then 429×5; /aqi beside it still 200
access log scan            → token absent (uvicorn --no-access-log)
request-log e2e            → /in/<redacted> on both 303 and 404
Chrome drive               → open …/in/<real> → lands <mount> clean URL,
                             board renders immediately, masthead SIGN OUT;
                             SIGN OUT → gate card (with link hint)
pytest                     → test_admin_auth 20/20 (5 new), admin_agg/
                             admin_usage/admin_v2/landing_serve/
                             inline_scripts/security/observability: 74 more
scripts/check_inline_scripts.py → OK (4 files parse clean)
```

## Honest limits (unchanged + new)

- The link **is** the token in a URL — anyone holding it holds the
  credential; it sits in browser history till it ages out. Rotation
  kills it and every minted cookie.
- Stateless cookie: no server-side revoke; worst case ≤8 h for a copy.
- Plain-HTTP NLB still carries the token + cookie in cleartext (same
  exposure as the form's POST body had — TLS is the standing owner call;
  `Secure` auto-enables behind a TLS listener).
- No per-IP→link binding; bucket keys the socket peer, not the URL.

## Files

`server/main.py` (+34) · `server/middleware.py` (+5) ·
`server/observability.py` (+13) · `server/admin.html` (−120 net) ·
`server/tests/test_admin_auth.py` (+89, 5 tests + boot-strip assert) ·
`docs/plan/admin-login.md` (rewritten primary flow) · this report.
