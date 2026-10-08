# admin-obscure lane report — the engine room moved off `/admin`

Date: 2026-10-08 · Branch: `base/v2` · Scope: server + public surfaces
+ operator docs. Verified **locally** against a real uvicorn boot
(`:8108`, `ALIVE_ADMIN_TOKEN` set) — every claim below is a curl/pytest
observation, not a code read. Prod untouched (GET-only lane, NO
deploy): the console is still at its old path live until the next
deploy, and `tools/admin_mirror.py` keeps working on both.

Owner's ask: *"change the admin login URL, make it more complex so no
one can go through that."* This lane is **security by obscurity on top
of the real auth** — the HMAC cookie, 5-try rate bucket, and
`ALIVE_ADMIN_TOKEN` gate are untouched. Obscurity hides the door; the
lock is the same lock.

---

## 1. The new URL — actually random, one constant

```
/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs
```

- Generated `secrets.token_urlsafe(24)` → 32 urlsafe chars ≈ **192
  bits**. A path-guess attack at even 1,000 req/s needs ~10⁴⁸ years —
  the entropy was always going to be fine.
- Held in **one file**: `server/admin_mount.py` (`ADMIN_MOUNT`).
  `main.py`, `admin_agg.py`, `middleware.py`, all three test files,
  `tools/admin_mirror.py`, `tools/load_v2.py`, `scripts/gen_api_docs.py`
  and `server/test_api.py` all import it — **rotation is one edit**.
- Committed on purpose (owner reads it from repo/docs); it's a spare
  key, not a password — `docs/plan/admin-login.md` says where it lives
  and where it must not be pasted.

## 2. Everything hangs under the mount — page, api, auth

| Surface | Old | New |
|---|---|---|
| console page | `GET /admin` | `GET <mount>` (+ trailing slash) |
| sign-in | `POST /v2/admin/login` | `POST <mount>/login` |
| session probe | `GET /v2/admin/session` | `GET <mount>/session` |
| sign-out | `POST /v2/admin/logout` | `POST <mount>/logout` |
| ops api | `GET /admin/api*` | `GET <mount>/api*` (agg router re-prefixed) |
| usage | `GET /v2/usage` | `GET <mount>/api/usage` |

APIs moved **with** the page rather than staying at `/admin/api*` —
leaving them behind would have kept a discoverable console surface at
guessable paths. `admin.html` hardcodes nothing: `const
M=location.pathname...` derives the mount from where the page was
served, so the same file survives the next rotation for free.
`_admin_guard`, `_session_sign/_session_ok`, the `alive_admin`
HttpOnly SameSite=Strict cookie and the 5-try login rate bucket are
unchanged (middleware's rate key now names the mount).

## 3. Old paths — honest 404s, no existence leak

Verified live on `:8108` — every one of these returns **404**, the same
response as any made-up URL (no redirect, no 401 hint):

`/admin`, `/admin/`, `/admin.html`, `/admin/api`, `/admin/api/status`,
`/v2/admin/login` (GET **and** POST), `/v2/admin/logout`,
`/v2/admin/session`, `/v2/usage`.

New regression test `test_old_admin_paths_are_honest_404s` pins it.

## 4. Public surfaces — zero pointers

Served-HTML audit (`curl -H 'Accept: text/html'`):

| Page | `admin` hits left | What they are |
|---|---|---|
| `/` | 2 | `osm_admin_5` — wire-data field name from `/v2/districts`, not a pointer |
| `/city` | 0 | nav `admin` + footer `ops ↗` links removed |
| `/community` | 0 | nav `admin` + `Admin →` link removed |

Beyond the HTML: `/community`'s **JSON** basis string literally said
"/v2/city and /admin read" — now "the ops console read". **`/docs` +
`/openapi.json` enumerated every `/a-…` route** — that alone would
have published the secret path to any crawler, so all console routes
+ both admin routers are now `include_in_schema=False`; the served
schema has zero mount paths and zero `/admin` literals (only
`admin_level`, a public geojson field name). Mobile app: zero admin
references — untouched.

## 5. Noindex without a robots.txt

`x-robots-tag: noindex, nofollow` on the page route +
`<meta name="robots" content="noindex,nofollow">` in `admin.html`.
Deliberately **no** robots.txt entry — robots.txt is public; listing
`/a-…` there would leak the exact thing we're hiding. Pinned by
`test_console_page_carries_noindex`.

## 6. Docs + tooling

- `docs/plan/admin-login.md` — rewritten: new-URL section up top (path,
  rotation, handling rules) + the curl chain + T-30 flow all on the
  mount.
- `docs/plan/demo-morning.md`, `docs/submission/submission-checklist.md`
  — the T-30 action checklists carry the real mount URL; descriptive
  docs (`runbook.md`, `judge-qa-v2.md`, `11-demo-script.md`,
  `repo-readme.md`) say "unlisted URL" and point at admin-login.md.
- `tools/admin_mirror.py` — rewritten around `ADMIN_MOUNT`; falls back
  to each old path on 404 so the mirror works pre-deploy too.
- `tools/load_v2.py`, `server/test_api.py` — import the mount.
- `docs/api/REFERENCE.md`, `openapi.json`, samples — generated docs;
  `gen_api_docs.py` now emits mount-derived paths on the next regen.

## 7. Verification — everything above, reproduced

```
ALIVE_ADMIN_TOKEN=test-token-xyz /tmp/alive-venv312/bin/uvicorn \
    main:app --host 127.0.0.1 --port 8108
```

- `GET <mount>` → **200** (168 KB) + `x-robots-tag: noindex, nofollow`; `GET <mount>/` → 200
- `POST <mount>/login` (real token) → **200** + `Set-Cookie alive_admin=v1.…`
- `GET <mount>/session` w/ cookie → `{"authenticated":true}`;
  `<mount>/api`, `<mount>/api/usage`, `<mount>/api/status` → **200**
- `POST <mount>/logout` → **200** + `Max-Age=0`
- guest `GET <mount>/api` → **401**; `login` w/ bad token → **401**
  (real auth intact)
- all §3 paths → **404**
- `PYTHONPATH=. pytest -q tests/test_admin_auth.py
  tests/test_admin_v2.py tests/test_admin_usage.py` → **33 passed**
- `python3 scripts/check_inline_scripts.py` → **OK** (4 blocks parse)

## 8. Honest limits

- **Obscurity is not auth.** The mount is a committed secret of the
  "spare key" class — fine in the private repo, useless if pasted into
  submission docs/chat/on stage. The real barrier stays the 256-bit
  `ALIVE_ADMIN_TOKEN` + rate bucket; rotate the URL via one edit if it
  ever escapes.
- **prod is still old-path** until the next deploy — by design
  (GET-only lane). `admin_mirror.py` bridges both.
- `/docs` stays public (it never hid anything else); it now simply
  doesn't enumerate the console.
- `include_in_schema=False` also hides the console from FastAPI's own
  tooling — an acceptable trade for the leak it closes.
