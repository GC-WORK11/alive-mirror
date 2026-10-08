# Alive — demo-morning runbook (the one checklist you hold)

*Written 2026-10-07 ~13:05 UTC, re-synced ~21:15 UTC for the **Oct-7
owner fix wave** — every moving number below re-verified live on prod
build **`6bc2b808`** (`/health` `build_sha` == ECR image tag; deploy-7 —
transit real names on the wire, `deploy-7-report.md`). The stage script
is **`demo-script.md` v3** (rewritten beat-by-beat against HEAD
`e147dbd`); the judge card is **`judge-answers-v7.md`**.
Sources: `docs/demo-day.md`, `docs/plan/demo-script.md`,
`docs/plan/admin-login.md`, `docs/plan/go-nogo.md`,
`docs/submission/submission-checklist.md` §3, plus the wave's lane
evidence — chooser-craft, audit-fix/2, home-truth, delhi-today-truth,
search-report, jank-perf, nav-journey (SIGBUS X1), map-perf,
offline-verify, union-regression, judge-answers-v6/v7.

**⚠ THE BINARY DECIDES WHICH SCRIPT IS REAL.** The pinned demo APK
`alive108-ef5d95f.apk` predates the whole wave (19 Mobile commits
behind) — on it, the 4-act chooser, the visible air field, raw-phrase
search, the no-film cold open and Delhi Today's honest gate **do not
exist**. Re-cut at **`e147dbd` or later — never in
`d8c7b41..edc4666`** (map-perf alone crashes Android at launch;
`edc4666` is the fix). If no re-cut lands, the phone beats fall back
to v2 wording (`demo-script.md` contingency row). Nothing here is
seeded or faked; numbers marked **⟳ LIVE** move with the field — read
them at T-45, never from memory.*

`NLB = http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
(HTTP :80 only — never `https://`, never `:8000`)

```bash
# Export once at the top of any shell you run checks from:
export NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
export AWS_DEFAULT_REGION=ap-south-1
curl -s -o /dev/null -w "NLB -> %{http_code}\n" "$NLB/health"   # expect 200
```

---

## Before the clock starts (first thing, any time before T-90)

- [ ] **Public repo baseline pushed** — the Oct-8-history rule is a
  whole-team disqualifier, not a downgrade. If not already done:
  create an EMPTY GitHub repo (no README/license), then
  `./scripts/public-repo.sh https://github.com/<owner>/<new>.git`
  — needs push auth in the credential helper. Verified: `go-nogo` #1.
- [ ] **DEPLOY FREEZE from T-60 → demo end.** No pushes to `base/v2`,
  no deploys, no task swaps — **every `base/v2` push triggers a
  prod rebuild** (watchdog mechanic, observed 3× today). A mid-window
  deploy = fresh task serving thin field + route_ids 404ing +
  `build_sha` flipping under a judge's eyes.
- [ ] **Backup videos on the phone**: `docs/video/cut1.mp4` +
  `docs/video/cut2.mp4` copied over, played once **in airplane mode**.
- [ ] **APK installed + opened once** (see T-45 phone block — first
  boot is a gauntlet, get it done tonight, not in the hall).

---

## T-90 — GO/NO-GO gate + warm the task

Run all five checks. **Any fail → fix it or call it; don't proceed on
hope.** Then warm.

| # | check | exact command | pass |
|---|-------|---------------|------|
| 1 | service health | `curl -s "$NLB/health" \| python3 -m json.tool \| head -40` | HTTP 200 · `field_stale:false` · `engine:"alive_core"` · `transit.real_feeds` bus+metro `true` · `build_sha` = the deployed tag (`6bc2b808` family — re-check anytime with this same curl; a flip means a task restart or a freeze-break, see T-5) |
| 2 | plan serving (priced engine) | `python3 tools/warm_task.py` | exit 0 → prints `WARM: priced engine serving after Ns`; last line `/tiles/health ok — 22.7 MB` |
| 3 | field age < 20 min | `curl -s "$NLB/health"` → `field_age_s` | `< 1200` (it peaks ~920 s then resets on the ~15-min cycle — a stuck reading >1200 s means the ingest loop died) |
| 4 | APK installed + warmed | on the phone: app opens → home hero shows a live "outside" number → tap "Air map" (the field must be painted, not a bare basemap) → "Where to?" India Gate → Huda City Centre → plan lands → back to home | install the latest `alive108-<sha>.apk` — **must be a re-cut ≥`e147dbd`** (the wave's Mobile commits; `demo-kit.md` §1). The pinned `ef5d95f` still *works* (r2 pack inside) but shows the OLD app — v1 chooser, invisible field, welcome film on fresh install. `c3bb731`/`0b11123` are **never**; a `d8c7b41..edc4666` cut crashes at launch. `shasum -a 256` the file against its report |
| 5 | admin login works | `TOKEN=$(aws secretsmanager get-secret-value --secret-id alive108/admin-token --query SecretString --output text)` then `curl -s -D- -o /dev/null -X POST "$NLB/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs/login" -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN\"}" \| grep -i '^set-cookie'` | `alive_admin=v1.<exp>.<sig>; HttpOnly; Max-Age=28800` — proves token + endpoint good before you need them on camera |

**NO-GO conditions (cut or fix, don't fake):**
- `/health` `field_stale:true` or `field_age_s` stuck > 1200 s after two
  refresh cycles (~30 min).
- `warm_task.py` exit 1 — engine never priced within the timeout.
- Demo-OD plan returns `options:[]` twice in a row (one honest planner
  timeout is normal on cold far-ODs; two means cut to backup video).
- Public repo not pushed — disqualifier.
- APK crashes on open twice — demo the web surfaces (`/`, `/city`, and the
  console at its unlisted URL); same numbers.

---

## T-45 — pre-warm the phone + live-verify the moving lines

### The phone (3 min — kills the two cold-start traps from rehearsal-v2)

First boot on a fresh install is a gauntlet, not a demo. On the wave's
build the order is **ambient number beats first (~4 s, 9 s offline
fallback) → 3-page onboarding (consent is page 3) → location
permission → home — NO welcome film** (retired `4b8ac8a`), and the
notification permission is **lazy** now (it fires on the first real
air event after consent, or when you arm a reminder — don't stand
there waiting for the dialog). On the old `ef5d95f` binary the film is
still in. And the **first-ever plan still runs the chooser *behind*
the vehicle wizard** — the signature beat plays occluded. All
first-run-only. So:

- [ ] APK installed + opened once **before** morning — grant every
  permission when the dialogs fire (location; notifications fire
  lazily post-consent), swipe the onboarding pages, answer consent
  either way (it persists).
- [ ] **iOS-only caution (SIGBUS — closed on sim `849fd4a`,
  belt-and-suspenders):** the YG-scavenge crash class is dead on sim
  (40/40 repro-clean, fix `TARGET_OS_SIMULATOR`-gated). It could only
  bite a binary **predating** `849fd4a` — the re-cut at `e147dbd`
  carries the fix, but if the phone somehow runs older, don't open
  "Where to?" in the first ~90 s after a fresh-install cold launch.
  On Android there's no such caution (0 crashes across every drive).
- [ ] **Now, on any working uplink**: open the app → search
  `India Gate` → `Huda City Centre` → let the compare sheet land →
  walk through the vehicle wizard once → **leave the app on home**.
  This clears the wizard so tomorrow's on-camera chooser plays clean,
  seeds every last-good cache — **and caches the map tiles over the
  demo corridor**. On any APK ≥`54a296e` (incl. pinned `ef5d95f`) the
  r2 pack already pulled all 744 NCR tiles — pan anyway,
  belt-and-braces.
- [ ] Rig note that might be real: suggestion rows sometimes eat a
  light tap — if a row seems dead, **long-press it ~300 ms**. Same on
  compare CTAs. (rehearsal-v2 F5; possibly emulator flake, possibly
  real — the press takes 1 s to learn.)

### The live lines — these moved *twice* today; check, don't recite

```bash
# 1) The why/parali line — flips with the wind (refused ↔ carrying,
#    it flipped at 12:31 UTC today: SW refused → N carrying):
curl -s "$NLB/v2/why" | python3 -m json.tool | head -25
#    read `line` + `cause_note` + `cause_note_fields.carrying`:
#    carrying:true  → "stubble smoke drifting in — N fires in the
#                      Punjab–Haryana belt, a N wind is carrying it"
#    carrying:false → "fires in the belt today, but the wind isn't
#                      carrying it this way — measured, not reported"

# 2) The leave-later row — renders only when pct_less_vs_now > 8:
curl -s "$NLB/v2/depart?from_lat=28.6129&from_lon=77.2295&to_lat=28.4958&to_lon=77.0854&vehicle=car" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('pct:', d['pct_less_vs_now'], 'now:', d['now']['dose_ug'], 'best:', d['best'])"
#    tonight: pct 27, now 14.3 → best 10.4 @ +13 h (11:00 IST).
#    If it reads ≤8 tomorrow the row is gone — narrate the curve's
#    dip→overnight climb instead (see fallback table).

# 3) The plan numbers you'll quote — demo OD only:
curl -s -X POST "$NLB/v2/plan" -H 'content-type: application/json' \
  -d '{"from":{"lat":28.6129,"lon":77.2295},"to":{"lat":28.4958,"lon":77.0854}}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); o=d['options']; print('opts:',len(o),'took_ms:',round(d.get('took_ms',0)),'degraded:',d.get('degraded')); [print(' ',x['mode'],(x.get('dose') or {}).get('mid')) for x in o]"
#    tonight's read: 23 opts, car-AC 15.5 mid, walk 535.1 → ~34.5×,
#    warm took_ms 118–326. metro+walk is GTFS-hours dependent —
#    ABSENT at the ~02:35 IST read, present (~38–53 µg) in service
#    hours. If absent at T-45, the "car beats metro" clause comes out.

# 4) The state of the machine:
curl -s "$NLB/health" | python3 -m json.tool | head -30
#    build_sha (demo build — `6bc2b808` family; re-check: this same
#    curl — a flip means a task restart or a freeze-break, not field
#    drift), field_age_s, stations count (52–54 drift band), wind.

# 5) Full sweep if you have 3 min — prints FLAGS for anything stale:
bash scripts/verify_numbers.sh
```

### Pinned numbers that DON'T move (verified today, quote freely)

- spread on the demo OD: **~34–35×** (34.5× on tonight's wire —
  car-AC 15.5 vs walk 535.1) — say "more than thirty times"
- options count: **"about twenty"** (16–24 seen across reads)
- car-AC vs walk on the demo OD: **about ten-to-sixteen vs
  four-to-six-hundred µg** — read the screen, it ranges with the field
- the chooser's beat (new 4-act, `2590598`): **frame** (rings mark
  from/to ~640 ms) → **ways** (≤3 candidates equal weight, ~¾ s each,
  540 ms stagger) → **hold** ~300 ms → **settle + verdict pill**
  (~260 ms after the winner thickens; ONE honest line —
  "cleanest and fastest" / "cleanest · N% less than fastest" / the
  server's `reason_line` — holds ~4 s then fades). Felt total **~4–6 s**
  — let it play out before reading the ladder. (On the OLD `ef5d95f`
  binary it's the v1 chooser: candidates draw as equals → settle →
  pill ~4.2 s — still real, just fewer acts.)
- graph: **1,070,459 edges / 903,058 priced** · `alive_core` · ~15 ms
  self-hosted OSRM
- field heartbeat: **15 min**, `refresh_in_s` counts down on the wire
- admin cookie: ~8 h, survives redeploys
- offline honesty: **8/8 checks PASS** on the release build
  (testday-offline) — nothing on screen pretends
- privacy, verified end-to-end today: spine audit **PASS** — zero
  identity fields on any gated wire, k≥3 **firing live** (55 cells →
  12 publishable, every hour bucket dark) — and the one latent gap
  (ungated day-rows) **closed and live on prod** (privacy-spine +
  privacy-f1-fix + deploy5). "A street publishes only after 3
  different riders crossed it" is now true on every surface.
- community ledger **proven 100% real** (community-sanity): the page
  reconciles exactly to DynamoDB + S3 — 44 trips / 24 contributors /
  1,278.9 µg — zero test-labelled devices, zero seeds, zero non-Delhi
  geometry. Caveats to say if pressed: "contributors" counts device
  tokens not humans; two legacy `/observe` traversals inflate two
  corridor dose avgs until ~Oct-8 06:20Z (the 44-trip headline is
  unaffected).
- iOS release measured **0/60 cold launches clean**
  (ios-release-residual) — and the sim SIGBUS class is now closed
  (`849fd4a`: 40/40 repro-clean; caution kept in the T-45 block as
  belt-and-suspenders for pre-fix binaries).
- app cold open: **~0.8–1 s** on the release APK (`am start -W`
  845 ms; offline relaunch → honest home+map 938 ms) — no welcome film.
- sheet opens: "Where to?" ~200–250 ms (index pre-warmed at boot),
  air map ~50–70 ms, check-in pill echo ~80 ms (jank-perf).
- offline pack verified end-to-end on Android: 744 region_tiles +
  297 resources, airplane-mode cold relaunch renders the basemap
  (offline-verify). Rides in the pinned `ef5d95f` too.
- `/v2/skill` answers in **~0.7 s on prod** (was ~6 s — deploy4).

---

## T-30 — admin sign-in + physical setup

### Admin sign-in (60 s — full playbook `docs/plan/admin-login.md`)

- [ ] Have the operator token physically at hand — **phone note or
  paper**, not a laptop you'll unlock on stage. (Secrets Manager
  `alive108/admin-token`; fetch cmd in the GO/NO-GO table.)
- [ ] In the demo browser open `$NLB/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` — a guest lands on the
  **gate card** ("engine room · OPERATOR ONLY"), not the board.
- [ ] Paste the token → **SIGN IN** → board renders + ticks ~30 s.
- [ ] **Chrome will offer "Save password?" → tap Never.** The token
  does not go into a password manager on a shared machine.
- [ ] If it says `wrong token`: re-paste carefully — **5 bad tries →
  429**; wait ~5 s, one clean attempt passes.
- [ ] Judges never go near the console URL? Leave it gated — the gate card
  itself is the privacy story.

### Physical

- [ ] Phone battery > 80% + power bank + cable on the table.
- [ ] Phone on a network that reaches the NLB — **venue Wi-Fi with a
  captive portal breaks plain-HTTP silently; a phone hotspot is the
  safe uplink.** Verify: `curl -s -o /dev/null -w '%{http_code}'
  $NLB/health` → 200 on the network you'll actually use.
- [ ] AWS console signed in + pinned BEFORE the venue — ECS
  `alive108` service card (never log in live on stage). The video
  must show the console — no console, no score.
- [ ] Kill background apps; disable auto-lock.
- [ ] 3-min sanity on the real hardware: basemap street labels draw;
  "Where to?" opens on a normal tap; one map/sheet control responds.

---

## T-5 — the two lines to re-check

```bash
curl -s "$NLB/health" | python3 -c "import json,sys; d=json.load(sys.stdin); print('sha:',d['build_sha'],'stale:',d['field_stale'],'age_s:',d.get('field_age_s'))"
# ^ task alive, `build_sha` still in the `6bc2b808` family, field fresh.
#   If build_sha CHANGED (a task restarted), re-run:
#   python3 tools/warm_task.py   — before stepping on stage.

curl -s "$NLB/v2/why" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['line']); print(d['cause_note'])"
# ^ the exact line you're about to say — it flips with the wind.
```

Glance at the phone: still on home, live "outside" number showing.

---

## T-0 — beat order (~2:50, 10 s slack)

Stage beats from `docs/plan/demo-script.md` (the 8-row table is the
canonical verbatim; this is the order + the honest number behind each):

| # | time | on screen | the line (shape, not script) |
|---|------|-----------|------------------------------|
| 1 | 0:00–0:15 | **phone cold open → home** — hero ambient number + provenance + freshness; incidents card above the doors | "no video, no splash — it opens on the number. Sixty-seven micrograms per cubic metre outside right now — same air other apps call AQI one-fifty-seven. It says where it read it, how far the nearest real instrument is, and how old the number is. Below it — what's in Delhi's air right now, measured not reported." ⟳ LIVE |
| 2 | 0:15–0:35 | **phone**: tap "Air map" — the field itself | "this isn't a styled map — this IS the air: every cell the kriged field in its own official band, contour edges where it crosses, the instruments' own numbers floating on it, rings at the fifty-four live stations. Redder means worse; nothing else on the screen uses colour." |
| 3 | 0:35–0:55 | **phone**: "Where to?" → type `ashook nagar shadara gali no 4`, then `huda city centre` | "search works the way you actually type — misspelled, phonetic, a gali number, 'near the mandir'; it folds the spelling, anchors 'near' to the real landmark, never invents a pin. Now the trip — HUDA city centre." |
| 4 | 0:55–1:35 | **phone**: plan lands → the 4-act chooser on the map → compare ladder + leave-later row | "watch the map think: your from, your to — then the ways, drawn as equals — then one settles and *says why*. Same twenty-five kilometres: on foot about five hundred µg, a sealed AC car about fifteen — more than a thirty-times spread the map you use today never tells you. And it prices *when* — leave at eleven, about a quarter less." Metro clause ONLY if the row's on the wire. |
| 5 | 1:35–1:55 | **phone**: "your lungs' calendar" week sheet → "Delhi today" | "every trip lands in your lungs' calendar — seven real days, blank means the app wasn't with you, never a fake zero. Delhi today: the city's air is shared, but your trips are yours — until you've taken one it says so." |
| 6 | 1:55–2:15 | **laptop**: `/` landing + `/community` + `/v2/city` + console gate→board | "the same field serves the public page — and every donated trip becomes a live sensor: forty-seven real donations, twenty-five contributors; a street only publishes after three different riders cross it — the privacy is in the math." ⟳ LIVE counts |
| 7 | 2:15–2:35 | AWS console — ECS `alive108` | "real infrastructure: ECS Fargate behind an NLB — one task, healthy, Spot-priced; DynamoDB holds only aggregates." Read task-def off the console, never a memorized number. |
| 8 | 2:35–2:50 | console field map — species pills → back to `/` | "we hold one rule: no fake precision — the band is *measured* (95.2% @2σ over 3,550 held-out station-hours). Click NO₂ — a different map, not a relabeled layer. Dose every 250 metres for the rider, emissions per mode for the city — Alive, the map that prices the air." |

**Do NOT improvise other ODs on stage.** The metro+walk row is only
guaranteed on the demo OD (India Gate → Huda City Centre — verified
present twice today while the CP→Gurugram script OD went without).
Other ODs serve, but the metro row may be absent and the doses drift —
rehearsed is rehearsed for a reason.

**Two AQI anchors, don't conflate**: DelhiToday shows the city-average
US AQI (was 86 today — a citywide mean) while `/aqi` at CP point-reads
"in the 150s". Both honest; different anchors.

---

## Fallback table — beat | if it fails | say this instead

| beat | if it fails | say this instead |
|------|-------------|------------------|
| landing `/` | page won't paint / boot overlay stuck | `/city` is the same field — "same data, different face" |
| `/aqi` number | `field_stale:true` or old age | "it reports its own age instead of pretending fresh — the honesty is the product" (read the real age aloud) |
| plan call | > 4 s on the demo OD | "1.07 million edges being re-priced off this morning's field" — it lands; warm hits ~0.5–2 s, a post-refresh reprice ~6–9 s is legit. `options:[]` once = honest planner timeout; retry once, then cut to the backup video |
| chooser | plays behind the vehicle wizard | only happens if T-45 pre-warm was skipped — close the wizard sheet, the winner is already drawn; run the OD once more and it plays clean |
| chooser pill | text differs from the script | the pill quotes `chooserVerdict`/the server's `reason_line` verbatim — read whatever it says; it's the engine's own words. On the new beat it pins ONCE (~4 s) then fades — don't wait for a second pill (the two-pill cycle was the old build) |
| dose ladder | numbers drifted | "they move with the field — read the screen: about seven-to-nine vs two-fifty-to-three-hundred" — say the range, never a stale constant |
| metro clause | no `metro+walk` row | drop the clause entirely — the road-mode rows alone carry the ~35× spread; transit rows honestly absent ≠ a bug |
| leave-later | row absent (`pct ≤ 8`) | "today the curve is flat — the honest answer is 'it doesn't matter when'; on a swing day it tells you the cheaper hour" — narrate the dip→overnight climb on the curve |
| `/v2/day` windows | both `null` | "no meaningful window today — flat air all day" — the `decisions` row says it in plain words; read `hours[]` + `day_mean_pm25` out loud |
| fires aside | `carrying:false`, or modifier `null` | "fires burn in the belt every day — today the wind isn't carrying it to us; the model checks, and honestly says no" |
| community counts | numbers not on the app surface | they're wire-level totals — open `curl $NLB/community` in the browser (or the admin board) and read `obs_total`/`contributors`/`avoided_ug_all` live |
| admin login | 429 rate_limited | wait ~5 s, one clean paste — the bucket refills ~1/5 s |
| admin login | `admin auth is not configured` (503) | task env lost the token — deep failure; demo everything else, gate card still tells the privacy story |
| venue Wi-Fi | anything stops loading | switch the phone to the hotspot you armed at T-30; captive portals kill plain HTTP silently |
| venue Wi-Fi + hotspot | **both** dead | the app still demos air-gapped: bundled 124k-row gazetteer search, a pre-planned route's nav leg, receipt, ledger, day log all work offline; the r2 pack is IN any APK ≥`54a296e` (incl. the pinned `ef5d95f`) — 744 tiles verified on Android, airplane-mode cold relaunch → honest home+map in 938 ms (`offline-verify-report.md`). Home surfaces offline render as honest empty containers, not fake zeros (C4). Only a **new** plan honestly refuses — for server beats, cut to `cut1.mp4`/`cut2.mp4` on the phone |
| APK | crashes on open | relaunch once — every state persists (consent, vehicle, recents, ledger); back on the map in ~1 s. iOS-only on a pre-`849fd4a` binary: give the map ~90 s to settle after a fresh-install cold launch before opening "Where to?" (SIGBUS class — closed on sim by `withAllocInYoung(false)`, 40/40 repro-clean). Crash twice → web surfaces carry the same numbers |
| AWS console | won't load | CLI understudy from any credentialed shell: `aws ecs describe-services --cluster alive108 --service alive108 --query 'services[0].{status:status,running:runningCount,taskDef:taskDefinition,capacity:capacityProviderStrategy}'` → ACTIVE · 1/1 · FARGATE_SPOT — describe it, don't fake the screen |
| a judge hits prod mid-demo | numbers differ from your line | expected — the field rebuilds every 15 min; "every number on every screen is served live, which is why mine moved too" |

---

## Standing rules for the day

- **Probe rule**: prod is GET-only except the app's own `POST /v2/plan`,
  `/v2/reroute`, `/v2/feedback` (and consented `/v2/trip` donations).
- **FARGATE_SPOT stays** — the on-demand flip is skipped by default
  (₹0 budget, owner call 2026-10-07). A reclaim is rare and the
  replacement serves in ~4 min; if one lands mid-demo, re-run
  `warm_task.py` then this checklist.
- **`/v2/strip` route_ids are per-task in-memory** — after any task
  swap, re-mint plan→strip pairs; old ids 404.
- **Never deploy inside the window.** Whatever HEAD is at T-60 is the
  demo build.
- **Android is the demo device** — zero crashes across every
  recorded drive (rehearsal-v2, offline-verify, map-perf). iOS Release
  keeps its 0/60 cold-launch record and the sim SIGBUS class is now
  **root-caused and closed** (`849fd4a` — 40/40 repro-clean,
  sim-gated). Mid-range Android *feel* is honestly unproven
  (SwiftShader deltas only — `map-perf-report.md`); the demo phone's
  real glass is the proof. If anyone asks: "verified on the
  emulator; the phone tells the real story." Nothing else changed:
  read the screen, not the script.
- **Read the screen, not the script.** The pinned ranges above are
  honest; a recited constant that the field moved past is a gotcha,
  not a feature.
