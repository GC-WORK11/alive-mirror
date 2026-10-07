# fix-demo-script — unit-bug verification + stage-script wording pins

Lane: `fix-demo-script` · pass **2026-10-07 ~05:15–06:10 UTC**.
Findings source: `docs/lanes/demo-rehearsal-report.md` (§4 drift log,
§7 fix list). Scope per dispatch: **A** verify the shipped
`ug_saved_vs_now` unit fix end-to-end (commit `0c9ba5a` landed it
before this lane pulled — do not re-implement); **B** exact-edit the
script wording debts in `docs/plan/demo-script.md`,
`docs/11-demo-script.md`, `docs/demo-day.md`. Prod probe discipline:
GETs + sanctioned `POST /v2/plan` only.

- **Live service at verify time:** build **`a1dca1ec`**, NLB HTTP :80.
  Stations **51** (waqi+dpcc), transit real_feeds metro+bus `true`,
  fires **44** (12 in-belt, 26.2 MW), wind easterly → smoke modifier
  **1.06, `carrying:false`, fires REFUSED**; stagnation primary
  (VC ~1,683 m²/s). `next_hours` pm2.5 69.4 → 95.7 (~38% swing).

---

## A. `ug_saved_vs_now` unit bug — verified fixed, residuals closed

**Wire contract (producer side, `server/main.py` /depart):**
`saved = round(100 * (1 - best["dose_ug"] / now_slot["dose_ug"]))` —
a **percent**, served under both `pct_less_vs_now` (honest key) and
`ug_saved_vs_now` (legacy alias for the same value) — `:1018`,
`:1030–1031`. No µg field exists on the wire for this quantity.
`tests/test_honesty_polish.py::test_depart_percent_key_is_honestly_named`
already pins both keys equal and 0–100.

**The shipped bug** (rehearsal §4): `useShellFlow.remind` read the
percent as µg and recomputed a percent off it → scheduled notification
over-claimed ~2.5× (true 13% → ~32% shown).

**`0c9ba5a` verification (not re-implemented):**
- `remind` now takes `pct_less_vs_now ?? ug_saved_vs_now` verbatim —
  matches the server contract exactly. Correct.
- `pct_less_vs_now` added to `DepartCurve` + mapped in `mapDepart`,
  and to the shell's narrower `Depart` shape (`types.ts`). Complete.
- **Residual wrong-unit use found and closed in this lane:**
  `CompareSheet.tsx`'s leave-later row still read
  `depart.ug_saved_vs_now` raw for both the `>8` gate and the rendered
  `n`. Now both consumers go through one helper.

**This lane's delta on top of `0c9ba5a`:**
- `Mobile/src/api/depart.ts` — new exported pure helper
  `departSavedPct(d) = d?.pct_less_vs_now ?? d?.ug_saved_vs_now ?? null`
  with a comment carrying the contract (works on `DepartCurve` and the
  shell `Depart`).
- `useShellFlow.remind` — routes through `departSavedPct` (same math,
  single point of truth).
- `CompareSheet.tsx` — `departSaved = departSavedPct(depart)`; row gate
  `depart && departSaved != null && departSaved > 8`; render
  `Math.round(departSaved)`. Behavior identical for today's wire;
  legacy-alias reads now documented as percent, not µg.
- **`Mobile/src/api/depart.test.ts` (new, 4 tests)** — pins the
  verbatim-percent read: served 13 → 13 (not ~33), `ug_saved_vs_now`
  alias alone → 13, `pct_less_vs_now` wins when both present (8 vs 13),
  null → null. Also mirrors the remind copy's
  `Math.max(0, Math.round(departSavedPct(d) ?? 0))` so the scheduled
  notification's math is covered.

## B. Script wording pins

**`docs/plan/demo-script.md`:**
- **Beat 3** re-pinned to the OD that actually serves a metro+walk row:
  India Gate → **Huda City Centre metro station** (the string the judge
  flow types resolves there; the old CP→Gurugram script OD serves no
  metro row). Verbatim line and verified-numbers column rewritten to
  today's `a1dca1ec` reads: **23 options**, car-AC **10.3**, car-open
  18.6, bike 24.5, bus 26.9, auto 31.6, **metro+walk 67.0**, cycle
  ~152–173, walk **353.4** → **~34×**. CP→GGN kept as cold backup
  (11.4 / 418.2 → 36.7×, no metro row).
- **Beat 4** re-worded true to the app's real surface: the curve is
  **24 h**, not 4-day — the old "5× / ~113" claim cannot appear on it.
  New line quotes the live 24 h reads (now 9.6 → best 9.1 @+6 h →
  worst 16.2 @+23 h ≈ **1.7×**) and moves the ~4× claim to the verbal
  `hours=120` window (best 7.9 @+51 h, spike 38.4 @+58 h). The
  leave-later row is **absent today** (served pct 5 < the >8 gate) —
  column notes the gate so the operator doesn't promise a row that
  isn't there.
- Numbers sheet: routing line, µg/km ladder (÷24.7 km), "honest
  surprise" (~6.5× = 67.0 vs 10.3 + GTFS-hours caveat), and the
  do-not-say metro line all re-pinned to the demo OD.

**`docs/11-demo-script.md` (film):**
- Header `depart −N%` now explicit that −83% was that day's read;
  −13% at the Oct-7 rehearsal, −5%/row-absent later — always day-read.
- 2:05–2:35 beat re-worded: read "leave HH:MM — same trip, N% less
  PM2.5" off the row **on recording day**; the row exists only when
  `pct_less_vs_now` > 8, else fall back to narrating the DepartGraph
  24 h dip → overnight climb. "hourly five days out" → "hourly about
  four days out" (104 slots at hours=120).

**`docs/demo-day.md`:**
- "The judge's first 90 seconds": inserted **before** the ~30–90 s
  taps — **iOS rule: app open ≥90 s BEFORE the first search-sheet
  tap** (cold launch → "Where to?" inside ~10–90 s is the verified
  mount-vs-draw SIGSEGV window on iOS; Android-proven safe, but never
  hand over a cold-launched iOS build — let consent/hero beats eat
  the window).
- **T-45 drift checklist** now covers the rehearsal's full list:
  ladder re-based to demo OD (~10–11 car-AC / ~330–420 walk,
  "about ten vs three-fifty"); **US AQI at CP — drifts inside
  'Unhealthy': 152–157** (new item + curl); fires line → 44 total /
  12 in-belt / 26.2 MW, carrying NW-gated, easterly/southerly REFUSED;
  options count 23 on demo OD with metro+walk present (absent CP→GGN);
  why-line → stagnation quote + VC ~1,683 m²/s; stations/samples
  accepted band **51–54**; community → 40 obs / **22 contributors** /
  **1,028.5 µg** avoided all-time (24 h: 8.0 km / 62.5 µg).

## Gates

- `Mobile`: `npx tsc --noEmit` clean · `npx expo lint` clean · api
  runner **12/12** (incl. 4 new `depart.test.ts`) · store runner
  **76/76**. nav `counters.test.ts` ×2 + offline `queue.test.ts` ×3
  fail identically on clean base/v2 (verified stash→run→pop) —
  pre-existing, untouched here.
- `server`: fresh-box bootstrap (`.venv312` + `pip install -r
  requirements.txt pytest`; `alive_core` C++ ext not built —
  `core/alive_core_ref.py` fallback covers it) →
  `pytest -q tests/test_honesty_polish.py` **3/3 pass** (the depart
  percent contract test).
