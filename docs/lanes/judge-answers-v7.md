# judge-answers-v7 — the demo-day card, re-armed for the app fix wave

The sixth armed-answer card. v6 (`judge-answers-v6.md`) still stands for the
unchanged attacks (1–12, 15, 18–23: privacy spine, community audit, admin,
notify, ops, cost, seeded-data, aggregate-leak — re-read it; numbers there
are pinned on `7c68c8bc` ~14:20 UTC and drift). **This v7 re-arms what the
~20-commit Oct-7 Mobile fix wave actually changed** — every claim verified
against code at HEAD `e147dbd` + the lane reports + live prod
**`6bc2b808`** (`/health.build_sha`, deploy-7) on **2026-10-07
~21:00–21:10 UTC (~02:30–02:40 IST Oct-8)**:

- **The chooser is a 4-act beat now** — `2590598` `RouteTint.tsx`:
  frame (origin ring → destination ring, ~640 ms) → ways (≤3 candidates at
  equal weight, ~¾ s each staggered ~540 ms) → hold (~300 ms) → settle +
  verdict pill (+260 ms, ~4 s hold, fades). Felt beat **~4–6 s**
  (`chooser-craft-report.md` — on-device Release shots: `act0-frame`,
  `act1-candidate-draw`, `settle-bold-winner`, pill "cleanest and fastest" /
  "cleanest · 53% less than fastest").
- **The air map IS the field** — `677dc5d`+`e1e9d22` `AirFieldLayer.tsx`:
  CPCB band cells at CONF_A .92/.60/.34 + band-ink **contour seams** +
  per-cell µg reads (z≥10.5) + instrument rings + names (z≥14.5). Verified
  painted on-device + through gestures (`audit-fix-report.md`,
  `union-regression-report.md` `airmap-after-pan.png`).
- **Search speaks raw Delhi** — `c583cab`: phonetic fold + gali/block/pocket
  units + near-anchor + kind scan; verified `ashook nagar shadara gali no 4`
  → real rows + Photon fill `· OpenStreetMap`; `pawan bakery near hanuman
  mandir` → real bakeries. Index slice-builds at boot — the sheet opens in
  ~200–250 ms, not a multi-second freeze (`search-report.md`, `jank-perf-report.md`).
- **Home tells the truth about its number** — `3088716`: source eyebrow,
  "PM2.5 dust per m³ · same air = AQI N on other apps", nearest-monitor km,
  "air reading: N min old"; "your daily limit"; **"your lungs' calendar"**
  WeekSheet — 7 real day cells + "the air ahead" ghosted forecast +
  honesty footer (`home-truth-report.md`).
- **Delhi Today got honest** — `7a2cedd`: `own===0` collapses traveller
  aggregates to "no trips yet — go live your day, we'll count it here";
  **IncidentsCard** on home = `cause_note` + "· measured, not reported"
  (`delhi-today-truth-report.md`).
- **Welcome film retired** — `4b8ac8a`: `WelcomeScreen` unmounted (owner:
  "slop I never asked for"); fresh install = ambient beat (4 s / 9 s
  fallback) → onboarding (consent p3) → location ask; notif permission is
  lazy (`App.tsx` + `events.ts` + `notify.ts`).
- **Offline pack verified end-to-end on Android** — airplane-mode cold
  relaunch → rendered basemap + honest home **938 ms**, 744 region_tiles /
  297 resources (`offline-verify-report.md`).
- **Transit real names live on prod** — `6bc2b808` serves "Bus 405",
  "0AIRPORTEXP-4(NS) → 764EXT"; all-caps feed ids suppressed
  (`deploy-7-report.md`, live-verified).
- **✅ iOS Release SIGBUS — root-caused and CLOSED on sim** —
  `849fd4a` (`sigbus-release-report.md`): reproduced 9/35 cycles, the JS
  thread faulting into a just-scavenged young-gen semi-space segment
  (every crash window is a GC-Young-Gen event); three mechanism kills
  (off-thread jsi destructs, continuation hops, virtual jsi calls) didn't
  close it — `withAllocInYoung(false)` on sim did: **40/40 clean** under
  the full repro (fresh install, early sheet open, tiles settling).
  Device builds unaffected — all gates `TARGET_OS_SIMULATOR`. Changes
  attack #13 below.
- **⚠ Mid-range Android feel unproven** — `map-perf-report.md`: KVM runs
  sit on a ~500 ms/present SwiftShader floor; covered-cap (0 presents under
  the home sheet) and follow-mode p50 501→153 ms are the only proven deltas.
- **leftover-fixup `e147dbd` folded in** — 30 s ageTick drives all
  "N min old" surfaces (freshness lines tick live, not stale at open);
  `/health` ping gets an 8 s AbortController (a blackholed fetch counts
  as a miss, no more false-online strips); same-named place dedupe
  ("Connaught Place · district" vs "· Delhi" collapse to one row);
  exitNav clears plan artifacts; `transit_v2.line_name` extended on
  server (DEPLOY-PENDING — prod `6bc2b808` already suppresses the
  all-caps ids; the next deploy also strips tag/paren suffixes).
- **⚠ The pinned APK `ef5d95f` predates ALL of the above** — 19 Mobile
  commits behind HEAD. A re-cut ≥`e147dbd` (and never `d8c7b41..edc4666`)
  is required or the stage script narrates ghosts. See `demo-kit.md` §1.

Format: **THE ATTACK** · **THE HONEST ANSWER** (≤3 sentences out loud) ·
**THE PROOF** · **THE WEAKNESS LEFT** (plainly, no spin).

---

## The five you must know cold

1. **"Citizen layer is empty"** → ~34× dose spread on the demo OD live right
   now (car-AC **15.5** vs on-foot **535.1** mid, `6bc2b808`); daytime reads
   add the honest surprise: "a sealed car beats the metro — the coach is
   clean, the access walks aren't" (metro+walk ~38–53 µg in service hours).
2. **"Privacy is a slide"** → k≥3 firing live: 55 cells → 12 publishable,
   every hour bucket dark; installs honestly `null`; fresh phone's Delhi
   Today says "no trips yet" instead of borrowing strangers'.
3. **"What does it cost"** → 7-day AWS bill **$0.00** (₹0); $50 budget armed.
4. **"Is it actually live"** → `curl $NLB/health` on the spot:
   `field_stale:false`, `engine:"alive_core"`, `build_sha` = deployed tag.
5. **"iOS crashes"** → "we found one today, root-caused it, and closed
   it" — the YG-scavenge SIGBUS class (sim Release, early search-open) is
   dead: 40/40 clean under the exact repro, fix sim-gated. 0/60 cold
   launches stands. Device hardware honestly unmeasured.

---

## Re-armed attacks (answers changed by the wave)

### 13. "It crashes. Your own lane reports documented a cold-launch crash." → RESOLVED — SIGBUS ROOT-CAUSED AND CLOSED

**THE ATTACK:** "You claim Release is clean — but your own lane caught
SIGBUS on a Release build today."

**THE HONEST ANSWER:** "Caught it, reproduced it nine-in-thirty-five, and
root-caused it — the JS thread was faulting into a young-gen semi-space
segment that a GC scavenge had just unmapped, a simulator-only memory
layout class. We killed the mechanism itself — no young-gen copies ever
happen now — and ran the exact failing repro forty-for-forty clean. The
zero-out-of-sixty cold-launch record stands, and Android never crashed
in any recorded drive."

**THE PROOF:** `849fd4a` + `sigbus-release-report.md` — repro 9/35, three
false-lead kills documented (off-thread jsi destructs, continuation hops,
virtual jsi calls), mechanism fix `withAllocInYoung(false)` gated on
`TARGET_OS_SIMULATOR` → **40/40 clean** under full repro; warm() burst
also defers 15 s past the cold-boot window; 0/60 cold cycles unchanged
(`ios-release-residual-report.md`).

**THE WEAKNESS LEFT:** the fix is sim-gated by design — device Release
hardware remains unmeasured (always was). Honest line if pushed: "the
class we could reproduce is closed; we never claimed device numbers we
don't have — the Android APK is our stage phone, zero crashes across
every drive."

### 16. "The map is a skeleton — and your offline claim was just a row in a database." → BOTH SIDES CLOSED

**THE ATTACK:** "'Works offline' — did anyone actually walk it?"

**THE HONEST ANSWER:** "Yes — the whole walk, on Android, in airplane mode:
killed the radios, cold-relaunched, and nine hundred thirty-eight
milliseconds later the home screen and the Delhi basemap were both real —
seven hundred forty-four offline tiles inside the app, verified in the
binary's own database. Trips, receipts, the ledger, search's gazetteer —
all of it still works with no network."

**THE PROOF:** `offline-verify-report.md` — r2 pack `delhi-ncr-z9-13-r2`,
744 region_tiles + 297 resources counted in the installed MBTiles-style
store; airplane-mode cold relaunch → basemap renders ~4 viewports out,
home honest, zero crashes; style `GET /v2-light.json` live on prod.

**THE WEAKNESS LEFT:** the home surface is still a blind list offline (C4 —
cached daylog/hero renders as an honest container without numbers); a *new*
plan refuses offline — honestly, with a message, not a spinner.

### 20. "Cute demo — but Delhi will be clean that day, won't it?" → RE-PINNED: TOMORROW IS THE LEAST-BAD OF FIVE

**THE ATTACK:** "Your whole story needs smog. What if demo day is a good-air
day?"

**THE HONEST ANSWER:** "Then the app says so — and that's the product
working. Tonight's own outlook calls tomorrow the least-bad of the next
five days — about eighty micrograms average against a hundred-and-thirty
across the stretch, with four straight 'very poor' days behind it. A clean
day doesn't hurt the demo; the dose spread between a sealed car and a walk
is a thirty-times fact on good air too — it just gets bigger on bad ones."

**THE PROOF:** `GET /v2/outlook` live ~21:05 UTC — best_day Oct-8 Moderate
~80.5 (−50.1 vs the 5-day mean ~131), Oct-9…12 Very Poor; the demo-OD dose
spread at a mild-afternoon read was still ~33× (v6), tonight's dirty-evening
read is ~34.5× — the spread survives clean air because it's mode-vs-mode,
not smog-vs-clear.

**THE WEAKNESS LEFT:** a clean day weakens the incidents card (it'll read
"the air is mixing well" instead of a fire line) — same honesty, softer
visceral hit.

### 14. "Is the data real — or painted to look real?" → RE-ARMED: THE MAP LITERALLY SHOWS THE INSTRUMENTS

Add to v6's answer: "…and on the app's air map the instruments are *on the
glass* — rings at the real station positions, names at neighbourhood zoom,
each cell carrying its own measured number, edges drawn as contour seams
where the field crosses a band boundary. Pan it: the cell numbers and the
station reads agree because the field reads the instrument at its own
station — the leave-one-out number on the wire is the honest price of the
cells in between."

**THE PROOF:** `AirFieldLayer.tsx` (`airfieldValues` z≥10.5,
`airStationDots`, `airStationNames` z≥14.5) + `/aqi.calibration` live:
LOO MAE 8.8 / RMSE 12.7 / n=70 / bias +0.2 — "error between stations — at a
station the field reads the instrument itself" is on the response.

### 17. "Half the app is dead switches and stub endpoints — it's demo-ware." → STRONGER

Add: "This week we put the honest-emptiness rule on the screens themselves:
a fresh install's Delhi Today says 'no trips yet — go live your day, we'll
count it here' instead of borrowing strangers' aggregates; the lungs'
calendar foots 'a blank day is a day the app wasn't with you, never a
zero'; the hero names where the ambient number was read and how old it is.
The surfaces you'd call demo-ware are the ones that now refuse to pretend."

**THE PROOF:** `delhi-today-truth-report.md` (own===0 collapse, filesystem
proof no ledger.json on fresh install) + `home-truth-report.md` (WeekSheet
shots + honesty footer).

---

## The NEW attacks the wave invites

### 24. "That search demo was canned — nobody types like that."

**THE ATTACK:** "You picked a query the app knows. Real people type garbage."

**THE HONEST ANSWER:** "Type yours — anything. We demo with a misspelled
phonetic phrase and a landmark-relative query because that's how Delhi
actually types: 'ashook nagar shadara gali no 4' resolves the real street,
'pawan bakery near hanuman mandir' finds real bakeries near the nearest
Hanuman Mandir. If the local index doesn't know it, an OpenStreetMap fill
answers and labels itself as the web result — nothing is invented."

**THE PROOF:** `search-report.md` — phonetic fold, gali/block/pocket units,
near-anchor, kind scan verified on sim; Photon t3 rows carry
`· OpenStreetMap` attribution; the dropped-chars bug (each keystroke used to
blow the rows away) was killed by `useDeferredValue` + memoized rows.

**THE WEAKNESS LEFT:** genuinely obscure inputs still thin out — that's
what the labelled web fallback is for; the sheet says "no place found — try
a landmark" instead of hallucinating.

### 25. "The air map is a paint job — show me it's the data."

**THE ATTACK:** "Band-coloured cells could be a static overlay for all I know."

**THE HONEST ANSWER:** "Each cell is painted from the field's own read at
its own centre — the same serve the planner doses from. The legend reads
the field's actual station count and freshness: 'fifty-four live stations ·
air reading: N minutes old'. Ask for the number two ways — the `/aqi`
endpoint says what the cell says, because they're the same kriged surface."

**THE PROOF:** `airfieldCells` fill = `properties.ugm3` at CPCB band steps
(30/60/90/120/250) at CONF_A opacities; legend from FIELD.status() (same
block `/v2/plan` carries). Cross-check live: `/aqi?lat=&lon=` value vs the
cell under that pin.

**THE WEAKNESS LEFT:** the *landing page's* raster tiles are pre-baked
(~15-min batch) while the phone reads the live field — during a refresh the
two can disagree by one refresh; that's honesty, not a bug, and we can say
it.

### 26. "How does it feel on a real mid-range Android — not your emulator?"

**THE ATTACK:** "Your perf claims were measured on a software rasterizer.
On a ₹15k phone this could be a slideshow."

**THE HONEST ANSWER:** "Honest answer: we don't know yet, and we stopped
claiming numbers we can't measure. What we *can* say: the tune we shipped
shows up even under a five-hundred-millisecond software floor as more
presents per gesture — the follow-mode median dropped 501 to 153
milliseconds, and under a covering sheet the map stops presenting entirely.
Zero frames wasted is verified; how smooth it *feels* on real glass is the
phone's story to tell — the demo phone is the proof or it isn't."

**THE PROOF:** `map-perf-report.md` — KVM/SwiftShader ~500 ms/present floor;
covered-cap verified (0 presents while the home sheet covers the map);
follow-mode p50 delta 501→153 ms; `edc4666` launch-crash fix (a glass
`run: false` halts any teardown race).

**THE WEAKNESS LEFT:** pan/zoom deltas unverifiable on software GL — say
"verified on the emulator" not "smooth on every phone". If a real
mid-ranger stutters on stage, that's a fair hit — the mitigation is the
release APK being small and the field already warm.

---

## Watch items — re-armed

### F'. Metro row — ABSENT at tonight's read (GTFS hours)

`metro+walk` is **off the wire** on the demo OD at ~02:35 IST Oct-8 —
outside service hours (23 opts, all road modes). It returned ~38–53 µg in
daytime reads. **T-45 re-check decides if "car beats metro" is spoken.**
The dose spread (~34×) doesn't need it.

### G'. Fires — still REFUSED, and the honesty story got better

`carrying:false` at this stamp — wind ~4 km/h NNE, off the 270–360° gate;
belt 16 fires/41.4 MW, modifier ×1.08. The incidents card on home narrates
it verbatim: "the wind isn't carrying it this way right now · air barely
mixing — ventilation 521 m²/s vs ~3,000 typical · measured, not reported".
T-45 `curl /v2/why` picks the wording; the flip is a feature.

### I'. Offline basemap — CLOSED on Android (r2 pack verified)

See #16 — airplane-mode PASS, 938 ms cold relaunch. The pack rides any APK
≥`54a296e` — including the pinned `ef5d95f` — so **offline works even if
the re-cut doesn't land**.

### J'. Demo vehicle — Android APK; iOS Release is sim-clean again

SIGBUS class closed on sim (`849fd4a`, 40/40 repro-clean — #13). The
~90 s early-search caution now applies only to a binary **predating**
`849fd4a` — on a fresh re-cut it's belt-and-suspenders. If both
platforms are on the table **the Android APK is still the safer live
drive** (0 crashes across every recorded drive; iOS device hardware
remains unmeasured).

### K'. APK tip drift — now the biggest single risk

The pinned `ef5d95f` is **19 Mobile commits behind HEAD** — v1 chooser,
invisible field, welcome film, old search on that glass. The stage script
v3 narrates HEAD. **Re-cut ≥`e147dbd`** (never `d8c7b41..edc4666`), then
re-pin `demo-kit.md` §1. If no re-cut lands: narrate the v1 chooser beats
and drop the air-field/raw-search claims — v2's phone wording is the
fallback, and the script's contingency row says so.

### L'. Landing film-strip is v1 chooser (minor)

`chooser.mp4` + the landing strip show the old chooser's settles. Not wrong
— but a fresh 4-act capture is better if a re-cut lands. Flagged in
`demo-kit.md` §3.

---

## Numbers card — re-pinned on prod `6bc2b808`, ~21:00–21:10 UTC (~02:30–02:40 IST Oct-8)

| figure | live now | source |
|---|---|---|
| prod build | **`6bc2b808`** == ECR tag (deploy-7 — transit line names live) | `/health.build_sha` |
| stations | **54** waqi+dpcc both `ok` · history.climatology 125 | `/health` + `/aqi.field` |
| field | 102 samples · age ~4 min · `stale:false` | `/aqi.field`, `/health` |
| edges | 1,070,459 / 903,058 priced · `osrm-local` ~15 ms | `/health.routing` |
| transit feeds | metro `true` + bus `true` real | `/health.transit.real_feeds` |
| CP point | pm2.5 **72.4** breathing / **67.1** ambient · **US AQI 157** · nearest **1.8 km** · smoke ×1.08 | `/aqi` |
| fires | **90** / 16 in-belt / 41.4 MW · modifier ×1.08 · **`carrying:false`** (NNE ~4 km/h) | `/aqi.fire`, `/v2/why` |
| why | stagnation — VC **521 m²/s** vs ~3,000 · trend **+11.0 µg / 5.8 h** (91.8→102.7, climbing) | `/v2/why` |
| LOO | MAE **8.8** / RMSE 12.7 / n=70 / bias +0.2 | `/aqi.calibration` |
| city | mean **92.5** / median 91.6 / max 137.6 · aqi **209** · GRAP-indicative **stage 1** — dirty evening (was mild-afternoon ~47; name the anchor) | `/v2/city` |
| breath | day-inhaled **~1,329 µg mid ≈ 4.2 cigarettes** | `/v2/city.breath` |
| corridors | 9 dirty corridors now · publishable 12/55 (k≥3) | `/v2/city`, `/v2/city/moves` |
| community | **47 obs / 8 today / 25 contributors / 34.7 km** · avoided **444.3 today / 1,410.3 all-time** | `/community` |
| plan demo OD | **23 opts** · car-AC **15.5** (6.3–24.8) · car-open 28.2 · bike 37.0 · bus 40.7 (46m) · auto 47.8 · cycle ~237–266 · **walk 535.1 → 34.5×** · **metro absent (02:35 IST)** · `took_ms` 118–326 warm | `POST /v2/plan` |
| depart demo OD | now 14.3 → best **10.4 @ +13 h (Oct-8 11:00)** → worst 23.2 @ +23 h · **pct 27 → leave-later row armed** | `/v2/depart` |
| outlook | Oct-8 **Moderate ~80 = best of 5** → Oct-9…12 **Very Poor** | `/v2/outlook` |
| skill | ~330 pairs · h+0 ~90% band → h+11 ~36% | `/v2/skill` (v6 stamp — re-hit T-45) |
| app truths | cold open ≤~1 s release / no film · Where-to ~200–250 ms · air map ~50–70 ms · chooser ~4–6 s · check-in echo ~80 ms | jank-perf + offline-verify + RouteTint |
| offline | r2 pack **744 tiles + 297 resources** · airplane-mode relaunch → honest home+map **938 ms** | `offline-verify-report.md` |
| iOS crash | 0/60 cold · **SIGBUS class closed on sim** — repro 9/35 → fix `withAllocInYoung(false)` → **40/40 clean**; device unmeasured | `sigbus-release-report.md` `849fd4a` |
| Android crash | **0** across all drives incl. airplane-mode + map-perf | lane oracles |
| spend | net **$0.00 / 7d** | ops-handover |

*Everything ⟳ drifts — T-45 re-pin is mandatory; `verify_numbers.sh`.*
