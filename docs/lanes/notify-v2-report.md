# notify-v2 — cause-aware event kinds lane report

Mandate: the notify-v2 lane brief — audit the events engine shipped in
`4d20990`, then add cause-aware kinds only where the served data carries
them. Built on `base/v2` (`341126f`), verified on iPhone 17 / iOS 26.5
simulator against the live backend (`http://65.2.28.40`).

## What shipped

| piece | file | what it does |
|---|---|---|
| pure detectors | `Mobile/src/store/events-core.ts` (new) | every threshold + the re-ping ladders in one fetch-free module — `fired()`, `trendShift()`, `grapMove()`, `outlookMove()`, `reflectSummary()`, `causeClause()`, `feedLive()` |
| detector tests | `Mobile/src/store/events.test.ts` (new) | 33 node:test cases — every new kind's fire path AND its silence paths |
| engine wiring | `Mobile/src/store/events.ts` | four new blocks (trend, grap-move, outlook, reflect) + feed-stall record; existing blocks audited (fixes below) |
| kinds + keys | `Mobile/src/notify.ts` | `AirEventKind` + `EV_KEYS` extended: `trend_up/down`, `grap_up/down/clear`, `outlook_heavy/light`, `reflect` |
| copy | `Mobile/src/i18n/strings.ts` | en+hi pairs for all eight titles/bodies + three cause clauses + reflect compare fragments + one new settings row |
| settings | `settings.ts`, `SettingsScreen.tsx` | `alerts_reflect` toggle (default on, greyed under the master); trend+grap ride `alerts_band` ("air turning worse"), outlook rides `alerts_windows` — hints updated to say so |

## Kinds table — trigger → signal → threshold → copy → dedupe → verified

| kind | signal field (verbatim from the wire) | threshold | copy (en / hi) | dedupe (per UTC day) | how verified |
|---|---|---|---|---|---|
| `trend_up` / `trend_down` | `/v2/why` `drivers[kind=trend].direction` + `evaluated.trend.{from_pm25,to_pm25,span_h,delta_ug}` | server's own admission only — it fires the driver past Δ≥12 µg/6 h/≥3 builds/≤2.5 h-fresh; client never re-derives | "the city's air is climbing · {a} → {b} µg/m³ over {h}h{cause}" / "शहर की हवा भारी हो रही है · {h} घंटे में {a} → {b} µg/m³{cause}" | re-ping at +12 µg new move | unit tests (up/down/no-driver/no-endpoints/no-direction); live today: `delta_ug=-0.4`, driver absent → correctly silent |
| `grap_up` / `grap_down` / `grap_clear` | `/v2/day` `grap.equivalent_stage` vs persisted baseline | stage transition both ways; arrival into ≥III stays `severe`'s; first read silent | "the day moved up a GRAP step · our read now maps to stage {s} (aqi ~{a}) — computed from today's air, not the official call" / hi mirror | same arrow at same stage = same claim (silent); different stage re-pings | unit tests (0→1 up, 2→3→severe, 4→0 clear, null-baseline silent); sim: seeded `grapStage:3` → live stage 0 → `grap_clear` banner |
| `outlook_heavy` / `outlook_light` | `/v2/outlook` `days[label=tomorrow].pm25_mid` vs `days[today]` | ±max(15 µg, 15%) — the server's own flat floor; silent on `n_hours<6` or `confidence=lo`; IST 17:00–22:00 only | "tomorrow reads heavier · avg ~{b} µg/m³ vs ~{a} today{cause}" / "कल की हवा भारी दिख रही है · औसत ~{b} µg/m³ बनाम आज ~{a}{cause}" | re-ping only on a ≥15 µg forecast revision | unit tests (±30% fire, sub-floor silent, sliver silent, lo-conf silent, window gate); live: today 68 → tomorrow 117 is +72% but it's ~09:30 IST — outside the evening window, correctly silent |
| `reflect` | the on-device ledger (`ledger.json`) — yesterday's own trips | ≥1 real trip yesterday; compare = nearest earlier trip-day within 7 days, ±15% flat bar | "yesterday on the road · {n} trips · about {u} µg inhaled{cmp}" / "कल सड़क पर · {n} यात्राएँ · करीब {u} µg साँस में{cmp}" | once a day, never re-pings | unit tests (sum+compare, skip-empty-days, no-yesterday silent, today excluded, zero-dose ignored); sim: seeded yesterday rows → banner |
| feed-stall (record, not a kind) | `/v2/why` `evaluated.fires.feed_age_s` vs `feed_stale_after_s` + `/v2/day` `field.stale` | past the feed's own staleness bound | — (never a notification) | written to `events.json` `feedHealth` only on state change | unit tests (live/stale/no-bounds); code path — both feeds healthy today |

`{cause}` = `causeClause()`: names only drivers the server admitted right
now — `stubble_smoke` gets its served compass sector ("stubble smoke riding
the north-west wind" / "उत्तर-पश्चिम हवा पर पराली-धुआँ"), `stagnation` is
"the air barely moving to clear it". No admitted driver → empty string,
never a guessed cause. Present tense — it describes what's driving today's
air, not a forecast of tomorrow's met.

## Audit fixes to the shipped engine

1. **`window` re-ping spam** — the old dedupe re-pinged on *any* revised
   start minute; a 1-minute forecast revision re-notified the same window.
   Now a revision must move ≥30 min (`WINDOW_REPING_MIN`).
2. **`fires`/`fires_nc` double-ping on a wind flip** — they were separate
   ladders: 20 fires pinged as `fires`, the wind read flipping
   `carrying:false` re-pinged the same 20 as `fires_nc`. Now both kinds
   share one mark — the higher of the two is the bar (`fire()` mark
   override).
3. **`stagnation` marginal stillness** — it fired whenever the driver was
   admitted (server floor ≈1.25×). "Barely mixing" would ping most winter
   days → daily spam. Now needs `detail.factor ≥ 1.5` on top of primary
   admission, re-ping at score +0.2.
4. **`band` unchanged** — crossing-up into Poor+ with a fresh baseline is
   honest; today's air (idx ≤ 2 all day) correctly never claimed it.

## Dedupe semantics (`fired()` in events-core.ts)

One `seen[kind] = {day, level}` per kind; a new UTC day resets all. Within a
day: fires +max(15, 50%) · band/severe strictly higher · stagnation +0.2
score · window ≥30-min start move · trend +12 µg · grap arrows re-ping only
on a different stage under the same arrow · outlook ±15 µg revision ·
reflect never.

## Verified on sim (iPhone 17, iOS 26.5, live prod)

Fresh dev-client install, `EXPO_PUBLIC_API_URL=http://65.2.28.40`, events
baselines seeded into `Documents/events.json` (the on-device state file —
a stored prior is the only way to show a jump within one session),
yesterday's trips seeded into `Documents/ledger.json`. Device captures in
`docs/assets/notify-v2/` — every banner below fired off live served reads:

- `fires-nc-banner.png` — "fires up in the burn belt / 4 → 20 fires
  northwest — the wind isn't bringing it to Delhi right now": live
  `belt_fires:20, carrying:false` vs seeded baseline 4 → +16 ≥ +15.
- `stagnation-banner.png` — "the air is sitting over the city / barely
  mixing — 2× stiller than usual; expect the day's smoke to linger":
  un-seeded, live primary driver factor 1.91 ≥ 1.5.
- `grap-clear-banner.png` — "the day eased off the GRAP map / our read no
  longer maps to a stage (aqi ~129) — still our computed read": seeded
  `grapStage:3` vs live `equivalent_stage:0`.
- `window-banner.png` — "easiest hours ahead / today's lightest air
  ~09:30–17:30 IST · about 58 µg/m³": un-seeded, IST-now inside the lead.
- `reflect-banner.png` — "yesterday on the road / 2 trips · about 84 µg
  inhaled — heavier than Saturday (60 µg)": seeded ledger rows; the
  compare clause names the nearest earlier trip-day within 7 days.
- `settings-rows.png` — Notifications card with the new "your day on the
  road" row under the existing three; `settings.json` persisted
  `alerts_reflect:true` on toggle.
- `events.json` post-check `seen` held marks for all five kinds at their
  real levels (`fires_nc:20`, `stagnation:75`, `grap_clear:0`,
  `window:570`, `reflect:1`) — the dedupe store proves every fire.

Honest silences today (checked against live probes): `trend_*` — server
admitted no trend driver (Δ −0.4 µg under the 12 µg floor); `outlook_*` —
~09:25 IST, outside the 17:00–22:00 gate (the fold itself was
heavy-tomorrow +72%, so the gate — not the data — is what silences it);
`severe` — equivalent stage 0; `band` — ambient ~59–68 µg never crossed
Poor; `fires` — `carrying:false`, only `fires_nc` could claim.

**One observed loss, honestly described**: on the seeded launch that ran
~20 s after the first-ever OS permission grant, `fires_nc` met its rule
(baseline refreshed 4 → 20) but no mark landed and no banner delivered,
while the four later kinds in the same check marked fine. The identical
re-seed three minutes later fired + marked + bannered (`seen.fires_nc:20`,
screenshot above). The only difference between the two launches was the
fresh-install permission window, so the probable cause is a permission
state still settling at that first read — I could not reproduce it to
prove the exact call that dropped it. Baselines are "last observed" by
design, so a jump consumed under an undelivered ping can't re-claim —
accepted semantics, logged here so a repeat sighting gets chased.

## Honest limits

- All pings are foreground-poll only (60 s `aqiPoll`) — unchanged, and the
  settings hint still says so.
- `outlook_*` is evenings-only by design; verified by unit tests + the
  gate, not by a banner (was ~09:30 IST).
- `/v2/why` still throttled to 10 min — trend/stall read on that cadence.
- feed-stall is a *record* for a diagnostics surface that doesn't exist
  yet — it lands in `events.json`, readable the day one ships. Nothing
  user-facing.

## Gates

`npx tsc --noEmit` clean · `npx expo lint` clean · `node src/store/test-runner.mjs`
53/53 pass.
