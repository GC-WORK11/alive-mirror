# ALive-108 — demo-morning runbook (the one checklist you hold)

*Written 2026-10-07 ~13:05 UTC, last sync ~14:25 UTC — every moving
number below re-verified live on prod build **`7c68c8bc`** (`/health`
`build_sha` == ECR image tag; deploy-5 roll 2 — `deploy5-report.md`).
Sources: `docs/demo-day.md`, `docs/plan/demo-script.md`,
`docs/11-demo-script.md`, `docs/plan/admin-login.md`,
`docs/plan/go-nogo.md`, `docs/submission/submission-checklist.md` §3,
plus today's lane evidence — rehearsal-v2 (Android), deploy5,
privacy-f1-fix, offline-pack-fix, community-sanity,
ios-release-residual, judge-answers-v6, watchdog (deploy sweeps, all
alarms OK), testday-offline (8/8 honesty checks PASS), admin-login-e2e.
A final freeze-cut APK re-cut is IN FLIGHT (apk-recut lane) — the APK
steps below point at it, not at the older `c3f7e9e` freeze. Nothing
here is seeded or faked; the numbers marked **⟳ LIVE** move with the
field — read them at T-45, never from memory.*

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
| 1 | service health | `curl -s "$NLB/health" \| python3 -m json.tool \| head -40` | HTTP 200 · `field_stale:false` · `engine:"alive_core"` · `transit.real_feeds` bus+metro `true` · `build_sha` = the deployed tag (`7c68c8bc` family — re-check anytime with this same curl; a flip means a task restart or a freeze-break, see T-5) |
| 2 | plan serving (priced engine) | `python3 tools/warm_task.py` | exit 0 → prints `WARM: priced engine serving after Ns`; last line `/tiles/health ok — 22.7 MB` |
| 3 | field age < 20 min | `curl -s "$NLB/health"` → `field_age_s` | `< 1200` (it peaks ~920 s then resets on the ~15-min cycle — a stuck reading >1200 s means the ingest loop died) |
| 4 | APK installed + warmed | on the phone: app opens → home hero shows a live "outside" number → search India Gate → Huda City Centre → plan lands → back to home | install the latest `alive108-<sha>.apk` from the final freeze-cut — **check the recut report for the sha** (newest `docs/lanes/apk-*-report.md`) and `shasum -a 256` the file against it; `alive108-c3f7e9e.apk` is the OLD freeze (predates the offline-pack fix — its r1 pack warms zero tiles), `c3bb731`/`0b11123` are **never** (30–40 Mobile commits behind) |
| 5 | admin login works | `TOKEN=$(aws secretsmanager get-secret-value --secret-id alive108/admin-token --query SecretString --output text)` then `curl -s -D- -o /dev/null -X POST "$NLB/v2/admin/login" -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN\"}" \| grep -i '^set-cookie'` | `alive_admin=v1.<exp>.<sig>; HttpOnly; Max-Age=28800` — proves token + endpoint good before you need them on camera |

**NO-GO conditions (cut or fix, don't fake):**
- `/health` `field_stale:true` or `field_age_s` stuck > 1200 s after two
  refresh cycles (~30 min).
- `warm_task.py` exit 1 — engine never priced within the timeout.
- Demo-OD plan returns `options:[]` twice in a row (one honest planner
  timeout is normal on cold far-ODs; two means cut to backup video).
- Public repo not pushed — disqualifier.
- APK crashes on open twice — demo the web surfaces (`/`, `/city`,
  `/admin`); same numbers.

---

## T-45 — pre-warm the phone + live-verify the moving lines

### The phone (3 min — kills the two cold-start traps from rehearsal-v2)

First boot on a fresh install is a gauntlet, not a demo: **welcome film
→ POST_NOTIFICATIONS dialog → 3-page onboarding (consent is page 3) →
location permission → home**. And the **first-ever plan runs the
chooser *behind* the vehicle wizard** — the signature beat plays
occluded. Both are first-run-only. So:

- [ ] APK installed + opened once **before** morning — grant every
  permission when the dialogs fire (notifications, location), swipe
  the onboarding pages, answer consent either way (it persists).
- [ ] **Now, on any working uplink**: open the app → search
  `India Gate` → `Huda City Centre` → let the compare sheet land →
  walk through the vehicle wizard once → **leave the app on home**.
  This clears the wizard so tomorrow's on-camera chooser plays clean,
  seeds every last-good cache — **and caches the map tiles over the
  demo corridor**. The pack fix is live on prod but any APK installed
  before the freeze re-cut still carries r1-era code that downloads
  zero tiles — only the viewport you actually panned renders offline,
  so panning the demo OD now is what makes the map survive a dead
  hall. (On the re-cut APK the r2 pack pulls all 744 NCR tiles itself
  — pan anyway, belt-and-braces.)
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
#    today: pct 17→25→29 across reads (row present all day). If it
#    reads ≤8 tomorrow the row is gone — narrate the curve's
#    dip→overnight climb instead (see fallback table).

# 3) The plan numbers you'll quote — demo OD only:
curl -s -X POST "$NLB/v2/plan" -H 'content-type: application/json' \
  -d '{"from":{"lat":28.6129,"lon":77.2295},"to":{"lat":28.4958,"lon":77.0854}}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); o=d['options']; print('opts:',len(o),'took_ms:',round(d.get('took_ms',0)),'degraded:',d.get('degraded')); [print(' ',x['mode'],(x.get('dose_ug') or {}).get('mid')) for x in o]"
#    today: 20–22 opts, car-AC 7.4–8.9, walk 254–307 → ~34–35×,
#    metro+walk PRESENT (48.5 → 58.8). Confirm a `metro+walk` row
#    exists — if absent, the "car beats metro" clause comes out.

# 4) The state of the machine:
curl -s "$NLB/health" | python3 -m json.tool | head -30
#    build_sha (demo build — `7c68c8bc` family; re-check: this same
#    curl — a flip means a task restart or a freeze-break, not field
#    drift), field_age_s, stations count (51–54 drift band), wind.

# 5) Full sweep if you have 3 min — prints FLAGS for anything stale:
bash scripts/verify_numbers.sh
```

### Pinned numbers that DON'T move (verified today, quote freely)

- spread on the demo OD: **~34–35×** (34.4× at rehearsal, 34.5× on my
  13:00 UTC probe) — say "more than thirty times"
- options count: **"about twenty"** (16–22 seen today; swings 9–24)
- car-AC vs walk on the demo OD: **about seven-to-nine vs
  two-fifty-to-three-hundred µg** — read the screen, it ranges
- chooser pill: holds **~4.2 s, twice** ("cleanest and fastest" →
  "cleanest · N% less than fastest") — narrate the SECOND pill, it
  carries the quantified claim; let the animation finish before
  reading the ladder
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
  (ios-release-residual) — the ~47% dev-debug crash is a
  dev-inspector-only race; honestly a post-demo engineering item.
- `/v2/skill` answers in **~0.7 s on prod** (was ~6 s — deploy4).

---

## T-30 — admin sign-in + physical setup

### Admin sign-in (60 s — full playbook `docs/plan/admin-login.md`)

- [ ] Have the operator token physically at hand — **phone note or
  paper**, not a laptop you'll unlock on stage. (Secrets Manager
  `alive108/admin-token`; fetch cmd in the GO/NO-GO table.)
- [ ] In the demo browser open `$NLB/admin` — a guest lands on the
  **gate card** ("engine room · OPERATOR ONLY"), not the board.
- [ ] Paste the token → **SIGN IN** → board renders + ticks ~30 s.
- [ ] **Chrome will offer "Save password?" → tap Never.** The token
  does not go into a password manager on a shared machine.
- [ ] If it says `wrong token`: re-paste carefully — **5 bad tries →
  429**; wait ~5 s, one clean attempt passes.
- [ ] Judges never go near `/admin`? Leave it gated — the gate card
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
# ^ task alive, `build_sha` still in the `7c68c8bc` family, field fresh.
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
| 1 | 0:00–0:12 | `/` landing — live raster + wind arrow | "not a video — the live field over NCR, right now; the arrow is today's real wind" |
| 2 | 0:12–0:30 | `/aqi` at Connaught Place | "US AQI in the 150s ⟳ LIVE — built minutes ago from ~52 live instruments + a satellite model, kriged by our own C++ engine; the countdown is the 15-min field heartbeat" |
| 3 | 0:30–1:05 | **phone**: India Gate → Huda City Centre plan → chooser → compare ladder | "about twenty options — watch them draw as equals before the winner settles and names why … same road, same minutes: on foot ~two-fifty-to-three-hundred µg, a sealed AC car about seven-to-nine — a thirty-times spread the map you use today never tells you." **Metro clause only if the row exists**: "metro plus walk about fifty — the sealed car beats it, because the clean coach is bookended by road-level walks." Let both ~4.2 s pills play. |
| 4 | 1:05–1:30 | `/depart` curve (app's 24 h window) | "when you leave matters as much as how — this is the same trip re-priced every departure hour; it climbs overnight." If the leave-later row is up: "leave ~HH:MM — ~N% less" (read it off screen). |
| 5 | 1:30–1:55 | `/v2/city` + `/community` + `/admin` | "every donated trip becomes a live sensor — the air varies street to street, and a street only publishes after 3 different riders cross it; the privacy is in the math." Community counts ⟳ LIVE from `curl $NLB/community`. |
| 6 | 1:55–2:20 | AWS console — ECS `alive108` | "real infrastructure: ECS Fargate behind an NLB — one task, healthy, Spot-priced; DynamoDB holds only aggregates." Read task-def off the console, never a memorized number. |
| 7 | 2:20–2:40 | `/admin` field map — species pills | "we hold one rule: no fake precision — the band is *measured* (95.2% @2σ over 3,550 held-out station-hours). Ten pollutants ride the lattice — ammonia is honestly empty — click NO₂, it's a different map, not a relabeled layer." |
| 8 | 2:40–2:50 | back to `/` | "dose every 250 metres for the rider, emissions per mode for the city — ALive-108, the map that prices the air." |

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
| chooser pill | text differs from the script | the pill quotes the server's `reason_line` verbatim — read whatever it says; it's the engine's own words |
| dose ladder | numbers drifted | "they move with the field — read the screen: about seven-to-nine vs two-fifty-to-three-hundred" — say the range, never a stale constant |
| metro clause | no `metro+walk` row | drop the clause entirely — the road-mode rows alone carry the ~35× spread; transit rows honestly absent ≠ a bug |
| leave-later | row absent (`pct ≤ 8`) | "today the curve is flat — the honest answer is 'it doesn't matter when'; on a swing day it tells you the cheaper hour" — narrate the dip→overnight climb on the curve |
| `/v2/day` windows | both `null` | "no meaningful window today — flat air all day" — the `decisions` row says it in plain words; read `hours[]` + `day_mean_pm25` out loud |
| fires aside | `carrying:false`, or modifier `null` | "fires burn in the belt every day — today the wind isn't carrying it to us; the model checks, and honestly says no" |
| community counts | numbers not on the app surface | they're wire-level totals — open `curl $NLB/community` in the browser (or the admin board) and read `obs_total`/`contributors`/`avoided_ug_all` live |
| admin login | 429 rate_limited | wait ~5 s, one clean paste — the bucket refills ~1/5 s |
| admin login | `admin auth is not configured` (503) | task env lost the token — deep failure; demo everything else, gate card still tells the privacy story |
| venue Wi-Fi | anything stops loading | switch the phone to the hotspot you armed at T-30; captive portals kill plain HTTP silently |
| venue Wi-Fi + hotspot | **both** dead | the app still demos air-gapped: bundled 124k-row gazetteer search, a pre-planned route's nav leg, receipt, ledger, day log all work offline (8/8 honesty checks). Basemap: the pack fix IS live on prod (`GET /v2-light.json` serves, `region_tiles`=744 verified on iOS sim — `offline-pack-fix-report.md`) but it only reaches a phone via the freeze re-cut — **any APK installed before it still warms zero tiles**, so on this morning's install the map renders only where the T-45 pan cached it (ambient cache is the plan, not a fallback). On the re-cut APK the whole NCR z9–13 pack is already local. Only a **new** plan honestly refuses — for server beats, cut to `cut1.mp4`/`cut2.mp4` on the phone |
| APK | crashes on open | relaunch once — every state persists (consent, vehicle, recents, ledger); back on the map in <1 s. Crash twice → web surfaces carry the same numbers |
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
- **iOS is not the demo device** — and the release build is now
  measured clean: **0/60 cold launches** on the reference rig
  (`ios-release-residual-report.md`; sim-verified — a device release
  build is unmeasured). The ~47% residual is dev-debug only: the
  crash victim is the React dev inspector, which doesn't exist in
  release builds — fixing the underlying race is a post-demo item.
  Android stays the demo target (never crashed in E2E).
- **Read the screen, not the script.** The pinned ranges above are
  honest; a recited constant that the field moved past is a gotcha,
  not a feature.
