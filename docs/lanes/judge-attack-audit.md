# judge-attack-audit.md — the hostile judge

**Verified 2026-10-07 ~00:20–00:45 UTC.** Every claim below was re-derived this session
against live prod (`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, build
`ce01ec5c`) or cited to `file:line` in the repo at HEAD. GET-only probes except one
`POST /v2/plan` (read-only query surface, canonical OD CP→Gurugram — same as
`scripts/verify_numbers.sh`).

This audit assumes the judge has our GitHub link open in one tab and the live
endpoints in another. The standard is not "is it defensible in a design review" —
it's "does it survive a skeptical expert reading the actual wire."

---

## The 3 attacks most likely to land on stage

### 1. "Your citizen layer is empty — 'measured by its own commuters' is a ghost town."

The privacy-preserving citizen sensor is the pitch's spine. Live tonight:

- `GET /community` → `obs_total: 22`, `contributors: 14`, `latest_obs_age_min: ~1630` (≈27 h), `obs_24h: 0`
- `GET /v2/city/moves` → `39 trips / 7d`, `12 of 54 corridors` publishable

Fourteen contributors total — almost certainly all dev devices. A judge who taps
"how Delhi actually moves" on DelhiToday, or curls `/community` during Q&A, sees a
layer that has never carried a real commuter. The k≥3 suppression is working *as
designed* — the emptiness is honest — but "honest emptiness" is still emptiness.
Every corridor-merge, privacy-pipeline, and community-field claim in the pitch
reduces to "infrastructure for a crowd we don't have." If a rival built their demo
on seeded synthetic data, they look more alive than us on stage.

### 2. "'Nothing leaves your phone' — over plaintext HTTP."

Prod serves **HTTP :80 only**. `https://` :443 times out (verified 00:35 UTC);
`scripts/deploy.sh:256` creates a single NLB listener `--protocol TCP` with no
certificate, no TLS, no 443. The release APK's `EXPO_PUBLIC_API_URL` points at the
same `http://…elb…` hostname (`Mobile/src/components/shell/net.ts:9-13`).

Every privacy guarantee in the repo — trim-300 m, thin-100 m, round-4dp, k≥3,
hashed token — is an **at-rest** guarantee. In transit, `POST /v2/trip` sends
trip cells + dose + vehicle class in cleartext through Delhi cellular networks and
whatever WiFi the demo phone is on. One sentence kills the pillar: *"your
'privacy-first' dosimeter ships consented movement data unencrypted."* The honest
counter (payload is already aggregates, no credentials, no domain → no cert) is
true and will not sound like it. This is the cheapest fix in the whole report —
a domain + ACM cert + a TLS listener — and it isn't done.

### 3. "Show me the AWS: your scheduler is a `for` loop and your DynamoDB can't be seen."

The sponsor criterion is AWS depth. The committed evidence:

- All three `infra/schedules/*.json` are `"State": "DISABLED"` with literal
  `"${*_TARGET_ARN}"` placeholder ARNs (`ingest-15min.json:7,10`;
  `rollup-daily-0030IST.json:7,10`; `validate-weekly.json:7,10`);
  `provision.sh` auto-disables on `*STUB*`.
- The real 15-min tick is an in-app daemon thread —
  `server/main.py:1867-1885` `threading.Thread(target=_ingest.run_forever)`.
  `deploy.sh` provisions exactly **one** service, **one** task definition,
  `desired-count 1` — there is no separate ingest worker task.
- Daily rollup + weekly validation may never run anywhere: the in-app loop is
  off unless `ALIVE_ROLLUP_IN_APP=1` (`main.py:1931-1961`), the EventBridge jobs
  are disabled, and their only readers are admin endpoints behind 401. The S3→local
  mirror (`_start_rollup_mirror`) faithfully syncs a shelf nothing has proven to
  stock.
- DynamoDB liveness is unverifiable from outside: public `/health` hand-picks its
  keys (`main.py:299-346`) and omits `trips_backend` — that field exists only in
  `health.py:361`'s `collect_health()`, which serves the 401-gated admin API.
  `store.py:_select_trips` (332-352) silently falls back to `backend="memory"`
  if boto3/credentials don't resolve. Aggregates could be RAM-backed tonight and
  no public surface would say so.
- `docker-compose.yml` runs the same product locally — the literal "$5 VPS" jab.

Counters exist (S3 archive live — `/v2/archive` recorded hours + `alive108-air`
bucket; `AGG_TABLE`/`COMMUNITY_BUCKET` set in the task env, `deploy.sh:204-208`;
boto3 installed per `requirements.txt:4`) — but none of it is *provable* to a
judge from the public wire, and the EventBridge story in `18-aws-architecture.md:30-31`
describes a topology that is aspirational, not running.

---

## Full attack table

### TECHNICAL

| attack | where it bites | how hard | honest counter we have | counter we DON'T have |
|---|---|---|---|---|
| "Kriging adds nothing — your own file says IDW ties it." | `server/data/field_validation.md:16` — "kriging does not beat IDW on this window" (MAE 21.8 IDW vs 22.0 kriged, 3,550 held-out pairs) | **High** with a stats-literate judge — our geostat pitch dies on our own linked artifact | Kriging is kept for the σ it emits, not the µ — IDW can't produce a calibrated interval; the ±band is the product of the krige | Any window where kriging demonstrably beat IDW; a justification for keeping the heavier method on the landing copy that names it |
| "Your 'self-grade' grades the model against itself." | `server/skill.py` — pairs = served-forecast snapshot vs the pipeline's *own later recorded field*; for non-station cells both sides are the same model+krige blend. `band_hit_pct` is CPCB-band equality, not σ-coverage. Live: h+1 80.8% → h+11 **21.7%** | **High** — "the model grades itself" is a headline beat; the honest version is "consistency check" | The mechanism is genuinely real (persisted forecasts, scored later); the wording is precise if read carefully; MAE ladder is published | A live score against held-out *instrument* truth — `field_calibration.json` is a static artifact, not a live loop |
| "Your real error is worse than your headline." | `/aqi.calibration` on the wire: `mae_ug 46.1`, `median_abs_pct 56.0`, `n_stations 94`; `field_validation.md`: MAE 22.0, **bias +51.6%** | Medium-high — the numbers are ugly but self-published | Radical-honesty posture: error bars exist *because* error is large; at a station the field reads the instrument; LOO ≠ forecast skill; 95.2%@2σ coverage is calibrated, not assumed | One sentence answering "what's your error, full stop" — 46.1, 22.0, 8.5, 4.2 all float on different surfaces measuring different things; a judge picks the worst |
| "33× is a strawman — nobody walks 23.7 km." | `POST /v2/plan` CP→Gurugram: walk 276.9 µg vs car-AC 8.7 µg ≈ **32×** live tonight; distance 23.7 km | Medium — lands as a heckle, not a kill | Decomposition is real (conc ~2.4× × time ~10× × VE ~1.4×); NUMBERS.md §103 shows 31–45× across ODs; metro+walk 40.2 is the realistic alternative; product sells time-shifting (`/depart`: tonight −8% best vs now), not mode-shaming | A headline that isn't the extreme pair — "up to 33×" invites the heckle by construction |
| "The C++ engine is OSRM + a price tag." | Live plan wire: every baseline route is `router_backend: "osrm-local"`; `alive_core-path` only generates `least-smoke` alternates | Medium | The dose-priced alternate generation is the thing OSRM can't do (non-trivial edge weights re-priced every 15 min in-memory); the *recommended* row is an engine row (car least-smoke 8.8 vs OSRM fastest 8.3); benches are C++-vs-Python (`docs/plan/bench-results.md`) | A bench vs re-weighted OSRM producing the same alternates — the comparison was never run, so "why not just re-weight OSRM" stands unanswered |
| "1.07M edges is unverifiable." | `/health.routing.edges` = 1,070,459 live; `route_graph.meta.json` committed | Low | Verifiable tonight; `edges_priced` 903,058 echoes the "0.90M" landing claim exactly | — |
| "The ±band is decorative." | `airfield.py:1003-1016` — `σ_total = sqrt(σ² + (0.12µ)²) × SIGMA_CAL(3.2)`; `sigma()` returns `None` outside coverage (1021-1044) | Low | SIGMA_CAL is calibrated against measured coverage (29%-of-nominal raw → honest 95.2% @ ±2σ); `nearest_sample_km: 1.8` echoes live; no fake precision off-coverage | — |
| Cold-start honesty | `main.py` transit compiled at boot; `/health.transit` live `{on_disk, compiled, real_feeds}` | Low | Verified live; GTFS baked in image, no runtime fetch | — |
| "15-min field" cadence | `field.age_s 239`, `refresh_in_s 661`, `stale_after_s 2700` live | Low | Rebuild cadence real; staleness honestly flagged on wire | Field can legally serve up to 45 min stale; "live" is "≤15 min old" — thin attack but quotable |

### PRIVACY

| attack | where it bites | how hard | honest counter we have | counter we DON'T have |
|---|---|---|---|---|
| Plaintext HTTP transport | NLB TCP:80 only (`deploy.sh:256`); https :443 dead; app `API` = `http://…elb` in release (`net.ts:9-13`) | **Critical on stage** | Payload is trimmed aggregates; no credentials on the wire | TLS — needs a domain + cert; absent tonight |
| Skip → sharing ON, disclosure doesn't travel | `OnboardingScreen.tsx:175` `skip = () => finish("on")`; the `consent_footnote` renders only inside `step===2` (:376-378) — a page-0/1 skipper consents unseen | High with a privacy judge | Consent page itself is a real equal-weight two-button choice; Settings one-tap undo; receipts echo donated/private; documented default (doc 07 §3) | Opt-in-by-default — the gold standard the skeptic invokes. "Skip = donate" is indefensible phrasing no matter the UX intent |
| Outbox resurrect-after-wipe | `nav/engine.ts:288-294` fail→`enqueueTripDonation` vs `offline/queue.ts:210-215` `clearOutbox` — no generation check; flagged `docs/lanes/mobile-audit.md:26` | Medium-high — "delete my data" leaks | Narrow timing window (donate-fail → delete → enqueue); post-wipe enqueues are still consent-gated | The fix — a generation counter like `api/cache.ts:93-103` already has |
| k≥3 vs sybil / field poisoning | `POST /v2/trip` is unauthenticated; k = distinct *hashed tokens* (`community.py:89`, `_token` sha256[:16] of self-chosen id — mintable); `dose_ug` accepted to 50,000 (`trip.py:88-89`); implied-C `dose/(VE·dur·microenv)` has **no plausibility clamp** in `corridor_field_samples` (701-731); `corridor_estimate` merges into the krige posterior unclamped (`airfield.py:1006-1016`) | Medium — technical, invisible on stage, but real | Corridor cells weigh 1× vs stations' 3×; median-of-3 + 72h window + speed/duration bounds (140 km/h, `trip.py:125`); currently zero live corridor data anyway | Device attestation, rate limit, or an implied-C sanity bound — a script can write the field tonight and nothing would log it loudly |
| Rotating-token linkability | `Mobile/src/community.ts` — contributor id `anon-`+16 hex, 30-day TTL; donations within a window share one hashed id | Low-medium | Disclosed; rotation bounds the window; raw token never stored server-side (hash only) | — |
| NLB sees raw IPs | inherent to any NLB; no mitigation claimed | Low | "Aggregates only" is about what leaves the phone, and it's true of the payload | Nothing — transport metadata is unaddressed by the whole design |
| Bearer device token | `trip.py` sha256[:16] — replayable if extracted from the device | Low | Hash-at-ingest; tokens are write-only (no read API binds history to a token server-side) | — |
| `daylog.json` editable → dose is self-reported | Donated `dose_ug` comes from the client's own store; server bounds (50 k) but doesn't recompute | Medium | Implied-C inversion bounds what a fake dose can claim; k≥3 + 72h; ledger/receipts are self-display only — nothing downstream *trusts* the number financially | Server-side recompute from donated geometry — would double-trim privacy anyway; the honest answer is "the corridor layer is the anti-fraud check, not the dose field" |

### AWS-DEPTH

| attack | where it bites | how hard | honest counter we have | counter we DON'T have |
|---|---|---|---|---|
| EventBridge all disabled / stub ARNs | `infra/schedules/*.json` — all `"DISABLED"`; `provision.sh:147` `*STUB*`; real tick is `main.py:1867-1885` thread | **High** — sponsor-visible | `18-aws-architecture.md:31` + code comments say "in-app loop owns it" — the docs don't hide it; rollup/validate are genuinely better as scheduled jobs than threads | Enabled schedules or a public artifact proving the jobs ran — `admin/api/validation` is 401 so the outputs can't be shown live |
| DynamoDB load-bearing? | `store.py:332-352` silent memory fallback; `trips_backend` hidden from `/health` (main.py:299-346 vs health.py:361) | Medium | `AGG_TABLE=alive108-agg` + `COMMUNITY_BUCKET` in task env (`deploy.sh:204-208`); boto3 installed | Public proof — one extra key on `/health` would close it |
| "$5 VPS" | `docker-compose.yml` runs the whole product | Medium | Real AWS plumbing: NLB Elastic-IP, CodeBuild→ECR→Fargate, S3 archive (`/v2/archive` live: `bucket alive108-air`), Secrets Manager keys | A *feature* that requires AWS — everything user-facing is one Python process; the moat is architectural honesty, not service count |
| Secrets Manager decorative? | keys fetched via env in task def | Low | Standard practice for ECS | — |

### PRODUCT

| attack | where it bites | how hard | honest counter we have | counter we DON'T have |
|---|---|---|---|---|
| "Does a Delhiite need a dosimeter?" | onboarding = 3 steps + vehicle sheet; location permission lazy at nav start (`nav/engine.ts:522`) | Medium | The dosimeter answers "when to leave / which road / what did I breathe" — daily-decision utility; PUC ask is optional post-onboarding; city surfaces need no app at all | A user story from a real non-dev Delhiite — all evidence of use is our own devices |
| PUC certificate ask | `VehicleSheet.tsx` — fuel→year→PUC readings (CO%/HC ppm, diesel smoke-opacity), `:89-104` | Medium | Calibrates *your own tailpipe* emissions for the ledger — novel, voluntary, off the critical path | Nothing — it's a real friction point by design; the ask is unusual and will be questioned |
| Hindi parity bolted-on? | `i18n/strings.ts` — 556 keys with `hi` mirror; `modeLabel()` localizes even "least-smoke rd/alt N" engine suffixes (:1263+) | Low | Real depth — verified | Residual: server-computed `reason_line`, gazetteer place names pass through English; `dataFromModelOnly` still says "estimated from satellites" (CAMS is model assimilation — loose wording) |
| iOS SIGSEGV residual | `docs/plan/go-nogo.md:21` — documented demo APK `e849bf6f` predates fix `266d0d9` + all dosimeter surfaces; `mobile-audit.md:28` — residual SIGSEGV observed 1/2 on search-sheet open | **High if not rebuilt** | Guards verified (no Modal imports, JS-driver sheets, REPORT_POOL never unmounted); take-2 iOS video crashed on *sim* GPU kill, not app bug | A rebuilt APK on demo HEAD — the sibling lane owns it; if it doesn't land, the stage demo runs a pre-dosimeter build with a known crash class |
| Landing links its own counter-evidence | `landing.html` step-02 links `field_validation.md` right beside "95.2% inside ±2σ" — the click shows ±1σ 53.2%, "kriging does not beat IDW", IGNOU +598% | Medium | Transparency-as-brand; the citation is the credibility | Nothing — a judge who clicks sees the underbelly before we can frame it |

### CLAIM-vs-TRUTH (live re-verification, 2026-10-07 ~00:30 UTC)

| claim | where | verdict |
|---|---|---|
| 1.07M edges / 0.90M priced | landing, README | **TRUE** live — 1,070,459 / 903,058 (`/health.routing`) |
| 54 instruments | landing `stnHero` (JS-overridden live) | **TRUE** now — `stations.count 54`, feeds `waqi+dpcc` both `ok` |
| "instruments report every 15 minutes" | `landing.html` step-01 | **LOOSE** — the *field* rebuilds every 15 min (`age_s 239`, ttl 900); WAQI sub-index cadence is not ours to claim; DPCC pages are 5-min when live |
| "kriging… every cell keeps its own error band" | `landing.html` step-02 | **TRUE-ish** — `kriging: "on"` on wire; band is posterior σ, None off-coverage |
| MAE claim | wire | `/aqi.calibration` serves `mae_ug 46.1 / n 94 / "OpenAQ"` — real but stale label: DPCC instruments now feed the field while calibration artifact predates them |
| "9M station-hours" | NUMBERS.md:74 | Flagged **unverifiable** in our own ledger — not quoted on current surfaces (good hygiene, keep it that way) |
| 33× walk-vs-car | every surface | **TRUE** — 276.9 vs 8.7 µg tonight (≈32×; 31–45× range across ODs per ledger) |
| `band_hit` | `/v2/skill` | Real but it's CPCB-band equality, h+11 = 21.7% — quote horizons honestly |
| community "live" | `/community` | **ROTTED on stage terms** — 22 obs all-time, obs_24h = 0 |
| `/observe` retired | `/observe` → 410 | TRUE |
| `/v2/ledger` | 422 without params | TRUE (not a bug — needs params) |

### META

| attack | how hard | honest counter we have | counter we DON'T have |
|---|---|---|---|
| "Wrapper over WAQI+DPCC" | Medium | Feeds are *inputs*; the product is fusion (krige over WAQI+DPCC+CAMS prior), dose-priced routing (local OSRM graph + C++ engine), GTFS compiled in, on-device dose ledger, k≥3 aggregate donation — none of that is a fetch | The *field alone* is genuinely fetch+krige over public sources — if the pitch foregrounds "the field," the attack lands; it has to foreground the dosimeter |
| "Dose math is one multiplication" | Medium | `exposure.py:51-149` — microenv factors (metro .45 / car-AC .55 / walk 1.30) + VE tables with citations [1]-[6]; the multiplication runs *over a priced 1.07M-edge graph* + forecast + your vehicle's emissions — "yes, and it's legible on purpose" is the honest flex | Nothing — but rehearse it: the simplicity is the *point* (auditable ≠ trivial) |
| "Fetch-of-fetches" | Medium | OSRM is *local* (own OSM build: 1.07M edges, 230 turn bans, 3,428 access overrides); transit is compiled GTFS; FIRMS CSV self-ingested; S3 archive self-built | The station layer depends on DPCC scraping — public pages, 5-min cadence, `ingest_dpcc.py` with UA/ModSecurity workarounds; one WAF change ends the "54" claim (stall is armed in judge-proof; the *scrape-evasion* optic is not) |
| "AI-built repo" (docs/lanes is 50+ Devin lane reports) | Low | The lanes *are* the engineering record — cite them as transparency | The optics that the product is codegen, not craft — countered by showing the C++ engine + krige math nobody asks an LLM to wing |

---

## Attacks that fail — with proof

Accusations a judge could try that the evidence defeats:

1. **"It's dressed-up nearest-neighbor."** Fails: `/aqi` returns `kriging:"on"`, `sigma_coverage:"per-query"`, `nearest_sample_km` echoed (1.8 km at CP — transparency, not hiding); `airfield.py` krige posterior + `_clamp_krige`; IDW is a *documented* fallback, not the serve path. The nearest-cell snap (`_snap_nearest`, :852) only runs at the coverage edge and reports its own distance.
2. **"The ±band is decorative."** Fails: `SIGMA_CAL=3.2` was calibrated against measured 29%-of-nominal raw coverage (`airfield.py:996-1004`); `sigma()` returns `None` outside coverage — no fake precision (`airfield.py:1018-1044`); 95.2%@±2σ is a *measured* artifact figure (`field_validation.md`), not a hand-pick.
3. **"33× is fabricated."** Fails: re-derived live this session — walk 276.9 µg ÷ car-AC 8.7 µg ≈ 32× on the canonical OD; decomposes into conc ×~2.4 × duration ×~10 × VE ×~1.4; ledger shows 31–45× across ODs all week (`NUMBERS.md:103-104`).
4. **"1.07M edges is a slide number."** Fails: `GET /health` `.routing.edges` = 1,070,459 and `.edges_priced` = 903,058 — live, unhardcoded, matching `route_graph.meta.json`.
5. **"'No uploads' is a lie — trips are donated."** Fails *as stated*: donation is consent-gated (`nav/engine.ts:322-327` `s.donated = await donate(s)` inside `shareEnabled` dep); the pipeline trims/thins/rounds before anything persists (`trip.py` TRIM_M=300, THIN_M=100, ROUND_DP=4, H3 res-8, bounds clip); `/observe` returns 410. *Caveat:* this defeats the absolutist attack — the skip-default and plaintext transport above are the versions that actually bite.
6. **"C++ engine is vapor."** Fails: `engine:"alive_core"` on `/aqi` wire; `engine:"alive_core-path"` + `engine_dose_ug` on every least-smoke plan option; the recommended row tonight IS an engine path (8.8 µg); benches committed (`docs/plan/bench-results.md`, re-runnable `tools/bench_*.py`).
7. **"The field is fake/static."** Fails: `field.built_at` 00:32 UTC, `age_s` 239, `refresh_in_s` 661, `samples` 102, `station_readings` 54, `stations_status {waqi:ok, dpcc:ok}`, `smoke_modifier` 1.1 with live wind — the field is measurably alive between probes.
8. **"Hindi is a veneer."** Mostly fails: 556 keyed strings with `hi` mirrors; engine suffixes ("least-smoke rd") re-localize; receipts/ledger/onboarding covered. Residual leaks (server reason lines, gazetteer names) are cosmetic, not structural.
9. **"Cold-start is hidden."** Fails: transit feeds baked+compiled at boot; `/health.transit` exposes it; cold plan measured ~5.6–6.6 s on a fresh OD tonight (5643 ms on the wire), consistent with the documented 6.6 s claim.
10. **"The archive is fake."** Fails: `/v2/archive` serves recorded hour indices ([1,3,4,5] tonight) + `bucket: alive108-air` + per-hour snapshots with real gaps — a fake archive would have no gaps.

---

## Bottom line for the room

The honest-posture moat is real — most "gotcha" attacks fail because the project
self-publishes its worst numbers. Where it still bleeds:

- **Ship-fixable before demo:** TLS/domain; `/health.trips_backend`; a footnote
  render on every onboarding step (not just step 2); APK rebuild on HEAD for the
  SIGSEGV class + dosimeter surfaces.
- **Narrative-fixable:** never say "live citizen layer" — say "the privacy
  pipeline is live, the crowd is the launch"; never say "the model grades itself"
  without adding "against its own later field — instrument grading is on the
  method page"; answer the AWS question with the CodeBuild→ECR→Fargate→S3 pipeline,
  not EventBridge.
- **Structural, unrehearsable:** the community layer is empty, the transport is
  plaintext, and the schedules are stubs. Those three are where a prepared judge
  earns their chair.
