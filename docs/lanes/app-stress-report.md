# App-stress lane report — apk-v4 adversarial drive

- **Build:** `alive108-b4a96d2.apk` (release, universal ABIs)
- **Rig:** Pixel_7 AVD, android-35 x86_64, swiftshader, adb root, `tcpdump` on `any` (port 80), full logcat
- **API:** live `http://65.2.28.40` (ELB) — healthy the whole session; one transient plan failure noted below
- **Drive time:** ~55 min of hostile input (nav churn, connectivity kill, consent flips, locale flips, lifecycle, memory, rapid-fire)
- **Session log:** PID stable (3899) through every torture pass until the deliberate force-stop; zero FATAL/ANR/SIGSEGV/ReactNativeJS errors in logcat

## Findings

| # | Sev | Surface | Finding | Repro | Evidence |
|---|-----|---------|---------|-------|----------|
| F1 | **HIGH — fixed this commit** | nav engine (`engine.ts` odometer arrival) | Any fix whose nearest route point is the destination vertex completes the trip instantly — `routeLen - alongM <= ARRIVE_M` fires on the *clamped* projection while `snap.offsetM` is never inspected, and the check runs **before** the off-route counter so it never even registers as off-route. 6/6 repros. | Feed a fix ~1.1–1.9 km off the corridor (mine sat near CP while the cached route ended at India Gate) → tap Start → "You're here" receipt in <1–5 s, distance **0 km**, dose booked, trip logged. | [clip](https://app.devin.ai/attachments/91181dec-009b-4c9b-a61d-c0fdcf37b49f/churn1_fix.mp4), [receipt](https://app.devin.ai/attachments/6766e8bf-2c1b-49e4-a907-ced03a822346/x1_nav_3s.png), wire proof: `POST /v2/trip {distance_km:0, duration_s:37, trajectory:[]}` at 22:26:30 in [net4.pcap](https://app.devin.ai/attachments/91ed92c9-34fb-41fc-899f-e9d53c3ff717/net4.pcap) |
| F2 | **MED** | ledger (`store/ledger.ts` `DEDUPE_MS = 10 min`) | Dedupe keys on `from`+`to`+`vehicle` **names** and keeps the *first* entry. Two real trips silently vanished: the 1.8 km / ≈1.1 µg ended-early trip (22:45, merged into a phantom 0-km entry at 22:36) and the 2.5 km / ≈0.7 µg Hindi trip (22:55, merged into the 22:51 entry). Locale-fragile too — entry 4's `from` was stored as "सेंट्रल दिल्ली" while the earlier ones say "central Delhi", so the same physical trip keys differently after a language flip. | Two trips, same O&D, <10 min apart → second never appears in ledger or week totals. 9 actual trips → 4 rows. | [ledger screenshot](https://app.devin.ai/attachments/e6d327b8-a804-4d22-b703-a94f68907623/s38_ledger2.png); `ledger.json` pulled via adb (4 entries vs 9 trips) |
| F3 | **LOW** | nav chrome | Offline banner renders **under** the turn instruction card — only its tail ("…ing again") peeks out during nav. | `svc wifi disable && svc data disable` mid-nav; banner appears ~35 s in (2-miss debounce) but is occluded. | [s18_off_35s.png](https://app.devin.ai/attachments/fa45b45a-303f-4919-ba4e-d5c9b370ec92/s18_off_35s.png) |
| F4 | LOW / env | compare → plan | One transient "दोनों जगहों के बीच कोई रास्ता नहीं मिला" toast, self-recovered ~8 s later when the plan landed. Could not distinguish API hiccup from first-request race — surfaced honestly either way. | Pick a saved place right after cold relaunch. | [s40_noroute.png](https://app.devin.ai/attachments/8239c67c-358f-4962-96ad-ec9f348fc978/s40_noroute.png) |
| N1 | note | planning origin | Trips planned from the **launch-time fused position**, not the freshest fix — `getCurrentPositionAsync(Balanced)` serves last-known. Emulator-grade quirk (GMS caches aggressively) but plausible on real devices returning stale last-known. | `emu geo fix` updated position, then Start → `/v2/plan` body still carried the old origin coords. | pcap plan bodies |
| N2 | note | server | `/v2/trip` accepted `distance_km:0, duration_s:37, trajectory:[]` with `{"stored":true, "ledger_recorded":true}` — no plausibility floor. Phantom trips pollute the collective. Worth a server-side sanity check (min distance/duration/speed). | Consequence of F1. | pcap response body |
| U1 | UNTESTED | lifecycle | True LMK OOM kill — `am send-trim-memory` reaches COMPLETE but cannot force a real low-memory kill of a foreground process on this AVD. | — | — |
| U2 | UNTESTED | positioning | Real-GPS multipath/jitter under a flyover, and iOS — emulator fixes are clean injects. | — | — |

## PASS list (what survived the poking)

- **Offline degrade/recovery:** wifi+data killed mid-nav → "can't reach the server — trying again" ~35 s later, counters kept accruing, no hang; reconnect → banner cleared, trip resumed (ETA kept ticking).
- **Consent mid-flow:** sharing OFF → receipt says "kept on this phone only" and **zero `/v2/trip` on the wire** (pcap-verified); ON again → donation resumed (`POST` confirmed, `stored:true`, server discards raw trajectory — privacy pipeline is real).
- **Locale EN→HI mid-session:** every reachable surface clean — sidebar, home, search, compare, nav turn card, receipt, vehicle wizard, ledger. No clipping, no stale-English keys; proper nouns correctly stay Latin ("India Gate", street names in turn cues).
- **Lifecycle:** 60 s background mid-nav → resume: trip honest, position advanced from the newest fix only (watcher paused properly, no teleport artifacts). Force-stop mid-nav → clean relaunch to home with live data. Portrait locked in `app.json` — no landscape surface exists to break.
- **Sheet churn ×20** (sidebar/search/compare/steps open-close): single-instance sheets, no duplicates, overlays consistently render above the map — D1 elevation fix holds.
- **Memory:** RUNNING_LOW/CRITICAL trims inert; COMPLETE while backgrounded → full state recovery, no white-screen.
- **Rapid-fire:** keyboard-mash garbage into search → honest empty state ("कोई जगह नहीं मिली"), no crash; double-tap result row → single compare sheet; 7-tap vehicle-class storm → one coherent wizard instance, backs out without saving junk.
- **Honest end-to-end arrival:** fed fixes walking the actual polyline → real "आप पहुँच गए।" arrival with 3.9 km logged — arrival path works when fixes are truly on-route.
- **Receipt copy is honest:** "Trip ended." vs "You're here." correctly distinguished; donation line matches what actually hit the wire ("kept on this phone only" ↔ no POST; "added anonymously…" ↔ POST).

## Fix committed this lane

`Mobile/src/nav/engine.ts` — odometer arrival now requires `snap.offsetM <= OFF_ROUTE_M` (the fix must be on the corridor, not just near the end vertex along-track). Verified with the app's own snap math on the real 134-point polyline:

| fix (lon,lat) | alongM | offset | arrive before | arrive after |
|---|---|---|---|---|
| 77.226, 28.624 | 3981 | 1229 m | **TRUE (bug)** | false |
| 77.221, 28.629 | 3981 | 1887 m | **TRUE (bug)** | false |
| 77.228, 28.623 | 3981 | 1109 m | **TRUE (bug)** | false |
| 77.2114, 28.6103 | 2119 | 1 m | false | false |
| at end vertex | 3981 | 0 m | true | **true** |
| 45 m off at end | 3981 | 39 m | true | **true** |

Honest arrivals preserved on both paths (odometer on-corridor ≤40 m; `ArrivalTracker` proximity ≤60 m raw ×2 fixes covers off-corridor-at-dest). `npx tsc --noEmit` clean; `node src/nav/test-runner.mjs` 38/38 pass; `npx expo lint` shows 1 pre-existing `import/no-unresolved` false-positive on `src/map/cam.ts` → `expo-device` — identical on the clean tree (module installed, v57.0.2; resolver nit, not a break).

## Verdict

A judge poking it for ~55 minutes finds: **one real break — every trip "arrived" the instant a fix snapped nearest the destination vertex** (fixed here), a ledger that silently forgets your second trip within 10 minutes, and an offline banner that hides behind the turn card. Everything else — offline, consent, Hindi, lifecycle, memory, input storms — degrades honestly and never crashes.
