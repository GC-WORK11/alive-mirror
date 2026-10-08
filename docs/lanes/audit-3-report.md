# audit-3 — bug-hunter third pass on the NEW HEAD

Scope: everything `2babf6d..1f188e9` (19 commits — onboarding-gate
safefile writes, pickSeq/pickTailGate, where-to rebuild, ios-nits,
landing-v9→v10, search-depth 210k gazetteer) plus the earlier passes'
note backlog. Hunt order A–E as briefed. Prod GET-only.

---

## FINDINGS — fixed this pass

### F1 — consent.json resurrected across delete-my-data · HIGH
`Mobile/src/store/consent.ts:76` (pre-fix). `saveConsent` captured
nothing at call time; its merge body ran on `writeTail` *after* a wipe.
`loadConsent` inside the merge repopulated `mem = EMPTY` post-wipe, so
the `mem === null` resurrection guard never fired — a save called
before the wipe but executing after it rewrote `consent.json` with the
stale patch. User sees: taps "delete my data", but `seen:true` survives
→ onboarding gate skipped on next launch, and `sharing:"on"` re-arms
trip donation — a privacy claim the app explicitly makes. Race window:
any save within one queued writeTail turn of the wipe (consent tap and
settings share-toggle are the writers).
Fix: capture `wipeGen` at call time; the merge drops when
`gen !== wipeGen || mem === null` (consent.ts:83-86). Regression test
"queued across delete-my-data is dropped whole" in onboarding.test.ts.

### F2 — admin brute-force budget double the documented one · MED
`server/middleware.py:445-449`. `/login` and `/in/<token>` verify the
SAME credential and the comments promise "same brake, same bucket —
~1 guess per 5 s". `_limits_for` keys buckets by matched prefix, so
each path got its OWN bucket: an attacker gets 5+5 burst then ~2/5s
sustained (~480 guesses/hr vs the 240 documented). The v2 note flagged
the wrong "same bucket" claim — it was wrong because it didn't exist.
Fix: `_BUCKET_CLASS` aliases the `/in/` prefix into the login class
(middleware.py:455-458); comments now true. Test
`test_in_link_shares_one_bucket_with_login` pins 5 attempts split
across both paths → 429 on either.

### F3 — "Your location" async tail re-opens dead surfaces · MED
`Mobile/App.tsx:1247` (pre-fix). The `posNowDetailed()` wait is up to
~9 s; the *failure* branch checks `phaseRef.current === "search"`
before writing, the *success* branch had no gate at all. Back-press
during the wait → tail calls `pick()` → `setPhase("place")` (place is
allowed from any non-nav phase) → the place sheet re-mounts over the
home the user just returned to. With `placePickSlot` set, the closure
also re-writes a home/work slot and re-opens the sidebar post-cancel —
exactly the superseded-async-tail class the last pick-race fix gated
everywhere else.
Fix: post-await `phaseRef.current !== "search"` early-return
(App.tsx:1254), same gate as the failure branch below it.

### F4 — moves card paints stale cache with no age disclosure · LOW
`Mobile/src/api/city.ts:271` (pre-fix). `peekCityMoves()` returned the
disk hit raw; unlike the city payload (`agedCity`/`stale` chips) the
moves card has no age labelling — a past-TTL copy painted an old
"last 7 days" distribution as current. Fix: serve only `hit.fresh`;
stale hits wait on the wire like a miss (city.ts:272).

---

## FINDINGS — evidenced, fix left to the owning lane

### F5 — search-corpus regressions on HEAD (search-depth lane) · HIGH
`server/tests/test_query_tolerance.py` — 5 failures against the real
committed corpus on `1f188e9`:
- `compound_kind_near_place`: "atm near cp" returns rows but ZERO
  flagged `compound` — the anchor/compound path silently skipped
  (rows now carry `overture:*` categories the cooked-category map
  doesn't claim).
- `compound_kind_in_place` + `kind_compound_still_wins_before_subplace`:
  "school sector 62 noida" — no compound rows at all.
- `sector_beta_alpha_resolve_to_sectors`: "beta 2 greater noida" top
  hit is `overture:lodging` "Sector Beta 2, Greater Noida, Up" —
  prefix expectation "beta 2" no longer met.
- `search_latency_compound_path`: p95 316ms vs <50ms budget (the 210k
  scan path itself — may be env, but compound absence isn't).
Also 2 `test_path_legality` failures are `ModuleNotFoundError:
alive_core` — this box has no eigen/core build; environment gap, not a
defect. The 5 above are real behavior changes the 210k-row lane
introduced — either compound resolution is broken under the new corpus
(demo-visible: kind+anchor queries stop resolving) or the tests pin
pre-corpus expectations. Needs the search-depth lane's call.

---

## NOTES (suspicions, verified-inert, or carried)

- tour/welcome `load*Seen` have no `wipeGen`/`inflight` guard (consent
  does): a read in-flight across wipe resolves and re-sets `mem` —
  in-session only (disk still purged → next launch correct). consent
  was worth fixing — its file carries `sharing`, theirs only gate
  replay.
- cross-store micro-window: `writeJsonDoc` is fire-and-forget inside
  every `writeTail` merge (daylog/ledger/daysum/settings/consent); a
  write already inside tmp→bak→move can land bytes after the sync
  purge. One safefile-level seam would close all stores at once —
  deliberately not patched store-by-store here.
- from-pick jumping straight to `compare` leaves the previous `place`
  in state — place sheet closed but preview card could read a dead
  destination name. Cosmetic, narrow.
- `bandRamp` SVG gradient id shared by HomeScreen + DelhiToday
  BandScale instances — both defs identical → collision visually inert.
- departAB missing-pct floors to `~1%` via `Math.max(1, …)` —
  directionally still correct (a `best` exists ⇒ lighter); marginal
  claim, not a false one.
- v10 landing nav still links `github.com/…/releases` → 404 for
  unauthenticated (private repo). F3 owner decision, carried.
- `/in/<token>` URL sits in browser history for the request's lifetime
  before the 303 strips it — same residual as v2; mitigated by
  redirect + `no-store` + redacted request log.
- Prod GET sweep: `/`, `/city`, `/community`, `/health`,
  `/openapi.json` all 200; zero mount/token/secret strings on public
  pages (the `osm_admin_5` hits are the documented districts data
  field; city.html hits are code comments).
- `landing.html` interactive ids all resolve (`#fieldSec` anchor
  fixed; `sparkGo` is a styling hook on a working `<a>`; `TYP_MONTH`
  is payload-driven — the v2 hardcoded-october note is closed).
- `scripts/build_corpus.py` / `fetch_overture.py`: no credential
  paths, no secrets — public Overture/Wikidata/OSM sources only.

## Verified clean (the classes the last fixes created)

safefile tmp→bak→move ordering + `.bak` fallback; pickTailGate
surface sets (stay/advance) vs `Phase`; `invalidatePicks` covering
close/switch/reroute tails; `navCollectionsFor` chunk math vs
resampleLine stepM boundaries; `loadRoute` resets strip+odometer+along;
drawHold transition windows covering camera ops + sheet mounts;
SearchScreen commit latch dies with `visible` (not a leak); DelhiToday
peek-then-wire — no double-aged math; web-tier seq checks on both
callbacks + `WEB_LIVE` label; App.tsx:1433 gate legal (post-gate hooks
belong to NavSession); `include_in_schema=False` on every admin route;
admin page carries no token-storage machinery.

## Gates

- `node src/{store,api,nav,offline}/test-runner.mjs` — 252 pass, 0 fail
  (incl. new consent regression).
- `npx tsc --noEmit` — clean. `npx expo lint` — clean.
- `pytest tests` — 1190 pass, 62 skip; 7 fail = F5 (5 corpus) +
  env gap (2 alive_core not built — no eigen on this box).
- `pytest tests/test_admin_auth.py` — 21 pass (incl. new shared-bucket).
