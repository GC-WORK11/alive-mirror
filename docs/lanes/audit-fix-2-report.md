# audit-fix-2 lane — the ugly tier + jargon structural flags

Owns everything `component-audit-report.md` did NOT assign to the
audit-fix lane (that lane's commit e1e9d22 claimed #1–5, #10, #21, #22,
#24 — untouched here), plus the copy-fixable structural items from
`jargon-sweep-report.md`'s flagged table. Read both reports first;
nothing in audit-fix's scope is re-fixed.

Rig: iPhone 17 sim (`E0224A22`, iOS 27.0), dev client + Metro
(`EXPO_PUBLIC_API_URL=http://65.2.28.40`), sim geo 28.6139,77.2090.
Shots in `shots/audit-fix-2/`. Gates: `npx tsc --noEmit` clean,
`npx expo lint` clean, test runners 84/76/17/16 pass — 0 fail.

## Search drops characters on fast typing (audit #17) — FIXED

Before: typing "india gate" fast rendered "indiate" and ranked a junk
POI ("INDIATECH247 computer shop") first — the audit's own repro.

Root cause (verified, not guessed): each keystroke runs `setQ(text)`
as an URGENT commit that re-rendered the whole component — ~25 rows,
each `Title` doing regex-split highlight math. While JS was mid-render
the native field re-asserted the last committed value over the
in-flight keystroke → characters dropped. A `startTransition` on the
secondary state (tried first) wasn't enough — the urgent commit still
walked every row synchronously.

Fix (`SearchScreen.tsx`): `useDeferredValue(q)` drives the query work
(`t0query`, `ServerSearch.setQuery`, `merged`, `serverRows`, `typing`,
`pending`, `empty`, the row `query` highlight prop). Both list
branches (results / saved+recents) are memoized element TREES — the
urgent keystroke commit reuses identical element objects and bails at
the subtree root, so the echo path repaints only the pill. `renderPlace`
is a `useCallback` so the memo deps are stable.

Verified live: after Fast Refresh, "india gate" typed in one go —
every character landed, "India Gate Entry" (Kashturba Gandhi / Shahjahan
Road) ranked top-2 (`search-india-gate-all-chars.png`). Second pass
"connaught place" — all 15 chars, Connaught Place rows ranked,
matched-prefix highlight intact (`search-connaught-place.png`).

## One clock everywhere (jargon flag: 24h/12h split) — FIXED

New helpers at the bottom of `strings.ts`:

- `clockLabel(d)` → "4:42 pm" / "4:42 अपराह्न" — the verbose form
  (Ledger rows, receipts).
- `clockTight(d)` → "4:42pm" — compact form (header, depart graph,
  daylog stays, ETA).
- `hourLabel(d)` → "4pm" / "4 बजे" — whole-hour form (arc ticks,
  "heaviest from ~8pm").
- `wireClockLabel(s)` — rewrites every `HH:MM` token inside a SERVED
  string to 12h and strips the trailing ` IST` (the device clock is
  already local). Applied to server `start_label`/`end_label`
  windows, outlook `compactHours`, event `window`/`outlook` fires.

Callers converted: LedgerScreen (`cigLine` + row times), NavChrome
ETA (`clock(etaS)`), DepartGraph (`dateOf`/`hourLabel`/`clockTight`
labels), daywords `compactHours` + `shortDate`, daylog stay labels,
HomeScreen `fmtHr` + header clock, CompareSheet `arrivalLabel`,
HourArc scrub strings, DaysAhead window labels.

daylog.test.ts updated for the intentional format change
("8:00am–8:25am" was "08:00–08:25").

## Jargon structural items — copy-fixable set

- **fake-exact decimals on served species** — DelhiToday species tiles
  + the "why this is an estimate" band edges now `Math.round` —
  `285.2 µg/m³` → `285`, `0–237.5` → `0–238`. A kriged city field
  doesn't carry tenths; printing them was fake precision.
- **US AQI tile** — kept + framed (design intent: it's the index
  other air apps quote — judge-facing comparison). New
  `citySpeciesNote` line: "US AQI is the index other air apps
  quote" + the tile's own `0–500 scale` gloss (hi mirrors both).
- **GRAP roman numerals** — `grapStageLabel()` in `events.ts`
  renders "stage 2 of 4" (hi "चरण 2 / 4") for severe + band
  notifications. The wire stage number was already plain; only the
  numeral styling died.
- **`<0.01 cigarettes`** — `cigsTrace` "a trace of a cigarette" /
  hi "सिगरेट का नामो-निशान" — wired in Ledger hero, NavChrome dose
  card, ReceiptSheet `cigTxt`, App.tsx share-trip path, and
  `receipt_pmBandTiny` ("includes a trace of fine dust (PM2.5)").
- **`÷{o}` pax notation** — `emit_perPax` now reads ", per rider
  ({o} aboard)" (hi ", प्रति सवार ({o} सवार)") — the ÷ glyph is gone.
- **`receipt_lessVs` "2.3× less"** — new `smokeFraction(ratio)`
  helper maps the dose:worst ratio to the nearest common fraction
  word within 13% ("about a third of walking" / hi "पैदल की तुलना
  में लगभग तिहाई धुआँ"). Ratios between common fractions (7.3×)
  honestly keep the × form — a fake "a seventh of" reads worse.
  Also gated on `fullRun`: an ended-early stub no longer claims an
  inflated ratio.
- **`why.line` en rebuild** — dropped the `lang === "en"` passthrough
  in `DelhiToday.tsx whyLine()`; en now rebuilds from `drivers[]`
  the way hi already did, so a future unit/decimal leak in the wire
  grammar can't reach the surface.
- **`~{win} IST` on notification windows** — `wireClockLabel` strips
  ` IST` and converts to 12h, so the hi string carries no Latin
  token.
- **'Bus CGOCOMPLEX-2' raw line ids** — DEPLOY-PENDING server fix
  (prod is GET-only; committed, not deployed):
  `server/transit_v2.py` `line_name()` maps all-caps feed-internal
  ids (`^[A-Z0-9_-]{9,}$` — real route numbers like `347ACL` and
  board names like `HOHO` survive) to plain "Bus"; `DTC "347AUP"`
  gets the UP/DOWN suffix stripped → `347A`. `server/v2/plan.py`
  `_transit_option` drops `?`/`Bus` from the `lines` join so the
  receipt alt reads "Bus 347A → Metro", never "Bus CGOCOMPLEX-2".

## Audit 'ugly'/'nit' tier — the rest

- **#6 dead OSM attribution** — `App.tsx` `logoPosition`/`attribution`
  moved to `insets.bottom + 164` — above the DayPeek card, tappable.
  Verified live: ⓘ visible + pressable with DayPeek open.
- **#8 DayPeek dead press** — press on the "your day so far" card now
  returns to Home (was a silent no-op-looking card). Verified: tap →
  home screen.
- **#9 raw ISO date** — outlook expanded header renders via
  `shortDate` ("Friday, Oct 9") instead of `{open.date_ist}`
  verbatim.
- **#12 header clock a minute stale** — the home header tick moved
  from a 30 s interval to 1 s aligned tick; verified live (1:16 →
  1:20 → 1:22 pm tracked the status bar).
- **#13 week-strip a11y lie** — uncounted day cells expose
  `weekNoReads` ("nothing logged") instead of the "T 0" the code
  refuses to print.
- **#14 duplicated freshness** — the incidents card's `ageLine` is
  gated on `outlook.fieldStale` — one freshness line per screen, not
  two.
- **#16 two "the air" numbers** — DelhiToday hero appends
  `cityHeroAirNow` ("city average now ~94 µg/m³") and the species
  block carries `cityBasisPm25Ug` ("the raw number behind the hero
  figure") — the 94-vs-62 pair reconciles on the surface itself.
- **#15 "+" mid-sentence** — DelhiToday's prose "+" → "and" via the
  en rebuild; WHO cells already carry the species note.
- **#18 recents truncate mid-word** — `rowSub` got
  `adjustsFontSizeToFit minimumFontScale={0.75}` + `numberOfLines={1}`
  — long official names shrink whole rather than clip.
- **#19 "Your location" silent no-op** — `useShellFlow` guards a
  <50 m self-pick with `pickTooClose` ("that's about {n} m away —
  basically here; no route needed") instead of silently ignoring it.
- **#20 50 m pin → full compare** — same guard on choose-on-map: a
  pin within 50 m of origin doesn't spin up the full compare +
  depart graph.
- **#23 depart graph on trivial trips** — DayStrip bars guard
  `km >= 0.5`; sub-500 m trips don't render an 8-bar day curve.
- **#25 turn-by-turn cramped "0 µg" tick** — NavChrome `cellBand`
  marginBottom 7 — the scale floor no longer touches the arrive meta.
- **#26 "≈ 0.4 µg about" dangling qualifier** — `receipt_estShort`
  "about" now precedes the number; verified string order in Receipt.
- **#27 "Bicycle · 10m" reads as duration** — `timeAgo` renders the
  full phrase now (`agoMin` "{n} min ago"), so the row reads
  "Bicycle · 10 min ago" — no longer ambiguous with ride length.
- **#28 expander opens mid-clipped** — Sidebar scroll-to-end moved to
  a `useEffect` on `[section, reduceMotion]` with 120/340 ms
  timeouts, so "How ALive works" scrolls its tail into view.
  Verified live: expand → paragraph lands fully visible.
- **#29 double share-explainer** — `shareDataHint` rewritten to the
  one-line honest form "on — one tap to stop anytime" (the
  `settingsShareExplain` line keeps the why); the two lines no longer
  say the same thing.
- **#30 notifications parent hint** — `settingsAlertsHint` now names
  the relationship plainly ("the master switch for the alerts
  below") instead of re-listing the events the sub-toggles own;
  `morningAlert` capitalized "Morning air alert" like its siblings.
- **#31 dead-looking units row** — `settingsUnitsInfo` adds the info
  line under "km / metric" so it reads as an explanation, not a
  disabled toggle.
- **#33 "Your trips" → "Trips"** — door label and ledger title now
  agree.
- **#35 pure-black welcome stage** — `WelcomeScreen` ROOM `#14110E` —
  warm-neutral-adjacent, not pure black (design law).

## Left alone on purpose

- **#11 pull-to-refresh vs scroll** — the audit itself says "no
  complaint if intentional"; the pull is the designed refresh
  gesture. Unchanged.
- **why.line / cause_note server grammar** — the wire still serves
  engineering grammar (`m²/s`, `38.9 → 80.1`); the client rebuilds
  everywhere a surface reads it. Rewriting the wire is a server
  lane's job, not a copy fix — flagged onward.
- **NCR bbox three-way divergence** (hardcode hunt) — t0/net/
  tileWarm carry different NCR bounds. Single-sourcing is a shared
  constant refactor touching the warm path; deferred, reported.
- **`WHO_DAILY_UG` duplication + DayPeek `budgetUg=216` re-hardcode**
  — correct values, drift risk noted; same shared-constant cleanup.
- **`fmtCig` kept opt-in** — "a trace" now carries the <0.01 case;
  the full metaphor stays behind `show_cig` per owner design.
