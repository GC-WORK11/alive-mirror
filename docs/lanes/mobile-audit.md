# Lane — Mobile app audit (Mobile/, Expo SDK ~57 / RN 0.86)

Auditor: read-only pass over the entire `Mobile/src` tree (~21.8k LOC, 70
files incl. tests). Gates re-run this session: `tsc --noEmit` clean,
`expo lint` clean, `node src/store/test-runner.mjs` 18/18,
`node src/nav/test-runner.mjs` 70/70. Live wire verified by GET-only
calls to prod (2026-10-07 ~00:20 UTC).

## Verdict

**No fakes found.** Every headline number on every screen traces to a real
API field or honest on-device computation; every degrade path renders
honestly (hidden cards, "—", sparse labels, frozen counters) instead of
synthesizing. The privacy spine holds: timeline/dose never leaves the
device except through the consented, client-trimmed `/v2/trip` donation
path — with one narrow resurrect-after-wipe edge below. No Modal
anywhere; every MapLibre source follows the always-mounted EMPTY-FC
guard. **The worst thing in this tree is not a fake — it's a documented
opt-out consent flow and a residual iOS crash class the code guards
can't fully prove closed.**

## Findings

| sev | tag | finding | evidence | why a judge/user cares |
|---|---|---|---|---|
| MED | BUG | **Outbox resurrect-after-wipe.** A trip donation whose POST fails *after* `clearAllData`/`clearOutbox` ran re-creates `outbox.json` and auto-flushes on the next `up` event — a consented trajectory can leave the device after "delete my data". The cache layer solved this exact class with a generation counter; the outbox never got it. | `engine.ts:288-294` (fail → `enqueueTripDonation`), `offline/queue.ts:93-108` (enqueue writes unconditionally) vs `queue.ts:210-215` (clearOutbox) — no generation check; compare `api/cache.ts:93-103` (`cacheGeneration`/`wipeGen` guard) | Privacy is the spine; "delete my data" must be total. Window is narrow (donate-fail → delete → enqueue within seconds) but the promise is absolute. |
| MED | JUDGE-RISK | **Skip→sharing-on, disclosure doesn't travel.** The persistent top-right Skip is on all 3 onboarding pages and calls `finish("on")` — but the `consent_footnote` ("skipping counts as sharing on — either way, one tap in Settings undoes it") renders only on page 2. A page-0/1 skipper consents to donation without ever seeing the choice. | `OnboardingScreen.tsx:175` (`const skip = () => finish("on")`), `:201-212` (persistent skip), `:376-378` (footnote inside `step === 2`); doc 07 §3 documented default | Deliberate opt-out, mitigated by Settings one-tap undo + receipt provenance (`nav_donated`/`nav_queued`/`nav_private`) — but a privacy-skeptical judge taps Skip first and lands on a map already set to donate. |
| MED | JUDGE-RISK | **iOS SIGSEGV class not conclusively closed.** Every code-level guard is present and internally consistent (below), but ios-journey-overnight observed a residual SIGSEGV(11) on search-sheet open (1/2 attempts) — the same class the search-crash lane fixed in d791879. | `docs/lanes/ios-journey-overnight-report.md:5,21-50`; guards verified at `HazardLayers.tsx:18,56`, `CorridorLayer.tsx:31`, `RouteTint.tsx:78,90`, `ReportsLayer.tsx` (REPORT_POOL=40, never unmounted), `ui.tsx:163-194` (JS-driver sheet graph, `useNativeDriver:false`), `map/cam.ts:11-13` (camDur=0), `App.tsx:720` (80ms deferred re-plan) | A crash on the judge's literal first poke (open search) is the worst possible demo-day failure. All live mount patterns follow the documented guard — residual suspect space is prop-swap/timing inside MapLibre, not unmount races. Needs the verify lane, not more code review. |
| LOW | BUG (i18n) | **Nav banner distance hardcodes `" m"`.** Under 950m the turn banner prints `"350 m"` in both languages; `unitsM: "मी"` exists and the km branch uses `unitsKm` correctly — the m branch forgot it. | `NavChrome.tsx:63` (`\`${Math.max(10, Math.round(m/10)*10)} m\``) vs `strings.ts:934-935` | Visible script mixing on the flagship nav screen in Hindi mode — exactly the leak class the i18n law bans. |
| LOW | BUG (i18n) | **T0 search subtitles are English-only.** `kindLabel` returns hardcoded English category labels ("school", "hospital", "metro entrance") that render as result-row subtitles regardless of `lang`. | `search/t0.ts:273-329` (`SUFFIX_LABELS`, `kindLabel`) → `SearchScreen.tsx:358,476` (`subtitle={p.subtitle}`) | Hindi user offline (or hitting a gazetteer-only kind) sees English labels beside Devanagari names — script mixing. Narrow reach (T0 tier only) but real. |
| LOW | BUG (i18n) | **Share-trip CO₂ line double-units.** `t("nav_kg", {n:"~1.2"})` already yields "1.2 किग्रा"/"1.2 kg", then the code appends a literal ` CO₂` → Hindi share text reads "~1.2 किग्रा CO₂". | `App.tsx:704` vs `strings.ts:413-414,1019-1020` | The share card is the artifact a judge screenshots to WhatsApp — script mixing in the one string that leaves the phone. |
| LOW | BUG (i18n) | **WelcomeScreen bypasses t() with hardcoded English.** "live · the field here, this hour" / "live · field mean over the ncr lattice" / "nothing served — never faked" / "then — what you breathe" / "what delhi breathes". Component defaults `lang="en"`. Reachable in hi mode: delete-my-data wipes `welcomeSeen` but preserves `lang` (`App.tsx:552`), so a Hindi user who deletes data gets the English cinematic. | `WelcomeScreen.tsx:217-219,309,322,331`; `App.tsx:552` | First-launch impression + a real leak on the post-wipe path. Also the only English leak that fires on first open. |
| NIT | BUG (latent i18n) | `useNetStatus().label` hardcodes English pill text — currently dead (App renders `t("offline")`/`t("offlineStale")`/`t("offlinePending")` + `updatedMinAgo` properly), but the field ships in the hook's API. | `offline/status.ts:74-81` vs `App.tsx:854-858` | Any future consumer rendering `net.label` leaks English in hi mode. The string should die or take a lang param. |
| NIT | BUG (dead code) | `postTrip` exported, zero callers (engine.ts inlines donation via `postJson`); `FieldLayer` = 198 lines, zero imports (self-noted "kept for the city-view lane"); `Sidebar.tsx:463` `(onDelhiToday \|\| true)` always-true guard. | `api/trip.ts:30-57`, `components/FieldLayer.tsx`, `Sidebar.tsx:463` | Dead code invites fixes to the wrong place; the `\|\| true` hides intent. |
| NIT | BUG (stale comments) | Comments that contradict code: `OnboardingScreen.tsx:160` says "JS driver — same guard" but passes `useNativeDriver: true` (single-value opacity/translate — safe either way); `CompareSheet.tsx:335` promises "accentWash wash + accent edge" but `selFill` (820-823) is background-only. | file:line above | Auditors read comments as truth; the nav-crash comments are load-bearing documentation — they must not lie. |
| NIT | DESIGN-LAW | WelcomeScreen is a darkroom (`ROOM #0E1013`, light status bar, hairline corner brackets `HAIR`) against the light-theme law — a deliberate cinematic exception, and the only hairlines used decoratively in the app. | `WelcomeScreen.tsx:39,234,356-360` | Owner call: it's "different + smoother" vs "light theme" — flag for confirmation, not a fix. The darkroom metaphor is defensible; the hairline brackets are the only thing I'd question. |
| NIT | DOC | `Mobile/AGENTS.md` prescribes Expo Router + `src/app/` routes — the app is a single composition root (`App.tsx`, phase state machine `idle\|search\|compare\|nav`) with zero router. | `Mobile/AGENTS.md` vs `App.tsx`, `useShellFlow.ts` | Future lanes will hunt for a `src/app` that doesn't exist. |

## Clean bill — verified real, not vibes

**Numbers traced to wire** (live GETs, 2026-10-07 ~00:20 UTC, all real):
`/health` ok build ce01ec5c; `/aqi` pm25=59.5 ambient=55.1, lo/hi real,
field.source "waqi+dpcc-stations+open-meteo/cams", stale:false;
`/v2/city` pm25_stats.mean=57.1, breath.day_inhaled_ug {0/820/2058},
freshness {age_min:3,"live"}; `/v2/city/moves` n_trips=39 min_k=3
insufficient=false; `/v2/outlook` 5 real days; `/depart` real slots;
`/v2/day` real keys.

- **Home hero dose** — daylog.ts trapezoid-integrates real foreground
  `/aqi` samples (≤45min pairs, gaps honestly uncovered) + real trip
  doses; `thin = <3 samples && 0 trips` → sparse hero ("N of 3
  samples"), never padded. VE_REST_M3H=0.6 literate-sourced.
- **Every "live" counter** — counters.ts ME_VE per mode with citations,
  1Hz measured dt, strip nulls propagate; `stripOk=false` freezes
  counters rather than fabricating continuation.
- **Honest degrade everywhere** — CityMoves insufficient_data path +
  suppressed-count footnote + k≥3 stated; FreshnessChip tones keyed to
  real age_s (stale ≥30m); `planDegraded`/`refining`/`loadingRoute` all
  surface honestly; "—" for absent fields; `Nothing served — never
  faked` is literal code.
- **SIGSEGV mitigations** — zero `Modal` imports (all overlays are
  absolute-fill Views); every GeoJSONSource always-mounted with
  EMPTY-FC swaps; REPORT_POOL parked markers; JS-driver sheet graph;
  two-frame mounts + deferred camera commits. Consistent everywhere —
  see JUDGE-RISK #3 for the residual runtime question.
- **Egress closed** — only POSTs: `/v2/plan`, `/v2/reroute`, `/v2/trip`
  (consent-gated, TRAJ_TRIM_M=300/THIN_M=100/ROUND_DP=4 client-side,
  <600m → empty trajectory), `/v2/feedback` (user-initiated),
  DELETE `/v2/ledger`. contributorId = 64-bit CSPRNG rotated 30d
  (expo-crypto; Math.random only as emergency fallback). No analytics
  SDKs. Sample lat/lon used only for ~450m dedupe — never leaves.
- **i18n** — `updatedMinAgo`, `consent_footnote`, `unitsM`/`unitsKm`
  exist both langs; Hindi nav instructions rebuilt road-first
  verb-final; roundabout ordinals mapped; dayparts hand-composed
  (सुबह/दोपहर/शाम/रात); no script mixing except findings above.
- **Design law** — zero `fontSize < 11` (floor = `V2Type.micro` 11;
  `label-1` = 12); borderWidth only on selection/division/emptiness;
  accent = small forest only; band colors only where color encodes air
  (routeTint pmColor, tier washes, band words); Satoshi/FSERIF/FMONO +
  Devanagari family discipline everywhere.
- **State machine** — every overlay owns an explicit BackHandler
  (search/settings/delhi/ledger/sidebar close; onboarding traps
  intentionally — consent is required); all `setInterval`s have
  cleanups; pending-plan flags + preserveIdx cover the async
  selection-swap race; `outcome != null && !navigating` gates prevent
  sheet-on-sheet overlap.
- **Edge cases** — "0 µg" never faked (0–0 collapse in NavChrome,
  `inhaled.lo>0` range gate in DelhiToday, strip-failure freeze);
  thin-week unmounts rather than rendering stubs; T0 gazetteer is a
  real 2.7MB bundled corpus with 75m dedupe; offline reverse-geocode
  names nearest *real* place only; contributor id rotates without
  touching history.

**Not verified here** (out of a read audit's reach): runtime SIGSEGV
repro (finding #3 — code is clean, the sim run said otherwise);
server-side behaviour of POST endpoints (GET-only mandate; server lanes
own that); `FieldLayer`'s future-lane intent.
