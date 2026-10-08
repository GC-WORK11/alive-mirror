# Admin sign-in — the demo-morning playbook

How Govinda opens the engine room at T-30, on his laptop or the phone.
Proved end-to-end on prod **2026-10-07 ~11:35 UTC (~17:05 IST)**, live
build `43913dc0` — wire chain, gate, rate limit, and a real Chrome
drive (screenshots in `docs/lanes/admin-login-e2e-report.md`).

## The URL — unlisted on purpose (admin-obscure lane, 2026-10-08)

The engine room moved off `/admin` to a high-entropy path — security
by obscurity **on top of** the real auth below, never instead of it:

```
http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs
```

- `/admin`, `/admin.html`, `/admin/api*`, `/v2/admin/*`, `/v2/usage`
  all answer an **honest 404** now — same response as any made-up URL,
  so a path scan learns nothing (no redirect, no 401 hint).
- The whole console — page, api, sign-in, sign-out, session probe,
  usage rollup — hangs under the one mount, held in
  **`server/admin_mount.py`** (`ADMIN_MOUNT`). Never hardcode the
  literal elsewhere; rotate by editing that file + redeploying.
- Everything in this doc is unchanged except the paths: the gate card,
  the token, the cookie, the 5-try rate bucket are exactly what they
  were. Obscurity hides the door; the lock is the same lock.
- The path is committed on purpose (you're reading it now). Treat it
  like a spare key, not a password: fine in the private repo and ops
  notes, don't paste it in submission docs, chat, or on stage.
- Noindex rides on the route itself (`x-robots-tag` + page meta) —
  robots.txt never names it, since that file is public by design.

## The token — where it is, never what it is

- Lives in **AWS Secrets Manager `alive108/admin-token`** (region
  `ap-south-1`). The task def injects it into the container as
  `ALIVE_ADMIN_TOKEN`; it's also the HMAC key that signs every session
  cookie — **rotating the secret logs everyone out, instantly.**
- The value is **never in git, docs, or the report.** Fetch it:
  `aws secretsmanager get-secret-value --secret-id alive108/admin-token
  --region ap-south-1 --query SecretString --output text`
- Format only (safe to say out loud): 48 chars, `[0-9a-z]` — generated
  2026-10-03.
- **T-30 physical prep:** copy it into a phone note or onto paper
  beforehand — not a laptop you have to unlock on stage, and not into a
  browser's "save password" prompt (click **Never** when Chrome asks).

## The 60-second flow — laptop or phone, identical

1. Open `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs`
   (the unlisted console URL — `/admin` 404s by design).
2. A guest lands on the **gate card** — "ALIVE·108 / engine room ·
   OPERATOR ONLY — it opens for the operator and nobody else."
3. Paste the token → **SIGN IN**.
4. The board renders and refreshes itself every 30 s; the masthead
   shows **SIGN OUT** while you're in.
5. Session ≈ **8 h**, and it survives a task redeploy — the cookie is
   stateless-signed (`alive_admin=v1.<exp>.<sig>`, HttpOnly,
   SameSite=Strict), so nothing server-side can lose it.
6. **SIGN OUT** when done — gate card returns immediately. (Honest
   bound: the minted cookie stays valid till its signed expiry if a
   copy exists; rotation is the global kill.)

Same flow on the phone's browser — no device binding, nothing to
install. Venue Wi-Fi caveat stands: NLB is HTTP :80, so a captive
portal breaks it — phone hotspot is the safe uplink.

## The operator-only line for judges

> "That's the engine room — operator only. It shows the machine itself:
> feeds, models, counters. No person is ever shown — groups of 3+
> phones only. Everyone else gets the public city view."

If a judge wants to *see* it: sign in live — the board's own banner
says it (`NO PERSON IS EVER SHOWN · GROUPS OF 3+ PHONES ONLY`), and the
privacy story *is* the demo: the gated API only serves aggregate
scalars; there is no per-device data server-side to leak.

## What the board shows once you're in (verified live this pass)

- **Hero**: city-mean pm2.5 right now + CPCB band (read 40.1 µg/m³
  satisfactory at capture), cells sampled, median/worst, the
  WHO-guideline line, Indian AQI.
- **Field freshness** strip: rebuild age (~12 m), instruments (52 govt
  feeds), map points (99), streets priced (9,03,058 of 10,70,459),
  fires spotted (44 / 12 in the belt), next rebuild countdown.
- **Honesty tiles**: hidden-monitor MAE (read 11.96 µg/m³ — the "how
  wrong is the map" number), species reads, σ band.
- **The pipeline panel**: measure → interpolate → sample → breathe →
  emit → aggregate, with the real constants from the mount's `api/model`.
- **Usage tab** (mount's `api/usage`): devices / trips / donations —
  aggregate-only by construction (`k_min:3`).

## Ops equivalent — the exact curl chain (verify, don't stage)

```bash
NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
TOKEN=$(aws secretsmanager get-secret-value --secret-id alive108/admin-token \
        --region ap-south-1 --query SecretString --output text)

M=/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs   # admin_mount.ADMIN_MOUNT

# 1) sign in → 200 + Set-Cookie alive_admin=v1.<exp>.<sig>
curl -s -D- -o /dev/null -X POST "$NLB$M/login" \
     -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN\"}" \
     | grep -i '^set-cookie'
#    alive_admin=v1.<exp>.<sig>; HttpOnly; Max-Age=28800; Path=/; SameSite=strict

# 2) session probe → {"authenticated":true}
curl -s "$NLB$M/session" -H "Cookie: alive_admin=<v1....>"

# 3) gated data opens → 200
curl -s "$NLB$M/api/usage" -H "Cookie: alive_admin=<v1....>"
curl -s "$NLB$M/api"       -H "Cookie: alive_admin=<v1....>"

# 4) sign out → Set-Cookie Max-Age=0
curl -s -D- -o /dev/null -X POST "$NLB$M/logout" \
     -H "Cookie: alive_admin=<v1....>" | grep -i '^set-cookie'
```

Bearer still works for pure-ops clients
(`Authorization: Bearer $ALIVE_ADMIN_TOKEN`) — kept for curl/go-nogo,
never needed in the browser.

## Failure modes on stage

| Symptom | Meaning | Fix |
|---|---|---|
| gate card says `admin auth is not configured` (503 on the login POST) | task env lost `ALIVE_ADMIN_TOKEN` | secrets broke the rollout — check service events, rollback; same failure as pre-cookie |
| `wrong token — try again` (401) | typo / stale copy | re-paste from the SM value; 5 bad tries → 429 |
| 429 `rate_limited` | login bucket drained (5 then ~1/5 s) | wait ~5 s, one clean attempt — it passes |
| board re-locks mid-view | cookie expired or signed out in another tab | sign in again — 30 s probe re-locks by design |
| captive portal / no conn | NLB is plain HTTP :80 | switch to the phone hotspot; flow is identical |

## What it does NOT fix (carry the honesty)

- **Plain HTTP** — token and cookie ride cleartext on :80. Same
  exposure as the old Bearer header; TLS is the standing owner
  decision, and `Secure` auto-enables the day a TLS listener exists.
- **No per-cookie revocation** — stateless by design; worst case a
  copied cookie lives ≤8 h. Global kill = rotate the secret.
- **One operator identity** — one token, one "operator". Right size
  for the demo; wrong shape if a second human ever needs the board.
