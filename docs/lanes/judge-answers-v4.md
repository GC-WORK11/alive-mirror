# judge-answers-v4 — the demo-morning card, refreshed for tonight's landings

The third armed-answer card. `judge-proof.md` covers the first ten hardest
questions; `judge-answers-v3.md` (b372a41) covered the audit-surfaced attacks.
This v4 is the same card **re-armed after tonight's landings** — the pentest
(`aea1c68`), the low-RAM audit (`e0aca00`), the SIGSEGV root-fix (`3c24a5e`),
`/v2/usage` (`16d3764`), landing v5 (`eaf7e8b`), the demo rehearsal + script
fix (`fca86b3`/`69cde82`), and the hostile prod drive
(`demo-exchange-max.md`, `fb4a993`). Several v3 answers are now *better* —
three of last night's open weaknesses closed.

Format per attack: **THE ATTACK** (as a judge would say it) · **THE HONEST
ANSWER** (≤3 sentences you can say out loud) · **THE PROOF** (endpoint +
field / file:line / lane report) · **THE WEAKNESS LEFT** (stated plainly —
no spin). Where the honest answer is "we're weak here", the card says what
to say plainly.

Every figure re-verified against live prod
(`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, build
**`70914c00`** — rolled mid-write from `e0aca004`; the live probe below
was taken on `e0aca004` ~06:50 UTC and re-checked on `70914c00` ~06:57,
which now also serves the `stations_climatology` rename) on
**2026-10-07 ~06:50–06:57 UTC (~12:20–12:27 IST)**. Numbers drift with
the field — say "about ~N" and re-run `scripts/verify_numbers.sh` at T-45.

---

## The ten v3 attacks, re-answered

## 1. "Your citizen layer is empty."

**THE ATTACK:** "'Measured by its own commuters' — /community shows 41
observations all-time, 2 today, 23 contributors. A rival with seeded data
looks more alive than you."

**THE HONEST ANSWER:** "It's 41 real donations from dev devices — the
network is early and we say so; what proves it isn't the count, it's the
gate: 43 of 55 tracked corridors are suppressed right now because fewer
than three distinct devices crossed them in 72 hours, and that counter is
public. The field itself doesn't depend on the citizen layer — 53
government-grade instruments carry it; donations only sharpen corridors
where the crowd actually walks. A seeded map wouldn't have a suppression
mechanism at all — and ours just verified live: every published row on
/community shows ≥3 devices."

**THE PROOF:** `GET /community` live → `obs_total:41`, `obs_today:2`,
`contributors:23`, `top_corridors[].devices` = 6,5,… (all ≥3);
`GET /v2/city/moves` → `n_trips:41`, `min_k:3`, corridors `active:12` of
`tracked:55` (72 h window). `server/community.py:702-731`
(`corridor_field_samples`: median needs ≥3 fresh traversals AND ≥3
distinct hashed devices or the cell emits nothing); `server/community.py:89-90`
(`_K_MIN_DEVICES=3`, `_CELL_WINDOW_S=72h`). New since v3: `GET /v2/usage`
exists (`16d3764` — devices seen 24h/7d, trips/hour, dose median, feedback
rollups) but is **admin-gated** — it proves adoption honestly to an
operator, invisible to a guest judge.

**THE WEAKNESS LEFT:** "Infrastructure for a crowd we don't have" is still
literally true — and now a judge *can't see* the best defense: `/v2/usage`
returns 401 to guests by design (`demo-exchange-max.md` attack #1 calls
this out). The line is: "the usage surface is operator-gated because it's
aggregate telemetry — the public proof is the suppression counter itself."
Don't oversell the layer.

## 2. "'Nothing leaves your phone' — over plaintext HTTP."

**THE ATTACK:** "Your privacy-first dosimeter ships consented movement
data unencrypted. NLB is TCP:80 only; `POST /v2/trip` travels cleartext
through Delhi cell networks."

**THE HONEST ANSWER:** "True — the transport is plaintext today, and we
don't pretend otherwise: the README and the pentest both say 'no TLS
terminator today'. What travels is already an aggregate — no credentials,
no identity, endpoints trimmed 300 m — and the pentest fixed the parts
that made plaintext worse than it had to be: the admin token compare is
now constant-time, and the rate limiter can no longer be rotated around
with spoofed headers. TLS itself is a domain plus an ACM cert and a 443
listener — an owner/architecture call we've flagged, not hidden."

**THE PROOF:** `scripts/deploy.sh:256` (single `create-listener
--protocol TCP` on :80, no certificate); `pentest-report.md` findings
table — plain HTTP edge flagged **MED, owner decision** (iOS needs
`NSAllowsArbitraryLoads`, Android the cleartext plugin *only because of
this*); `hmac.compare_digest` admin-token compare landed `aea1c68`.
At-rest guarantees that DO hold: `server/v2/trip.py` TRIM 300 m /
THIN 100 m / ROUND ~11 m, sha256[:16] of the device token (raw discarded);
`server/community.py:_fold` — no per-trip row ever created.

**THE WEAKNESS LEFT:** Same as v3 — the cheapest fix in the audit still
isn't done. If a judge asks "when", the honest answer is "a domain and a
cert — it's the one real gap we'd close first." Do not say "it's in the
pipeline"; it is a flagged owner decision, in writing, in the pentest
report.

## 3. "Your AWS is decorative — EventBridge stubs, an in-app daemon, and a docker-compose."

**THE HONEST ANSWER:** unchanged from v3 — half right, and we say which
half: the scheduler layer is honestly-disabled scaffolding; the
load-bearing AWS is the deploy itself (CodeBuild→ECR→Fargate behind an
NLB on an Elastic IP, DynamoDB aggregates, S3 field archive + community
snapshot, Secrets Manager). Tonight adds one more visible-from-outside
proof: `/health.build_sha` tracks the running ECR image — `e0aca004`
right now, matching git commit `e0aca004` byte-for-byte.

**THE PROOF:** same pointers as v3 (`infra/schedules/*.json` DISABLED,
`server/main.py` in-app `run_forever` tick, `scripts/deploy.sh:80-118`
CodeBuild→ECR, `:244` NLB/EIP, `:204-208` `AGG_TABLE`/`COMMUNITY_BUCKET`/
`ALIVE_AIR_BUCKET`, `:210-215` Secrets Manager); `GET /v2/archive` →
`storage.bucket:"alive108-air"` with today's honest gap pattern
(recorded `[1,3–12]`, gaps `{0,2}` — the recorder never back-fills).
Plus `pentest-report.md`: S3 `alive108-air` verified private +
public-access-block + AES256; the build bucket's block is now pinned
idempotently in `deploy.sh` on next deploy.

**THE WEAKNESS LEFT:** Same as v3, plus a sharper edge tonight:
`/v2/usage` exists but a guest can't read it (401) — same unverifiability
class as `trips_backend`. If pressed: "the aggregate backend is
provisioned DynamoDB with an honest memory fallback; the archive and the
deploy pipeline are what you can check from outside."

## 4. "Kriging doesn't beat IDW on your own artifact."

**THE HONEST ANSWER:** unchanged — what kriging buys isn't a better mean,
it's the σ: the ±band on every /aqi read, the dose band on every route,
the thing that widens honestly where stations are thin, and the posterior
our corridor traversals merge into. And tonight the claim sits inside the
new landing v5 — where a hostile audit verified every clause against the
live wire (`demo-exchange-max.md`: landing **REAL**, "95.2% of 3,550
held-out station-hours inside ±2σ" matches `field_validation.md` —
which publishes the MAE tie next to it, not a cherry-pick).

**THE PROOF:** `server/data/field_validation.md` (MAE 22.0 kriged vs
21.8 IDW AND ±2σ coverage 95.2% vs 95.4% nominal in one table);
`server/airfield.py:77` (`SIGMA_CAL=3.2`), `:996-1016` (`_krige_posterior`),
`:1018-1044` (`sigma()` returns `None` outside coverage — no fake
precision); `server/exposure.py:341` (σ → `dose lo/hi` — visible live
today: every `/v2/plan` option carries `dose {lo,mid,hi}`).

**THE WEAKNESS LEFT:** unchanged — no window exists where kriging beats
IDW on MAE. The honest frame stays "the mean is a tie; the band is the
reason."

## 5. "Your self-grade decays — and it grades the model against itself."

**THE ATTACK:** "/v2/skill decays with horizon, and the 'truth' side is
your own recorded field. The model grades itself."

**THE HONEST ANSWER:** "It does decay — every forecast does — and we
publish the whole ladder instead of hiding the tail; tonight it reads
90% band-hit at h+0 down to ~33% at h+11 on 271 graded pairs. The hit
metric is strict CPCB-category equality, not 'were you close'. On
non-station cells the 'recorded' side does share our model+krige blend —
which is exactly why we call it a self-grade and publish the method,
not accuracy."

**THE PROOF:** `GET /v2/skill` live — `pairs:271`, overall mae 26.4 /
bias +20.4 / band_hit 49.6%; ladder: h+0 mae 3.6 / band 90.0% →
h+11 mae 41.6 / band 33.0% (last night read ~22% — **the tail number
drifts by the hour; say "low-thirties by h+11" today and re-read at
T-45**); `coverage.snapshots:39` since Oct-5 20:00 IST. The
instrument-truth comparison judges want: the rebuilt LOO — now ON the
wire (see #6).

**THE WEAKNESS LEFT:** unchanged — the self-grade's ground truth is our
own pipeline output; the honest line is the published ladder plus the
instrument-anchored LOO, not a synthetic comparison.

## 6. "46.1 MAE on the wire vs your 95.2% headline — which is it?" → CLOSED

**THE HONEST ANSWER:** "It was stale and we caught it ourselves — the
published LOO was an OpenAQ-era artifact that had quietly broken, so we
rebuilt it as a real krige refit over the live WAQI+DPCC instruments.
**The wire now serves the rebuilt number**: `mae_ug 8.8, rmse 12.7,
n_stations 70, bias +0.2` — and a hostile drive tonight verified it on
prod, not just at HEAD."

**THE PROOF:** `GET /aqi` → `calibration` **now serves the rebuilt
artifact on build `e0aca004`** (`method:"leave-one-out over live
WAQI+DPCC instrument readings (krige refit per held-out station)"`,
mae 8.8 / rmse 12.7 / n 70 / median_abs_pct 8.8 / bias +0.2 — verified
live this hour; `demo-exchange-max.md` numbers-match table confirms the
same on `dc6d0cc2`); commit `6ad7de6`; `demo-exchange-max.md`
"LOO 8.8 on prod (stale 46.1 closed)".

**THE WEAKNESS LEFT:** The attack's *shape* survives even though its
number died — a judge can still ask "which error, full stop?" Answer:
"about 9 µg between stations by the rebuilt LOO, ~6 at an instrument,
~22 on the clean-air archive window — which measure do you want?", then
show the file. And the lesson generalized: **before quoting any
number-class to a judge, `curl /health` and diff `build_sha` against
HEAD** — deploy lag is how this attack was born.

## 7. "Skip consents unseen — a page-0 skipper donates without ever seeing the choice."

**THE HONEST ANSWER:** unchanged — it was a dark pattern, our own audit
caught it, and the disclosure now travels with the button on every page
(`1afccd8`). Sharing-ON-by-default remains our documented choice — now
an informed one, undoable in one tap.

**THE WEAKNESS LEFT:** unchanged — a privacy judge can still prefer
opt-in; the answer is the documented default + one-tap undo.

## 8. "Field poisoning is feasible — unauthenticated POSTs write your field." → MOSTLY CLOSED

**THE ATTACK:** "POST /v2/trip needs no auth. A script can mint corridor
cells anywhere on Earth and feed implied-PM2.5 into your krige posterior."

**THE HONEST ANSWER:** "It was true when our audit found it — tonight
both halves of the fix are in. Every kept trip point must land inside the
dose field's service area or the donation is refused with 422
`outside service area`; and the implied-concentration inversion —
dose ÷ ventilation ÷ duration ÷ micro-environment — is capped at 900 µg/m³
with a 422 `implausible dose_ug for duration_s`, mirroring the
measurement ceiling our own fold uses. On top of that, the rate limiter
now keys on the TCP socket peer, so the donation faucet can't be widened
with spoofed headers — verified live an hour ago."

**THE PROOF:** commits `9f4533b` (geo bound: `in_service_area` → 422)
+ `e483a96` (implied-C ≤ 900 → 422), landed ~30 min after v3 was
stamped — v3's "not landed yet" was true when written;
`server/tests/test_v2_hardening.py`; `docs/lanes/fix-trip-bounds-report.md`.
Rate limiter: `server/middleware.py` — `_client_key` sha256s `ip:<socket
peer>`; XFF honored only inside `ALIVE_TRUSTED_PROXIES` CIDRs (empty by
default, correct for the L4 NLB). **Live-verified on prod this
hour (both builds):** a 150-request parallel burst with a unique
`X-Forwarded-For` + `X-Device-Token` per request got **75×200/75×429 on
`e0aca004` and 91/59 on `70914c00` — statistically identical to the
unmarked control**; the pentest's original reproduction on the pre-fix
image got 200×200. k≥3 gate + median-of-≥3
fresh traversals still stand behind it (`community.py:702-731`), and
corridor cells still "weigh like model points (1×), never stations (3×)".

**THE WEAKNESS LEFT:** One honest residual — the k-gate counts *hashed*
devices, and tokens are self-minted: an attacker who fabricates ≥3 tokens
can still inject a fake corridor cell at the 1 rps/IP pace (`pentest`
flags this MED — it needs attestation/anti-abuse design; a botnet beats
any IP limiter). The line: "the bounds and the socket-peer limiter hold
the line today; attestation is the next real layer, not a tonight fix."

## 9. "Your ~35× rests on a long OD nobody walks."

**THE ATTACK:** "You demo a 24.7 km walk nobody takes. The spread is a
strawman."

**THE HONEST ANSWER:** "It's the demonstrative pair, not a promise — the
long OD exists so the decomposition is visible: concentration × time ×
ventilation. Across 40 real OD pairs the engine audit found genuine dose
savings on about a quarter of them with zero absurd detours; the spread
moves with the field — it read 34.5× on the demo OD an hour ago — which
is why we quote a band, not a constant. And the product answer isn't
'drive instead' — it's 'leave at a cleaner hour', where /depart shows
savings on routes people actually take."

**THE PROOF:** live `POST /v2/plan` this hour on the judge-typed OD
(India Gate → "huda city centre" resolves to the metro station, 24.7 km):
**23 options**, car-AC **9.0** (band 3.9–14.1) vs on-foot **310.5** →
**34.5×**; metro+walk **61.6 present** (car-AC beats it ~6.9× — the
"honest surprise" row, GTFS-service-hours dependent); `took_ms ~5,950`
on a fresh OD — the "under two seconds" line is only true on the warmed
OD (`warm_task.py` at T-40 is load-bearing). `docs/plan/NUMBERS.md`
31–45× band; `docs/plan/demo-script.md` numbers sheet re-pinned by the
fix lane.

**THE WEAKNESS LEFT:** Same as v3 — the headline IS the extreme pair; and
the metro row is OD- and service-hours-dependent (absent on a 31.3 km
endpoint I tried tonight — **re-verify it exists at T-45** or the
"car beats metro" clause dies silently).

## 10. "Your engine dose can exceed the OSRM dose on the same OD — the 'least-smoke' row is dirtier."

**THE HONEST ANSWER:** unchanged — correct and disclosed: engine rows
carry `duration_basis:"freeflow"` + `duration_model:"estimated"` on the
wire; without a congestion feed a dirtier-slower row is a duration-model
artifact, not a smokier corridor; the 40-OD re-run found zero
genuinely-smokier corridors.

**THE PROOF:** live tonight — every least-smoke row in my own
`POST /v2/plan` above still carries the flag; `demo-exchange-max.md`
verified `duration_basis:"freeflow"` + `ranking` block on prod;
`Bridge/contract.ts:447-449`; `docs/plan/handoff.md:78` (103 worse-dose
rows, all duration-model artifact).

**THE WEAKNESS LEFT:** unchanged — real until a congestion feed lands;
the `duration_basis` flag has to be said first, not discovered.

---

## The NEW attacks — armed tonight

## 11. "Is it secure? Or is it a demo that never got attacked?"

**THE ATTACK:** "Hackathon projects never see a real attack. Your auth is
a Bearer token in an env var and your limiter is a toy."

**THE HONEST ANSWER:** "We attacked ourselves before a judge could — a
dedicated pentest lane last night found two real HIGHs and fixed both in
the same commit: the rate limiter was fully bypassable (spoofed
X-Forwarded-For minted a fresh bucket per request — the L4 NLB can't
append XFF, so every hop was client-supplied), and a stored XSS in the
admin review tile could have stolen the operator token. Both are closed
and the limiter fix is **live-verified on prod an hour ago** — a
150-request spoofed burst now dies at 429 exactly like an unmarked one."

**THE PROOF:** `docs/lanes/pentest-report.md` — findings table, both
HIGHs + the full clean list (secrets in bundle: none; on-device stores:
by-design under purge contract; CORS*: header-only auth so no CSRF
surface; error paths: shaped 422s, no tracebacks). Live re-verification
this session: 150-req parallel burst w/ rotating
XFF+device-token → 75×200/75×429 on `e0aca004` and 91×200/59×429 after
the mid-write roll to `70914c00` — spoof-immunity held across the
deploy; unmarked control was statistically identical (74/76). The
pre-fix image returned 200×200 to the same probe. Also landed: constant-time
`hmac.compare_digest` admin token; release-build `console.debug` gated on
`__DEV__`; build-bucket `put-public-access-block` in `deploy.sh`; a nav
dose-inflation bug (`counters.ts` derived-speed fallback) fixed as a
found-cleanup.

**THE WEAKNESS LEFT:** Three flagged-not-fixed items, all disclosed:
TLS (owner decision — see #2), donation attestation (see #8's residual),
and botnet-class floods being beyond any in-process limiter (that's an
edge/Shield question, not app code). The story to tell is exactly the
honest one: *found by us, fixed by us, verified by us — the residual list
is in the same report.*

## 12. "Does it scale? One Fargate task, one vCPU — ten judges open it at once."

**THE ATTACK:** "You're on a single 1vCPU/3GB Spot task. The demo itself
is a load test. What's the first thing that falls over?"

**THE HONEST ANSWER:** "We measured it instead of guessing: the working
set is ~0.95 GB live-measured against the ~2 GB the API process actually
gets after the OSRM sidecar — about a gigabyte of headroom — and the
per-request RSS delta is *zero* across a mixed 24-request loop; memory
is not the limiter. The binding constraint is CPU: a /v2/plan reprice
takes ~2.5–6.5 s of single-thread work, so the honest capacity is
**~8–15 concurrent active users** — enough for a demo room, not for a
viral spike — and the 10 rps/IP limiter plus a 256-entry solve-dedupe
mean the fifteenth concurrent judge queues politely instead of tipping
the task over."

**THE PROOF:** `docs/lanes/lowram-report.md` — staged boot RSS table
(interpreter 17 MB → full warm ~0.88–1.7 GB depending on load order),
per-request probe (warm idle 726 MB, first `/v2/reach` +211 one-time,
then +0 across the loop), the cache inventory (every hot-path store
bounded — 20 entries itemized), the task budget verified in
`scripts/deploy.sh` (`--cpu 1024 --memory 3072`, sidecar takes 1 GB).
Fixes landed: `TripAggregates` stale-cell prune (`c08a046` — the only
true unbounded-growth → OOM vector found, dev-backend only anyway),
gazetteer ~107 MB always-resident saving via lazy index (`822949b`).
Suite: 1204 passed.

**THE WEAKNESS LEFT:** The honest posture is a demo room, not the
internet — a Hacker-News spike would queue and eventually hit honest
timeouts, and cold start on a fresh task is ~60–100 s to a priced engine
(engineered out of the demo window by the T-60 Spot→on-demand flip +
T-40 warm_task.py — see the deploy-freeze rule below). Also structural:
place data held ~3× (~267 MB dicts + ~110 MB rows + ~48 MB C++ index) —
flagged, not re-architected this week.

## 13. "It crashes. The simulator build SIGSEGV'd all week."

**THE ATTACK:** "Your own lane reports documented a ~40% cold-launch
crash. Judges don't get a second tap."

**THE HONEST ANSWER:** "Root-caused and fixed — and it was never the
race we thought it was. `lldb` on a live crash showed every thread parked
except the victim dying inside Hermes' old-gen freelist: jsi destructors
(`~SyncCallback`, the `~Promise` every async turbomodule call creates,
`~SharedState`) were running on native module queues and corrupting
Hermes' pinned-root bookkeeping — the next GC walk died minutes-seconds
later. The fix hops all of that destruction onto the JS thread and sizes
the heap out of the window — and every line of it is
`#if TARGET_OS_SIMULATOR`, so the hardware the demo runs on was never the
crash surface and is untouched."

**THE PROOF:** `docs/lanes/sigsegv-coldfix-report.md` — full mechanism +
`bt all` evidence (`sigsegv-coldfix-bt40805.txt`), fix at `3c24a5e`
(`Mobile/patches/react-native+0.86.3.patch`, 7 files, patch-package +
`ios.buildReactNativeFromSource`), gate **34/34 real cold launches, 0
crashes** (20 search + 10 compare + 4 post-wipe — real-touch taps, not
a11y presses); crash-rate progression 40% → 19% → 5% → 0 as each layer
landed. Same bug family as upstream hermes#1957 / expo#45374 /
bluesky-social#10672; Expo already shipped its half (#47454) — ours was
the RN-core residue. Android: the rehearsal drive ran a deliberate
in-window probe (cold launch → sheet at +38 s) with a **zero-line**
FATAL/ANR/SIGSEGV oracle for the whole session.

**THE WEAKNESS LEFT:** An independent sibling verify (`34053b8`,
ios-cold-drive addendum-3) found **22/24 mounts survive — 2 cold-boot
SIGSEGV kills on the same rig**; their verdict: "substantially confirmed,
not proven zero on this rig." The honest line: "root-caused,
sim-verified 34/34 on the gate build, independently reproduced at
22/24 — and it only ever existed on the simulator; the Android demo
build has a clean oracle across every run." Also disclosed in the
report: a third-party native block holding `jsi::Value` raw could in
theory re-hit the class — the `ProtectMetadata` tripwire ships armed to
convert any recurrence into an early diagnosable abort.

## 14. "Is the data real — or painted to look real?"

**THE ATTACK:** "Your routes paint PM2.5 along the path. Anyone can
gradient a polyline. Prove the paint comes from the field."

**THE HONEST ANSWER:** "A hostile audit asked exactly that last night —
they pulled the walk option's painted segments, queried /aqi at every
segment midpoint, and all **12 of 12 spans landed within ±5%** of the
live field at that point (ratios 0.96–1.10, consistent with the ×1.06
smoke modifier). The same audit diffed `Bridge/contract.ts` against the
served wire — exact match — and walked every public surface checking
each rendered number against its wire. Verdict on all four pages:
REAL."

**THE PROOF:** `docs/lanes/demo-exchange-max.md` —
`demo-exchange-max-shots/seg_midpoints.txt` (the 12-span table),
`numbers-match` table (25 rows verified to the decimal, incl. live drift
observed mid-audit: obs_total 40→41, contributors 22→23 — real donations
landing during the probe), mobile-contract parity
(`contract.ts:434-457` == served segment shape), `/v2/usage` guest→401
correct, unfurl per-UA verified. `segments[]` on every plan option
(commit `c152760`, reroute parity `58632f3`); route renderer consumes
segments-first with MAP_QUIET for nulls (`routeTint.ts`).

**THE WEAKNESS LEFT:** Honest by construction but verifiable only because
the audit built the check — there's no standing public "prove the paint"
endpoint beyond `/aqi` itself (a judge can re-run the same midpoint
check in five minutes; that's the answer if asked). The two-medians
nit (see watch items) is the residual that *looks* like a mismatch to a
screenshot-compare judge.

---

## Watch items — armed, not attacked

### A. Thin citizen layer ("who actually uses it?")

The numbers are the honest answer: **41 trips all-time, 23 contributors,
2 today, 12.0 km** — say "forty-something real dev donations" never
"users" and never "growing". The defense-in-public is the k≥3 suppression
counter (12 of 55 publishable); the defense-in-private is `/v2/usage`
(admin-gated — offer to open it on stage Wi-Fi if a judge presses:
`devices.seen_24h`, `trips.per_hour`, `dose.median_ug_per_trip` are real
reads, but a guest 401 is *correct behavior*, so frame it as "gated by
design, here's why" not a malfunction).

### B. The depart ~1% day

Tonight's live read on the demo OD (car mode): now **31.5** → best
**30.7 @+5 h** → worst **57.3 @+23 h**; `pct_less_vs_now` = **3** — the
leave-later row is *absent* (gate >8; it read 13 at rehearsal — it
flickers). If a judge's screenshot catches the marquee surface showing
"leave ~11:00 — 1–3% less dose": **say the curve reads the field, not
the pitch — today the air is flat all day, and the honest saving is
small; on a swing day the same surface pays double digits.** Then pivot
to where the promise is visible anyway: the 24 h curve's own peak
(~1.7–1.9× tonight) or the verbal `hours=120` read (worst ~57 @+23 h /
spike ~38–58 µg out to +58 h). Never promise the row — check
`pct_less_vs_now` at T-45 and script whichever surface is alive.

### C. Rolling deploys mid-demo — the freeze-window rule

The audit watched `build_sha` flip `aea1c688→dc6d0cc2` and `/v2/usage` go
404→401 **inside 15 minutes** — a judge re-checking a number mid-pass
could screenshot the skew. **Now codified in `docs/demo-day.md`
(`70914c0`): DEPLOY FREEZE T-60 → demo end** — no pushes, no deploys, no
task swaps (a mid-demo roll = fresh task serving thin field + `/v2/*`
routes minted on the old task 404ing + `build_sha` flipping under a
judge's eyes; whatever HEAD is at T-60 is the demo build, fixes found
inside the window queue for after — no exceptions short of prod down).
If a judge does catch skew anyway: "that's a rolling deploy catching
up — refresh in thirty seconds" is true and visible.

### D. `/health` duplicate `stations` keys — verdict + flag

The payload carries `sources.stations.count:53` (live instruments — the
number the landing claims) **and** `history.stations:125` (climatology
archive stations, `server/history.py:142` `summary()` → `len(db["stations"])`).

**Verdict: not a JSON duplicate-key bug** — they're distinct paths and
both values are true for their population. **But it is a real naming
collision on the prove-it surface**: a judge curling /health to "prove
the 53" greps `"stations"` and sees `125`. **Fix-needed: yes — severity
P3, and it landed while this card was being written**: sibling lane
`70914c0` renamed it to `history.stations_climatology` in
`history.summary()` (one-line wire change; consumers were `main.py:376`
+ `admin_agg.py:56`; `verify_numbers.sh` already reads the new key).
**Already live on prod**: the deploy to `70914c00` mid-write put
`stations_climatology:125` on the wire (verified ~06:57 UTC) — the key
now disambiguates itself. Armed line if a judge still asks about the
two counts: "125 is the climatology archive that backs the 'vs typical'
baseline; 53 is tonight's live instruments — the field paints from the
53."

---

## The numbers card — live prod `e0aca004`, ~06:50 UTC / ~12:20 IST Oct-7

*Re-pin at T-45 — this card is internally consistent as of this stamp.*

| figure | live value now | source |
|---|---|---|
| stations live | **53** (waqi+dpcc, both feeds `ok`) | `/health.sources.stations.count`; `/aqi.field.station_readings` agrees (accepted band 51–54; 24 if DPCC stalls >90 min) |
| climatology stations | **125** | `/health.history.stations` — the dup-key watch item |
| field freshness | `field_age_s ~96–136`, `field_stale:false`, ~15-min cadence | `/health` |
| model samples | **101** | `/aqi.field.samples`, `/v2/plan.field.samples` |
| edges | **1,070,459** total / **903,058** priced | `/health.routing` |
| engine | `alive_core` | `/health.engine` |
| transit | metro `true` + bus `true` real feeds | `/health.transit.real_feeds` |
| city pm2.5 | mean **55.6** / median **54.8** / max **69.3** (25-pt lattice); aqi **93**, GRAP indicative **stage 0**; **−35.4%** vs typical Oct (median 86.1) | `/v2/city.pm25_stats`, `.typical`, `.grap` |
| CP point | pm2.5 **76.2** (ambient 71.9; lo 58.1 / hi 94.4), **us_aqi 159**, nearest sample **1.8 km** | `/aqi?lat=28.6315&lon=77.2167` |
| breath | **798 µg/day mid ≈ 2.53 cigarettes** | `/v2/city.breath` |
| why-line | stagnation primary — "air barely moving" (VC **1,417 m²/s** vs ~3,000) | `/v2/why.drivers[0]` |
| fires | **44** total / **12** in-belt / **26.2 MW** belt FRP (31 day / 13 night; NOAA-21×29, NPP×9, NOAA-20×6); modifier **×1.06** | `/fires` + `/aqi.fire` + `/aqi.smoke_modifier` |
| fires carrying? | **NO — REFUSED tonight** (wind **3.6 km/h @123°**, easterly; belt is NW) | `/aqi.wind`, `/v2/why` — T-45 re-check decides the aside |
| LOO calibration | **mae 8.8 / rmse 12.7 / n 70 / bias +0.2** — rebuilt, ON the wire | `/aqi.calibration` |
| skill | **271 pairs**; overall mae 26.4 / band 49.6%; h+0 mae 3.6·band 90% → h+11 mae 41.6·band **33.0%**; 39 snapshots since Oct-5 20:00 IST | `/v2/skill` |
| community | **41 obs / 2 today / 23 contributors** / 12.0 km / 4.2 µg today; avoided **117.8 today / 1,083.8 all-time**; latest donation **~2 h ago** | `/community` |
| corridors | **12 publishable / 55 tracked**, min_k 3 (72 h) | `/v2/city/moves` |
| archive | recorded **[1,3–12]**, gaps **{0,2}**, rest pending | `/v2/archive` |
| usage endpoint | `GET /v2/usage` → **401 `{"detail":"admin token required"}`** for guests — live + correctly gated | live probe |
| rate limiter | defaults 10 rps/burst 30; plan+reroute 2/6; trip+observe+report 1/5; `/health` exempt — **XFF/token spoof immunity live-verified on both builds** (150-burst: 75×200/75×429 @e0aca004, 91/59 @70914c00 ≈ unmarked 74/76) | `middleware.py` + live probe |
| plan demo OD (IG→"huda city centre", 24.7 km) | **23 options**: car-AC **9.0** (3.9–14.1) / walk **310.5** → **34.5×**; metro+walk **61.6 present** (car beats ~6.9×); `took_ms ~5,950` fresh | sanctioned `POST /v2/plan` |
| plan alternate OD (IG→Huda proper, 31.3 km) | 20 options, no metro row — OD/service-hours dependent | same |
| depart demo OD (car) | now **31.5** → best **30.7 @+5 h** → worst **57.3 @+23 h**; `pct_less_vs_now` **3** → leave-later row **absent** (gate >8) | `/depart` |
| latencies | GETs ~0.3–0.5 s; plan fresh-OD `took_ms` ~5.9–6.5 s server (reprice), warm ~50–660 ms; first `/v2/reach` one-time ~+200 ms raster | curl + wire |
| spend | **~$46/mo** (Fargate Spot + small data) — last credentialed verify Oct-6; T-45 CLI understudy re-checks | docs/demo-script beat 6 |
| task shape | 1 task × 1 vCPU / 3 GB (API ≈2 GB after OSRM sidecar); RSS ~0.95 GB → ~1 GB headroom; **~8–15 concurrent users** honest posture | `deploy.sh` + `lowram-report.md` |
| builds | prod **`70914c00`** (rolled ~06:55 from `e0aca004` — carries every code fix incl. the rename; HEAD is now only docs ahead) | `/health.build_sha` + `git merge-base` |

---

## Attacks that fail — quick reference

| accusation | why it fails — proof pointer |
|---|---|
| "It's dressed-up nearest-neighbor" | `GET /aqi` → kriging on, `nearest_sample_km:1.8` echoed; `airfield.py` krige posterior + `_clamp_krige`; IDW is a *documented* fallback — `_snap_nearest` only at the coverage edge, reports its own distance |
| "The ±band is decorative" | `SIGMA_CAL=3.2` vs measured 29%-of-nominal raw coverage (`airfield.py:996-1004`); `sigma()`→`None` outside coverage — no fake precision; live dose bands on every plan option tonight (`lo 3.9/mid 9.0/hi 14.1` on car-AC) |
| "The spread is fabricated" | re-derived live repeatedly — tonight 34.5× (9.0 vs 310.5 on the typed demo OD); a cooked number doesn't drift with the field, this one does; decomposition closes to the decimal |
| "1.07M edges is a slide number" | `/health.routing.edges` 1,070,459 / `edges_priced` 903,058 live, matching `route_graph.meta.json` |
| "The C++ engine is vaporware" | `/health.engine` = `alive_core`; `server/core/bindings.cpp`; `test_parity_dose.py` 8 tests bit-for-bit vs Python ref |
| "The archive is fake/staged" | `/v2/archive` recorded `[1,3–12]` gaps `{0,2}` — `archive.py` records only the served field, never back-fills; honest gaps are the unfakeable part |
| "Hindi is a veneer" | `Mobile/src/i18n/strings.ts` — `hi` mirror compiler-enforced; `modeLabel()` localizes even engine suffixes; hi-parity lane reports |
| "You hid the cold start" | `docs/plan/cold-path.md` — cold plan 6,650 ms → warm ~120 ms, fresh task ~60–100 s; T-60/T-40 runbook in writing before any judge asked |
| **NEW** "Security is a claim, not a test" | `pentest-report.md`: 2 HIGHs found+fixed same commit; spoofed-XFF burst live-verified dead on prod (75×429 ≈ unmarked); TLS + attestation openly residual |
| **NEW** "It falls over under a demo load" | `lowram-report.md`: ~0.95 GB working set vs ~2 GB budget, per-request RSS delta 0, every hot cache bounded; CPU-bound honest posture ~8–15 concurrent — the limiter queues, RAM flat |
| **NEW** "The app crashes on cold open" | `sigsegv-coldfix-report.md`: root-caused (off-JS-thread jsi destructors → Hermes corruption), sim-only fix `3c24a5e`, gate 34/34 clean; independent verify 22/24 — say "root-caused and sim-gated, hardware untouched"; Android zero-crash oracle |
| **NEW** "The route paint isn't the field" | `demo-exchange-max.md`: 12/12 segment spans within ±5% of `/aqi` at midpoints (0.96–1.10); contract.ts == wire byte-shape; live drift observed mid-audit (real donations landing) |
| **NEW** "`/health` contradicts itself — 53 vs 125" | populations, not a dup-key bug: `sources.stations.count` = live instruments vs `history.stations` = climatology archive; already renamed `stations_climatology` on prod (`70914c00` live) |
| **NEW** "Numbers don't match their siblings" | rolling-deploy skew is the only true source of this (audit watched build flip mid-pass) → freeze rule: no deploys inside the demo window, `build_sha`==HEAD check at T-45 |

---

## Re-verify morning-of (numbers that moved tonight alone)

- `/community`: **41 / 23 / 2** — say "forty-something dev donations",
  never "users". `/v2/usage` is gated — don't promise its numbers on stage.
- `/v2/skill` h+11 band_hit: **33.0% tonight** (was ~22% last night —
  it drifts hourly; re-read at T-45 and quote the fresh read).
- `stations.count`: **53** (band 51–54; 24 in a DPCC stall).
- `/aqi.calibration`: now serves the rebuilt **8.8/n=70** — the stale-46.1
  answer is *retired*, but the deploy-lag *habit* stays: check
  `/health.build_sha` vs HEAD before quoting anything.
- Depart: `pct_less_vs_now` **3** tonight → leave-later row absent; it
  read 13 at rehearsal. Check at T-45 — the row and the "remind me"
  affordance live and die on that gate.
- Fires aside: modifier **1.06 REFUSED** tonight (easterly 123°). The
  belt is NW — the aside only fires on a carrying wind; T-45
  `curl /v2/why` decides.
- Demo OD: **metro+walk row present tonight** (61.6 vs car 9.0) — it's
  GTFS-service-hours dependent; re-verify at T-45 or the "car beats
  metro" clause is verbal-only.
- Demo APK: rehearsal build was already 19 `Mobile/` commits stale —
  per runbook the stage build re-cuts at final HEAD and re-smokes
  cold-launch→sheet→compare→depart→notifications.
- Freeze rule: no deploys inside the demo window; last image by T-60;
  `build_sha` check at T-45.
