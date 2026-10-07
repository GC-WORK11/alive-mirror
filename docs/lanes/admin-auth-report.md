# admin-auth lane report — real sign-in for the engine room

Date: 2026-10-07 · Branch: `base/v2` · Scope: `/admin` + every path
behind `_admin_guard` (`/admin/api*`, `/v2/usage`). Built on the pentest
lane's findings (`docs/lanes/pentest-report.md`): Bearer compare was
already constant-time, the limiter already keys on the socket peer — this
lane replaces the *browser's* token plumbing, which was the live hole.
Live-verified on a local task (`:8099`, real field, real Chrome).

---

## What was wrong before

`admin.html` held the operator token in `sessionStorage.alive_admin_tok`
and sent it as a Bearer on every gated fetch, after a `prompt()` dialog.
Two problems, one of them already proven against us:

- **Any page-context script could read it.** The stored-XSS the pentest
  found (unescaped review note → innerHTML) had exactly this payoff:
  note JS runs → `sessionStorage.alive_admin_tok` → full `/admin/api/*`.
  The sink was fixed; the *theft path* stayed live for the next sink.
- `prompt()` is a worse-than-nothing UX: blocking, serialising parallel
  401s, unstyled, and it trained "type the secret into a browser dialog".

The HTML page itself was always public — fine, it carried no data —
but "public page + JS-held secret" meant the gate depended entirely on
script hygiene.

## Design (~120 lines, stdlib + hmac only, zero cost, zero infra)

```
POST /v2/admin/login   {"token": <ALIVE_ADMIN_TOKEN>}  → 200 + Set-Cookie
GET  /v2/admin/session                              → {"authenticated": bool}
POST /v2/admin/logout                               → cookie deleted
```

**Cookie** `alive_admin=v1.<exp>.<sig>` — signed-*stateless*:
`sig = HMAC-SHA256(key=ALIVE_ADMIN_TOKEN, "alive-admin-v1:<exp>")[:32]`.
No session store, no DB, no new dependency. Flags: `HttpOnly`,
`SameSite=Strict`, `Path=/`, `Max-Age=8h` (`ALIVE_ADMIN_SESSION_S`
overrides). `Secure` is set **only when the request arrives over TLS**
(scheme or `x-forwarded-proto: https`) — see honest limits.

**Guard** `_admin_guard` now accepts the cookie **or** `Authorization:
Bearer` — Bearer is deliberately kept for ops curl / go-nogo checks and
any non-browser client. Token unset → unchanged loopback-only dev
default; `/v2/admin/login` then answers 503 (`admin auth is not
configured`), so `session`/`login` mirror the guard exactly.

**Rate limit** `/v2/admin/login` gets its own bucket in
`_DEFAULT_PATH_LIMITS`: `(0.2, 5)` — five attempts then ~1 per 5 s,
keyed on the TCP socket peer (the pentest lane's fix — XFF and
self-minted headers mint nothing). A real login needs one shot;
anything past five is brute force. Verified: 6th POST → 429 +
`Retry-After`, global budget untouched.

**Page** — `admin.html` fails closed:
- Boot → `GET /v2/admin/session` → unauthenticated lands on a gate
  card (warm paper, one card, hairlines, mono small-caps — the ops
  register; guests get a `/city` escape link). No gated fetch fires.
- Form posts the token **once**; JS never stores or re-reads it —
  it tracks only `AUT` (a boolean). 401 mid-view → locked tiles +
  gate with "session ended — sign in again". The probe rides every
  30 s tick, so sign-out/expiry in another tab re-locks this one.
- `sessionStorage.alive_admin_tok`, `alive_admin_tok_no`, and both
  `prompt()` calls are **deleted** — the sessionStorage keys still
  present are the unrelated `alive_boot_v1` intro flag.
- Masthead button is now `sign out` → POST `/v2/admin/logout`.

## Threat model

| Path | Status |
|---|---|
| XSS → token theft | **closed.** The secret exists in JS for ~0 ms (one POST body). An injected script can't read an HttpOnly cookie, and can't mint one — signing needs the server-side token. Residual: injected JS could still *use* the ambient session to fetch `/admin/api/*` in-page (same as any cookie scheme) — but can't exfiltrate a reusable credential, and the fix to the one stored-XSS sink stands. |
| Brute force | **closed.** 5 tries then ~1/5 s per socket peer, against a 256-bit token from Secrets Manager — hopeless, and loud (429s). |
| CSRF | **closed by construction.** `SameSite=Strict` means a cross-site request never carries the cookie; login/logout are the only state-changing authed surfaces, and neither is attacker-useful. CORS stays `*` — credentialed responses aren't readable cross-origin anyway (no `allow-credentials`), and Strict means the cookie isn't even *sent* cross-site. |
| Token rotation | every issued cookie dies with the old token (it's the HMAC key) — rotation is a global logout, which is what you want. |
| Cookie replay / theft on-wire | **OPEN — same as before.** The NLB is plain HTTP :80; a copied cookie works until expiry. No worse than the Bearer it replaces (which also rode plaintext), but it is why `Secure` is conditional and TLS remains the top owner decision from the pentest report. |
| Session revocation | **OPEN, bounded.** Stateless = no server-side kill. Logout deletes the cookie *in that browser*; a copied value lives on until its signed `exp` — worst case ~8 h. Chosen deliberately (zero-infra constraint); rotating `ALIVE_ADMIN_TOKEN` is the global kill switch. |
| Redeploy / restart | **non-issue** — stateless means sessions survive restarts and rolling deploys; nothing in memory to lose. (The brief worried about the opposite: in-memory sessions dying on redeploy. Signed-stateless makes it a non-question.) |
| Guest reach | `/community`, `/`, `/city`, `/landing`, `/health`, `/aqi`, `/v2/city` etc. untouched — all GETs, all still open. `/admin` HTML still serves publicly (it carries no data); gated APIs now 401 without a session. |

## Verification (all done on this branch)

- `pytest tests/test_admin_auth.py` — **12/12**: login ok + cookie
  flags (HttpOnly/Strict/Path/Max-Age), Secure-only-over-TLS, bad
  token/empty/malformed → 401, unconfigured → 503, cookie opens
  `/v2/usage` + `/admin/api`, guest 401, expired-sig-valid → 401,
  forged/malformed → 401, rotation kills sessions, logout clears,
  loopback dev unchanged, login bucket 429s after 5, Bearer kept,
  served page has the gate and zero sessionStorage-token machinery.
  `test_admin_usage.py` 9/9 + `test_security.py` + `test_landing_serve`
  + `test_admin_v2` + `test_admin_agg` + `test_community_v2` — **83
  passed** in the adjacent sweep.
- Live curl chain on `:8099` (`ALIVE_ADMIN_TOKEN` set): guest 401 →
  wrong 401 → right 200 + `Set-Cookie alive_admin=v1.<exp>.<sig>;
  HttpOnly; Max-Age=28800; Path=/; SameSite=strict` → cookie opens
  `/v2/usage` 200 → logout `Max-Age=0`.
- Real Chrome (headless channel): guest sees gate → wrong token shows
  `wrong token — try again` → right token hides gate, board renders
  live (71.1 µg/m³ hero, all feeds) → masthead flips to `sign out` →
  click → gate returns. Cookie introspection: `alive_admin`,
  `httpOnly: true`, `sameSite: Strict`.
- Boot strip still resolves over the gate for its ≤2.4 s first-visit
  window — cosmetic, once per session, self-dismisses.

## Demo-morning runbook (owner-facing)

1. Token lives in AWS Secrets Manager `alive108/admin-token`
   (go-nogo step 8 already fetches it for the curl check).
2. Open `http://<NLB>/admin` → gate card → paste token → sign in.
3. Session ≈ 8 h — sign in again if it lapses; `sign out` ends early.
4. Phone hotspot / hall Wi-Fi — same flow; nothing device-bound.
5. If sign-in says `not configured`, the task env lost
   `ALIVE_ADMIN_TOKEN` — same failure as before, same fix (task env).

## Still weak, honestly

- **Plain HTTP everywhere.** The cookie rides cleartext on :80 —
  sniffable on hostile Wi-Fi exactly like the Bearer was. TLS is the
  fix (pentest owner-decision #1); `Secure` auto-enables the moment it
  lands. On demo hall Wi-Fi this is the real residual risk.
- **No server-side revocation** — by design (zero-cost, zero-infra);
  the global kill is token rotation, the per-cookie bound is `exp`.
- **Single shared operator identity** — one token, everyone who has it
  is "the operator". Right size for the demo; wrong shape if a second
  human ever needs the board with accountability.
- The gate is client-side — `/admin` HTML serves to anyone (by design:
  it carries no data). All data surfaces fail closed server-side.
