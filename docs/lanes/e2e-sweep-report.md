# e2e-sweep — device-honest full drive, iOS sim

Lane: e2e-sweep (test lane — no code changes). Rig: iPhone 17 sim `EDD9B083` iOS 26.5,
dev client Debug (RN-from-source, patch active) built from `base/v2` @ `1f188e9`,
Metro `EXPO_PUBLIC_API_URL=http://65.2.28.40`. Prod server build `06919cac` (`:225`).
Prod ground truth curled at ~15:00 UTC 8 Oct (`~/e2e-sweep/prod_*.json` on the lane box);
the field drifts ±2–4 µg between snapshots — diffs below allow for that.
Sim clock = UTC (not IST) throughout — see TZ finding.

## Test gates (real counts, all at HEAD)

| gate | command | result |
|---|---|---|
| store | `node src/store/test-runner.mjs` | **98/98 pass** |
| nav | `node src/nav/test-runner.mjs` | **100/100 pass** |
| api | `node src/api/test-runner.mjs` | **37/37 pass** |
| offline | `node src/offline/test-runner.mjs` | **16/16 pass** |
| search/t0 | `node src/search/test-runner.mjs` | **12/12 pass** (incl. prebuilt-vs-lazy parity, 46s) |
| types | `npx tsc --noEmit` | **clean, 0 errors** |
| lint | `npx expo lint` | **clean** |
| i18n static | key-parity script | **989=989 keys en↔hi**; only legit shared tokens identical (year ranges, "PUC", templates); zero hardcoded JSX strings (wordmark only) |

263/263 node tests green. No red suite, no skipped, no todo.

## Issues (severity = P0 lie/crash · P1 real defect · P2 misleading/degraded · P3 polish)

| # | feature | what I did | result | evidence | severity | file:line |
|---|---|---|---|---|---|---|
| 1 | CountUp dose readout | watched hero + route-option cards across offline cold start, map→home transitions, options sheet | Headline renders literal **"0 µg"/"≈0"** while siblings compute real values: hero 0 for ~25–30 s on offline cold start, ~8–10 s on map→home, every option card ≈0 for ~60 s while its own "8–29 µg" range and "44 min" render. `useState(() => reduceMotion ? value : 0)` + rAF-starved step → on any slow JS thread the marquee dose is a false zero. Real user could read "no dose" on a 78 µg day | shots `countup-zero-option-card.png`, `countup-zero-hero-offline.png`; video r3 | **P1** | `Mobile/src/ui.tsx:96–118` (init `:101`) |
| 2 | Air-event alerts | read `events.json` seen-map + banner text + live curls | **`outlook_heavy` AND `outlook_light` both fired same day ~3 min apart** — "tomorrow ~102 vs ~71" then "tomorrow ~183 vs ~216 · lightest 11:30–3:30". 183/216 match no fetched payload (live 71/102, cached 70.8/101.5, prod 68.7/99.6). Dedupe is `seen[kind]={day,level}` per-kind-per-day — opposite-direction folds are different kinds, so a mid-day verdict flip (stale→fresh outlook, or poll variance) can emit BOTH | `events.json`; banners on rec-1 video ~8:34 | **P1** | `store/events.ts:191–198` (dedupe key), `:386–402` (fold→kind) |
| 3 | Post-wipe onboarding | delete-all → relaunch → re-consent → location page (5/5) | "turn on location" AND "not now" both ate 3+ a11y/pixel presses — no visible OS dialog, consent already persisted so only a kill+relaunch unblocked it. Possible invisible permission-dialog block or dead hit-area on the replayed gate | video r3 | **P2** | `OnboardingScreen.tsx` location page (~:400–460) |
| 4 | Kind localization | Hindi search recents + PlaceSheet | Raw `"overture:rental_service"` kind leaks on recents ("Chandigarh Travel — overture:rental_service"); PlaceSheet prints EN "airport" while the search list localized the same kind to "एयरपोर्ट" — same string localized inconsistently by surface | `placesheet-kind-en.png` | **P2** | `src/i18n` KIND_LABEL/localizeKind coverage; `PlaceSheet.tsx` kind render |
| 5 | expo-notifications | every cold launch | `ERR_NOTIFICATIONS_KEYCHAIN_ACCESS` error toast on **every** cold boot (getRegistrationInfoAsync — keychain entitlement absent on unsigned sim build). Local UN notifications still fire (real banners verified). Sim-only in Debug; needs a device/Release check to close | `gate-coldboot.png` (toast bottom), LogBox shot, Metro log | **P2** | `notify.ts` getRegistrationInfo path |
| 6 | Clock/greeting | read header | "Good morning · Delhi · Thursday · 8:33 am" while it was ~21:03 IST — device-local TZ under a Delhi label. Fine for Delhi users; misleading if a non-IST viewer/demo watches | `hindi-home.png` (सुप्रभात 9:45 vs real IST) | **P3** | HomeScreen header / `clockLabel` |
| 7 | Layer toggles | toggled fires/spots/corridors, then kill-reopen | All three flip + markers render — but selections are **session-scoped**: kill #3 reset them. If intended (lazy fetch) fine; if users expect persistence it's silent | `layers-on.png` | **P3** | `LayersSheet.tsx` state |
| 8 | Receipt expander | toggled per-trip receipt | a11y expanded/collapsed flips but renders no visible detail change — expander looks flat | video r3 | **P3** | `LedgerScreen.tsx` receipt expander (~:107) |
| 9 | a11y labels | read a11y tree in Hindi | a few labels stay English ("1 hour ago" style age strings); cosmetic, a11y-tree only | a11y dumps | **P3** | a11y label fns |
| 10 | seen-flag timing | read flag write times vs first paint | `welcome_seen_v1`/`coach_tour_seen_v1` write `seen:true` AT MOUNT before user finishes — deliberate ("never re-show outranks finish"), but a kill between mount and first paint loses the tour forever | Documents file ts | **P3** (by design — noted) | `App.tsx:776`; `CoachTour.tsx:219` |

## Verified PASS — everything else checked, honestly working

| feature | what I did | result | evidence |
|---|---|---|---|
| Consent gate | Next×3 → "Share trips anonymously" → iOS loc dialog | `consent.json {seen:true, sharing:"on"}`; prompt fired once; **no replay on any relaunch** | `gate-coldboot.png`; Documents |
| Gate hero number | read page-0 ~70 µg/m³ "moderate" | = prod `/v2/city` mean 70.6 / `/aqi` ambient 68.3 — live, not canned | shot 01 |
| Home hero | diff vs live `/aqi` @CP | 71 µg/m³ (prod 68–75 drift) · "same air = AQI 159" (prod us_aqi 158–159) · "4.7× WHO" (71/15 ✓) · "nearest monitor ~1.6 km" (prod exactly 1.6) · "16 fires belt" (prod belt_fires 16) · age ticks "1→15 min" | shots 06–09 |
| Empty dose | fresh install | "your count starts once the phone logs its first hours" — honest zero | shot 06 |
| Dose accumulation | 3 kills + 65 min | 36→42→50 µg accumulating ~0.76 µg/min, "1 घंटे 5 मिनट गिने" persists | `hindi-home.png` |
| DelhiToday | diff every figure vs `/v2/city` | hero 1160 µg = `breath.day_inhaled_ug.mid` EXACT · 5.4× WHO (1160/216) · species table = live means · "15% below 10-yr avg" = vs_now −14.7 · forecast bars = `next_hours` · why/cause_note verbatim · provenance honest | shots 15–17b |
| Community | DelhiToday with own≥1 | "पिछले 7 दिन · 54 यात्राएं"=obs_total · "6 यात्राएं · 6.3 किमी · ≈9 µg · ≈2.2kg छोड़ा"=today · mode split 80/6/15 = 43/3/8 · k-anonymity gate hides totals until first own trip (verified own===0 empty card first) | `community-hindi.png` |
| Search | query "connaught" | 11 live results, real places+distances (Photon tier — different geocoder than `/v2/search`, both real); honest empty state, no fake recents | shots |
| PlaceSheet | select IGI | "air there now ~76 µg/m³" local read plausible vs prod 68–90; honest absence of share/copy (clipboard empty, no dead button) | `placesheet-kind-en.png` |
| Trip plan CP→IGI | Directions → 14 options | distinct honest dose mids (car ≈16–23 / auto ≈47–60; control `/v2/plan` mids 12–45 same corridor); felt multipliers local-computed; km/ETA sane | a11y tree |
| Depart strip | options sheet | "lightest ~tomorrow 12am ~12 µg · ~20% less" = prod `/depart` best +16h/pct_less shape | shots |
| Nav chrome | started nav, read meta, bg 65 s | "44 मिनट · 24.5 किमी · 10:36 पहुँचें · ~2 मिनट रुके थे" — arrive AND paused render full (newline-truncation fix 519f9ff held); dose kept counting through fix-gap; arrive shifted honestly | `nav-meta.png` |
| Nav no-fix state | sim loc not reaching watch | "no location — counting the air where you started" — honest, no fabricated position | video r1 |
| Nav end | खत्म करें with no movement | "शुरू होने से पहले ही खत्म — <100 m, कुछ गिना नहीं गया" — no fabricated trip | video r3 |
| Vehicle wizard | Settings → मेरी गाड़ी | full flow car→petrol→2017-20→PUC-skip → `vehicle.json {"cls":"car","fuel":"petrol","year":"y2017_2020","puc":null}`; row updates | Documents |
| Notifications | armed सुबह का हवा-अलर्ट + air-event alerts | real iOS banners fired (stagnation "19× stiller", GRAP, fires "9× stiller — smoke will linger · 16 fires"); arm is honest async (~15 s perms→fetch→schedule, reverts on fail); all 7 toggles match settings.json | `notif-banner.png`, events.json |
| Rate → feedback | 4 stars → भेजें | real POST fires; first attempt transient-failed with honest "नहीं भेजा जा सका" (stars kept) → retry → "शुक्रिया"; endpoint curl-verified 200 `stored:true` | `rate-err.png` |
| Share↔consent | Settings गुमनाम toggle off→on | consent.json flips `sharing:"off"`↔`"on"` — "one tap undoes it" verified | Documents |
| Hindi runtime | toggle + walked every surface | every app-composed surface in Devanagari (सेटिंग्स/कहाँ जाना है?/हवा का नक्शा/आज की दिल्ली/यात्राएँ/आग/भेजें/शुक्रिया); latin place-names legit (server-fed localizeKind); persists across kills | `hindi-home.png`, `hindi-home-kill3.png` |
| NO-NETWORK (pf) | blocked API+tile+photon IPs, cold relaunch | offline basemap pack renders · honest chip "सर्वर से संपर्क नहीं — फिर कोशिश हो रही है" · cached field+dose persist · ambient chip honestly ABSENT not faked · search→honest "कोई जगह नहीं मिली" + local fallbacks · self-recovers on unblock w/o relaunch | `offline-search-hindi.png` |
| bg→fg | home 32 s, return | clock advances, dose/map intact, no freeze | video r3 |
| Kill-reopen ×3 | terminate+launch | no gate replay, settings/lang persist, dose intact | `hindi-home-kill3.png` |
| Outside service | loc 28.05,77.05 + 25.5,77.5 | beyond-edge point shows honest extrapolated ~81 (prod 80.8); null point → honest "हवा के नक्शे से बाहर — यहां रीडिंग नहीं" chip | `outside-chip.png` |
| Layers | fires/spots/corridors on | all 3 flip + markers appear (fires NW of viewport — honest, not fake-placed) | `layers-on.png` |
| Delete-all | सेटिंग्स→मेरा डेटा मिटाएँ→confirm | consent/settings/vehicle/ledger/daylog/places/events wiped + cache emptied; daysum.json keeps only zeroed 6-day scaffolds (no personal data); gate replays exactly once on relaunch → fresh home, honest zero | `post-wipe-fresh.png` |

## Not covered (honest leftovers)

- Scripted along-route `simctl location` walk — off-route detection + reroute not exercised end-to-end.
- Corridors layer pin-vs-polyline differentiation unverified; receipt-expander detail render needs a closer look (flat in a11y).
- Post-wipe location-page freeze (P2 #3) needs a repro with OS-dialog state check.
- Android untouched (no KVM on this box); device (non-sim) build unverified — the SIGSEGV patch is sim-gated, and the keychain toast (P2 #5) may be absent on a provisioned device.
- The "183/216" alert numbers match no fetched payload — transient server flip suspected; a server-side outlook-history check could pin it.

## Verdict

Ship-shape on honesty: **zero fabricated data found** — every number traced to a live
endpoint or a local derivation, every empty/fail/offline state degrades honestly.
Two P1s worth a lane: the CountUp false-zero (real zero rendered to users) and
opposite-direction alert pairs. Nothing blocks demo.

Evidence dir: `docs/lanes/e2e-sweep-shots/` (14 shots). Full agent log:
`~/e2e-sweep/agent-notes.md` on the lane box; recordings on the box
(`~/screencasts/rec-fe3795b8…`, `rec-6462d032…`, `rec-round3-sweep`).
