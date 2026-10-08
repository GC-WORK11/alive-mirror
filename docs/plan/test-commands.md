# test-commands — nav engine unit tests (feat/r4-testnav lane)

Real unit tests for the Phase-4 nav engine math (Alive). New files
only — no engine source was modified.

## Run

```bash
cd Mobile && node src/nav/test-runner.mjs
```

Requires Node ≥ 22.15 (`module.registerHooks`; this repo pins nothing —
Node 22.23 verified). No extra dependencies: the tests run on node's
built-in `node:test` + type stripping, so they execute against the real
`.ts` sources, not a transpiled copy.

Equivalent ad-hoc single file: `node --test` does NOT work alone — the
app's `moduleResolution: bundler` means imports are extensionless, which
node ESM won't resolve. `test-runner.mjs` installs a resolve hook that
retries relative specifiers with `.ts` appended and stubs `react-native`
(minimal `Platform.select`) so `src/api/reroute.ts` → `shell/net.ts`
loads in node. It then imports every `src/nav/*.test.ts` in-process;
`node:test` auto-runs them and exits non-zero on failure.

## Typecheck

```bash
cd Mobile && npx tsc --noEmit
```

Clean. Each `*.test.ts` carries `/// <reference types="node" />` so
`node:test` / `node:assert` resolve without a tsconfig `types` edit
(tsconfig is outside this lane's file ownership).

## Coverage map

| Spec item | File | What's covered |
|---|---|---|
| 1. Strip interpolation | `strip.test.ts` | `stripCumM` chunk accumulation + clamps; `fieldAtAlongM` lerp at t=0.25/0.5, knot-exact, uneven spacing, `d<0`/`d>length` clamping, single-sample strip, empty strip, per-edge null propagation |
| 2. Off-route detection | `offroute.test.ts` | `OffRouteTracker`: 2 fixes don't fire, 3rd does, strict `>40` boundary, single on-route fix resets streak, `reset()`; plus `snapToPolyline` offset/along/heading and `havM`/`flattenCoords`/`polylineLengthM` |
| 3. Arrival | `offroute.test.ts` | `ArrivalTracker`: `≤60 m` × `2` consecutive fixes fires, boundary `60` counts, `60.1` resets, tracker re-fires each in-radius fix (see finding F2) |
| 4. Counters | `counters.test.ts` | 1 Hz dose integration `C·ME·VE·dt` per edge, measured-dt halving, `dt≤0` no-op, null-conc honesty, cMid edge fallback, vehicle `ef·v/1000` vs idle floor, PM idle share, `travelledM` accumulation |
| 5. Reroute trigger | `reroute.test.ts` | mocked `fetch` captures `POST {api}/v2/reroute` body (`route_id`, `at`/`from`, `to`, `mode`); response normalization (bare/`option`/`route_geojson`/`duration_s`); null on http/network/payload failure; tracker→request integration: 0 calls at 2 fixes, 1 call at 3 with live fix as origin |
| 6. Emission factors | `counters.test.ts` | cold-start `1+COLD_UPLIFT·(1−km/cold_start_km)` taper scripted over a 4 km trajectory (expected sum 4.525 g), occupancy divisor (+0 treated as 1), per-pkm shared-mode path proving idle/cold/occupancy are ignored |

## Not covered (deliberate)

- `useNavEngine` itself is a React hook owning `expo-location` +
  MapLibre refs — it can't render in node and there is no RN test
  renderer in the project. Covered indirectly: every pure helper it
  calls is tested here.
- `REROUTE_COOLDOWN_MS = 15000` (engine.ts:27) and the `arrivedRef`
  fire-once guard (engine.ts:184) are private hook internals — no
  injectable seam. Their inputs (tracker semantics) are tested.
- `fetchStrip` pulls `expo-file-system` through the offline cache —
  heavier than the react-native stub justifies.

## Findings (reported, not fixed — engine untouched)

- **F1 — `travelledM` only accrues when an emissions curve exists**
  (counters.ts:85-88, `if (!curve) return` precedes the odometer
  update). On strip fetch failure the engine keeps ticking with
  `strip = null` (engine.ts:143-146 "counters-frozen" state), so the
  arrival receipt's `distanceKm` (engine.ts:193) reports **0** even
  though the user moved and GNSS fixes kept flowing. Dose staying 0 is
  intended honesty; distance 0 looks like an oversight.
- **F2 — arrival fires on the *second* in-radius fix, not the first**:
  `ARRIVE_FIXES = 2` (offroute.ts:15). Mission phrased it as "within
  60 m → arrival"; actual spec is 2 consecutive fixes ≤60 m. Tracker
  returns `true` on *every* fix once the streak is ≥2 — the fire-once
  property comes from the hook's `arrivedRef`, not the tracker.
- **F3 — `flattenCoords` duplicates the shared vertex** where
  MultiLineString legs join (offroute.ts:31-42). Documented as the
  intended approximation; it creates a zero-length segment in
  `polylineLengthM` (harmless) and a possible duplicate step boundary.
- **F4 — `OffRouteTracker.update` re-fires on every fix at streak ≥3**.
  Combined with the 15 s cooldown this is the documented retry path,
  but note a *successful* reroute relies on `offRef.reset()` inside the
  hook — if `postReroute` returns geometry `null` (usable payload minus
  geometry), the engine resets nothing and will re-POST after cooldown.
