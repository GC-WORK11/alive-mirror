# Offline · what degrades, what lies, what the pill says

Delhi networks drop — metro tunnels, basements, congestion. This doc is the
contract between `Mobile/src/offline/**` and the screens that use it.
Rule zero (doc 02): **show a feature only when it's true.** A number shown
offline must carry its age or not be shown at all.

## The pieces (all in `Mobile/src/`)

| Module | Job |
|---|---|
| `api/cache.ts` | Typed TTL cache on expo-file-system (`Paths.document/alive-cache/`). `cacheGet` (TTL-respecting), `cachePeek` (last-good, flags `fresh`), `cacheSet`, `cacheInvalidate`, `cacheAgeS`, `cacheClear`, `cacheKeys`. |
| `offline/net.ts` | `fetchCached(url, {ttlMs, key?, fetcher?, timeoutMs?})` — network-first with 6 s abort → cache+`{stale:false}` on success → cached copy + `{stale:true, ageS, expired}` on failure → `{ok:false}` honest null when nothing saved. In-flight dedupe per key. Emits `up`/`stale`/`down` on `onNetEvent` — that bus *is* our connectivity signal (no NetInfo dep). `probe()` = `GET /health` ≤4 s. |
| `offline/queue.ts` | Durable outbox (`Paths.document/outbox.json`) for `POST /v2/trip`. `enqueue`/`enqueueTripDonation`, `flush()` (ordered, stops on network/5xx, drops 4xx as `rejected`), cap 50 → oldest dropped + persisted `dropped` count. `wireAutoFlush()` flushes on the next `up` event — the manual seam, since NetInfo is absent. |
| `offline/status.ts` | `useNetStatus()` → `{state: "online"|"stale"|"offline", lastOkAt, staleAgeS, pending, label, refresh}`. Probes `/health` on mount and every `probeMs` (20 s) **only while not online** — zero polling cost when live. |

The pill (integrator wires it, e.g. top of the map): `label` is `""` when
live; otherwise e.g. `offline — showing last known air · 2 saved to send`.

## Degradation matrix

State per row: **fresh** (request just landed) → **stale** (serving disk
copy, age labeled) → **none** (nothing cached — honest empty/offline UI).

| Feature | Fresh | Stale (cached copy + age) | None (no cache) |
|---|---|---|---|
| Search T0 (on-device gazetteer) | always — no network | — | — |
| Search T1/T2 `/v2/search` | results stream in | n/a (not cached — recents/T0 carry it) | T0 results only; pill "offline" |
| Plan options `POST /v2/plan` (also legacy `/decide`/`/depart`) | live bands + tags | last options for same O/D (key `cacheKeys.plan`, ~100 m rounded); rows get "as of … ago" | show "can't plan without network" — no fake options |
| Turn steps `/directions` | live | last steps for same O/D if integrator caches them | nav not startable offline |
| Route strip `GET /v2/strip` | live field curve | last strip (key `cacheKeys.strip`); **live counters keep ticking** — math is local by design (doc 04 §5) | counters can't start; don't start the trip |
| Live tick `/aqi` during nav | dose ticks | last strip value continues; pill flips "stale" | dose counter freezes at last honest value — never extrapolates |
| "Delhi today" `GET /v2/city` | live totals | last summary + "as of … ago" | "no saved city data" |
| Trip donation `POST /v2/trip` | sent, outbox stays empty | n/a | **queued** to outbox; pill shows pending count; flush on reconnect |
| Legacy donations `/observe`, `/report` | sent | n/a | same outbox (`enqueue`) or honest drop — never a silent success |
| `/community`, `/reports`, `/fires`, `/blackspots` layers | live | cacheable via `fetchCached` if a lane wants it | layer hidden, not an empty layer pretending |
| Map tiles | MapLibre runtime cache | its own cache — out of our scope | grey grid, not our bug to mask |
| Ledger, recents, saved places, scheduled reminders | always — on-device | — | — |

## TTL guidance (set at call site, not baked in)

| Data | `ttlMs` | Why |
|---|---|---|
| `/v2/city` | 30 min | city stats move slowly |
| `/v2/plan` options | 15 min | bands drift with the field; older than that, say so loudly |
| `/v2/strip` | 24 h | route_ids die server-side in 1 h, but a dead strip only matters for refresh — the *samples* stay a truthful "last known" |
| field/`/aqi` | 10 min | air moves fast — expired flag should show quickly |

`expired:true` on a stale result = past its TTL: show it dimmer, with the
age. `stale` within TTL: normal "as of … ago".

## Honesty rules the integrator must keep

1. `fetchCached` result `ok:false` → render the feature's empty text, never
   a placeholder number.
2. `stale:true` → the age (`ageS`) appears next to the number. "about
   0.4 cigarettes" becomes "about 0.4 cigarettes · 40 min ago".
3. The donation outbox is bounded and counted — if `droppedTotal() > 0`
   the settings/data-sharing line can say so. Dropping silently is the
   only true failure mode.
4. Never call `probe()` on a timer while online — requests themselves are
   the signal; polling burns the same data plan that just came back.
