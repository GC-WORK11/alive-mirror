# Feature-walk report — ALive·108 (iOS sim, base/v2)

**Lane:** feature-walk — "try all features and more." Full functional drive of every surface on a real device, not a code audit.
**Device:** iPhone 17 sim · iOS 26.5 (UDID EDD9B083-63F1-44E6-9A7B-0A6964CC2561), Debug dev-client, metro on :8081, prod API `http://65.2.28.40` **GET-only** (no deploy, no writes initiated; app-internal samples/ledger traffic is the app's own behavior).
**HEAD:** pulled to `e3a1183`+ (walk ran across `596ca9c`→`519f9ff`).
**Method:** feature inventory enumerated from code first (App.tsx phase machine, Sidebar, CompareSheet, all screens/sheets), then each item driven on-device via the iOS accessibility bridge + coordinate taps. Offline degradation tested by blackholing the API IP on the host (`route add 65.2.28.40 127.0.0.1`) — the sim's calls failed for real while everything else on the box stayed up. GPS driven via `simctl location` script for a real nav trip.

Legend: **PASS** works end-to-end · **DEGRADED** works with a visible honesty caveat or partial failure · **FAIL** dead/inert/wrong · **N/T** not testable on this rig.

## Per-feature table

| # | Feature | Verdict | Evidence / notes |
|---|---------|---------|------------------|
| 1 | Boot + consent gate | PASS | App cold-boots to onboarding → consent → home. |
| 2 | Home hero (dose today) | PASS | Counts up animated ("18 µg · 25% of daily limit · 44m counted"); counts **locally even with API dead** (13→18 µg while blackholed). shot `ss_ba57f2c0`. |
| 3 | Incidents card ("in Delhi's air right now") | PASS | Live "27 fires in the Punjab–Haryana belt, up from 16 over ~5.7h · air barely mixing · city avg 90→54 µg/m³ · ~6h · measured, not reported". |
| 4 | Door rows (Air map / Delhi today / Trips) | PASS | All three open their surfaces. |
| 5 | "the move" hour-arc card | PASS | "cleanest ~8:30am-12:30pm ≈53 · heaviest from ~7:30pm ≈83" + per-hour cells "hour 0..20". |
| 6 | "where it accumulated" card | PASS | 10-min dose buckets (≈5.7/≈5.4 µg) **plus per-trip attribution rows** ("Car (AC) your location → Conna… ≈0.5 µg", "Bike/scooter … ≈0.3 µg") — trips itemized in the dose. |
| 7 | Week strip → Week sheet | PASS | Opens "your lungs' calendar — ≈13 µg this week · 1 of 7 days counted", hour arc, accumulated chunks, "the air ahead" 5-day forecast. `ss_d4819965`. Taps occasionally land queued (see findings F5). |
| 8 | Week-sheet day cells → day story | PASS | Tapping "saturday 10 Oct" expands "lightest ~10:30am-4:30pm ≈81 · heaviest 12:30-2:30am & 7:30pm-12:30am · ≈127-159 µg/m³". Days with no data stay quiet (honest blank). |
| 9 | "days ahead" 5-day forecast | PASS | today 64 → monday 159, "today looks least-bad — ~64 vs ~131 across the 5-day". |
| 10 | Check-in card (breath/eyes/energy) | PASS | good/meh/rough chips select; "stays on this phone — never uploaded · the pattern needs ~7 days". Selections persist in-session. `ss_7d069f9a`. |
| 11 | Daily-limit card | PASS | "59 µg left of the 72 µg you set · sensitive profile"; profile chips general/sensitive/child switch the limit. |
| 12 | Search — typed query | PASS | "connaught plce" (phonetic-ish typo) → 10+ ranked results across categories (address/locality/hotel/college/mall/temple/police) with distances. `ss_a12e0f50`. |
| 13 | Search — recents | PASS | "Connaught Place, Delhi, 300 m" persisted and re-offered. |
| 14 | Search — "Your location" | PASS | Resolves to GPS fix (28.6315,77.2167 scripted) → "your location" rows in trips/ledger. |
| 15 | Search — "Choose on map" (armed pick) | PASS online / DEGRADED offline | Online: banner "tap the map to drop a pin there" → pick → route drawn + compare. Offline: pick consumed but **no pin, no error, no compare** — silent fail (see F3). |
| 16 | Search — long-press save home/work | N/T | `SaveStrip` exists in code (save/remove home/work per row); not exercised on device before context ran out — flagged for next pass. |
| 17 | Plan — option ladder | PASS | 1.07 km CP trip → 13 options across 6 modes: Car(AC), Car(windows), Bike/scooter, Bus, Auto, Bicycle(+alt), Metro+walk, On foot(+2 alts) — each with km, arrive-time, dose band "µg 0–1…9–23", "×N more inhaled than car", route summary. Progressive load ("adding metro, bus and more…"). `ss_d87238ca`. |
| 18 | Plan — depart-by-hour row | PASS | Appears once the ladder's dose spread passes its gate: "air by hour · lightest around 8:00 pm — ≈1 µg". Hour change re-computes every option's µg live (car ≈0→1, foot ≈16). Drag-scrub not fully exercised (a11y), tap-driven change verified. |
| 19 | Plan — turn-by-turn steps | PASS | "Head right on Baba Kharak Singh Marg 31 m → Bear left onto Outer Circle 964 m → Turn right onto Radial Road 6 87 m → …" + "You'll arrive"; footer toggles "hide turns". |
| 20 | Plan — vehicle chip → My vehicle | PASS | Chip opens VehicleSheet; earlier verified 6-class grid selection propagates ("your usual" badge on Bike/scooter in compare). |
| 21 | Plan — "remind me" / departure ping | DEGRADED | Bell path exists (`remind`/`armDeparture` in useShellFlow) but notification delivery on this dev-client sim is blocked by a missing keychain entitlement (see F4) — cannot verify a fired ping on the rig. |
| 22 | Plan — outside-NCR error path | N/T | Code has planError/outside state; a Mumbai query wasn't driven before window closed. Flagged. |
| 23 | Nav — start → follow | PASS | Start → NavChrome, user puck follows scripted GPS; progress ring/step updates live. |
| 24 | Nav — recenter | PASS | Pan breaks follow (recenter control appears); tap restores follow. |
| 25 | Nav — end → receipt | PASS | End → receipt card with real meters (verified on a scripted 4.6 km trip earlier in session, incl. share sheet). |
| 26 | Nav — reroute | PASS | GPS nudged off-line → recalculated ("1.3 km left" from off-route point). Auto-arrive on destination also verified earlier. |
| 27 | Ledger (Trips) | PASS | "2 trips · ≈0.8 µg (≈0.4 kg put out)" + 7-day bar chart + per-trip rows "Car (AC) … ≈0.5 µg · ≈64 µg less than the smokiest way · ≈0.20 ciga…". `ss_5d257dd4`. |
| 28 | Ledger — trip expand | PASS | Row expands: "smoke you breathed ≈0.5 µg (about 0.3–0.7 · a trace of a cigarette) · smoke your ride put out ≈0.4 kg" + delete. `ss_fa9842e2`. |
| 29 | Ledger — delete this trip | PASS | Car trip deleted → aggregate updated live to "1 trip · ≈0.3 µg". "delete all trips" present (not run — destructive on shared prod ledger; lane is GET-only). |
| 30 | Sidebar | PASS | Menu → drawer: settings rows, My vehicle inline grid, Delhi's air etc. (earlier pass: all rows alive). |
| 31 | Delhi today sheet | PASS | Hero number + mode-mix + air-now card + band scale (verified earlier). |
| 32 | Settings — toggles → behavior | PASS | show_cig → "0.02 cigarettes" in compare detail + "2.3 cigarettes" Delhi today; vehicle profile → "your usual" chip; Air-alerts master off → 4 sub-toggles disable (verified earlier). |
| 33 | Settings — quiet hours / units / consent-share | PARTIAL | Quiet-hours/units verified persisting earlier; **consent-share-off end-to-end (does the app really stop posting) not re-verified this pass** — lane is GET-only so I didn't force a POST path. Flagged for the offline/consent lane. |
| 34 | Settings — "Delete my data" | N/T | DELETE /v2/ledger — destructive write to prod, out of lane bounds (GET-only). Code path reviewed; UI row exists. |
| 35 | Language toggle en↔hi mid-flow | PASS | Flipped earlier mid-session; all surfaces re-render (see F1 note — incidents card was briefly stale while refetching, then rebuilt; code path rebuilds on `[lang]`, not a bug). |
| 36 | Layers sheet (fires/crash spots/streets travellers crossed) | PASS | Three switches all toggle ON; layer icon goes green-active; persisted across surfaces. `ss_31dcbc93`. Markers verified at CP zoom only for air stations — fire/crash pins not in view at that zoom (layers toggle state itself confirmed). |
| 37 | Locate me | PASS | Recenters + re-follows on the user dot. |
| 38 | Air-map surface | PASS | "the air map — 53 live stations · redder = worse · air reading: 8→13 min old" — the age label ticks up (honest staleness). `ss_d6ff46b7`. |
| 39 | Offline (API blackholed) — home | PASS | Hero keeps counting locally; cached incidents/ahead stay; no crash, no spinners-in-place-of-data. |
| 40 | Offline — search sheet | PASS | Banner "can't reach the server — trying again" + cached recents + Your location/Choose on map still offered. `ss_22c9b49b`. |
| 41 | Offline — map basemap | PASS | Map still renders/pans (offline pack `delhi-ncr-z9-13-r2` warmed on first render — `warmBasemap` via `OfflineManager.createPack`, no user-facing button by design). |
| 42 | Offline — plan/compare | DEGRADED→honest | Pick consumed but compare produced no error surface in the observed window (silent; see F3). Search sheet's own banner is honest; the post-pick path is the gap. |
| 43 | Notification entry points (tap → deep-link) | DEGRADED | Routing code present ("air-event-*"→air map, "alive-daily-brief"/"alive-departure"→Delhi today) but a notification cannot be *fired* on this dev-client sim — `ERR_NOTIFICATIONS_KEYCHAIN_ACCESS: A required entitlement is not present` in metro log. Deep-link target can't be confirmed on the rig. |
| 44 | "You Are Here" + "About this map" buttons | FAIL? | Both dispatch a press with **zero visible change** on the map surface (3 attempts each). Likely MapLibre attribution/annotation chrome that reads as a button but does nothing → dead-tap candidates to either wire or de-a11y-label. |
| 45 | Day-card tap on air-map surface | DEGRADED | "your day so far" card needed 3 presses before home opened (queued-tap pattern, see F5) — feels dead on first touch. |
| 46 | Kill API mid-compare | N/T | Not driven (compare loaded too fast between blackhole windows). |

## Findings (catalogued)

**F1 — (closed) incidents-card Hindi linger after en flip:** observed once; inspection shows the card refetches and rebuilds `causeNote(fields, lang)` on `[lang]` — the linger is the refetch window, not staleness. No fix.

**F2 — post-nav bare map:** after receipt "Done", the map is left bare — DayPeek/home chrome does not auto-appear until a surface tap. Disorienting end-state; small UX fix candidate (auto-show DayPeek on nav exit). Not a crash; catalogued for the owner lane.

**F3 — offline map-pick silent fail:** with the API dead, armed map-pick consumed the tap and produced no pin, no compare sheet, no error. `reverseName` itself degrades honestly (bundled gazetteer → "nearest: X · offline" → raw coords "dropped pin"), so the break is downstream — the compare fetch fails without surfacing `planError` in the observed window. Repro: kill API → search → Choose on map → tap map. **Fix candidate:** surface the existing planError/retry state when the post-pick plan fetch fails offline. Small fix; not applied (needs device re-verify and the lane was at context limit).

**F4 — notifications can't fire on dev-client sim:** `ERR_NOTIFICATIONS_KEYCHAIN_ACCESS` on registration — scheduling/deep-link delivery unverifiable on this rig (environment limitation, not app code). Covers #21 and #43.

**F5 — first-press-eaten pattern:** several controls (week strip, day card on air-map, door rows, turn-by-turn) took 2–3 presses; all presses eventually landed. Most likely the sim a11y bridge queuing during `holdMapDraw` windows rather than app deadness — every "dead" control later fired. Re-test on hardware before calling these real.

**F6 — "About this map" / "You Are Here" inert:** a11y-exposed buttons with no handler-visible effect. Cheapest fix: strip their `accessibilityRole="button"`/label or wire an info sheet. Micro.

## Structural / by-design notes

- Depart row gate (`km≥0.5 && saved>8µg`) means short/low-spread trips may never show "air by hour" — observed appearing late, once the full ladder's dose spread qualified.
- Offline pack has no UI affordance by design — `warmBasemap` fires on first map render; "airplane behavior" of the map is therefore ambient, not user-controlled.
- "trips stay on your phone" + "a 5-second check-in, on this phone only" — ledger and check-ins are local; the only server write path is ledger sync + delete, both out of lane bounds to drive.
- RN `Switch` a11y press double-dispatches on this bridge — a rig artifact; coordinate taps were used for all toggles.

## Coverage caveats

- Untested: #16 save home/work strip, #22 outside-NCR error, #34 delete-my-data (GET-only), #46 mid-compare API kill, depart-graph drag-scrub, Android (KVM child not spawned — iOS sim coverage only).
- All screenshots: `docs/lanes/feature-walk-shots/` + session `~/screenshots/`.

**Bottom line:** the app's surfaces are unusually honest — everything carries measured-vs-estimated labels, staleness ages visibly, the dosimeter counts offline, and nothing shows fake data. Real gaps found: offline post-pick path dies silently (F3), post-nav bare-map end state (F2), two inert map chrome buttons (F6), and notification delivery unverifiable on the rig (F4). No crashes, no fake numbers, no dead primary CTAs in ~46 features walked.
