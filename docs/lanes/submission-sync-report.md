# Lane report — submission-sync (docs to today's truth)

**When:** 2026-10-07 ~10:45–11:25 UTC (~16:15–16:55 IST) · **Build:** `698cf808` live (`/health` `build_sha` == image `alive108-api:698cf808`) · **Lane:** docs-sync pass — every judge-facing number re-derived from the wire this pass; no seeded or memorized figures carried forward.

## What landed since the docs' last pin (`4eb9e1e8` / `a1dca1ec`)

Route chooser `e2ff634` (candidates draw as equals → camera unions bounds → winner settles bold ~1.4–1.7 s → verdict pill pins `chooserVerdict`/`reason_line` at `pointAtFrac(geometry,0.45)`, hold 4.2 s) · admin auth `b563da2` (`POST /v2/admin/login` → `alive_admin=v1.<exp>.<sig>` HMAC-signed HttpOnly+SameSite=Strict cookie, ~8 h; guests land on a gate card; sessionStorage token + `prompt()` deleted; Bearer kept for ops) · `cause_note` `795ff3b`+`1c062c3` (measured-fields-only parali-watch line on `/v2/why` + `/v2/city.why` + city.html tile, en/hi) · map depth `b47ffd4` (v2-light + 744 NCR tiles z9–13 / 27.4 MB) · iOS residual kill `9fbd851` (Promise JS-thread hop, 12/30→0/30 drive-bys) · codebase-truth `1627a13`/`b633a2d` · landing v6 `666c4c8` · release package `c3f7e9e` · deploy.sh verified ×2.

## Live reads this pass (all `698cf808`, ~10:45–11:25 UTC)

- `/health`: edges 1,070,459 / priced 903,058 · stations **52** (waqi+dpcc ok, band 52–54) · model ~**97** samples · fires **44** (12 belt / 26.2 MW / ×1.06 SW-refused) · wind 9.9 km/h @241° · climatology 125 · transit real_feeds metro+bus · `engine: alive_core` · field age ~7 min.
- `/aqi` @CP: pm2.5 **64.5** bz / **60.8** ambient · US AQI **154** · LOO 8.8/12.7/70/+0.2.
- `/v2/city`: mean **43.2** / max 55.0 · −24.0% vs Oct median 56.9 · GRAP 0 / aqi 73 · breath **620 µg ≈1.96 cig** · next_hours 60.8→78.2 · `why.cause_note` live (nested, not top-level): *"12 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now · city mean 60.6 → 46.8 µg/m³ over 5.8 h"*.
- `/v2/why`: **trend primary** (−13.7 µg/5.8 h, 33 builds) · VC ~3,468 · fires refused.
- `/v2/day` @CP: mean 67.5 · both windows honestly `null` (61–75 flat) · `decisions` row present.
- `/v2/outlook` @CP: Moderate 67.5 → Poor 107.2 → VP 176.9 / 134.1 / 136.8 (Oct-8…11).
- `/community`: **44 obs · 24 contributors · 31.4 km today · avoided 1,278.9 all-time / 312.9 today**.
- `/v2/city/moves`: 44 trips · **12 of 55 corridors publishable** · min_k 3.
- `/v2/skill`: **304 pairs** · h+0 MAE 3.8/90.2% → h+11 37.2/37.7%.
- `/v2/reach`: walk@25 **3,767/167.9 km** · walk@50 11,409/618.0 · car@25 993,344/92,805.9 `edge_partial`.
- `/v2/archive` today: recorded [1,3–16] · gaps {0,2} · pending 17–23.
- `/depart` demo OD IG→HCC (24 h): now **20.7** → worst **45.2 @+19 h** (~2.2×) · dip 17.3 @+23 h · `pct_less_vs_now` **16** (row present; script OD read 0/absent).
- `/v2/plan` demo OD IG→HCC: cold hit 9 opts + `degraded:["engine"]` (9.2 s) → warm **16 opts, ~1.2 s**; car-AC **7.4** / car_open 13.5 / bike 17.7 / bus 19.4 / auto 22.8 / **metro+walk 53.2** / cycle ~113 / **walk 255.0 → ~34.5×**.
- `/v2/plan` script OD CP→GG: **17–18 opts**; car-AC **7.2→8.6** / **walk 237.9→284.6 → ~33×** (field refreshed mid-pass — both reads recorded, spread stable).
- `/v2/plan` video OD KG→IG: **24 opts, 4.0 s**; car 3.8 / open 6.9 / bike 8.1 / bus 9.9 / auto 11.2 / bus966 24.8 / metro+walk 43.4 / cycle 51.9 / walk 117.1 → ~30.8×.
- `/v2/admin/session` (GET): `{"authenticated":false}` · `/v2/usage` guest → 401 · `/admin` HTML public (gate card inside).
- `/grid` pm2.5↔nitrogen_dioxide corr (484 cells): **r=+0.14** today (was +0.55/+0.47/+0.34 — drifts).

## Files touched + staleness fixed

| file | edits | what was stale → now |
|---|---|---|
| `docs/submission/writeup.md` | ~18 | header pin `1627a13f`→`698cf808` + today's landings named; stations 54→52/~97; community 22/14/725.9→44/24/1,278.9; `/v2/day` windows → both-null honest read; reach 4,103/182.5→3,767/167.9; dose table → 17-opt read (car 7.2 … walk 237.9, 33.0×, ×1.06); depart → ~20→46; skill 210→304; EventBridge honest UTC-misnamed; CloudWatch→3 armed alarms; cost ~$46/mo→**$0.00 net/7d**; **new "Security & reliability" section** (admin sign-in, pentest caveat, iOS 0/30, P0 script-guard `326e64e`→`f9ea5ae`, codebase-truth, deploy ×2); design beat → chooser + parali tile + gate card |
| `docs/submission/repo-readme.md` | ~11 | dose para → chooser + 17 opts + ×1.06 + `698cf808`; dose table re-pinned; day mean ~105→~68; reach re-pinned; field 54→52; cause_note sentence added; arch diagram `24 WAQI + 30 DPCC`→`WAQI + DPCC (52 live today)`; cost → $0.00/7d |
| `docs/builder-center/article-draft.md` | 6 | stations 54→52, samples →~97, dose ~10/~340→~7.2/~238 ~33×, corridors 54→55, Secrets bullet → HMAC-cookie line, EventBridge UTC-misnamed + ops-handover ref, CloudWatch 3 alarms + $0.00 |
| `docs/submission/ai-disclosure.md` | 1 | Devin trailer count 651/658 → **1,077 / 1,084** (`git log --format=%b`) |
| `docs/submission/submission-checklist.md` | 5 | status header → Oct-7 `698cf808` + flood list; stations ≥40(54)→**52–54**; T-45 build → `698cf808`; T-30 admin → gate-card/`POST /v2/admin/login` flow; T-20 APK caveat → `70914c0` is **40 commits behind HEAD** (no chooser/cause_note/iOS-kill/map-depth/dead-switch) — rebuild required |
| `docs/submission/video-shotlist.md` | ~20 | header `698cf808`; beat 3 → let chooser play + new ladder (~7/~21/~105/~238, 33.0×, metro 32.5 ~4.5×); beat 4 → reach/corridors/breath ~620 µg + why-beat rewritten for `cause_note` (fires refused today) + parali tile; beat 5 → **sign in before rolling** (gate card → HttpOnly ~8 h), 52 instruments/~97, fires 44/12, archive [1,3–16]/{0,2}, skill 304 pairs; full drift-table re-pin |
| `README.md` | 9 | `/admin` note → gate card + `POST /v2/admin/login`; "What it is" → chooser sentence + cause_note sentence; demo-OD ~9/~310→~7.4/~255 (~34.5×); stations 53→52 (band 51–54→52–54) ×2 places; donations ~40→44/24; phase-4 row → iOS residual killed 0/30 (`9fbd851`) + phase-5 row → chooser/cause_note/admin; `~185` lane reports → ~200 |
| `docs/plan/demo-script.md` (stage ≤3:00) | ~16 | new dated re-pin block (`698cf808`, ships listed, fires→refused, admin gate warning); beat 2 → 52 instruments/44 fires/154/64.5/60.8/×1.06; **beat 3 → chooser folded into the FROM→TO moment** (animation description + verbatim "watch them draw as equals before the winner settles and names why") + demo-OD re-pin (16 opts, 7.4/255/34.5×, metro 53.2/~7.2×, cold-hit degraded honest note); beat 4 → demo-OD depart read (20.7→45.2 @+19h, −16% row present); beat 5 → 24 contributors/31.4 km/1,278.9 + gate card; beat 6 → `698cf808` + $0.00/7d; beat 7 → r=+0.14; numbers sheet fully re-pinned (+outlook +admin sign-in rows); do-not-say updated (metro 7.2×, 238/255, fires→cause_note, `/admin` gating) |
| `docs/11-demo-script.md` (3-min video) | 6 | header re-pin `698cf808` KG→IG 24 opts; **0:18–0:45 → chooser animation folded in** before the dose-coloured reveal; dose table re-pinned (3.8…117.1, ~31×); voiceover → 52 anchors/~97 samples + cause_note; depart row → 16% demo/0 script today; AWS beat → build_sha `698cf808` + admin-token→HMAC-cookie |
| `docs/demo-day.md` | ~14 | header → "Last verified 2026-10-07 `698cf808`" + ships-named block (Oct-6 "public board" flagged as history); body: dose example 4eb9e1e8→698cf808 (~7.2/~238), stations 54→52 ×3, fires 67/×1.08→44/×1.06-refused, why beat → trend+cause_note, judge-flow ~10/~355→~7.4/~255+chooser note, `/admin` flow → **gate card + sign-in** rewrite, task-def `:181`→"read off console"; T-45 pins: spread 33.3/35.9→**33.0/34.5**, ladder 10.3/353→7.4/255, AQI 152–157→154, day 71–82/~76→61–75/~67.5, fires build →698cf808, archive 21→[1,3–16]/{0,2}, options →16 warm/degraded-cold + **metro+walk present on BOTH ODs today**, build_sha →698cf808, skill 131→304, why → trend+cause_note, stations 51–54→52–54/~97, community 40/22/1,028.5→44/24/1,278.9, reach →3,767/167.9; iOS addendum → **RESOLVED `9fbd851` 0/30** |
| `docs/plan/judges-faq.md` | 12 | skill 21-pair block → 304 pairs (h+0 3.8/90.2% → h+11 37.2/37.7%); health block 54/67→52/44/~97; moves 54→55 corridors; §10 retitle 22→44 trips + 24/1,278.9; archive prose → today's pattern; nearest-sample pin de-dated; skill-h example → 304; re-derive table fully re-pinned (+cause_note +admin rows); dose-ladder worked output → today's mids (8.6/284.6 → 33.1×); worked decomposition → 2.36×10.0×1.4 ≈ 33× closes; walk band → 284.6 (0–931.3) |
| `docs/plan/go-nogo.md` | 5 | header → re-pinned `698cf808`; row 3 build truth → `698cf808`/ECR; row 4 stations 54→52 band 52–54; row 9 APK → **`70914c0` v10 but ~40 commits behind HEAD — rebuild required**; cold-window wart 54→52/band |
| `docs/17-submission-writeup.md` | 1 | "wind-advected IDW" → kriged C++ + fitted nowcast blend (superseded draft; canonical = submission/writeup.md) |
| `docs/19-submission-checklist.md` | 2 | "54 instruments" → 52/band; `/admin` link → "(sign-in gate since Oct-7)" |

**Total: 12 files, ~120 stale lines/blocks corrected.**

## Residual stale surfaces (deliberately left)

- Dated drift-note history inside `docs/demo-day.md` / `docs/plan/demo-script.md` rehearsal logs — kept as history by the docs' own convention.
- Lane reports under `docs/lanes/*` — evidence-pointers stamped on their own builds by design.
- `docs/plan/handoff.md` chain (cont.N notes) — dated ledger, not judge-facing prose.
- APK `70914c0` binaries remain behind HEAD — flagged in checklist/go-nogo, not fixable here.

## Re-verification commands (for the next sync pass)

```bash
NLB=http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
curl -s $NLB/health | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["build_sha"],d["sources"]["stations"],d["sources"]["fires"],d["sources"]["model"])'
curl -s $NLB/community | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["obs_total"],d["contributors"],d["avoided_ug_all"])'
curl -s $NLB/v2/why | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("cause_note"),d["drivers"][0])'
bash scripts/verify_numbers.sh   # zero-flag gate on the pinned numbers
```
