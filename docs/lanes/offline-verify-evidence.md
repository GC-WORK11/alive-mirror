# offline-verify lane — Android emulator evidence (KVM rig)

Lane goal: prove the venue-dead-wifi story end-to-end on a real emulator —
pack downloads, every surface degrades honestly, the pill debounce neither
flashes nor sleeps, and the app recovers live without restart.

Rig: AVD `demo` (Android 35, google_apis x86_64, SwiftShader, 2048 MB,
`-no-window`), `adb root`. APK: debug build with `debuggableVariants = []`
local-only + `EXPO_PUBLIC_API_URL=http://65.2.28.40` baked.

- APK sha256 `d06a18968abeb6d25d7bf0828a7eb8b44d5fb353dbba9af415cf4b4cf074b0ec`
- 237,281,814 bytes; bundle contains prod URL ×1, zero dev hosts
- Built at commit `c06f478` (includes this lane's two fixes below)
- Debug-build caveat: all timings are SwiftShader upper bounds.

## Pack (verified from the app's own sqlite)

`su 0 sqlite3 /data/data/com.anonymous.app/files/mbgl-offline.db`:

```
region_tiles   = 744        (expected exactly 744: z9=6 z10=16 z11=48 z12=154 z13=520)
region_resources = 297
tiles          = 747
regions row    = {"bounds":[28.2,76.8,28.95,77.9],"style_url":"http://65.2.28.40/v2-light.json","pixel_ratio":2.625,"min_z":9,"max_z":13,"name":"delhi-ncr-z9-13-r2"}
```

logcat: zero `Unable to parse resourceUrl` / `Mbgl-HttpRequest` errors lifetime.

alive-cache dir populated: `e0f34216-v2_city.json`,
`5faa142a-airfield_grid_28_pm2_5.json`, plan
`858dac62-217_28.632_77.219_car_24.json`, `e8f1883d-77.217_28.632_77.219_car.json`,
`v2_strip_*`, `v2_outlook_*`, `v2_daycurve_*` entries present.

## Online ground truth (STEP 3, before radios off)

- `curl /aqi?lat=28.6315&lon=77.2167` → pm25_ambient 63.3, us_aqi 155,
  belt_fires 16 → app showed "outside ~63 · moderate", "AQI 155",
  "4.2× WHO limit" (63.3/15), "16 fires" — PASS.
- `/v2/city` → why.line "the air is barely moving — the day's pollution is
  sitting over the city + levels still climbing"; Delhi Today "a day of
  Delhi air — 1376 µg — poor", pollutants PM10 268.7 / NO₂ 32 / O₃ 37.3 /
  CO 1090.5 / SO₂ 16.8 / US AQI 158 — rendered verbatim.
- Plan flow online: Your location (geo fix 28.6315,77.2167 ≈ CP) →
  Connaught Place → typical Delhi ride → compare "Car (AC) ≈1µg least
  smoky · 1.28km · arrive 20:57 · 2min" + "tomorrow 11:00 → ~29% less
  smoke — ping me" + "6 min old — live stations + satellite estimate".

## STEP 4 — transient flaps (`svc wifi/data off` → on)

| flap | window | pill shown? | verbatim | notes |
|------|--------|-------------|----------|-------|
| 10 s | OFF 20:58:55 → ON 20:59:09 | NO (3/3 frames clean) | — | ~200px band delta = status icons only |
| 25 s | OFF 20:59:41 → ON 21:00:06 | NO (8/8 frames clean) | — | no apiOk flip |
| 45 s | OFF 21:00:53 → ON 21:01:38 | NO (14 in-window + 4 post frames clean) | — | pings in flight when radios died appear to have completed on restore → 0 misses counted |

Verdict: debounce does NOT flash on transient stalls — including a 45 s
hold, because apiOk needs 2 *completed* misses and in-flight connects
survived the flap. Honest note: the /health ping is a bare `fetch` with
no timeout (App.tsx:475) — detection latency on stall-type outages is
unbounded; on this rig sustained-off produced fast ENETUNREACH rejects so
the pill did land (below). Worth a hard look for real-venue NAT stalls.

## STEP 5 — sustained offline walk (radios off 21:03:58 → 21:16:36)

Pill timeline: pill visible ~21:04:35 (t+37 s) — first form seen was the
apiOk-false string; after cold relaunch the stale form was present:

- `"can't reach the server — trying again"` (apiOk=false → 2 /health misses)
- `"offline — showing last known air · updated 12 min ago"` (net.state
  offline — 3 consecutive read failures; the `· updated N min ago` age
  ticks with the last-good read)

Per-surface (all screenshots in `offline-verify-shots/`):

1. **Home** — last-known hero stayed: "33 µg good · 15% of your daily
   limit · outside ~66 · moderate". "48m counted" dose counter kept
   accruing locally (no fake refresh). Pill + age visible. PASS.
2. **Air map** — full basemap from pack at ~z14 viewport incl. CP radial
   streets; air-field tint + legend "redder = worse air right now · 54
   live stations · good → severe · air reading: 6 min old" — cached field
   with honest age, not frozen-live. Panned ~2 viewports clean.
   Zoom past z13: renderer overzooms z13 vector tiles — geometry persists,
   no new detail, no blank/grey (designed tradeoff per offline.md). PASS
   (with the documented z13 cap).
3. **Search** — "karol" → 6 gazetteer rows under "Results" (Karol Bagh
   station/metro/terminal/market with distances 2.4–3.6 km). "connaught"
   → Connaught High Street, Connaught Lane ×2, Connaught Place.
   Recents persisted. No spinner-hang; rows tappable. PASS.
4. **Plan** — new destination (Karol Bagh metro, never queried online):
   `"couldn't load the ways there — check the connection"` + "try again",
   no fake options, no hang. "try again" re-fails honestly. Cached O/D
   (Your location → Connaught Place): full compare served offline —
   "Car (AC) ≈1µg least smoky · 1.28 km · arrive 21:13 · 2 min",
   "tomorrow 11:00 → ~29% less smoke — ping me", air-by-hour strip —
   with freshness chip "22 min old — live stations + satellite
   estimate" ticking. PASS.
5. **Delhi Today** — cached city payload verbatim: "a day of Delhi air —
   1376 µg — poor", 6.4× WHO line, why.line, pollutant table, US AQI 158;
   stale marker present verbatim `"older data — reconnecting"`. PASS.
6. **Trips** — "Trips — no trips yet — finish a trip and its smoke
   numbers land here" (honest local empty; no trips had completed). PASS.
7. **Settings/menu** — drawer renders; "Share anonymous trip data"
   toggle flipped OFF then back ON (checked→false→true observed in the
   a11y tree). Language toggle not exercised mid-test (would re-string
   the whole UI). PASS. (Delete-my-data NOT touched, per spec.)
8. **VENUE TEST** — `am force-stop` + `am start -W` while offline: home +
   map in 938 ms cold start, honest offline state, stale pill form
   showing "updated 12 min ago". PASS.

Crash grep (offline window only): **0** FATAL/SIGSEGV/SIGABRT/ANR.
Lifetime count 2 = the 20:15 pre-fix crash this lane fixed (`edc4666`)
plus its ANR — no post-fix crashes. (Watch the grep: case-insensitive
`anr` matches "ScanResult" Wifi lines — real count is word-bounded.)

## STEP 6 — recovery (radios ON 21:16:36)

- Emulator took ~60–90 s to re-provision TCP after `svc enable` (rig
  latency — `nc 65.2.28.40 80` first succeeded ~21:17:40; ICMP ping is
  always dead through QEMU user-net, don't use it as a signal).
- Pill cleared by ~21:18:2x — i.e. within ~20–40 s of real connectivity
  (status probe cadence 20 s). No restart — the cold-relaunched app
  already had its intervals running.
- Hero updated in place: "43 µg good · 20% of daily limit · 1h 2m
  counted · outside ~66 · moderate" — dose reconciled elapsed time
  honestly, outside value continuous with pre-offline ~66.
- Outbox: no queued writes observed (`· N waiting to send` suffix never
  appeared; ledger had no trips to donate). PASS.

## Bugs fixed this lane (pushed)

1. `edc4666` — `src/map/style.ts`: React-mounted gesture-label copies
   carried raw numbers in array-typed MLRN layout props (icon-padding,
   icon-offset, text-offset, icon/text-translate, icon-text-fit-padding)
   → `UnexpectedNativeTypeException` FATAL at first map mount. Wrapped as
   `[v]` on the React copy path only; verified map renders + pan/zoom.
2. `c06f478` — `src/components/shell/net.ts` `posNow()`:
   `getCurrentPositionAsync(Balanced)` returns null when the network/fused
   provider can't serve a fresh fix even though a valid last-known fix
   exists → plan flow dead-ended on "couldn't get your location" while
   home showed real numbers (same device, last-known path). posNow falls
   back to last-known with the same guards as the home read (in-NCR,
   ≤15 min). Applied at useShellFlow.ts:163, :383, App.tsx:652, :913,
   :936. Verified on device: Your location → compare rendered.

## Catalogue (bigger issues, file:line, observed-vs-expected — NO refactor)

1. **"Where from?" can't take typed place picks** — `App.tsx:903`
   (`onSearchSelect` → `pick(p,"to")` hardcoded) and `:860`/`:862`
   (map tap/long-press → `pick(...,"to")`). With `editWhich==="from"` the
   "Where from?" sheet still routes a selected place into `to`.
   Observed: typing a FROM place drops it into `to`; `from` is only
   seedable via Your-location row, map pick, or long-press. Expected:
   `pick(p, which ?? editWhich)` honored at all three call sites.
2. **`to` persists after a completed plan** — observed: after the online
   CP flow, reopening "Where to?" showed Connaught Place still loaded as
   `to` (compare retained). Expected per offline.md's fresh-start wording:
   destination should clear when the flow ends. Minor UX drift, not a
   crash.
3. **/health ping has no timeout** — `App.tsx:475` bare `fetch`. On
   stall-type dead networks (route blackhole, not ENETUNREACH) detection
   latency is unbounded; observed the 45 s flap produce 0 misses because
   in-flight connects succeeded on restore. Suggest an AbortSignal ~5 s
   to match the documented cadence intent.

## Rig quirks (not app bugs)

- QEMU user-net: ICMP ping to real IPs always fails — use TCP (`nc`) to
  test connectivity; `svc wifi/data off` kills routes instantly
  (ENETUNREACH) but enable takes ~60–90 s to provision TCP.
- `emu geo fix` alone does not advance the fused provider's elapsed-time
  unless an app holds an active GPS request — launch Google Maps once
  (grant its location) then emit the fix.
- SwiftShader: no basemap text labels render (geometry/colors fine);
  taps get eaten during settle — retap or slow (900 ms) swipes for
  map pans; `uiautomator dump` can go stale vs screencap.
- `input text` needs the EditText node focused first (tap its bounds);
  `adb emu`/keyevent space = 62.
- Zombie "Application Error" system window from the pre-fix crash
  persisted in the window list; non-blocking once the app was focused.
- Google Maps sign-in sheet ("Make it your map / SKIP") can surface if
  Back overshoots onto Maps in recents — SKIP it and `am start` back.
