# admin-login-e2e lane report — demo-morning sign-in, proven on prod

Date: 2026-10-07 · Branch: `base/v2` · Scope: the full `/admin` sign-in
path on the **live NLB** (`alive108-2699c171ddded465.elb.ap-south-1`,
build `43913dc0` == `/health.build_sha`). Companion to
`admin-auth-report.md`, which proved the mechanism on `:8099`; this
lane proves it on prod and turns it into the T-30 playbook
(`docs/plan/admin-login.md`).

---

## 1. Token check — Secrets Manager

`aws secretsmanager get-secret-value --secret-id alive108/admin-token
--region ap-south-1` (via boto3; aws-cli isn't on this box):

- **exists**, plain-string secret (not a JSON envelope)
- **format only**: 48 chars, charset `[0-9a-z]` — 30 digits + 18
  lowercase, no symbols
- version `76a393ff-…`, created **2026-10-03**
- the value was never printed, written to disk, or committed — it rode
  shell env vars / process args only

## 2. The real login flow — curl chain on prod (~11:35 UTC)

| # | Step | Observed |
|---|---|---|
| 1 | `POST /v2/admin/login` `{token: <SM value>}` | **200** `{"ok":true,"expires_in":28800}` + `Set-Cookie: alive_admin=v1.<exp>.<sig>; HttpOnly; Max-Age=28800; Path=/; SameSite=strict` |
| 2 | `GET /v2/admin/session` with cookie | **200** `{"authenticated":true}` |
| 3 | `GET /v2/usage` with cookie | **200**, 2,494 B — live aggregates (`devices.total:24`, `k_min:3`, dynamodb stores) |
| 4 | `GET /admin/api` with cookie | **200**, 8,697 B — live board snapshot (`field: 99 samples / 52 station_readings`, fires, community, uptime 3,406 s) |
| 5 | `POST /v2/admin/logout` with cookie | **200** + `Set-Cookie: alive_admin=""; Max-Age=0` |

## 3. Gate behavior — every probe run against prod

| Probe | Result | Verdict |
|---|---|---|
| `GET /v2/usage` guest | **401** | gated |
| `GET /admin/api` guest | **401** | gated |
| `GET /admin/api/reviews` guest | **401** | gated |
| `GET /v2/admin/session` guest | **200** `{"authenticated":false}` | probe works, fails closed |
| `GET /admin` guest | **200**, 167 KB HTML containing the gate-card markup (`id="gate"`, `gatetok`, `gateform`) | page is public by design — it carries no data; JS shows the gate before any gated fetch |
| `GET /city` guest (control) | **200** | public surfaces untouched |
| `POST /v2/admin/login` wrong token | **401** `{"detail":"bad operator token"}` | constant-time `hmac.compare_digest` behind it |
| login brute-force probe | **429** `{"error":"rate_limited","detail":"too many requests from this client","retry_after_s":N,"limit":{"rate_per_s":0.2,"burst":5}}` + `Retry-After` header | limiter keyed on socket peer, exactly the `(0.2, 5)` bucket in `middleware.py` |
| correct login ~6 s after a 429 | **200** + fresh cookie | bucket refills ~1/5 s — a real login needs one shot; recovery is seconds, not minutes |
| old cookie replayed after logout | **200** | **by design** — stateless cookie stays valid till signed `exp` (≤8 h); logout deletes it in *that browser*; rotation is the global kill |

**Deviation, honestly:** the brief capped wrong-token probes at ≤6 —
the probe loop double-fired (a leftover second curl inside the loop),
so ~12 wrong POSTs hit prod. No impact: that's exactly what the limiter
is for, and it absorbed them — interleaved 401/429 as the 5-token
bucket drained and refilled ~1/5 s. Sequence observed on the primary
probe: 401, 401, 401, 429, 401, 429.

## 4. Browser proof — real Chrome on prod

Same URL, same flow Govinda runs at T-30 (screenshots in
`admin-login-e2e-shots/`):

1. `gate-card.png` — guest lands on the gate: **"ALIVE·108 / engine
   room · OPERATOR ONLY — it opens for the operator and nobody else"**
   + `sessions last ~8 h · sign-in is rate-limited · not the operator?
   delhi's air, the public view →`. No gated fetch fires.
2. token pasted (masked field) → SIGN IN → **board renders live**:
   `board-live.png` — hero 40.1 µg/m³ satisfactory (25 cells, median
   40.6, worst 50.1, indian aqi 67), freshness 12 m GOOD, 99 map
   points, hidden-monitor MAE 11.96, 52 instruments, 9,03,058 streets
   priced of 10,70,459, fires 44/12-in-belt, next rebuild countdown,
   masthead flipped to **SIGN OUT** + `NO PERSON IS EVER SHOWN · GROUPS
   OF 3+ PHONES ONLY`, 30 s auto-refresh ticking.
3. SIGN OUT → `signout-gate-returns.png` — gate card back, token field
   cleared.

**Caught on the drive:** Chrome's "Save password?" prompt fired on
sign-in — dismissed with **Never**. The playbook now says so; a saved
token in a synced password manager is an unowned copy.

## 5. Docs landed

- **`docs/plan/admin-login.md`** — the demo-morning playbook: the
  60-second sign-in (laptop or phone), the judge line ("operator only —
  the machine's feeds/models/counters; no person is ever shown"), the
  exact curl chain, the failure-mode table, the honest residuals.
- **`docs/demo-day.md`** — two stale checklist lines fixed: T-30 and
  T-25 still said "the public board renders tokenless" (pre-`b563da2`
  truth — guests get the gate card now); both point at the playbook.

## Honest residuals (unchanged from the auth lane, still true on prod)

- **Plain HTTP :80** — token and cookie ride cleartext. Same exposure
  as the Bearer it replaced; `Secure` auto-enables when a TLS listener
  exists. On demo-hall Wi-Fi this is the real residual — the phone
  hotspot is the fix on the day.
- **No per-cookie revocation** — replayed-cookie-200 after logout is
  observed, not theoretical. Bounded by `exp` ≤8 h; global kill is
  rotating `alive108/admin-token`.
- **Single operator identity** — one token = "the operator".
- Cosmetic: `logout`'s clearing cookie carries Starlette's default
  `SameSite=lax` vs login's `Strict` — harmless (a deletion only needs
  name+path), noted so nobody "fixes" it blind.
