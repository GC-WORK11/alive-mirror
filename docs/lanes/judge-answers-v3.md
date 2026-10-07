# judge-answers-v3 — the demo-morning card for the NEW attacks

The second armed-answer card. `judge-proof.md` covers the first ten hardest
questions; this one covers the attacks `judge-attack-audit.md` (0f5f879)
surfaced after it — the ones most likely to be asked *by a judge who has
our GitHub open in one tab and the live wire in the other*.

Format per attack: **THE ATTACK** (as a judge would say it) · **THE HONEST
ANSWER** (≤3 sentences you can say out loud) · **THE PROOF** (endpoint +
field / file:line / lane report) · **THE WEAKNESS LEFT** (stated plainly —
no spin). Where the honest answer is "we're weak here", the card says what
to say plainly.

Every figure re-verified against live prod
(`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, build `bc8f82c4`)
and `base/v2` HEAD on **2026-10-07 ~01:20 UTC**. Numbers drift with the
field — say "about ~N" and re-run `scripts/verify_numbers.sh` at T-45.

---

## 1. "Your citizen layer is empty."

**THE ATTACK:** "'Measured by its own commuters' — /community shows 22
observations all-time, zero in the last 24 hours, 14 contributors. That's
a ghost town, and a rival with seeded data looks more alive than you."

**THE HONEST ANSWER:** "It's 22 real donations from dev devices — and the
emptiness is the k≥3 gate working at real scale: 42 of 54 tracked corridors
are suppressed tonight because not enough distinct devices crossed them,
and the counter that says so is public. The field itself doesn't depend on
the citizen layer — it's instrument-driven, 54 government-grade reads plus
the model; donations only sharpen corridors where ≥3 devices have
traversed them in 72 hours. A seeded map wouldn't have a suppression
mechanism at all."

**THE PROOF:** `GET /community` → `obs_total:22`, `obs_24h:0`,
`contributors:14`, `top_corridors[].devices` = 6,4,4,3,4 (every published
row ≥3). `GET /v2/city/moves` → `min_k:3`, `n_trips:39` (7d), corridors
`active:12` of `tracked:54`. `server/community.py:702-731`
(`corridor_field_samples`: median needs ≥3 fresh traversals AND ≥3
distinct hashed devices or the cell emits nothing); `server/community.py:89-90`
(`_K_MIN_DEVICES=3`, `_CELL_WINDOW_S=72h`); `server/airfield.py:1012-1016`
(corridor estimate folds into the krige posterior only where coverage
exists — additive, never gap-filling); `/health.sources.stations` →
`waqi+dpcc` instruments carry the field.

**THE WEAKNESS LEFT:** The claim "infrastructure for a crowd we don't
have" is true tonight — every privacy-pipeline proof is real, but the
social proof of commuters actually using it is zero. The line above is
the whole answer; don't oversell the layer.

## 2. "'Nothing leaves your phone' — over plaintext HTTP."

**THE ATTACK:** "Your privacy-first dosimeter ships consented movement
data unencrypted. NLB is TCP:80 only; `POST /v2/trip` travels cleartext
through Delhi cell networks."

**THE HONEST ANSWER:** "True — the transport is plaintext today, and we
don't pretend otherwise: the README says 'no TLS terminator today'. What
travels is already an aggregate — no credentials, no identity, endpoints
trimmed 300 m — so the exposure is a coarse trip shadow, not a dossier;
but it's real, and closing it is a domain plus an ACM cert and a 443
listener, which we haven't provisioned."

**THE PROOF:** `scripts/deploy.sh:256` (single `create-listener
--protocol TCP` on :80, no certificate); `README.md:22` ("HTTP (NLB :80 —
no TLS terminator today)" — admitted in the repo, not discovered);
`https://…elb…` :443 connection times out (verified tonight). At-rest
guarantees that DO hold on the wire: `server/v2/trip.py:35-38` (TRIM 300 m
/ THIN 100 m / ROUND ~11 m), `:234` (sha256[:16] of the device token,
raw discarded, `trip.py:11` docstring "never stored, never logged");
`server/community.py:_fold` — no per-trip row ever created.

**THE WEAKNESS LEFT:** This is the cheapest fix in the whole audit and it
isn't done — "TLS via ACM + a 443 listener" is **not** provisioned
anywhere in `scripts/` or `infra/` (checked tonight). If a judge asks
"when", the honest answer is "a domain and a cert — it's the one real gap
we'd close first", not "it's in the pipeline".

## 3. "Your AWS is decorative — EventBridge stubs, an in-app daemon, and a docker-compose."

**THE ATTACK:** "All three schedules are DISABLED with placeholder ARNs;
the real tick is a `for` loop in the app; docker-compose runs the whole
product. This is a $5 VPS wearing AWS badges."

**THE HONEST ANSWER:** "Half right, and we say which half: the scheduler
layer is a scaffold — EventBridge is provisioned and honestly disabled,
and the docs don't hide that the in-app loop owns the tick. What's
load-bearing AWS is the deploy itself: the image is built in-cloud by
CodeBuild, held in ECR, run by Fargate behind an NLB on an Elastic IP,
aggregates sit in DynamoDB, the hourly field archive and the community
snapshot live in S3, and keys come from Secrets Manager — you can see two
of those on the public wire right now."

**THE PROOF:** Decorative, admitted: `infra/schedules/*.json` all
`"State":"DISABLED"` with `${*_TARGET_ARN}` placeholders
(`ingest-15min.json`, `rollup-daily-0030IST.json`, `validate-weekly.json`);
`infra/provision.sh` auto-disables on `*STUB*`; real tick =
`server/main.py:1880` `threading.Thread(target=_ingest.run_forever)`;
rollup in-app only if `ALIVE_ROLLUP_IN_APP=1` (`main.py:1942`);
`deploy.sh` provisions one service, one task def, `desired-count 1`.
Load-bearing: `scripts/deploy.sh:80-118` (CodeBuild→ECR in-cloud build),
`:244` (NLB Elastic-IP allocation + TCP target group), `:204-208` (task
env: `AGG_TABLE=alive108-agg`, `COMMUNITY_BUCKET`,
`ALIVE_AIR_BUCKET=alive108-air`), `:210-215` (Secrets Manager: openaq,
waqi, admin-token keys); `server/agg_ddb.py` (`DDBDeviceLedger`, rows
keyed `ledger#<hash>`); live `GET /v2/archive` →
`storage.bucket:"alive108-air"` + recorded-hours coverage; `GET /health`
→ `build_sha` = the ECR image tag.

**THE WEAKNESS LEFT:** Two things a judge can't verify from the public
wire and we shouldn't claim they can: whether DynamoDB is actually the
live backend (`store.py:332-352` silently falls back to `memory`;
`trips_backend` isn't on public `/health` — it only exists in the
401-gated `health.py:361` collect), and whether the rollup/validate jobs
have ever run (admin outputs are gated). If pressed: "the aggregate
backend is provisioned DynamoDB with an honest memory fallback — the
field archive and the deploy pipeline are the parts you can check from
outside."

## 4. "Kriging doesn't beat IDW on your own artifact."

**THE ATTACK:** "Your own `field_validation.md` says kriging MAE 22.0 vs
IDW 21.8 — 'kriging does not beat IDW on this window'. Why is the heavier
method on the landing page?"

**THE HONEST ANSWER:** "Because what kriging buys isn't a better mean —
it's the σ, and the σ is the product: it's the ±band on every /aqi read,
the dose band on every route, the thing that widens honestly where
stations are thin, and the posterior our corridor traversals merge into.
IDW can't emit a calibrated interval — our ±2σ band covers held-out
truth 95.2% of the time because kriging produces a real error estimate;
that file publishes both numbers because we'd rather show you the tie
than hide it."

**THE PROOF:** `server/data/field_validation.md` — the admission itself
(3,550 station-hours / 85 stations: MAE 22.0 kriged vs 21.8 IDW-only)
*and* the coverage table on the same page (±2σ measured 95.2% vs 95.4%
nominal under `SIGMA_CAL`). Mechanism: `server/airfield.py:77`
(`SIGMA_CAL=3.2`), `:996-1016` (`_krige_posterior`: `sd = sqrt(krige_sd²
+ (0.12µ)²) × SIGMA_CAL`, corridor estimate merges as a
precision-weighted posterior), `:1018-1044` (`sigma()` returns `None`
outside coverage — no fake precision); `server/exposure.py:341` (the σ
propagates into `dose_ug_lo/hi`). IDW is a documented fallback
(`krige.KrigeField` + "advection-weighted IDW fallback" in the
validation header), not the serve path.

**THE WEAKNESS LEFT:** No window exists where kriging demonstrably beats
IDW on MAE — the honest frame is "the mean is a tie; the band is the
reason". A judge who wants kriging justified on point-error alone won't
be moved.

## 5. "Your self-grade decays to ~22% by h+11 — and it grades the model against itself."

**THE ATTACK:** "/v2/skill: band-hit 88% at h+0 decaying to ~22% at h+11,
and the 'truth' side is your own recorded field. The model grades
itself."

**THE HONEST ANSWER:** "It does decay — every forecast does — and we
publish the ladder instead of hiding it; a low-twenties band-hit at
eleven hours out is the honest tail of a PM2.5 forecast, not a bug, and
the hit metric is strict CPCB-category equality, not 'were you close'.
On non-station cells the 'recorded' side does share our model+krige
blend — which is exactly why we call it a self-grade and publish the
method rather than calling it accuracy."

**THE PROOF:** `GET /v2/skill` live tonight — `pairs:227`, h+0 MAE 4.2 /
band_hit 88.3% → h+11 MAE 49.3 / band_hit 23.8% (the ~21.7% read was the
audit night's — the number drifts, the shape doesn't);
`server/skill.py` — earliest-capture rule, `MIN_PAIRS=5` thin floor,
hourly realizations only ("a handful of hours is one weather regime, not
a score"). For the instrument-truth comparison judges want: the rebuilt
LOO calibration at HEAD (`server/data/field_calibration.json`, commit
`6ad7de6`) — real krige refit per held-out WAQI+DPCC instrument,
`mae_ug:8.8`, `n_stations:70`, bias +0.2 — so at-horizon error past
~h+3 is honestly larger than between-station error; we don't claim
otherwise.

**THE WEAKNESS LEFT:** There is no live grade against held-out
*instrument* truth — the self-grade's ground truth is our own pipeline
output, and the older "h+4 ≈ station disagreement" counter died with the
rebuilt LOO (8.8, not 46.1 — forecast decay past ~h+3 is genuinely
worse than interpolation error). The honest lines are the published
ladder and the live self-grade itself — don't reach for a comparison
the numbers no longer support.

## 6. "46.1 MAE on the wire vs your 95.2% headline — which is it?"

**THE ATTACK:** "Your /aqi serves `mae_ug:46.1` while the pitch says
95.2% inside ±2σ. Those can't both be good."

**THE HONEST ANSWER:** "They measure different things, and the 46.1
itself is a stale artifact we already caught: leave-one-out is the
'between stations' error — delete an instrument, interpolate at its
spot — while 95.2% is coverage, whether the band we state actually
contains reality at the rate we claim, measured on 3,550 held-out
station-hours. We found the published LOO was OpenAQ-era and quietly
broken, rebuilt it as a real krige refit over the live WAQI+DPCC
instruments, and the honest between-stations number is now 8.8 µg —
that lands on the wire with the next deploy. The band exists because
point error exists; a service that hid either number would be lying,
we publish both."

**THE PROOF:** `GET /aqi` → `calibration` still serves the old artifact
on the deployed build `bc8f82c4` (`mae_ug:46.1`, `n_stations:94`,
`method:"leave-one-out over live OpenAQ instrument readings"` — deploy
lag, verified tonight); `server/data/field_calibration.json` at HEAD
now reads `mae_ug:8.8`, `n_stations:70`, `median_abs_pct:8.8`, bias
+0.2, `method:"leave-one-out over live WAQI+DPCC instrument readings
(krige refit per held-out station)"`; commit `6ad7de6` — the fix commit
says plainly why the old number was stale twice over (OpenAQ is the
dead last-resort leg; the old selector matched 0 stations under the
co-pollutant blend); `server/data/field_validation.md` — the *same
window* publishes MAE 22.0 (point error vs archive truth) AND ±2σ
coverage 95.2% vs nominal 95.4% — coverage and error in one table, not
cherry-picked apart.

**THE WEAKNESS LEFT:** Deploy lag is the residual — a judge hitting
`/aqi` tonight still sees 46.1 while the repo says 8.8, and either
number is only "true" for its measure (8.8 LOO between stations / 22.0
archive window / 6.2 post-DPCC at-instrument holdout). The one-liner if
asked "what's your error, full stop": "about 9 µg between stations by
the rebuilt LOO, ~6 at an instrument, ~22 on the clean-air holdout
window — which measure do you want?" — then show the file, not the
headline.

## 7. "Skip consents unseen — a page-0 skipper donates without ever seeing the choice."

**THE ATTACK:** "Skip sits on every onboarding page and counts as
sharing-ON, but the disclosure only rendered on the consent page — so
skipping on page 0 or 1 consented invisibly. That's a dark pattern."

**THE HONEST ANSWER:** "It was, and it's fixed — caught by our own audit
lane, not by a judge. The disclosure now travels with the button: the
'skipping counts as sharing on' line renders on every page where Skip is
visible, so nobody consents without seeing it. Sharing-ON-by-default is
still our documented choice — the fix is that it's now an informed one,
and Settings undoes it in one tap."

**THE PROOF:** commit `1afccd8` "fix(onboarding): skip→sharing-on
disclosure travels with the button" — `Mobile/src/screens/
OnboardingScreen.tsx`: the `consent_footnote` moved outside the
`step===2` conditional to render on every page (diff: +9/−5 lines);
flagged in `docs/lanes/judge-attack-audit.md` privacy table and fixed
the same day it was filed.

**THE WEAKNESS LEFT:** Opt-in-by-default remains a defensible-but-argued
choice — a privacy judge can still prefer opt-in, and the answer is the
documented-default line plus the one-tap undo, not a claim that it's the
gold standard.

## 8. "Field poisoning is feasible — unauthenticated POSTs write your field."

**THE ATTACK:** "POST /v2/trip needs no auth and has no geographic bound.
A script can mint corridor cells anywhere on Earth and feed implied-PM2.5
into your krige posterior."

**THE HONEST ANSWER:** "Mostly true, and it was our own audit that found
it — the donation endpoint is unauthenticated by design (no accounts),
and tonight the sanity bounds cap magnitudes and speeds but not
geography. What limits the blast radius today: a cell only ever
publishes with ≥3 distinct devices and a median of ≥3 fresh traversals
inside 72 hours, corridor cells weigh like model points not stations,
and everything sits behind the dedupe guard — but the geo-bound itself
isn't in, and that fix is in flight."

**THE PROOF:** `server/v2/trip.py:82-104` — `_BOUNDS` caps
`distance_km≤300`, `dose_ug≤50k`, `MAX_SPEED_KMH=140`,
`MIN_TRIP_KM=0.1` (magnitude + plausibility, no bbox); `:230-306` —
cells minted for any finite lat/lon, `origin_area`/`dest_area` simply
return `None` outside NCR while `record_trip` still runs (the audit's
exact finding, `docs/lanes/server-audit.md` med-BUG row). Mitigations
live: `server/community.py:702-731` (median needs ≥3 fresh traversals +
≥3 distinct devices in 72 h), cells "weigh like model points (1×), never
like stations (3×)" (`corridor_field_samples` docstring), dedupe at
`trip.py:52-60`. No trip-bounds commit exists on `base/v2` at HEAD —
`fd1b54a6` did not land (checked tonight).

**THE WEAKNESS LEFT:** The implied-C inversion
(`dose/(VE·dur·microenv)`) has no plausibility clamp and the corridor
estimate merges into the krige posterior unclamped
(`airfield.py:1012-1016`) — a scripted donor with ≥3 sock-puppet tokens
could write the field tonight and nothing would log it loudly. Say it
plainly, then: "the geo-bound and a sanity clamp are the fix we owe; the
k-gate and median are what's holding the line today."

## 9. "Your 33× rests on a 23.7 km OD nobody walks."

**THE ATTACK:** "You demo Connaught Place→Gurugram on foot — a 23.7 km
walk nobody takes. The 33× is a strawman."

**THE HONEST ANSWER:** "It's the demonstrative worst pair, not a promise
— we picked the long OD so the decomposition is visible: ~2.4×
concentration × ~10× time × ~1.4× ventilation. Across 40 real OD pairs
the engine audit found genuine dose savings on about a quarter of them
with zero absurd detours, and the same-mode multiple across the week ran
31–45× — the number moves with the field, which is why we quote a band
and a range, not a constant. And the product answer isn't 'drive
instead' — it's 'leave at a cleaner hour', where /depart shows real
double-digit savings on routes people actually take."

**THE PROOF:** `docs/plan/NUMBERS.md` (spread walk÷car "31–45× across
ODs all week"; tonight 33.3× CP→GG, 35.9× IG→HCC — drift, not a
constant); `docs/plan/handoff.md:78` (40-OD re-run: 10/38 ODs win vs
fast row, 16/38 vs same-mode, 0 absurd detours, all worse-dose rows
duration-model artifact — 0 genuinely-smokier corridors); live
`POST /v2/plan` decomposition closes to the decimal (judge-qa-v2 §2);
`GET /depart` → now 22.8 → best ~21 µg (the time-shifting answer,
verified tonight).

**THE WEAKNESS LEFT:** "Up to 33×" invites the heckle by construction —
the headline number IS the extreme pair; if a judge wants the typical
pair, the honest figure is still "about thirty-something× on the demo
OD, less on short hops", which is fine as long as we don't pretend a
commute OD was chosen at random.

## 10. "Your engine dose can exceed the OSRM dose on the same OD — the 'least-smoke' row is dirtier."

**THE ATTACK:** "On some ODs your least-inhalation engine row is slower
AND dirtier than the OSRM row — because engine durations are freeflow
graph speeds with no congestion feed."

**THE HONEST ANSWER:** "Correct and disclosed — engine rows carry
`duration_basis:'freeflow'` and `duration_model:'estimated'` right on
the wire: the engine prices edges for smoke, not traffic, and without a
congestion feed a dirtier-slower row is a duration-model artifact, not a
smokier corridor. Our 40-OD re-run checked every one: all worse-dose
rows were the duration gap, zero were genuinely-smokier corridors."

**THE PROOF:** `server/v2/plan.py:1886-1891` (`duration_model:"estimated"`,
`duration_basis:"freeflow"` — emitted on engine rows, not hidden);
`Bridge/contract.ts:447-449` (the caveat is in the contract);
`docs/plan/handoff.md:78` (40-OD re-run: 103 worse-dose rows, all
duration-model artifact per decomposition — engine ~27 km/h implied vs
OSRM freeflow ~55 — 0 genuinely-smokier corridors);
`docs/lanes/server-audit.md` med row (the judge-risk framing and the
rehearsed-answer instruction).

**THE WEAKNESS LEFT:** The artifact is real until a congestion feed
lands — a judge scanning the table can still *see* a dirtier-slower
row before we explain it, so the `duration_basis` flag has to be said
first, not discovered.

---

## Attacks that fail — quick reference

Accusations a hostile judge can try that the evidence defeats. One line
each, for stage lookup.

| accusation | why it fails — proof pointer |
|---|---|
| "It's dressed-up nearest-neighbor" | `GET /aqi` → `kriging:"on"`, `sigma_coverage:"per-query"`, `nearest_sample_km` echoed live; `airfield.py` krige posterior + `_clamp_krige`; IDW is a *documented* fallback, not the serve path — `_snap_nearest` only runs at the coverage edge and reports its own distance |
| "The ±band is decorative" | `SIGMA_CAL=3.2` calibrated against measured 29%-of-nominal raw coverage (`airfield.py:996-1004`); `sigma()` returns `None` outside coverage (`:1018-1044`) — no fake precision; 95.2%@±2σ is the *measured* figure in `server/data/field_validation.md`, not a hand-pick |
| "33× is fabricated" | re-derived live repeatedly — decomposition closes to the decimal (2.36× conc × 10× time × 1.4× VE); 31–45× across ODs all week in `NUMBERS.md`; a cooked number doesn't drift with the field, this one does |
| "1.07M edges is a slide number" | `GET /health` → `.routing.edges` 1,070,459 / `.edges_priced` 903,058, live and unhardcoded, matching `route_graph.meta.json` (`bans:230`, `pbf_sha256`) |
| "The C++ engine is vaporware / OSRM with a price tag" | `GET /health` → `engine:"alive_core"`; `server/core/bindings.cpp`; `server/tests/test_parity_dose.py` — 8 tests, C++ reproduces the Python reference bit-for-bit; what OSRM can't do is re-price a million edges for dose every 15 min in-memory (the `alive_core-path` alternates) |
| "The archive is fake/staged" | `GET /v2/archive` → `storage.bucket:"alive108-air"`, tonight `recorded:[1,3,4,5,6]`, `gaps:[0,2]`, pending rest — `server/archive.py:24-52` records only the served field and never back-fills; honest gaps are the unfakeable part |
| "Hindi is a veneer" | `Mobile/src/i18n/strings.ts` — 556 keys with a `hi` mirror the compiler enforces (`hi: Record<StringKey,string>`); `modeLabel()` localizes even engine suffixes like "least-smoke alt N" (`:1263+`); `docs/lanes/hi-parity-v2-*.md` lane reports |
| "You hid the cold start" | `docs/plan/cold-path.md` — measured: cold plan 6,650 ms → warm ~120 ms, fresh task ~60–100 s to a priced engine; `docs/demo-day.md` T-60 Spot→on-demand + T-40 `tools/warm_task.py` — engineered out of the demo window, in writing, before any judge asked |

---

## Re-verify morning-of (numbers that moved tonight alone)

- `/community`: obs_total **22**, obs_24h **0**, contributors **14** —
  say "two dozen dev donations", never "users".
- `/v2/skill`: pairs grow hourly (227 tonight); h+11 band_hit read **21.7%**
  at the audit, **23.8%** tonight — say "low twenties by h+11".
- `stations.count`: **53** tonight (54 earlier; drifts with DPCC page
  availability; 24 if the site stalls past 90 min).
- `/aqi.calibration`: prod still serves the **stale 46.1/n=94 "OpenAQ"**
  artifact; HEAD has the rebuilt LOO (**8.8/n=70**, commit `6ad7de6`).
  Check `/health.build_sha` vs HEAD before quoting either number to a
  judge — a redeploy flips which answer is true.
- Fires modifier, corridors active, plan multiples, `/depart` — all
  drift; `verify_numbers.sh` at T-45 is the canonical re-derive.
- Deploy lag check: prod `bc8f82c4` tonight vs audit's `ce01ec5c` —
  diff `/health.build_sha` against HEAD before quoting any HTML-surface
  claim to a judge.
