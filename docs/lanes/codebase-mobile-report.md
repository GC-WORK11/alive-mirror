# codebase-mobile — code-truth pass, split B (Mobile)

Lane: `codebase-mobile`. Pass 2026-10-07 ~09:50 UTC. HEAD `9fbd851` + lane fixes.
Scope: `Mobile/` (Expo RN). Correction to the brief: there is no `src/app/`
and no expo-router — navigation is the phase state machine in `App.tsx` +
`src/components/shell/useShellFlow.ts` (`idle|search|compare|nav` + overlay
flags). `Mobile/AGENTS.md`'s Expo Router section is stale docs-debt (the
deadcode lane already flagged it).

## Gates (re-run at this HEAD, not just trusting script-guard)

| gate | result |
|---|---|
| `npx tsc --noEmit` | exit 0 (script-guard reported green at f9ea5ae; re-verified at 9fbd851) |
| `npx expo lint` | exit 0 |
| `node src/{store,nav,api,offline}/test-runner.mjs` | 170/170 pass (76+76+12+6) |

## Inventory — every screen/component traced to a mount + data source

Screens (`src/screens/`):

| file | reachable | data source | verdict |
|---|---|---|---|
| WelcomeScreen.tsx | introSeen gate, welcome_seen_v1 | `GET /v2/city` pm25_stats.mean + ambient fallback | real — honest null frame ("never faked"), no fake figure |
| OnboardingScreen.tsx | introSeen === false | saveConsent → consent.json | real |
| HomeScreen.tsx | homeOpen (default surface) | daylog.json reconstruction + daysum rollup + fetchDayCurve (`/v2/day` → `/grid` fallback) + `/v2/outlook` | real — holes not guesses, stale aged honestly |
| SearchScreen.tsx | phase==="search" | ServerSearch `/v2/geocode` (abort/debounce/seq) + T0 bundled gazetteer + places.json recents | real — EMPTY_TIERS on dead network, no fabricated rows |
| SettingsScreen.tsx | settingsOpen | settings.json + `POST /v2/feedback` (rate) — **verified live on prod: 200** | real |
| LedgerScreen.tsx | ledgerOpen | ledger.json + daysum | real |
| DelhiToday.tsx | delhiOpen | `/v2/city` | real |
| VehicleSheet.tsx | vehicleOpen / wizArmed / CompareSheet-internal | vehicle.json → saveVehicle | real |

Shell (`src/components/shell/`):

| file | reachable | data source | verdict |
|---|---|---|---|
| SearchBar.tsx | idle chrome | chrome only | real |
| Sidebar.tsx | sidebarOpen | settings + ledger week + todayUg; every section data-gated | real — unwired rows hidden |
| CompareSheet.tsx | phase==="compare" | `/v2/plan` options + departCurve (`/v2/day`/`/grid`) + vehicle.json | real — degraded-arms honest banner, planError typed |
| NavChrome.tsx | phase==="nav" | useNavEngine live counters (dose/co2 Bands, etaS, offRoute) | real — `doseUg` prop is a documented dead-compat path (finding D1) |
| ReceiptSheet.tsx | nav summary !== null | engine NavSummary | real — mounts only on real arrival |
| CheckinSheet.tsx | HomeScreen | setCheckin → daylog.json | real |
| HourArc.tsx | HomeScreen + WeekStrip | daylog reconstruction | real |
| WeekStrip.tsx | HomeScreen | daysum rollup | real |
| LayersSheet.tsx | layersOpen | lazy fetch `/fires` `/blackspots` `/community` on first enable | real |
| LayersButton/LocateButton.tsx | idle chrome | chrome only | real |
| net.ts / settings.ts / types.ts / useShellFlow.ts | infra | — | real |

Components (`src/components/`):

| file | reachable | data source | verdict |
|---|---|---|---|
| ReportsLayer.tsx | MapTree always-mounted | `GET /reports` 60 s poll → reconcileReportSlots pure reducer | real — pool exhaust drops, never fakes |
| CorridorLayer.tsx | MapTree | `/community` top_corridors | real |
| HazardLayers.tsx | MapTree | `/fires` + `/blackspots` | real |
| RouteTint.tsx | MapTree (compare) | `/v2/strip` per option → fieldAtAlongM | real — failure leaves flat tint, never faked |
| FreshnessChip.tsx | idle + HomeScreen | `/aqi` field block age_s | real — null-safe, honest stale |
| DepartGraph.tsx | CompareSheet | departCurve.slots | real |
| BandScale.tsx | DelhiToday/HomeScreen | CPCB band idx | real |
| CityMoves.tsx | DelhiToday | `/v2/city` | real — honest mid-line on load fail |
| PressSpring.tsx | everywhere | gesture primitive | real |

Infra: api/{plan,city,dayfield,depart,outlook,strip,reroute,cache},
nav/{engine,strip,counters,offroute,speech,instructions,index},
offline/{net,queue,status,index}, store/{ledger,daylog,daysum,consent,
vehicle,welcome,events,events-core,safefile,localize}, search/{client,t0,
recents,CategoryIcon}, map/{style,tileWarm,routeTint,cam,drawHold},
startup/{idle,marks}, community, notify, perf, haptics, theme, icons,
ui, a11y, i18n/strings — all imported, all real. **Zero orphaned files**
(a11y/index, nav/index, offline/index are directory barrels; index.ts is
the entry).

## Fake-hunt

`mock|dummy|fake|placeholder|lorem|TODO|FIXME` over src/: every hit is an
honesty-contract comment or a legitimate `placeholderTextColor` prop.
No mock arrays, no fetch-fail fallback data, no hardcoded figures rendered
as data. The failure idioms are consistent: skeletons, honest-empty states,
last-good-stale labelling, `fetchCached` "never throws — failure is data",
`throw` on uncovered curve so last-good survives. Verified-clean.

## Findings (severity-ranked; nothing deleted per owner rule)

**Fixed this pass — unambiguous real bugs**

1. **`settings.remind` was a dead master switch.** The Settings row wrote
   the flag but nothing read it: CompareSheet still offered the remind row
   and `remind()` scheduled the OS ping regardless; toggle-off also never
   cancelled an already-armed departure ping. Fix: `remindEnabled` prop
   gates the row (CompareSheet), new `disarmDepart()` (flow: cancelDeparture
   + reset `notified` so re-on doesn't claim a dead ping), called from
   `patchSettings` on `remind === false`. The offer + the OS are now both
   bound to the switch.
2. **`brief` toggle-off left the scheduled `alive-daily-brief` firing.**
   `cancelDailyBrief` existed but was never called. `patchSettings` now
   cancels on `brief === false`.
3. **delete-my-data left scheduled OS pings armed.** `deleteAll` now calls
   `disarmDepart()` + `cancelDailyBrief()` inside the wipe — pending pings
   carry the wiped trip/brief context.

**Reported — not fixed (out of lane's unambiguous-bug scope)**

- **MED — no React error boundary anywhere.** A render throw inside any
  sheet/map child crashes to the OS. The throw-free store/API contract
  (`fetchCached`, safefile) covers async paths, not render. Candidate for
  a dedicated lane (needs a designed fallback surface).
- **LOW — `navDose` dead plumbing.** `useShellFlow` still returns
  `navDose` (useState(0), documented as kept-for-compat); App.tsx never
  destructures it and passes literal `doseUg={0}` into NavSession — dead
  once `nav` prop is always present. Deletion would touch the documented
  pre-integration compat seam — listed, not removed.
- **LOW — `community.ts:38` `Math.random()` fallback** for contributorId
  if `crypto.getRandomValues` throws (CSPRNG is primary; fallback only on
  crypto failure). Anon-id quality degrades silently; no privacy leak
  (id is random by design either way).
- **LOW — ~70 exported symbols never imported outside their own module.**
  Mostly types + module-internal constants/helpers with an unnecessary
  `export` (e.g. `BreathEdge`, `FSERIF`, `PM25_BREAKS`, `FH`,
  `dumpMarks`, `invalidateAllDays`, `fetchTiers`, `SEARCH_TIMEOUT_MS`,
  `EMPTY_TIERS`, `JankResult`, `V2_TILES_ENV`, `v2Style`…). Dead-export
  weight, not dead code — internal uses are real. Full list reproducible
  via the export-vs-import sweep in this lane's notes.
- **INFO — `Mobile/AGENTS.md` stale**: claims Expo Router + `src/app/`;
  actual nav is the phase state machine. Also flagged by deadcode lane.
- **INFO — `/v2/feedback` is LIVE on prod** (POST → 200
  `{"stored":true,"total_reviews":2}`); the Settings rate feature is real.
  Corrects the stale "410-retired" claim in memory/lane lore.

## Crash-hygiene audit

All `void (async …)` / `void fn()` sites traced: awaited calls carry
`.catch(() => null)` or sit inside try; `fetchCached`/`readJsonDoc`/
`writeJsonDoc` never reject ("failure is data") so no practical
unhandled-rejection path exists in the depart/community/nav/store flows.
The one real gap is the missing error boundary (above).

## Diff this lane

- `App.tsx`: import `cancelDailyBrief`; destructure `disarmDepart`;
  `patchSettings` cancels on remind/brief off; `deleteAll` disarms;
  `remindEnabled={settings.remind}` to CompareSheet.
- `src/components/shell/useShellFlow.ts`: `disarmDepart` (cancel + reset
  `notified`); export it.
- `src/components/shell/CompareSheet.tsx`: `remindEnabled` prop gates the
  depart-remind row.
