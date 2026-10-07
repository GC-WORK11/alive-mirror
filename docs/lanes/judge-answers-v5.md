# judge-answers-v5 — the demo-morning card, refreshed for today's landings

The fourth armed-answer card. `judge-proof.md` covers the first ten hardest
questions; `judge-answers-v3.md` the audit-surfaced attacks; `judge-answers-v4.md`
re-armed after last night's landings. This v5 is the same card **re-armed after
today's**: the iOS crash residual killed (`9fbd851`), real admin auth
(`b563da2`), the landing P0 incident + its permanent gate (`f9ea5ae`/`f017dad`),
map depth r6 (`b47ffd4`), the cinematic route chooser (`e2ff634`), ops verified
on THIS account (`ops-handover.md` + `deploy-eod-report.md`), the code-truth
censuses (`1627a13`, `b633a2d`), landing v6 (`666c4c8`), and real notification
banners on-device (`notify-e2e-report.md`).

Format per attack: **THE ATTACK** (as a judge would say it) · **THE HONEST
ANSWER** (≤3 sentences you can say out loud) · **THE PROOF** (endpoint +
field / file:line / lane report) · **THE WEAKNESS LEFT** (stated plainly —
no spin).

Every figure re-verified against live prod
(`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, build
**`1627a13f`**, `/health.build_sha` == deployed ECR tag; HEAD `b633a2d` is
Mobile + docs ahead only — zero server diff) on **2026-10-07
~10:05–10:15 UTC (~15:35–15:45 IST)**. `scripts/verify_numbers.sh` ran
**zero flags** at this stamp. Numbers drift with the field — say "about ~N"
and re-run it at T-45.

---

## The ten attacks, re-answered (numbers re-pinned)

## 1. "Your citizen layer is empty."

**THE ATTACK:** "'Measured by its own commuters' — /community shows 44
observations all-time, 5 today, 24 contributors. A rival with seeded data
looks more alive than you."

**THE HONEST ANSWER:** "It's 44 real donations from dev devices — the
network is early and we say so; what proves it isn't the count, it's the
gate: 43 of 55 tracked corridors are suppressed right now because fewer
than three distinct devices crossed them in 72 hours, and that counter is
public. The field itself doesn't depend on the citizen layer — 52
government-grade instruments carry it; donations only sharpen corridors
where the crowd actually walks. A seeded map wouldn't have a suppression
mechanism at all — every published corridor on /community shows ≥3
devices."

**THE PROOF:** `GET /community` live → `obs_total:44`, `obs_today:5`,
`contributors:24`, `top_corridors[].devices` = 10s/7d, 8s/6d, 6s/5d, …
(all ≥3); `GET /v2/city/moves` → `n_trips:44`, `min_k:3`, corridors
`active:12` of `tracked:55` (72 h window). `server/community.py:702-731`
(`corridor_field_samples`: median needs ≥3 fresh traversals AND ≥3
distinct hashed devices or the cell emits nothing); `community.py:89-90`
(`_K_MIN_DEVICES=3`, `_CELL_WINDOW_S=72h`). `GET /v2/usage` exists but is
**admin-gated** — and tonight the gate is a real sign-in (see #11).

**THE WEAKNESS LEFT:** "Infrastructure for a crowd we don't have" is still
literally true — and the best defense is still behind the gate: `/v2/usage`
returns 401 to guests *by design*. The line: "the usage surface is
operator-gated because it's aggregate telemetry — the public proof is the
suppression counter itself." Don't oversell the layer.

## 2. "'Nothing leaves your phone' — over plaintext HTTP."

**THE ATTACK:** "Your privacy-first dosimeter ships consented movement
data unencrypted. NLB is TCP:80 only; `POST /v2/trip` travels cleartext
through Delhi cell networks."

**THE HONEST ANSWER:** "True — the transport is plaintext today, and we
don't pretend otherwise: the pentest says 'no TLS terminator today' in
writing. What travels is already an aggregate — no credentials, no
identity, endpoints trimmed 300 m — and the fixes keep landing around it:
the admin surface moved OFF Bearer-in-sessionStorage onto an HttpOnly
signed cookie this morning (see #11). TLS itself is a domain plus an ACM
cert and a 443 listener — an owner/architecture call we've flagged, not
hidden, and it's the top item in the pentest's residual list."

**THE PROOF:** `scripts/deploy.sh:256` (single `create-listener
--protocol TCP` on :80); `pentest-report.md` findings — plain HTTP edge
flagged **MED, owner decision**. `admin-auth-report.md` honest-limits
row: the new `alive_admin` cookie rides cleartext too — `Secure` is
conditional and *auto-enables the moment TLS lands*. At-rest guarantees:
`server/v2/trip.py` TRIM 300 m / THIN 100 m / ROUND ~11 m, sha256[:16] of
the device token (raw discarded); `community.py:_fold` — no per-trip row
ever created.

**THE WEAKNESS LEFT:** Same as v3/v4 — the cheapest fix in the audit still
isn't done, and the new admin cookie inherits the exposure (a copied
cookie works until its signed `exp`, worst ~8 h). If asked "when": "a
domain and a cert — the one real gap we'd close first." Not "in the
pipeline" — a flagged owner decision, in writing.

## 3. "Your AWS is decorative — stubs and a docker-compose."

**THE HONEST ANSWER:** Half right and we say which half — the scheduler
layer is honestly-disabled scaffolding, and the load-bearing AWS is the
deploy itself. **Today the whole ops loop got re-verified on this
account**: `deploy.sh` ran end-to-end twice in anger (CodeBuild→ECR→task
def→NLB register→healthy), three CloudWatch alarms are armed and the SNS
email is a *confirmed* subscription, and the bill for the last 7 days is
literally $0.00.

**THE PROOF:** `docs/plan/ops-handover.md` — every line verified on
account `185708268748` 2026-10-07 ~08:30–09:10 UTC: alarms
`alive108-field-age`/`alive108-field-emitter-dead`/`alive108-target-down`
all **OK** → SNS `alive108-ops` → owner email **confirmed** (not pending);
budget `alive108-monthly` $50 armed; `aws ce` net billed **$0.00 / 7 d**
(promo credits absorb ~$1.65/day gross ≈ $50/mo run-rate);
`deploy-eod-report.md` — today's two live deploys to `1627a13f`, target
healthy, every surface byte-compared to HEAD. CodeBuild→ECR→Fargate +
DynamoDB aggregates + S3 field archive + Secrets Manager — the
`/health.build_sha` tracks the running image (`1627a13f` == git).

**THE WEAKNESS LEFT:** Same core as before — EventBridge stubs stay
DISABLED scaffolding, and `/v2/usage` still can't be shown to a guest.
New honest note: the ops doc lists real config drift (a misnamed UTC-vs-IST
cron, a deleted always-green 5xx alarm — *removed because it was false
security*). "The scheduler stubs are honestly off; the alarms that exist
are the ones that can actually fire."

## 4. "Kriging doesn't beat IDW on your own artifact."

**THE HONEST ANSWER:** unchanged — what kriging buys isn't a better mean,
it's the σ: the ±band on every /aqi read, the dose band on every route,
the thing that widens honestly where stations are thin, and the posterior
our corridor traversals merge into. The MAE tie is published in the same
table as the coverage win — we don't cherry-pick.

**THE PROOF:** `server/data/field_validation.md` (MAE 22.0 kriged vs 21.8
IDW AND ±2σ coverage 95.2% vs 95.4% nominal in one table);
`server/airfield.py:77` (`SIGMA_CAL=3.2`), `:996-1016`
(`_krige_posterior`), `:1018-1044` (`sigma()` → `None` outside coverage —
no fake precision); `server/exposure.py:341` (σ → `dose lo/hi` — live
today: every `/v2/plan` option carries `dose {lo,mid,hi}`, e.g. car-AC
`1.5–9.7–17.8`).

**THE WEAKNESS LEFT:** unchanged — no window exists where kriging beats
IDW on MAE. "The mean is a tie; the band is the reason."

## 5. "Your self-grade decays — and it grades the model against itself."

**THE HONEST ANSWER:** "It does decay — every forecast does — and we
publish the whole ladder instead of hiding the tail; right now it reads
90% band-hit at h+0 down to ~36% at h+11 on 295 graded pairs. The hit
metric is strict CPCB-category equality, not 'were you close'. On
non-station cells the 'recorded' side shares our model+krige blend —
which is exactly why we call it a self-grade and publish the method."

**THE PROOF:** `GET /v2/skill` live — `pairs:295`, overall mae 24.9 /
bias +19.5 / band_hit 51.2%; ladder: h+0 mae 3.8 / band 89.7% → h+11
mae 38.2 / band **36.2%** (was 33.0% last night — **the tail drifts by
the hour; say "mid-thirties by h+11" today and re-read at T-45**);
`coverage.snapshots:42`, 40 hours graded since Oct-5 20:00 IST. The
instrument-truth comparison: the rebuilt LOO (see #6).

**THE WEAKNESS LEFT:** unchanged — self-grade truth is our own pipeline;
the honest line is the ladder plus instrument-anchored LOO.

## 6. "46.1 MAE on the wire vs your 95.2% headline — which is it?" → CLOSED

**THE HONEST ANSWER:** unchanged — stale artifact caught by us, rebuilt
as a real krige refit over live WAQI+DPCC instruments, and **still on the
wire today**: `mae_ug 8.8 / rmse 12.7 / n_stations 70 / bias +0.2`.

**THE PROOF:** `GET /aqi` → `calibration` live-verified ~10:09 UTC on
`1627a13f` (`method:"leave-one-out over live WAQI+DPCC instrument
readings (krige refit per held-out station)"`). The lesson stands:
**before quoting any number-class to a judge, `curl /health` and diff
`build_sha` against HEAD** — deploy lag is how this attack was born.

**THE WEAKNESS LEFT:** the attack's *shape* survives — "which error, full
stop?" Answer: "about 9 µg between stations by the rebuilt LOO, ~6 at an
instrument, ~22 on the clean-air archive window — which measure do you
want?"

## 7. "Skip consents unseen — a page-0 skipper donates without ever seeing the choice."

**THE HONEST ANSWER:** unchanged — it was a dark pattern, our own audit
caught it, the disclosure travels with the button on every page
(`1afccd8`). Sharing-ON-by-default remains our documented choice — now an
informed one, undoable in one tap.

**THE WEAKNESS LEFT:** unchanged — a privacy judge can prefer opt-in; the
answer is the documented default + one-tap undo.

## 8. "Field poisoning is feasible — unauthenticated POSTs write your field." → MOSTLY CLOSED

**THE HONEST ANSWER:** "It was true when our audit found it — both halves
of the fix are in and live-verified: every kept trip point must land
inside the service area (422 `outside service area`), the implied-C
inversion is capped at 900 µg/m³ (422 `implausible dose_ug for
duration_s`), and the limiter keys on the TCP socket peer so spoofed
headers mint nothing."

**THE PROOF:** commits `9f4533b` + `e483a96`;
`server/tests/test_v2_hardening.py`; `fix-trip-bounds-report.md`; last
night's live burst (150 spoofed-XFF+token requests → ~50/50 200/429,
identical to unmarked control; pre-fix image returned 200×200). k≥3 gate
+ median-of-≥3 traversals stand behind it (`community.py:702-731`).

**THE WEAKNESS LEFT:** unchanged — hashed self-minted tokens mean a
≥3-token fabricator can still inject a corridor cell at 1 rps/IP
(pentest MED — attestation is the next real layer). "The bounds and the
socket-peer limiter hold today; attestation is not a tonight fix."

## 9. "Your ~35× rests on a long OD nobody walks."

**THE ATTACK:** "You demo a 24.7 km walk nobody takes. The spread is a
strawman."

**THE HONEST ANSWER:** "It's the demonstrative pair, not a promise — the
long OD exists so the decomposition is visible: concentration × time ×
ventilation. Across 40 real OD pairs the engine audit found genuine dose
savings on about a quarter of them with zero absurd detours; the spread
moves with the field — it read ~33× on the demo OD an hour ago — which
is why we quote a band, not a constant. And the product answer isn't
'drive instead' — it's 'leave at a cleaner hour'."

**THE PROOF:** live `POST /v2/plan` ~10:12 UTC on the judge-typed OD
(India Gate → "huda city centre", 24.7 km): **23 options**, car-AC
**9.7** (band 1.5–17.8) vs on-foot **349.5–396** → **~36×** mid-to-mid,
**33.2×** on `verify_numbers.sh`'s own pairing (slowest/best 40.6×);
`took_ms ~6,670` fresh (warm ~50–660 ms — the T-40 `warm_task.py` is
load-bearing). **No metro+walk row in this read** — see watch item F.
`docs/plan/NUMBERS.md` 31–45× band.

**THE WEAKNESS LEFT:** Same — the headline IS the extreme pair; and
today's read had **no transit row** (GTFS service-hours dependent — it
read metro+walk 61.6 last night). **Re-verify at T-45 or the "car beats
metro ~7×" clause is verbal-only.**

## 10. "Your engine dose can exceed the OSRM dose on the same OD."

**THE HONEST ANSWER:** unchanged — correct and disclosed: engine rows
carry `duration_basis:"freeflow"` + `duration_model:"estimated"` on the
wire; without a congestion feed a dirtier-slower row is a duration-model
artifact, not a smokier corridor; the 40-OD re-run found zero
genuinely-smokier corridors.

**THE PROOF:** `Bridge/contract.ts:447-449`;
`docs/plan/handoff.md:78` (103 worse-dose rows, all duration-model
artifact); the flag rides today's live plan response.

**THE WEAKNESS LEFT:** unchanged — real until a congestion feed lands;
say `duration_basis` first.

---

## v4's new attacks, re-armed

## 11. "Is it secure? Or is it a demo that never got attacked?" → HARDER TO HIT NOW

**THE ATTACK:** "Your admin console is a Bearer token in an env var plus
a browser `prompt()` — one XSS away from full compromise."

**THE HONEST ANSWER:** "That was true this morning — we fixed it before
lunch. The operator token now mints a stateless HMAC-signed session
cookie — HttpOnly, SameSite=Strict, 8-hour expiry — the JS never holds
the secret past one POST body, so the XSS-steals-token path is dead by
construction, and the login endpoint is rate-limited five tries then
~one per five seconds per socket peer. Verified end-to-end: 12 auth
tests plus a live curl chain — guest 401, wrong token 401, right token
200 + signed cookie, logout kills it."

**THE PROOF:** `b563da2` + `docs/lanes/admin-auth-report.md` —
`POST /v2/admin/login` → `Set-Cookie alive_admin=v1.<exp>.<sig>`
(`sig=HMAC-SHA256(token,"alive-admin-v1:<exp>")[:32]` — stateless, no
session store, rotation of the token is a global logout);
`GET /v2/admin/session` **live on prod right now** →
`{"authenticated":false}` for this probe; `/v2/usage` guest → 401
`"admin sign-in required"` (the detail string itself changed — the gate
is the new auth); login bucket `(0.2,5)` verified — 6th POST → 429.
`sessionStorage.alive_admin_tok` + both `prompt()` calls **deleted from
the shipped page**. Bearer deliberately kept for ops curl — same guard,
two transports.

**THE WEAKNESS LEFT:** Named in the report, not hidden: the cookie rides
plaintext :80 until TLS lands (a copied cookie works until `exp` — same
exposure class as the Bearer it replaced); no server-side revocation
(stateless — token rotation is the kill switch); one shared operator
identity (right size for the demo, wrong if a second human needs the
board with accountability).

## 12. "Does it scale? One Fargate task, one vCPU — ten judges open it at once."

**THE HONEST ANSWER:** unchanged — measured, not guessed: ~0.95 GB
working set vs ~2 GB the API actually gets, per-request RSS delta zero;
the binding constraint is CPU (~2.5–6.5 s per `/v2/plan` reprice) →
honest posture **~8–15 concurrent active users** — a demo room, not a
viral spike; the 10 rps/IP limiter + 256-entry solve-dedupe mean the
fifteenth judge queues politely.

**THE PROOF:** `docs/lanes/lowram-report.md`; `deploy.sh` `--cpu 1024
--memory 3072` (OSRM sidecar takes 1 GB); 20 bounded hot-path stores
itemized.

**THE WEAKNESS LEFT:** unchanged — cold start ~60–100 s on a fresh task
(engineered out of the demo window by T-60 Spot→on-demand flip + T-40
warm task; runbook in `docs/demo-day.md` §Ops).

## 13. "It crashes. The simulator build SIGSEGV'd all week." → THE RESIDUAL IS DEAD

**THE ATTACK:** "Your own lane reports documented a ~40% cold-launch
crash — and last night's card admitted a 2/24 residual. Judges don't get
a second tap."

**THE HONEST ANSWER:** "The residual is dead too — measured, not hoped.
After the destructor funnel, the same rig still killed 12 of 30 cold
launches; lldb showed five different Hermes structures dying — the
corruption was constant, the walker varied. The hole was `Promise` —
every async turbomodule call runs `resolve/reject` on a module queue, a
full off-JS-thread runtime mutation during cold-boot promise churn. One
surgical hop moved the whole call onto the JS thread: **0 kills in 30
real cold cycles on the same rig, same harness, minutes apart —
z ≈ 3.9, p ≈ 5e-5.** And it's all `#if TARGET_OS_SIMULATOR` — the
hardware the demo runs on was never the crash surface."

**THE PROOF:** `docs/lanes/ios-residual-report.md` — 40% (12/30,
Wilson [24.6%,57.7%]) → 0% (0/30, upper bound ≲11% at 95%); 11 lldb
`bt all` captures (`ios-residual-logs/lldb-C*.txt`), five distinct
victim structures (OldGen::search ×6, IdentifierHashTable, JSMapImpl,
StringPrimitive, CardBoundaryTable); fix `9fbd851` —
`TurboModuleUtils::Promise` gains `enable_shared_from_this` +
`invokeAsync` hop, binary-verified reachable in the shipped dylib;
parent fix `3c24a5e` (`Mobile/patches/react-native+0.86.3.patch`).
Android: zero-line FATAL/ANR oracle across every run.

**THE WEAKNESS LEFT:** honestly bounded, not proven-zero: 0/30 bounds the
rate ≲11% (95%) — say "30 clean cold launches straight on the rig that
was killing 40%", never "it can't crash". The mutator is *inferred*
(open §7 hole + matching structures), not caught red-handed. Other
off-thread jsi touches could exist — the `ProtectMetadata` tripwire
stays armed to convert a recurrence into a diagnosable abort. iOS sim
only — hardware never had it.

## 14. "Is the data real — or painted to look real?"

**THE HONEST ANSWER:** unchanged — a hostile audit pulled the painted
segments, queried /aqi at every midpoint: **12/12 spans within ±5%**
(ratios 0.96–1.10, consistent with the ×1.06 smoke modifier); contract
diffed byte-shape against the wire; live drift observed mid-audit (real
donations landing during the probe).

**THE PROOF:** `demo-exchange-max.md` + `seg_midpoints.txt`;
`segments[]` on every plan option (`c152760`, reroute parity `58632f3`).

**THE WEAKNESS LEFT:** unchanged — no standing "prove the paint"
endpoint beyond `/aqi` itself; a judge can re-run the midpoint check in
five minutes — that IS the answer.

---

## The NEW attacks — armed today

## 15. "Your landing page was dead on prod this morning. How do you catch regressions?"

**THE ATTACK:** "I curled your site an hour ago and got a frozen splash.
You don't even know when your front page dies."

**THE HONEST ANSWER:** "We caught it ourselves, mid-drive — a hostile
visual lane captured `Uncaught SyntaxError` on the live page, a sibling
lane root-caused it to a bare apostrophe inside a single-quoted JS
string from that morning's copy pass, and the fix shipped and deployed
within the hour, re-driven live. Then we made the whole bug class
unshippable: a real HTML parser extracts every inline `<script>` in
`server/*.html` and runs `node --check` on it — as a pytest *and* a CI
gate at push, with a planted-bomb red test proving it fires."

**THE PROOF:** `docs/lanes/visual-thread-report.md` (dead-state capture
→ `landing-390-dead`, diagnosed in-chat, healed shots after `f9ea5ae` +
deploy); `docs/lanes/script-guard-report.md` — `scripts/check_inline_scripts.py`
(stdlib only; comment-embedded `<script>` prose emits warnings not code;
`.mjs` retry for module scripts; line-preserving padding so the error
line IS the HTML line), `server/tests/test_inline_scripts.py` (3 tests —
green on the 4 real blocks, red on the planted f9ea5ae fixture),
`.github/workflows/ci.yml` `Inline script syntax gate` step — a syntax
bomb fails the push in seconds. The old guardrail
(`test_landing_script_wellformed` — brace counter) stayed green through
the incident; that's why the new gate exists. Full apostrophe sweep of
every user-facing surface: zero live bombs, enumeration in the report.

**THE WEAKNESS LEFT:** the incident did happen — the honest frame is
"our own drive caught it, the fix was live within the hour, and the
class can never ship again" — not "it never breaks." And the gate
covers syntax only: a correctly-quoted string with wrong copy is still
review work. Also true: `node --check` guards `server/*.html` — the
Mobile bundle's gate is `tsc`+lint+the test runners, all green at HEAD.

## 16. "The map is a skeleton — GTA Vice City, not Google Maps."

**THE ATTACK:** "Zoom in and it's emptiness — no streets, no blocks. A
routing app whose map has no roads."

**THE HONEST ANSWER:** "That was a style gap, not a data gap — the tiles
already carried the full OpenMapTiles schema; we hid it behind minzooms.
This morning the style got densified: minor-road casings and the full
street mesh from z12, buildings z13, housenumbers and one-way arrows
z15, and the opening camera lands inside the street regime at z12.5.
Plus the whole NCR basemap prefetch-warms itself — 744 tiles z9–13,
27.4 MB, verified sitting in the on-device cache — so venue-wifi death
can't blank the demo map."

**THE PROOF:** `docs/lanes/map-depth-report.md` + `b47ffd4` —
`Mobile/src/map/v2-light.json` (+271 lines: casing layers, minzoom
drops, per-class landuse), `App.tsx` `INIT_VIEW` z11→12.5,
`Mobile/src/map/tileWarm.ts` (`OfflineManager.createPack` NCR z9–13,
once per install, fails silent; ambient cache raised 160 MB).
Device-verified: `map-depth-shots/ios-z13…z16-nd.png` — every block
named, housenumbers, one-ways, building footprints on the real sim;
`cache.db` holds `delhi-ncr-z9-13-r1` = **744 tiles / 27.4 MB**. Honest
bar: "at z13+ we're at Google's street-level coverage — same OSM data;
we don't have brand POIs, traffic layer, or their palette — we keep
warm-neutral so dose colors are the only saturated hues."

**THE WEAKNESS LEFT:** stated in-report: no brand POIs/ratings, no live
traffic layer; z14+ streams live not prefetched (~200 MB was the wrong
trade); OpenFreeMap-hosted base with documented fallbacks
(`v2RasterStyle`, prod `delhi.pmtiles`).

## 17. "Half the app is dead switches and stub endpoints — it's demo-ware."

**THE ATTACK:** "Every hackathon app has a settings page where the
toggles do nothing. Prove yours aren't glued on."

**THE HONEST ANSWER:** "We ran a code-truth census this morning on both
halves. Server: every reachable GET serves real data — zero stub
endpoints; every `stub|dummy|TODO` grep hit is a 'never fake' house-rule
comment. Mobile: every screen and component traced to its mount and its
data source — zero fakes; and the audit *did* find three dead switches —
they're wired now: the remind toggle gates the offer AND cancels the
armed OS ping, the brief toggle cancels the daily ping, and
delete-my-data disarms both."

**THE PROOF:** `docs/lanes/codebase-server-report.md` (`1627a13`) —
route census over `main.py` + 4 mounted routers + FastAPI defaults
(~68 decorated route registrations by this card's own AST recount —
the lane enumerated 64 by decorator-grep; either way every reachable
GET answers real data, every observed 4xx is honest); **zero** stub
endpoints; zero duplicate JSON keys (AST + 30-response wire replay);
two real bugs fixed in-pass (`_end_label` naive-TZ, dead admin timing
labels); findings filed not hidden (shadowed `/admin/api` index,
writerless `POST /report`, unwired `/v2/depart`+`/v2/today` aliases).
`docs/lanes/codebase-mobile-report.md` (`b633a2d`) — the three
dead-switch fixes + zero-orphan inventory; **`/v2/feedback` verified
LIVE on prod — the old "410-retired" lore was wrong**: POST → 200
`{"stored":true,"total_reviews":2}` (lane's write; this card's own
malformed POST drew the schema 422 `stars must be 1..5` — registered
and validating, not a sinkhole).

**THE WEAKNESS LEFT:** the real residuals are on the same reports:
no React error boundary anywhere (MED — a render throw still reaches
the OS), ~70 dead exports, `Mobile/AGENTS.md` stale (claims Expo
Router). "The census publishes its own findings section — that's the
answer."

## 18. "Who runs this thing? Who's paying — and who gets paged when it dies?"

**THE ATTACK:** "It's a Fargate task someone launched from a laptop.
Nobody's watching it; the bill is somebody's surprise."

**THE HONEST ANSWER:** "The ops loop is verified, in writing, on this
account — we ran `deploy.sh` end-to-end twice today: CodeBuild→ECR→new
task def→NLB register→healthy target, and rollback is one flag to an
immutable sha tag. Three CloudWatch alarms watch the things that
actually break — field staleness, the ingest emitter going silent, the
target group draining — into an SNS topic whose email subscription is
*confirmed*, not pending. And the bill is boring: $0.00 net for the last
seven days — promo credits absorb the ~$1.65/day gross; a $50 budget
alarm is the tripwire if the credits ever stop."

**THE PROOF:** `docs/plan/ops-handover.md` — verified ~08:30–09:10 UTC
on account `185708268748`: alarms table (state OK + breach conditions),
`get-metric-statistics` truth pass (what `FieldAgeSeconds` 0.0 actually
means), SNS sub state `confirmed` to the owner's email,
`aws ce` cost table line-by-line ($10.4 gross → $0.00 net),
`alive108-monthly` budget ActualSpend $0.00 / Forecast $16.25 /
HEALTHY; `deploy-eod-report.md` — today's two live rolls to `1627a13f`,
TG healthy, every page byte-compared to HEAD; rollback:
`./scripts/deploy.sh rollback <sha>` (immutable ECR tags;
`f9ea5ae8` = last fully-baked pre-today build).

**THE WEAKNESS LEFT:** honest: the run-rate (~$50/mo) is real the day
credits end; the ops doc itself lists config drift to not re-introduce
(a misnamed cron, a deleted always-green 5xx alarm); Spot reclaim means
a task swap is always ~4 min away — the T-60 flip is the owner's call,
default stays Spot.

## 19. "The 'remind me' button — does anything actually fire, or is it UI?"

**THE ATTACK:** "Notification claims are the easiest thing to fake at a
hackathon. Show me a real banner from the real engine."

**THE HONEST ANSWER:** "Recorded, on-device, un-seeded: on iOS the
permission dialog fires the moment the engine has something real to
say, then `stagnation` and `clean-window` banners slide in off live
prod fields — and mid-drive the server admitted a `trend_down` driver
and the phone pinged it, un-scripted. The dedupe file itself is the
proof: a +8 fire-count jump correctly did NOT fire because the rule
floor is +15 — the engine stays quiet when it should, and that's on
video too."

**THE PROOF:** `docs/lanes/notify-e2e-report.md` +
`notify-e2e-shots/` — `ios-natural-fires.mp4` (permission → two real
banners), lockscreen + Notification Center stacks, `events-final.json`
verbatim dedupe marks (`stagnation`, `window`, `trend_down`,
`grap_clear`, `reflect`; `beltFires` rebaselined 4→12, **no `fires_nc`
mark**). Release APK side: `POST_NOTIFICATIONS` in the decoded manifest
+ the notify engine + banner strings inside the shipped bundle —
statically proven, runtime banner pending an emulator (org session cap;
fills when it lands).

**THE WEAKNESS LEFT:** foreground-poll only (60 s tick — the settings
copy says so); `outlook_*` pings gate evenings-only by design; Android
runtime delivery proof is the one unfilled cell in the table — say
"iOS proved end-to-end, Android statically verified with the emulator
run queued", not "both platforms".

## 20. "Cute demo — but Delhi will be clean that day, won't it?"

**THE ATTACK:** "Pollution demos need dirty air. If demo morning is a
blue-sky day your whole product reads flat."

**THE HONEST ANSWER:** "Check the wire — `/v2/outlook` forecasts the
demo window into the worst air of the week: tomorrow (demo day one)
Poor ~107, then Friday ~177, Saturday ~134, Sunday ~137 µg/m³ — every
demo day is CPCB Very Poor. The demo doesn't need luck; the season is
the exhibit — and the honest dose spread gets *wider* in dirty air."

**THE PROOF:** `GET /v2/outlook` live ~10:10 UTC: `2026-10-08 Poor
107.1` (heavy hours 20:30–23:30 IST), `2026-10-09 Very Poor 176.9`,
`2026-10-10 Very Poor 134.1`, `2026-10-11 Very Poor 136.8`; `best_day`
= today. The day cards carry their own honesty: Fri–Sun rows are
`confidence:"lo"` with `anchor_w 0.0` — "past the live anchor's reach,
raw CAMS skill only" printed on the wire itself.

**THE WEAKNESS LEFT:** it's a forecast — CAMS can drift the band by
demo morning (say "the forecast says Very Poor", not "it will be");
heavy hours listed are IST evening — a 10 AM demo slot still reads
Poor-to-Very-Poor on the day-mean, but the cleanest-window rows
(Sat/Sun ~10:30–18:30) are where the "leave at a cleaner hour" beat
gets its biggest payoff. Re-read at T-45.

---

## Watch items — armed, not attacked

### A. Thin citizen layer ("who actually uses it?")

The numbers are the honest answer: **44 trips all-time, 24 contributors,
5 today, 31.4 km today** — say "forty-something real dev donations"
never "users" and never "growing" (latest donation ~3 h old at stamp
time). The defense-in-public is the k≥3 suppression counter (12 of 55
publishable); the defense-in-private is `/v2/usage` — now behind the
real sign-in (see #11): offer to open it on stage Wi-Fi if a judge
presses, and frame the guest 401 as "gated by design" not a malfunction.

### B. The depart ~8% day

Live read on the demo OD (auto mode, full window): now **26.6** → best
**24.5 @+23 h** → worst **54.7 @+20 h**; `pct_less_vs_now` = **8** —
the Mobile leave-later row is *still absent* (gate is `>8`; it read 13
at rehearsal, 3 last night — it flickers). The landing's own depart
line shows at `pct>0` ("leave ~09:00 — 8% less"), so the surfaces
disagree by design-of-threshold, not by bug. If a screenshot catches a
small saving: **"the curve reads the field, not the pitch — today's air
is flat until evening, so the honest saving is small; on a swing day
the same surface pays double digits — and Friday's forecast is exactly
that swing."** Never promise the row — check `pct_less_vs_now` at T-45.

### C. Rolling deploys mid-demo — the freeze-window rule

Unchanged, now armed twice over: DEPLOY FREEZE T-60 → demo end
(`docs/demo-day.md`), **and** the landing-P0 war story (#15) is the
exhibit of why gates matter. If a judge catches number-skew: "that's a
rolling deploy catching up — refresh in thirty seconds." `build_sha`
== HEAD check at T-45 (prod `1627a13f`; HEAD `b633a2d` is Mobile+docs
only — no server diff, no skew risk).

### D. `/health` stations — CLOSED

`history.stations` was renamed `stations_climatology` (`70914c0`) and is
live on prod — the dup-key scare is a story now: **52** live instruments
(`sources.stations.count`) vs **125** climatology archive
(`history.stations_climatology`). "125 is the decade archive behind the
'vs typical' baseline; 52 is tonight's live instruments."

### E. Demo-day air — the forecast is the drama (NEW)

See attack #20: all three weekend demo days read Very Poor on the wire.
Script order matters: land the "the field is live, not canned" beat
first, then point at the outlook row — "it saw this coming three days
out." The cleanest-window cells (Sat/Sun late-morning-to-evening ~64–94
µg) are the "leave at a cleaner hour" payoff. `confidence:"lo"` past the
anchor — the wire says so itself; keep the honesty.

### F. Metro row — absent on this read (NEW)

Today's `/v2/plan` on the demo OD returned **no metro+walk option**
(last night it served 61.6 vs car 9.0 — "car beats metro ~7×").
GTFS-service-hours dependent. **At T-45 re-run the demo OD: if a
transit row exists, the "honest surprise" clause is live; if not, the
clause is verbal-only** — do not quote a row that isn't on the wire.

### G. Fires aside — still refused (NEW)

`carrying:false` on `/v2/why` — wind **6.4 km/h from 225° (SW)**; the
burn belt is NW. Modifier ×1.06 is evaluated and on the wire, the
"smoke drifting in" story is not. The aside only fires on a carrying
wind; T-45 `curl /v2/why` decides.

### H. Android notification proof — pending (NEW)

iOS end-to-end proved (banners on live field); Android is statically
proven (manifest permission + engine in the shipped bundle) with the
runtime emulator run queued behind the org session cap. If the demo
rig is the Android APK: "the engine and the permission ship in the
binary — the runtime banner is the one proof still landing." If it
fills before demo: replace this line with the video pointer.

---

## The numbers card — live prod `1627a13f`, ~10:10 UTC / ~15:40 IST Oct-7

*Re-pin at T-45 — this card is internally consistent as of this stamp;
`verify_numbers.sh` ran zero flags.*

| figure | live value now | source |
|---|---|---|
| stations live | **52** (waqi+dpcc, both feeds `ok`; accept 52–54, 24 if DPCC stalls >90 min) | `/health.sources.stations.count`; `/aqi.field.station_readings` agrees |
| climatology stations | **125** | `/health.history.stations_climatology` (renamed, live) |
| field freshness | `field_age_s ~126`, refresh ~13 min, `field_stale:false` | `/health` |
| model samples | **100** | `/aqi.field.samples` |
| edges | **1,070,459** total / **903,058** priced | `/health.routing` |
| engine | `alive_core` | `/health.engine` |
| transit | metro `true` + bus `true` real feeds | `/health.transit.real_feeds` |
| city pm2.5 | mean **43.1** / median **43.7** / max **55.5** (25-pt lattice); city aqi **72**, GRAP indicative **stage 0**; **−30.1%** vs typical Oct (median 61.7) | `/v2/city.pm25_stats`, `.typical`, `.grap` |
| CP point | pm2.5 **64.2** breathing, **us_aqi 154**, nearest sample **1.8 km** | `/aqi?lat=28.6315&lon=77.2167` |
| breath | **618 µg/day mid ≈ 1.96 cigarettes** | `/v2/city.breath` |
| why-line | **trend** primary now — field easing −15.0 µg over 5.9 h (34 builds); VC **3,329 m²/s** vs ~3,000 ref — ventilation briefly *above* typical | `/v2/why.drivers[0]` |
| fires | **44** total / **12** in-belt / **26.2 MW** FRP; modifier **×1.06** | `/aqi.fire` + `/v2/why` |
| fires carrying? | **NO — REFUSED** (wind **6.4 km/h from 225°** SW; belt is NW) | `/v2/why.evaluated.fires.carrying:false` |
| LOO calibration | **mae 8.8 / rmse 12.7 / n 70 / bias +0.2** — rebuilt, ON the wire | `/aqi.calibration` |
| skill | **295 pairs**; overall mae 24.9 / band 51.2%; h+0 mae 3.8·band 89.7% → h+11 mae 38.2·band **36.2%**; 42 snapshots / 40 h graded | `/v2/skill` |
| community | **44 obs / 5 today / 24 contributors** / 31.4 km / 10.9 µg dose today; avoided **312.9 today / 1,278.9 all-time**; latest donation **~3 h ago** | `/community` |
| corridors | **12 publishable / 55 tracked**, min_k 3 (72 h) | `/v2/city/moves.corridors` |
| archive | recorded **[1,3–15]**, gaps **{0,2}**, 14 today / 42 total; pending 16–23 | `/v2/archive` |
| usage endpoint | guest → **401 `{"detail":"admin sign-in required"}`** — gated by the new auth | live probe |
| admin session | `GET /v2/admin/session` → **`{"authenticated":false}`** live on prod | live probe |
| feedback endpoint | **LIVE** — `POST /v2/feedback` registered + validating (malformed probe → 422 `stars must be 1..5`; lane's real POST → 200 `stored:true, total_reviews:2`). Old "410" lore is dead. | probe + `codebase-mobile-report.md` |
| rate limiter | defaults 10 rps/burst 30; plan+reroute 2/6; trip+observe+report 1/5; **admin login 0.2/5**; `/health` exempt — XFF/token spoof immunity live-verified last night | `middleware.py` + `admin-auth-report.md` |
| plan demo OD (IG→"huda city centre", 24.7 km) | **23 options**: car-AC **~9.7** (1.5–17.8) / walk **~349–396** → **~36×** mid (33.2× verify_numbers pairing; slowest/best 40.6×); **no metro row this read**; `took_ms ~6,670` fresh | sanctioned `POST /v2/plan` |
| depart demo OD (auto) | now **26.6** → best **24.5 @+23 h** → worst **54.7 @+20 h**; `pct_less_vs_now` **8** → remind row absent (`>8` gate); landing line shows | `/depart` |
| outlook @CP | today Moderate 67.3 → Thu **Poor 107.1** → Fri **Very Poor 176.9** → Sat **Very Poor 134.1** → Sun **Very Poor 136.8** — all three demo days Very Poor | `/v2/outlook` |
| latencies | GETs ~0.3–0.5 s; plan fresh-OD `took_ms` ~6.7 s; warm ~50–660 ms | curl + wire |
| spend | **net $0.00 last 7 d** (promo credits; ~$1.65/day gross ≈ $50/mo run-rate); `alive108-monthly` $50 budget armed | `ops-handover.md` §4 |
| task shape | 1 task × 1 vCPU / 3 GB (API ≈2 GB after OSRM sidecar); **~8–15 concurrent** honest posture | `deploy.sh` + `lowram-report.md` |
| builds | prod **`1627a13f`** == ECR tag == today's deploys; HEAD `b633a2d` is Mobile+docs ahead only (no server diff) | `/health.build_sha` + git |
| ops | deploy.sh verified live ×2 today; 3 alarms OK → SNS email **confirmed**; rollback = `deploy.sh rollback <sha>` | `ops-handover.md` + `deploy-eod-report.md` |
| iOS crash residual | **0/30** post-hop (was 12/30 same rig); Wilson bound ≲11% | `ios-residual-report.md` |
| offline basemap | **744 tiles z9–13 / 27.4 MB** in on-device cache | `map-depth-report.md` |

---

## Attacks that fail — quick reference

| accusation | why it fails — proof pointer |
|---|---|
| "It's dressed-up nearest-neighbor" | `GET /aqi` → kriging on, `nearest_sample_km:1.8` echoed; `airfield.py` krige posterior; IDW is a *documented* fallback |
| "The ±band is decorative" | `SIGMA_CAL=3.2` vs measured coverage; `sigma()`→`None` outside coverage; live dose bands on every option (car-AC `1.5–17.8` today) |
| "The spread is fabricated" | re-derived live: ~36× today (9.7 vs ~350 mid); a cooked number doesn't drift with the field |
| "1.07M edges is a slide number" | `/health.routing.edges` 1,070,459 / `edges_priced` 903,058 live |
| "The C++ engine is vaporware" | `/health.engine` = `alive_core`; `test_parity_dose.py` 8 tests bit-for-bit |
| "The archive is fake/staged" | `/v2/archive` recorded [1,3–15] gaps {0,2} — records only the served field, never back-fills |
| "Hindi is a veneer" | `strings.ts` `hi` mirror compiler-enforced; hi-parity lane reports |
| "You hid the cold start" | `docs/plan/cold-path.md` + T-60/T-40 runbook in writing before any judge asked |
| "Security is a claim, not a test" | pentest 2 HIGHs found+fixed; **plus today's real auth**: HMAC cookie sign-in live on prod (`/v2/admin/session` → `authenticated:false` guest), login rate-limited, XSS theft path deleted — `admin-auth-report.md` |
| "It falls over under a demo load" | `lowram-report.md`: ~0.95 GB vs ~2 GB, per-request RSS delta 0, all hot caches bounded; honest ~8–15 concurrent |
| "The app crashes on cold open" | residual **dead**: 40%→**0/30** post Promise-hop (`9fbd851`, Wilson ≲11%), five-structure lldb evidence; sim-only, hardware untouched — `ios-residual-report.md` |
| "The route paint isn't the field" | `demo-exchange-max.md`: 12/12 segment midpoints within ±5% of `/aqi` |
| "The map is empty" | `map-depth-report.md`: full OSM street mesh z12+, device shots z13–16, **744-tile** offline prefetch on-device |
| "It just asserts the best route" | `route-chooser-report.md`: candidates draw as equals → winner settles + verdict pill pins the honest reason on-route; verified on 3 OD pairs (and the verify pass caught+fixed a real strip-race bug) |
| "Nobody would notice a regression" | `visual-thread-report.md` + `script-guard-report.md`: the dead-landing P0 was caught mid-drive, fixed+deployed within the hour, and the bug class is now a CI gate |
| "Half the code is stubs/dead UI" | `codebase-server-report.md` + `codebase-mobile-report.md`: full census, zero stub endpoints, zero fakes, 3 dead switches wired this pass, findings filed not hidden; `/v2/feedback` live (old lore was wrong) |
| "Nobody's watching prod / who's paying" | `ops-handover.md`: 3 alarms OK + SNS confirmed + budget armed + **$0.00 net/7d**; `deploy-eod-report.md`: deploy.sh ran live twice today |

---

## Re-verify morning-of (numbers that moved today alone)

- `/community`: **44 / 24 / 5** — say "forty-something dev donations".
- `/v2/skill` h+11 band_hit: **36.2% now** (33.0% last night, ~22% the
  night before — drifts hourly; re-read at T-45).
- `stations.count`: **52** (band 52–54; 24 in a DPCC stall).
- City air eased intraday: mean **43.1** (was 55.6 this morning);
  `/v2/why` driver flipped stagnation→trend-falling; CP pm25 **64.2**,
  us_aqi **154**.
- `/aqi.calibration`: rebuilt **8.8/n=70** still on the wire — but the
  deploy-lag *habit* stays: `/health.build_sha` vs HEAD before quoting.
- Depart: `pct_less_vs_now` **8** → remind row still gated out (`>8`);
  landing's own line shows it. Check at T-45.
- **Metro row absent this read** — the "car beats metro ~7×" clause
  needs a live row at T-45 or it stays verbal.
- Fires aside: **REFUSED** (SW wind 225° vs NW belt) — `carrying:false`.
- **Outlook is the demo-day story**: Thu Poor 107 → Fri/Sat/Sun Very
  Poor 177/134/137 — `confidence:"lo"` past the anchor; re-read at
  T-45 and let the wire's own confidence labels carry the honesty.
- `/v2/feedback` lore corrected: **LIVE**, POST→200. Kill any stale
  "410" line on sight.
- `/v2/usage` guest 401 now reads `admin sign-in required` — the gate
  is the cookie auth, not a raw token check.
- Demo build: stage APK re-cuts at final HEAD and re-smokes
  cold-launch→sheet→compare→depart→notifications per runbook; the
  chooser beat + map depth + dead-switch fixes (`e2ff634`/`b47ffd4`/
  `b633a2d`) ship in that cut.
- iOS rig: the 0/30 is sim-side; hardware cold-open was never the crash
  surface — but re-smoke the demo rig anyway at T-40.
- Freeze rule: no deploys inside the demo window; last image by T-60;
  `build_sha` check at T-45.
