# judge-answers-v6 — the final card, armed for demo morning

The fifth armed-answer card and the last refresh: `judge-proof.md` covers the
first ten hardest questions; v3 the audit-surfaced attacks; v4/v5 re-armed
across yesterday's and this morning's landings. This v6 folds in the final
landing wave — every claim below was verified against its lane report, not
trusted from the brief:

- iOS crash **final verdict** — Release build `0/60` cold cycles
  (`ios-release-residual-report.md`, `0c13dd9`): the residual is a
  dev-debug-only race whose victim is the React dev inspector. Honest answer:
  "release clean; the debug race is a post-demo engineering item."
- Offline pack **found broken then fixed then live** — `offline-walk` caught
  r1 downloading 0 tiles (`81c2326`); `54a296e` shipped the http-style_url
  repair + parity test; iOS sim verified `region_tiles=744`; prod route live
  on `ffddab93` (`offline-pack-fix-report.md`).
- Privacy spine **audited PASS + F1 fixed** — zero identity fields on any
  gated wire, k≥3 verified firing live (55 cells → 12 publishable, all hour
  buckets dark), installs honestly `null` (`privacy-spine-report.md`); the one
  latent gap (ungated day-rows) closed at `af653e5`
  (`privacy-f1-fix-report.md` — tests green; **deploy pending**, see below).
- Community ledger **proven 100% real** — page↔store reconciliation exact to
  DynamoDB + S3, zero test-labelled devices, zero seeds
  (`community-sanity-report.md`, `cb4efbe`/`834e6d6`).
- `/v2/skill` **6 s → 0.7 s on prod** (`deploy4-report.md`, `c86074ff`).
- Landing **v7 live** — hero = the shipped app's real home screen, new
  film-strip of three real chooser frames (`landing-v7-report.md`,
  `ffddab9` = deploy-5 image).
- notify-e2e **complete on BOTH platforms** — real banners on iOS dev-client
  AND the release APK incl. the real permission dialogs
  (`notify-e2e-report.md`).
- Admin login **proven end-to-end on prod** + the T-30 playbook landed
  (`admin-login-e2e-report.md`, `docs/plan/admin-login.md`).
- Rehearsal-v2 verdicts folded in (`demo-rehearsal-v2-report.md`) + the timed
  T-90→T-0 runbook exists at `docs/plan/demo-morning.md`
  (`demo-morning-report.md`).

Format per attack: **THE ATTACK** (as a judge would say it) · **THE HONEST
ANSWER** (≤3 sentences you can say out loud) · **THE PROOF** (endpoint +
field / file:line / lane report) · **THE WEAKNESS LEFT** (stated plainly —
no spin).

Every figure re-verified against live prod
(`alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`, build
**`ffddab93`** — `/health.build_sha` == deployed ECR tag; HEAD `7c68c8b` is
ahead only by `af653e5` + docs — the **single server diff** between prod and
HEAD is the privacy day-row gate, itself test-verified and latent-only) on
**2026-10-07 ~14:00–14:10 UTC (~19:30–19:40 IST)**. `verify_numbers.sh` ran
**one flag** (a stale fires count inside `writeup.md` — doc nit, not live
skew). Numbers drift with the field — say "about ~N" and re-run at T-45.

---

## The ten attacks, re-answered (numbers re-pinned)

## 1. "Your citizen layer is empty."

**THE ATTACK:** "'Measured by its own commuters' — /community shows 44
observations all-time, 5 today, 24 contributors. A rival with seeded data
looks more alive than you."

**THE HONEST ANSWER:** "It's 44 real donations from dev devices — and this
afternoon an audit proved every one of them real: the page reconciles
*exactly* to the raw stores, and a dictionary attack on all 24 device
hashes against ~140 test-style ids found zero hits. The network is early
and we say so; what proves it isn't the count, it's the gate — 43 of 55
tracked corridors are suppressed right now because fewer than three
distinct devices crossed them, and that counter is public. A seeded map
wouldn't have a suppression mechanism at all — every published corridor
shows ≥3 devices."

**THE PROOF:** `GET /community` live → `obs_total:44`, `obs_today:5`,
`contributors:24`, `top_corridors[].devices` = 10s/7d, 8s/6d, 6s/5d, 5s/5d,
5s/4d (all ≥3); `GET /v2/city/moves` → `n_trips:44`, `min_k:3`, corridors
`active:12` of `tracked:55` (72 h window). `community-sanity-report.md` —
full `alive108-agg` scan (170 items) + S3 snapshot: day sums 17+14+8+5=44
exact, 24 distinct `device#<sha256[:16]>` ledger metas exact, avoided
Σ=1,278.9 exact; zero test-labelled devices, zero non-Delhi geometry,
zero seed writes (the load tool never POSTs trips). `server/community.py`
`_K_MIN_DEVICES=3` + publish-time gates. `GET /v2/usage` exists but is
**admin-gated** — and the gate is a real sign-in (see #11).

**THE WEAKNESS LEFT:** "Infrastructure for a crowd we don't have" is still
literally true — newest donation ~7 h old at this stamp. Honest caveats
from the audit, in writing: two legacy `/observe` traversals inflate two
corridor dose averages until they age out ~Oct-8 06:20Z (the 44-trip
headline is unaffected — it reads the shared ledger they never entered);
14 ledger rows carry pre-bound impossible speeds (admitted before the
Oct-7 bounds fix); "24 contributors" counts device tokens, not humans.
And the page's own wording is loose: the real gate is "≥3 phones **ever**
crossed it AND a trip in the last 72 h" — say it that way if pressed.

## 2. "'Nothing leaves your phone' — over plaintext HTTP."

**THE ATTACK:** "Your privacy-first dosimeter ships consented movement
data unencrypted. NLB is TCP:80 only; `POST /v2/trip` travels cleartext
through Delhi cell networks."

**THE HONEST ANSWER:** "True — the transport is plaintext today, and we
don't pretend otherwise: the pentest says 'no TLS terminator today' in
writing. What travels is already an aggregate — no credentials, no
identity, endpoints trimmed 300 m — and the fixes keep landing around it:
the admin surface moved OFF Bearer-in-sessionStorage onto an HttpOnly
signed cookie this morning and the sign-in was proven end-to-end on prod
today (see #11). TLS itself is a domain plus an ACM cert and a 443
listener — an owner/architecture call we've flagged, not hidden, and it's
the top item in the pentest's residual list."

**THE PROOF:** `scripts/deploy.sh` (single TCP:80 listener);
`pentest-report.md` — plain HTTP edge flagged **MED, owner decision**.
`admin-login-e2e-report.md` honest-residuals row: the `alive_admin` cookie
rides cleartext too — `Secure` is conditional and *auto-enables the moment
TLS lands*; the report's own fix for demo-day is "the phone hotspot." At
rest: `server/v2/trip.py` TRIM 300 m / THIN 100 m / ROUND ~11 m,
sha256[:16] of the device token (raw discarded); `privacy-spine-report.md`
verified zero identity fields leave any wire (see #22).

**THE WEAKNESS LEFT:** Same as v3–v5 — the cheapest fix in the audit still
isn't done, and the admin cookie inherits the exposure (a copied cookie
works until its signed `exp`, worst ~8 h). If asked "when": "a domain and
a cert — the one real gap we'd close first." Not "in the pipeline" — a
flagged owner decision, in writing.

## 3. "Your AWS is decorative — stubs and a docker-compose."

**THE HONEST ANSWER:** Half right and we say which half — the scheduler
layer is honestly-disabled scaffolding, and the load-bearing AWS is the
deploy itself. **Today the ops loop ran in anger four times**:
`deploy.sh` rolled CodeBuild→ECR→task def→NLB register→healthy at
`1627a13f` (twice), `c86074ff` (deploy-4, the skill-latency fix) and
`ffddab93` (deploy-5, landing v7 + the offline-pack route) — with a
fifth killed mid-run when a sibling lane's newer image won. Three
CloudWatch alarms are armed and the SNS email is a *confirmed*
subscription; the 7-day bill is literally $0.00.

**THE PROOF:** `docs/plan/ops-handover.md` — verified on account
`185708268748` 2026-10-07 ~08:30–09:10 UTC: alarms
`alive108-field-age`/`alive108-field-emitter-dead`/`alive108-target-down`
all **OK** → SNS `alive108-ops` → owner email **confirmed**; budget
`alive108-monthly` $50 armed; `aws ce` net billed **$0.00 / 7 d** (promo
credits absorb ~$1.65/day gross ≈ $50/mo run-rate). `deploy-eod-report.md`
+ `deploy4-report.md` + `offline-pack-fix-report.md` — today's rolls, TG
healthy each time, pages byte-compared to HEAD. `/health.build_sha`
tracks the running image (`ffddab93` == git).

**THE WEAKNESS LEFT:** Same core — EventBridge stubs stay DISABLED
scaffolding, `/v2/usage` can't be shown to a guest, and the ops doc lists
real config drift (a misnamed UTC-vs-IST cron, a deleted always-green 5xx
alarm — removed because it was false security). New honest note: a
killed-mid-run deploy leaves `:latest` pointing one tag behind live —
cosmetic only (task-defs pin sha tags), stated in the fix report so the
next lane doesn't chase it.

## 4. "Kriging doesn't beat IDW on your own artifact."

**THE HONEST ANSWER:** unchanged — what kriging buys isn't a better mean,
it's the σ: the ±band on every /aqi read, the dose band on every route,
the thing that widens honestly where stations are thin, and the posterior
our corridor traversals merge into. The MAE tie is published in the same
table as the coverage win — we don't cherry-pick.

**THE PROOF:** `server/data/field_validation.md` (MAE 22.0 kriged vs 21.8
IDW AND ±2σ coverage 95.4% nominal in one table — live re-verify 3,550
pairs / 85 stations at this stamp); `server/airfield.py:77`
(`SIGMA_CAL=3.2`), `_krige_posterior`, `sigma()` → `None` outside
coverage; live today: every `/v2/plan` option carries `dose {lo,mid,hi}`
— e.g. car-AC `3.4–9.1–14.9` on the verify OD right now.

**THE WEAKNESS LEFT:** unchanged — no window exists where kriging beats
IDW on MAE. "The mean is a tie; the band is the reason."

## 5. "Your self-grade decays — and it grades the model against itself."

**THE HONEST ANSWER:** "It does decay — every forecast does — and we
publish the whole ladder instead of hiding the tail; right now it reads
90% band-hit at h+0 down to ~36% at h+11 on 330 graded pairs. The hit
metric is strict CPCB-category equality, not 'were you close'. On
non-station cells the 'recorded' side shares our model+krige blend —
which is exactly why we call it a self-grade and publish the method. And
the endpoint earned its own war story today: the ~5 s miss was an
O(archive) S3 doc re-parse per request — a sig-checked parsed-doc cache
put it at ~0.7 s on prod, verified before/after on the same build."

**THE PROOF:** `GET /v2/skill` live — `pairs:330`, overall mae 24.3 /
bias +19.2 / band_hit 51.5%; ladder: h+0 mae 4.1 / band 89.7% → h+11 mae
37.2 / band **36.1%** (the tail drifts by the hour; say "mid-thirties by
h+11" and re-read at T-45); `coverage.snapshots:46`, 44 h graded since
Oct-5 20:00 IST. `deploy4-report.md` — miss 5.25 s → **0.71 s** wall on
prod `c86074ff` (~0.2 s server-side; `generated_ist` advanced on each
spaced hit = real recomputes, not cache replays); re-hit at this stamp
0.55 s wall incl. ~0.5 s vantage RTT. Instrument-truth: the LOO below.

**THE WEAKNESS LEFT:** unchanged — self-grade truth is our own pipeline;
the honest line is the ladder plus instrument-anchored LOO.

## 6. "46.1 MAE on the wire vs your 95.2% headline — which is it?" → CLOSED

**THE HONEST ANSWER:** unchanged — stale artifact caught by us, rebuilt
as a real krige refit over live WAQI+DPCC instruments, and **still on the
wire today**: `mae_ug 8.8 / rmse 12.7 / n_stations 70 / bias +0.2`.

**THE PROOF:** `GET /aqi` → `calibration` live-verified ~14:04 UTC on
`ffddab93` (`method:"leave-one-out over live WAQI+DPCC instrument
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
informed one, undoable in one tap. (Rehearsal-v2 re-verified the consent
page persists across force-stop + cold relaunch: `consent.json
{"seen":true,"sharing":"on"}`.)

**THE WEAKNESS LEFT:** unchanged — a privacy judge can prefer opt-in; the
answer is the documented default + one-tap undo.

## 8. "Field poisoning is feasible — unauthenticated POSTs write your field." → MOSTLY CLOSED

**THE HONEST ANSWER:** "It was true when our audit found it — both halves
of the fix are in and live-verified: every kept trip point must land
inside the service area (422 `outside service area`), the implied-C
inversion is capped at 900 µg/m³ (422 `implausible dose_ug for
duration_s`), and the limiter keys on the TCP socket peer so spoofed
headers mint nothing. And today's ledger audit double-checked the whole
corpus from the other side: zero test-labelled devices, zero injected
geometry, zero seed writes — the bounds hold and the store shows it."

**THE PROOF:** commits `9f4533b` + `e483a96`;
`server/tests/test_v2_hardening.py`; `fix-trip-bounds-report.md`; the
live burst (150 spoofed-XFF+token requests → ~50/50 200/429, identical
to unmarked control); `community-sanity-report.md` pollution hunt (all
55 cells Delhi H3 res-8, doses 0–38.4 µg, km 0.4–12.9, in-bounds).
k≥3 gate + median-of-≥3 traversals stand behind it.

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
moves with the field — it read ~33× on the demo OD minutes ago — which
is why we quote a band, not a constant. And the product answer isn't
'drive instead' — it's 'leave at a cleaner hour'; the depart surface is
offering exactly that on this same OD right now (35% less by leaving
tomorrow 10:00)."

**THE PROOF:** live `POST /v2/plan` ~14:07 UTC on the judge-typed OD
(India Gate → HUDA City Centre, ~24.7 km): **21 options**, car-AC
**10.5–12.3** vs on-foot **367–375** → **~33×** mid-to-mid; the
verify-Numbers pairing (CP→Gurugram) reads **33.3×** (slowest/best
36.5×). **Metro+walk is back on the wire**: 38.5 on the demo OD / 39.2
on the verify OD — "car beats metro ~4×" is armed again (see watch F).
`took_ms ~7,100–8,900` fresh (warm ~50–660 ms — T-40 `warm_task.py` is
load-bearing). `docs/plan/NUMBERS.md` 31–45× band.

**THE WEAKNESS LEFT:** Same — the headline IS the extreme pair; the
transit row is GTFS-service-hours dependent and flickered twice today
(absent on v5's read, present again now). **Re-verify at T-45 or the
"car beats metro ~4×" clause is verbal-only.**

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

## v4's attacks, re-armed

## 11. "Is it secure? Or is it a demo that never got attacked?" → PROVEN END-TO-END ON PROD

**THE ATTACK:** "Your admin console is a Bearer token in an env var plus
a browser `prompt()` — one XSS away from full compromise."

**THE HONEST ANSWER:** "Fixed before lunch, proven on prod by dinner. The
operator token mints a stateless HMAC-signed session cookie — HttpOnly,
SameSite=Strict, 8-hour expiry — the JS never holds the secret past one
POST body, so the XSS-steals-token path is dead by construction, and the
login endpoint is rate-limited five tries then ~one per five seconds per
socket peer. This afternoon a lane ran the whole thing live: real login
on the real NLB, board renders live data, logout clears, every gate
probe registered — then did it again in a real browser, screenshots to
prove it. The demo-morning playbook for it exists too."

**THE PROOF:** `admin-login-e2e-report.md` — prod curl chain ~11:35 UTC:
`POST /v2/admin/login` → 200 + `Set-Cookie alive_admin=v1.<exp>.<sig>;
HttpOnly; Max-Age=28800; SameSite=strict`; `GET /v2/admin/session` →
`{"authenticated":true}`; `/v2/usage` + `/admin/api` → 200 live
aggregates; logout → cookie killed. Gate probes: guest → 401 on every
gated surface, `/v2/admin/session` guest → `{"authenticated":false}`
(fails closed), wrong token → 401 `bad operator token`
(`hmac.compare_digest`), 12-POST brute probe → interleaved 401/**429**
`retry_after` (bucket `(0.2,5)` exactly as `middleware.py`). Browser:
`admin-login-e2e-shots/` — gate card → SIGN IN → live board → SIGN OUT.
`docs/plan/admin-login.md` — the T-30 playbook incl. "Chrome 'Save
password?' → **Never**" (a saved token is an unowned copy).
`GET /v2/admin/session` on prod right now → `{"authenticated":false}`.

**THE WEAKNESS LEFT:** Named, not hidden: cookie rides plaintext :80
until TLS (copied cookie valid till `exp` — replayed-after-logout 200
*observed*, bounded ~8 h, rotation of `alive108/admin-token` is the
global kill); no per-cookie revocation (stateless by design); one shared
operator identity (right size for the demo). On demo-hall Wi-Fi the
phone hotspot is the documented mitigation.

## 12. "Does it scale? One Fargate task, one vCPU — ten judges open it at once."

**THE HONEST ANSWER:** unchanged — measured, not guessed: ~0.95 GB
working set vs ~2 GB the API actually gets, per-request RSS delta zero;
the binding constraint is CPU (~2.5–8 s per `/v2/plan` reprice — today's
fresh reads ran 7.1–8.9 s post-refresh) → honest posture **~8–15
concurrent active users** — a demo room, not a viral spike; the 10
rps/IP limiter + 256-entry solve-dedupe mean the fifteenth judge queues
politely. The worst user-visible tail got patched today — `/v2/skill`
miss 5.2 s → 0.7 s on prod.

**THE PROOF:** `docs/lanes/lowram-report.md`; `deploy.sh` `--cpu 1024
--memory 3072` (OSRM sidecar takes 1 GB); 20 bounded hot-path stores;
`deploy4-report.md` (skill parsed-doc cache, `generated_ist`-advancing
recomputes at 0.71 s).

**THE WEAKNESS LEFT:** unchanged — cold start ~60–100 s on a fresh task
(engineered out of the demo window by the T-40 warm task + Spot flip
rule; `docs/demo-day.md` §Ops, `docs/plan/demo-morning.md`).

## 13. "It crashes. Your own lane reports documented a cold-launch crash." → RELEASE IS CLEAN; DEBUG RACE IS POST-DEMO

**THE ATTACK:** "The simulator build SIGSEGV'd all week — and even your
fix has a residual. Judges don't get a second tap."

**THE HONEST ANSWER:** "The final verdict is in and it's honest: the
iOS **Release** build — the binary a demo would actually run — survived
**60 of 60 cold launches** on the same rig, same sim, same prod backend.
The dev-debug build does still crash ~1-in-2 cold launches — but every
kill's victim thread is `consoleTaskRun`, the React dev inspector's
console-replay task, which *does not exist* in a release build. The
debug race is real engineering debt filed for after the demo; it is not
a demo risk because the demo vehicle is the release binary."

**THE PROOF:** `ios-release-residual-report.md` (`0c13dd9`) — Release-
iphonesimulator `0/30` + `0/30` = **0/60**, Wilson [0%, 6.0%] vs dev-debug
14/30 (46.7%): two-proportion z ≈ 4.3, Fisher p ≈ 8.4e-6 — decisively
different rates, not worse luck. Oracles: 0 pid deaths through the 22 s
window, 0 SIGSEGV in the runningboardd stream, 0 `.ips` crash reports.
Exercise per cycle = real `simctl location set` CoreLocation → JSI
promise traffic (the suspected corruptor class). `ios-residual-reverify-
report.md` — the 14/30 debug regression, every victim `consoleTaskRun`.
Android side: **zero FATAL/ANR/SIGSEGV across every recorded drive** —
rehearsal-v2 logcat oracle, apk-v10 KVM drive (all steps PASS),
notify-e2e six+ relaunches.

**THE WEAKNESS LEFT:** honest bounds: 0/60 bounds the release rate ≲6%
(95%); whether the corruptor is gone or merely finds no victim is
unproven — both models fit the data, stated in the report. A **device**
(hardware) build is unmeasured — the RN patch is
`#if TARGET_OS_SIMULATOR` only and this rig has no device. And the rule:
if anyone must demo the dev-client (Metro), the ~47% cold residual
still stands — **don't; ship the Release build.**

## 14. "Is the data real — or painted to look real?"

**THE HONEST ANSWER:** unchanged — a hostile audit pulled the painted
segments, queried /aqi at every midpoint: **12/12 spans within ±5%**
(ratios 0.96–1.10, consistent with the ×1.08 smoke modifier on the wire
right now); contract diffed byte-shape against the wire; live drift
observed mid-audit (real donations landing during the probe).

**THE PROOF:** `demo-exchange-max.md` + `seg_midpoints.txt`;
`segments[]` on every plan option (`c152760`, reroute parity `58632f3`);
today's `smoke_modifier` 1.08 live on `/v2/plan` + `/v2/why.evaluated`.

**THE WEAKNESS LEFT:** unchanged — no standing "prove the paint"
endpoint beyond `/aqi` itself; a judge can re-run the midpoint check in
five minutes — that IS the answer.

## 15. "Your landing page was dead on prod this morning. How do you catch regressions?"

**THE HONEST ANSWER:** "We caught it ourselves, mid-drive — a hostile
visual lane captured `Uncaught SyntaxError` on the live page, a sibling
root-caused it to a bare apostrophe in a single-quoted JS string, and the
fix shipped within the hour. Then we made the whole bug class
unshippable: a real HTML parser extracts every inline `<script>` in
`server/*.html` and runs `node --check` on it — as a pytest *and* a CI
gate at push, with a planted-bomb red test proving it fires. And the page
itself kept moving: v7 is live right now — the hero is the shipped app's
actual home screen and there's a new film-strip of three real recorded
chooser frames."

**THE PROOF:** `visual-thread-report.md` + `script-guard-report.md` —
`scripts/check_inline_scripts.py`, `server/tests/test_inline_scripts.py`
(green on real blocks, red on the planted fixture), CI `Inline script
syntax gate` step. `landing-v7-report.md` (`ffddab9`) — hero =
`demo-rehearsal-v2` real device capture served 236 CSS px via preloaded
srcset (19–30 KB webp), chooser strip = three frames from a real run on
the shipped build; page weight ≤206 KB all-in. Live-verified at this
stamp: `/` 200, 118,614 B, serves `app-hero-*.webp` +
`app-choose-strip-*.webp` markers.

**THE WEAKNESS LEFT:** the incident did happen — "our own drive caught
it, fixed within the hour, the class can't ship again" is the frame, not
"it never breaks." The gate covers syntax only; wrong copy in a quoted
string is still review work.

## 16. "The map is a skeleton — and your offline claim was just a row in a database."

**THE ATTACK:** "Zoom in and it's emptiness — no streets, no blocks. And
your 'offline pack' — did it ever download a tile?"

**THE HONEST ANSWER:** "The densification stands — full OSM street mesh
from z12, buildings z13, housenumbers and one-ways z15, opening camera
inside the street regime. And on the pack you're right to ask: our own
offline walk found it broken — the region row existed with **zero
tiles** because MapLibre can't parse a `file://` style URL. It got fixed
the same day: the server now serves the bundled style over HTTP, the
warm path points at it, and on a real iOS sim the repaired pack
downloaded all **744 tiles** into the on-device cache. The route it
depends on is live on prod right now. What survives on the installed
demo APK today is the ambient cache plus the pre-warm pan — which is
exactly what the runbook does at T-45."

**THE PROOF:** `offline-walk-report.md` (`81c2326`) — the honest
found-broken report (file:// `style_url` → `region_tiles` 0 forever);
`offline-pack-fix-report.md` (`54a296e`) — new `GET /v2-light.json`
(byte-identical 94,254 B copy, `test_v2_light_parity.py` guards drift),
`tileWarm.ts` rewritten to the http URL, pack renamed `r2` so a dead r1
row can't shadow it, 6 unit tests; iOS sim `cache.db`:
`region_tiles=744` + `region_resources=297`, counts stable. Prod probe
at this stamp: `GET /v2-light.json` → **200, 94,254 B** on `ffddab93`.
Densification: `map-depth-report.md` + `b47ffd4`.

**THE WEAKNESS LEFT:** the shipped APK (`apk-v10` @ `70914c0`) predates
the fix — installed builds still carry dead-r1 code (they're no worse
off: r1 never downloaded anyway); the working pack lands in the next
APK cut ≥`54a296e`. Android-side pack verification is queued on the
KVM child (same MapLibre `OfflineManager` API both platforms; iOS is
the verified arm). Style/env overrides skip the pack by design;
Devanagari glyphs inside the pack depend on OFM's ranges — noted.
No brand POIs/ratings, no live traffic layer; z14+ streams not
prefetched. The demo-morning fallback is ambient cache + the T-45 pan —
say it exactly like that.

## 17. "Half the app is dead switches and stub endpoints — it's demo-ware."

**THE HONEST ANSWER:** unchanged — the code-truth census ran on both
halves. Server: every reachable GET serves real data — zero stub
endpoints. Mobile: every screen traced to mount + data source — zero
fakes; the audit *did* find three dead switches — they're wired now
(remind gates the offer AND cancels the armed OS ping, brief cancels the
daily ping, delete-my-data disarms both). Since then the full server
suite re-ran green on the privacy fix (1,244 passed, 5 platform skips).

**THE PROOF:** `codebase-server-report.md` — route census, zero stub
endpoints, zero duplicate JSON keys, two real bugs fixed in-pass,
findings filed not hidden; `codebase-mobile-report.md` — dead-switch
fixes + zero-orphan inventory; `/v2/feedback` verified LIVE on prod
(malformed probe → 422 `stars must be 1..5` — validating, not a
sinkhole). `privacy-f1-fix-report.md` — `pytest tests` full suite
**1,244 passed**.

**THE WEAKNESS LEFT:** unchanged — no React error boundary anywhere
(MED), ~70 dead exports, `Mobile/AGENTS.md` stale. "The census publishes
its own findings section — that's the answer."

## 18. "Who runs this thing? Who's paying — and who gets paged when it dies?"

**THE HONEST ANSWER:** unchanged and re-verified — the ops loop is
written down and was exercised four times today (see #3): deploys at
`1627a13f` ×2, `c86074ff`, `ffddab93`, rollback = one flag to an
immutable sha tag. Three CloudWatch alarms → SNS *confirmed* email;
$0.00 net/7 d under promo credits (~$50/mo run-rate after); $50 budget
alarm armed. A 2 h watchdog swept the latest roll: 9 clean field
cycles.

**THE PROOF:** `docs/plan/ops-handover.md` + `deploy-eod-report.md` +
`deploy4-report.md` + `9216f2d` watchdog report; rollback
`./scripts/deploy.sh rollback <sha>`.

**THE WEAKNESS LEFT:** honest: run-rate is real the day credits end;
Spot reclaim means a task swap is always ~4 min away — stay-Spot is the
owner's standing call ($0 budget), flip only on reclaim or decision.

## 19. "The 'remind me' button — does anything actually fire, or is it UI?" → BOTH PLATFORMS PROVEN

**THE ATTACK:** "Notification claims are the easiest thing to fake at a
hackathon. Show me a real banner from the real engine."

**THE HONEST ANSWER:** "Recorded on both platforms, off live prod
fields. On iOS the permission dialog fires the moment the engine has
something real to say, then stagnation and clean-window banners slide
in un-seeded — and mid-drive the server admitted a trend-down and the
phone pinged it, un-scripted. On the release APK the real Android 13+
permission dialog was granted through the UI, the same three triggers
fired naturally, and a window *revision* re-post replaced its own card
in place — dedupe machinery working on camera. The proof of honesty is
what did NOT fire: the fires trigger stayed dark all day on both rigs
because the belt count rose +8 and the rule floor is +15."

**THE PROOF:** `notify-e2e-report.md` + `notify-e2e-shots/` — iOS:
`ios-natural-fires.mp4` (permission → two live banners), lockscreen/NC
stacks, `events-final.json` verbatim marks (`stagnation`, `window`,
`trend_down`, `grap_clear`, `reflect`, `outlook_heavy` — the last fired
on the first poll after its 17:00 IST gate opened); **no `fires_nc`
mark** (`beltFires` rebaselined 4→12, +8 < +15 floor). Android APK
`70914c0` on the KVM rig: GrantPermissionsViewModel grant via UI,
`air-events` channel `mImportance=4` HIGH sound+vibration, shade +
keyguard shots, `shade_now2.png` = the window revision replacing its own
card, dedupe marks verbatim; natural `stagnation`/`window`/`trend_down`
+ seeded-prior `grap_clear`/`reflect`. Alarm-side: `dumpsys alarm`
shows the armed `RTC_WAKEUP` for tomorrow 10:00 and the 07:00 daily
ping toggle on/off with the settings switch (rehearsal-v2).

**THE WEAKNESS LEFT:** heads-up **peek** never rendered on the
android-35 google_apis emulator across ~11 min of footage (NMS
autogroup presentation quirk — post, channel, shade, keyguard,
in-place replace all verified; on iOS the peek did render) — claim
peek on iOS, or one physical-device check before claiming it on
Android. Foreground-poll only (60 s tick — settings copy says so);
`outlook_*` evenings-only by design; `band`/`severe` honestly quiet
today (rules verified by the jump-silence + unit tests).

## 20. "Cute demo — but Delhi will be clean that day, won't it?" → RE-PINNED; THE SHAPE CHANGED

**THE ATTACK:** "Pollution demos need dirty air. If demo morning is a
blue-sky day your whole product reads flat."

**THE HONEST ANSWER:** "The forecast moved since this morning — and the
move is itself the demo. The weekend reads Very Poor on the wire —
Friday ~168, Saturday ~130, Sunday ~138 µg/m³. Tomorrow, day one, is
the honest in-between: a **Moderate** ~87 day-mean, but with a dirty
evening (heavy hours 19:30–23:30 IST) and a clean 14:30–18:30 window —
which is literally the product's pitch: the same `/v2/depart` surface is
already telling a commuter 'leave tomorrow 10:00, breathe 35% less'.
The season is the exhibit; the honest dose spread gets *wider* in dirty
air, and it does get dirty."

**THE PROOF:** `GET /v2/outlook` live ~14:05 UTC: `2026-10-07
Satisfactory 58.1` (partial, conf hi) → `2026-10-08 Moderate 86.6`
(conf med, anchor_w 0.62, cleanest window 14:30–18:30 @39, heavy
19:30–23:30) → `2026-10-09 Very Poor 168.4` → `2026-10-10 Very Poor
130.2` → `2026-10-11 Very Poor 137.9` (all `confidence:"lo"`,
`anchor_w 0.0` — "past the live anchor's reach, raw CAMS skill only"
printed on the wire itself). `best_day` = today. `/v2/depart` on the
verify OD: `pct_less_vs_now` **35** → best 16.2 µg @ +20 h (Oct-8
10:00) vs now 25.0 / worst 50.3 @ +23 h.

**THE WEAKNESS LEFT:** the "every demo day Very Poor" line from v5 is
**dead** — tomorrow is Moderate; don't say it. It's a forecast — CAMS
can drift the band again by morning (say "the forecast says", not "it
will be"). The cleanest-window rows (Thu 14:30–18:30; Sat 09:30–18:30;
Sun 11:30–16:30) are where "leave at a cleaner hour" pays off — land
the live-field beat first, then point at the outlook. Re-read at T-45.

---

## The NEW attacks — armed on the final wave

## 21. "Your community ledger could be seeded test junk — prove it isn't."

**THE ATTACK:** "Hackathon dashboards are full of `test_user_42`. Audit
the ledger itself — if it's staged, everything downstream is a lie."

**THE HONEST ANSWER:** "We did the audit you just described — full scan
of the DynamoDB aggregates table plus the S3 corridor snapshot,
recomputed every displayed figure from raw items: the page's 44 trips,
24 contributors and 1,279 µg avoided reconcile **exactly** — day sums
17+14+8+5, twenty-four distinct hashed device metas, not one off. Then
we dictionary-attacked all 24 device hashes against ~140 test-style
candidates — zero hits. Zero non-Delhi geometry, zero impossible
values, zero seed scripts in the write path. The wrinkles it found are
data wrinkles, not fabrication — and they're listed in the report."

**THE PROOF:** `community-sanity-report.md` — 170-item `alive108-agg`
scan + S3 `community/state.json`: ledger↔day sums field-exact;
corridor names all real CP-area streets from the offline gazetteer;
`tools/load_v2.py` never POSTs trips; consent-off drives verifiably
posted **zero** telemetry. k≥3 visibly suppressing: 29 cells with
trips but <3 devices correctly invisible; every hour bucket dark on
live data (5 trips from 3 devices spread across 4 hours — if the gate
were absent, 4 rows would exist).

**THE WEAKNESS LEFT:** real but disclosed in the same report — two
legacy `/observe` traversals (the retired pre-ledger path) inflate two
corridor dose averages until ~Oct-8 06:20Z; 14 ledger rows carry
pre-bound impossible speeds (real traversals, broken duration
telemetry — refused by the implied-C gate anyway); and "contributors"
counts tokens not humans — a reinstall mints a new one.

## 22. "The admin board can reconstruct a person — aggregates always leak."

**THE ATTACK:** "'Aggregates only' is what every leaky system says.
Show me a field that can't collapse to one user."

**THE HONEST ANSWER:** "The privacy promise is structural, not
rhetorical: a person-identifying row can't be served because none
exists at rest — trajectories die at ingest, devices are sha256[:16]
before any store. And today a hostile audit of every gated wire found
**zero identity fields anywhere** — every `devices`/`contributors`
value is an integer count; the only hex strings are public H3 cells
and a graph checksum. k≥3 isn't a claim — it was caught firing in four
independent places at once. The one latent gap the audit found, it
filed and we fixed the same day."

**THE PROOF:** `privacy-spine-report.md` — recursive scan of
`/v2/usage`, `/admin/api`, `/admin/api/*`, the `/admin` page source:
**zero** token/device/contributor/install/uuid/hash/email/_id fields;
station lat/lons are government monitors only; corridor rows are
~500 m cell centres. Live suppression evidence: 43/55 corridor cells
suppressed (three rows sit exactly at k=3), all recent-hour buckets
dark, 1 OD pair counted under `suppressed` not shown, review notes
withheld below k=3. "Installs" renders `null` + the reason — a number
that can't exist isn't faked. `privacy-f1-fix-report.md` (`af653e5`)
— the F1 day-row gap closed with the same suppress-and-count shape as
the other surfaces, tests incl. "three donations from ONE device is
k=1"; full suite 1,244 green.

**THE WEAKNESS LEFT:** honest and stated: the F1 fix is committed but
**not yet deployed** — prod `ffddab93` predates `af653e5`; nothing
identifying is served meanwhile because every live day-row is ≥3, but
the structural hole stays latent until the next roll (say it exactly
like that if pressed). F2 — bare counts in windowed totals can
degenerate to one person on a 1-device window — was assessed and
deliberately not gated (a count is not a person; gating ops counters
is a policy call, disclosed not hidden). The stateless cookie's replay
bound (~8 h) is in #11.

## 23. "'Works offline' is a bullet on your slide — did anyone actually walk it?"

**THE ATTACK:** "Every app claims offline. Did you ever pull the cable
and try?"

**THE HONEST ANSWER:** "Yes — and the honest report led to a real bug:
the walk found the prefetch pack created its region row and downloaded
**zero tiles** — the fix shipped and is verified and live (see #16).
What actually works air-gapped today is what an 8/8 honesty pass
measured: mid-trip navigation plus the trip receipt on the cached
strip, landmark search through the bundled 124k-row gazetteer,
home/last-known repaints, and honest error+retry on the surfaces that
need the field. The demo-morning plan is unglamorous and true: 160 MB
ambient cache plus a pre-warm pan over the demo corridor at T-45 —
stream it once on good Wi-Fi and dead venue Wi-Fi can't blank the map."

**THE PROOF:** `offline-walk-report.md` (the walk + the finding),
`offline-pack-fix-report.md` (the fix + iOS-sim `region_tiles=744` +
prod route live), `testday-offline-report.md` (8/8 honesty pass —
air-gapped nav + receipt verified), `docs/plan/demo-morning.md` (the
T-45 pan written into the timed checklist).

**THE WEAKNESS LEFT:** the working pack reaches devices only in the
next APK cut ≥`54a296e` (installed APKs carry the dead-r1 code — no
regression, it never downloaded); Android pack verification still
queued on the KVM child. Plan/live surfaces honestly degrade (real
error + retry) rather than fake-stale — that's the posture, say it as
a feature.

---

## Watch items — armed, not attacked

### A. Thin citizen layer ("who actually uses it?")

**44 trips all-time / 24 contributors / 5 today / 31.4 km / 10.9 µg /
312.9 avoided today / 1,278.9 all-time** — say "forty-something real dev
donations", never "users", never "growing" (newest donation ~7 h old).
The public defense is the suppression counter (12 of 55 publishable);
the audit trail is `community-sanity-report.md` (see #21). `/v2/usage`
stays behind the sign-in — offer to open it on stage Wi-Fi; guest 401 =
"gated by design".

### B. The depart day — ARMED, row shows comfortably

Live on the verify OD: now **25.0** → best **16.2 @ +20 h** (tomorrow
10:00) → worst **50.3 @ +23 h**; `pct_less_vs_now` **35** — far over
the `>8` gate (it read 25–29 all afternoon; the flicker only exists at
served==8). Rehearsal-v2 showed the armed row verbatim: "leave tomorrow
10:00 → breathe ~25% less" + armed `RTC_WAKEUP` in `dumpsys`. Check at
T-45 anyway — the number reads the field.

### C. Rolling deploys mid-demo — the freeze-window rule

DEPLOY FREEZE T-60 → demo end. Prod is `ffddab93`; HEAD `7c68c8b` is
ahead only by `af653e5` (F1) + docs — if the privacy roll lands before
the freeze, re-check `build_sha`. Number-skew under a roll: "that's a
deploy catching up — refresh in thirty seconds."

### D. `/health` stations — CLOSED

`stations_climatology` still live: **54** live instruments (waqi+dpcc
both `ok`; band 52–54; 24 = DPCC stall) vs **125** decade-archive
stations. Same answer.

### E. Demo-day air — re-pinned (see #20)

Tomorrow Moderate ~87 with a dirty evening + a real clean window;
Fri–Sun Very Poor. Script order: live-field beat first, then the
outlook row, then the depart payoff (`pct 35` on the wire right now).
`confidence:"lo"` past the anchor — the wire's own honesty.

### F. Metro row — PRESENT AGAIN

`metro+walk` is on the wire at this stamp: **38.5** on the demo OD /
**39.2** on the verify OD → "car beats metro ~4×" clause is armed
(v5's "no metro row" read is stale). Still GTFS-service-hours
dependent — it flickered twice today (absent on some ODs/reads).
**T-45: re-run the demo OD; if absent, the clause stays verbal.**

### G. Fires aside — REFUSED at this stamp, but it flipped today

`/v2/why`: `carrying:false` — wind **4.1 km/h from 23°** (NNE); the
burn-belt gate is the 270–360° quadrant. Belt **16 fires / 41.4 MW /
modifier ×1.08**, feed live. The watchdog measured the gate honestly
both directions today: `carrying` flipped true on a northerly midday
(claim + full uplift ×1.27), back false as the wind clocked off-quad
(downscale exactly `1+(x−1)×0.3`, code-verified). Both wordings live
in `demo-morning.md` — T-45 `curl /v2/why` decides which the judge
hears; the flip itself is a good story ("the claim follows the wind,
verified live").

### H. Android notification proof — CLOSED (see #19)

Runtime proof landed on the release APK. Residual: heads-up peek on
the emulator — delivery verified, peek unproven on Android (it did
render on iOS).

### I. Offline basemap on the demo phone — ambient cache is the plan (NEW)

Installed APKs (`apk-v10` @ `70914c0`, rehearsal @ `c3f7e9e`) predate
the r2 fix — their pack code is dead-r1 (harmless; r1 never downloaded
anyway). If a final APK re-cuts ≥`54a296e` tonight, the r2 pack warms
once on good Wi-Fi at first launch. Otherwise: the T-45 pre-warm pan
over the demo corridor is what the venue survives on — stated in
`demo-morning.md`.

### J. iOS demo vehicle = Release, never dev-client (NEW)

60/60 cold cycles on the Release binary; the ~47% dev-debug residual
is a `consoleTaskRun` victim that only exists under a CDP inspector —
filed post-demo. If hardware ever enters the story: unmeasured, patch
is sim-only — say so.

### K. APK tip drift (NEW)

The v10 binary (`70914c0`) predates `54a296e` (r2 pack), `af653e5`
(F1), `795ff3b` (news air-card) and assorted docs — the app surfaces
still carry `why.line` which is live, and rehearsal-v2 ran clean on an
even older cut. Runbook note stands: if a re-cut lands, take the
newest per `apk-*-report.md`; don't chase it during the freeze.

---

## The numbers card — live prod `ffddab93`, ~14:05 UTC / ~19:35 IST Oct-7

*Re-pin at T-45 — internally consistent as of this stamp;
`verify_numbers.sh` ran one doc-nit flag (writeup fires count).*

| figure | live value now | source |
|---|---|---|
| stations live | **54** (waqi+dpcc, both `ok`; band 52–54, 24 if DPCC stalls >90 min) | `/health.sources.stations.count`; `/aqi.field.station_readings` agrees |
| climatology stations | **125** | `/health.history.stations_climatology` |
| field freshness | `field_age_s ~430–590`, refresh ~13–15 min (cycle slipped to ~26–29 min around the day's deploys — watchdog-noted), `field_stale:false` | `/health` |
| model samples | **102** | `/aqi.field.samples` |
| edges | **1,070,459** total / **903,058** priced | `/health.routing` |
| engine | `alive_core` | `/health.engine` |
| transit | metro `true` + bus `true` real feeds | `/health.transit.real_feeds` |
| city pm2.5 | mean **47.2** / median **42.3** / max **62.4** (25-pt lattice); city aqi **79**, GRAP indicative **stage 0**; **−29.2%** vs typical Oct (median 66.7) | `/v2/city.pm25_stats`, `.typical`, `.grap` |
| CP point | pm2.5 **62.3**, **us_aqi 152**, nearest sample **1.8 km** | `/aqi?lat=28.6315&lon=77.2167` |
| breath | **679 µg/day mid ≈ 2.15 cigarettes** | `/v2/city.breath` |
| why-line | **stagnation** primary — VC **467 m²/s** vs ~3,000 ref (factor 6.4; "the air is barely mixing — the day's pollution is sitting over the city"); trend easing −11.1 µg over 5.9 h underneath | `/v2/why.drivers[0]` + `.evaluated.trend` |
| fires | **90** total / **16** in-belt / **41.4 MW** FRP; modifier **×1.08** | `/aqi.fire` + `/v2/why.evaluated.fires` |
| fires carrying? | **NO — REFUSED** (wind **4.1 km/h from 23°** NNE; belt gate is 270–360°; flipped true midday on a northerly — watchdog-verified both ways) | `/v2/why.evaluated.fires.carrying:false` |
| LOO calibration | **mae 8.8 / rmse 12.7 / n 70 / bias +0.2** — rebuilt, ON the wire | `/aqi.calibration` |
| skill | **330 pairs**; overall mae 24.3 / band 51.5%; h+0 mae 4.1·band 89.7% → h+11 mae 37.2·band **36.1%**; 46 snapshots / 44 h graded; endpoint miss 5.2 s → **0.7 s** live | `/v2/skill` + `deploy4-report.md` |
| community | **44 obs / 5 today / 24 contributors** / 31.4 km / 10.9 µg dose today; avoided **312.9 today / 1,278.9 all-time**; latest donation **~7 h ago** | `/community` |
| community audit | page↔store **exact** (170 DDB items + S3 snapshot); 0 test-labelled devices (≈140-candidate dictionary attack); 0 non-Delhi geometry; 0 seed writes | `community-sanity-report.md` |
| corridors | **12 publishable / 55 tracked**, min_k 3 (72 h); all recent-hour buckets suppressed; 1 OD pair suppressed | `/v2/city/moves` + `privacy-spine-report.md` |
| archive | recorded **[1,3–19]**, gaps **{0,2}**, 17 today; pending 20–23 | `/v2/archive` |
| usage endpoint | guest → **401** — gated by the cookie auth | live probe |
| admin session | `GET /v2/admin/session` → **`{"authenticated":false}`** live on prod | live probe |
| admin e2e | login→cookie→board→logout proven on prod + browser shots + T-30 playbook | `admin-login-e2e-report.md` |
| feedback endpoint | **LIVE** — POST→200 stored; malformed→422 | probe + `codebase-mobile-report.md` |
| rate limiter | defaults 10 rps/burst 30; plan+reroute 2/6; trip+observe+report 1/5; **admin login 0.2/5** (live-probed → 429); `/health` exempt | `middleware.py` + e2e report |
| plan demo OD (IG→HCC ~24.7 km) | **21 options**: car-AC **10.5–12.3** / walk **367–375** → **~33×** mid; **metro+walk 38.5 PRESENT**; `took_ms ~7,100` fresh | sanctioned `POST /v2/plan` ~14:07 UTC |
| plan verify OD (CP→GG) | 21 opts: car ~9.1–11.4 / walk ~303–332 → **33.3×** (slowest/best 36.5×); metro+walk **39.2**; `took_ms ~8,360` fresh | `verify_numbers.sh` |
| depart verify OD (auto) | now **25.0** → best **16.2 @ +20 h** (Oct-8 10:00) → worst **50.3 @ +23 h**; `pct_less_vs_now` **35** → remind row shows | `/v2/depart` |
| outlook @CP | today Satisfactory 58.1 → Thu **Moderate 86.6** (clean 14:30–18:30 @39; heavy 19:30–23:30) → Fri **Very Poor 168.4** → Sat **Very Poor 130.2** → Sun **Very Poor 137.9** | `/v2/outlook` |
| latencies | GETs ~0.3–0.6 s; `/v2/skill` re-hit **0.55 s** wall; plan fresh-OD `took_ms` ~7.1–8.9 s; warm ~50–660 ms | curl + wire |
| spend | **net $0.00 last 7 d** (promo credits; ~$1.65/day gross ≈ $50/mo run-rate); $50 budget armed | `ops-handover.md` §4 |
| task shape | 1 task × 1 vCPU / 3 GB (API ≈2 GB after OSRM sidecar); **~8–15 concurrent** honest posture | `deploy.sh` + `lowram-report.md` |
| builds | prod **`ffddab93`** == ECR tag == deploy-5; HEAD `7c68c8b` ahead by `af653e5` (F1 fix — the only server diff) + docs | `/health.build_sha` + git |
| ops | deploy.sh ran live ×4 today (2×`1627a13f`, `c86074ff`, `ffddab93`); 3 alarms OK → SNS confirmed; rollback `deploy.sh rollback <sha>` | `ops-handover.md` + deploy reports |
| iOS crash | Release **0/60** (Wilson ≲6%); dev-debug 14/30 — victim `consoleTaskRun` (inspector-only); device build unmeasured | `ios-release-residual-report.md` |
| Android crash | **0** FATAL/ANR/SIGSEGV across every recorded drive (rehearsal-v2, apk-v10 KVM, notify-e2e) | lane oracles |
| offline pack | r1 dead (file:// style_url, 0 tiles) → r2 fixed: `GET /v2-light.json` **live on prod** (200, 94,254 B byte-identical); iOS sim `region_tiles=744`+297; needs APK cut ≥`54a296e` | `offline-pack-fix-report.md` |
| offline fallback | 160 MB ambient cache + T-45 pre-warm pan (8/8 air-gap honesty pass) | `testday-offline-report.md` + `demo-morning.md` |
| landing | v7 live: hero = shipped app's real home (srcset 472w/708w webp), chooser film-strip = 3 real frames; page ≤206 KB all-in | `/` live + `landing-v7-report.md` |
| privacy | gated wires carry **zero identity fields**; k≥3 firing live (43/55 suppressed, hours dark, 1 OD suppressed, review notes withheld); installs `null`+reason; F1 fixed `af653e5` (deploy pending) | `privacy-spine` + `privacy-f1-fix` reports |

---

## Attacks that fail — quick reference

| accusation | why it fails — proof pointer |
|---|---|
| "It's dressed-up nearest-neighbor" | `GET /aqi` → kriging on, `nearest_sample_km:1.8` echoed; `airfield.py` krige posterior; IDW is a *documented* fallback |
| "The ±band is decorative" | `SIGMA_CAL=3.2` vs measured coverage (95.4%, 3,550 pairs live); `sigma()`→`None` outside coverage; live dose bands on every option (car-AC `3.4–14.9` today) |
| "The spread is fabricated" | re-derived live: ~33× today (car-AC 10.5–12.3 vs walk 367–375); a cooked number doesn't drift with the field |
| "1.07M edges is a slide number" | `/health.routing.edges` 1,070,459 / `edges_priced` 903,058 live |
| "The C++ engine is vaporware" | `/health.engine` = `alive_core`; `test_parity_dose.py` bit-for-bit |
| "The archive is fake/staged" | `/v2/archive` recorded [1,3–19] gaps {0,2} — records only the served field, never back-fills |
| "The community layer is seeded" | `community-sanity-report.md`: exact page↔store reconciliation, dictionary-attacked device hashes → 0 test ids, 0 non-Delhi geometry, 0 seed writes; k≥3 visibly suppressing real rows |
| "Aggregates still leak a person" | `privacy-spine-report.md`: zero identity fields on any wire; k≥3 caught firing in 4 places live; installs honestly `null`; F1 found+fixed `af653e5` |
| "Hindi is a veneer" | `strings.ts` `hi` mirror compiler-enforced; hi-parity lane reports |
| "You hid the cold start" | `docs/plan/cold-path.md` + T-40 warm task + demo-morning runbook in writing before any judge asked |
| "Security is a claim, not a test" | pentest 2 HIGHs found+fixed; HMAC cookie sign-in **proven e2e on prod** (login chain, gate probes, browser board render) — `admin-login-e2e-report.md` |
| "It falls over under a demo load" | `lowram-report.md`: ~0.95 GB vs ~2 GB, RSS delta 0; honest ~8–15 concurrent; skill tail 5.2 s→0.7 s fixed live |
| "The app crashes on cold open" | Release **0/60** cold cycles (victim class inspector-only); Android 0-crash across all recorded drives — `ios-release-residual-report.md` |
| "The route paint isn't the field" | `demo-exchange-max.md`: 12/12 segment midpoints within ±5% of `/aqi` |
| "The map is empty / offline is vaporware" | `map-depth-report.md` (mesh z12+, device shots); `offline-walk`→`offline-pack-fix`: broken pack found by our own walk, fixed, `region_tiles=744` on-device, route live on prod |
| "It just asserts the best route" | `route-chooser-report.md` + rehearsal-v2: candidates→pill→bold plays; pill holds ~4.2 s ×2 ("cleanest and fastest" → "cleanest · 51% less than fastest"); first-run wizard eats the beat once — pre-warm the demo OD |
| "Nobody would notice a regression" | `visual-thread-report.md` + `script-guard-report.md`: dead-landing P0 caught mid-drive, fixed within the hour, bug class is now a CI gate |
| "Half the code is stubs/dead UI" | `codebase-server-report.md` + `codebase-mobile-report.md`: census, zero stubs/fakes, 3 dead switches wired, findings filed; `/v2/feedback` live; full suite 1,244 green |
| "Nobody's watching prod / who's paying" | `ops-handover.md`: 3 alarms OK + SNS confirmed + budget armed + **$0.00 net/7d**; deploy.sh ran live ×4 today; watchdog 9 clean cycles |
| "Notifications are fake" | `notify-e2e-report.md`: real banners **both platforms** — iOS dev-client + release APK incl. real permission dialogs, in-place revision re-post, verbatim dedupe marks; the +8-belt-jump correctly did NOT fire |
| "Demo day will be clean anyway" | `/v2/outlook` live: Fri–Sun Very Poor 168/130/138; tomorrow Moderate 87 with a real clean-window + `pct_less 35` depart payoff on the wire |

---

## Re-verify morning-of (numbers that moved today alone)

- `/community`: **44 / 24 / 5** — "forty-something dev donations",
  newest ~7 h old.
- `/v2/skill` h+11 band_hit: **36.1% now** (36.2% at v5, 33.0% before —
  drifts hourly; re-read at T-45). Pairs 330.
- `stations.count`: **54** (band 52–54; 24 in a DPCC stall).
- City air drifted again: mean **47.2** (43.1 at v5, 55.6 this
  morning); `/v2/why` primary flipped trend→**stagnation** (VC 467 vs
  ~3,000 — barely mixing); CP pm25 **62.3**, us_aqi **152**.
- Fires: **90 total / 16 belt / 41.4 MW / ×1.08** (was 44/12/26.2/×1.06)
  — `carrying:false` now, was true midday; keep both wordings.
- **Outlook re-pinned — v5's line is dead**: tomorrow Moderate 86.6
  (was Poor 107); Fri 168 / Sat 130 / Sun 138 Very Poor;
  `confidence:"lo"` past the anchor; re-read at T-45.
- **Depart armed**: `pct_less_vs_now` **35** (was 8) — row shows;
  tomorrow 10:00 is the payoff. Check at T-45.
- **Metro row PRESENT** (38.5 demo OD / 39.2 verify OD) — "car beats
  metro ~4×" armed; GTFS-hours dependent, re-check at T-45.
- `/aqi.calibration`: rebuilt **8.8/n=70** still on the wire —
  `/health.build_sha` vs HEAD before quoting (prod `ffddab93`; HEAD
  `7c68c8b` ahead by the F1 fix + docs only).
- `/v2/feedback` lore: **LIVE**, POST→200. Kill any stale "410" line.
- `/v2/usage` guest 401 → `admin sign-in required` — the gate is the
  cookie auth; playbook `docs/plan/admin-login.md` (Save-password →
  Never; hotspot on demo Wi-Fi).
- **Offline**: prod route `/v2-light.json` live (200, 94,254 B); the
  demo phone's pack path is ambient cache + T-45 pan unless a fresh
  APK ≥`54a296e` is cut and warmed on good Wi-Fi before doors.
- **iOS**: demo vehicle = the **Release** binary (60/60); never the
  dev-client (~47% cold residual, inspector-victim only).
- Demo build: rehearsal APK `c3f7e9e` / v10 `70914c0` run clean;
  pre-warm the demo OD once (first-plan vehicle wizard eats the
  chooser beat), film→notif→onboarding→location order is rehearsed.
- Freeze rule: no deploys inside the demo window; last image by T-60;
  `build_sha` check at T-45.
