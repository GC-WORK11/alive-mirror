# Lane — offline-verify report (real Android, KVM)

The audit could never test real offline (sim radio can't toggle). This lane
proved the venue-dead-wifi story end-to-end on a hardware-accelerated Android
emulator: pack downloads, every surface degrades honestly, the pill debounce
neither flashes nor sleeps, the app recovers live without restart.

- **Rig**: KVM child session `f8c71991f6974f33bb957f47fdd1ebd8` — AVD `demo`
  (Android 35, google_apis x86_64, SwiftShader, `-no-window`), `adb root`.
- **Build**: debug APK at `c06f478` (`debuggableVariants=[]` local-only, never
  committed), `EXPO_PUBLIC_API_URL=http://65.2.28.40`, sha256
  `d06a18968abeb6d25d7bf0828a7eb8b44d5fb353dbba9af415cf4b4cf074b0ec`,
  237,281,814 B. Bundle holds prod URL ×1, zero dev hosts.
- **Caveat**: SwiftShader + debug inflate all timings — treat as upper bounds.
- **Evidence**: `docs/lanes/offline-verify-evidence.md` (sqlite dumps, flap
  timelines, verbatim strings) + `docs/lanes/offline-verify-shots/` (16 shots).
  Numbers below were re-verified by the parent against code/prod where marked
  `✓indep`.

## Pack — PASS `✓indep`

`su 0 sqlite3 /data/data/com.anonymous.app/files/mbgl-offline.db`:

- `region_tiles = 744` — recomputed from the region row's own bounds
  [28.2,76.8,28.95,77.9] z9–13: z9=6 + z10=16 + z11=48 + z12=154 + z13=520
  = **744 exactly** `✓indep`.
- `region_resources = 297`, `tiles = 747`, regions row verbatim
  `delhi-ncr-z9-13-r2` style `http://65.2.28.40/v2-light.json` `✓indep`
  (matches `src/map/tileWarm.ts` PACK_NAME + `mapStyle`).
- Zero `Mbgl-HttpRequest`/`Unable to parse resourceUrl` in logcat lifetime.
- alive-cache populated: v2_city, airfield_grid, plan, v2_strip/outlook/
  daycurve entries all present.

## Verdict per surface (radios off 21:03:58 → 21:16:36)

| Surface | Verdict | Evidence |
|---|---|---|
| Home offline | PASS, w/ caveat C4 | Last-good hero held ("33 µg good · 15% of daily limit · outside ~66 · moderate"); dose display froze honest at "48m counted" (no fake tick — reconciled to "1h 2m" on reconnect) `✓indep shots 01/12/13`. Caveat: **zero visible offline affordance on the resting surface** — pill is under the home sheet by design and the hero's outside-line shows no age (see C4) |
| Air map offline | PASS | Full basemap geometry from pack at ~z14 viewport (CP radial), air-field tint + legend "redder = worse air right now · 54 live stations · air reading: 6 min old" — cached + labelled `✓indep shot 02`. Panned ~2 viewports clean (shot 03). z14+ overzooms z13 vector tiles — geometry persists, no blank (documented z13 cap per offline.md, shot 04) |
| Search offline | PASS | "karol" → 6 gazetteer rows w/ distances 2.4–3.6 km; "connaught" → CP; recents persist; no spinner-hang `✓indep shot 05 + t0 code path` |
| Plan — new dest | DEGRADED-honest | "couldn't load the ways there — check the connection" + try-again (`plan_failed` strings.ts:514 verbatim `✓indep shot 06`); no fakes, no hang, re-try re-fails honestly |
| Plan — cached O/D | PASS | Full compare served offline (Your location→CP): "Car (AC) ≈1µg least smoky · 1.28km · 2min", tomorrow-window, air-by-hour strip, freshness chip "22 min old" ticking (shot 07) |
| Delhi Today | PASS | Cached city payload verbatim (1376 µg poor, 6.4× WHO, pollutant table, AQI 158) + stale chip "older data — reconnecting" (`cityStale` strings.ts:231 `✓indep shot 08`) |
| Trips / Settings | PASS | Honest empty ledger copy; share toggle flipped and persisted (a11y checked→false→true). Delete-my-data untouched per spec (shots 09/10) |
| Venue test — cold relaunch offline | PASS | `am force-stop` + cold start → honest home+map in 938 ms; stale pill form in a11y (shot 11) |
| Recovery | PASS | Pill cleared ~20–40 s after TCP actually returned (rig reprovision lag 60–90 s is QEMU, not the app); hero updated in place 33→43 µg, 48m→1h2m counted — elapsed gap reconciled, no restart `✓indep shot 13` |
| Outbox | PASS | No queued writes; "· N waiting to send" suffix never appeared |
| Crashes in offline window | **0** | FATAL/SIGSEGV/SIGABRT/ANR grep clean (lifetime 2 = the pre-fix crash this lane fixed at edc4666) |

## Debounce (STEP 4) — PASS w/ caveat C3

Graded flaps `svc wifi/data off → on`: **10 s, 25 s, 45 s → pill shown in
0 windows** (3/3, 8/8, 14+4 frames + a11y greps clean; shots 14/15/16).
Sustained off: apiOk-false pill "can't reach the server — trying again" at
~t+37 s (2 /health misses at 15 s cadence, App.tsx:475-479), then the stale
form "offline — showing last known air · updated 12 min ago" after 3 read
fails (status.ts:60 FAILS_BEFORE_OFFLINE; age suffix ticks, strings.ts:475-477
`✓indep`).

*Note: a11y-based flap evidence stays valid on home — uiautomator exposes the
sheet-covered pill node (proven: stale string in the 21:15 dump while the same
frame shows no pixels). Pixel diffs alone on home could never have seen a pill
(C4) — both signals were used.*

## Bugs fixed this lane (all pushed to base/v2)

| Commit | Fix | Verified |
|---|---|---|
| `edc4666` | `src/map/style.ts` — React-mounted gesture-label copies carried raw numbers in array-typed MLRN layout props (icon-padding/-offset/-translate, text-offset/-translate, icon-text-fit-padding) → `UnexpectedNativeTypeException` FATAL at first map mount. Wrapped `[v]` on the React copy path only | Map renders + pans/zooms on device `✓indep diff reviewed` |
| `c06f478` | `src/components/shell/net.ts` `posNow()` — `getCurrentPositionAsync(Balanced)` returns null when the fused provider can't serve a fresh fix though a valid last-known exists → plan flow dead-ended on "couldn't get your location". Falls back to last-known with home-read's guards (in-NCR, ≤15 min). All 5 Balanced sites (useShellFlow.ts:171/:406, App.tsx:652/:917/:939). The /aqi poll's own getCurrentPositionAsync at App.tsx:548 intentionally stays raw — last-known-first order, gated by `freshGps` | Diff reviewed `✓indep`; device-verified Your-location→compare |
| `a5b30c9` | Parent fix — `c06f478`'s new `expo-location` import broke all 4 node test-runners (`ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING`; store 84→16, nav exit 1). Stubbed `expo-location` in store/nav/api/offline runners | 193/193 tests pass again `✓indep ran` |
| `f366d49` | This evidence pack (181-line md + 16 shots) | — |

## Catalogue — bigger issues (observed-vs-expected, file:line, NO refactor)

1. **"Where from?" can't take typed place picks** `✓indep` — map tap
   (App.tsx:864), long-press (:870) and search select (:906) all hardcode
   `pick(p,"to")`; `pick`'s own `which ?? editWhich` honors the armed slot
   only when `which` is omitted (your-location at :924 does it right;
   saved-place navigate at :964 also hardcodes "to" — destination-intent by
   design, fine). Observed: with `editWhich==="from"` (e.g. after
   `locPickFailed`), typing a FROM place still lands it in `to`. Expected:
   drop the explicit `"to"` so `editWhich` is honored at the three typed-pick
   sites — deliberate UX-flow call, hence catalogued not one-lined.
2. **`to` persists after a completed plan** — after the online CP flow,
   reopening "Where to?" showed Connaught Place still loaded as `to`
   (compare retained). Expected per offline.md fresh-start wording: clear on
   flow end. Minor drift.
3. **`/health` ping has no timeout** `✓indep` — `App.tsx:475` bare
   `fetch(url, {keepalive:true})`, no AbortSignal. On blackhole/stall-type
   dead nets (not the ENETUNREACH this rig produced) detection latency is
   unbounded — apiOk needs 2 *completed* misses. Observed: the 45 s flap
   counted 0 misses because in-flight connects finished on restore. Suggest
   `AbortSignal.timeout(~5000)` to match the documented 15 s cadence intent.
4. **Home surface is offline-blind (design gap, new)** `✓indep` — the pill
   mounts at App.tsx:1144 *before* `HomeScreen` (:1179; `ss.home` is opaque
   `flex:1` over the map) → "below sheets" z-order hides it on the resting
   surface; a11y still exposes it. Meanwhile the hero's field age rides
   `mapField` (App.tsx:799-808), a memo keyed on `aqiField` identity — with
   reads failing, it never recomputes: `age_s` and `stale` freeze at
   last-good (the known frozen-age quirk's offline face — the map's "air
   reading: 6 min old" freezes the same way and never crosses
   `stale_after_s=2700`). Net effect observed on device: 13 min into dead
   wifi the home still read "48m counted · outside ~66 · moderate" with no
   pill pixel, no age line, no stale chip. The only honest ticker (pill's
   "updated N min ago") was under the sheet. Worth a product call: home may
   want its own stale affordance (e.g. surface `airAgeLine` computed
   wall-clock, or let the pill peek above the home sheet specifically).
5. **Frozen "counted" display** — same mechanism, already-folded into the
   verdict: dose display held "48m" for the whole window then jumped to
   "1h 2m" on reconnect — *honest* reconciliation of elapsed time, no fake
   ticking. Fine as-is; flagged only so the static number isn't misread as
   a bug.

## Rig quirks (not app bugs)

- QEMU user-net: ICMP always fails — use TCP `nc` to test connectivity;
  `svc … off` kills routes instantly (ENETUNREACH), re-enable takes 60–90 s.
- `emu geo fix` won't advance the fused provider unless an app holds a GPS
  request — launch Google Maps once first.
- SwiftShader draws no basemap text labels; eats taps during settle
  (retap / slow swipes); `uiautomator dump` can go stale vs screencap.
- `input text` needs the EditText focused first; space = `keyevent 62`.

## Bottom line

The venue story holds: pack real (744/297/747), every surface degrades
honestly or works from cache, zero crashes offline, clean recovery, debounce
doesn't flash. The one thing a judge would *see* missing: on the resting home
sheet there is no visual "this is old data" tell while offline (C4) — a11y
has it, pixels don't.
