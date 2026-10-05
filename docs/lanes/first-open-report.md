# first-open lane — report

Cold-install audit of Mobile/ on iOS Simulator (Release-iphonesimulator build;
Android emulator is impossible on the macOS box — no nested HVF). Live backend
at 65.2.28.40, read-only boot GETs only. Commits: `33112f4` (fix) + `8f45203`
(tooling). Code: `Mobile/App.tsx` only.

## Timing — before vs after (icon tap → …)

| stage | before (`a3abb61` parent) | after (`33112f4`) | after @ ~1 Mbps |
|---|---|---|---|
| splash/native paint | ~+0.5 s | ~+0.5 s | ~+0.5 s |
| first readable content | hero painted but **invisible** — opaque onboarding sheet + OS location dialog covered it from ~+0.9 s | ~+2.5 s hero + search pill | ~+2.5 s |
| first REAL number | ≥ +10–15 s (requires dismissing dialog, then 3-page sheet; unattended: never) | **~+2.8–3.0 s** — "outside now ~66 µg/m³" chip + Move card | **~+3.0 s** |
| consent sheet | mounted at first paint (~+0.9 s) | slides in ~+6.2 s — still required | ~+7 s |
| location permission dialog | at boot, before any content — a data-grab with zero context | after consent is answered (returning users: at boot, unchanged) | same |

Fetched `/aqi` was in-hand at +2.4 s before AND after — the wall was never the
fetch, it was what the user could *see*.

## Walls found

1. **Location permission ask at boot.** `requestForegroundPermissionsAsync` ran
   in the boot effect — the OS dialog landed on top of the first paint, ahead of
   consent and of any value. → Moved into an `introSeen`-gated effect: fires at
   boot for returning users, fires right after the consent answer on cold
   installs. Verified driven: consent → dialog → "Allow While Using App" →
   positioned read.
2. **Consent sheet gated everything.** `OnboardingScreen` mounted at first paint
   (`visible={introSeen === false}`) — required, yes, but it needn't block the
   first value. → `gateReady` gate: sheet shows 4 s after `ambientUg` lands
   (9 s fallback if the field can't answer — honest, not a dead screen). Consent
   semantics untouched: same 3 pages, same donation ask, same `settings.share`
   write; no POST can fire in the gap (trip posts only on arrival).
3. **Boot `/aqi` read waited on GPS it couldn't have.** `aqiPoll` burnt a real
   `getCurrentPositionAsync` even with no permission — a needless stall on cold
   installs. → boot call passes `freshGps=false`: samples the Delhi centroid
   (city-wide field anyway) immediately; once the post-consent fix lands,
   `aqiPollRef` re-reads positioned without waiting out the 60 s poll.
   Verified: cold daylog gets a centroid sample at ~+2.3 s; after permission,
   a positioned sample (sim set to 28.7041,77.1125 → `amb 75.8` ≠ centroid 66.1 —
   the field varies, the upgrade is real).

## What still honestly blocks first value

- The dosimeter hero itself stays `—` / "still sparse" until the daylog has
  enough samples (thin-daylog honesty kept deliberately). First value today =
  the ambient chip + Move card + week strip, all real.
- First-number time is RTT-bound: three boot GETs ≈ 450 ms each; ~1 Mbps moved
  nothing (total boot payload ~12 KB). On truly dead networks the sheet still
  arrives at +9 s over visible-but-sparse chrome — no dead screen either way.
- Sim artifact, watch it on device: after the consent grant the app died once —
  signature consistent with the documented iOS-sim render-thread crash class
  around camera/position commits (`camDur` already zeroes transitions on sim;
  the death was getCurrentPosition/flyTo-adjacent). The same code path ran clean
  on relaunch and produced the positioned read, so likely a sim flake, but
  worth one cold-install check on real hardware.

## Recordings

`/tmp/cold_runs/` on this box — `baseline_direct` (before), `fixed_direct2`
(after), `fixed_throttled` (~1 Mbps), `driven_consent` (consent → dialog →
grant), `probe` (debug-overlay run proving `amb=66.1` visible under
`gate=false` then `gate=true` sheet).
